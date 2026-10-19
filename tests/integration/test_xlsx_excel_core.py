"""Open the standard-library .xlsx in Excel through COM (Windows with Excel only).

Excel is driven by a PowerShell script (no pywin32 dependency) with
``Visible=False`` and ``DisplayAlerts=False``; it always quits, and the test
kills the Excel process it started if the script times out or Excel stays.
A workbook that Excel would have to repair makes ``Workbooks.Open`` fail in
that mode, and the contents Excel reads back (cells, formats, merges,
borders, page setup and shapes with their line, fill and text attributes) are
compared with the model, which also catches parts Excel dropped or reset.
PDF checks use ``ExportAsFixedFormat`` and depend on Excel's active printer
(the print factors were measured with "DocuWorks PDF" and "DocuWorks
Printer"); with other printers the print checks are expected to fail (xfail),
or fail when GRIDLAYOUTPDF_REQUIRE_EXCEL=1. The cases at DocuWorks PDF's worst
conditions are skipped unless that printer is active.
"""

import dataclasses
import io
import json
import math
import os
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

import pytest

from gridlayoutpdf.renderers.xlsx._model import (
    BORDER_STYLES,
    Arrowhead,
    CellRange,
    CellValue,
    Diamond,
    EdgeBorder,
    Ellipse,
    Font,
    Group,
    HeaderFooter,
    HeaderSection,
    Line,
    Margins,
    PageNumber,
    PageSetup,
    Picture,
    Polyline,
    Rect,
    RichText,
    Run,
    Sheet,
    SheetPageCount,
    TextBox,
    TextFrame,
    Workbook,
    range_edges,
)
from gridlayoutpdf.renderers.xlsx._package import save_workbook, write_workbook
from gridlayoutpdf.renderers.xlsx._units import (
    _MAX_DIGIT_WIDTH_PX,
    _PRINT_FACTORS,
    MAX_FIT_SCALE,
    excel_column_width_pt,
    excel_row_height_pt,
    print_fit,
)


def _excel_missing_reason() -> str | None:
    if sys.platform != "win32":
        return "Excel COM checks need Windows"
    import winreg

    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application\CLSID"))
    except OSError:
        return "Microsoft Excel is not installed (no Excel.Application COM class)"
    return None


_MISSING = _excel_missing_reason()
# GRIDLAYOUTPDF_REQUIRE_EXCEL=1 turns a missing Excel into a failure instead of a skip.
_REQUIRE_SETTING = os.environ.get("GRIDLAYOUTPDF_REQUIRE_EXCEL", "")
if _REQUIRE_SETTING not in ("", "0", "1"):
    raise RuntimeError(f"GRIDLAYOUTPDF_REQUIRE_EXCEL must be 0 or 1, not {_REQUIRE_SETTING!r}")
_REQUIRED = _REQUIRE_SETTING == "1"
pytestmark = pytest.mark.skipif(_MISSING is not None and not _REQUIRED, reason=_MISSING or "")


@pytest.fixture(autouse=True)
def _excel_is_required():
    if _MISSING is not None:
        pytest.fail(f"GRIDLAYOUTPDF_REQUIRE_EXCEL=1 but {_MISSING}")


_PRELUDE = r"""
$ErrorActionPreference = 'Stop'
$params = Get-Content -Raw -Encoding UTF8 -LiteralPath $args[0] | ConvertFrom-Json
Add-Type -Namespace XlsxCheck -Name Native -MemberDefinition '[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr window, out uint process);'
$xl = New-Object -ComObject Excel.Application
try {
  [uint32]$excelProcess = 0
  [void][XlsxCheck.Native]::GetWindowThreadProcessId([System.IntPtr]$xl.Hwnd, [ref]$excelProcess)
  Set-Content -Encoding ASCII -LiteralPath $args[2] -Value $excelProcess
  $xl.Visible = $false
  $xl.DisplayAlerts = $false
  $xl.ScreenUpdating = $false
  $result = & {
"""
_POSTLUDE = r"""
  }
  ConvertTo-Json -InputObject $result -Depth 8 -Compress | Set-Content -Encoding UTF8 -LiteralPath $args[1]
} finally {
  foreach ($book in @($xl.Workbooks)) { $book.Close($false) }
  $xl.Quit()
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
"""


def _running(process: int) -> bool:
    """Is the Excel with this PID still running? (The image name guards against a reused PID.)"""
    completed = subprocess.run(["tasklist", "/FI", f"PID eq {process}", "/FI", "IMAGENAME eq EXCEL.EXE",
                                "/FO", "CSV", "/NH"], capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(f"tasklist failed with exit code {completed.returncode}")
    return f'"{process}"' in completed.stdout.decode("ascii", "replace")


def _run_excel(directory: Path, body: str, params: dict, *, timeout: float = 180):
    """Run ``body`` (a PowerShell block whose value is the result) in a hidden Excel."""
    script, inputs, outputs, process_file = (directory / name for name in (
        "excel.ps1", "params.json", "result.json", "excel.pid"))
    script.write_text(_PRELUDE + body + _POSTLUDE, encoding="utf-8-sig")
    inputs.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
    process_file.unlink(missing_ok=True)
    outputs.unlink(missing_ok=True)
    error = ""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
             str(inputs), str(outputs), str(process_file)], capture_output=True, timeout=timeout)
        if completed.returncode != 0:
            error = (completed.stderr + completed.stdout).decode("oem", "replace")  # PowerShell's console code page
    except subprocess.TimeoutExpired:
        error = f"the Excel COM check did not finish in {timeout} s"
    process = int(process_file.read_text(encoding="ascii").strip()) if process_file.exists() else None
    if process is not None and process <= 0:
        error += "\nthe Excel process ID could not be read, so a remaining Excel cannot be stopped"
    elif process is not None:
        deadline = time.monotonic() + 20
        try:
            while _running(process) and time.monotonic() < deadline:
                time.sleep(0.5)
            remaining = _running(process)
        except RuntimeError as exc:
            error += f"\n{exc}"
            remaining = True
        if remaining:
            killed = subprocess.run(["taskkill", "/PID", str(process), "/T", "/F"], capture_output=True)
            error += f"\nExcel (PID {process}) did not quit and " + (
                "was stopped" if killed.returncode == 0 else f"could not be stopped (exit {killed.returncode})")
    assert not error, error
    return json.loads(outputs.read_text(encoding="utf-8-sig"))


def _png() -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 4 for _ in range(2))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _jpeg() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 2), (0, 128, 255)).save(buffer, "JPEG")
    return buffer.getvalue()


MINCHO = Font("ＭＳ 明朝", 10.5)
W, H = 16.08, 15.48  # Excel shows both as 21 px = 15.75 pt
X = 4 * 60.0  # drawings start after the four wide columns, so they lie in pixel-rounded columns
MERGE = CellRange(4, 0, 5, 2)
FRAME = TextFrame(((Run("σ"), Run("ck", vert_align="subscript"), Run("2", vert_align="superscript")), (),
                   (Run("2行目"),)), font=MINCHO, h_align="center", v_align="center", insets_pt=(1.5, 0, 0, 0))

CELLS = (
    CellValue(0, 0, "Ｌ＝", font=MINCHO),
    CellValue(0, 1, -2.0, number_format='0.000;"−"0.000', h_align="right"),
    CellValue(0, 2, 1234.5, number_format="#,##0.0", h_align="center", v_align="top"),
    CellValue(0, 3, 2.5, number_format='"+"0.00', v_align="bottom"),
    CellValue(1, 0, RichText((Run("σ"), Run("ck", vert_align="subscript"),
                              Run("2", Font("ＭＳ ゴシック", 9), vert_align="superscript"))), font=MINCHO),
    CellValue(1, 1, "_x0041_"),
    CellValue(1, 2, "a\r\nb"),
    CellValue(2, 0, "縦", rotation=90),
    CellValue(2, 1, "横", rotation=270),
    CellValue(2, 2, "書体", font=Font("ＭＳ ゴシック", 9, color=(1, 0, 0), bold=True, italic=True), fill=(1, 1, 0)),
    CellValue(4, 0, "結合", h_align="center"),
)
BORDERS = (
    tuple(EdgeBorder(8, col, "top", style, color=(0, 0, 1) if col == 0 else (0, 0, 0))
          for col, style in enumerate(BORDER_STYLES))
    + range_edges(MERGE, "top", "thin") + range_edges(MERGE, "bottom", "thin")
    + range_edges(MERGE, "left", "medium") + range_edges(MERGE, "right", "medium")
)
DRAWINGS = (
    Line(X + 0.5 * W, 10 * H, X + 5 * W, 10.5 * H, stroke_width_pt=0.75),
    Line(X + 5 * W, 11 * H, X + W, 13 * H, stroke_width_pt=1, color=(1, 0, 0), dash=(3, 1.5),
         start_arrow=Arrowhead("oval"), end_arrow=Arrowhead()),
    Polyline(((X + W, 14 * H), (X + 3 * W, 14 * H), (X + 2 * W, 16 * H)), closed=True, fill=(0, 0, 1)),
    Polyline(((X + 4 * W, 14 * H), (X + 6 * W, 14 * H))),
    Rect(X + W + 3.2, 17 * H + 1.7, 4 * W, 2 * H, text=FRAME),
    Rect(X + 6 * W, 17 * H, 4 * W, 2 * H, corner_radius_pt=5, fill=(0.9, 0.9, 0.9)),
    Ellipse(X + W, 20 * H, 4 * W, 2 * H, text=FRAME),
    Diamond(X + 6 * W, 20 * H, 4 * W, 2 * H, text=FRAME, stroke=False, fill=(1, 1, 0)),
    TextBox(X + W, 23 * H, 4 * W, 2 * H, TextFrame(((Run("上向き"),),), font=MINCHO, rotation=90)),
    TextBox(X + 6 * W, 23 * H, 4 * W, 2 * H, TextFrame(((Run("下_x0041_"),),), font=MINCHO, rotation=270)),
    Picture(X + W, 26 * H, 4 * W, 2 * H, _png(), "png"),
    Group((Rect(X + 6 * W, 26 * H, 2 * W, H), Group((Line(X + 6 * W, 28 * H, X + 9.5 * W, 28 * H),
                                                      Ellipse(X + 8 * W, 27 * H, W, H))))),
)
# Excel's Shape.Type and AutoShapeType (msoLine 9, msoFreeform 5, msoAutoShape 1, msoTextBox 17,
# msoPicture 13, msoGroup 6; msoShapeRectangle 1, RoundedRectangle 5, Oval 9, Diamond 4).
SHAPE_KINDS = [(9, None), (9, None), (5, None), (5, None), (1, 1), (1, 5), (1, 9), (1, 4), (17, None), (17, None),
               (13, None), (6, None)]
PAGE = PageSetup(paper="A4", orientation="portrait", margins=Margins(36, 54, 18, 27, 9, 13.5), scale=85,
                 first_page_number=3)
HEADER = HeaderFooter(left=HeaderSection(("A&B_x0030_",)), center=HeaderSection(("- ", PageNumber(), " -")),
                      right=HeaderSection((PageNumber(), "/", SheetPageCount())))
FOOTER = HeaderFooter(left=HeaderSection((PageNumber(), "+1")),
                      center=HeaderSection((SheetPageCount(), "-2"), font=Font("ＭＳ 明朝", 9)),
                      right=HeaderSection(("12AB計算書",), font=Font("ＭＳ 明朝", 9, bold=True)))
COLUMNS = (60.0,) * 4 + (W,) * 10  # 60 pt (80 px) leaves room for the formatted numbers
MAIN = Sheet("計算書", COLUMNS, (H,) * 30, cells=CELLS, merges=(MERGE, CellRange(4, 4, 6, 4)), borders=BORDERS,
             row_breaks=(10, 20), page=PAGE, header=HEADER, footer=FOOTER, drawings=DRAWINGS,
             show_gridlines=False)
SECOND = Sheet("it's ２", (20.0,) * 3, (18.0,) * 4, cells=(CellValue(0, 0, 1.0),),
               page=PageSetup(paper="A3", orientation="landscape", print_gridlines=True),
               drawings=(Picture(0, 0, 40, 20, _png(), "png"), Picture(0, 20, 40, 20, _jpeg(), "jpeg")))
FEATURES = Workbook((MAIN, SECOND))

_READ_FEATURES = r"""
  $book = $xl.Workbooks.Open($params.path, 0, $true)
  $sheets = @()
  foreach ($ws in $book.Worksheets) {
    $ws.Activate() | Out-Null
    $cells = @()
    foreach ($address in $params.cells) {
      $c = $ws.Range($address)
      $cells += [ordered]@{ address = $address; value = $c.Value2; text = $c.Text; format = $c.NumberFormat;
        h = $c.HorizontalAlignment; v = $c.VerticalAlignment; orientation = $c.Orientation;
        font = $c.Font.Name; size = $c.Font.Size; bold = $c.Font.Bold; italic = $c.Font.Italic;
        color = $c.Font.Color; fill = $c.Interior.Color; pattern = $c.Interior.Pattern;
        merge = $c.MergeArea.Address($false, $false) }
    }
    $rich = @()
    if ($ws.Index -eq 1) {
      for ($k = 1; $k -le 4; $k++) {
        $f = $ws.Range('A2').Characters($k, 1).Font
        $rich += [ordered]@{ sub = $f.Subscript; sup = $f.Superscript; name = $f.Name; size = $f.Size }
      }
    }
    $borders = @()
    foreach ($address in $params.borders) {
      $b = $ws.Range($address).Borders
      $edges = @()
      foreach ($index in 8, 9, 7, 10) {
        $edges += [ordered]@{ style = $b.Item($index).LineStyle; weight = $b.Item($index).Weight; color = $b.Item($index).Color }
      }
      $borders += [ordered]@{ address = $address; edges = $edges }
    }
    $widths = @(); for ($col = 1; $col -le $params.columns[$ws.Index - 1]; $col++) { $widths += $ws.Columns.Item($col).Width }
    $heights = @(); for ($row = 1; $row -le $params.rows[$ws.Index - 1]; $row++) { $heights += $ws.Rows.Item($row).Height }
    $shapes = @()
    foreach ($s in $ws.Shapes) {
      $item = [ordered]@{ name = $s.Name; type = $s.Type; left = $s.Left; top = $s.Top; width = $s.Width;
        height = $s.Height; hflip = $s.HorizontalFlip; vflip = $s.VerticalFlip; auto = $null; items = @();
        row = $s.TopLeftCell.Row; column = $s.TopLeftCell.Column;
        text = $null; orientation = $null; line = $null; fill = $null; runs = @(); frame = $null }
      if ($s.Type -eq 1) { $item.auto = $s.AutoShapeType }
      if ($s.Type -eq 6) { foreach ($g in $s.GroupItems) { $item.items += [ordered]@{ type = $g.Type; left = $g.Left; top = $g.Top; width = $g.Width; height = $g.Height } } }
      if ($s.Type -ne 6 -and $s.Type -ne 13) {
        $item.line = [ordered]@{ visible = $s.Line.Visible; weight = $s.Line.Weight; color = $s.Line.ForeColor.RGB;
          dash = $s.Line.DashStyle; begin = $s.Line.BeginArrowheadStyle; end = $s.Line.EndArrowheadStyle }
      }
      if ($s.Type -eq 1 -or $s.Type -eq 5 -or $s.Type -eq 17) { $item.fill = [ordered]@{ visible = $s.Fill.Visible; color = $s.Fill.ForeColor.RGB } }
      if ($s.Type -eq 1 -or $s.Type -eq 17) {
        $t = $s.TextFrame2
        $item.text = $t.TextRange.Text; $item.orientation = $t.Orientation
        $align = $null; if ($t.HasText) { $align = $t.TextRange.Paragraphs(1).ParagraphFormat.Alignment }
        $item.frame = [ordered]@{ anchor = $t.VerticalAnchor; align = $align;
          left = $t.MarginLeft; top = $t.MarginTop; wrap = $t.WordWrap }
        for ($k = 1; $k -le [math]::Min(4, $t.TextRange.Length); $k++) {
          $f = $t.TextRange.Characters($k, 1).Font
          $item.runs += [ordered]@{ name = $f.Name; size = $f.Size; sup = $f.Superscript; sub = $f.Subscript }
        }
      }
      $shapes += $item
    }
    $breaks = @(); foreach ($brk in $ws.HPageBreaks) { if ($brk.Type -eq -4135) { $breaks += $brk.Location.Row } }
    $p = $ws.PageSetup
    $sheets += [ordered]@{ name = $ws.Name; cells = $cells; rich = $rich; borders = $borders; widths = $widths;
      heights = $heights; shapes = $shapes; breaks = $breaks; paper = $p.PaperSize; orientation = $p.Orientation;
      margins = @($p.LeftMargin, $p.TopMargin, $p.RightMargin, $p.BottomMargin, $p.HeaderMargin, $p.FooterMargin);
      zoom = $p.Zoom; first = $p.FirstPageNumber; printGridlines = $p.PrintGridlines;
      header = @($p.LeftHeader, $p.CenterHeader, $p.RightHeader); footer = @($p.LeftFooter, $p.CenterFooter, $p.RightFooter);
      printArea = $p.PrintArea; gridlines = $book.Windows.Item(1).DisplayGridlines }
  }
  if ($params.pdf) { $book.Worksheets.Item(1).ExportAsFixedFormat(0, $params.pdf) }
  [ordered]@{ sheets = $sheets; count = $book.Worksheets.Count }
"""


@pytest.fixture(scope="module")
def features(tmp_path_factory):
    directory = tmp_path_factory.mktemp("xlsx_excel")
    path = directory / "features.xlsx"
    save_workbook(FEATURES, path)
    result = _run_excel(directory, _READ_FEATURES, {
        "path": str(path), "pdf": str(directory / "features.pdf"),
        "columns": [len(sheet.column_widths_pt) for sheet in FEATURES.sheets],
        "rows": [len(sheet.row_heights_pt) for sheet in FEATURES.sheets],
        "cells": ["A1", "B1", "C1", "D1", "A2", "B2", "C2", "A3", "B3", "C3", "A5", "E5"],
        "borders": [f"{chr(65 + col)}9" for col in range(len(BORDER_STYLES))] + ["A5", "B5", "C6", "C5"],
    })
    result["pdf"] = directory / "features.pdf"
    return result


def test_excel_opens_the_workbook_without_repair(features):
    assert features["count"] == 2
    assert [sheet["name"] for sheet in features["sheets"]] == ["計算書", "it's ２"]


def test_cell_values_number_formats_and_fonts(features):
    cells = {cell["address"]: cell for cell in features["sheets"][0]["cells"]}
    assert cells["A1"]["value"] == "Ｌ＝" and cells["A1"]["font"] == "ＭＳ 明朝" and cells["A1"]["size"] == 10.5
    assert (cells["B1"]["value"], cells["B1"]["text"], cells["B1"]["format"]) == (-2, "−2.000", '0.000;"−"0.000')
    assert (cells["C1"]["value"], cells["C1"]["text"]) == (1234.5, "1,234.5")
    assert (cells["D1"]["value"], cells["D1"]["text"]) == (2.5, "+2.50")
    assert cells["A2"]["value"] == "σck2"
    assert cells["C3"]["font"] == "ＭＳ ゴシック" and cells["C3"]["size"] == 9
    assert cells["C3"]["bold"] and cells["C3"]["italic"]
    assert cells["C3"]["color"] == 0x0000FF  # Excel colors are 0xBBGGRR
    assert cells["C3"]["fill"] == 0x00FFFF and cells["C3"]["pattern"] == 1


def test_text_that_spreadsheetml_would_change_keeps_its_characters(features):
    cells = {cell["address"]: cell for cell in features["sheets"][0]["cells"]}
    assert cells["B2"]["value"] == "_x0041_"
    assert cells["C2"]["value"] == "a\r\nb"
    assert features["sheets"][0]["header"][0] == "A&&B_x0030_"


def test_rich_text_runs_keep_scripts_and_fonts(features):
    assert features["sheets"][0]["rich"] == [
        {"sub": False, "sup": False, "name": "ＭＳ 明朝", "size": 10.5},
        {"sub": True, "sup": False, "name": "ＭＳ 明朝", "size": 10.5},
        {"sub": True, "sup": False, "name": "ＭＳ 明朝", "size": 10.5},
        {"sub": False, "sup": True, "name": "ＭＳ ゴシック", "size": 9}]


def test_alignment_and_text_rotation(features):
    cells = {cell["address"]: cell for cell in features["sheets"][0]["cells"]}
    # xlLeft -4131, xlCenter -4108, xlRight -4152; xlTop -4160, xlBottom -4107.
    assert (cells["A1"]["h"], cells["A1"]["v"]) == (-4131, -4108)
    assert (cells["B1"]["h"], cells["C1"]["h"], cells["C1"]["v"], cells["D1"]["v"]) == (-4152, -4108, -4160, -4107)
    # Range.Orientation reports textRotation 90 as xlUpward (-4171) and 180 (rotation 270) as xlDownward (-4170).
    assert (cells["A3"]["orientation"], cells["B3"]["orientation"]) == (-4171, -4170)


def test_merges(features):
    cells = {cell["address"]: cell for cell in features["sheets"][0]["cells"]}
    assert cells["A5"]["merge"] == "A5:C6" and cells["E5"]["merge"] == "E5:E7"


# Excel's (LineStyle, Weight) for each SpreadsheetML border style, read in Excel 16.0.
EXCEL_BORDERS = {
    "hair": (1, 1), "thin": (1, 2), "medium": (1, -4138), "thick": (1, 4), "double": (-4119, 4),
    "dotted": (-4118, 2), "dashed": (-4115, 2), "dashDot": (4, 2), "dashDotDot": (5, 2),
    "mediumDashed": (-4115, -4138), "mediumDashDot": (4, -4138), "mediumDashDotDot": (5, -4138),
    "slantDashDot": (13, -4138),
}


def test_every_border_style_and_its_color_read_back(features):
    borders = {item["address"]: item["edges"] for item in features["sheets"][0]["borders"]}
    for col, style in enumerate(BORDER_STYLES):
        top = borders[f"{chr(65 + col)}9"][0]
        assert (top["style"], top["weight"]) == EXCEL_BORDERS[style], style
        assert top["color"] == (0xFF0000 if col == 0 else 0), style


def test_merged_range_borders_cover_the_whole_side(features):
    borders = {item["address"]: item["edges"] for item in features["sheets"][0]["borders"]}
    top, bottom, left, right = range(4)
    assert (borders["A5"][top]["style"], borders["A5"][top]["weight"]) == (1, 2)
    assert (borders["A5"][left]["style"], borders["A5"][left]["weight"]) == (1, -4138)
    assert (borders["C6"][bottom]["style"], borders["C6"][bottom]["weight"]) == (1, 2)
    assert (borders["C6"][right]["style"], borders["C6"][right]["weight"]) == (1, -4138)


def test_column_widths_and_row_heights_are_the_pixel_rounded_sizes(features):
    first, second = features["sheets"]
    assert first["widths"] == [excel_column_width_pt(width) for width in COLUMNS]
    assert excel_column_width_pt(60.0) == 60.0 and excel_column_width_pt(W) == 15.75
    assert first["heights"] == [excel_row_height_pt(H)] * 30
    assert second["widths"] == [excel_column_width_pt(20.0)] * 3
    assert second["heights"] == [excel_row_height_pt(18.0)] * 4


def test_page_setup_header_footer_breaks_and_print_area(features):
    first, second = features["sheets"]
    assert (first["paper"], first["orientation"], first["zoom"], first["first"]) == (9, 1, 85, 3)
    assert first["margins"] == [36, 54, 18, 27, 9, 13.5]
    assert first["header"] == ["A&&B_x0030_", "- &P -", "&P/&N"]
    assert first["footer"] == ['&P&"-,Regular"+1', '&9&K000000&"ＭＳ 明朝,Regular"&N&"ＭＳ 明朝,Regular"-2',
                               '&9&K000000&"ＭＳ 明朝,Bold"12AB計算書']
    assert first["breaks"] == [11, 21]
    assert first["printArea"] == "$A$1:$N$30"
    assert first["gridlines"] is False and first["printGridlines"] is False
    assert (second["paper"], second["orientation"], second["printGridlines"]) == (8, 2, True)
    assert second["printArea"] == "$A$1:$C$4"


def _excel_box(bounds):
    """Where Excel should put a box, written out by hand (not with the library's SheetGeometry).

    The drawings lie right of the four 60 pt (80 px) columns, in columns and
    rows of 16.08 x 15.48 pt that Excel shows as 21 px = 15.75 pt; a point keeps
    its fraction of its cell.
    """
    left, top, right, bottom = bounds
    x0, x1 = (X + (value - X) / W * 15.75 for value in (left, right))
    y0, y1 = (value / H * 15.75 for value in (top, bottom))
    return x0, y0, x1 - x0, y1 - y0


def test_shapes_keep_their_kinds_and_cell_positions(features):
    shapes = features["sheets"][0]["shapes"]
    assert [(shape["type"], shape["auto"]) for shape in shapes] == SHAPE_KINDS
    for shape, drawing in zip(shapes, DRAWINGS):
        actual = (shape["left"], shape["top"], shape["width"], shape["height"])
        assert actual == pytest.approx(_excel_box(drawing.bounds()), abs=0.05), shape["name"]
    # The first line starts half way into the fifth column (a 21 px one) on row 11's top edge.
    assert shapes[0]["left"] == pytest.approx(X + 0.5 * 15.75, abs=0.05)
    assert (shapes[0]["row"], shapes[0]["column"]) == (11, 5)
    # Shapes whose corner lies on a cell boundary start in the cell after it.
    assert (shapes[2]["row"], shapes[2]["column"]) == (15, 6)
    assert (shapes[8]["row"], shapes[8]["column"]) == (24, 6)
    assert (shapes[1]["hflip"], shapes[1]["vflip"]) == (-1, 0)
    group = DRAWINGS[-1]
    leaves = [group.children[0], *group.children[1].children]
    assert [item["type"] for item in shapes[-1]["items"]] == [1, 9, 1]
    for item, leaf in zip(shapes[-1]["items"], leaves):
        actual = (item["left"], item["top"], item["width"], item["height"])
        assert actual == pytest.approx(_excel_box(leaf.bounds()), abs=0.05)
    # Excel reads both pictures of the second sheet back, the PNG and the JPEG (msoPicture 13).
    assert [shape["type"] for shape in features["sheets"][1]["shapes"]] == [13, 13]


def test_shape_lines_fills_and_arrowheads(features):
    shapes = features["sheets"][0]["shapes"]
    plain, dashed = shapes[0]["line"], shapes[1]["line"]
    assert (plain["weight"], plain["color"], plain["dash"]) == (0.75, 0, 1)  # msoLineSolid
    assert (dashed["weight"], dashed["color"]) == (1, 0x0000FF)
    assert dashed["dash"] != 1  # a custom dash is not solid
    # msoArrowheadNone 1, Triangle 2, Oval 6: start_arrow is at (x1, y1), the head end of the line.
    assert (plain["begin"], plain["end"]) == (1, 1)
    assert (dashed["begin"], dashed["end"]) == (6, 2)
    assert shapes[2]["fill"] == {"visible": -1, "color": 0xFF0000}
    assert shapes[3]["fill"]["visible"] == 0 and shapes[3]["line"]["visible"] == -1
    assert shapes[5]["fill"] == {"visible": -1, "color": 0xE6E6E6}
    assert shapes[7]["line"]["visible"] == 0 and shapes[7]["fill"]["color"] == 0x00FFFF
    assert shapes[8]["line"]["visible"] == 0 and shapes[8]["fill"]["visible"] == 0


def test_shape_text_runs_alignment_and_rotation(features):
    shapes = features["sheets"][0]["shapes"]
    assert shapes[4]["text"] in ("σck2\r\r2行目", "σck2\n\n2行目")
    assert [(run["name"], run["size"], run["sub"], run["sup"]) for run in shapes[4]["runs"]] == [
        ("ＭＳ 明朝", 10.5, 0, 0), ("ＭＳ 明朝", 10.5, -1, 0), ("ＭＳ 明朝", 10.5, -1, 0), ("ＭＳ 明朝", 10.5, 0, -1)]
    # msoAnchorMiddle 3, msoAlignCenter 2; insets are pt; wrap=False is msoFalse.
    frame = shapes[4]["frame"]
    assert (frame["anchor"], frame["align"], frame["left"], frame["top"], frame["wrap"]) == (3, 2, 1.5, 0, 0)
    # msoTextOrientationUpward 2 for 90° counterclockwise, Downward 3 for 270°.
    assert (shapes[8]["orientation"], shapes[9]["orientation"]) == (2, 3)
    # DrawingML text is not SpreadsheetML text: _x0041_ stays as written.
    assert shapes[9]["text"] == "下_x0041_"


def test_page_field_followed_by_a_sign_prints_as_text(features):
    pymupdf = pytest.importorskip("pymupdf")
    with pymupdf.open(features["pdf"]) as document:
        first_page = document[0].get_text()
    # first_page_number 3 and 3 pages: "&P/&N" prints "3/3"; "A&B" prints with one "&".
    assert "- 3 -" in first_page and "3/3" in first_page and "A&B_x0030_" in first_page
    # A sign after a page field is text, not page arithmetic (that would print "4" and "1").
    assert "3+1" in first_page and "3-2" in first_page
    # Text that starts with hex digits after a section font is not read as part of the color code.
    assert "12AB計算書" in first_page


_READ_WIDTHS = r"""
  $widths = @()
  foreach ($path in $params.paths) {
    $book = $xl.Workbooks.Open($path, 0, $true); $ws = $book.Worksheets.Item(1)
    $row = @(); for ($col = 1; $col -le $params.count; $col++) { $row += $ws.Columns.Item($col).Width }
    $widths += ,$row
    $book.Close($false)
  }
  ,$widths
"""


def test_every_measured_default_font_gives_the_computed_column_widths(tmp_path):
    widths = (0.75, 3.75, 8.25, 12.0, 15.75, 16.08, 60.0, 99.75, 300.0)
    paths = []
    for index, (name, size) in enumerate(_MAX_DIGIT_WIDTH_PX):
        path = tmp_path / f"font{index}.xlsx"
        save_workbook(Workbook((Sheet("S", widths, (15.0,)),), default_font=Font(name, size)), path)
        paths.append(str(path))
    read = _run_excel(tmp_path, _READ_WIDTHS, {"paths": paths, "count": len(widths)})
    expected = [excel_column_width_pt(width) for width in widths]
    for font, actual in zip(_MAX_DIGIT_WIDTH_PX, read):
        assert actual == expected, font


_EXPORT_PDF = r"""
  foreach ($item in $params.books) {
    $book = $xl.Workbooks.Open($item.path, 0, $true)
    $book.Worksheets.Item(1).ExportAsFixedFormat(0, $item.pdf)
    $book.Close($false)
  }
  [ordered]@{ printer = $xl.ActivePrinter }
"""
MEASURED_PRINTERS = ("DocuWorks PDF on ", "DocuWorks Printer on ")
PRINT_PITCH = Path(__file__).parents[2] / "scripts" / "xlsx_probe" / "print_pitch.json"


GOTHIC, MINCHO_105 = Font("游ゴシック", 11), Font("ＭＳ 明朝", 10.5)
EVEN = Margins(36, 36, 36, 36, 18, 18)
A4_GRID = Margins(left=50.88, top=54.598, right=50.6, bottom=47.0, header=18, footer=18)


def _height_edge(rows: int, target: int, factor: float, row_pt: float) -> Margins:
    """Top and bottom margins that make a page's rows fit at ``target`` + 0.005 % with ``factor`` (A4 portrait)."""
    printable = (target + 0.005) / 100 * rows * excel_row_height_pt(row_pt) * factor
    side = (841.8898 - printable) / 2
    return Margins(36, side, 36, side, 18, 18)


def _band_edge(columns: int, target: int, factor: float, column_pt: float = 16.08) -> Margins:
    """Left and right margins that make the width fit at ``target`` + 0.005 % with ``factor`` (A4 portrait)."""
    printable = (target + 0.005) / 100 * columns * excel_column_width_pt(column_pt) * factor
    side = (595.2756 - printable) / 2
    return Margins(side, 36, side, 36, 18, 18)


FIT_CASES = {
    # id: (columns, column pt, rows per page, row pt, pages, paper, orientation, margins, font, limited by, scale)
    "a4-35-columns": (35, 16.08, 50, 15.48, 3, "A4", "portrait", EVEN, GOTHIC, "width", 91),
    "a4-landscape-52-columns": (52, 16.08, 34, 15.48, 2, "A4", "landscape", EVEN, GOTHIC, "width", 90),
    "a4-100-columns": (100, 16.08, 30, 15.48, 2, "A4", "portrait", EVEN, GOTHIC, "width", 30),
    "a3-at-the-maximum": (30, 20.0, 60, 18.0, 2, "A3", "portrait", EVEN, GOTHIC, "maximum", 100),
    "a3-tall-pages": (40, 20.0, 80, 18.0, 2, "A3", "portrait", EVEN, GOTHIC, "height", 76),
    # Just wide enough at the lowest scale of each band (21 px columns).
    "band-90-lowest": (35, 16.08, 20, 15.48, 2, "A4", "portrait", _band_edge(35, 90, 1.04), GOTHIC, "width", 90),
    "band-55-lowest": (60, 16.08, 20, 15.48, 2, "A4", "portrait", _band_edge(60, 55, 1.05), GOTHIC, "width", 55),
    "band-20-lowest": (150, 16.08, 20, 15.48, 2, "A4", "portrait", _band_edge(150, 20, 1.08), GOTHIC, "width", 20),
    # Just wide enough at the largest column factors measured with "DocuWorks PDF" (11 px at 60 % and 30 %);
    # they only test those factors when the active printer is DocuWorks PDF.
    "docuworks-pdf-worst-60-percent": (100, 8.25, 20, 15.48, 2, "A4", "portrait", _band_edge(100, 60, 1.05, 8.25),
                                       GOTHIC, "width", 60),
    "docuworks-pdf-worst-30-percent": (200, 8.25, 20, 15.48, 2, "A4", "portrait", _band_edge(200, 30, 1.08, 8.25),
                                       GOTHIC, "width", 30),
    "ms-mincho-10.5-default-font": (35, 16.08, 50, 15.48, 2, "A4", "portrait", EVEN, MINCHO_105, "width", 91),
    "a4-reference-grid-at-100": (30, 16.08, 47, 15.48, 2, "A4", "portrait", A4_GRID, GOTHIC, "maximum", 100),
}
DOCUWORKS_PDF_CASES = ("docuworks-pdf-worst-60-percent", "docuworks-pdf-worst-30-percent")


def _worst_case(kind: str, record: dict, column_factor: float, row_factor: float) -> tuple:
    """A case just wide (columns) or just tall (rows) enough at the record's cell size and scale."""
    cell, scale = record["pixels"] * 0.75, record["scale"]
    font = Font(record["font"], record["size"])
    limit = "maximum" if scale == MAX_FIT_SCALE else None  # at 100 % print_fit reports the maximum
    if kind == "columns":
        count = int(500 / (cell * scale / 100 * column_factor))
        return (count, cell, 20, 15.48, 2, "A4", "portrait", _band_edge(count, scale, column_factor, cell),
                font, limit or "width", scale)
    count = int(700 / (cell * scale / 100 * row_factor))
    return (10, 16.08, count, cell, 2, "A4", "portrait", _height_edge(count, scale, row_factor, cell),
            font, limit or "height", scale)


def _fits_as_expected(case: tuple) -> bool:
    columns, width, rows_per_page, height, pages, paper, orientation, margins, font, limited_by, scale = case
    rows = rows_per_page * pages
    sheet = Sheet("S", (width,) * columns, (height,) * rows, row_breaks=tuple(range(rows_per_page, rows, rows_per_page)),
                  page=PageSetup(paper=paper, orientation=orientation, margins=margins))
    fit = print_fit(sheet, font)
    return (fit.scale, fit.limited_by) == (scale, limited_by)


def _worst_measured_cases(records: list[dict]) -> dict:
    """Cases just wide or just tall enough where each band's measured factor is largest.

    In each band the records are tried from the largest factor down, and a
    record is skipped when the case built for it (20 rows or 10 columns, the
    margins set to just fit) would not come out at that scale and extent with
    ``print_fit`` (the top of a lower band can then be a scale of the band
    above). At 100 % the expected extent is "maximum", which also skips the
    check that 5 % more no longer fits. An empty band or a band without a
    usable record is an error.
    """
    cases, upper = {}, MAX_FIT_SCALE + 1
    for lowest, column_factor, row_factor in _PRINT_FACTORS:
        band = [record for record in records if lowest <= record["scale"] < upper]
        upper = lowest
        if not band:
            raise ValueError(f"print_pitch.json has no records from {lowest} %")
        for kind, field in (("columns", "column_factor"), ("rows", "row_factor")):
            for record in sorted(band, key=lambda item: item[field], reverse=True):
                case = _worst_case(kind, record, column_factor, row_factor)
                if _fits_as_expected(case):
                    font_id = {"游ゴシック": "yu-gothic", "ＭＳ 明朝": "ms-mincho"}[record["font"]]  # measured fonts
                    cases[f"{kind}-{record['pixels']}px-{record['scale']}-percent-{font_id}"] = case
                    break
            else:
                raise ValueError(f"no {kind} record from {lowest} % gives a case print_fit can return")
    return cases


FIT_CASES.update(_worst_measured_cases(json.loads(PRINT_PITCH.read_text(encoding="utf-8"))["records"]))


@pytest.mark.parametrize("case", FIT_CASES, ids=list(FIT_CASES))
def test_fit_scale_prints_each_manual_page_on_one_sheet_without_much_spare(tmp_path, case, record_property):
    """Each page fits on its sheet at the fitted scale and no longer does 5 % (10 % below 55 %) larger."""
    pymupdf = pytest.importorskip("pymupdf")
    columns, width, rows_per_page, height, pages, paper, orientation, margins, font, limited_by, expected = (
        FIT_CASES[case])
    rows = rows_per_page * pages
    breaks = tuple(range(rows_per_page, rows, rows_per_page))
    # The mark sits four columns from the right edge so that its text fits inside the print area.
    marks = tuple(CellValue(row - 1, max(0, columns - 4), f"P{page}")
                  for page, row in enumerate((*breaks, rows), start=1))
    sheet = Sheet("S", (width,) * columns, (height,) * rows, cells=marks, row_breaks=breaks,
                  page=PageSetup(paper=paper, orientation=orientation, margins=margins))
    fit = print_fit(sheet, font)
    assert (fit.scale, fit.limited_by) == (expected, limited_by)
    # Below 55 % Excel's column factor moves between 0.99 and 1.067 from one scale to the next
    # (print_pitch.json), so the 1.08 band may leave up to 10 % unused; elsewhere at most 5 %.
    spare = 1.10 if fit.column_factor == 1.08 else 1.05
    larger = math.ceil(fit.scale * spare)
    books = []
    for name, value in (("fit", fit.scale), ("larger", larger)):
        path = tmp_path / f"{name}.xlsx"
        scaled = dataclasses.replace(sheet, page=dataclasses.replace(sheet.page, scale=value))
        save_workbook(Workbook((scaled,), default_font=font), path)
        books.append({"path": str(path), "pdf": str(tmp_path / f"{name}.pdf")})
    printer = _run_excel(tmp_path, _EXPORT_PDF, {"books": books}, timeout=240)["printer"]
    record_property("printer", printer)
    if not printer.startswith(MEASURED_PRINTERS):
        message = f"the print factors were not measured with the active printer {printer}"
        if _REQUIRED:
            pytest.fail(message)
        pytest.xfail(message)
    if case in DOCUWORKS_PDF_CASES and not printer.startswith("DocuWorks PDF on "):
        pytest.skip(f"DocuWorks PDF's worst conditions only test anything with that printer, not {printer}")
    with pymupdf.open(books[0]["pdf"]) as document:
        assert len(document) == pages, f"scale {fit.scale} % with {printer}"
        assert [f"P{page}" in document[page - 1].get_text() for page in range(1, pages + 1)] == [True] * pages
    if limited_by != "maximum":  # at the maximum the pages are allowed to have room left
        with pymupdf.open(books[1]["pdf"]) as document:
            assert len(document) > pages, f"{larger} % still fits with {printer}: {fit.scale} % leaves too much unused"


def test_reference_grid_prints_on_the_a4_pdf_grid_at_100_percent_with_yu_gothic(tmp_path, record_property):
    """With 游ゴシック 11 as the Normal font, 21 px cells print at A4.pdf's 16.08 x 15.48 pt pitch."""
    pymupdf = pytest.importorskip("pymupdf")
    borders = (tuple(EdgeBorder(0, col, "left", "hair") for col in range(30))
               + tuple(EdgeBorder(row, 0, "top", "hair") for row in range(47)))
    sheet = Sheet("S", (16.08,) * 30, (15.48,) * 47, borders=borders, page=PageSetup(margins=A4_GRID))
    assert print_fit(sheet, GOTHIC).scale == 100
    path, pdf = tmp_path / "grid.xlsx", tmp_path / "grid.pdf"
    save_workbook(Workbook((sheet,), default_font=GOTHIC), path)
    printer = _run_excel(tmp_path, _EXPORT_PDF, {"books": [{"path": str(path), "pdf": str(pdf)}]})["printer"]
    record_property("printer", printer)
    if not printer.startswith(MEASURED_PRINTERS):
        message = f"printing was not measured with the active printer {printer}"
        if _REQUIRED:
            pytest.fail(message)
        pytest.xfail(message)
    with pymupdf.open(pdf) as document:
        assert len(document) == 1
        xs, ys = [], []
        for drawing in document[0].get_drawings():
            box = drawing["rect"]
            if box.height > 2 * box.width:
                xs.append(box.x0 + box.width / 2)
            elif box.width > 2 * box.height:
                ys.append(box.y0 + box.height / 2)

    def merged(values):
        groups = []
        for value in sorted(values):
            if groups and value - groups[-1][-1] < 3:
                groups[-1].append(value)
            else:
                groups.append([value])
        return [sum(group) / len(group) for group in groups]

    xs, ys = merged(xs), merged(ys)
    assert len(xs) == 30 and len(ys) == 47
    # The pitch is A4.pdf's grid; where the first border prints depends on the printer driver
    # (0.06 pt inside the margins with "DocuWorks PDF", 0.80 pt with "DocuWorks Printer").
    # Positions from the first border, so a drift over the page would show (measured: at most 0.12 pt,
    # one 1/600 inch printer dot, over 46 rows).
    assert [x - xs[0] for x in xs] == pytest.approx([k * 16.08 for k in range(30)], abs=0.25)
    assert [y - ys[0] for y in ys] == pytest.approx([k * 15.48 for k in range(47)], abs=0.25)
    assert 0 <= xs[0] - 50.88 <= 1.0 and 0 <= ys[0] - 54.598 <= 1.0


_TRY_OPEN = r"""
  $opened = @()
  foreach ($path in $params.paths) {
    try { $book = $xl.Workbooks.Open($path, 0, $true); $book.Close($false); $opened += [ordered]@{ opened = $true; message = "" } }
    catch { $opened += [ordered]@{ opened = $false; message = $_.Exception.Message } }
  }
  $opened
"""


def test_a_workbook_excel_would_have_to_repair_does_not_open(tmp_path):
    """The checks above rely on this: with alerts off, Open fails instead of repairing."""
    good = write_workbook(Workbook((Sheet("S", (W,), (H,), cells=(CellValue(0, 0, 1.0, number_format="0.0"),)),)))
    broken = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(good)) as source, zipfile.ZipFile(broken, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(b's="1"', b's="99"')  # a cell format that does not exist
            target.writestr(info, data)
    (tmp_path / "good.xlsx").write_bytes(good)
    (tmp_path / "broken.xlsx").write_bytes(broken.getvalue())
    opened = _run_excel(tmp_path, _TRY_OPEN, {"paths": [str(tmp_path / "good.xlsx"), str(tmp_path / "broken.xlsx")]})
    assert [item["opened"] for item in opened] == [True, False]
    # The broken one fails in Open itself (Excel's "cannot get the Open property" COM error), not on the path.
    assert "Open" in opened[1]["message"] and "broken.xlsx" not in opened[1]["message"]
