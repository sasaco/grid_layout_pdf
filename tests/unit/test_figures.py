from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from gridlayoutpdf.bounds import command_bounds
from gridlayoutpdf.errors import FontError, LayoutOverflowError
from gridlayoutpdf.figures import Arrow, Figure, Label
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.geometry import GridSpec, Point
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.profiles import PageProfile
from gridlayoutpdf.scene import Line, Polyline, Rectangle, Text
from gridlayoutpdf.styles import ReportStyle, TextStyle


@pytest.fixture(scope="module")
def context():
    fonts = FontRegistry()
    profile = PageProfile("figure", 200, 200, GridSpec(0, 0, 10, 10, 20, 20))
    return LayoutContext(fonts, profile, ReportStyle())


def test_figure_measures_declared_grid_frame_and_snapshots_commands(context):
    items = [Rectangle(1, 1, 28, 18, 1), Line(2, 10, 28, 10)]
    figure = Figure(3, 2, *items, block_id="beam")
    items.clear()
    measured = measure_block(figure, context, 40)
    assert (measured.width, measured.rows, measured.height) == (30, 2, 20)
    assert measured.block_id == "beam" and measured.keep_together
    assert measured.commands == figure.items
    assert len(measured.parts) == 1 and measured.parts[0].rows == 2
    assert measured.split(1) is None
    moved = measured.translated(40, 30)
    assert moved[0] == Rectangle(41, 31, 28, 18, 1)
    assert measure_block(figure, context, 40) == measured
    with pytest.raises(FrozenInstanceError):
        figure.rows = 9


@pytest.mark.parametrize("col_span, rows", [(0, 2), (1, 0), (-1, 2), (1, -1), (True, 2), (2, False), (1.5, 2), (1, "2")])
def test_figure_requires_positive_integer_grid_frame(col_span, rows):
    with pytest.raises(ValueError):
        Figure(col_span, rows)


def test_figure_rejects_invalid_items_context_and_width(context):
    with pytest.raises(ValueError, match="items"):
        Figure(3, 2, object())
    with pytest.raises(ValueError, match="block_id"):
        Figure(3, 2, block_id=3)
    with pytest.raises(ValueError, match="context"):
        Figure(3, 2).measure(None, 30)
    for width in (0, -1, True, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="available_width"):
            Figure(3, 2).measure(context, width)
    with pytest.raises(LayoutOverflowError) as caught:
        Figure(3, 2, block_id="load").measure(context, 29)
    assert (caught.value.block_id, caught.value.needed, caught.value.available) == ("load", 30, 29)


@pytest.mark.parametrize("command", [
    Line(.4, 5, 10, 5, 1), Line(10, 5, 29.6, 5, 1),
    Line(5, .4, 5, 10, 1), Line(5, 10, 5, 19.6, 1),
    Text(0, 10, "j", TextStyle()), Text(24, 10, "Å", TextStyle()),
    Text(5, 8, "Å", TextStyle()), Text(5, 19, "g", TextStyle()),
])
def test_figure_direct_measure_checks_ink_and_strokes_on_all_edges(context, command):
    with pytest.raises(LayoutOverflowError, match="load") as caught:
        Figure(3, 2, command, block_id="load").measure(context, 30)
    assert caught.value.block_id == "load"


def test_figure_font_error_has_item_path_and_cause(context):
    with pytest.raises(FontError, match=r"load.items\[0\]") as caught:
        Figure(3, 2, Text(1, 10, "\U0010ffff", TextStyle()), block_id="load").measure(context, 30)
    assert isinstance(caught.value.__cause__, FontError)


@pytest.mark.parametrize("end, expected", [
    ((25, 10), ((19, 12), (25, 10), (19, 8))),
    ((5, 30), ((3, 24), (5, 30), (7, 24))),
    ((17, 26), ((11.8, 22.4), (17, 26), (15, 20))),
])
def test_arrow_is_vector_shaft_and_open_head_in_any_direction(context, end, expected):
    arrow = Arrow(5, 10, *end)
    measured = Figure(4, 4, arrow).measure(context, 40)
    shaft, head = measured.commands
    assert shaft == Line(5, 10, *end, .6)
    assert isinstance(head, Polyline) and not head.closed
    for point, expected_point in zip(head.points, expected, strict=True):
        assert (point.x, point.y) == pytest.approx(expected_point)
    assert head.width == .6
    with pytest.raises(FrozenInstanceError):
        arrow.head_width = 10


@pytest.mark.parametrize("kwargs", [
    {"x2": 5, "y2": 10}, {"head_length": 21}, {"head_length": 0},
    {"head_width": -1}, {"width": 0}, {"width": True}, {"x1": float("nan")},
    {"y2": float("inf")}, {"color": (2, 0, 0)}, {"color": (0, 0)},
    {"head_length": float("inf")}, {"head_width": True},
])
def test_arrow_invalid_geometry_and_style_fail_at_construction(kwargs):
    with pytest.raises(ValueError):
        Arrow(**{ "x1": 5, "y1": 10, "x2": 25, "y2": 10, **kwargs})


def test_arrow_head_stroke_must_fit_figure(context):
    with pytest.raises(LayoutOverflowError):
        Figure(4, 4, Arrow(5, 1, 30, 1)).measure(context, 40)
    colors = [0, .5, 1]
    arrow = Arrow(5, 10, 25, 10, color=colors)
    colors[1] = 1
    assert Figure(4, 4, arrow).measure(context, 40).commands[0].color == (0, .5, 1)


@pytest.mark.parametrize("align, expected_x", [("left", 10.5419921875), ("center", 8.75), ("right", 6.9580078125)])
def test_label_anchors_actual_ink_boundary_and_inherits_body_style(context, align, expected_x):
    result = Figure(3, 2, Label(10, 11, "j", align=align)).measure(context, 30)
    command, = result.commands
    assert command == Text(expected_x, 11, "j", context.style.body)
    label = Label(1, 11, "か\u3099", style=TextStyle(size=9))
    command, = Figure(3, 2, label).measure(context, 30).commands
    assert command.text == "が" and command.style.size == 9


@pytest.mark.parametrize("kwargs", [
    {"x": True}, {"y": float("inf")}, {"text": None}, {"text": "A\nB"},
    {"text": "A\rB"}, {"text": "A\tB"}, {"style": "body"}, {"align": "justify"},
])
def test_label_validates_single_line_and_style_at_construction(kwargs):
    with pytest.raises(ValueError):
        Label(**{"x": 10, "y": 11, "text": "日本", **kwargs})


def test_label_missing_glyph_has_figure_item_diagnostic(context):
    with pytest.raises(FontError, match=r"labels.items\[0\]") as caught:
        Figure(3, 2, Label(1, 11, "\U0010ffff"), block_id="labels").measure(context, 30)
    assert isinstance(caught.value.__cause__, FontError)


@pytest.mark.parametrize("arrow", [
    Arrow(30, 10, .2, 10), Arrow(5, 10, 39.8, 10),
    Arrow(10, 30, 10, .2), Arrow(10, 5, 10, 39.8),
])
def test_arrow_tip_stroke_cannot_cross_any_declared_frame_edge(context, arrow):
    with pytest.raises(LayoutOverflowError):
        Figure(4, 4, arrow).measure(context, 40)
