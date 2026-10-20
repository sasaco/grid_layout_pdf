"""FR-021: Excel shows the number cells of ``_numbers`` exactly as the text was written.

Workbooks of number cells are written with ``write_workbook`` and opened in a
hidden Excel through COM (PowerShell, no pywin32), with ``Visible=False`` and
``DisplayAlerts=False``; Excel always quits, and the test stops the Excel
process it started if it stays. ``Range.Text`` is compared with the source
text and with ``excel_display``, and ``Range.Value2`` must be the number.
The display depends on Excel's separators, so every run first checks that
they are ``.`` and ``,``. The printer settings are not read or changed.
Without Excel the Excel tests are skipped, or fail when
GRIDLAYOUTPDF_REQUIRE_EXCEL=1.
"""

import itertools
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from gridlayoutpdf.renderers.xlsx._model import CellRange, CellValue, Sheet, Workbook
from gridlayoutpdf.renderers.xlsx._numbers import (
    MAX_DECIMAL_PLACES,
    MAX_NUMBER_FORMATS,
    classify_number,
    excel_display,
)
from gridlayoutpdf.renderers.xlsx._package import write_workbook


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
_REQUIRE_SETTING = os.environ.get("GRIDLAYOUTPDF_REQUIRE_EXCEL", "")
if _REQUIRE_SETTING not in ("", "0", "1"):
    raise RuntimeError(f"GRIDLAYOUTPDF_REQUIRE_EXCEL must be 0 or 1, not {_REQUIRE_SETTING!r}")
needs_excel = pytest.mark.skipif(_MISSING is not None and _REQUIRE_SETTING != "1", reason=_MISSING or "")


@pytest.fixture
def excel():
    if _MISSING is not None:
        pytest.fail(f"GRIDLAYOUTPDF_REQUIRE_EXCEL=1 but {_MISSING}")


_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$cells = Get-Content -Raw -Encoding UTF8 -LiteralPath $args[3] | ConvertFrom-Json
Add-Type -Namespace XlsxNumbers -Name Native -MemberDefinition '[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr window, out uint process);'
$xl = New-Object -ComObject Excel.Application
$book = $null
try {
  [uint32]$excelProcess = 0
  [void][XlsxNumbers.Native]::GetWindowThreadProcessId([System.IntPtr]$xl.Hwnd, [ref]$excelProcess)
  Set-Content -Encoding ASCII -LiteralPath $args[2] -Value $excelProcess
  $xl.Visible = $false
  $xl.DisplayAlerts = $false
  $xl.ScreenUpdating = $false
  $separators = [ordered]@{ decimal = [string]$xl.International(3); thousands = [string]$xl.International(4);
                            system = [bool]$xl.UseSystemSeparators; excel_decimal = [string]$xl.DecimalSeparator;
                            excel_thousands = [string]$xl.ThousandsSeparator }
  $book = $xl.Workbooks.Open($args[0], 0, $true)
  $sheet = $book.Worksheets.Item(1)
  $read = @(foreach ($address in $cells) {
    $cell = $sheet.Cells.Item($address[0] + 1, $address[1] + 1)
    [ordered]@{ text = [string]$cell.Text; value = $cell.Value2; type = $cell.Value2.GetType().Name;
                format = [string]$cell.NumberFormat }
  })
  $result = [ordered]@{ separators = $separators; cells = $read }
  ConvertTo-Json -InputObject $result -Depth 5 -Compress | Set-Content -Encoding UTF8 -LiteralPath $args[1]
} finally {
  if ($null -ne $book) { $book.Close($false) }  # only the workbook this script opened
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


def _stop_excel(process_file: Path, *, wait: float = 20) -> str:
    """Wait for the Excel the script started to quit, stop it if it stays, and return what went wrong."""
    if not process_file.exists():
        return "\nthe Excel process ID was not written, so a remaining Excel cannot be stopped"
    try:
        process = int(process_file.read_text(encoding="ascii").strip())
    except ValueError:
        process = 0
    if process <= 0:
        return "\nthe Excel process ID could not be read, so a remaining Excel cannot be stopped"
    error = ""
    deadline = time.monotonic() + wait
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
    return error


def _read_cells(directory: Path, sheet: Sheet, addresses: list[tuple[int, int]], timeout: float = 300) -> list[dict]:
    """Open ``sheet`` in Excel and read Text, Value2 and NumberFormat of each 0-based (row, col)."""
    book, script, cells, outputs, process_file = (directory / name for name in (
        "numbers.xlsx", "numbers.ps1", "cells.json", "result.json", "excel.pid"))
    for stale in (outputs, process_file):
        stale.unlink(missing_ok=True)
    book.write_bytes(write_workbook(Workbook((sheet,))))
    script.write_text(_SCRIPT, encoding="utf-8-sig")
    cells.write_text(json.dumps([list(address) for address in addresses]), encoding="utf-8")
    error = ""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
             str(book), str(outputs), str(process_file), str(cells)], capture_output=True, timeout=timeout)
        if completed.returncode != 0:
            error = f"PowerShell exited with {completed.returncode}\n" + (
                completed.stderr + completed.stdout).decode("oem", "replace")  # PowerShell's console code page
    except subprocess.TimeoutExpired:
        error = f"the Excel COM check did not finish in {timeout} s"
    finally:  # also on KeyboardInterrupt: COM starts Excel outside PowerShell's process tree
        error += _stop_excel(process_file)
    assert not error, error
    result = json.loads(outputs.read_text(encoding="utf-8-sig"))
    separators = result["separators"]
    # FR-021's display matches only with these separators (the ja-JP default)
    assert (separators["decimal"], separators["thousands"]) == (".", ","), (
        f"Excel's separators are {separators}; number cells show the text unchanged only with . and ,")
    return result["cells"]


def _column(cells: list[CellValue], width_pt: float = 300.0) -> Sheet:
    return Sheet("数値", (width_pt,), (15.0,) * len(cells), tuple(cells))


def _check_numbers(directory: Path, texts: list[str]) -> None:
    numbers = [classify_number(text) for text in texts]
    assert all(number is not None for number in numbers), [t for t, n in zip(texts, numbers) if n is None]
    cells = [CellValue(row, 0, number.value, number_format=number.number_format, h_align="right")
             for row, number in enumerate(numbers)]
    read = _read_cells(directory, _column(cells), [(row, 0) for row in range(len(cells))])
    assert [cell["text"] for cell in read] == texts
    assert [cell["type"] for cell in read] == ["Double"] * len(texts)
    assert [cell["value"] for cell in read] == [number.value for number in numbers]
    assert [cell["format"] for cell in read] == [number.number_format for number in numbers]


MINUS = chr(0x2212)
TEXTS = [
    # the examples confirmed with the user
    "7.381125", "1,234.5", MINUS + "2.000", "12", "+2.50",
    # zero, signs and separators
    "0", "0.0", "+0", "+0.000", "0.5", "-0.5", MINUS + "0.5", "-2.000", "1,234", "12,345,678",
    "1,234,567.891", "-1,234", MINUS + "1,234.50", "+1,234.50",
    # values that are not exact in binary
    "0.1", "0.3", "2.675", "1.005", "-0.7", "99999999999999.9",
    # 15 digits, the largest integer part and the most places
    "999999999999999", MINUS + "999,999,999,999,999", "0.123456789012345", "123456789012.345",
    "-0.000123456789012345", "0.00000123456789012345", "1." + "0" * 20, "0." + "0" * 19 + "1",
    "0." + "0" * 20, MINUS + "1,234." + "0" * 20, "+1,234." + "0" * 20, "-999,999,999,999,999." + "0" * 20,
]


@needs_excel
def test_excel_shows_number_cells_as_written(tmp_path, excel):
    _check_numbers(tmp_path, TEXTS)


@needs_excel
def test_excel_opens_every_format_in_one_workbook(tmp_path, excel):
    """All 168 formats of ``_numbers`` (164 custom) fit in one workbook, small and largest integer parts."""
    texts = []
    signs, separators, places_range = ("", "+", "-", MINUS), (False, True), range(MAX_DECIMAL_PLACES + 1)
    for sign, thousands, places in itertools.product(signs, separators, places_range):
        fraction = "." + "0" * places if places else ""
        texts.append(sign + ("1,234" if thousands else "1") + fraction)
        texts.append(sign + ("999,999,999,999,999" if thousands else "999999999999999") + fraction)
    assert len({classify_number(text).number_format for text in texts}) == MAX_NUMBER_FORMATS == 168
    _check_numbers(tmp_path, texts)


# Formats and values outside what classify_number gives: rounding and a single section's minus.
DISPLAY_CASES = (
    (-2.0, "0.000"), (-2.0, '"+"0.00'), (-2.0, '"+"0.00;"-"0.00'), (2.5, "0"), (0.5, "0"), (-0.5, '0;"' + MINUS + '"0'),
    (1.25, "0.0"), (-1.25, "0.0"), (2.675, "0.00"), (0.1234567890123456, "0." + "0" * 16),
    (123456789012345678.0, "0"), (1234567.25, "#,##0.00"), (-1234.5, "#,##0.0"), (0.0, '0.0;"-"0.0'),
    (1e-30, "0." + "0" * 30), (1.0, "0." + "0" * 20),
    # 15 significant digits: the nearest, an exact half toward zero
    (100000000000000.5, "0"), (100000000000001.5, "0"), (-100000000000000.5, "0"), (1000000000000002.5, "0"),
    (10000000000000.25, "0.0"), (12345678901234.25, "0.0"), (7462911.561158455, "0.000000000"),
    (0.30000000000000004, "0." + "0" * 16), (1.0000000000000002, "0." + "0" * 16), (0.1, "0." + "0" * 19),
    # rounding the exact value or a 17-digit decimal differs here (1.00000000000009 or ...08)
    (1.000000000000085, "0." + "0" * 14), (-1.000000000000095, "0." + "0" * 14),
    (1.000000000000105, "0." + "0" * 14), (1.000000000000115, "0." + "0" * 14),
)


@needs_excel
def test_excel_display_models_excel(tmp_path, excel):
    cells = [CellValue(row, 0, value, number_format=number_format)
             for row, (value, number_format) in enumerate(DISPLAY_CASES)]
    read = _read_cells(tmp_path, _column(cells, 400.0), [(row, 0) for row in range(len(cells))])
    assert [cell["text"] for cell in read] == [excel_display(value, number_format)
                                               for value, number_format in DISPLAY_CASES]


GRID_PT = 14.17  # a 5 mm grid cell


@needs_excel
def test_number_cells_need_the_width_of_their_text(tmp_path, excel):
    """A number in grid cells merged to its text's width shows as written; in one grid cell it is ``###``.

    This is the condition FR-021's mapping must keep (``_numbers`` cannot see widths): text that does
    not fit runs over or is cut, but a number that does not fit is shown as ``#`` only.
    """
    number = classify_number("1,234,567.891")
    cells = (
        CellValue(0, 0, number.value, number_format=number.number_format, h_align="right"),
        CellValue(1, 0, number.value, number_format=number.number_format, h_align="right"),
        CellValue(2, 0, "1,234,567.891"),
    )
    sheet = Sheet("数値", (GRID_PT,) * 8, (15.0,) * 3, cells, merges=(CellRange(0, 0, 0, 7),))
    wide, narrow, text = _read_cells(tmp_path, sheet, [(0, 0), (1, 0), (2, 0)])
    assert wide["text"] == "1,234,567.891"
    assert narrow["text"] and set(narrow["text"]) == {"#"}
    assert text["text"] == "1,234,567.891"


@needs_excel
def test_turned_number_cells_need_the_height_of_their_text(tmp_path, excel):
    """Turned 90 or 270 degrees, a number needs its text's length in height: merged rows show it, one row is ``#``."""
    number = classify_number("1,234,567.891")
    cells = (
        CellValue(0, 0, number.value, number_format=number.number_format, rotation=90),
        CellValue(0, 1, number.value, number_format=number.number_format, rotation=90),
        CellValue(0, 2, "1,234,567.891", rotation=90),
        CellValue(0, 3, number.value, number_format=number.number_format, rotation=270),
    )
    sheet = Sheet("数値", (GRID_PT,) * 4, (GRID_PT,) * 8, cells,
                  merges=(CellRange(0, 0, 7, 0), CellRange(0, 3, 7, 3)))
    upward, narrow, text, downward = _read_cells(tmp_path, sheet, [(0, 0), (0, 1), (0, 2), (0, 3)])
    assert upward["text"] == downward["text"] == text["text"] == "1,234,567.891"
    assert narrow["text"] and set(narrow["text"]) == {"#"}


def _fake_excel(monkeypatch, states, taskkill_exit=0):
    """Replace tasklist with ``states`` (True: Excel still runs; the last one repeats) and record taskkill."""
    calls, remaining = [], list(states)

    def running(process):
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    def run(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, taskkill_exit)

    monkeypatch.setattr(sys.modules[__name__], "_running", running)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return calls


def test_stop_excel_waits_for_excel_to_quit(tmp_path, monkeypatch):
    process_file = tmp_path / "excel.pid"
    process_file.write_text("4242", encoding="ascii")
    calls = _fake_excel(monkeypatch, [True, True, False])
    assert _stop_excel(process_file) == ""
    assert calls == []


def test_stop_excel_reports_an_excel_it_could_not_stop(tmp_path, monkeypatch):
    process_file = tmp_path / "excel.pid"
    process_file.write_text("4242", encoding="ascii")
    calls = _fake_excel(monkeypatch, [True], taskkill_exit=128)
    error = _stop_excel(process_file, wait=0)
    assert calls == [["taskkill", "/PID", "4242", "/T", "/F"]]
    assert "could not be stopped (exit 128)" in error


def test_read_cells_reports_a_silent_powershell_failure(tmp_path, monkeypatch):
    def run(arguments, **kwargs):
        (tmp_path / "result.json").write_text('{"separators": {}, "cells": []}', encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 1, b"", b"")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(sys.modules[__name__], "_stop_excel", lambda process_file: "")
    with pytest.raises(AssertionError, match="PowerShell exited with 1"):
        _read_cells(tmp_path, _column([CellValue(0, 0, 1.0)]), [(0, 0)])


def test_read_cells_stops_excel_when_interrupted(tmp_path, monkeypatch):
    stopped = []

    def run(arguments, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(sys.modules[__name__], "_stop_excel", lambda process_file: stopped.append(process_file) or "")
    with pytest.raises(KeyboardInterrupt):
        _read_cells(tmp_path, _column([CellValue(0, 0, 1.0)]), [(0, 0)])
    assert stopped == [tmp_path / "excel.pid"]


# _stop_excel needs no Excel: tasklist and taskkill are replaced.
def test_stop_excel_stops_excel_when_tasklist_fails(tmp_path, monkeypatch):
    process_file = tmp_path / "excel.pid"
    process_file.write_text("4242", encoding="ascii")
    calls = []

    def failing_tasklist(process):
        raise RuntimeError("tasklist failed with exit code 1")

    def run(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(sys.modules[__name__], "_running", failing_tasklist)
    monkeypatch.setattr(subprocess, "run", run)
    error = _stop_excel(process_file, wait=0)
    assert calls == [["taskkill", "/PID", "4242", "/T", "/F"]]
    assert "tasklist failed" in error and "was stopped" in error


@pytest.mark.parametrize("content", [None, "", "x", "0"])
def test_stop_excel_reports_a_missing_process_id(tmp_path, content):
    process_file = tmp_path / "excel.pid"
    if content is not None:
        process_file.write_text(content, encoding="ascii")
    assert "cannot be stopped" in _stop_excel(process_file)
