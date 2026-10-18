"""Opt-in spacers that disappear at the top of a page, like LaTeX's \\vspace."""

from dataclasses import dataclass, replace

import pytest

from gridlayoutpdf.blocks import Spacer
from gridlayoutpdf.containers import Indent, KeepWithNext, Leading
from gridlayoutpdf.document import Document
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.layout import LayoutContext, LayoutPart, MeasuredBlock
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.scene import Text
from gridlayoutpdf.styles import ReportStyle


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * .6, style.size * .8, style.size * .2)


FONTS = FixedFonts()
SMALL = replace(A4_PORTRAIT_REFERENCE, name="five-body-rows", body_end_row=5)


@dataclass(frozen=True)
class PartsBlock:
    part_rows: tuple[int, ...]
    block_id: str = "block"
    keep_with_next: bool = False

    def measure(self, context, width):
        parts = tuple(LayoutPart(rows, (Text(0, 11, f"{self.block_id}:{index}", context.style.body),))
                      for index, rows in enumerate(self.part_rows))
        return MeasuredBlock(width, context.profile.grid.pitch_y, parts,
                             keep_with_next=self.keep_with_next, block_id=self.block_id)


def rows_by_page(pages):
    return [[(placement["block_id"], placement["row"], placement["rows"])
             for placement in page.metadata["placements"]] for page in pages]


def layout(*blocks):
    return rows_by_page(Document(*blocks, fonts=FONTS, profile=SMALL).layout())


def test_marked_spacer_inside_a_page_reserves_its_rows():
    assert layout(PartsBlock((1,), "a"), Spacer(2, discard_at_page_top=True),
                  PartsBlock((1,), "b")) == [
        [("a", 0, 1), ("Document.blocks[1]", 1, 2), ("b", 3, 1)],
    ]


def test_marked_spacer_after_a_full_page_is_discarded_but_default_spacer_is_kept():
    assert layout(PartsBlock((5,), "a"), Spacer(2, discard_at_page_top=True),
                  PartsBlock((1,), "b")) == [[("a", 0, 5)], [("b", 0, 1)]]
    assert layout(PartsBlock((5,), "a"), Spacer(2), PartsBlock((1,), "b")) == [
        [("a", 0, 5)], [("Document.blocks[1]", 0, 2), ("b", 2, 1)],
    ]


def test_marked_spacer_that_does_not_fit_the_page_end_is_discarded_on_the_next_page():
    assert layout(PartsBlock((4,), "a"), Spacer(2, discard_at_page_top=True),
                  PartsBlock((1,), "b")) == [[("a", 0, 4)], [("b", 0, 1)]]


def test_marked_spacer_at_document_start_is_discarded():
    assert layout(Spacer(1, discard_at_page_top=True), PartsBlock((1,), "a")) == [[("a", 0, 1)]]
    assert layout(Spacer(9, discard_at_page_top=True)) == []


def test_keep_with_next_spacer_does_not_leave_a_blank_row_on_the_next_page():
    assert layout(PartsBlock((5,), "a"), KeepWithNext(Spacer(1, discard_at_page_top=True)),
                  PartsBlock((1,), "b")) == [[("a", 0, 5)], [("b", 0, 1)]]


def test_marked_spacer_after_a_heading_moved_by_keep_chain_stays_below_the_heading():
    assert layout(PartsBlock((4,), "a"), PartsBlock((1,), "h", keep_with_next=True),
                  Spacer(1, discard_at_page_top=True), PartsBlock((1,), "b")) == [
        [("a", 0, 4)], [("h", 0, 1), ("Document.blocks[2]", 1, 1), ("b", 2, 1)],
    ]


def test_wrappers_preserve_the_page_top_mark_and_default_is_false():
    context = LayoutContext(FONTS, SMALL, ReportStyle())
    width = SMALL.body_rect.width
    assert Spacer(1).measure(context, width).discard_at_page_top is False
    for block in (KeepWithNext(Spacer(1, discard_at_page_top=True)),
                  Indent(Spacer(1, discard_at_page_top=True), 10),
                  Leading(Spacer(1, discard_at_page_top=True), 1)):
        assert block.measure(context, width).discard_at_page_top is True
    assert MeasuredBlock(width, 1).discard_at_page_top is False


@pytest.mark.parametrize("value", [1, 0, None, "yes"])
def test_page_top_flag_must_be_a_boolean(value):
    with pytest.raises(ValueError, match="discard_at_page_top"):
        Spacer(1, discard_at_page_top=value)
    with pytest.raises(ValueError, match="discard_at_page_top"):
        MeasuredBlock(10, 1, discard_at_page_top=value)
