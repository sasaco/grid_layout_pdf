"""The shared validators and the single grid rounding every boundary uses."""

import math

import pytest

from gridlayoutpdf.geometry import GridSpec
from gridlayoutpdf.validation import TOLERANCE, _integer, whole_units_ceil, whole_units_in


PITCHES = (15.48, 16.08, 12.8, 0.1, 1 / 3)


def reference_ceil(length, pitch):
    """The smallest whole count whose boundary reaches length, in float steps."""
    count = 0
    while count * pitch < length:
        count += 1
    return count


def reference_in(start, end, pitch):
    """The complete units inside [start, end], compared as drawing does."""
    count = 0
    while start + (count + 1) * pitch <= end:
        count += 1
    return count


def test_one_absolute_roundoff_allowance_is_shared():
    assert TOLERANCE == 1e-7


@pytest.mark.parametrize("value", [True, False, 1.0, "2", None])
def test_integer_without_a_minimum_still_rejects_non_integers(value):
    with pytest.raises(ValueError, match="turns must be an integer$"):
        _integer(value, "turns", None)


@pytest.mark.parametrize("value", [-7, 0, 9])
def test_integer_without_a_minimum_accepts_any_integer(value):
    assert _integer(value, "turns", None) is None


def test_integer_reports_the_callers_own_wording():
    with pytest.raises(ValueError, match=r"^rows must be a positive integer$"):
        _integer(0, "rows", 1, message="rows must be a positive integer")


@pytest.mark.parametrize("value", [True, 2.0, -1])
def test_integer_rejects_booleans_floats_and_values_below_the_minimum(value):
    with pytest.raises(ValueError, match=r"col_spans must be an integer >= 1"):
        _integer(value, "col_spans", 1)


@pytest.mark.parametrize("length, pitch, expected", [
    # math.ceil alone answers 54 here, and 18 in the second case.
    (678.4000000000001, 12.8, 53),
    (230.40000000000003, 12.8, 19),
    (0.0, 15.48, 0),
])
def test_whole_units_ceil_corrects_both_float_boundary_directions(length, pitch, expected):
    assert math.ceil(length / pitch) != expected or length == 0
    assert whole_units_ceil(length, pitch) == expected
    assert whole_units_ceil(length, pitch) == reference_ceil(length, pitch)


@pytest.mark.parametrize("pitch", PITCHES)
def test_whole_units_ceil_reaches_every_sampled_length(pitch):
    for count in range(1, 40):
        exact = count * pitch
        for length in (exact, math.nextafter(exact, 0), math.nextafter(exact, 1e9)):
            assert whole_units_ceil(length, pitch) == reference_ceil(length, pitch)


@pytest.mark.parametrize("pitch", PITCHES)
def test_grid_rows_use_the_shared_rounding(pitch):
    grid = GridSpec(0, 0, 16.08, pitch, 30, 47)
    for count in range(0, 40):
        exact = count * pitch
        for height in (exact, math.nextafter(exact, 1e9)):
            assert grid.rows_for(height) == whole_units_ceil(height, pitch)


@pytest.mark.parametrize("start, end, pitch, expected", [
    # math.floor of the interval answers 30 here, and 11 in the second case.
    (54.598, 534.478, 15.48, 31),
    (54.598, 195.398, 12.8, 10),
])
def test_whole_units_in_corrects_both_float_boundary_directions(start, end, pitch, expected):
    assert math.floor((end - start) / pitch) != expected
    assert whole_units_in(start, end, pitch) == expected
    assert whole_units_in(start, end, pitch) == reference_in(start, end, pitch)


@pytest.mark.parametrize("start", [0.0, 54.598, 200.25])
@pytest.mark.parametrize("pitch", PITCHES)
def test_whole_units_in_counts_only_complete_units(start, pitch):
    for count in range(1, 30):
        end = start + count * pitch
        for boundary in (end, math.nextafter(end, 0), math.nextafter(end, 1e9)):
            assert whole_units_in(start, boundary, pitch) == reference_in(start, boundary, pitch)
