"""Printing at 100 % with the measured printed cell sizes (Step 8, the A3 footer fix).

At 100 % ``print_fit`` also accepts a page whose cells, at their measured
printed sizes (print_pitch.json, scale 100) plus the safety margin, fit the
print area, so the map shrinks the PDF's right and bottom margins only that
far and Excel's margin-aligned header and footer sections stay within a cell
of the PDF's.
"""

import json
import math
from pathlib import Path

import pytest

from gridlayoutpdf.renderers.xlsx._model import Font, Margins, PageSetup, Sheet
from gridlayoutpdf.renderers.xlsx._units import (
    FULL_SCALE_MARGIN,
    FULL_SCALE_PRINTED_PT,
    FULL_SCALE_ROOM_PT,
    PRINT_MEASURED_FONTS,
    full_scale_size_pt,
    print_fit,
)

GOTHIC, MINCHO = Font("游ゴシック", 11), Font("ＭＳ 明朝", 10.5)
PRINT_PITCH = Path(__file__).parents[2] / "scripts" / "xlsx_probe" / "print_pitch.json"
A4_WIDTH, A4_HEIGHT = 595.2756, 841.8898
A3_WIDTH = 1190.5512


def _grid(columns, rows, breaks=(), margins=Margins(50.88, 54.598, 50.6, 47.0, 18, 18), paper="A4",
          orientation="portrait", width=16.08, height=15.48):
    return Sheet("S", (width,) * columns, (height,) * rows, row_breaks=breaks,
                 page=PageSetup(paper=paper, orientation=orientation, margins=margins))


def test_the_printed_sizes_are_the_100_percent_measurements():
    records = json.loads(PRINT_PITCH.read_text(encoding="utf-8"))["records"]
    assert set(FULL_SCALE_PRINTED_PT) == set(PRINT_MEASURED_FONTS)
    for (font, size), (columns, rows) in FULL_SCALE_PRINTED_PT.items():
        measured = {record["pixels"]: record for record in records
                    if (record["font"], record["size"]) == (font, size) and record["scale"] == 100}
        assert sorted(columns) == sorted(rows) == sorted(measured) == list(range(11, 31))
        assert columns == {pixels: record["printed_column_pt"] for pixels, record in measured.items()}
        assert rows == {pixels: record["printed_row_pt"] for pixels, record in measured.items()}


def test_the_map_uses_the_same_printed_sizes():
    from gridlayoutpdf.renderers.xlsx import _map

    assert (_map.PRINTED_COLUMN_PT, _map.PRINTED_ROW_PT) == FULL_SCALE_PRINTED_PT[("游ゴシック", 11.0)]


def test_full_scale_size_adds_the_margin_and_the_room_to_the_printed_cells():
    assert (FULL_SCALE_MARGIN, FULL_SCALE_ROOM_PT) == (1.006, 4.5)
    width, height = full_scale_size_pt(_grid(30, 94, (47,)), GOTHIC)
    assert width == pytest.approx(30 * 16.08 * 1.006 + 4.5)
    assert height == pytest.approx(47 * 15.48 * 1.006 + 4.5)  # the tallest page
    width, height = full_scale_size_pt(_grid(3, 5, (2,), width=9.0, height=22.5), MINCHO)  # 12 px, 30 px
    assert width == pytest.approx(3 * 9.0 * 1.006 + 4.5)
    assert height == pytest.approx(3 * 20.764 * 1.006 + 4.5)


@pytest.mark.parametrize(("width", "height"), [(7.5, 15.48), (23.25, 15.48), (16.08, 7.5), (16.08, 23.25)])
def test_full_scale_size_is_none_outside_the_measured_cell_sizes(width, height):
    # 10 px and 31 px were not measured
    assert full_scale_size_pt(_grid(3, 3, width=width, height=height), GOTHIC) is None


def test_full_scale_size_checks_its_arguments_like_print_fit():
    with pytest.raises(ValueError, match="Sheet"):
        full_scale_size_pt((16.08,), GOTHIC)
    with pytest.raises(ValueError, match="measured"):
        full_scale_size_pt(_grid(3, 3), Font("Calibri", 11))


def _a4(right, bottom=47.0, rows=47):
    return _grid(30, rows, margins=Margins(50.88, 54.598, right, bottom, 18, 18))


def _edge(paper_extent, origin, need):
    return math.floor((paper_extent - origin - need) * 100) / 100


def test_the_a4_reference_grid_prints_at_100_percent_up_to_the_measured_edge():
    need_width, need_height = full_scale_size_pt(_a4(50.6), GOTHIC)
    right = _edge(A4_WIDTH, 50.88, need_width)
    assert right == 54.6
    fit = print_fit(_a4(right), GOTHIC)
    assert fit.scale == 100 and fit.limited_by == "maximum"
    assert fit.column_factor == pytest.approx(need_width / 472.5) and fit.row_factor == 1.0  # rows by the band
    assert print_fit(_a4(right + 0.01), GOTHIC) == (99, "width", 1.04, 1.0)
    bottom = _edge(A4_HEIGHT, 54.598, need_height)
    assert print_fit(_a4(50.6, bottom), GOTHIC).scale == 100
    assert print_fit(_a4(50.6, bottom + 0.01), GOTHIC) == (99, "height", 1.04, 1.0)


def test_the_a3_reference_grid_prints_at_100_percent_up_to_the_measured_edge():
    def a3(right):
        return _grid(67, 47, margins=Margins(50.88, 54.598, right, 47.0, 18, 18), paper="A3",
                     orientation="landscape")

    need_width, _ = full_scale_size_pt(a3(42.0), GOTHIC)
    right = _edge(A3_WIDTH, 50.88, need_width)
    assert right == 51.34
    assert print_fit(a3(right), GOTHIC).scale == 100
    assert print_fit(a3(right + 0.01), GOTHIC) == (99, "width", 1.04, 1.0)


def test_a_page_the_band_factors_already_fit_keeps_them():
    assert print_fit(_a4(50.6), GOTHIC) == (100, "maximum", 1.04, 1.0)


def test_the_measured_sizes_are_used_only_at_100_percent():
    right = _edge(A4_WIDTH, 50.88, full_scale_size_pt(_a4(50.6), GOTHIC)[0])
    assert print_fit(_a4(right), GOTHIC, maximum=99) == (99, "maximum", 1.04, 1.0)


def test_cells_outside_the_measured_sizes_keep_the_band_factors():
    # 31 px columns: 20 x 23.25 = 465 pt; 1.04 needs 483.6 pt
    sheet = _grid(20, 10, margins=Margins(50.88, 54.598, A4_WIDTH - 50.88 - 480.0, 47.0, 18, 18), width=23.25)
    assert print_fit(sheet, GOTHIC).scale == 99


def test_each_extent_may_fit_by_either_rule():
    # 30 columns: the band (1.04) needs 491.4 pt and fits 493.8 pt; 47 rows: the band needs 740.25 pt,
    # the measured sizes 736.43 pt, and the print area is cut at the measured edge
    need_height = full_scale_size_pt(_a4(50.6), GOTHIC)[1]
    bottom = _edge(A4_HEIGHT, 54.598, need_height)
    fit = print_fit(_a4(50.6, bottom), GOTHIC)
    assert fit.scale == 100
    assert fit.column_factor == 1.04 and fit.row_factor == pytest.approx(need_height / (47 * 15.75))
