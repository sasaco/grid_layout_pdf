"""SideRule draws a vertical rule beside a block, part by part, so that it follows page breaks."""

from dataclasses import dataclass, replace

import pytest

import gridlayoutpdf
from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, Document, FontRegistry, KeepWithNext, LayoutContext,
    LayoutOverflowError, LayoutPart, Line, MeasuredBlock, Rectangle, ReportStyle, SideRule, Spacer, Text,
    TextMetrics, measure_block,
)


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * .6, style.size * .8, style.size * .2)


FONTS = FixedFonts()
CONTEXT = LayoutContext(FONTS, A4_PORTRAIT_REFERENCE, ReportStyle())
PITCH = A4_PORTRAIT_REFERENCE.grid.pitch_y
SMALL = replace(A4_PORTRAIT_REFERENCE, name="five-body-rows", body_end_row=5)


@dataclass(frozen=True)
class PartsBlock:
    part_rows: tuple[int, ...]
    block_id: str = "block"
    width: float = 60.0
    prefix_rows: int = 0

    def measure(self, context, available_width):
        def part(rows, index):
            return LayoutPart(rows, (Text(20, 11, str(index), context.style.body),), {"n": index})
        prefix = (part(self.prefix_rows, -1),) if self.prefix_rows else ()
        return MeasuredBlock(self.width, context.profile.grid.pitch_y,
                             tuple(part(rows, index) for index, rows in enumerate(self.part_rows)),
                             prefix=prefix, min_first=1, min_last=1, block_id=self.block_id)


def rules(part):
    return [command for command in part.commands if isinstance(command, Rectangle)]


def test_every_part_gets_a_rule_over_its_whole_height():
    measured = measure_block(SideRule(PartsBlock((1, 2, 1)), 10, style=gridlayoutpdf.BorderStyle.MEDIUM), CONTEXT, 100)
    for part, rows in zip(measured.parts, (1, 2, 1)):
        rule, = rules(part)
        assert (rule.x, rule.y, rule.width, rule.height) == pytest.approx((10 - .5, 0, 1, rows * PITCH))
        assert (rule.stroke, rule.fill) == (False, (0, 0, 0))
        assert part.commands[:-1] == measure_block(PartsBlock((1, 2, 1)), CONTEXT, 100).parts[
            part.metadata["n"]].commands
        assert part.metadata["side_rule_pt"] == 10
        assert part.metadata["side_rule_style"] == "medium"


def test_top_and_bottom_shorten_only_the_first_and_last_parts():
    measured = measure_block(SideRule(PartsBlock((1, 2, 1)), 10, top=3, bottom=2), CONTEXT, 100)
    first, middle, last = (rules(part)[0] for part in measured.parts)
    assert (first.y, first.height) == pytest.approx((3, PITCH - 3))
    assert (middle.y, middle.height) == pytest.approx((0, 2 * PITCH))
    assert (last.y, last.height) == pytest.approx((0, PITCH - 2))
    single, = measure_block(SideRule(PartsBlock((1,)), 10, top=3, bottom=2), CONTEXT, 100).parts
    assert (rules(single)[0].y, rules(single)[0].height) == pytest.approx((3, PITCH - 5))


def test_a_repeating_prefix_is_ruled_over_its_whole_height():
    measured = measure_block(SideRule(PartsBlock((1,), prefix_rows=1), 10, top=3, bottom=2), CONTEXT, 100)
    prefix, = measured.prefix
    assert (rules(prefix)[0].y, rules(prefix)[0].height) == pytest.approx((0, PITCH))
    assert (rules(measured.parts[0])[0].y, rules(measured.parts[0])[0].height) == pytest.approx((3, PITCH - 5))


def test_flow_flags_and_width_are_kept_and_a_spacer_rule_is_dropped_with_it():
    child = measure_block(KeepWithNext(Spacer(2, discard_at_page_top=True)), CONTEXT, 100)
    ruled = measure_block(SideRule(KeepWithNext(Spacer(2, discard_at_page_top=True)), 10), CONTEXT, 100)
    assert (ruled.keep_with_next, ruled.discard_at_page_top, ruled.width) == (True, True, child.width)
    assert len(rules(ruled.parts[0])) == 1
    pages = Document(PartsBlock((5,), "a"), SideRule(Spacer(2, discard_at_page_top=True), 10),
                     PartsBlock((1,), "b"), fonts=FONTS, profile=SMALL).layout()
    assert [len(page.metadata["placements"]) for page in pages] == [1, 1]
    assert not any(isinstance(command, Rectangle) for page in pages for command in page.commands)


def test_the_rule_breaks_with_the_page_and_continues_at_the_next_page_top():
    pages = Document(SideRule(PartsBlock((2, 2, 2), "ruled"), 10, top=3, bottom=2), fonts=FONTS,
                     profile=SMALL).layout()
    found = [[command for command in page.commands if isinstance(command, Rectangle)] for page in pages]
    assert [len(page) for page in found] == [2, 1]
    first, second = found[0]
    assert first.y + first.height == pytest.approx(second.y)  # one continuous rule on the page
    assert (first.height, second.height) == pytest.approx((2 * PITCH - 3, 2 * PITCH))
    last, = found[1]
    text, = [command for command in pages[1].commands if isinstance(command, Text)]
    assert (last.y, last.height) == pytest.approx((text.y - 11, 2 * PITCH - 2))  # from the next page top


def test_a_child_narrower_than_the_rule_is_widened_up_to_the_available_width():
    measured = measure_block(SideRule(PartsBlock((1,), width=30), 50, style="medium"), CONTEXT, 100)
    assert measured.width == pytest.approx(50.5)
    with pytest.raises(LayoutOverflowError, match="rule"):
        measure_block(SideRule(PartsBlock((1,), width=30), 99.8, style="medium"), CONTEXT, 100)


def test_the_default_style_is_thin():
    assert SideRule(PartsBlock((1,)), 10).style is gridlayoutpdf.BorderStyle.THIN
    rule, = rules(measure_block(SideRule(PartsBlock((1,)), 10), CONTEXT, 100).parts[0])
    assert (rule.x, rule.width) == pytest.approx((9.75, .5))


def test_a_double_rule_is_two_bars_whose_centres_are_one_pt_apart():
    part, = measure_block(SideRule(PartsBlock((2,)), 10, style="double", top=3), CONTEXT, 100).parts
    left, right = rules(part)
    assert [(bar.x, bar.width) for bar in (left, right)] == pytest.approx([(9.25, .5), (10.25, .5)])
    assert all((bar.y, bar.height) == pytest.approx((3, 2 * PITCH - 3)) for bar in (left, right))


def test_a_dashed_rule_is_a_dashed_line_kept_inside_each_part():
    measured = measure_block(SideRule(PartsBlock((1, 1)), 10, style=gridlayoutpdf.BorderStyle.MEDIUM_DASHED, top=3),
                             CONTEXT, 100)
    first, second = ([c for c in part.commands if isinstance(c, Line)] for part in measured.parts)
    assert first == [Line(10, 3, 10, PITCH - .5, 1, dash=(6, 2))]
    assert second == [Line(10, .5, 10, PITCH - .5, 1, dash=(6, 2))]
    assert not rules(measured.parts[0])


@pytest.mark.parametrize("options", [
    {"x": -1}, {"x": float("nan")}, {"x": .2}, {"x": .7, "style": "thick"}, {"x": 10, "style": .72},
    {"x": 10, "style": 1}, {"x": 10, "style": None}, {"x": 10, "style": True}, {"x": 10, "style": "solid"},
    {"x": 10, "top": -1}, {"x": 10, "bottom": float("inf")}, {"x": 10, "color": "black"},
])
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValueError):
        SideRule(PartsBlock((1,)), **options)


def test_the_old_pt_width_keyword_is_gone():
    with pytest.raises(TypeError, match="width"):
        SideRule(PartsBlock((1,)), 10, width=.72)


def test_a_dashed_rule_with_no_room_inside_its_part_is_rejected():
    with pytest.raises(ValueError, match="no dashed rule"):
        measure_block(SideRule(PartsBlock((1,)), 10, style="dashed", top=PITCH - .1), CONTEXT, 100)


def test_a_rule_shortened_to_nothing_is_rejected():
    with pytest.raises(ValueError, match="top and bottom"):
        measure_block(SideRule(PartsBlock((1,)), 10, top=PITCH, bottom=0), CONTEXT, 100)
