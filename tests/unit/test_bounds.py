import importlib
from pathlib import Path

import pytest

from gridlayoutpdf.errors import FontError
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.geometry import Point, Rect
from gridlayoutpdf.scene import Line, Polyline, Rectangle, Text
from gridlayoutpdf.styles import TextStyle


def command_bounds(command, fonts):
    try:
        module = importlib.import_module("gridlayoutpdf.bounds")
    except ModuleNotFoundError:
        pytest.fail("Shared command bounds are not implemented")
    return module.command_bounds(command, fonts)


@pytest.fixture
def fonts():
    result = FontRegistry()
    result.register("body", Path(__file__).parents[1] / "fixtures/fonts/ipaexm.ttf")
    return result


@pytest.mark.parametrize("command,expected", [
    (Line(10, 20, 30, 40, width=2), Rect(9, 19, 22, 22)),
    (Line(30, 40, 10, 20, width=2), Rect(9, 19, 22, 22)),
    (Polyline((Point(10, 5), Point(-2, 20), Point(3, 8)), width=1), Rect(-2.5, 4.5, 13, 16)),
    (Rectangle(10, 20, 30, 40, stroke_width=0.5), Rect(9.75, 19.75, 30.5, 40.5)),
])
def test_stroke_bounds_are_hand_computed_and_direction_independent(command, expected, fonts):
    assert command_bounds(command, fonts) == expected


def test_text_bounds_keep_real_ink_overhang_and_translate_baseline(fonts):
    # Pinned font glyf header/advance measurements, independent of this helper.
    result = command_bounds(Text(20, 30, "jÅ", TextStyle(tracking=0.25)), fonts)
    assert result == Rect(19.4580078125, 20.849609375, 11.1435546875, 11.1376953125)
    assert command_bounds(Text(20, 30, "jA\u030a", TextStyle(tracking=0.25)), fonts) == result


def test_missing_fonts_glyphs_and_unsupported_commands_fail_explicitly(fonts):
    with pytest.raises(FontError, match="U\\+"):
        command_bounds(Text(20, 30, "\U0010ffff", TextStyle()), fonts)
    with pytest.raises(ValueError, match="Unsupported.*object"):
        command_bounds(object(), fonts)
