from dataclasses import FrozenInstanceError, dataclass
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
        return importlib.import_module("gridlayoutpdf.containers")
    except ModuleNotFoundError:
        pytest.fail("Layout containers are not implemented")


@pytest.fixture
def context():
    fonts = FontRegistry()
    return LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())


@dataclass(frozen=True)
class FixedBlock:
    result: MeasuredBlock
    block_id: str = "child"

    def measure(self, context, available_width):
        return self.result


@dataclass(frozen=True)
class FillBlock:
    rows: int = 1
    block_id: str = "fill"

    def measure(self, context, available_width):
        commands = (Line(1, 2, available_width - 1, 2),)
        return MeasuredBlock(available_width, context.profile.grid.pitch_y,
                             (LayoutPart(self.rows, commands),))


@dataclass(frozen=True)
class BrokenBlock:
    error: Exception
    block_id: str = "broken-child"

    def measure(self, context, available_width):
        raise self.error


def fixed(width=20, rows=1, *, commands=None, keep_with_next=False, block_id="child"):
    if commands is None:
        commands = (Line(1, 2, 9, 2),)
    parts = () if rows == 0 else (LayoutPart(rows, commands),)
    return FixedBlock(MeasuredBlock(width, 15.48, parts,
                      keep_with_next=keep_with_next, block_id=block_id), block_id)


def test_stack_concatenates_prefix_and_parts_at_integer_row_offsets(context):
    first = FixedBlock(MeasuredBlock(40, 15.48,
        (LayoutPart(2, (Line(3, 4, 11, 4),)), LayoutPart(1, (Line(5, 6, 13, 6),))),
        prefix=(LayoutPart(1, (Line(1, 2, 9, 2),)),)))
    last = fixed(30, 2, commands=(Line(7, 8, 15, 8),))
    stack = api().Stack(first, fixed(10, 0), last, block_id="vertical")
    result = measure_block(stack, context, 100)
    assert (result.width, result.rows, result.height, result.block_id) == (40, 6, 92.88, "vertical")
    assert len(result.parts) == 1 and result.prefix == ()
    assert result.commands == (
        Line(1, 2, 9, 2), Line(3, 19.48, 11, 19.48),
        Line(5, 52.44, 13, 52.44), Line(7, 69.92, 15, 69.92),
    )
    assert result.split(3) is None
    assert result.minimum_rows == 6
    assert first.result.commands[0] == Line(1, 2, 9, 2)


def test_stack_measures_every_child_at_full_available_width(context):
    stack = api().Stack(fixed(20, 2), FillBlock(3))
    result = stack.measure(context, 100)
    assert result.width == 100 and result.rows == 5
    assert result.commands[-1] == Line(1, 32.96, 99, 32.96)
    assert stack.measure(context, 60).commands[-1] == Line(1, 32.96, 59, 32.96)
    assert stack.measure(context, 100) == result


def test_stack_children_snapshot_and_result_are_immutable(context):
    child = fixed()
    children = [child]
    stack = api().Stack(*children, block_id="stack")
    children.clear()
    assert stack.children == (child,)
    with pytest.raises(FrozenInstanceError):
        stack.children = ()
    with pytest.raises(FrozenInstanceError):
        stack.block_id = "changed"
    assert stack.measure(context, 100).commands == (Line(1, 2, 9, 2),)


def test_empty_stack_reserves_no_rows_or_commands(context):
    stack = api().Stack()
    result = measure_block(stack, context, 80)
    assert (result.width, result.rows, result.parts, result.commands) == (80, 0, (), ())
    assert result.split(0) is None


@pytest.mark.parametrize("tail,expected", [
    ((False, False), True), ((True, False), False), ((True, True), True),
])
def test_stack_keep_next_uses_last_visible_child_and_ignores_blank_tail(context, tail, expected):
    visible, keep = tail
    heading = fixed(keep_with_next=True)
    body = fixed(commands=None if visible else (), keep_with_next=keep)
    blank = fixed(rows=2, commands=(), keep_with_next=False)
    result = api().Stack(heading, body, blank).measure(context, 100)
    assert result.keep_with_next is expected
    assert result.rows == 4
    assert api().Stack(blank).measure(context, 100).keep_with_next is False


@pytest.mark.parametrize("child", [None, object(), "bad", 3])
def test_stack_defers_nonmeasurable_child_rejection_until_atomic_measure(context, child):
    stack = api().Stack(child, block_id="vertical")
    assert stack.children == (child,)
    with pytest.raises(ValueError, match="vertical.*children\\[0\\].*measure"):
        stack.measure(context, 100)


def test_stack_child_overflow_keeps_diagnostic_dimensions_and_cause(context):
    stack = api().Stack(fixed(101, block_id="too-wide"), block_id="vertical")
    with pytest.raises(LayoutOverflowError, match="vertical.*children\\[0\\].*too-wide") as caught:
        stack.measure(context, 100)
    assert caught.value.block_id == "too-wide"
    assert (caught.value.needed, caught.value.available) == (101, 100)
    assert isinstance(caught.value.__cause__, LayoutOverflowError)


def test_stack_child_font_error_keeps_all_context_and_original_cause(context):
    original = FontError("Missing U+10FFFF")
    stack = api().Stack(BrokenBlock(original), block_id="vertical")
    with pytest.raises(FontError, match="vertical.*children\\[0\\].*broken-child.*U\\+10FFFF") as caught:
        stack.measure(context, 100)
    assert caught.value.__cause__.__cause__ is original


def test_stack_validates_real_child_ink_before_combining(context):
    stack = api().Stack(fixed(commands=(Text(0, 11, "j", TextStyle()),)), block_id="vertical")
    with pytest.raises(LayoutOverflowError, match="vertical.*bounds"):
        stack.measure(context, 100)


@pytest.mark.parametrize("width", [0, -1, True, "100", float("inf"), float("nan")])
def test_stack_rejects_invalid_available_width_even_when_empty(context, width):
    with pytest.raises(ValueError, match="available_width"):
        api().Stack().measure(context, width)


def test_stack_rejects_invalid_context_and_identifier(context):
    with pytest.raises(ValueError, match="context"):
        api().Stack().measure(None, 100)
    with pytest.raises(ValueError, match="block_id"):
        api().Stack(block_id=3)


def test_columns_use_declared_grid_widths_gaps_and_maximum_height(context):
    columns = api().Columns(FillBlock(1), FillBlock(3), FillBlock(2),
                            col_spans=(2, 1, 3), gap_cols=1, block_id="horizontal")
    result = measure_block(columns, context, 130)
    assert result.width == pytest.approx(128.64)
    assert result.rows == 3 and result.height == pytest.approx(46.44)
    assert result.block_id == "horizontal"
    assert len(result.parts) == 1 and result.prefix == ()
    coordinates = [(c.x1, c.y1, c.x2, c.y2) for c in result.commands]
    assert coordinates[0] == pytest.approx((1, 2, 31.16, 2))
    assert coordinates[1] == pytest.approx((49.24, 2, 63.32, 2))
    assert coordinates[2] == pytest.approx((81.4, 2, 127.64, 2))
    assert result.split(2) is None and result.minimum_rows == 3


def test_columns_zero_gap_keep_actual_declared_width_even_with_narrow_children(context):
    columns = api().Columns(fixed(10), fixed(10, 2), col_spans=(2, 3), gap_cols=0)
    result = columns.measure(context, 100)
    assert result.width == pytest.approx(80.4)
    assert result.rows == 2
    assert result.commands[1].x1 == pytest.approx(33.16)
    # Child stroke envelopes stay within separate declared columns.
    assert result.commands[0].x2 + 0.25 < result.commands[1].x1 - 0.25


def test_columns_exact_fit_and_one_point_short_report_dimensions(context):
    columns = api().Columns(FillBlock(), FillBlock(), col_spans=(2, 3), block_id="horizontal")
    assert columns.measure(context, 96.48).width == pytest.approx(96.48)
    with pytest.raises(LayoutOverflowError, match="horizontal.*width") as caught:
        columns.measure(context, 95.48)
    assert caught.value.block_id == "horizontal"
    assert caught.value.needed == pytest.approx(96.48)
    assert caught.value.available == 95.48


def test_columns_child_cannot_exceed_its_declared_span(context):
    columns = api().Columns(fixed(33, block_id="wide-child"), col_spans=(2,), block_id="horizontal")
    with pytest.raises(LayoutOverflowError, match="horizontal.*children\\[0\\].*wide-child") as caught:
        columns.measure(context, 100)
    assert (caught.value.needed, caught.value.available) == pytest.approx((33, 32.16))
    assert isinstance(caught.value.__cause__, LayoutOverflowError)


def test_columns_validate_each_child_before_it_can_overlap_the_next_column(context):
    child = fixed(16.08, commands=(Line(1, 2, 16, 2, width=1),))
    columns = api().Columns(child, fixed(10), col_spans=(1, 1), gap_cols=0)
    with pytest.raises(LayoutOverflowError, match="Columns.*bounds"):
        columns.measure(context, 100)


def test_columns_copy_input_spans_and_children_and_repeat_measure_without_mutation(context):
    child = fixed()
    spans, children = [2], [child]
    columns = api().Columns(*children, col_spans=spans)
    children.clear()
    spans[0] = 99
    assert columns.children == (child,) and columns.col_spans == (2,)
    assert columns.gap_cols == 1
    first = columns.measure(context, 100)
    assert columns.measure(context, 100) == first
    with pytest.raises(FrozenInstanceError):
        columns.col_spans = (3,)
    with pytest.raises(FrozenInstanceError):
        columns.children = ()


@pytest.mark.parametrize("left_visible,left_keep,right_visible,right_keep,expected", [
    (True, True, True, False, True), (True, False, True, True, True),
    (True, False, True, False, False), (False, True, True, False, False),
])
def test_columns_keep_next_if_any_visible_column_requests_it(
    context, left_visible, left_keep, right_visible, right_keep, expected
):
    left = fixed(commands=None if left_visible else (), keep_with_next=left_keep)
    right = fixed(commands=None if right_visible else (), keep_with_next=right_keep)
    result = api().Columns(left, right, col_spans=(2, 2)).measure(context, 100)
    assert result.keep_with_next is expected


def test_empty_columns_reserve_no_rows_and_all_empty_children_keep_declared_width(context):
    result = api().Columns(col_spans=()).measure(context, 80)
    assert (result.width, result.rows, result.parts, result.commands) == (80, 0, (), ())
    result = api().Columns(fixed(10, 0), col_spans=(2,)).measure(context, 80)
    assert result.width == pytest.approx(32.16)
    assert result.parts == () and result.rows == 0


@pytest.mark.parametrize("spans", [(), (1, 2), None, (0,), (-1,), (True,), (1.5,), ("2",), (float("inf"),)])
def test_columns_reject_invalid_or_mismatched_spans(spans):
    with pytest.raises(ValueError, match="col_spans"):
        api().Columns(fixed(), col_spans=spans)


@pytest.mark.parametrize("gap", [-1, True, 1.5, "1", None, float("inf")])
def test_columns_reject_invalid_gap(gap):
    with pytest.raises(ValueError, match="gap_cols"):
        api().Columns(fixed(), col_spans=(2,), gap_cols=gap)


def test_columns_reject_nonmeasurable_child_bad_context_width_and_identifier(context):
    with pytest.raises(ValueError, match="horizontal.*children\\[0\\].*measure"):
        api().Columns(None, col_spans=(1,), block_id="horizontal").measure(context, 100)
    with pytest.raises(ValueError, match="context"):
        api().Columns(col_spans=()).measure(None, 100)
    with pytest.raises(ValueError, match="available_width"):
        api().Columns(col_spans=()).measure(context, 0)
    with pytest.raises(ValueError, match="block_id"):
        api().Columns(col_spans=(), block_id=False)


def test_keep_together_retains_parts_prefix_commands_flags_and_child_identity(context):
    original = MeasuredBlock(60, 15.48,
        (LayoutPart(1, (Line(1, 2, 9, 2),)), LayoutPart(2), LayoutPart(1)),
        prefix=(LayoutPart(1, (Line(3, 4, 11, 4),), {"role": "header"}),),
        break_after=(1, 2), keep_with_next=True, prefer_keep=True, block_id="child-id")
    assert original.split(2) is not None
    child = FixedBlock(original)
    container = api().KeepTogether(child)
    result = measure_block(container, context, 100)
    assert container.block is child
    assert (result.width, result.row_pitch, result.rows, result.height) == (60, 15.48, 5, 77.4)
    assert result.parts == original.parts and result.prefix == original.prefix
    assert result.commands == original.commands
    assert result.break_after == (1, 2)
    assert result.keep_together is True and result.keep_with_next is True
    assert result.prefer_keep is True and result.block_id == "child-id"
    assert result.min_first == original.min_first and result.min_last == original.min_last
    assert result.split(2) is None and result.minimum_rows == 5
    assert original.keep_together is False
    assert container.measure(context, 100) == result
    assert api().KeepTogether(child, block_id="wrapper").measure(context, 100).block_id == "wrapper"
    with pytest.raises(FrozenInstanceError):
        container.block = fixed()


def test_keep_together_uses_shared_measurement_for_child_failure(context):
    with pytest.raises(LayoutOverflowError, match="group.*too-wide") as caught:
        api().KeepTogether(fixed(101, block_id="too-wide"), block_id="group").measure(context, 100)
    assert (caught.value.needed, caught.value.available) == (101, 100)
    assert isinstance(caught.value.__cause__, LayoutOverflowError)
    with pytest.raises(ValueError, match="available_width"):
        api().KeepTogether(fixed()).measure(context, 0)


def test_empty_keep_together_preserves_zero_rows(context):
    result = api().KeepTogether(api().Stack()).measure(context, 80)
    assert (result.width, result.rows, result.commands) == (80, 0, ())
    assert result.keep_together is True and result.split(0) is None


@pytest.mark.parametrize("child", [None, object(), "bad", True])
@pytest.mark.parametrize("kind", ["KeepTogether", "At"])
def test_single_child_containers_reject_nonmeasurable_children(kind, child):
    cls = getattr(api(), kind)
    args = (child,) if kind == "KeepTogether" else (0, 0, 1, child)
    with pytest.raises(ValueError, match="block.*measure"):
        cls(*args)


def test_at_is_an_immutable_flow_directive_without_measurement(context):
    child = fixed()
    at = api().At(3, 2, 5, child, block_id="placed")
    assert (at.row, at.col, at.col_span, at.block, at.block_id) == (3, 2, 5, child, "placed")
    assert not hasattr(at, "measure")
    with pytest.raises(FrozenInstanceError):
        at.row = 4
    with pytest.raises(FrozenInstanceError):
        at.block = fixed()
    # Paper limits are resolved by Document, not this profile-independent directive.
    distant = api().At(10000, 20000, 30000, child)
    assert distant.row == 10000 and distant.col_span == 30000
    assert api().At(0, 0, 1, api().Stack()).row == 0


@pytest.mark.parametrize("field,value", [
    ("row", -1), ("row", True), ("row", 0.5), ("row", None),
    ("col", -1), ("col", False), ("col", "1"), ("col", float("inf")),
    ("col_span", 0), ("col_span", -1), ("col_span", True), ("col_span", 1.5),
])
def test_at_rejects_invalid_grid_indices_and_span(field, value):
    values = {"row": 0, "col": 0, "col_span": 1, "block": fixed()}
    values[field] = value
    with pytest.raises(ValueError, match=field):
        api().At(**values)


@pytest.mark.parametrize("kind", ["At", "KeepTogether"])
def test_single_child_containers_reject_invalid_identifier(kind):
    cls = getattr(api(), kind)
    args = (fixed(),) if kind == "KeepTogether" else (0, 0, 1, fixed())
    with pytest.raises(ValueError, match="block_id"):
        cls(*args, block_id=42)


def test_nested_containers_measure_without_drawing_and_preserve_known_offsets(context, monkeypatch):
    from reportlab.pdfgen import canvas

    def no_canvas(*args, **kwargs):
        pytest.fail("Container measurement cannot construct a PDF Canvas")

    monkeypatch.setattr(canvas, "Canvas", no_canvas)
    module = api()
    columns = module.Columns(fixed(rows=1), fixed(rows=2), col_spans=(2, 2))
    stack = module.Stack(columns, fixed())
    result = measure_block(module.KeepTogether(stack), context, 100)
    assert result.rows == 3 and len(result.commands) == 3
    coordinates = [(c.x1, c.y1, c.x2, c.y2) for c in result.commands]
    assert coordinates[0] == pytest.approx((1, 2, 9, 2))
    assert coordinates[1] == pytest.approx((49.24, 2, 57.24, 2))
    assert coordinates[2] == pytest.approx((1, 32.96, 9, 32.96))
    assert result.split(1) is None


@pytest.mark.parametrize("kind", ["Stack", "Columns"])
def test_atomic_container_trace_retains_children_prefix_and_body_metadata(context, kind):
    original = MeasuredBlock(20, 15.48,
        (LayoutPart(2, (Line(1, 2, 9, 2),), {"anchors": {"relation": [8, 12]}}),
         LayoutPart(1, metadata={"line": 2})),
        prefix=(LayoutPart(1, metadata={"role": "header"}),), block_id="first")
    second = fixed(20, 2, block_id="second")
    module = api()
    container = (module.Stack(FixedBlock(original), second) if kind == "Stack" else
                 module.Columns(FixedBlock(original), second, col_spans=(2, 2)))
    result = container.measure(context, 100)
    children = result.parts[0].metadata["children"]
    assert children[0]["block_id"] == "first"
    assert (children[0]["x_pt"], children[0]["y_pt"], children[0]["width"], children[0]["rows"]) == (0, 0, 20, 4)
    assert children[0]["prefix"] == ({"row": 0, "rows": 1, "metadata": {"role": "header"}},)
    assert children[0]["parts"][0]["row"] == 1 and children[0]["parts"][0]["rows"] == 2
    assert children[0]["parts"][1]["row"] == 3
    assert children[0]["parts"][0]["metadata"]["anchors"]["relation"] == (8, 12)
    expected_origin = (0, 61.92) if kind == "Stack" else (48.24, 0)
    assert (children[1]["x_pt"], children[1]["y_pt"]) == pytest.approx(expected_origin)
    assert children[1]["block_id"] == "second"
    assert result.rows == (6 if kind == "Stack" else 4)
    assert result.commands[-1].x1 == pytest.approx(expected_origin[0] + 1)
    assert result.commands[-1].y1 == pytest.approx(expected_origin[1] + 2)
    with pytest.raises(TypeError):
        children[0]["parts"][0]["metadata"]["anchors"]["relation"][0] = 99
    with pytest.raises(TypeError):
        children[1]["x_pt"] = 999
    assert "commands" not in children[0]


def test_nested_container_trace_survives_keep_together(context):
    module = api()
    leaf = FixedBlock(MeasuredBlock(20, 15.48, (LayoutPart(1, metadata={"anchors": {"equals": 7}}),),
                                   block_id="equation"))
    nested = module.Stack(module.Columns(module.KeepTogether(leaf), col_spans=(2,), block_id="columns"))
    result = module.KeepTogether(nested).measure(context, 100)
    columns = result.parts[0].metadata["children"][0]
    assert columns["block_id"] == "columns"
    equation = columns["parts"][0]["metadata"]["children"][0]
    assert equation["block_id"] == "equation"
    assert equation["parts"][0]["metadata"]["anchors"]["equals"] == 7
    assert equation["x_pt"] == equation["y_pt"] == 0


@pytest.mark.parametrize("text", ["", " ", "\u3000"])
def test_atomic_stack_preserves_heading_keep_next_across_blank_text_commands(context, text):
    from gridlayoutpdf.blocks import Heading
    from gridlayoutpdf.equations import MathBlock

    blank = MathBlock(text)
    result = api().Stack(Heading("Heading"), blank).measure(context, 100)
    assert result.rows == 2 and result.keep_with_next is True
    assert result.commands[-1].text == text


@pytest.mark.parametrize("text", [" ", "\u3000"])
def test_columns_ignore_blank_heading_keep_flag_and_preserve_real_heading_flag(context, text):
    from gridlayoutpdf.blocks import Heading, Paragraph

    result = api().Columns(Heading(text), Paragraph("body"), col_spans=(5, 5)).measure(context, 200)
    assert result.rows == 1 and result.keep_with_next is False
    result = api().Columns(api().Stack(Heading("Heading"), Paragraph(text)), Paragraph("body"),
                           col_spans=(5, 5)).measure(context, 200)
    assert result.rows == 2 and result.keep_with_next is True


@pytest.mark.parametrize("wide,outer_span,inner_span,padding,expected_width", [
    (False, 9, 7, 16.08, 112.56),
    (True, 34, 33, 8.04, 530.64),
])
@pytest.mark.parametrize("align", ["left", "center", "right"])
def test_columns_exact_grid_width_survives_table_padding_roundoff(
    context, wide, outer_span, inner_span, padding, expected_width, align,
):
    from gridlayoutpdf.blocks import Paragraph
    from gridlayoutpdf.bounds import command_bounds
    from gridlayoutpdf.document import Document
    from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE
    from gridlayoutpdf.tables import Cell, Table

    profile = A3_LANDSCAPE_REFERENCE if wide else A4_PORTRAIT_REFERENCE
    columns = api().Columns(Paragraph("A"), col_spans=(inner_span,), block_id="inner-columns")
    table = Table((outer_span,), [[Cell(columns, padding=padding, align=align)]], block_id="outer-table")
    pages = Document(table, fonts=context.fonts, profile=profile).layout()
    assert len(pages) == 1
    cell = pages[0].metadata["placements"][0]["parts"][0]["metadata"]["cells"][0]
    assert cell["content"]["width"] == pytest.approx(expected_width)
    text = [command for command in pages[0].commands if isinstance(command, Text)]
    assert len(text) == 1 and text[0].text == "A" and text[0].style.size == 10
    assert command_bounds(text[0], context.fonts).x == pytest.approx(50.88 + padding)


@pytest.mark.parametrize("wide,outer_span,inner_span,padding", [
    (False, 9, 7, 16.08),
    (True, 34, 33, 8.04),
])
@pytest.mark.parametrize("align", ["left", "center", "right"])
def test_columns_real_width_shortage_in_table_still_reports_needed_available_and_path(
    context, wide, outer_span, inner_span, padding, align,
):
    from gridlayoutpdf.blocks import Paragraph
    from gridlayoutpdf.document import Document
    from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE
    from gridlayoutpdf.tables import Cell, Table

    profile = A3_LANDSCAPE_REFERENCE if wide else A4_PORTRAIT_REFERENCE
    columns = api().Columns(Paragraph("A"), col_spans=(inner_span,), block_id="inner-columns")
    # Add .00005 pt on both sides: a real .0001 pt shortage exceeds rounding tolerance.
    table = Table((outer_span,), [[Cell(columns, padding=padding + .00005, align=align)]], block_id="outer-table")
    with pytest.raises(LayoutOverflowError) as caught:
        Document(table, fonts=context.fonts, profile=profile).layout()
    assert caught.value.block_id == "outer-table.rows[0].cells[0]"
    assert caught.value.needed - caught.value.available == pytest.approx(.0001)
    assert "outer-table.rows[0].cells[0]" in str(caught.value)
    assert "inner-columns" in str(caught.value)
    assert caught.value.__cause__ is not None
