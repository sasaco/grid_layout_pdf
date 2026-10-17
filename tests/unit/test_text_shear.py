"""Baseline-preserving glyph shear and its composition with rigid rotation."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from gridlayoutpdf import (
    FontRegistry, GridSpec, LayoutContext, LayoutOverflowError, LayoutPart,
    MeasuredBlock, PageProfile, QuarterTurn, ReportStyle, ScenePage, Text,
    TextStyle, layout_trace, measure_block,
)
from gridlayoutpdf.bounds import command_bounds


@pytest.fixture
def fonts():
    result = FontRegistry()
    result.register("body", Path(__file__).parents[1] / "fixtures/fonts/ipaexm.ttf")
    return result


def sheared(*args, **kwargs):
    assert "shear_x" in Text.__dataclass_fields__, "Text must support native glyph shear"
    return Text(*args, **kwargs)


def test_default_zero_and_translation_preserve_an_immutable_shear():
    plain = sheared(10, 20, "D", TextStyle(), 1)
    assert plain.shear_x == 0
    command = replace(plain, shear_x=.342)
    moved = command.translated(3, -4)
    assert (moved.x, moved.y, moved.quarter_turns, moved.shear_x) == (13, 16, 1, .342)
    assert moved.style is command.style
    with pytest.raises(FrozenInstanceError):
        moved.shear_x = 0


@pytest.mark.parametrize("value", [True, False, "0.342", None, [], float("inf"), float("-inf"), float("nan"), 10**1000])
def test_shear_rejects_nonfinite_or_nonnumeric_values(value):
    assert "shear_x" in Text.__dataclass_fields__
    with pytest.raises(ValueError, match="shear_x.*finite number"):
        Text(0, 0, "D", TextStyle(), shear_x=value)


@pytest.mark.parametrize("value", [-2, 0, .342, 2])
def test_shear_accepts_finite_signed_coefficients(value):
    assert sheared(0, 0, "D", TextStyle(), shear_x=value).shear_x == value


@pytest.mark.parametrize("turns", range(4))
@pytest.mark.parametrize("shear", [-.342, .342])
def test_bounds_shear_all_real_ink_corners_before_rotating(fonts, turns, shear):
    # Pinned IPAex glyph/advance envelope for jÅ, including j's left overhang.
    corners = [(x - shear*y, y) for x in (-.5419921875, 10.6015625)
               for y in (-9.150390625, 1.9873046875)]
    rotations = (lambda x,y:(x,y), lambda x,y:(y,-x),
                 lambda x,y:(-x,-y), lambda x,y:(-y,x))
    points = [rotations[turns](*point) for point in corners]
    expected = (20 + min(p[0] for p in points), 30 + min(p[1] for p in points),
                20 + max(p[0] for p in points), 30 + max(p[1] for p in points))
    result = command_bounds(sheared(20, 30, "jÅ", TextStyle(tracking=.25),
                                    quarter_turns=turns, shear_x=shear), fonts)
    assert (result.x, result.y, result.right, result.bottom) == pytest.approx(expected)


def test_positive_shear_moves_above_baseline_right_and_keeps_advance(fonts):
    plain = sheared(20, 30, "D", TextStyle(tracking=.3))
    slanted = replace(plain, shear_x=.342)
    initial, transformed = command_bounds(plain, fonts), command_bounds(slanted, fonts)
    assert transformed.right > initial.right
    assert (transformed.y, transformed.height) == (initial.y, initial.height)
    assert fonts.measure(plain.text, plain.style).width == fonts.measure(slanted.text, slanted.style).width


@pytest.mark.parametrize("turns", range(4))
def test_trace_emits_only_nonzero_shear_and_uses_transformed_bounds(fonts, turns):
    profile = PageProfile("trace", 200, 200, GridSpec(10, 10, 10, 10, 15, 15))
    plain = sheared(50, 50, "D", TextStyle(), quarter_turns=turns)
    command = replace(plain, shear_x=.342)
    traces = layout_trace((ScenePage(profile, (plain, command)),), fonts)["pages"][0]["commands"]
    assert "shear_x" not in traces[0]
    assert traces[1]["shear_x"] == .342
    assert traces[1].get("direction", [1, 0]) == traces[0].get("direction", [1, 0])
    bounds = command_bounds(command, fonts)
    assert traces[1]["bounds"] == {"x": bounds.x, "y": bounds.y, "width": bounds.width, "height": bounds.height}


class FixedBlock:
    def __init__(self, command, width=60):
        self.command, self.width = command, width

    def measure(self, context, available_width):
        return MeasuredBlock(self.width, 10, (LayoutPart(5, (self.command,)),))


@pytest.mark.parametrize("turns", [-1, 1])
@pytest.mark.parametrize("existing", range(4))
def test_quarter_turn_keeps_local_shear_and_composes_only_rotation(fonts, turns, existing):
    context = LayoutContext(fonts, PageProfile("outer", 200, 200, GridSpec(10, 10, 10, 10, 15, 15)), ReportStyle())
    command = sheared(25, 25, "jÅ", TextStyle(tracking=.25), quarter_turns=existing, shear_x=.342)
    block = QuarterTurn(FixedBlock(command), turns=turns, local_grid=GridSpec(0, 0, 10, 10, 6, 5))
    rotated = measure_block(block, context, 100).commands[0]
    assert rotated.shear_x == command.shear_x
    assert rotated.quarter_turns == (existing + turns) % 4
    assert (rotated.x, rotated.y) == ((25, 35) if turns == 1 else (25, 25))
    assert rotated.style is command.style


@pytest.mark.parametrize("turns", [-1, 1])
@pytest.mark.parametrize("shear", [-.5, .5])
def test_measurement_rejects_sheared_ink_outside_child_even_when_advance_fits(fonts, turns, shear):
    context = LayoutContext(fonts, PageProfile("outer", 200, 200, GridSpec(10, 10, 10, 10, 15, 15)), ReportStyle())
    style = TextStyle()
    bounds = fonts.measure("jÅ", style).bounds
    x = 20-bounds.right-.1 if shear > 0 else -bounds.x+.1
    plain = sheared(x, 20, "jÅ", style)
    local = GridSpec(0, 0, 10, 10, 2, 5)
    measure_block(QuarterTurn(FixedBlock(plain, 20), turns=turns, local_grid=local), context, 100)
    bad = QuarterTurn(FixedBlock(replace(plain, shear_x=shear), 20), turns=turns, local_grid=local)
    with pytest.raises(LayoutOverflowError, match="bounds"):
        measure_block(bad, context, 100)
