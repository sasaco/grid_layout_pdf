"""pt, EMU, pixel and Excel column-width unit conversions.

Excel lays out a sheet in whole screen pixels (measured in Excel 16.0 at
96 DPI; other DPI settings are not measured). Column widths are stored in
characters of the Normal style's maximum digit width (MDW, pixels) and become
``Truncate(((256 * width + Truncate(128 / MDW)) / 256) * MDW)`` pixels
(ECMA-376 Part 1, 18.3.1.13). Row heights are stored in pt and Excel shows
them truncated to whole pixels, so the writer stores whole-pixel heights.
Both are rounded half up to the nearest pixel; a length below half a pixel
is an error because Excel would hide the row or column.
"""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from ._model import Font, Sheet

EMU_PER_PT = 12_700
PIXELS_PER_PT = 96 / 72
MAX_ROW_HEIGHT_PT = 409
MAX_COLUMN_WIDTH_CHARS = 255
PIXEL_LIMIT = 1_000_000  # lengths must round to fewer pixels than this
EDGE_TOLERANCE_PT = 1e-6  # float error accepted at a cell boundary or the sheet's edge

# Maximum digit width in pixels at 96 DPI of Normal style fonts, read from
# Excel 16.0 as Range.Width of columns 1, 2, 3, 10 and 20 characters wide
# (2026-10-20, see grid-excel-output-execution.md). Only these are accepted.
_MAX_DIGIT_WIDTH_PX = {
    ("游ゴシック", 11.0): 8,
    ("Yu Gothic", 11.0): 8,
    ("游ゴシック", 10.5): 8,
    ("游ゴシック", 10.0): 7,
    ("游明朝", 11.0): 8,
    ("ＭＳ 明朝", 11.0): 8,
    ("ＭＳ 明朝", 10.5): 7,
    ("ＭＳ ゴシック", 11.0): 8,
    ("ＭＳ ゴシック", 10.5): 7,
    ("ＭＳ Ｐゴシック", 11.0): 8,
    ("Calibri", 11.0): 7,
    ("Arial", 10.0): 7,
}


def max_digit_width_px(font: "Font") -> int:
    """Return the measured MDW of a Normal style ``Font``, or raise ValueError."""
    try:
        return _MAX_DIGIT_WIDTH_PX[(font.name, font.size)]
    except KeyError:
        known = ", ".join(f"{name} {size:g} pt" for name, size in _MAX_DIGIT_WIDTH_PX)
        raise ValueError(
            f"the default font {font.name} {font.size:g} pt has no measured digit width; use one of: {known}"
        ) from None


def _pixels(length_pt: float, what: str) -> int:
    if isinstance(length_pt, bool) or not isinstance(length_pt, (int, float)):
        raise ValueError(f"{what} must be a number in pt")
    try:
        length_pt = float(length_pt)
    except OverflowError:
        raise ValueError(f"{what} is too large") from None
    if not math.isfinite(length_pt):
        raise ValueError(f"{what} must be finite")
    scaled = length_pt * PIXELS_PER_PT
    if scaled < 0.5:  # also negative values, including -inf after the multiplication
        raise ValueError(f"{what} {length_pt} pt is shorter than half a pixel (0.375 pt)")
    if not scaled < PIXEL_LIMIT:  # far beyond Excel's 409 pt rows and 255-character columns
        raise ValueError(f"{what} {length_pt} pt is not below {PIXEL_LIMIT} pixels")
    pixels = math.floor(scaled + 0.5)
    if pixels >= PIXEL_LIMIT:
        raise ValueError(f"{what} {length_pt} pt is not below {PIXEL_LIMIT} pixels")
    return pixels


def column_pixels(width_pt: float) -> int:
    """Return the whole-pixel width Excel shows for a column of ``width_pt``."""
    return _pixels(width_pt, "column width")


def excel_column_width_pt(width_pt: float) -> float:
    """Return the width in pt Excel actually uses for a column of ``width_pt``."""
    return column_pixels(width_pt) / PIXELS_PER_PT


def column_width_chars(width_pt: float, default_font: "Font") -> float:
    """Return the ``<col width>`` value that Excel turns into ``column_pixels``."""
    mdw = max_digit_width_px(default_font)
    return round(256 * column_pixels(width_pt) / mdw) / 256


def excel_row_height_pt(height_pt: float) -> float:
    """Return the whole-pixel height in pt that is stored and used by Excel."""
    return _pixels(height_pt, "row height") / PIXELS_PER_PT


def pt_to_emu(value_pt: float) -> int:
    """Return whole EMU; ``value_pt`` must be a finite number (ValueError otherwise)."""
    if isinstance(value_pt, bool) or not isinstance(value_pt, (int, float)):
        raise ValueError("pt_to_emu needs a finite number")
    try:
        value = float(value_pt)
    except OverflowError:
        raise ValueError("pt_to_emu: the length is too large") from None
    if not math.isfinite(value):
        raise ValueError("pt_to_emu needs a finite number")
    emu = value * EMU_PER_PT
    if not math.isfinite(emu):
        raise ValueError("pt_to_emu: the length is too large")
    return round(emu)


def dash_value(length_pt: float, stroke_width_pt: float) -> int:
    """Return a DrawingML dash or space length: 1/1000 % of the line width as written (whole EMU)."""
    return math.floor(length_pt * EMU_PER_PT / pt_to_emu(stroke_width_pt) * 100_000 + 0.5)


# Excel prints a column wider than it shows it, and a row shorter (or a little
# taller), by factors that depend on the scale, the cell size and the printer
# driver. Measured with scripts/xlsx_probe/measure_print_pitch.py (Excel 16.0's
# PDF export, Normal fonts 游ゴシック 11 and ＭＳ 明朝 10.5):
# - printer "DocuWorks PDF": only 29 scales from 10 % to 400 % and cells of
#   11, 16, 21 and 30 px; the raw data was overwritten, the maxima checked by
#   reviewers are kept in DOCUWORKS_PDF_MAXIMA: columns 1.0284 (90 % and up),
#   1.0430 (55-89 %), 1.0673 (20-54 %); rows 0.9933 from 20 %; at 10 %
#   ＭＳ 明朝 10.5 printed columns 1.16 and rows 1.23 times their size.
# - printer "DocuWorks Printer": every whole percent from 20 % to 100 % and
#   every cell size from 11 to 30 px (print_pitch.json): columns 1.0322 (12 px,
#   93 %), 1.0370 (12 px, 63 %), 1.0475 (12 px, 28 %); rows 0.9931, 0.9955 and
#   1.0158 (12 px, 21 %).
# Each factor is at least 0.6 % above the largest value of both printers.
# Other printer drivers were not measured.
DOCUWORKS_PDF_MAXIMA = {90: (1.0284, 0.9933), 55: (1.0430, 0.9933), 20: (1.0673, 0.9933)}
_PRINT_FACTORS = ((90, 1.04, 1.0), (55, 1.05, 1.01), (20, 1.08, 1.025))  # (lowest scale, column, row)
MIN_FIT_SCALE = 20
MAX_FIT_SCALE = 100
MEASURED_CELL_PIXELS = tuple(range(11, 31))  # cell sizes measured in print_pitch.json
PRINT_MEASURED_FONTS = (("游ゴシック", 11.0), ("ＭＳ 明朝", 10.5))


def page_heights_pt(row_heights_pt: Sequence[float], row_breaks: Sequence[int]) -> tuple[float, ...]:
    """Return Excel's height of each page: rows between manual breaks.

    The rows and breaks are checked as ``Sheet`` checks them.
    """
    from ._model import MAX_ROW_BREAKS, MAX_ROWS, _finite, _tuple  # the model imports this module

    heights = tuple(_finite(height, "row height") for height in _tuple(row_heights_pt, "row_heights_pt"))
    breaks = _tuple(row_breaks, "row_breaks")
    if not 1 <= len(heights) <= MAX_ROWS or any(excel_row_height_pt(height) > MAX_ROW_HEIGHT_PT for height in heights):
        raise ValueError(f"rows must be 1 to {MAX_ROWS} heights of at most {MAX_ROW_HEIGHT_PT} pt")
    bounds = (0, *breaks, len(heights))
    integers = all(isinstance(row, int) and not isinstance(row, bool) for row in breaks)
    if len(breaks) > MAX_ROW_BREAKS or not integers or any(start >= end for start, end in zip(bounds, bounds[1:])):
        raise ValueError("row breaks must be increasing rows inside the rows, at most 1026 of them")
    return tuple(math.fsum(excel_row_height_pt(height) for height in heights[start:end])
                 for start, end in zip(bounds, bounds[1:]))


class PrintFit(NamedTuple):
    """The fitted scale, the extent that limits it and the print factors used for it."""

    scale: int
    limited_by: str  # "width", "height" or "maximum"
    column_factor: float
    row_factor: float


def print_fit(sheet: "Sheet", default_font: "Font", *, maximum: int = 100) -> PrintFit:
    """Return the largest whole percent at most ``maximum`` that prints every page of ``sheet`` on one paper.

    The print area is every column and each page runs between the sheet's
    manual row breaks; the paper and margins are ``sheet.page``. Columns and
    rows are multiplied by the measured print factors of the scale's band
    (columns 1.04, 1.05, 1.08 and rows 1.0, 1.01, 1.025 from 90, 55, 20 %; each at
    least 0.6 % above the largest measured value, ``column_factor`` and
    ``row_factor`` of the result). ``default_font`` must be the
    ``Workbook.default_font`` the sheet is written with; only the fonts whose
    printing was measured are accepted. With the printer "DocuWorks
    Printer" every whole percent from 20 % to 100 % and every cell size from
    11 to 30 px was measured; with "DocuWorks PDF" only 29 scales and 11, 16,
    21 and 30 px (raw data lost). Smaller or larger cells and other printer
    drivers are accepted but were not measured. Raise ValueError for a
    non-Sheet, an unmeasured default font, a maximum outside 20-100, a column
    wider than 255 characters of the default font, or when even 20 % (the
    smallest measured scale) is too large.
    """
    from ._model import Font, Sheet  # the model imports this module

    if not isinstance(sheet, Sheet):
        raise ValueError("print_fit needs a Sheet")
    font = default_font
    if (not isinstance(font, Font) or (font.name, font.size) not in PRINT_MEASURED_FONTS or font.bold
            or font.italic or font.color != (0.0, 0.0, 0.0)):
        measured = ", ".join(f"{name} {size:g} pt" for name, size in PRINT_MEASURED_FONTS)
        raise ValueError(f"printing was measured only with the default fonts {measured}")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not MIN_FIT_SCALE <= maximum <= MAX_FIT_SCALE:
        raise ValueError(f"maximum must be an integer between {MIN_FIT_SCALE} and {MAX_FIT_SCALE}, the measured scales")
    if any(column_width_chars(width, font) > MAX_COLUMN_WIDTH_CHARS for width in sheet.column_widths_pt):
        raise ValueError("a column is wider than Excel's 255 characters of the default font")
    printable_width, printable_height = sheet.page.printable_size_pt
    width = math.fsum(excel_column_width_pt(width) for width in sheet.column_widths_pt)
    height = max(page_heights_pt(sheet.row_heights_pt, sheet.row_breaks))
    for lowest, factor, row_factor in _PRINT_FACTORS:
        by_width = 100 * printable_width / (width * factor)
        by_height = 100 * printable_height / (height * row_factor)
        scale = min(maximum, math.floor(min(by_width, by_height)))
        if scale >= lowest:
            break
    if scale < MIN_FIT_SCALE:
        raise ValueError(f"the pages do not fit on the paper even at {MIN_FIT_SCALE} % (the smallest measured scale)")
    limited_by = "maximum" if min(by_width, by_height) >= maximum else "width" if by_width <= by_height else "height"
    return PrintFit(scale, limited_by, factor, row_factor)


def fit_scale_percent(sheet: "Sheet", default_font: "Font", *, maximum: int = 100) -> int:
    """Return ``print_fit(sheet, default_font, maximum=maximum).scale``.

    Use the result with ``dataclasses.replace(sheet, page=replace(sheet.page, scale=...))``.
    """
    return print_fit(sheet, default_font, maximum=maximum).scale
