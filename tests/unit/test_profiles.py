"""Measured and derived paper profiles checked against independent values."""

from dataclasses import FrozenInstanceError

import pytest

from gridlayoutpdf.geometry import GridSpec, Rect
from gridlayoutpdf.profiles import (
    A3_LANDSCAPE_REFERENCE,
    A4_PORTRAIT_REFERENCE,
    PageProfile,
    derived_profile,
)


@pytest.mark.parametrize(
    ("profile", "name", "width", "columns", "right", "body_width"),
    [
        (A4_PORTRAIT_REFERENCE, "A4_PORTRAIT_REFERENCE", 595, 30, 533.28, 482.4),
        (A3_LANDSCAPE_REFERENCE, "A3_LANDSCAPE_REFERENCE", 1191, 67, 1128.24, 1077.36),
    ],
)
def test_reference_profiles_preserve_measured_paper_and_grid(profile, name, width, columns, right, body_width):
    assert isinstance(profile, PageProfile)
    assert profile.name == name
    assert (profile.width, profile.height) == (width, 842)
    assert (profile.grid.origin_x, profile.grid.origin_y) == (50.88, 54.598)
    assert (profile.grid.pitch_x, profile.grid.pitch_y) == (16.08, 15.48)
    assert (profile.grid.columns, profile.grid.rows) == (columns, 47)
    assert profile.grid.x(columns) == pytest.approx(right, abs=1e-10)
    assert profile.grid.y(47) == pytest.approx(782.158, abs=1e-10)
    assert profile.body_start_row == 0
    assert profile.body_end_row == 47
    body = profile.body_rect
    assert (body.x, body.y) == (50.88, 54.598)
    assert body.width == pytest.approx(body_width, abs=1e-10)
    assert body.height == pytest.approx(727.56, abs=1e-10)
    assert Rect(0, 0, width, 842).contains(body)
    with pytest.raises(FrozenInstanceError):
        profile.width = 1


def test_body_rows_reserve_space_without_changing_grid():
    grid = GridSpec(50.88, 54.598, 16.08, 15.48, 30, 47)
    profile = PageProfile("reserved", 595, 842, grid, body_start_row=2, body_end_row=45)
    assert profile.grid is grid
    assert profile.body_rect.x == 50.88
    assert profile.body_rect.y == pytest.approx(85.558, abs=1e-10)
    assert profile.body_rect.width == pytest.approx(482.4, abs=1e-10)
    assert profile.body_rect.height == pytest.approx(665.64, abs=1e-10)


@pytest.mark.parametrize("field", ["width", "height"])
@pytest.mark.parametrize("invalid", [0, -1, True, float("inf"), float("nan"), "100", None])
def test_profile_rejects_invalid_paper_dimensions(field, invalid):
    values = dict(name="custom", width=100, height=100, grid=GridSpec(10, 10, 10, 10, 3, 4))
    values[field] = invalid
    with pytest.raises(ValueError, match=field):
        PageProfile(**values)


@pytest.mark.parametrize("name", ["", "  ", None, True])
def test_profile_requires_nonempty_name(name):
    with pytest.raises(ValueError, match="name"):
        PageProfile(name, 100, 100, GridSpec(10, 10, 10, 10, 3, 4))


@pytest.mark.parametrize("grid", [None, "grid", Rect(10, 10, 10, 10)])
def test_profile_requires_grid_spec(grid):
    with pytest.raises(ValueError, match="grid"):
        PageProfile("custom", 100, 100, grid)


@pytest.mark.parametrize(
    "grid",
    [
        GridSpec(-0.1, 10, 10, 10, 3, 4),
        GridSpec(10, -0.1, 10, 10, 3, 4),
        GridSpec(70.1, 10, 10, 10, 3, 4),
        GridSpec(10, 60.1, 10, 10, 3, 4),
    ],
)
def test_profile_rejects_any_grid_edge_outside_paper(grid):
    with pytest.raises(ValueError, match="grid"):
        PageProfile("custom", 100, 100, grid)


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, None), (47, None), (True, 40), (1.0, 40), ("0", 40), (None, 40),
     (0, 0), (3, 3), (3, 2), (0, 48), (0, True), (0, 40.0), (0, "40")],
)
def test_profile_rejects_invalid_or_empty_body_row_intervals(start, end):
    with pytest.raises(ValueError, match="body"):
        PageProfile("custom", 595, 842, A4_PORTRAIT_REFERENCE.grid, start, end)


def test_profile_allows_grid_and_body_touching_page_edges():
    profile = PageProfile("edge", 100, 100, GridSpec(0, 0, 10, 10, 10, 10), 9, 10)
    assert profile.body_rect == Rect(0, 90, 100, 10)


@pytest.mark.parametrize(
    ("name", "width", "height", "columns", "rows", "right", "bottom"),
    [
        ("A4_LANDSCAPE_DERIVED", 842, 595, 45, 31, 774.48, 534.478),
        ("A3_PORTRAIT_DERIVED", 842, 1191, 45, 69, 774.48, 1122.718),
        ("A4_DERIVED", 595, 842, 30, 47, 533.28, 782.158),
        ("one-cell", 128.68, 129.92, 1, 1, 66.96, 70.078),
    ],
)
def test_derived_profiles_keep_pitch_and_minimum_margins(name, width, height, columns, rows, right, bottom):
    profile = derived_profile(name, width, height)
    assert profile.name == name
    assert (profile.width, profile.height) == (width, height)
    assert (profile.grid.origin_x, profile.grid.origin_y) == (50.88, 54.598)
    assert (profile.grid.pitch_x, profile.grid.pitch_y) == (16.08, 15.48)
    assert (profile.grid.columns, profile.grid.rows) == (columns, rows)
    assert profile.body_end_row == rows
    assert profile.grid.x(columns) == pytest.approx(right, abs=1e-10)
    assert profile.grid.y(rows) == pytest.approx(bottom, abs=1e-10)
    assert width - right >= 61.72 - 1e-10
    assert height - bottom >= 59.842 - 1e-10
    assert width - (right + 16.08) < 61.72
    assert height - (bottom + 15.48) < 59.842


@pytest.mark.parametrize(("width", "height"), [(100, 842), (595, 100), (128.679999, 129.92), (128.68, 129.919999)])
def test_derived_profiles_reject_paper_without_a_whole_cell(width, height):
    with pytest.raises(ValueError, match="cell"):
        derived_profile("small", width, height)


@pytest.mark.parametrize("field", ["width", "height"])
@pytest.mark.parametrize("invalid", [True, 0, -1, float("inf"), float("nan"), "595", None])
def test_derived_profiles_reject_invalid_paper_dimensions(field, invalid):
    values = dict(name="derived", width=595, height=842)
    values[field] = invalid
    with pytest.raises(ValueError, match=field):
        derived_profile(**values)
