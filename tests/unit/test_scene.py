from dataclasses import FrozenInstanceError

import pytest

from gridlayoutpdf import scene
from gridlayoutpdf.geometry import Point
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.styles import TextStyle


def test_text_translation_keeps_baseline_style_and_source_immutable():
    style = TextStyle()
    command = scene.Text(1, -3, "日本語", style)
    moved = command.translated(10, 20)
    assert (moved.x, moved.y, moved.text, moved.style) == (11, 17, "日本語", style)
    assert (command.x, command.y) == (1, -3)
    with pytest.raises(FrozenInstanceError):
        command.x = 2


def test_stroke_commands_translate_without_changing_geometry_or_style():
    line = scene.Line(1, -2, 5, 8, width=0.75, color=(0.1, 0.2, 0.3))
    assert line.translated(3, 4) == scene.Line(4, 2, 8, 12, 0.75, (0.1, 0.2, 0.3))
    points = [[0, 0], [3, -2], [6, 0]]
    polyline = scene.Polyline(points, width=0.75, color=(0.1, 0.2, 0.3), closed=True)
    points[0][0] = 99
    assert polyline.points == (Point(0, 0), Point(3, -2), Point(6, 0))
    moved = polyline.translated(2, 5)
    assert moved.points == (Point(2, 5), Point(5, 3), Point(8, 5))
    assert (moved.width, moved.color, moved.closed) == (0.75, (0.1, 0.2, 0.3), True)
    rectangle = scene.Rectangle(1, -2, 30, 40, stroke_width=0.75, color=(0.1, 0.2, 0.3))
    assert rectangle.translated(3, 4) == scene.Rectangle(4, 2, 30, 40, 0.75, (0.1, 0.2, 0.3))
    for command in (line, polyline, rectangle):
        with pytest.raises(FrozenInstanceError):
            command.color = (1, 1, 1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "1", None])
def test_commands_reject_nonfinite_or_nonnumeric_coordinates(value):
    constructors = [
        lambda: scene.Text(value, 0, "text", TextStyle()),
        lambda: scene.Line(0, value, 1, 1),
        lambda: scene.Polyline([(0, 0), (value, 1)]),
        lambda: scene.Rectangle(0, 0, value, 1),
    ]
    for construct in constructors:
        with pytest.raises(ValueError):
            construct()


@pytest.mark.parametrize("width", [0, -1, True, float("nan"), float("inf")])
def test_stroke_width_is_finite_and_positive(width):
    for construct in (
        lambda: scene.Line(0, 0, 1, 1, width=width),
        lambda: scene.Polyline([(0, 0), (1, 1)], width=width),
        lambda: scene.Rectangle(0, 0, 1, 1, stroke_width=width),
    ):
        with pytest.raises(ValueError, match="width"):
            construct()


@pytest.mark.parametrize("color", [(0, 0), (0, 0, 0, 0), (-1, 0, 0), (0, 1.1, 0), (True, 0, 0), (float("nan"), 0, 0), None])
def test_colors_must_be_three_finite_components_between_zero_and_one(color):
    for construct in (
        lambda: scene.Line(0, 0, 1, 1, color=color),
        lambda: scene.Polyline([(0, 0), (1, 1)], color=color),
        lambda: scene.Rectangle(0, 0, 1, 1, color=color),
    ):
        with pytest.raises(ValueError, match="color"):
            construct()


def test_mutable_color_inputs_are_copied():
    color = [0.1, 0.2, 0.3]
    commands = [scene.Line(0, 0, 1, 1, color=color),
                scene.Polyline([(0, 0), (1, 1)], color=color),
                scene.Rectangle(0, 0, 1, 1, color=color)]
    color[0] = 1
    assert all(command.color == (0.1, 0.2, 0.3) for command in commands)


def test_text_requires_text_and_a_valid_style():
    with pytest.raises(ValueError, match="text"):
        scene.Text(0, 0, None, TextStyle())
    with pytest.raises(ValueError, match="style"):
        scene.Text(0, 0, "text", {})


@pytest.mark.parametrize("points,closed", [([], False), ([(0, 0)], False), ([(0, 0), (1, 1)], True), ([(0, 0), (1, 1)], 1), ([1, 2], False)])
def test_polylines_reject_insufficient_points_or_invalid_closed_flag(points, closed):
    with pytest.raises(ValueError):
        scene.Polyline(points, closed=closed)


def test_rectangle_rejects_negative_dimensions_and_derived_overflow():
    with pytest.raises(ValueError, match="width"):
        scene.Rectangle(0, 0, -1, 1)
    with pytest.raises(ValueError, match="height"):
        scene.Rectangle(0, 0, 1, -1)
    with pytest.raises(ValueError, match="finite"):
        scene.Rectangle(1e308, 0, 1e308, 1)


@pytest.mark.parametrize("offset", [True, float("nan"), float("inf"), "1"])
def test_translation_validates_offsets_before_coordinate_arithmetic(offset):
    commands = [scene.Text(0, 0, "x", TextStyle()), scene.Line(0, 0, 1, 1),
                scene.Polyline([(0, 0), (1, 1)]), scene.Rectangle(0, 0, 1, 1)]
    for command in commands:
        with pytest.raises(ValueError):
            command.translated(offset, 0)


def test_scene_page_copies_commands_and_recursively_freezes_metadata():
    commands = [scene.Text(50, 60, "日本語", TextStyle())]
    metadata = {"anchors": [{"x": 50}], "flags": [True, None], "caption": "図"}
    page = scene.ScenePage(A4_PORTRAIT_REFERENCE, commands, metadata)
    commands.clear()
    metadata["anchors"][0]["x"] = 999
    assert len(page.commands) == 1
    assert page.metadata["anchors"][0]["x"] == 50
    assert page.metadata["flags"] == (True, None)
    with pytest.raises(TypeError):
        page.metadata["new"] = 0
    with pytest.raises(TypeError):
        page.metadata["anchors"][0]["x"] = 2
    with pytest.raises(FrozenInstanceError):
        page.commands = ()
    assert scene.ScenePage(A4_PORTRAIT_REFERENCE).commands == ()
    assert scene.ScenePage(A4_PORTRAIT_REFERENCE).metadata == {}


@pytest.mark.parametrize("metadata", [{"x": float("nan")}, {"x": float("inf")}, {1: "x"}, {"x": object()}, {"x": {1, 2}}, []])
def test_scene_page_rejects_metadata_that_cannot_be_serialized_consistently(metadata):
    with pytest.raises(ValueError, match="metadata"):
        scene.ScenePage(A4_PORTRAIT_REFERENCE, metadata=metadata)


def test_scene_page_rejects_non_scene_commands_and_invalid_profile():
    with pytest.raises(ValueError, match="commands"):
        scene.ScenePage(A4_PORTRAIT_REFERENCE, commands=[object()])
    with pytest.raises(ValueError, match="profile"):
        scene.ScenePage(None)


def test_scene_page_rejects_cyclic_metadata():
    metadata = {"children": []}
    metadata["children"].append(metadata)
    with pytest.raises(ValueError, match="metadata"):
        scene.ScenePage(A4_PORTRAIT_REFERENCE, metadata=metadata)


def test_text_quarter_turns_default_preserves_four_arguments_and_translation():
    horizontal = scene.Text(1, 2, "日本語", TextStyle())
    assert getattr(horizontal, "quarter_turns", None) == 0
    for turns in range(4):
        command = scene.Text(1, 2, "日本語", TextStyle(), quarter_turns=turns)
        assert command.translated(3, 4) == scene.Text(4, 6, "日本語", TextStyle(), quarter_turns=turns)
        assert command.quarter_turns == turns
        with pytest.raises(FrozenInstanceError):
            command.quarter_turns = 0


@pytest.mark.parametrize("turns", [True, False, -1, 4, 1.0, "1", None])
def test_text_quarter_turns_rejects_noninteger_and_out_of_range(turns):
    assert "quarter_turns" in scene.Text.__dataclass_fields__
    with pytest.raises(ValueError, match="quarter_turns"):
        scene.Text(1, 2, "x", TextStyle(), quarter_turns=turns)
