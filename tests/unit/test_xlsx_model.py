"""Validation of the immutable .xlsx sheet model; errors are never auto-corrected."""

from dataclasses import FrozenInstanceError

import pytest

from gridlayoutpdf.renderers.xlsx._model import (
    MAX_COLUMNS,
    MAX_ROWS,
    CellValue,
    Font,
    Sheet,
    Workbook,
    validate_sheet_name,
)


def _sheet(name="S", **kwargs):
    kwargs.setdefault("column_widths_pt", (16.08,) * 4)
    kwargs.setdefault("row_heights_pt", (15.48,) * 4)
    return Sheet(name, **kwargs)


def test_model_is_frozen_and_snapshots_sequences():
    widths = [16.08, 16.08]
    sheet = Sheet("S", widths, [15.48])
    widths.append(1.0)
    assert sheet.column_widths_pt == (16.08, 16.08)
    with pytest.raises(FrozenInstanceError):
        sheet.name = "T"


@pytest.mark.parametrize("size", [10.5, 1, 409, 6.5])
def test_font_sizes_in_half_point_steps(size):
    assert Font("IPAex明朝", size).size == size


@pytest.mark.parametrize("size", [9.9, 10.25, 0.5, 409.5, float("nan"), True, "10"])
def test_font_size_off_the_half_point_grid_or_range_is_an_error(size):
    with pytest.raises(ValueError, match="font size"):
        Font("IPAex明朝", size)


@pytest.mark.parametrize("kwargs", [
    {"name": ""}, {"name": 3}, {"color": (1, 0)}, {"color": (0, 0, 2)}, {"color": "red"},
    {"bold": 1}, {"italic": None},
])
def test_font_rejects_invalid_fields(kwargs):
    arguments = {"name": "IPAex明朝", "size": 10} | kwargs
    with pytest.raises(ValueError):
        Font(**arguments)


@pytest.mark.parametrize("name", [
    "a" * 31, "計算書", "😀" * 15 + "a", "History", "a'b", " lead", "a　b",
])
def test_sheet_names_excel_accepts(name):
    assert validate_sheet_name(name) == name


@pytest.mark.parametrize("name", [
    "", "a" * 32, "😀" * 16, "a[b", "a]b", "a:b", "a*b", "a?b", "a/b", "a\\b", "'ab", "ab'", "a\x01b", 5,
])
def test_sheet_names_excel_rejects_are_errors_and_never_renamed(name):
    with pytest.raises(ValueError, match="sheet name"):
        validate_sheet_name(name)


@pytest.mark.parametrize(("first", "second"), [
    ("abc", "ABC"), ("A", "Ａ"), ("ア", "ｱ"), ("Ä", "ä"), ("ß", "SS"), ("①", "1"), ("ﬁ", "fi"),
    ("ｶﾞ", "ガ"), ("σ", "ς"), ("é", "é"),
])
def test_sheet_names_excel_treats_as_the_same_are_errors(first, second):
    with pytest.raises(ValueError, match="used twice"):
        Workbook((_sheet(first), _sheet(second)))


def test_sheet_names_excel_treats_as_different_are_accepted():
    assert len(Workbook((_sheet("ア"), _sheet("あ"), _sheet("İ"), _sheet("i"))).sheets) == 4


def test_workbook_needs_sheets_and_a_font():
    with pytest.raises(ValueError, match="at least one sheet"):
        Workbook(())
    with pytest.raises(ValueError, match="Sheet"):
        Workbook(("S",))
    with pytest.raises(ValueError, match="default_font"):
        Workbook((_sheet(),), default_font="游ゴシック")


def test_sheet_size_limits_are_excel_limits():
    assert len(Sheet("S", (1.0,) * MAX_COLUMNS, (15.0,)).column_widths_pt) == MAX_COLUMNS
    with pytest.raises(ValueError, match="16384 columns"):
        Sheet("S", (1.0,) * (MAX_COLUMNS + 1), (15.0,))
    with pytest.raises(ValueError, match="1048576 rows"):
        Sheet("S", (1.0,), (15.0,) * (MAX_ROWS + 1))
    with pytest.raises(ValueError, match="columns"):
        Sheet("S", (), (15.0,))


@pytest.mark.parametrize(("widths", "heights"), [
    ((0.0,), (15.0,)), ((16.0,), (0.37,)), ((0.3,), (15.0,)), ((16.0,), (410.0,)), ((float("inf"),), (15.0,)),
])
def test_sheet_rejects_lengths_excel_cannot_show(widths, heights):
    with pytest.raises(ValueError):
        Sheet("S", widths, heights)


def test_cells_must_be_unique_and_inside_the_sheet():
    with pytest.raises(ValueError, match="more than once"):
        _sheet(cells=(CellValue(0, 0, "a"), CellValue(0, 0, "b")))
    with pytest.raises(ValueError, match="outside"):
        _sheet(cells=(CellValue(4, 0, "a"),))
    with pytest.raises(ValueError, match="outside"):
        _sheet(cells=(CellValue(0, 4, "a"),))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, b"x", "a\x00", "a" * 32_768],
                         ids=["nan", "inf", "bool", "bytes", "nul", "too-long"])
def test_cell_values_excel_cannot_hold_are_errors(value):
    with pytest.raises(ValueError):
        CellValue(0, 0, value)


def test_integer_cell_values_become_floats():
    assert CellValue(0, 0, 3).value == 3.0
    assert isinstance(CellValue(0, 0, 3).value, float)


# --- review round 1 ----------------------------------------------------------

import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

from gridlayoutpdf.renderers.xlsx._model import (  # noqa: E402
    CellRange,
    EdgeBorder,
    Line,
    Rect,
    paper_for_size,
)


@pytest.mark.parametrize("make", [
    lambda: CellValue(0, 0, 10**400),
    lambda: Font("IPAex明朝", 10**400),
    lambda: Sheet("S", (10**400,), (15.0,)),
    lambda: Line(0, 0, 10**400, 0),
])
def test_huge_integers_are_value_errors_not_overflow(make):
    with pytest.raises(ValueError):
        make()


@pytest.mark.parametrize("make", [
    lambda: Workbook({_sheet()}),
    lambda: _sheet(cells={CellValue(0, 0, "a"): 1}),
    lambda: _sheet(cells={CellValue(0, 0, "a")}),
    lambda: Font("IPAex明朝", 10, color={0, 0.5, 1}),
    lambda: Font("IPAex明朝", 10, color=frozenset({0, 0.5, 1})),
])
def test_unordered_collections_are_errors_so_output_order_is_fixed(make):
    with pytest.raises(ValueError, match="ordered"):
        make()


@pytest.mark.parametrize("name", ["a\tb", "a\nb", "a b", "a\x85b"])
def test_sheet_names_with_control_characters_are_errors(name):
    with pytest.raises(ValueError, match="sheet name"):
        validate_sheet_name(name)


@pytest.mark.parametrize("name", ["a\tb", "A" * 32, " "])
def test_font_names_excel_cannot_open_are_errors(name):
    # Excel 16.0 did not open a workbook with a 32-character font name (31 opened).
    with pytest.raises(ValueError, match="font name"):
        Font(name, 10)


def test_31_character_font_name_is_accepted():
    assert Font("A" * 31, 10).name == "A" * 31


@pytest.mark.parametrize("font", [Font("游ゴシック", 11, bold=True), Font("游ゴシック", 11, italic=True),
                                  Font("游ゴシック", 11, color=(1, 0, 0))])
def test_default_font_must_be_the_measured_plain_font(font):
    with pytest.raises(ValueError, match="default_font"):
        Workbook((_sheet(),), default_font=font)


def test_custom_number_formats_above_excel_limit_are_errors():
    # Excel 16.0 (ja-JP) opened 206 custom number formats and refused 207.
    def book(count):
        cells = tuple(CellValue(row, 0, 1.0, number_format=f'0.0"u{row}"') for row in range(count))
        return Workbook((Sheet("S", (16.0,), (15.0,) * count, cells=cells),))
    assert book(206)
    with pytest.raises(ValueError, match="206"):
        book(207)


def test_validation_is_linear_in_merges_cells_and_borders():
    rows, cols = 2000, 30
    merges = tuple(CellRange(row, col, row, col + 1) for row in range(rows) for col in range(0, cols, 2))
    cells = tuple(CellValue(merge.first_row, merge.first_col, "x") for merge in merges)
    borders = tuple(EdgeBorder(merge.first_row, merge.first_col, "top", "thin") for merge in merges)
    start = time.perf_counter()
    Sheet("S", (16.08,) * cols, (15.48,) * rows, cells=cells, merges=merges, borders=borders)
    assert time.perf_counter() - start < 3.0  # 30,000 merges; the quadratic checks took minutes


def test_drawing_on_the_far_edge_computed_with_float_error_is_accepted():
    rows, height = 47 * 37, 15.48
    bottom = 36 * 47 * height + 47 * height  # page offset + local position, as Step 8 computes it
    sheet = Sheet("S", (16.08,) * 30, (height,) * rows,
                  drawings=(Line(0, bottom, 30 * 16.08, bottom), Rect(0, 0, 30 * 16.08, bottom)))
    assert len(sheet.drawings) == 2
    with pytest.raises(ValueError, match="outside the sheet"):
        Sheet("S", (16.08,) * 30, (height,) * rows, drawings=(Line(0, bottom + 0.01, 10, bottom + 0.01),))


@pytest.mark.parametrize(("size", "expected"), [
    ((595.2756, 841.8898), ("A4", "portrait")), ((595, 842), ("A4", "portrait")),
    ((842, 595), ("A4", "landscape")), ((1191, 842), ("A3", "landscape")), ((841.89, 1190.55), ("A3", "portrait")),
])
def test_paper_for_size(size, expected):
    assert paper_for_size(*size) == expected


def test_paper_for_size_rejects_other_papers():
    with pytest.raises(ValueError, match="A4 or A3"):
        paper_for_size(515.9, 728.5)  # B5


_SCRIPT = """
import hashlib, sys
sys.path.insert(0, sys.argv[1])
from test_xlsx_drawing import _png
from gridlayoutpdf.renderers.xlsx._model import *
from gridlayoutpdf.renderers.xlsx._package import write_workbook
f = Font("IPAex明朝", 10)
s1 = Sheet("一", (16.08,) * 4, (15.48,) * 4,
           cells=(CellValue(0, 0, RichText((Run("a"), Run("2", vert_align="superscript"))), font=f),
                  CellValue(1, 1, 2.5, number_format='0.00"u"')),
           borders=(EdgeBorder(1, 1, "top", "thin"),),
           drawings=(Group((Rect(0, 0, 10, 10, text=TextFrame(((Run("x"),),), font=f)),
                            Picture(0, 20, 10, 10, _png(), "png"))),))
s2 = Sheet("二", (16.08,), (15.48,), cells=(CellValue(0, 0, "b"),))
print(hashlib.sha256(write_workbook(Workbook((s1, s2)))).hexdigest())
"""


def test_same_model_gives_the_same_bytes_in_processes_with_different_hash_seeds(tmp_path):
    script = tmp_path / "digest.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    digests = set()
    for seed in ("1", "2", "3"):
        environment = dict(os.environ, PYTHONHASHSEED=seed, PYTHONUTF8="1")
        completed = subprocess.run([sys.executable, str(script), str(Path(__file__).parent)], env=environment,
                                   capture_output=True, check=True)
        digests.add(completed.stdout.strip())
    assert len(digests) == 1


# --- review round 2 ----------------------------------------------------------

import itertools  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402

from gridlayoutpdf.renderers.xlsx._xml import escape_spreadsheet_text  # noqa: E402

_ENCODED = re.compile("_x([0-9A-Fa-f]{4})_")


def _decode_spreadsheet_text(text):
    """Decode _xHHHH_ left to right without overlaps, as a SpreadsheetML reader does."""
    return _ENCODED.sub(lambda match: chr(int(match.group(1), 16)), text)


def test_spreadsheet_text_escape_round_trips_every_short_string_of_the_risky_characters():
    alphabet = "_x0D\r"  # up to 8 characters, so "_x000D" followed by a CR is included
    failures = [text for length in range(1, 9) for text in map("".join, itertools.product(alphabet, repeat=length))
                if _decode_spreadsheet_text(escape_spreadsheet_text(text)) != text]
    assert failures == []


@pytest.mark.parametrize("text", ["_x0041_x0042_", "_x005F_x0041_", "_x000D\r", "_x0041\r", "a_x0041_b"])
def test_spreadsheet_text_escape_keeps_chained_and_cr_forms(text):
    assert _decode_spreadsheet_text(escape_spreadsheet_text(text)) == text


def test_the_same_merge_instance_given_twice_is_an_overlap():
    merge = CellRange(0, 0, 1, 1)
    with pytest.raises(ValueError, match="overlap"):
        _sheet(merges=(merge, merge))
    with pytest.raises(ValueError, match="overlap"):
        _sheet(merges=(CellRange(0, 0, 1, 1), CellRange(0, 0, 1, 1)))


def test_the_same_cell_or_border_instance_given_twice_is_an_error():
    cell = CellValue(0, 0, "a")
    border = EdgeBorder(0, 0, "top", "thin")
    with pytest.raises(ValueError, match="more than once"):
        _sheet(cells=(cell, cell))
    with pytest.raises(ValueError, match="same edge"):
        _sheet(borders=(border, border))


@pytest.mark.parametrize("make", [
    lambda: validate_sheet_name("S_x0041_"),
    lambda: Font("F_x0041_", 10),
    lambda: CellValue(0, 0, 1.0, number_format="0_x0029_"),
])
def test_names_and_formats_excel_would_decode_are_errors(make):
    with pytest.raises(ValueError, match="_xHHHH_"):
        make()


@pytest.mark.parametrize("make", [
    lambda: Line(0, 0, 10, 0, dash=bytearray(b"\x03\x01")),
    lambda: Font("IPAex明朝", 10, color=bytearray(b"\x00\x00\x00")),
    lambda: Line(0, 0, 10, 0, dash=memoryview(b"\x03\x01")),
])
def test_byte_sequences_are_not_number_sequences(make):
    with pytest.raises(ValueError, match="ordered"):
        make()


def test_cell_boundaries_far_down_a_tall_sheet_anchor_at_the_next_cell():
    from gridlayoutpdf.renderers.xlsx._drawing import SheetGeometry

    rows = 100_000
    geometry = SheetGeometry(Sheet("S", (16.08,), (15.48,) * rows))
    for row in (1, 47, 4_700, 99_999):
        assert geometry.y.anchor(math.fsum((15.48,) * row)) == (row, 0)
        assert geometry.y.anchor(row * 15.48) == (row, 0)


# --- review round 3 ----------------------------------------------------------

from gridlayoutpdf.renderers.xlsx._model import Diamond, Ellipse, Polyline, Run, TextFrame  # noqa: E402

_MINCHO = Font("IPAex明朝", 10)


@pytest.mark.parametrize("make", [
    lambda: Rect(0, 0, 10, 10, 0.5),
    lambda: Ellipse(0, 0, 10, 10, False),
    lambda: Diamond(0, 0, 10, 10, False),
    lambda: Polyline(((0, 0), (1, 1)), True),
    lambda: Line(0, 0, 1, 1, 0.5),
    lambda: TextFrame(((Run("x"),),), _MINCHO),
])
def test_style_fields_are_keyword_only_unlike_positional_scene_fields(make):
    # scene.Rectangle's fifth field is the stroke width; here it would silently be a corner radius.
    with pytest.raises(TypeError):
        make()


@pytest.mark.parametrize("make", [
    lambda: TextFrame(((Run("x"),),), font=_MINCHO, insets_pt=(1e308, 0, 0, 0)),
    lambda: Line(0, 0, 10, 0, dash=(1e308,)),
    lambda: Sheet("S", (16.0,), (1.7e308,)),
    lambda: Sheet("S", (1.7e308,), (15.0,)),
])
def test_huge_finite_floats_are_value_errors_not_overflow(make):
    with pytest.raises(ValueError):
        make()


def test_closed_polyline_needs_three_points_and_an_empty_text_is_no_text():
    with pytest.raises(ValueError, match="three points"):
        Polyline(((0, 0), (10, 10)), closed=True, fill=(1, 0, 0))
    with pytest.raises(ValueError, match="stroke, a fill or text"):
        Rect(0, 0, 10, 10, stroke=False, text=TextFrame(((),), font=_MINCHO))


@pytest.mark.parametrize("tolerance", [-1, 11, float("nan")])
def test_paper_tolerance_is_checked(tolerance):
    with pytest.raises(ValueError, match="tolerance"):
        paper_for_size(595, 842, tolerance)


def test_rotation_must_be_an_int_choice():
    with pytest.raises(ValueError, match="0, 90, 270 \\(an int\\)"):
        CellValue(0, 0, "x", rotation=90.0)
    with pytest.raises(ValueError, match="0, 90, 180, 270 \\(an int\\)"):
        TextFrame(((Run("x"),),), font=_MINCHO, rotation=90.0)
