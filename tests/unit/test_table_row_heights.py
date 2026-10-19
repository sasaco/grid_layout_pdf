"""Exact local-grid table heights preserve source geometry without shrinking."""

from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import pytest

from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, Cell, FontRegistry, GridSpec, LayoutContext, LayoutOverflowError, LayoutPart,
    Line, MeasuredBlock, PageProfile, QuarterTurn, ReportStyle, Table, TableBorders, Text, TextStyle,
    measure_block,
)


def sized_table(*args, **kwargs) -> Table:
    assert "row_heights" in Table.__dataclass_fields__, "Table must accept exact row_heights"
    return Table(*args, **kwargs)


@pytest.fixture
def context() -> LayoutContext:
    fonts = FontRegistry()
    profile = PageProfile("fine-table", 240, 400, GridSpec(20, 20, .01, .01, 20000, 36000))
    return LayoutContext(fonts, profile, ReportStyle())


@dataclass(frozen=True)
class FixedContent:
    """Reserve a known height with visible ink, independently of font metrics."""

    height: float
    block_id: str = "content"

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        rows = context.rows_for(self.height)
        return MeasuredBlock(10, context.profile.grid.pitch_y,
                             (LayoutPart(rows, (Line(1, self.height / 2, 9, self.height / 2, .1),)),),
                             block_id=self.block_id)


def test_row_heights_are_optional_copied_and_immutable(context: LayoutContext) -> None:
    plain = Table((4000,), ((Cell("A", padding=.6),),))
    assert getattr(plain, "row_heights", "absent") is None
    assert replace(plain, row_heights=None).measure(context, 100) == plain.measure(context, 100)
    heights = [1530]
    table = sized_table((4000,), ((Cell("A", padding=.6),),), row_heights=heights)
    heights[0] = 9999
    assert table.row_heights == (1530,)
    with pytest.raises(FrozenInstanceError):
        table.row_heights = (1,)


@pytest.mark.parametrize("heights", [
    (), (1000, 1000), 1000, True, "1000", (0,), (-1,), (True,),
    (1.5,), (1000.0,), ("1000",), (None,), (float("inf"),), (float("nan"),),
    (10 ** 400,),
])
def test_invalid_row_heights_fail_before_measurement(heights) -> None:
    with pytest.raises(ValueError, match="row_heights"):
        sized_table((4000,), (("",),), row_heights=heights)


def test_empty_table_accepts_only_empty_explicit_heights(context: LayoutContext) -> None:
    table = sized_table((4000,), (), row_heights=())
    result = measure_block(table, context, 100)
    assert result.rows == 0 and result.commands == ()
    with pytest.raises(ValueError, match="row_heights"):
        sized_table((4000,), (), row_heights=(1,))


def test_fine_grid_keeps_real_text_at_requested_size_and_exact_row_frames(context: LayoutContext) -> None:
    rows = ((Cell("原本 1", padding=.6, style=TextStyle(size=10)),),
            (Cell("原本 2", padding=.6, style=TextStyle(size=10)),))
    table = sized_table((6000,), rows, row_heights=(1530, 1620), block_id="source-table")
    result = measure_block(table, context, 100)
    assert result.rows == 3150 and result.height == pytest.approx(31.5)
    assert [part.metadata["row_heights"] for part in result.parts] == [(1530,), (1620,)]
    assert [part.metadata["cells"][0]["frame"]["height"] for part in result.parts] == pytest.approx([15.3, 16.2])
    text = [command for command in result.commands if isinstance(command, Text)]
    assert [command.text for command in text] == ["原本 1", "原本 2"]
    assert all(command.style.size == 10 for command in text)
    # The A4-sized pitch plus padding would enlarge each row to two lines.
    coarse = replace(context, profile=PageProfile("coarse-table", 240, 400,
                       GridSpec(20, 20, .01, 15.48, 20000, 23)))
    assert Table((6000,), rows).measure(coarse, 100).height == pytest.approx(61.92)


def test_content_and_padding_fit_at_exact_boundary(context: LayoutContext) -> None:
    table = sized_table((2000,), ((Cell(FixedContent(7.03), padding=.11),),),
                        row_heights=(725,), block_id="exact")
    measured = measure_block(table, context, 100)
    assert measured.height == pytest.approx(7.25)
    assert measured.parts[0].metadata["cells"][0]["content"]["y_pt"] == pytest.approx(.11)


def test_one_local_row_too_short_fails_without_inflating_requested_height(context: LayoutContext) -> None:
    table = sized_table((2000,), ((Cell(FixedContent(7.03), padding=.11),),),
                        row_heights=(724,), block_id="short")
    with pytest.raises(LayoutOverflowError, match=r"short\.rows\[0\]\.cells\[0\].*row_heights") as caught:
        measure_block(table, context, 100)
    assert caught.value.block_id == "short.rows[0].cells[0]"
    assert caught.value.needed == pytest.approx(7.25)
    assert caught.value.available == pytest.approx(7.24)
    assert table.row_heights == (724,)


def test_exact_height_rejects_even_subgrid_padding_overflow(context: LayoutContext) -> None:
    table = sized_table((2000,), ((Cell(FixedContent(7), padding=.005),),),
                        row_heights=(700,), block_id="fractional")
    with pytest.raises(LayoutOverflowError, match="row_heights") as caught:
        measure_block(table, context, 100)
    assert caught.value.needed == pytest.approx(7.01)
    assert caught.value.available == pytest.approx(7)


def test_rowspan_retains_unequal_explicit_rows_instead_of_redistributing_them(context: LayoutContext) -> None:
    table = sized_table((2000, 2000), (
        (Cell(FixedContent(15), rowspan=2, padding=.5), Cell(FixedContent(5), padding=.5)),
        (Cell(FixedContent(5), padding=.5),),
    ), row_heights=(700, 900), block_id="merged")
    result = measure_block(table, context, 100)
    assert len(result.parts) == 1 and result.parts[0].rows == 1600
    metadata = result.parts[0].metadata
    assert metadata["source_rows"] == (0, 1)
    assert metadata["row_heights"] == (700, 900)
    frames = {(cell["row"], cell["col"]): cell["frame"] for cell in metadata["cells"]}
    assert frames[(0, 0)]["height"] == 16
    assert frames[(0, 1)]["height"] == 7
    assert frames[(1, 1)]["y_pt"] == 7 and frames[(1, 1)]["height"] == 9
    # Rowspan suppresses the interior horizontal edge only inside its own cell.
    interior = [line for line in result.commands if isinstance(line, Line) and line.y1 == line.y2 == 7]
    assert interior == [Line(20, 7, 39.75, 7)]


def test_insufficient_rowspan_reports_summed_capacity(context: LayoutContext) -> None:
    table = sized_table((2000,), ((Cell(FixedContent(15), rowspan=2, padding=.5),), ()),
                        row_heights=(700, 899), block_id="short-span")
    with pytest.raises(LayoutOverflowError, match=r"short-span\.rows\[0\]\.cells\[0\].*row_heights") as caught:
        measure_block(table, context, 100)
    assert caught.value.needed == pytest.approx(16)
    assert caught.value.available == pytest.approx(15.99)
    assert table.row_heights == (700, 899)


def test_repeat_header_and_split_preserve_source_row_heights_and_sparse_rules(context: LayoutContext) -> None:
    rows = tuple((Cell(FixedContent(5), padding=.5),) for _ in range(4))
    borders = TableBorders(None, horizontal={0: "medium", 2: "thin", 4: "medium"})
    table = sized_table((2000,), rows, row_heights=(700, 800, 900, 1000), header_rows=1,
                        borders=borders, block_id="repeat")
    result = measure_block(table, context, 100)
    head, tail = result.split(1600)
    assert head.height == 15 and tail.height == 26
    assert head.prefix == tail.prefix == result.prefix
    assert head.prefix[0].metadata["source_rows"] == (0,)
    assert head.prefix[0].metadata["row_heights"] == (700,)
    assert [part.metadata["source_rows"] for part in head.parts] == [(1,)]
    assert [part.metadata["row_heights"] for part in tail.parts] == [(900,), (1000,)]
    assert [part.metadata["source_rows"] for part in tail.parts] == [(2,), (3,)]
    # Original boundary 3 is suppressed, so no new fragment frame is created.
    bottom_part_rules = [line for line in tail.parts[1].commands
                         if isinstance(line, Line) and line.y1 == line.y2 and line.width == 1]
    assert bottom_part_rules == [Line(.5, 9.5, 19.5, 9.5, 1)]


def test_explicit_heights_do_not_bypass_border_clearance(context: LayoutContext) -> None:
    table = sized_table((2000,), ((Cell(FixedContent(1), padding=0),),),
                        row_heights=(110,), block_id="border")
    # 1.1 pt leaves room between the thin frame lines, but not for the content.
    with pytest.raises(LayoutOverflowError, match="clearance"):
        measure_block(table, context, 100)


@pytest.mark.parametrize("turns", [-1, 1])
def test_rotated_table_keeps_exact_native_row_frames_and_font_size(context: LayoutContext, turns: int) -> None:
    table = sized_table((6000,), ((Cell("原本 1", padding=.6),), (Cell("原本 2", padding=.6),)),
                        row_heights=(1530, 1620), block_id="local-table")
    rotation = QuarterTurn(table, turns=turns, local_grid=GridSpec(0, 0, .01, .01, 10000, 10000))
    outer = replace(context, profile=A4_PORTRAIT_REFERENCE)
    measured = measure_block(rotation, outer, outer.profile.body_rect.width)
    assert measured.width == pytest.approx(31.5)
    assert measured.height == pytest.approx(61.92)  # Only the outer reservation rounds.
    child = measured.parts[0].metadata["child"]
    assert child["row_pitch"] == .01 and child["rows"] == 3150
    assert [part["metadata"]["row_heights"] for part in child["parts"]] == [(1530,), (1620,)]
    text = [command for command in measured.commands if isinstance(command, Text)]
    assert [command.text for command in text] == ["原本 1", "原本 2"]
    assert all(command.style.size == 10 and command.quarter_turns == turns % 4 for command in text)
