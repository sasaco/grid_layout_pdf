"""Step 10 second stage with Excel: scripts/compare_xlsx_pdf.py drives a real Excel (Windows with Excel only).

Without Excel the tests are skipped with the reason, or fail when
GRIDLAYOUTPDF_REQUIRE_EXCEL=1. Excel's active printer is recorded, never changed.
"""

import importlib.util
import os
import sys
import zipfile
from pathlib import Path

import pymupdf
import pytest

from gridlayoutpdf import Document, PageDecoration, Paragraph
from gridlayoutpdf.renderers.xlsx._model import CellRange, CellValue, Rect, Sheet, Workbook
from gridlayoutpdf.renderers.xlsx._package import save_workbook

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "compare_xlsx_pdf.py"
_SPEC = importlib.util.spec_from_file_location("compare_xlsx_pdf", SCRIPT)
compare = importlib.util.module_from_spec(_SPEC)
sys.modules["compare_xlsx_pdf"] = compare
_SPEC.loader.exec_module(compare)

_MISSING = compare.excel_missing_reason()
_REQUIRE_SETTING = os.environ.get("GRIDLAYOUTPDF_REQUIRE_EXCEL", "")
if _REQUIRE_SETTING not in ("", "0", "1"):
    raise RuntimeError(f"GRIDLAYOUTPDF_REQUIRE_EXCEL must be 0 or 1, not {_REQUIRE_SETTING!r}")
pytestmark = pytest.mark.skipif(_MISSING is not None and _REQUIRE_SETTING != "1", reason=_MISSING or "")


@pytest.fixture(autouse=True)
def _excel_is_required():
    if _MISSING is not None:
        pytest.fail(f"GRIDLAYOUTPDF_REQUIRE_EXCEL=1 but {_MISSING}")


def test_paragraphs_print_where_the_pdf_has_them(tmp_path, record_property):
    document = Document(Paragraph("1. 断面の諸元"), Paragraph("断面積は次の値とする。"), Paragraph("−2.000"),
                        header=PageDecoration("計算書"), footer=PageDecoration("{page} / {pages}", align="right"))
    target = compare.Target("paragraphs", "S", lambda: (document.layout(), None))
    code, report = compare.run(target, tmp_path, zoom=0.5)
    record_property("printer", report["excel"]["printer"])
    assert code == compare.EXIT_PASSED, (report["checks"], report["pages"])
    assert report["excel"]["printer"] and report["excel"]["version"]
    assert report["page_count"]["excel"] == 1 and report["summary"]["missing"] == 0
    assert report["number_cells"] == {"S": 1} and report["hash_cells"] == []
    assert report["checks"]["readback"] and report["checks"]["page_size"]
    assert report["pages"][0]["nearest"] == 0  # the header and footer are compared at their alignment
    assert (tmp_path / "side-by-side" / "page-01.png").is_file()


def test_a_number_too_wide_for_its_cell_is_reported(tmp_path):
    # Excel shows ### in a cell too narrow for the number, and nothing (an empty text) in a cell too
    # narrow for one # (measured: 11 px); both are numbers the reader cannot see.
    path = tmp_path / "narrow.xlsx"
    save_workbook(Workbook((Sheet("N", (30.0, 60.0, 8.0), (15.0,), cells=(
        CellValue(0, 0, 1234567.0, number_format="0.000"), CellValue(0, 1, 1.5, number_format="0.0"),
        CellValue(0, 2, 1234567.0, number_format="0.000"))),)), path)
    printed = compare.run_excel(path, [tmp_path / "narrow.pdf"], 180)
    assert printed["open_error"] is None
    (sheet,) = printed["sheets"]
    assert sheet["number_cells"] == 3
    assert [(cell["address"], cell["text"]) for cell in sheet["hashes"]] == [("A1", "###"), ("C1", "")]


def test_a_merged_number_counts_once_and_shapes_are_read_back(tmp_path):
    path = tmp_path / "merged.xlsx"
    save_workbook(Workbook((Sheet("M", (40.0, 40.0, 40.0), (15.0, 15.0), cells=(
        CellValue(0, 0, 12.5, number_format="0.00"),), merges=(CellRange(0, 0, 1, 1),),
        drawings=(Rect(90.0, 2.0, 20.0, 10.0),)),)), path)
    printed = compare.run_excel(path, [tmp_path / "merged.pdf"], 180)
    (sheet,) = printed["sheets"]
    assert sheet["number_cells"] == 1 and sheet["hashes"] == []
    assert sheet["shapes"] == compare.workbook_shapes(path)["M"] == 1


def test_a_turned_piece_is_found_in_excel_glyphs_read_the_same_way(tmp_path):
    from gridlayoutpdf import A4_PORTRAIT_REFERENCE, GridSpec, QuarterTurn

    grid = A4_PORTRAIT_REFERENCE.grid
    document = Document(Paragraph("本文"), QuarterTurn(Paragraph("回転"), turns=1,
                                                      local_grid=GridSpec(0, 0, grid.pitch_y, grid.pitch_x, 4, 1)))
    target = compare.Target("turned", "S", lambda: (document.layout(), None))
    code, report = compare.run(target, tmp_path, zoom=0.5)
    assert code in (compare.EXIT_PASSED, compare.EXIT_FAILED), report
    with pymupdf.open(tmp_path / "library.pdf") as library:
        turned = [piece for piece in compare.pdf_pieces(library[0]) if piece.vertical]
    assert [piece.text for piece in turned] == ["回転"]
    assert report["summary"]["missing"] == 0, report["pages"]
    assert [item for item in report["pages"][0]["outside"] if item["vertical"]] == []


def test_a_workbook_excel_cannot_open_is_reported(tmp_path):
    good, broken = tmp_path / "good.xlsx", tmp_path / "broken.xlsx"
    save_workbook(Workbook((Sheet("B", (20.0,), (15.0,), cells=(CellValue(0, 0, "x"),)),)), good)
    with zipfile.ZipFile(good) as source, zipfile.ZipFile(broken, "w") as target:
        for item in source.infolist():
            data = source.read(item)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = data[: len(data) // 2]  # an unclosed XML part: Excel would have to repair it
            target.writestr(item, data)
    printed = compare.run_excel(broken, [tmp_path / "broken.pdf"], 180)
    assert printed["open_error"], printed
    assert printed["sheets"] == []
