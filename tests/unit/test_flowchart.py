"""Flowchart parts for a Figure: a box of centred lines (TextBox, rounded as a terminal), a decision diamond
(TextDiamond) and an arrow along a polyline (Connector), with the rounded Rectangle a terminal is drawn with."""

import json
from pathlib import Path

import pymupdf
import pytest

from gridlayoutpdf import Arrow, Connector, Figure, TextBox, TextDiamond, layout_trace
from gridlayoutpdf.bounds import command_bounds
from gridlayoutpdf.errors import LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.geometry import GridSpec
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.profiles import PageProfile
from gridlayoutpdf.renderers import reportlab as backend
from gridlayoutpdf.scene import Polyline, Rectangle, ScenePage, Text
from gridlayoutpdf.styles import ReportStyle, TextStyle


@pytest.fixture(scope="module")
def context():
    fonts = FontRegistry()
    profile = PageProfile("flow", 200, 200, GridSpec(0, 0, 10, 10, 20, 20))
    return LayoutContext(fonts, profile, ReportStyle())


def commands(context, *items, block_id=""):
    return measure_block(Figure(20, 10, *items, block_id=block_id), context, 200).commands  # 200 x 100 pt


def centre_x(context, text):
    bounds = command_bounds(text, context.fonts)
    return bounds.x + bounds.width / 2


def vertical_centre(context, lines, style):
    first = context.fonts.measure(lines[0].text, style)
    last = context.fonts.measure(lines[-1].text, style)
    return (lines[0].y - first.ascent + lines[-1].y + last.descent) / 2


def test_rectangle_corner_radius_defaults_to_square_and_is_validated(context):
    assert Rectangle(0, 0, 10, 4).corner_radius == 0
    rounded = Rectangle(0, 0, 10, 4, corner_radius=2)
    assert rounded.translated(1, 1) == Rectangle(1, 1, 10, 4, corner_radius=2)
    assert command_bounds(rounded, context.fonts) == command_bounds(Rectangle(0, 0, 10, 4), context.fonts)
    for bad in (-1, 2.01, float("nan"), float("inf"), True, "1"):
        with pytest.raises(ValueError, match="corner_radius"):
            Rectangle(0, 0, 10, 4, corner_radius=bad)


def test_rounded_rectangle_renders_with_curves_and_is_traced(context, tmp_path):
    rounded = ScenePage(context.profile, (Rectangle(10, 10, 60, 20, corner_radius=10),))
    output = tmp_path / "rounded.pdf"
    backend.render_pdf((rounded,), output, context.fonts)
    with pymupdf.open(output) as document:
        (drawing,) = document[0].get_drawings()
        assert "c" in [item[0] for item in drawing["items"]]
        assert tuple(drawing["rect"]) == pytest.approx((10, 10, 70, 30), abs=0.01)
    trace = layout_trace((rounded,), context.fonts)
    assert trace["pages"][0]["commands"][0]["corner_radius"] == 10
    square = layout_trace((ScenePage(context.profile, (Rectangle(10, 10, 60, 20),)),), context.fonts)
    assert "corner_radius" not in json.dumps(square)


def test_text_box_centres_its_lines_in_the_box(context):
    rectangle, *lines = commands(context, TextBox(10, 20, 120, 40, ("永久作用による", "検討")))
    assert rectangle == Rectangle(10, 20, 120, 40, .6)
    assert all(isinstance(line, Text) for line in lines)
    assert [line.text for line in lines] == ["永久作用による", "検討"]
    style = context.style.body
    assert lines[1].y - lines[0].y == pytest.approx(1.4 * style.size)
    assert [centre_x(context, line) for line in lines] == pytest.approx([70, 70])
    assert vertical_centre(context, lines, style) == pytest.approx(40)


def test_text_box_takes_its_style_leading_and_line_width(context):
    style = TextStyle(size=8)
    rectangle, *lines = commands(context, TextBox(2, 2, 100, 40, ("a", "b"), style=style, leading=12,
                                                  stroke_width=1, color=(0.5, 0, 0)))
    assert rectangle == Rectangle(2, 2, 100, 40, 1, (0.5, 0, 0))
    assert {line.style for line in lines} == {style}
    assert lines[1].y - lines[0].y == pytest.approx(12)
    assert vertical_centre(context, lines, style) == pytest.approx(22)


def test_rounded_text_box_is_a_terminal_with_half_round_ends(context):
    rectangle, text = commands(context, TextBox(10, 10, 80, 20, ("START",), rounded=True))
    assert rectangle == Rectangle(10, 10, 80, 20, .6, corner_radius=10)
    assert centre_x(context, text) == pytest.approx(50)


def test_text_box_rejects_lines_that_do_not_fit(context):
    with pytest.raises(LayoutOverflowError) as caught:
        commands(context, TextBox(2, 2, 40, 20, ("全断面を有効として計算した",)), block_id="flow")
    assert caught.value.block_id == "flow"
    assert caught.value.available == pytest.approx(40 - 2 * 3)
    with pytest.raises(LayoutOverflowError):
        commands(context, TextBox(2, 2, 180, 12, ("a", "b")))


@pytest.mark.parametrize("arguments, keywords", [
    ((0, 0, 10, 10, ()), {}),
    ((0, 0, 10, 10, ("a\nb",)), {}),
    ((0, 0, 10, 10, ("a", 1)), {}),
    ((0, 0, 10, 10, "ab"), {}),
    ((0, 0, 0, 10, ("a",)), {}),
    ((0, 0, 10, -1, ("a",)), {}),
    ((0, float("nan"), 10, 10, ("a",)), {}),
    ((0, 0, 10, 10, ("a",)), {"padding": -1}),
    ((0, 0, 10, 10, ("a",)), {"leading": 0}),
    ((0, 0, 10, 10, ("a",)), {"style": "body"}),
    ((0, 0, 10, 10, ("a",)), {"stroke_width": 0}),
])
def test_text_box_and_diamond_validate_their_arguments(arguments, keywords):
    for kind in (TextBox, TextDiamond):
        with pytest.raises(ValueError):
            kind(*arguments, **keywords)


def test_text_box_rounded_must_be_a_boolean():
    with pytest.raises(ValueError, match="rounded"):
        TextBox(0, 0, 10, 10, ("a",), rounded=1)


def test_text_diamond_draws_a_closed_rhombus_with_centred_text(context):
    outline, text = commands(context, TextDiamond(20, 10, 120, 40, ("σb ≦ σbl",)))
    assert outline == Polyline(((80, 10), (140, 30), (80, 50), (20, 30)), .6, closed=True)
    assert text.text == "σb ≦ σbl"
    assert centre_x(context, text) == pytest.approx(80)
    assert vertical_centre(context, (text,), context.style.body) == pytest.approx(30)


def test_text_diamond_rejects_text_outside_the_rhombus(context):
    # A box of the same size holds the line; the rhombus, narrower at the height of the line, does not.
    line = ("σb ≦ σbl",)
    assert commands(context, TextBox(2, 2, 70, 30, line))
    with pytest.raises(LayoutOverflowError) as caught:
        commands(context, TextDiamond(2, 2, 70, 30, line), block_id="decision")
    assert caught.value.block_id == "decision"


def test_connector_draws_its_path_with_an_arrow_head_on_the_last_segment(context):
    path, head = commands(context, Connector(((10, 10), (60, 10), (60, 40))))
    assert path == Polyline(((10, 10), (60, 10), (60, 40)), .6)
    assert head == Arrow(60, 10, 60, 40)._commands()[1]
    straight = commands(context, Connector(((10, 10), (10, 40)), head_length=5, head_width=3, width=1))
    arrow = Arrow(10, 10, 10, 40, head_length=5, head_width=3, width=1)._commands()
    assert straight == (Polyline(((10, 10), (10, 40)), 1), arrow[1])


@pytest.mark.parametrize("points", [((0, 0),), ((0, 0), (0, 0)), ((0, 0), (10, 0), (10, 3)),
                                    ((0, 0), (float("inf"), 0)), "ab", ((0, 0), (1,))])
def test_connector_rejects_paths_without_room_for_its_head(points):
    with pytest.raises(ValueError):
        Connector(points)


def test_flowchart_parts_must_stay_inside_the_figure(context):
    with pytest.raises(LayoutOverflowError):
        commands(context, TextBox(150, 0, 60, 20, ("a",)))
