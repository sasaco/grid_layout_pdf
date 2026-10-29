"""A closed Polyline can be filled, like Rectangle and Circle (FR-029)."""

import pytest

import gridlayoutpdf as api
from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, Figure, FontRegistry, GridSpec, LayoutContext, LayoutPart, MeasuredBlock,
    Point, Polyline, QuarterTurn, Rect, ReportStyle, ScenePage, command_bounds, layout_trace, measure_block,
)

TRIANGLE = ((10, 20), (30, 20), (20, 40))


@pytest.fixture
def fonts():
    return FontRegistry()


def test_a_polyline_is_unfilled_and_stroked_by_default():
    polyline = Polyline(TRIANGLE, closed=True)
    assert polyline.fill is None and polyline.stroke is True
    assert Polyline(TRIANGLE) == Polyline(TRIANGLE, fill=None, stroke=True)


def test_a_closed_polyline_can_fill_with_or_without_a_stroke(fonts):
    filled = Polyline(TRIANGLE, 1, (0, 0, 1), True, fill=[1, 0, 0])
    assert filled.fill == (1.0, 0.0, 0.0) and filled.stroke is True
    assert filled.translated(1, 2).fill == (1.0, 0.0, 0.0)
    assert filled != Polyline(TRIANGLE, 1, (0, 0, 1), True)
    assert command_bounds(filled, fonts) == Rect(9.5, 19.5, 21, 21)
    bare = Polyline(TRIANGLE, closed=True, fill=(0, 0, 0), stroke=False)
    assert command_bounds(bare, fonts) == Rect(10, 20, 20, 20)


@pytest.mark.parametrize("kwargs, message", [
    ({"closed": False, "fill": (0, 0, 0)}, "closed"),
    ({"fill": (2, 0, 0)}, "fill"), ({"fill": (0, 0)}, "fill"), ({"fill": "white"}, "fill"),
    ({"stroke": 1}, "stroke"), ({"stroke": False}, "stroke or fill"),
    ({"closed": False, "stroke": False}, "stroke or fill"),
])
def test_polyline_paint_options_are_validated(kwargs, message):
    arguments = {"closed": True, **kwargs}
    with pytest.raises(ValueError, match=message):
        Polyline(TRIANGLE, **arguments)


def test_fill_is_traced_only_when_used(fonts):
    page = ScenePage(A4_PORTRAIT_REFERENCE, (
        Polyline(TRIANGLE, closed=True, fill=(1, 1, 0), stroke=False),
        Polyline(TRIANGLE, closed=True, fill=(0, 0, 0)),
        Polyline(TRIANGLE, closed=True),
    ))
    bare, filled, plain = layout_trace([page], fonts)["pages"][0]["commands"]
    assert bare["fill"] == [1, 1, 0] and bare["stroke"] is False
    assert bare["bounds"] == {"x": 10, "y": 20, "width": 20, "height": 20}
    assert filled["fill"] == [0, 0, 0] and "stroke" not in filled
    assert "fill" not in plain and "stroke" not in plain


def test_filled_polylines_flow_through_figures_and_rotation(fonts):
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())
    filled = Polyline(((2, 2), (8, 2), (5, 8)), closed=True, fill=(0, 0, 0), stroke=False)
    assert measure_block(Figure(2, 1, filled), context, 100).commands == (filled,)

    class Fixed:
        def measure(self, context, available_width):
            return MeasuredBlock(20, context.profile.grid.pitch_y, (LayoutPart(1, (filled,)),))

    local = GridSpec(0, 0, 10, context.profile.grid.pitch_y, 2, 1)
    (rotated,) = measure_block(QuarterTurn(Fixed(), turns=1, local_grid=local), context, 100).commands
    assert rotated.fill == (0, 0, 0) and rotated.stroke is False
    assert rotated.points == (Point(2, 18), Point(2, 12), Point(8, 15))
    assert "Polyline" in api.__all__
