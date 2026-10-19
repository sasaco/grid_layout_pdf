"""Pagination decisions checked with small deterministic measured blocks."""

from dataclasses import FrozenInstanceError, dataclass, replace
from math import nextafter
from pathlib import Path

import pytest

from gridlayoutpdf.blocks import Heading, PageBreak, Paragraph, Spacer
from gridlayoutpdf.containers import At, Columns, KeepTogether, Stack
from gridlayoutpdf.document import Document, PageDecoration, PageSection
from gridlayoutpdf.equations import Equation, EquationAnchors, EquationGroup, MathBlock
from gridlayoutpdf.errors import LayoutError, LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.geometry import GridSpec
from gridlayoutpdf.layout import LayoutPart, MeasuredBlock
from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE, PageProfile
from gridlayoutpdf.scene import Text
from gridlayoutpdf.styles import ReportStyle, TextStyle
from gridlayoutpdf.tables import Cell, Table


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * .6, style.size * .8, style.size * .2)


FONTS = FixedFonts()
SMALL = replace(A4_PORTRAIT_REFERENCE, name="five-body-rows", body_end_row=5)
WIDE = replace(A3_LANDSCAPE_REFERENCE, name="wide-five-body-rows", body_end_row=5)


@dataclass(frozen=True)
class PartsBlock:
    part_rows: tuple[int, ...]
    block_id: str = "block"
    visible: bool = True
    keep_together: bool = False
    keep_with_next: bool = False
    prefer_keep: bool = False
    min_first: int = 1
    min_last: int = 1

    def measure(self, context, width):
        parts = tuple(LayoutPart(rows, (Text(0, 11, f"{self.block_id}:{index}", context.style.body),)
                                 if self.visible else (), {"part_index": index})
                      for index, rows in enumerate(self.part_rows))
        return MeasuredBlock(width, context.profile.grid.pitch_y, parts,
                             keep_together=self.keep_together, keep_with_next=self.keep_with_next,
                             prefer_keep=self.prefer_keep, min_first=self.min_first,
                             min_last=self.min_last, block_id=self.block_id)


def text_pages(pages):
    return [[command.text for command in page.commands if isinstance(command, Text)] for page in pages]


def test_flow_exact_fit_and_next_atomic_block_starts_a_new_page():
    document = Document(PartsBlock((2,), "a"), PartsBlock((3,), "b"), PartsBlock((1,), "c"),
                        fonts=FONTS, profile=SMALL)
    pages = document.layout()
    assert text_pages(pages) == [["a:0", "b:0"], ["c:0"]]
    assert pages[0].commands[0].x == 50.88
    assert pages[0].commands[0].y == 65.598
    assert pages[0].commands[1].y == pytest.approx(96.558)
    assert pages[1].commands[0].y == 65.598
    assert [page.metadata["page_number"] for page in pages] == [1, 2]
    placement = pages[0].metadata["placements"][1]
    assert {key: placement[key] for key in ("block_id", "source_path", "row", "col", "rows", "width")} == {
        "block_id": "b", "source_path": "Document.blocks[1]", "row": 2, "col": 0,
        "rows": 3, "width": SMALL.body_rect.width,
    }
    assert placement["parts"][0] == {"row": 0, "rows": 3, "metadata": {"part_index": 0}}
    assert document.layout() == pages


def test_atomic_block_one_row_short_moves_without_blank_page():
    pages = Document(PartsBlock((2,), "a"), PartsBlock((4,), "b"), fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [["a:0"], ["b:0"]]


def test_oversized_atomic_block_fails_with_grid_row_diagnostics():
    with pytest.raises(LayoutOverflowError) as caught:
        Document(PartsBlock((6,), "giant"), fonts=FONTS, profile=SMALL).layout()
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (6, 5, "giant")
    assert "rows" in str(caught.value)


def test_empty_document_and_redundant_pagebreaks_never_create_blank_pages():
    assert Document(fonts=FONTS).layout() == ()
    assert Document(PageBreak(), Spacer(0), PageBreak(), fonts=FONTS).layout() == ()
    pages = Document(PageBreak(), PartsBlock((1,), "a"), PageBreak(), PageBreak(),
                     PartsBlock((1,), "b"), PageBreak(), fonts=FONTS).layout()
    assert text_pages(pages) == [["a:0"], ["b:0"]]


def test_positive_spacer_intentionally_reserves_rows_but_zero_block_does_not_start_page():
    pages = Document(PartsBlock((), "empty"), Spacer(2), PartsBlock((1,), "a"), fonts=FONTS, profile=SMALL).layout()
    assert len(pages) == 1
    assert pages[0].commands[0].y == pytest.approx(96.558)
    assert len(Document(Spacer(2), fonts=FONTS).layout()) == 1


def test_document_snapshots_input_sequence_and_is_immutable():
    children = [PartsBlock((1,), "a")]
    document = Document(*children, fonts=FONTS)
    children.clear()
    assert len(document.blocks) == 1
    with pytest.raises(FrozenInstanceError):
        document.profile = SMALL


@pytest.mark.parametrize("values", [{"fonts": "IPAex明朝"}, {"profile": "A4"}, {"style": None}, {"header": "text"}, {"footer": 3}])
def test_document_rejects_invalid_configuration(values):
    with pytest.raises(ValueError):
        Document(**{"fonts": FONTS, **values})


def test_document_without_fonts_uses_the_shared_default_registry():
    from gridlayoutpdf.fonts import default_fonts
    document = Document(Paragraph("日本"))
    assert document.fonts is default_fonts()
    assert Document(Paragraph("日本"), fonts=None).fonts is default_fonts()
    assert document.layout()[0].commands


def test_invalid_flow_node_is_rejected_with_source_path():
    with pytest.raises(ValueError, match=r"Document.blocks\[0\]"):
        Document(object(), fonts=FONTS).layout()


def test_split_uses_remaining_rows_and_retains_part_metadata_without_remeasurement():
    class Counted:
        block_id = "counted"
        calls = 0
        def measure(self, context, width):
            self.calls += 1
            return PartsBlock((1,) * 8, self.block_id).measure(context, width)
    block = Counted()
    pages = Document(Spacer(2), block, fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [["counted:0", "counted:1", "counted:2"],
                                ["counted:3", "counted:4", "counted:5", "counted:6", "counted:7"]]
    assert block.calls == 1
    assert pages[1].metadata["placements"][0]["parts"][0]["metadata"]["part_index"] == 3


def test_minimum_first_and_last_lines_control_legal_cuts():
    block = PartsBlock((1,) * 4, "para", min_first=2, min_last=2)
    pages = Document(Spacer(2), block, fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [["para:0", "para:1"], ["para:2", "para:3"]]
    pages = Document(Spacer(4), block, fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [[], ["para:0", "para:1", "para:2", "para:3"]]
    short = PartsBlock((1,) * 3, "short", min_first=2, min_last=2)
    assert text_pages(Document(short, fonts=FONTS, profile=SMALL).layout()) == [["short:0", "short:1", "short:2"]]


def test_prefer_keep_moves_only_blocks_that_fit_a_fresh_page():
    small = PartsBlock((1,) * 4, "small", prefer_keep=True)
    large = PartsBlock((1,) * 7, "large", prefer_keep=True)
    assert text_pages(Document(Spacer(2), small, fonts=FONTS, profile=SMALL).layout()) == [[], [f"small:{i}" for i in range(4)]]
    assert text_pages(Document(Spacer(2), large, fonts=FONTS, profile=SMALL).layout()) == [
        [f"large:{i}" for i in range(3)], [f"large:{i}" for i in range(3, 7)],
    ]


def test_keep_together_never_splits_even_when_body_parts_have_legal_cuts():
    block = PartsBlock((1,) * 6, "together", keep_together=True)
    with pytest.raises(LayoutOverflowError) as caught:
        Document(block, fonts=FONTS, profile=SMALL).layout()
    assert (caught.value.needed, caught.value.available) == (6, 5)


def test_nonprogressing_split_is_rejected_without_repeated_page_attempts():
    class BadMeasured(MeasuredBlock):
        def split(self, available_rows):
            return self, self
    class BadBlock:
        block_id = "bad-split"
        def measure(self, context, width):
            return BadMeasured(width, context.profile.grid.pitch_y,
                               tuple(LayoutPart(1) for _ in range(8)), block_id=self.block_id)
    with pytest.raises(LayoutError, match="split.*progress|reduce"):
        Document(BadBlock(), fonts=FONTS, profile=SMALL).layout()


def test_heading_and_whole_preferred_body_move_together_when_the_chain_fits_fresh():
    heading = PartsBlock((1,), "heading", keep_with_next=True)
    body = PartsBlock((1,) * 4, "body", prefer_keep=True, min_first=2, min_last=2)
    pages = Document(Spacer(2), heading, body, fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [[], ["heading:0", "body:0", "body:1", "body:2", "body:3"]]


def test_keep_next_suppresses_prefer_keep_only_when_the_whole_chain_cannot_fit_fresh():
    heading = PartsBlock((2,), "heading", keep_with_next=True)
    body = PartsBlock((1,) * 4, "body", prefer_keep=True, min_first=2, min_last=2)
    pages = Document(Spacer(1), heading, body, fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [["heading:0", "body:0", "body:1"], ["body:2", "body:3"]]


def test_contiguous_heading_chain_includes_spacers_and_skips_empty_blocks():
    blocks = (Spacer(1), PartsBlock((1,), "h1", keep_with_next=True), Spacer(1),
              PartsBlock((), "empty"), PartsBlock((1,), "h2", keep_with_next=True),
              PartsBlock((1,) * 4, "body", min_first=2, min_last=2))
    pages = Document(*blocks, fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [[], ["h1:0", "h2:0", "body:0", "body:1"], ["body:2", "body:3"]]
    assert pages[1].metadata["placements"][2]["row"] == 2


@pytest.mark.parametrize("tail", [(), (Spacer(0),), (Spacer(1),), (PageBreak(), PartsBlock((1,), "body"))])
def test_dangling_keep_next_is_diagnosed_at_eof_or_explicit_pagebreak(tail):
    with pytest.raises(LayoutError, match="heading.*keep_with_next"):
        Document(PartsBlock((1,), "heading", keep_with_next=True), *tail,
                 fonts=FONTS, profile=SMALL).layout()


def test_heading_chain_minimum_that_exceeds_empty_page_fails_in_rows():
    with pytest.raises(LayoutOverflowError) as caught:
        Document(PartsBlock((3,), "heading", keep_with_next=True),
                 PartsBlock((3,), "body"), fonts=FONTS, profile=SMALL).layout()
    assert (caught.value.block_id, caught.value.needed, caught.value.available) == ("heading", 6, 5)


def test_page_sections_remeasure_each_occurrence_and_restore_parent_profile():
    class Counted:
        block_id = "reused"
        calls = []
        def measure(self, context, width):
            self.calls.append((context.profile.name, width))
            return PartsBlock((1,), self.block_id).measure(context, width)
    child = Counted()
    pages = Document(child, PageSection(WIDE, child), child, fonts=FONTS, profile=SMALL).layout()
    assert [page.profile for page in pages] == [SMALL, WIDE, SMALL]
    assert child.calls == [(SMALL.name, SMALL.body_rect.width), (WIDE.name, WIDE.body_rect.width), (SMALL.name, SMALL.body_rect.width)]
    assert all(page.commands[0].y == 65.598 for page in pages)


def test_nested_page_sections_restore_each_parent_in_order():
    pages = Document(PartsBlock((1,), "a"), PageSection(WIDE, PartsBlock((1,), "b"),
                     PageSection(SMALL, PartsBlock((1,), "c")), PartsBlock((1,), "d")),
                     PartsBlock((1,), "e"), fonts=FONTS, profile=SMALL).layout()
    assert [page.profile for page in pages] == [SMALL, WIDE, SMALL, WIDE, SMALL]
    assert text_pages(pages) == [[f"{letter}:0"] for letter in "abcde"]


def test_empty_page_sections_do_not_flush_parent_or_count_pagebreaks():
    empty = PageSection(WIDE, PageBreak(), Spacer(0), Paragraph(""), Stack(),
                        PageSection(SMALL, PageBreak()), PageBreak())
    pages = Document(PartsBlock((1,), "a"), empty, PartsBlock((1,), "b"), fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [["a:0", "b:0"]]
    assert Document(empty, fonts=FONTS).layout() == ()
    assert len(Document(PageSection(WIDE, Spacer(1)), fonts=FONTS).layout()) == 1


def test_flow_stack_expands_recursively_preserving_split_rules_and_source_paths():
    pages = Document(Stack(Stack(PartsBlock((1,) * 7, "body")), PageBreak(), PartsBlock((1,), "end")),
                     fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [[f"body:{i}" for i in range(5)], ["body:5", "body:6"], ["end:0"]]
    assert pages[0].metadata["placements"][0]["source_path"] == "Document.blocks[0].children[0].children[0]"
    with pytest.raises(LayoutOverflowError):
        Document(KeepTogether(Stack(PartsBlock((1,) * 7))), fonts=FONTS, profile=SMALL).layout()


def test_keep_next_cannot_cross_real_section_boundaries_but_skips_empty_sections():
    heading = PartsBlock((1,), "heading", keep_with_next=True)
    body = PartsBlock((1,), "body")
    for blocks in ((heading, PageSection(WIDE, body)), (PageSection(WIDE, heading), body)):
        with pytest.raises(LayoutError, match="keep_with_next"):
            Document(*blocks, fonts=FONTS, profile=SMALL).layout()
    assert text_pages(Document(heading, PageSection(WIDE, PageBreak()), body, fonts=FONTS, profile=SMALL).layout()) == [["heading:0", "body:0"]]


def test_page_section_is_immutable_and_validates_profile():
    section = PageSection(WIDE, PartsBlock((1,)))
    assert isinstance(section.children, tuple)
    with pytest.raises(FrozenInstanceError):
        section.profile = SMALL
    with pytest.raises(ValueError, match="profile"):
        PageSection(None)


def test_at_places_at_explicit_grid_indices_and_reserves_vertical_band():
    pages = Document(At(3, 5, 4, PartsBlock((1,), "a"), block_id="positioned"),
                     PartsBlock((1,), "b"), fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [["a:0", "b:0"]]
    assert (pages[0].commands[0].x, pages[0].commands[0].y) == pytest.approx((131.28, 112.038))
    assert pages[0].commands[1].y == pytest.approx(127.518)
    placement = pages[0].metadata["placements"][0]
    assert (placement["block_id"], placement["row"], placement["col"], placement["rows"]) == ("positioned", 3, 5, 1)


@pytest.mark.parametrize("blocks", [
    (PartsBlock((2,), "a"), At(1, 0, 4, PartsBlock((1,), "b"))),
    (At(1, 0, 4, PartsBlock((2,), "a")), At(1, 5, 4, PartsBlock((1,), "b"))),
])
def test_at_cannot_place_in_the_past_or_overlap_even_in_a_different_column(blocks):
    with pytest.raises(LayoutError, match="At.*cursor|cursor.*At"):
        Document(*blocks, fonts=FONTS, profile=SMALL).layout()


def test_at_never_autopaginates_or_splits_when_its_frame_exceeds_body():
    with pytest.raises(LayoutOverflowError) as caught:
        Document(At(4, 0, 4, PartsBlock((1, 1), "a"), block_id="at"), fonts=FONTS, profile=SMALL).layout()
    assert (caught.value.block_id, caught.value.needed, caught.value.available) == ("at", 2, 1)


def test_empty_at_still_validates_body_and_column_ranges_without_creating_a_page():
    profile = replace(SMALL, body_start_row=2)
    assert Document(At(2, 0, 1, Spacer(0)), fonts=FONTS, profile=profile).layout() == ()
    for at in (At(1, 0, 1, Spacer(0)), At(6, 0, 1, Spacer(0)), At(2, 30, 1, Spacer(0))):
        with pytest.raises(LayoutError):
            Document(PageSection(profile, at), fonts=FONTS).layout()


def test_keep_next_cannot_cross_at_boundary_or_escape_atomic_at_child():
    heading = PartsBlock((1,), "heading", keep_with_next=True)
    with pytest.raises(LayoutError, match="keep_with_next"):
        Document(heading, At(2, 0, 4, PartsBlock((1,), "b")), fonts=FONTS, profile=SMALL).layout()
    with pytest.raises(LayoutError, match="keep_with_next"):
        Document(At(0, 0, 8, heading), PartsBlock((1,), "body"), fonts=FONTS, profile=SMALL).layout()
    assert len(Document(At(0, 0, 8, Stack(heading, PartsBlock((1,), "body"))), fonts=FONTS, profile=SMALL).layout()) == 1


def test_columns_keep_atomic_height_and_nested_local_metadata():
    columns = Columns(PartsBlock((1,), "left"), Stack(PartsBlock((1,), "r1"), PartsBlock((2,), "r2")),
                      col_spans=(8, 8), block_id="columns")
    page, = Document(columns, PartsBlock((1,), "after"), fonts=FONTS, profile=SMALL).layout()
    assert page.metadata["placements"][1]["row"] == 3
    children = page.metadata["placements"][0]["parts"][0]["metadata"]["children"]
    assert children[1]["x_pt"] == 9 * 16.08
    assert children[1]["parts"][0]["metadata"]["children"][1]["y_pt"] == 15.48


def test_decorations_use_final_page_counts_fixed_frames_and_default_nine_point_style():
    pages = Document(PartsBlock((5,), "a"), PartsBlock((1,), "b"), fonts=FONTS, profile=SMALL,
                     header=PageDecoration("Head {page:02d}/{pages:02d}", align="center"),
                     footer=PageDecoration("{page}/{pages}", align="right")).layout()
    assert len(pages) == 2
    for index, page in enumerate(pages, start=1):
        header = next(c for c in page.commands if c.text.startswith("Head"))
        footer = next(c for c in page.commands if c.text == f"{index}/2")
        assert header.text == f"Head {index:02d}/02"
        assert header.style.size == 9 and footer.style.size == 9
        assert header.x == pytest.approx(265.08)
        assert header.y == pytest.approx(34.638)
        assert footer.x == pytest.approx(517.08)
        assert footer.y == pytest.approx(158.478)
        assert page.metadata["decorations"]["header"]["text"] == header.text


def test_decoration_remeasures_each_profile_and_does_not_shift_body():
    header = PageDecoration("{page}/{pages}", align="center", style=TextStyle(size=10))
    pages = Document(PartsBlock((1,), "a"), PageSection(WIDE, PartsBlock((1,), "b")), PartsBlock((1,), "c"),
                     fonts=FONTS, profile=SMALL, header=header).layout()
    for number, page in enumerate(pages, start=1):
        assert page.commands[0].y == 65.598
        text = next(c for c in page.commands if c.text == f"{number}/3")
        assert text.x + 9 == pytest.approx(page.profile.body_rect.x + page.profile.body_rect.width / 2)
        assert text.style.size == 10


@pytest.mark.parametrize("values", [
    {"text": 1}, {"text": "bad\ttab"}, {"rows": 0}, {"rows": True}, {"gap_rows": -1},
    {"gap_rows": False}, {"align": "justify"}, {"style": 9},
    {"text": "{unknown}"}, {"text": "{page.__class__}"}, {"text": "{page:bad}"},
    {"text": "{page"}, {"text": "{page:{pages}}"}, {"text": "{page!s}"},
])
def test_decoration_rejects_invalid_geometry_styles_and_templates(values):
    with pytest.raises(ValueError):
        PageDecoration(**{"text": "{page}/{pages}", **values})


@pytest.mark.parametrize("side", ["header", "footer"])
def test_decoration_frame_cannot_extend_outside_paper(side):
    with pytest.raises(LayoutOverflowError) as caught:
        Document(PartsBlock((1,)), fonts=FONTS,
                 **{side: PageDecoration("x", rows=4, gap_rows=0)}).layout()
    assert f"page[1].{side}" in caught.value.block_id
    assert caught.value.needed > caught.value.available


def test_decoration_text_cannot_expand_its_reserved_rows_or_width():
    for decoration in (PageDecoration("x", style=TextStyle(size=40)), PageDecoration("x" * 200)):
        with pytest.raises(LayoutOverflowError) as caught:
            Document(PartsBlock((1,)), fonts=FONTS, header=decoration).layout()
        assert "page[1].header" in caught.value.block_id


def test_total_page_count_transition_from_nine_to_ten_revalidates_fixed_frame():
    grid = replace(SMALL.grid, pitch_x=20, columns=1)
    profile = replace(SMALL, grid=grid, body_end_row=1)
    header = PageDecoration("{page}/{pages}", gap_rows=0)
    blocks = tuple(PartsBlock((1,), "x") for _ in range(10))
    assert len(Document(*blocks[:9], fonts=FONTS, profile=profile, header=header).layout()) == 9
    with pytest.raises(LayoutOverflowError) as caught:
        Document(*blocks, fonts=FONTS, profile=profile, header=header).layout()
    assert "page[1].header" in caught.value.block_id


@pytest.fixture
def real_fonts():
    fonts = FontRegistry()
    return fonts


def test_real_paragraph_minimum_lines_and_equation_tail_anchors_are_preserved(real_fonts):
    paragraph = Paragraph("first\nsecond\nthird\nfourth", block_id="paragraph")
    pages = Document(Spacer(2), paragraph, fonts=real_fonts, profile=SMALL).layout()
    assert text_pages(pages) == [["first", "second"], ["third", "fourth"]]
    group = EquationGroup(*(Equation("A", str(index), result=str(index), unit="m") for index in range(7)),
                          anchors=EquationAnchors(5, 20, 25, 27), block_id="equations")
    pages = Document(Spacer(2), group, fonts=real_fonts, profile=SMALL).layout()
    assert len(pages) == 2
    assert [sum(c.text == "A" for c in p.commands if isinstance(c, Text)) for p in pages] == [3, 4]
    anchors = [part["metadata"]["anchors_pt"] for page in pages for placement in page.metadata["placements"]
               if placement["block_id"] == "equations" for part in placement["parts"]]
    assert len(anchors) == 7 and all(a == anchors[0] for a in anchors)
    assert anchors[0]["first_equal"] == pytest.approx(80.4)


def test_real_table_repeats_prefix_without_header_only_pages_and_keeps_rowspan_groups(real_fonts):
    table = Table((6, 6), ((Cell("head", colspan=2),),
                          (Cell("merged", rowspan=2), Cell("a")), (Cell("b"),),
                          (Cell("last"), Cell("c"))), header_rows=1, block_id="table")
    profile = replace(SMALL, body_end_row=6)
    pages = Document(Spacer(5), table, fonts=real_fonts, profile=profile).layout()
    assert text_pages(pages) == [[], ["head", "merged", "a", "b"], ["head", "last", "c"]]
    placements = [page.metadata["placements"][0] for page in pages[1:]]
    assert [p["prefix"][0]["metadata"]["source_rows"] for p in placements] == [(0,), (0,)]
    assert placements[0]["parts"][0]["metadata"]["source_rows"] == (1, 2)
    assert placements[1]["parts"][0]["row"] == 2


@pytest.mark.parametrize("table", [
    Table((6,), ((Cell(Spacer(6)),), ("body",)), header_rows=1, block_id="giant-header"),
    Table((6, 6), (("h1", "h2"), (Cell("merged", rowspan=3), "a"), ("b",), ("c",)),
          header_rows=1, block_id="giant-rowspan"),
])
def test_real_giant_table_header_or_connected_group_stops_with_row_diagnostics(real_fonts, table):
    with pytest.raises(LayoutOverflowError) as caught:
        Document(table, fonts=real_fonts, profile=SMALL).layout()
    assert caught.value.block_id == table.block_id
    assert caught.value.needed > 5 and caught.value.available == 5
    assert "rows" in str(caught.value)


@pytest.mark.parametrize("height", [72.02, nextafter(72.02, float("inf"))])
def test_footer_frame_exact_paper_boundary_uses_assembled_coordinates(real_fonts, height):
    profile = PageProfile("compact", 100, height, GridSpec(10, 10.1, 10, 15.48, 8, 3))
    page, = Document(Paragraph("x"), fonts=real_fonts, profile=profile,
                     footer=PageDecoration("1", gap_rows=0)).layout()
    frame = page.metadata["decorations"]["footer"]
    assert frame["y_pt"] + frame["height"] == 72.02


@pytest.mark.parametrize("height", [nextafter(72.02, 0), 72.02 - 1e-8])
def test_footer_frame_rejects_any_actual_boundary_overflow(real_fonts, height):
    profile = PageProfile("compact", 100, height, GridSpec(10, 10.1, 10, 15.48, 8, 3))
    with pytest.raises(LayoutOverflowError) as caught:
        Document(Paragraph("x"), fonts=real_fonts, profile=profile,
                 footer=PageDecoration("1", gap_rows=0)).layout()
    assert (caught.value.needed, caught.value.available) == (1, 0)


def test_footer_overflow_row_diagnostic_counts_the_exactly_fitting_row(real_fonts):
    profile = PageProfile("compact", 100, 72.02, GridSpec(10, 10.1, 10, 15.48, 8, 3))
    with pytest.raises(LayoutOverflowError) as caught:
        Document(Paragraph("x"), fonts=real_fonts, profile=profile,
                 footer=PageDecoration("1", rows=2, gap_rows=0)).layout()
    assert (caught.value.needed, caught.value.available) == (2, 1)


@pytest.mark.parametrize("origin, fits", [(15.48, True), (nextafter(15.48, float("inf")), True),
                                         (nextafter(15.48, 0), False), (15.48 - 1e-8, False)])
def test_header_frame_exact_and_adjacent_boundary_positions(real_fonts, origin, fits):
    profile = PageProfile("compact", 100, 100, GridSpec(10, origin, 10, 15.48, 8, 3))
    document = Document(Paragraph("x"), fonts=real_fonts, profile=profile,
                        header=PageDecoration("1", gap_rows=0))
    if fits:
        assert len(document.layout()) == 1
    else:
        with pytest.raises(LayoutOverflowError) as caught:
            document.layout()
        assert (caught.value.needed, caught.value.available) == (1, 0)


@pytest.mark.parametrize("blank", [MathBlock(""), MathBlock(" "), Paragraph(" "), Paragraph("\u3000")])
@pytest.mark.parametrize("tail", [(), (PageBreak(), Paragraph("body"))])
def test_empty_or_whitespace_commands_cannot_satisfy_keep_next(real_fonts, blank, tail):
    with pytest.raises(LayoutError, match="heading.*keep_with_next"):
        Document(Heading("Heading", block_id="heading"), blank, *tail, fonts=real_fonts).layout()


@pytest.mark.parametrize("blank", [MathBlock(""), Paragraph(" "), Paragraph("\u3000")])
def test_blank_reserved_rows_move_with_heading_and_real_body_at_capacity_boundary(real_fonts, blank):
    pages = Document(Spacer(2), Heading("Heading"), blank, Paragraph("body one\nbody two"),
                     fonts=real_fonts, profile=SMALL).layout()
    assert len(pages) == 2 and pages[0].commands == ()
    assert text_pages(pages)[1][-2:] == ["body one", "body two"]
    placements = pages[1].metadata["placements"]
    assert [(p["row"], p["rows"]) for p in placements] == [(0, 1), (1, 1), (2, 2)]


@pytest.mark.parametrize("container", [
    KeepTogether(Stack(Heading("Heading"), Paragraph("\u3000"))),
    Columns(Stack(Heading("Heading"), MathBlock("")), Paragraph(" "), col_spans=(10, 10)),
])
def test_atomic_container_blank_tail_cannot_hide_dangling_heading(real_fonts, container):
    with pytest.raises(LayoutError, match="keep_with_next"):
        Document(container, fonts=real_fonts).layout()


@pytest.mark.parametrize("text", [" ", "\u3000"])
def test_whitespace_only_heading_keeps_rows_without_creating_a_keep_next_chain(real_fonts, text):
    page, = Document(Heading(text), fonts=real_fonts).layout()
    assert page.metadata["placements"][0]["rows"] == 1


@pytest.mark.parametrize("capacity", [3, 4, 5])
def test_heading_requires_a_legal_paragraph_fragment_with_visible_body(real_fonts, capacity):
    profile = replace(SMALL, body_end_row=capacity)
    with pytest.raises(LayoutOverflowError) as caught:
        Document(Heading("H", block_id="heading"), Paragraph("\n\n\nbody\nmore"),
                 fonts=real_fonts, profile=profile).layout()
    assert (caught.value.block_id, caught.value.needed, caught.value.available) == ("heading", 6, capacity)


def test_heading_keeps_leading_blank_lines_and_first_visible_legal_fragment(real_fonts):
    pages = Document(Heading("H"), Paragraph("\n\n\nbody\nmore\nlast"),
                     fonts=real_fonts, profile=SMALL).layout()
    assert text_pages(pages) == [["H", "body"], ["more", "last"]]
    parts = pages[0].metadata["placements"][1]["parts"]
    assert [part["metadata"]["text"] for part in parts] == ["", "", "", "body"]
    assert [part["row"] for part in parts] == [0, 1, 2, 3]


@dataclass(frozen=True)
class TextPartsBlock:
    texts: tuple[str, ...]
    prefix_texts: tuple[str, ...] = ()
    break_after: tuple[int, ...] | None = None
    min_first: int = 2
    min_last: int = 2
    keep_together: bool = False
    prefer_keep: bool = False

    def measure(self, context, width):
        def parts(texts):
            return tuple(LayoutPart(1, (Text(0, 11, text, context.style.body),)) for text in texts)
        return MeasuredBlock(width, context.profile.grid.pitch_y, parts(self.texts),
                             prefix=parts(self.prefix_texts), break_after=self.break_after,
                             min_first=self.min_first, min_last=self.min_last,
                             keep_together=self.keep_together, prefer_keep=self.prefer_keep)


def test_explicit_whitespace_commands_do_not_satisfy_minimum_visible_fragment():
    body = TextPartsBlock(("", " ", "\u3000", "body", "more"))
    with pytest.raises(LayoutOverflowError) as caught:
        Document(PartsBlock((1,), "heading", keep_with_next=True), body,
                 fonts=FONTS, profile=SMALL).layout()
    assert (caught.value.needed, caught.value.available) == (6, 5)


def test_visible_prefix_can_satisfy_keep_next_but_blank_prefix_cannot():
    profile = replace(SMALL, body_end_row=4)
    heading = PartsBlock((1,), "heading", keep_with_next=True)
    visible = TextPartsBlock(("", " ", "body", "more"), prefix_texts=("PREFIX",))
    pages = Document(heading, visible, fonts=FONTS, profile=profile).layout()
    assert text_pages(pages) == [["heading:0", "PREFIX", "", " "], ["PREFIX", "body", "more"]]
    assert pages[0].metadata["placements"][1]["rows"] == 3
    blank = replace(visible, prefix_texts=("\u3000",))
    with pytest.raises(LayoutOverflowError) as caught:
        Document(heading, blank, fonts=FONTS, profile=profile).layout()
    assert (caught.value.needed, caught.value.available) == (6, 4)


def test_minimum_visible_fragment_respects_explicit_break_after_boundaries():
    body = TextPartsBlock(("", " ", "body", "more", "last"),
                          break_after=(1, 2, 4), min_first=1, min_last=1)
    heading = PartsBlock((1,), "heading", keep_with_next=True)
    profile = replace(SMALL, body_end_row=4)
    with pytest.raises(LayoutOverflowError) as caught:
        Document(heading, body, fonts=FONTS, profile=profile).layout()
    assert (caught.value.needed, caught.value.available) == (5, 4)
    pages = Document(heading, body, fonts=FONTS, profile=SMALL).layout()
    assert text_pages(pages) == [["heading:0", "", " ", "body", "more"], ["last"]]


def test_minimum_visible_fragment_respects_keep_together_and_minimum_first_count():
    heading = PartsBlock((1,), "heading", keep_with_next=True)
    for body in (TextPartsBlock(("", "body", "more"), keep_together=True, min_first=1, min_last=1),
                 TextPartsBlock(("body", "more", "third", "last"), min_first=3, min_last=1)):
        with pytest.raises(LayoutOverflowError) as caught:
            Document(heading, body, fonts=FONTS, profile=replace(SMALL, body_end_row=3)).layout()
        assert (caught.value.needed, caught.value.available) == (4, 3)


@pytest.mark.parametrize("capacity,expected_pages", [(5, 3), (7, 2)])
def test_visible_fragment_reservation_preserves_prefer_keep_chain_priority(capacity, expected_pages):
    body = TextPartsBlock(("", " ", "\u3000", "body", "more", "last"), prefer_keep=True)
    profile = replace(SMALL, body_end_row=capacity)
    pages = Document(Spacer(1), PartsBlock((1,), "heading", keep_with_next=True), body,
                     fonts=FONTS, profile=profile).layout()
    assert len(pages) == expected_pages and pages[0].commands == ()
    assert text_pages(pages)[1][0] == "heading:0" and "body" in text_pages(pages)[1]
    assert [c.text for page in pages for c in page.commands if isinstance(c, Text) and c.text.strip()] == [
        "heading:0", "body", "more", "last",
    ]
