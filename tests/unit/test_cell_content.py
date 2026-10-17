"""Explicit cell lines reserve physical height before one grid rounding."""

from dataclasses import FrozenInstanceError, dataclass, replace
import importlib
from math import nextafter
from pathlib import Path

import pytest

from gridlayoutpdf import (A4_PORTRAIT_REFERENCE, Cell, FontRegistry, Fraction, GridSpec,
                          FontError, LayoutContext, LayoutOverflowError, Literal, MathBox, PageProfile,
                          ReportStyle, Script, Table, Text, TextStyle, measure_block)
from gridlayoutpdf.styles import Insets


def lines(*args, **kwargs):
    spec = importlib.util.find_spec("gridlayoutpdf.cell_content")
    assert spec is not None, "CellLines must be implemented"
    return importlib.import_module("gridlayoutpdf.cell_content").CellLines(*args, **kwargs)


@pytest.fixture
def context():
    fonts = FontRegistry()
    fonts.register("body", Path(__file__).parents[1] / "fixtures/fonts/ipaexm.ttf")
    return LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())


def test_two_lines_round_once_and_keep_explicit_baselines(context):
    block = lines(("first", "second"), line_advance=12.8, inner_padding=.6, block_id="dense")
    result = measure_block(block, context, 100)
    assert result.rows == 2 and len(result.parts) == 1 and result.split(1) is None
    text = [c for c in result.commands if isinstance(c, Text)]
    assert [c.text for c in text] == ["first", "second"]
    assert text[1].y - text[0].y == pytest.approx(12.8)
    metadata = result.parts[0].metadata
    assert metadata["height_rounding"] == "single"
    assert metadata["line_count"] == 2 and metadata["line_advance"] == 12.8
    assert metadata["required_height_pt"] < 2 * context.profile.grid.pitch_y
    table = Table((7,), ((Cell(block, padding=0),),))
    assert table.measure(context, 120).rows == 2
    outer = replace(table, rows=((Cell(block, padding=.6),),)).measure(context, 120)
    assert outer.rows == 3
    assert outer.parts[0].metadata["cells"][0]["height_allocation"]["child_rounding_then_outer_padding"]


@pytest.mark.parametrize("align,factor", [("left", 0), ("center", .5), ("right", 1)])
def test_line_alignment_and_edge_padding_use_unscaled_intrinsic_width(context, align, factor):
    result = lines(("WWWW", "I"), align=align, inner_padding=Insets(left=2, right=3)).measure(context, 100)
    long, short = result.commands
    a = Literal("WWWW").measure(context.fonts, context.style.body)
    b = Literal("I").measure(context.fonts, context.style.body)
    assert result.width == pytest.approx(a.width + 5)
    assert short.x - long.x == pytest.approx((a.width - b.width) * factor)


def test_line_styles_are_copied_and_preserve_sizes_and_blank_lines(context):
    inputs = ["A", "", "B"]
    styles = [TextStyle(size=8), None, TextStyle(size=11)]
    block = lines(inputs, line_styles=styles, line_advance=15)
    inputs.clear()
    styles.clear()
    result = measure_block(block, context, 100)
    text = [c for c in result.commands if isinstance(c, Text) and c.text]
    assert [c.style.size for c in text] == [8, 11]
    assert text[1].y - text[0].y == pytest.approx(30)
    with pytest.raises(FrozenInstanceError):
        block.line_advance = 1
    assert lines(("", ""), line_advance=20).measure(context, 100).rows >= 2
    assert lines(()).measure(context, 100).rows == 1


@pytest.mark.parametrize("field,value", [
    ("lines", "abc"), ("lines", (None,)), ("lines", ("a\nb",)),
    ("lines", ("a\tb",)), ("style", "body"), ("line_styles", ()),
    ("line_styles", ("body",)), ("line_advance", 0), ("line_advance", True),
    ("line_advance", float("nan")), ("min_height", -1), ("min_height", True),
    ("inner_padding", -1), ("inner_padding", float("inf")), ("align", "justify"),
    ("block_id", 1),
])
def test_invalid_explicit_lines_options(field, value):
    with pytest.raises(ValueError):
        lines(**{"lines": ("A",), field: value})


def test_overflow_and_ink_contact_identify_block_and_line(context):
    with pytest.raises(LayoutOverflowError, match=r"narrow.*line 1"):
        lines(("long text",), block_id="narrow").measure(context, 1)
    with pytest.raises(LayoutOverflowError, match=r"touch.*line 2.*line 1"):
        lines(("日本語", "日本語"), line_advance=1, block_id="touch").measure(context, 100)


def test_fraction_and_script_lines_use_full_math_extents_and_reject_contact(context):
    result = measure_block(lines((Fraction("1", "2"), Script("x", superscript="2")), line_advance=35), context, 100)
    assert result.rows >= 3
    with pytest.raises(LayoutOverflowError, match="line"):
        lines((Fraction("1", "2"), "next"), line_advance=1).measure(context, 100)


def test_min_height_strict_grid_boundary_and_fine_pitch(context):
    pitch = context.profile.grid.pitch_y
    assert lines((), min_height=pitch).measure(context, 100).rows == 1
    assert lines((), min_height=nextafter(pitch, float("inf"))).measure(context, 100).rows == 2
    fine = replace(context, profile=PageProfile("fine", 300, 400, GridSpec(20, 20, .12, .12, 2000, 3000)))
    result = measure_block(lines(("A", "B"), line_advance=12.8, inner_padding=.6), fine, 100)
    assert result.height >= result.parts[0].metadata["required_height_pt"]
    assert result.height - result.parts[0].metadata["required_height_pt"] < .12


def test_measure_rejects_invalid_context_width_and_missing_fonts(context):
    block = lines(("a",))
    with pytest.raises(ValueError, match="context"):
        block.measure(None, 100)
    for width in (0, True, float("inf")):
        with pytest.raises(ValueError, match="available_width"):
            block.measure(context, width)
    with pytest.raises(FontError, match=r"unknown-font.*line 1"):
        lines(("A",), style=TextStyle(font="absent"), block_id="unknown-font").measure(context, 100)


@dataclass(frozen=True)
class BrokenNode:
    result: object

    def measure(self, fonts, style):
        return self.result


def test_math_nodes_cannot_hide_commands_outside_their_declared_reservation(context):
    bad = BrokenNode(MathBox(5, 1, 1, (Text(0, 0, "A", TextStyle(size=30)),), 0))
    with pytest.raises(LayoutOverflowError, match=r"outside.*line 1.*reserved"):
        lines((bad,), block_id="outside").measure(context, 100)
    with pytest.raises(ValueError, match=r"broken.*line 1.*MathBox"):
        lines((BrokenNode(None),), block_id="broken").measure(context, 100)


@pytest.mark.parametrize("dx,dy,axis", [(30, 0, "horizontal"), (-30, 0, "horizontal"),
                                        (1, 30, "vertical"), (1, -30, "vertical")])
@pytest.mark.parametrize("padding", [Insets(), Insets(2, 3, 1, 4)])
def test_displaced_math_commands_report_overflow_capacity_on_the_violated_axis(context, dx, dy, axis, padding):
    style = TextStyle()
    node = BrokenNode(MathBox(10, 10, 3, (Text(dx, dy, "A", style),), 0))
    with pytest.raises(LayoutOverflowError) as caught:
        lines((node,), inner_padding=padding, block_id="displaced").measure(context, 100)
    error = caught.value
    assert error.block_id == "displaced"
    assert f"line 1 exceeds reserved content bounds ({axis})" in str(error)
    glyph = context.fonts.measure("A", style).bounds
    if axis == "horizontal":
        expected_capacity = 10
        expected_shortage = (dx + glyph.right - 10) if dx > 0 else -(dx + glyph.x)
    else:
        frame_height = context.rows_for(13 + padding.top + padding.bottom) * context.profile.grid.pitch_y
        expected_capacity = frame_height - padding.top - padding.bottom
        baseline_within_content = 10 + (expected_capacity - 13) / 2
        expected_shortage = ((baseline_within_content + dy + glyph.bottom - expected_capacity)
                             if dy > 0 else -(baseline_within_content + dy + glyph.y))
    assert error.available == pytest.approx(expected_capacity)
    assert error.needed == pytest.approx(expected_capacity + expected_shortage)
    assert error.needed > error.available


def test_padding_cannot_exhaust_width_and_nonsequence_styles_rejected(context):
    with pytest.raises(LayoutOverflowError, match="inner_padding"):
        lines(("A",), inner_padding=Insets(left=60, right=40)).measure(context, 100)
    with pytest.raises(ValueError, match="line_styles"):
        lines(("A",), line_styles=1)


def test_actual_ink_contact_check_allows_safe_overlapping_font_metric_boxes(context):
    # IPAex's conservative 10pt line envelopes overlap at 8pt advance, while
    # these lowercase glyphs have smaller actual ink rectangles and stay apart.
    result = measure_block(lines(("xxx", "xxx"), line_advance=8), context, 100)
    assert result.commands[1].y - result.commands[0].y == pytest.approx(8)


def test_cell_lines_and_insets_fit_exact_row_height_without_expansion(context):
    content = lines(("A",), inner_padding=1)
    table = Table((4,), ((Cell(content, padding=Insets(top=1, bottom=1)),),), row_heights=(2,))
    assert table.measure(context, 100).rows == 2
    with pytest.raises(LayoutOverflowError, match="row_heights"):
        replace(table, row_heights=(1,)).measure(context, 100)
