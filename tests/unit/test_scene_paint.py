"""Dash patterns, filled shapes, circles and proportional column spans."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import gridlayoutpdf as api
from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, Figure, FontRegistry, GridSpec, LayoutContext, LayoutPart, Line,
    MeasuredBlock, PageProfile, Point, Polyline, QuarterTurn, Rect, Rectangle, ReportStyle,
    ScenePage, command_bounds, layout_trace, measure_block,
)


@pytest.fixture
def fonts():
    registry = FontRegistry()
    return registry


def test_lines_and_polylines_carry_a_validated_immutable_dash_pattern():
    line = Line(0, 0, 10, 0, dash=[2, 1.5])
    assert line.dash == (2.0, 1.5) and Line(0, 0, 1, 0).dash == ()
    assert line.translated(1, 1).dash == (2.0, 1.5)
    polyline = Polyline(((0, 0), (5, 5)), dash=(3,))
    assert polyline.dash == (3.0,) and polyline.translated(1, 0).dash == (3.0,)
    with pytest.raises(FrozenInstanceError):
        line.dash = ()


@pytest.mark.parametrize("dash", [(0, 1), (-1,), (float("nan"),), (True,), "2 2", 3, ("a",)])
def test_dash_lengths_must_be_positive_finite_numbers(dash):
    with pytest.raises(ValueError, match="dash"):
        Line(0, 0, 1, 0, dash=dash)
    with pytest.raises(ValueError, match="dash"):
        Polyline(((0, 0), (1, 1)), dash=dash)


def test_dash_does_not_change_stroke_bounds(fonts):
    assert command_bounds(Line(0, 0, 10, 0, 2, dash=(1, 1)), fonts) == command_bounds(Line(0, 0, 10, 0, 2), fonts)


def test_rectangles_can_fill_with_or_without_a_stroke(fonts):
    filled = Rectangle(10, 20, 30, 40, fill=(1, 1, 1), stroke=False)
    assert filled.fill == (1.0, 1.0, 1.0) and filled.stroke is False
    assert command_bounds(filled, fonts) == Rect(10, 20, 30, 40)
    outlined = Rectangle(10, 20, 30, 40, 2, fill=[0, 0, 0])
    assert outlined.fill == (0.0, 0.0, 0.0)
    assert command_bounds(outlined, fonts) == Rect(9, 19, 32, 42)
    assert Rectangle(0, 0, 1, 1).fill is None and Rectangle(0, 0, 1, 1).stroke is True


@pytest.mark.parametrize("kwargs, message", [
    ({"fill": (2, 0, 0)}, "fill"), ({"fill": (0, 0)}, "fill"), ({"fill": "white"}, "fill"),
    ({"stroke": 1}, "stroke"), ({"stroke": False}, "stroke or fill"),
])
def test_rectangle_paint_options_are_validated(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Rectangle(0, 0, 1, 1, **kwargs)


def test_circle_is_a_validated_translatable_command(fonts):
    circle = api.Circle(10, 20, 3, stroke_width=1, fill=(0, 0, 0))
    assert (circle.x, circle.y, circle.radius, circle.stroke) == (10, 20, 3, True)
    assert circle.translated(1, 2) == api.Circle(11, 22, 3, stroke_width=1, fill=(0, 0, 0))
    assert command_bounds(circle, fonts) == Rect(6.5, 16.5, 7, 7)
    disk = api.Circle(10, 20, 1.7, fill=(0, 0, 0), stroke=False)
    bounds = command_bounds(disk, fonts)
    assert (bounds.x, bounds.y, bounds.right, bounds.bottom) == pytest.approx((8.3, 18.3, 11.7, 21.7))
    for kwargs in ({"radius": 0}, {"radius": -1}, {"radius": float("inf")}):
        with pytest.raises(ValueError, match="radius"):
            api.Circle(0, 0, **kwargs)
    with pytest.raises(ValueError, match="stroke or fill"):
        api.Circle(0, 0, 1, stroke=False)
    assert api.Circle in api.Command.__args__ and "Circle" in api.__all__


def test_circles_flow_through_parts_scenes_figures_rotation_and_trace(fonts):
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())
    circle = api.Circle(5, 5, 2, fill=(1, 1, 1), stroke=False)
    part = LayoutPart(1, (circle,))
    assert part.commands == (circle,)
    page = ScenePage(A4_PORTRAIT_REFERENCE, (circle, Rectangle(0, 0, 4, 4, fill=(0, 0, 0)),
                                            Line(0, 0, 4, 0, dash=(1, 2))))
    trace = layout_trace([page], fonts)["pages"][0]["commands"]
    assert trace[0] == {"index": 0, "type": "Circle", "bounds": {"x": 3, "y": 3, "width": 4, "height": 4},
                        "x": 5, "y": 5, "radius": 2, "stroke_width": .5, "color": [0, 0, 0],
                        "fill": [1, 1, 1], "stroke": False}
    assert trace[1]["fill"] == [0, 0, 0] and "stroke" not in trace[1]
    assert trace[2]["dash"] == [1, 2]
    plain = layout_trace([ScenePage(A4_PORTRAIT_REFERENCE, (Line(0, 0, 4, 0), Rectangle(0, 0, 4, 4)))], fonts)
    assert all("dash" not in c and "fill" not in c for c in plain["pages"][0]["commands"])
    figure = measure_block(Figure(2, 1, circle), context, 100)
    assert figure.commands == (circle,)
    with pytest.raises(Exception, match="bounds"):
        measure_block(Figure(1, 1, api.Circle(5, 5, 6, fill=(0, 0, 0))), context, 100)

    class Fixed:
        def measure(self, context, available_width):
            return MeasuredBlock(20, context.profile.grid.pitch_y, (LayoutPart(1, (api.Circle(4, 3, 2, fill=(0, 0, 0)),)),))

    local = GridSpec(0, 0, 10, context.profile.grid.pitch_y, 2, 1)
    rotated = measure_block(QuarterTurn(Fixed(), turns=1, local_grid=local), context, 100)
    assert rotated.commands[0] == api.Circle(3, 16, 2, fill=(0, 0, 0))


def test_proportional_spans_round_cumulative_boundaries_and_keep_the_total():
    assert api.proportional_spans((1, 1, 1), 10) == (3, 4, 3)
    assert api.proportional_spans((2, 1), 4400) == (2933, 1467)
    assert api.proportional_spans([0.5, 0.25, 0.25], 4) == (2, 1, 1)
    assert api.proportional_spans((1,), 7) == (7,)
    assert sum(api.proportional_spans((3, 7, 11, 13), 4400)) == 4400


@pytest.mark.parametrize("weights, total", [
    ((), 10), ((1, -1), 10), ((0, 0), 10), ((1, float("nan")), 10), ((True,), 10),
    ((1,), 0), ((1,), 1.5), ((1, 1), 1),
])
def test_proportional_spans_reject_invalid_weights_and_empty_columns(weights, total):
    with pytest.raises(ValueError):
        api.proportional_spans(weights, total)
