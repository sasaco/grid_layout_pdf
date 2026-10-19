"""Measure how wide Excel prints columns and rows compared with their screen size.

Writes one sheet per (Normal font, pixel size, scale) with the library's .xlsx
writer, exports each sheet to PDF through Excel COM (PowerShell, hidden Excel),
finds the thin cell borders in the PDF and stores the printed pitch per cell
next to Excel's screen size. The JSON output is the evidence for the print
factors in ``renderers/xlsx/_units.py``.

    uv run --locked --extra dev python -X utf8 scripts/xlsx_probe/measure_print_pitch.py \
        --out scripts/xlsx_probe/print_pitch.json
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pymupdf

from gridlayoutpdf.renderers.xlsx._model import EdgeBorder, Font, Margins, PageSetup, Sheet, Workbook
from gridlayoutpdf.renderers.xlsx._package import save_workbook

FONTS = (("游ゴシック", 11.0), ("ＭＳ 明朝", 10.5))
PIXELS = tuple(range(11, 31))  # every whole pixel from 11 to 30
# Every whole percent the fit helper can return (20-100).
SCALES = tuple(range(20, 101))
CELLS = 6
PAPER_WIDTH = 595.2756  # A4 portrait, pt

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$items = Get-Content -Raw -Encoding UTF8 -LiteralPath $args[0] | ConvertFrom-Json
Add-Type -Namespace PitchProbe -Name Native -MemberDefinition '[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr window, out uint process);'
$xl = New-Object -ComObject Excel.Application
try {
  $xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.ScreenUpdating = $false
  [uint32]$excelProcess = 0
  [void][PitchProbe.Native]::GetWindowThreadProcessId([System.IntPtr]$xl.Hwnd, [ref]$excelProcess)
  Set-Content -Encoding UTF8 -LiteralPath $args[1] -Value ($xl.Version + "|" + $xl.Build + "|" + $xl.ActivePrinter + "|" + $excelProcess)
  foreach ($item in $items) {
    $book = $xl.Workbooks.Open($item.path, 0, $true)
    for ($k = 1; $k -le $book.Worksheets.Count; $k++) {
      $book.Worksheets.Item($k).ExportAsFixedFormat(0, ($item.pdf -f $k))
    }
    $book.Close($false)
  }
} finally {
  foreach ($book in @($xl.Workbooks)) { $book.Close($false) }
  $xl.Quit()
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
}
"""


def _cluster(values: list[float], gap: float) -> list[float]:
    """Merge the edges of one border (thin borders may print as two rectangles)."""
    groups: list[list[float]] = []
    for value in sorted(values):
        if groups and value - groups[-1][-1] < gap:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(group) / len(group) for group in groups]


def _pitch(path: Path, expected: float) -> tuple[float, float, float]:
    """Return the mean printed column and row pitch and the page width of the first page.

    ``expected`` is the rough pitch in the PDF's units; border edges closer
    than a third of it are one border.
    """
    with pymupdf.open(path) as document:
        page = document[0]
        xs, ys = [], []
        for drawing in page.get_drawings():
            box = drawing["rect"]
            if box.height > 2 * box.width:
                xs.append(box.x0 + box.width / 2)
            elif box.width > 2 * box.height:
                ys.append(box.y0 + box.height / 2)
        xs, ys = _cluster(xs, expected / 3), _cluster(ys, expected / 3)
        if len(xs) != CELLS or len(ys) != CELLS:
            raise RuntimeError(f"{path.name}: found {len(xs)} columns and {len(ys)} rows of borders")
        return (xs[-1] - xs[0]) / (CELLS - 1), (ys[-1] - ys[0]) / (CELLS - 1), page.rect.width


def _excel_running(process: int) -> bool:
    completed = subprocess.run(["tasklist", "/FI", f"PID eq {process}", "/FI", "IMAGENAME eq EXCEL.EXE",
                                "/FO", "CSV", "/NH"], capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(f"tasklist failed with exit code {completed.returncode}")
    return f'"{process}"' in completed.stdout.decode("ascii", "replace")


def _stop_excel(process: int) -> None:
    """Wait for the Excel this script started to quit; stop it (only if it is EXCEL.EXE) after 20 s."""
    if process <= 0:
        raise RuntimeError("the Excel process ID could not be read; check that no hidden Excel is left")
    deadline = time.monotonic() + 20
    while _excel_running(process) and time.monotonic() < deadline:
        time.sleep(0.5)
    if _excel_running(process):
        killed = subprocess.run(["taskkill", "/PID", str(process), "/T", "/F"], capture_output=True)
        if killed.returncode != 0:
            raise RuntimeError(f"Excel (PID {process}) did not quit and could not be stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true",
                        help="replace an existing output measured with the same printer "
                             "(another printer's data is kept and the new data goes to a dated file)")
    arguments = parser.parse_args()
    if arguments.out.exists() and not arguments.force:
        parser.error(f"{arguments.out} exists; measured data is evidence, pass --force to replace it")
    if not arguments.out.parent.is_dir():
        parser.error(f"the folder of {arguments.out} does not exist")
    # A PDF still held open (indexer, antivirus) must not lose the measured data when the folder is removed.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        items, keys = [], []
        for font_index, (name, size) in enumerate(FONTS):
            sheets = []
            for pixels in PIXELS:
                for scale in SCALES:
                    length = pixels * 0.75
                    borders = tuple(EdgeBorder(0, col, "left", "thin") for col in range(CELLS)) + tuple(
                        EdgeBorder(row, 0, "top", "thin") for row in range(CELLS))
                    sheets.append(Sheet(f"p{pixels}s{scale}", (length,) * CELLS, (length,) * CELLS, borders=borders,
                                        page=PageSetup(scale=scale, margins=Margins(10, 10, 10, 10, 0, 0))))
                    keys.append((name, size, pixels, scale, len(sheets)))
            path = directory / f"font{font_index}.xlsx"
            save_workbook(Workbook(tuple(sheets), default_font=Font(name, size)), path)
            items.append({"path": str(path), "pdf": str(directory / f"font{font_index}_{{0}}.pdf")})
        params = directory / "items.json"
        params.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        script = directory / "export.ps1"
        script.write_text(SCRIPT, encoding="utf-8-sig")
        environment = directory / "environment.txt"
        stop_error = None
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                            str(script), str(params), str(environment)], check=True, timeout=3 * 3600)
        finally:
            if environment.exists():  # stop the hidden Excel if it is still running
                try:
                    _stop_excel(int(environment.read_text(encoding="utf-8-sig").strip().split("|")[-1]))
                except RuntimeError as exc:  # reported after the data is saved
                    stop_error = exc
        version, build, printer, _ = environment.read_text(encoding="utf-8-sig").strip().split("|")
        records = []
        for name, size, pixels, scale, sheet_number in keys:
            font_index = [font for font, _ in FONTS].index(name)
            pdf = directory / f"font{font_index}_{sheet_number}.pdf"
            with pymupdf.open(pdf) as document:
                enlarged = document[0].rect.width / PAPER_WIDTH
            # Depending on the printer driver, Excel's PDF either keeps the content at 100 % and
            # enlarges the page by about 100 / scale, or keeps the page and scales the content.
            # The page is the paper (content scaled) or the paper enlarged by 100 / scale; take the nearer.
            candidate = min((1.0, 100 / scale), key=lambda value: abs(enlarged / value - 1))
            if abs(enlarged / candidate - 1) > 0.002:
                raise RuntimeError(f"the PDF page of {name} {pixels} px {scale} % has an unexpected size")
            enlarged = enlarged if candidate != 1.0 else 1.0
            screen = pixels * 0.75
            column, row, _ = _pitch(pdf, screen * scale / 100 * enlarged)
            on_paper = screen * scale / 100 * enlarged  # the screen size in the PDF's units
            records.append({
                "font": name, "size": size, "pixels": pixels, "scale": scale,
                "screen_pt": screen,
                "printed_column_pt": round(column, 4),
                "printed_row_pt": round(row, 4),
                "page_enlargement": round(enlarged, 4),
                "column_factor": round(column / on_paper, 4),
                "row_factor": round(row / on_paper, 4),
            })
        result = json.dumps({
            "measured": datetime.date.today().isoformat(),
            "excel": f"Excel {version} build {build}, ExportAsFixedFormat, active printer {printer}",
            "method": "6 x 6 cells with thin left/top borders; mean pitch of the border centres on page 1; "
                      "the PDF page is the paper (page_enlargement 1) or enlarged by about 100/scale; "
                      "factor = printed pitch / (screen size x scale/100 x page_enlargement)",
            "records": records,
        }, ensure_ascii=False, indent=1)
        code = _store(result, arguments.out, printer)  # inside the block: before the folder is removed
    if stop_error is not None:
        print(f"the data is saved, but {stop_error}", file=sys.stderr)
        code = code or KEPT_DATED
    raise SystemExit(code)


def printer_name(text) -> str:
    """The printer's name without its port ("... on Ne04:"), which may change between sessions."""
    if not isinstance(text, str):
        return ""
    return text.split("active printer ")[-1].rsplit(" on ", 1)[0]


KEPT_DATED = 3  # exit code: the new data is in a dated file and ``out`` was not replaced


def _store(result: str, out: Path, printer: str) -> int:
    """Save the measured data under a new dated name first, then replace ``out`` with it.

    Returns 0 when ``out`` holds the new data, and KEPT_DATED when it was
    kept (another printer's or unreadable data, or the replacement failed);
    the dated file stays then. The dated name is made unique by the system.
    """
    if not printer_name(printer):
        raise SystemExit("the active printer's name is empty; the data cannot be matched to a printer")
    prefix = f"{out.stem}.{datetime.datetime.now():%Y%m%d-%H%M%S}-"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=out.parent, prefix=prefix, suffix=out.suffix,
                                     delete=False) as stream:
        stream.write(result)
    dated = Path(stream.name)
    if out.exists():
        try:
            previous = json.loads(out.read_text(encoding="utf-8")).get("excel")
        except Exception:  # unreadable or unexpected JSON
            previous = None
        if not isinstance(previous, str) or printer_name(previous) != printer_name(printer):
            print(f"{out} holds another printer's or unreadable data ({previous!r}); the new data is {dated}",
                  file=sys.stderr)
            return KEPT_DATED
    try:
        os.replace(dated, out)
    except OSError as exc:
        print(f"could not replace {out} ({exc}); the new data is {dated}", file=sys.stderr)
        return KEPT_DATED
    return 0


if __name__ == "__main__":
    main()
