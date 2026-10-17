"""Immutable edge padding and consistent table reservation diagnostics."""

from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import pytest

import gridlayoutpdf.styles as styles
from gridlayoutpdf import (A4_PORTRAIT_REFERENCE, Cell, FontRegistry, LayoutContext,
                          LayoutOverflowError, LayoutPart, Line, MeasuredBlock,
                          ReportStyle, Table, measure_block)


def insets(*args, **kwargs):
    assert hasattr(styles, "Insets"), "Insets must be implemented"
    return styles.Insets(*args, **kwargs)


@pytest.fixture
def context():
    fonts = FontRegistry()
    fonts.register("body", Path(__file__).parents[1] / "fixtures/fonts/ipaexm.ttf")
    return LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())


@dataclass(frozen=True)
class Content:
    rows: int = 1

    def measure(self, context, available_width):
        return MeasuredBlock(10, context.profile.grid.pitch_y,
                             (LayoutPart(self.rows, (Line(1, 2, 9, 2, .1),)),), block_id="child")


def test_insets_are_immutable_zero_default_and_scalar_is_unchanged(context):
    assert insets() == insets(0, 0, 0, 0)
    value = insets(1, 2, 3, 4)
    with pytest.raises(FrozenInstanceError):
        value.top = 9
    plain = Table((4,), ((Cell(Content(), padding=3),),))
    edged = replace(plain, rows=((Cell(Content(), padding=insets(3, 3, 3, 3)),),))
    assert plain.measure(context, 100) == edged.measure(context, 100)
    assert plain.rows[0][0].padding == 3


@pytest.mark.parametrize("edge", ["top", "right", "bottom", "left"])
@pytest.mark.parametrize("value", [-1, True, None, "1", float("inf"), float("nan")])
def test_invalid_edge_rejected(edge, value):
    with pytest.raises(ValueError, match=edge):
        insets(**{edge: value})


@pytest.mark.parametrize("align,factor", [("left", 0), ("center", .5), ("right", 1)])
@pytest.mark.parametrize("valign,vfactor", [("top", 0), ("middle", .5), ("bottom", 1)])
def test_asymmetric_edges_use_same_inner_frame_for_all_alignment(context, align, factor, valign, vfactor):
    result = measure_block(Table((4,), ((Cell(Content(), padding=insets(1, 7, 2, 4),
                                               align=align, valign=valign),),)), context, 100)
    cell = result.parts[0].metadata["cells"][0]
    assert result.rows == 2
    assert cell["content"]["x_pt"] == pytest.approx(4 + (64.32 - 11 - 10) * factor)
    assert cell["content"]["y_pt"] == pytest.approx(1 + (30.96 - 3 - 15.48) * vfactor)
    assert cell["padding_pt"] == {"top": 1, "right": 7, "bottom": 2, "left": 4}
    assert cell["height_allocation"]["child_reserved_height_pt"] == pytest.approx(15.48)
    assert cell["height_allocation"]["required_height_pt"] == pytest.approx(18.48)
    assert cell["height_allocation"]["required_rows"] == 2


def test_horizontal_padding_does_not_add_rows_and_checks_width(context):
    result = Table((4,), ((Cell(Content(), padding=insets(right=7, left=4)),),)).measure(context, 100)
    assert result.rows == 1
    with pytest.raises(LayoutOverflowError, match="padding leaves"):
        Table((1,), ((Cell(Content(), padding=insets(left=17)),),)).measure(context, 100)


def test_rowspan_reports_last_row_increment_and_controller(context):
    table = Table((4, 4), ((Cell(Content(5), rowspan=2, padding=0), Cell(Content(), padding=0)),
                           (Cell(Content(), padding=0),)), block_id="span")
    result = table.measure(context, 150)
    allocations = result.parts[0].metadata["row_allocations"]
    assert [row["allocated_rows"] for row in allocations] == [1, 4]
    assert allocations[1]["rowspan_added_rows"] == 3
    assert "span.rows[0].cells[0]" in allocations[1]["controlling_cell_ids"]
    assert result.parts[0].metadata["height_mode"] == "automatic"


def test_exact_row_heights_keep_explicit_mode_and_reject_padding_shortage(context):
    table = Table((4,), ((Cell(Content(), padding=insets(bottom=15.48)),),), row_heights=(2,))
    result = table.measure(context, 100)
    metadata = result.parts[0].metadata
    assert metadata["height_mode"] == "explicit"
    assert metadata["row_allocations"][0]["specified_rows"] == 2
    with pytest.raises(LayoutOverflowError, match="row_heights"):
        replace(table, row_heights=(1,)).measure(context, 100)
