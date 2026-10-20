"""Measure Excel's left/right inner padding of a cell's text in its PDF export and on screen.

Run from the repository root:
    uv run --locked --extra dev python -X utf8 <this script> --out <json>

For each (Normal font, column pixels, text font, alignment, text) a merged
range of 3 columns gets the text and thin borders at its left and right edge.
Excel exports each sheet to PDF at 100 %. PyMuPDF finds the borders (vertical
drawings) and the characters (rawdict): left gap = first char x0 - left border
centre, right gap = right border centre - last char x1 (origin + advance),
centre offset = text middle - range middle. Gaps are also given in the
printed pixel (printed column pitch / column pixels).
Screen: AutoFit of a column holding n zero digits in the Normal font, its
Width (pt) in pixels minus n * MDW.
"""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import pymupdf

from gridlayoutpdf.renderers.xlsx._model import (
    CellRange, CellValue, EdgeBorder, Font, Margins, PageSetup, Sheet, Workbook,
)
from gridlayoutpdf.renderers.xlsx._package import save_workbook

NORMAL_FONTS = (("游ゴシック", 11.0), ("ＭＳ 明朝", 10.5))
PIXELS = (21, 30)
TEXT_FONTS = (("ＭＳ 明朝", 10.0), ("ＭＳ 明朝", 12.0), ("游明朝", 10.0), ("ＭＳ ゴシック", 10.0),
              ("IPAex明朝", 10.0))
ALIGNS = ("left", "right", "center")
TEXTS = ("12.50", "0.000", "kN", "断面")
COLUMNS = 6
SPAN = (1, 3)  # merged columns B:D

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$items = Get-Content -Raw -Encoding UTF8 -LiteralPath $args[0] | ConvertFrom-Json
$xl = New-Object -ComObject Excel.Application
$out = @()
try {
  $xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.ScreenUpdating = $false
  $out += ("printer|" + $xl.ActivePrinter + "|" + $xl.Version + "|" + $xl.Build)
  foreach ($item in $items) {
    $book = $xl.Workbooks.Open($item.path, 0, $false)
    for ($k = 1; $k -le $book.Worksheets.Count; $k++) {
      $book.Worksheets.Item($k).ExportAsFixedFormat(0, ($item.pdf -f $k))
    }
    $sheet = $book.Worksheets.Item(1)
    for ($n = 1; $n -le 12; $n++) {
      $sheet.Cells.Item(80, $n).NumberFormat = "@"
      $sheet.Cells.Item(80, $n).Value2 = ("0" * $n)
      [void]$sheet.Columns.Item($n).AutoFit()
      $out += ("autofit|" + $item.path + "|" + $n + "|" + $sheet.Columns.Item($n).Width)
    }
    $book.Close($false)
  }
} finally {
  foreach ($book in @($xl.Workbooks)) { $book.Close($false) }
  $xl.Quit()
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
}
Set-Content -Encoding UTF8 -LiteralPath $args[1] -Value $out
"""


def _sheet(name, pixels):
    width = pixels * 0.75
    cells, merges, borders, keys = [], [], [], []
    row = 0
    for font_name, size in TEXT_FONTS:
        for align in ALIGNS:
            for text in TEXTS:
                row += 1
                cells.append(CellValue(row, SPAN[0], text, font=Font(font_name, size), h_align=align))
                merges.append(CellRange(row, SPAN[0], row, SPAN[1]))
                borders.append(EdgeBorder(row, SPAN[0], "left", "thin"))
                borders.append(EdgeBorder(row, SPAN[1] + 1, "left", "thin"))
                keys.append((row, font_name, size, align, text))
    rows = row + 2
    sheet = Sheet(name, (width,) * COLUMNS, (18.0,) * max(rows, 61), cells=tuple(cells), merges=tuple(merges),
                  borders=tuple(borders), page=PageSetup(scale=100, margins=Margins(10, 10, 10, 10, 0, 0)))
    return sheet, keys


def _measure(pdf: Path, keys, pixels):
    rows = []
    with pymupdf.open(pdf) as document:
        for page_number, page in enumerate(document):
            verticals = []
            for drawing in page.get_drawings():
                box = drawing["rect"]
                if box.height > 2 * box.width:
                    verticals.append((box.x0 + box.width / 2, box.y0, box.y1, box.width))
            chars = []
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", ()):
                    for span in line["spans"]:
                        for char in span["chars"]:
                            chars.append((char["bbox"], char["origin"], char["c"], span["font"], span["size"]))
            page_rows = []
            for item in sorted(chars, key=lambda item: (round(item[1][1], 1), item[0][0])):
                y = item[1][1]
                if page_rows and abs(page_rows[-1][0] - y) < 3:
                    page_rows[-1][1].append(item)
                else:
                    page_rows.append([y, [item], verticals])
            rows.extend(page_rows)
    results = []
    if len(rows) != len(keys):
        raise RuntimeError(f"{pdf.name}: {len(rows)} text rows for {len(keys)} cells")
    pitches = []
    for (y, glyphs, verticals), (row, font_name, size, align, text) in zip(rows, keys):
        near = sorted({round(x, 3) for x, y0, y1, _ in verticals if y0 - 1 <= y <= y1 + 1})
        merged = []
        for x in near:
            if merged and x - merged[-1][-1] < 1.0:
                merged[-1].append(x)
            else:
                merged.append([x])
        near = [sum(group) / len(group) for group in merged]
        if len(near) != 2:
            raise RuntimeError(f"{pdf.name} row {row}: borders {near}")
        left, right = near
        glyphs.sort(key=lambda item: item[0][0])
        x0 = glyphs[0][0][0]
        x1 = glyphs[-1][0][2]
        printed_px = (right - left) / ((SPAN[1] - SPAN[0] + 1) * pixels)
        pitches.append(printed_px)
        results.append({
            "font": font_name, "size": size, "align": align, "text": text,
            "pdf_text": "".join(g[2] for g in glyphs), "pdf_font": glyphs[0][3], "pdf_size": round(glyphs[0][4], 3),
            "left_border": round(left, 3), "right_border": round(right, 3),
            "text_x0": round(x0, 3), "text_x1": round(x1, 3),
            "left_gap_pt": round(x0 - left, 3), "right_gap_pt": round(right - x1, 3),
            "centre_offset_pt": round((x0 + x1) / 2 - (left + right) / 2, 3),
            "printed_pt_per_px": round(printed_px, 5),
        })
    return results, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        items, plan = [], []
        for index, (name, size) in enumerate(NORMAL_FONTS):
            sheets = []
            for pixels in PIXELS:
                sheet, keys = _sheet(f"p{pixels}", pixels)
                sheets.append(sheet)
                plan.append((index, name, size, pixels, len(sheets), keys))
            path = directory / f"normal{index}.xlsx"
            save_workbook(Workbook(tuple(sheets), default_font=Font(name, size)), path)
            items.append({"path": str(path), "pdf": str(directory / f"normal{index}_{{0}}.pdf")})
        params = directory / "items.json"
        params.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        script = directory / "export.ps1"
        script.write_text(SCRIPT, encoding="utf-8-sig")
        log = directory / "log.txt"
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                        str(script), str(params), str(log)], check=True, timeout=1800)
        lines = log.read_text(encoding="utf-8-sig").splitlines()
        records = []
        for index, name, size, pixels, number, keys in plan:
            pdf = directory / f"normal{index}_{number}.pdf"
            results, _ = _measure(pdf, keys, pixels)
            for result in results:
                records.append({"normal_font": name, "normal_size": size, "pixels": pixels, **result})
        autofit = []
        for line in lines:
            parts = line.split("|")
            if parts[0] == "autofit":
                index = [item["path"] for item in items].index(parts[1])
                autofit.append({"normal_font": NORMAL_FONTS[index][0], "normal_size": NORMAL_FONTS[index][1],
                                "digits": int(parts[2]), "width_pt": float(parts[3]),
                                "width_px": round(float(parts[3]) / 0.75, 3)})
        result = {"environment": [line for line in lines if line.startswith("printer|")],
                  "records": records, "autofit": autofit}
        arguments.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
