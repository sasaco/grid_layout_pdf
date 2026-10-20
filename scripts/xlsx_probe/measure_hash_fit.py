"""Do numbers that the grid term rule fits in k columns show as #### in Excel?

For k = 1..8 merged columns of the A4 grid (16.08 pt -> 21 px) a right-aligned
number cell in ＭＳ 明朝 10 pt (half-width characters 5 pt) shows n characters via
its number format "0.000..."; n_max(k) = floor((k * 16.08 - 2 * 2.4) / 5) is the
most the library's rule puts in k columns. Excel's Range.Text (screen layout)
and the text of the exported PDF tell whether Excel drew the digits or #.

    uv run --locked --extra dev python -X utf8 <this script> --out <json>
"""

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path

import pymupdf

from gridlayoutpdf.renderers.xlsx._model import CellRange, CellValue, Font, Margins, PageSetup, Sheet, Workbook
from gridlayoutpdf.renderers.xlsx._package import save_workbook

PITCH = 16.08
PAD = 2.4
NORMAL_FONTS = (("游ゴシック", 11.0), ("ＭＳ 明朝", 10.5))
KS = tuple(range(1, 9))

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$items = Get-Content -Raw -Encoding UTF8 -LiteralPath $args[0] | ConvertFrom-Json
$xl = New-Object -ComObject Excel.Application
$out = @()
try {
  $xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.ScreenUpdating = $false
  $out += ("printer|" + $xl.ActivePrinter)
  foreach ($item in $items) {
    $book = $xl.Workbooks.Open($item.path, 0, $true)
    $sheet = $book.Worksheets.Item(1)
    foreach ($cell in $item.cells) {
      $out += ("text|" + $item.path + "|" + $cell.row + "|" + $sheet.Cells.Item($cell.row + 1, 1).Text)
    }
    $sheet.ExportAsFixedFormat(0, $item.pdf)
    $book.Close($false)
  }
} finally {
  foreach ($book in @($xl.Workbooks)) { $book.Close($false) }
  $xl.Quit()
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
}
Set-Content -Encoding UTF8 -LiteralPath $args[1] -Value $out
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        items, plan = [], []
        for index, (name, size) in enumerate(NORMAL_FONTS):
            cells, merges, keys = [], [], []
            row = 0
            for k in KS:
                n_max = math.floor((k * PITCH - 2 * PAD) / 5)
                for n in (n_max, n_max + 1, n_max + 2):
                    if n < 1:
                        continue
                    code = "0" if n == 1 else "0." + "0" * (n - 2)
                    cells.append(CellValue(row, 0, 0.0, number_format=code, font=Font("ＭＳ 明朝", 10.0),
                                           h_align="right"))
                    if k > 1:
                        merges.append(CellRange(row, 0, row, k - 1))
                    keys.append({"row": row, "k": k, "n": n, "n_max": n_max})
                    row += 1
            sheet = Sheet("s", (PITCH,) * 10, (15.48,) * row, cells=tuple(cells), merges=tuple(merges),
                          page=PageSetup(scale=100, margins=Margins(10, 10, 10, 10, 0, 0)))
            path = directory / f"n{index}.xlsx"
            save_workbook(Workbook((sheet,), default_font=Font(name, size)), path)
            pdf = directory / f"n{index}.pdf"
            items.append({"path": str(path), "pdf": str(pdf), "cells": keys})
            plan.append((name, size, path, pdf, keys))
        params = directory / "items.json"
        params.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        script = directory / "probe.ps1"
        script.write_text(SCRIPT, encoding="utf-8-sig")
        log = directory / "log.txt"
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                        str(script), str(params), str(log)], check=True, timeout=900)
        lines = log.read_text(encoding="utf-8-sig").splitlines()
        texts = {}
        for line in lines:
            parts = line.split("|")
            if parts[0] == "text":
                texts[(parts[1], int(parts[2]))] = parts[3]
        records = []
        for name, size, path, pdf, keys in plan:
            with pymupdf.open(pdf) as document:
                rows = []
                for page_number, page in enumerate(document):
                    found = []
                    for block in page.get_text("dict")["blocks"]:
                        for pdf_line in block.get("lines", ()):
                            found.append((round(pdf_line["bbox"][1], 1),
                                          "".join(span["text"] for span in pdf_line["spans"])))
                    rows.extend(text for _, text in sorted(found))
            for key, printed in zip(keys, rows + [None] * (len(keys) - len(rows))):
                records.append({"normal_font": name, "normal_size": size, **key,
                                "screen_text": texts[(str(path), key["row"])], "pdf_text": printed})
        arguments.out.write_text(json.dumps({"environment": [l for l in lines if l.startswith("printer|")],
                                             "records": records}, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        for record in records:
            print(record["normal_font"], record["k"], record["n"], record["n_max"],
                  "screen", record["screen_text"][:3] + ("…" if len(record["screen_text"]) > 3 else ""),
                  "#" in record["screen_text"], "pdf", (record["pdf_text"] or "")[:3], "#" in (record["pdf_text"] or ""))


if __name__ == "__main__":
    main()
