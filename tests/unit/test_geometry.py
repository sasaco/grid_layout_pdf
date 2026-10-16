"""Independent geometry and diagnostic contract checks."""

from dataclasses import FrozenInstanceError
import math

import pytest

from gridlayoutpdf.errors import FontError, LayoutError, LayoutOverflowError
from gridlayoutpdf.geometry import GridSpec, Point, Rect


def test_overflow_error_preserves_diagnostic_context_and_defaults():
    error = LayoutOverflowError(
        "Equation does not fit", block_id="eq-3", needed=72.5, available=60.0
    )
    assert isinstance(error, LayoutError)
    assert str(error) == "Equation does not fit"
    assert error.message == "Equation does not fit"
    assert error.block_id == "eq-3"
    assert error.needed == 72.5
    assert error.available == 60.0

    default = LayoutOverflowError("Too tall")
    assert default.block_id == ""
    assert default.needed is None
    assert default.available is None
    assert isinstance(FontError("Missing glyph"), LayoutError)


def test_rectangle_bounds_and_inclusive_containment_are_immutable():
    point = Point(-2, -5)
    rect = Rect(-2, -5, 12, 20)
    assert rect.right == 10
    assert rect.bottom == 15
    assert rect.contains(point)
    assert rect.contains(Point(10, 15))
    assert rect.contains(Rect(0, 0, 10, 15))
    assert rect.contains(Rect(10, 15, 0, 0))
    assert not rect.contains(Point(10.000001, 15))
    assert not rect.contains(Point(-2, -5.000001))
    assert not rect.contains(Rect(-2, -5, 12.000001, 20))
    assert not rect.contains(Rect(-2, -5.000001, 12, 20))
    with pytest.raises(FrozenInstanceError):
        point.x = 1
    with pytest.raises(FrozenInstanceError):
        rect.width = 1


@pytest.mark.parametrize("invalid", [True, False, float("inf"), -float("inf"), float("nan"), "1", None, 10**400])
@pytest.mark.parametrize("field", ["x", "y"])
def test_point_rejects_invalid_coordinates(field, invalid):
    values = {"x": 0, "y": 0}
    values[field] = invalid
    with pytest.raises(ValueError, match=field):
        Point(**values)


@pytest.mark.parametrize("invalid", [True, float("inf"), float("nan"), "2", None])
@pytest.mark.parametrize("field", ["x", "y", "width", "height"])
def test_rectangle_rejects_invalid_numbers(field, invalid):
    values = {"x": 0, "y": 0, "width": 10, "height": 20}
    values[field] = invalid
    with pytest.raises(ValueError, match=field):
        Rect(**values)


@pytest.mark.parametrize("field", ["width", "height"])
def test_rectangle_rejects_negative_dimensions(field):
    values = {"x": 0, "y": 0, "width": 10, "height": 20}
    values[field] = -0.001
    with pytest.raises(ValueError, match=field):
        Rect(**values)


def test_rectangle_rejects_nonfinite_derived_extent_and_invalid_contains_type():
    with pytest.raises(ValueError, match="right"):
        Rect(1e308, 0, 1e308, 1)
    with pytest.raises(ValueError, match="bottom"):
        Rect(0, 1e308, 1, 1e308)
    with pytest.raises(ValueError, match="Point or Rect"):
        Rect(0, 0, 1, 1).contains((0, 0))


def test_grid_coordinates_match_independently_measured_boundaries():
    grid = GridSpec(50.88, 54.598, 16.08, 15.48, 30, 47)
    for column, expected in [(0, 50.88), (1, 66.96), (15, 292.08), (30, 533.28)]:
        assert grid.x(column) == pytest.approx(expected, abs=1e-10)
    for row, expected in [(0, 54.598), (1, 70.078), (23, 410.638), (47, 782.158)]:
        assert grid.y(row) == pytest.approx(expected, abs=1e-10)
    with pytest.raises(FrozenInstanceError):
        grid.pitch_x = 10


@pytest.mark.parametrize(
    ("height", "expected"),
    [(0, 0), (0.01, 1), (15.48, 1), (30.96, 2), (30.96 + 1e-9, 3), (727.56, 47), (1000, 65)],
)
def test_rows_for_rounds_height_up_without_limiting_to_grid_rows(height, expected):
    grid = GridSpec(50.88, 54.598, 16.08, 15.48, 30, 47)
    assert grid.rows_for(height) == expected


def test_rows_for_does_not_add_a_row_for_float_boundary_roundoff():
    grid = GridSpec(0, 0, 1, 0.1, 1, 10)
    boundary = 3 * 0.1
    assert grid.rows_for(boundary) == 3
    assert grid.rows_for(math.nextafter(boundary, math.inf)) == 4


@pytest.mark.parametrize("field", ["origin_x", "origin_y", "pitch_x", "pitch_y"])
@pytest.mark.parametrize("invalid", [True, float("inf"), float("nan"), "1", None])
def test_grid_rejects_invalid_pt_values(field, invalid):
    values = dict(origin_x=0, origin_y=0, pitch_x=10, pitch_y=12, columns=3, rows=4)
    values[field] = invalid
    with pytest.raises(ValueError, match=field):
        GridSpec(**values)


@pytest.mark.parametrize("field", ["pitch_x", "pitch_y"])
@pytest.mark.parametrize("invalid", [0, -0.1])
def test_grid_requires_positive_pitch(field, invalid):
    values = dict(origin_x=0, origin_y=0, pitch_x=10, pitch_y=12, columns=3, rows=4)
    values[field] = invalid
    with pytest.raises(ValueError, match=field):
        GridSpec(**values)


@pytest.mark.parametrize("field", ["columns", "rows"])
@pytest.mark.parametrize("invalid", [0, -1, True, 1.5, 2.0, float("nan"), "3", None])
def test_grid_requires_positive_integer_counts(field, invalid):
    values = dict(origin_x=0, origin_y=0, pitch_x=10, pitch_y=12, columns=3, rows=4)
    values[field] = invalid
    with pytest.raises(ValueError, match=field):
        GridSpec(**values)


@pytest.mark.parametrize("method,invalid", [("x", -1), ("x", 31), ("y", -1), ("y", 48), ("x", True), ("y", 1.0), ("x", "2"), ("y", None)])
def test_grid_rejects_invalid_boundary_indices(method, invalid):
    grid = GridSpec(50.88, 54.598, 16.08, 15.48, 30, 47)
    with pytest.raises(ValueError, match="col|row"):
        getattr(grid, method)(invalid)


@pytest.mark.parametrize("invalid", [-1, True, float("inf"), float("nan"), "2", None])
def test_rows_for_rejects_invalid_height(invalid):
    with pytest.raises(ValueError, match="height"):
        GridSpec(0, 0, 10, 12, 3, 4).rows_for(invalid)


def test_grid_rejects_nonfinite_derived_boundaries():
    with pytest.raises(ValueError):
        GridSpec(1e308, 0, 1e308, 1, 2, 1)
    with pytest.raises(ValueError):
        GridSpec(0, 1e308, 1, 1e308, 1, 2)
    with pytest.raises(ValueError):
        GridSpec(0, 0, 1, 1, 10**400, 1)
