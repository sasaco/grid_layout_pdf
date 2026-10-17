"""Flow-rule, indentation and line-advance wrappers keep the child's measurement."""

from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import pytest

import gridlayoutpdf as api
from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, Document, FontRegistry, LayoutContext, LayoutOverflowError,
    LayoutPart, Line, MeasuredBlock, ReportStyle, Spacer, measure_block,
)


@pytest.fixture
def context():
    fonts = FontRegistry()
    fonts.register("body", Path(__file__).parents[1] / "fixtures/fonts/ipaexm.ttf")
    return LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())


@dataclass(frozen=True)
class FixedBlock:
    result: MeasuredBlock
    block_id: str = "child"

    def measure(self, context, available_width):
        return self.result


@dataclass(frozen=True)
class WidthBlock:
    """Reserve the offered width so callers can observe it."""

    rows: tuple[int, ...] = (1,)
    block_id: str = "width"

    def measure(self, context, available_width):
        parts = tuple(LayoutPart(rows, (Line(1, 2, available_width - 1, 2),)) for rows in self.rows)
        return MeasuredBlock(available_width, context.profile.grid.pitch_y, parts, block_id=self.block_id)


def parts(*rows, prefix=(), **flags):
    return MeasuredBlock(40, 15.48, tuple(LayoutPart(count, (Line(1, 2, 9, 2),), {"n": index})
                                          for index, count in enumerate(rows)),
                         prefix=tuple(LayoutPart(count) for count in prefix), **flags)


def test_keep_with_next_marks_only_the_flow_rule(context):
    original = parts(1, 2, break_after=(1,), prefer_keep=True, block_id="heading")
    wrapper = api.KeepWithNext(FixedBlock(original))
    result = measure_block(wrapper, context, 100)
    assert result == replace(original, keep_with_next=True)
    assert original.keep_with_next is False
    assert measure_block(api.KeepWithNext(FixedBlock(original), block_id="own"), context, 100).block_id == "own"
    with pytest.raises(FrozenInstanceError):
        wrapper.block = FixedBlock(original)
    with pytest.raises(ValueError, match="measure"):
        api.KeepWithNext(object())


def test_prefer_keep_together_marks_preference_but_keeps_legal_splits(context):
    original = parts(1, 1, 1, keep_with_next=True, block_id="table")
    result = measure_block(api.PreferKeepTogether(FixedBlock(original)), context, 100)
    assert result == replace(original, prefer_keep=True)
    assert result.keep_together is False and result.split(2) is not None
    with pytest.raises(ValueError, match="measure"):
        api.PreferKeepTogether(None)


def test_keep_with_next_moves_a_heading_with_its_body_in_flow(context):
    small = replace(A4_PORTRAIT_REFERENCE, name="small", body_end_row=A4_PORTRAIT_REFERENCE.body_start_row + 4)
    body = WidthBlock((1, 1), "body")
    keep = api.KeepWithNext(WidthBlock((1,), "head"))
    pages = Document(WidthBlock((3,), "filler"), keep, body,
                     fonts=context.fonts, profile=small).layout()
    assert len(pages) == 2
    assert [placement["block_id"] for placement in pages[1].metadata["placements"]][:2] == ["head", "body"]


def test_prefer_keep_together_moves_a_fitting_block_to_a_fresh_page(context):
    small = replace(A4_PORTRAIT_REFERENCE, name="small", body_end_row=A4_PORTRAIT_REFERENCE.body_start_row + 4)
    pages = Document(WidthBlock((3,), "filler"), api.PreferKeepTogether(WidthBlock((1, 1), "kept")),
                     fonts=context.fonts, profile=small).layout()
    assert [[placement["block_id"] for placement in page.metadata["placements"]] for page in pages] == [
        ["filler"], ["kept"]]


def test_indent_shifts_child_and_reduces_its_measurement_width(context):
    child = WidthBlock((1, 2), "body")
    prefixed = FixedBlock(parts(1, prefix=(1,), block_id="header"))
    result = measure_block(api.Indent(child, 30), context, 100)
    assert result.width == 100 and result.block_id == "body"
    assert result.commands == (Line(31, 2, 99, 2), Line(31, 17.48, 99, 17.48))
    assert [part.metadata["indent_pt"] for part in result.parts] == [30, 30]
    with_prefix = measure_block(api.Indent(prefixed, 10, block_id="moved"), context, 100)
    assert with_prefix.prefix[0].metadata == {"indent_pt": 10}
    assert with_prefix.parts[0].metadata == {"n": 0, "indent_pt": 10}
    assert (with_prefix.width, with_prefix.block_id) == (50, "moved")
    assert measure_block(api.Indent(child, 0), context, 100).commands[0] == Line(1, 2, 99, 2)


@pytest.mark.parametrize("left", [-1, float("nan"), float("inf"), True, "1"])
def test_indent_rejects_invalid_offsets(left):
    with pytest.raises(ValueError, match="left"):
        api.Indent(WidthBlock(), left)


def test_indent_that_leaves_no_width_is_an_overflow(context):
    with pytest.raises(LayoutOverflowError, match="indent") as caught:
        api.Indent(WidthBlock(), 100, block_id="deep").measure(context, 100)
    assert (caught.value.block_id, caught.value.needed, caught.value.available) == ("deep", 100, 100)


def test_leading_sets_every_body_part_to_the_line_advance(context):
    original = parts(1, 2, 1, break_after=(1, 2), min_first=2, block_id="lines")
    result = measure_block(api.Leading(FixedBlock(original), 2), context, 100)
    assert [part.rows for part in result.parts] == [2, 2, 2]
    assert [part.commands for part in result.parts] == [part.commands for part in original.parts]
    assert (result.break_after, result.min_first, result.block_id) == ((1, 2), 2, "lines")
    with pytest.raises(LayoutOverflowError, match="leading") as caught:
        api.Leading(FixedBlock(original), 1).measure(context, 100)
    assert caught.value.needed == pytest.approx(2 * 15.48)


def test_minimum_leading_only_raises_short_parts(context):
    original = parts(1, 3, block_id="lines")
    result = measure_block(api.Leading(FixedBlock(original), 2, minimum=True, block_id="own"), context, 100)
    assert [part.rows for part in result.parts] == [2, 3]
    assert result.block_id == "own"


@pytest.mark.parametrize("rows", [0, -1, 1.5, True])
def test_leading_rejects_nonpositive_or_noninteger_rows(rows):
    with pytest.raises(ValueError, match="rows"):
        api.Leading(WidthBlock(), rows)


def test_leading_rejects_repeating_prefix_and_invalid_minimum(context):
    with pytest.raises(ValueError, match="prefix"):
        api.Leading(FixedBlock(parts(1, prefix=(1,))), 2).measure(context, 100)
    with pytest.raises(ValueError, match="minimum"):
        api.Leading(WidthBlock(), 2, minimum=1)


def test_wrappers_preserve_empty_measurements(context):
    empty = FixedBlock(MeasuredBlock(40, 15.48))
    assert measure_block(api.Leading(empty, 2), context, 100).rows == 0
    assert measure_block(api.Indent(Spacer(0), 5), context, 100).rows == 0
