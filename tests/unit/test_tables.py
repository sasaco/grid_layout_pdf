from dataclasses import FrozenInstanceError, dataclass, replace
import importlib
from pathlib import Path

import pytest

from gridlayoutpdf.errors import FontError, LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.layout import LayoutContext, LayoutPart, MeasuredBlock, measure_block
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.scene import Line, Text
from gridlayoutpdf.styles import ReportStyle, TextStyle


def api():
    try:
        return importlib.import_module("gridlayoutpdf.tables")
    except ModuleNotFoundError:
        pytest.fail("Grid tables are not implemented")


@pytest.fixture
def context():
    fonts = FontRegistry()
    fonts.register("body", Path(__file__).parents[1] / "fixtures/fonts/ipaexm.ttf")
    return LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())


@dataclass(frozen=True)
class FixedBlock:
    width: float = 10
    rows: int = 1
    block_id: str = "fixed"
    commands: tuple = (Line(1, 2, 9, 2),)

    def measure(self, context, available_width):
        parts = (LayoutPart(self.rows, self.commands, {"anchors": {"equals": 5}}),) if self.rows else ()
        return MeasuredBlock(self.width, context.profile.grid.pitch_y, parts, block_id=self.block_id)


def test_cell_and_table_copy_inputs_and_are_frozen():
    module = api()
    cell = module.Cell("日本語")
    assert (cell.colspan, cell.rowspan, cell.align, cell.valign, cell.padding, cell.style) == (1, 1, None, "middle", 3, None)
    columns, rows, numeric, color = [2, 3], [[cell, "1.20"]], [1], [0.1, 0.2, 0.3]
    table = module.Table(columns, rows, numeric_columns=numeric, border_color=color, block_id="table")
    columns[0] = 99
    rows[0].clear()
    numeric.clear()
    color[0] = 1
    assert table.columns == (2, 3) and table.rows == ((cell, module.Cell("1.20")),)
    assert table.numeric_columns == (1,) and table.border_color == (0.1, 0.2, 0.3)
    with pytest.raises(FrozenInstanceError):
        cell.padding = 0
    with pytest.raises(FrozenInstanceError):
        table.rows = ()


@pytest.mark.parametrize("field,value", [
    ("content", 1.2), ("content", None), ("content", object()),
    ("colspan", 0), ("colspan", True), ("colspan", 1.5),
    ("rowspan", -1), ("rowspan", False), ("rowspan", "2"),
    ("padding", -1), ("padding", True), ("padding", float("inf")), ("padding", float("nan")),
    ("align", "justify"), ("valign", "center"), ("style", "bad"),
])
def test_cell_rejects_invalid_content_span_style_and_alignment(field, value):
    with pytest.raises(ValueError, match=field):
        api().Cell(**{field: value})


@pytest.mark.parametrize("columns", [(), None, (0,), (True,), (1.5,), ("2",), (float("inf"),)])
def test_table_rejects_invalid_columns(columns):
    with pytest.raises(ValueError, match="columns"):
        api().Table(columns, [])


@pytest.mark.parametrize("field,value", [
    ("header_rows", -1), ("header_rows", True), ("header_rows", 1.5), ("header_rows", 2),
    ("numeric_columns", [2]), ("numeric_columns", [True]), ("numeric_columns", [-1]),
    ("numeric_columns", None), ("border_width", 0), ("border_width", True),
    ("border_width", float("inf")), ("border_color", (0, 0)),
    ("border_color", (1.1, 0, 0)), ("border_color", (0, float("nan"), 0)),
    ("block_id", 3),
])
def test_table_rejects_invalid_options(field, value):
    with pytest.raises(ValueError, match=field):
        api().Table((2,), [["a"]], **{field: value})


@pytest.mark.parametrize("rows", [None, "abc", ["abc"], [[1]], [[None]]])
def test_table_rejects_invalid_row_structure(rows):
    with pytest.raises(ValueError, match="rows"):
        api().Table((2,), rows)


def test_table_rejects_holes_overlapping_spans_and_out_of_range_cells():
    module = api()
    cases = [
        ((1, 1), [["a"]]),
        ((1,), [["a", "b"]]),
        ((1,), [[module.Cell("a", colspan=2)]]),
        ((1,), [[module.Cell("a", rowspan=2)]]),
        ((1, 1, 1), [["a", module.Cell("b", rowspan=2), "c"], [module.Cell("d", colspan=2)]]),
    ]
    for columns, rows in cases:
        with pytest.raises(ValueError, match="rows\\["):
            module.Table(columns, rows)


def test_rowspan_may_cover_a_whole_empty_row_but_not_cross_header_boundary():
    module = api()
    table = module.Table((2,), [[module.Cell("a", rowspan=2)], []])
    assert table.rows[1] == ()
    with pytest.raises(ValueError, match="header"):
        module.Table((2,), [[module.Cell("a", rowspan=2)], []], header_rows=1)


def test_empty_table_is_zero_height_with_declared_width(context):
    result = measure_block(api().Table((2, 3), []), context, 100)
    assert result.width == pytest.approx(80.4)
    assert (result.rows, result.parts, result.prefix, result.commands) == (0, (), (), ())
    with pytest.raises(ValueError, match="header_rows"):
        api().Table((2,), [], header_rows=1)


def test_table_validates_context_available_width_and_declared_overflow(context):
    table = api().Table((2, 3), [], block_id="wide-table")
    with pytest.raises(ValueError, match="context"):
        table.measure(None, 100)
    for width in (0, True, float("nan")):
        with pytest.raises(ValueError, match="available_width"):
            table.measure(context, width)
    with pytest.raises(LayoutOverflowError, match="wide-table") as caught:
        table.measure(context, 80)
    assert (caught.value.needed, caught.value.available) == pytest.approx((80.4, 80))


def test_block_cell_rejects_a_style_that_would_be_ignored():
    with pytest.raises(ValueError, match="style.*string"):
        api().Cell(FixedBlock(), style=TextStyle())


@pytest.mark.parametrize("align,x", [("left", 3), ("center", 11.08), ("right", 19.16)])
@pytest.mark.parametrize("valign,y", [("top", 3), ("middle", 7.74), ("bottom", 12.48)])
def test_block_cell_alignment_uses_measured_frame_without_scaling(context, align, x, valign, y):
    module = api()
    table = module.Table((2,), [[module.Cell(FixedBlock(), align=align, valign=valign)]])
    result = measure_block(table, context, 100)
    cell = result.parts[0].metadata["cells"][0]
    assert result.rows == 2 and result.width == pytest.approx(32.16)
    assert (cell["content"]["x_pt"], cell["content"]["y_pt"]) == pytest.approx((x, y))
    command = next(c for c in result.commands if isinstance(c, Line) and c.width == 0.5 and c.y1 == c.y2 and c.x2 - c.x1 == 8)
    assert (command.x1, command.y1, command.x2, command.y2) == pytest.approx((x + 1, y + 2, x + 9, y + 2))
    assert cell["frame"] == {"x_pt": 0, "y_pt": 0, "width": 32.16, "height": 30.96}
    assert cell["content"]["parts"][0]["metadata"]["anchors"]["equals"] == 5


def test_numeric_column_default_and_explicit_string_alignment(context):
    module = api()
    table = module.Table((4, 4), [["123", module.Cell("123", align="left")]], numeric_columns=(0, 1))
    result = measure_block(table, context, 150)
    texts = [c for c in result.commands if isinstance(c, Text)]
    advance = context.fonts.measure("123", TextStyle()).width
    assert texts[0].x + advance == pytest.approx(61.32)
    assert texts[1].x == pytest.approx(67.32)
    assert all(c.style.size == 10 for c in texts)


def test_empty_cells_minimum_one_row_and_content_growth_reserves_whole_rows(context):
    module = api()
    empty = module.Table((2, 2), [["", ""]]).measure(context, 100)
    short = module.Table((2,), [[module.Cell(FixedBlock(rows=1))]]).measure(context, 100)
    tall = module.Table((2,), [[module.Cell(FixedBlock(rows=3))]]).measure(context, 100)
    assert (empty.rows, short.rows, tall.rows) == (1, 2, 4)
    assert empty.parts[0].metadata["source_rows"] == (0,)


def test_table_borders_are_inset_merged_and_contained(context):
    from gridlayoutpdf.bounds import command_bounds
    module = api()
    result = measure_block(module.Table((2, 3), [["", ""]], border_width=1, border_color=(0.2, 0.3, 0.4)), context, 100)
    lines = result.commands
    assert len(lines) == 5
    assert all(isinstance(line, Line) and line.width == 1 and line.color == (0.2, 0.3, 0.4) for line in lines)
    vertical = sorted(line.x1 for line in lines if line.x1 == line.x2)
    horizontal = sorted(line.y1 for line in lines if line.y1 == line.y2)
    assert vertical == pytest.approx((0.5, 32.16, 79.9))
    assert horizontal == pytest.approx((0.5, 14.98))
    for line in lines:
        bounds = command_bounds(line, context.fonts)
        assert bounds.x >= 0 and bounds.y >= 0
        assert bounds.right <= result.width and bounds.bottom <= result.height


def test_table_padding_width_and_child_overflow_have_cell_paths_and_dimensions(context):
    module = api()
    with pytest.raises(LayoutOverflowError, match="dense.*rows\\[0\\].cells\\[0\\].*padding") as caught:
        module.Table((1,), [[module.Cell("a", padding=9)]], block_id="dense").measure(context, 100)
    assert (caught.value.needed, caught.value.available) == pytest.approx((18, 16.08))
    with pytest.raises(LayoutOverflowError, match="dense.*rows\\[0\\].cells\\[0\\]") as caught:
        module.Table((1,), [[module.Cell(FixedBlock(width=11))]], block_id="dense").measure(context, 100)
    assert (caught.value.needed, caught.value.available) == pytest.approx((11, 10.08))
    assert isinstance(caught.value.__cause__, LayoutOverflowError)


def test_font_failure_keeps_cell_path_glyph_and_cause(context):
    with pytest.raises(FontError, match="glyphs.*rows\\[0\\].cells\\[0\\].*U\\+10FFFF") as caught:
        api().Table((3,), [["\U0010ffff"]], block_id="glyphs").measure(context, 100)
    assert isinstance(caught.value.__cause__, FontError)


def test_padding_too_small_for_real_ink_and_border_is_rejected(context):
    module = api()
    with pytest.raises(LayoutOverflowError, match="clearance.*border"):
        module.Table((2,), [[module.Cell("日", padding=0)]], block_id="clearance").measure(context, 100)


def test_header_only_table_has_atomic_body_not_header_only_prefix(context):
    result = api().Table((4,), [["H1"], ["H2"]], header_rows=2).measure(context, 100)
    assert result.prefix == () and len(result.parts) == 1
    assert result.parts[0].metadata["source_rows"] == (0, 1)
    assert result.split(2) is None


def test_table_header_repeats_once_per_split_without_missing_body(context):
    table = api().Table((4,), [["H"], ["A"], ["B"], ["C"], ["D"]], header_rows=1)
    result = measure_block(table, context, 100)
    assert len(result.prefix) == 1 and len(result.parts) == 4
    assert result.rows == 10 and result.minimum_rows == 4
    assert result.split(3) is None
    head, tail = result.split(6)
    assert (head.rows, tail.rows) == (6, 6)
    assert [c.text for c in head.commands if isinstance(c, Text)] == ["H", "A", "B"]
    assert [c.text for c in tail.commands if isinstance(c, Text)] == ["H", "C", "D"]
    assert tuple(p.metadata["source_rows"] for p in tail.parts) == ((3,), (4,))


def test_measurement_is_repeatable_and_metadata_is_deeply_immutable(context):
    module = api()
    table = module.Table((2,), [[module.Cell(FixedBlock())]])
    first = table.measure(context, 100)
    assert table.measure(context, 100) == first
    with pytest.raises(TypeError):
        first.parts[0].metadata["cells"][0]["content"]["parts"][0]["metadata"]["anchors"]["equals"] = 4


def test_transitively_connected_rowspans_form_one_part_with_deterministic_last_row_growth(context):
    module = api()
    rows = [
        [module.Cell(FixedBlock(rows=5), rowspan=2), module.Cell(FixedBlock())],
        [module.Cell(FixedBlock(rows=7), rowspan=2)],
        [module.Cell(FixedBlock())],
        ["after", "tail"],
    ]
    table = module.Table((4, 4), rows)
    result = measure_block(table, context, 150)
    assert len(result.parts) == 2
    assert result.parts[0].metadata["source_rows"] == (0, 1, 2)
    assert result.parts[0].metadata["row_heights"] == (2, 4, 4)
    assert result.parts[0].rows == 10 and result.parts[1].rows == 2
    assert result.split(9) is None
    head, tail = result.split(10)
    assert (head.rows, tail.rows) == (10, 2)
    frames = result.parts[0].metadata["cells"]
    assert frames[0]["frame"]["height"] == pytest.approx(92.88)
    assert frames[2]["frame"]["y_pt"] == pytest.approx(30.96)
    assert frames[2]["frame"]["height"] == pytest.approx(123.84)
    assert table.measure(context, 150) == result


def test_shorter_rowspans_are_satisfied_before_longer_spans(context):
    module = api()
    table = module.Table((3, 3), [
        [module.Cell(FixedBlock(rows=8), rowspan=3), module.Cell(FixedBlock(rows=5), rowspan=2)],
        [], [module.Cell(FixedBlock(rows=0, commands=()))],
    ])
    result = measure_block(table, context, 110)
    # Short span requires six rows -> [1,5,1]; long requires nine -> [1,5,3].
    assert result.parts[0].metadata["row_heights"] == (1, 5, 3)
    assert result.rows == 9


def test_colspan_and_rowspan_do_not_draw_borders_through_merged_cells(context):
    module = api()
    result = module.Table((2, 2), [
        [module.Cell("", colspan=2)],
        [module.Cell("", rowspan=2), ""], [""],
    ], header_rows=1).measure(context, 100)
    header_lines = result.prefix[0].commands
    assert len(header_lines) == 4
    assert not any(line.x1 == line.x2 == 32.16 for line in header_lines)
    body = result.parts[0]
    assert body.metadata["source_rows"] == (1, 2)
    internal = [line for line in body.commands if line.y1 == line.y2 == 15.48]
    assert len(internal) == 1
    assert (internal[0].x1, internal[0].x2) == pytest.approx((32.16, 64.07))


def test_string_paragraph_and_nested_fraction_cells_share_the_table_contract(context):
    from gridlayoutpdf.blocks import Paragraph
    from gridlayoutpdf.equations import MathBlock
    from gridlayoutpdf.math import Fraction, Script
    module = api()
    table = module.Table((6, 6, 6), [[
        "日本語", module.Cell(Paragraph("第一行\n第二行")),
        module.Cell(MathBlock(Fraction("a", Fraction("b", Script("c", superscript="2")))), align="center"),
    ]])
    result = measure_block(table, context, 300)
    texts = [command.text for command in result.commands if isinstance(command, Text)]
    assert texts == ["日本語", "第一行", "第二行", "a", "b", "c", "2"]
    assert result.rows >= 4
    assert len(result.parts) == 1 and result.split(2) is None


def test_incorrect_measure_protocol_reports_cell_path_and_explicit_math_adapter(context):
    from gridlayoutpdf.math import Fraction
    module = api()

    class WrongBlock:
        def measure(self):
            raise AssertionError("signature should prevent this body")

    for child in (Fraction("a", "b"), WrongBlock()):
        with pytest.raises((ValueError, TypeError), match="bad-protocol.*rows\\[0\\].cells\\[0\\].*MathBlock") as caught:
            module.Table((3,), [[module.Cell(child)]], block_id="bad-protocol").measure(context, 100)
        assert isinstance(caught.value.__cause__, (ValueError, TypeError))


def test_very_thick_border_is_rejected_and_no_canvas_is_constructed(context, monkeypatch):
    from reportlab.pdfgen import canvas
    module = api()

    def no_canvas(*args, **kwargs):
        pytest.fail("Table measurement must not construct a Canvas")

    monkeypatch.setattr(canvas, "Canvas", no_canvas)
    with pytest.raises(LayoutOverflowError, match="border_width"):
        module.Table((2,), [[""]], border_width=16).measure(context, 100)
    assert module.Table((2,), [["safe"]]).measure(context, 100).rows == 2


def test_border_cannot_exceed_a_narrow_empty_cell_even_when_whole_table_is_wide(context):
    module = api()
    profile = replace(context.profile, grid=replace(context.profile.grid, pitch_x=0.5))
    small_grid = LayoutContext(context.fonts, profile, context.style)
    table = module.Table((1, 10), [[module.Cell("", padding=0), module.Cell("", padding=0)]], border_width=1)
    with pytest.raises(LayoutOverflowError, match="rows\\[0\\].cells\\[0\\].*border"):
        table.measure(small_grid, 10)


@pytest.mark.parametrize("column", [0, 1, 2])
@pytest.mark.parametrize("align", ["left", "center", "right"])
@pytest.mark.parametrize("kind", ["table", "columns", "math"])
def test_exact_nested_grid_width_is_independent_of_cell_column(context, column, align, kind):
    from gridlayoutpdf.containers import Columns
    from gridlayoutpdf.equations import MathBlock
    from gridlayoutpdf.math import MathBox
    module = api()

    class ExactMath:
        def measure(self, fonts, style):
            return MathBox(32.16, 10, 2, (Line(1, -2, 9, -2),), 2.5)

    if kind == "table":
        child = module.Table((2,), [["A"]], block_id="inner")
    elif kind == "columns":
        child = Columns(FixedBlock(), col_spans=(2,), block_id="inner")
    else:
        child = MathBlock(ExactMath(), block_id="inner")
    row = ["", "", ""]
    row[column] = module.Cell(child, padding=8.04, align=align)
    outer = module.Table((3, 3, 3), [row], block_id="outer")
    result = measure_block(outer, context, 144.72)
    cell = result.parts[0].metadata["cells"][column]
    assert cell["content"]["width"] == 32.16
    assert cell["content"]["x_pt"] == pytest.approx((8.04, 56.28, 104.52)[column], abs=1e-12)
    assert cell["frame"]["width"] == pytest.approx(48.24, abs=1e-12)


def test_table_width_guard_tolerates_only_common_absolute_roundoff(context):
    table = api().Table((2,), [["A"]], block_id="inner")
    assert measure_block(table, context, 32.16 - 5e-8).width == 32.16
    with pytest.raises(LayoutOverflowError, match="inner.*width") as caught:
        measure_block(table, context, 32.16 - 0.0001)
    assert caught.value.needed == 32.16
    assert caught.value.available == 32.16 - 0.0001


@pytest.mark.parametrize("column", [0, 1, 2])
def test_nested_table_actual_shortage_still_fails_with_cell_diagnostic(context, column):
    module = api()
    inner = module.Table((2,), [["A"]], block_id="inner")
    row = ["", "", ""]
    row[column] = module.Cell(inner, padding=8.04005)
    with pytest.raises(LayoutOverflowError, match=rf"outer.*rows\[0\].cells\[{column}\].*inner") as caught:
        measure_block(module.Table((3, 3, 3), [row], block_id="outer"), context, 144.72)
    assert caught.value.needed == 32.16
    assert caught.value.available == pytest.approx(32.1599, abs=1e-12)
