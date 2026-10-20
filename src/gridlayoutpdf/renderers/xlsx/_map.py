"""FR-021: map tagged ``ScenePage`` sequences to the grid Excel sheet model.

One grid cell of a page is one sheet cell. A report (a name and its pages) is
one sheet; where the paper, the grid or the page decorations (the header and
footer's template, alignment, font or position) change, the next sheet
begins (``name``, ``name_2``, ``name_3`` ...), and pages follow each other
down the sheet with a manual page break between them. Everything is decided
from the commands' semantic tags and the page metadata (``semantics``), never
from where a line happens to lie:

* Cell sizes are whole Excel pixels, chosen cell by cell from the measured
  printed sizes (``PRINTED_COLUMN_PT``, ``PRINTED_ROW_PT``) so that every
  grid boundary prints as close to its PDF position as they allow, without
  building up an error over the page. Shapes keep their place inside their
  cell.
* Text pieces become cells. A piece is the text of one structure unit (a
  paragraph or cell line, an equation part or term, a fraction's numerator or
  denominator, a math block) on one row, split where a fraction of that unit
  lies between its atoms or atoms are half a cell or more apart. Atoms of
  one piece are joined left to right, with a space where the PDF leaves at
  least 0.08 em between them; scripts are superscript and subscript runs of
  the same cell's rich text at the base size. A piece fills the cell of its
  baseline row and every column its glyph ink touches (merged when more than
  one). A piece that lands on taken cells moves right (along the reading
  direction in turned tables) and the move is recorded; moving past the
  grid's edge is always an error.
* A grid term (``term_columns="grid"``) takes the whole columns its tag
  names, found from its ink, alignment and the cell padding it was laid out
  with; columns off the page's column boundaries, or another padding than
  ``cell_padding_pt``, are recorded.
* An equation's relation is centred on its anchor boundary in the PDF; its
  cell starts at that boundary (centred), so the left-hand side keeps the
  columns before it.
* A piece that is a plain number (``_numbers.classify_number``) is a number
  cell with a format that shows the PDF text when its cells are as wide as
  the text drawn in whole pixels (Excel's screen) plus the cell padding on
  both sides; otherwise it stays text and is recorded as "number_as_text".
* Fractions: the numerator and denominator are cells in consecutive rows (the
  denominator moves down, recorded, if both would share a row; inner
  fractions first), the bar is a shape on the boundary between them, and the
  other pieces of the same equation line are merged over the rows of the
  line and centred vertically (a label wrapped to several lines keeps each
  line in its own row). A fraction in a superscript or subscript cannot be
  rich text; it is written the same way and recorded.
* Only Table, Rule and SideRule lines (``semantics.BORDER_ROLES``) become cell
  borders, and only when they lie on cell boundaries from end to end; any
  other line, fraction bars and figures are shapes. A border that is off the
  boundaries, shorter than its cells or inside a merged piece becomes a
  shape and is recorded, and so is a border that loses its edge to another
  one it does not cover. At a page break the page above keeps its last
  row's bottom border and the page below its first row's top border.
* A QuarterTurn laid out on the page grid with its pitches swapped becomes
  turned cells; any other one becomes a group of shapes and is recorded.
* A Figure is one shape group (TextBox and TextDiamond are shapes with text,
  Label a frameless text box); an Image is a picture.
* Page decorations become the Excel header and footer: ``{page}`` is the page
  field counted from the sheet's first page number and ``{pages}`` the
  report's page count; a format specification is an error.

``strict=True`` raises ``XlsxStrictError`` when anything was moved or not
written the way its structure asks for (``XlsxResult.shifts`` and
``fallbacks``; numbers kept as text are not). Commands without a tag are
mapped like user commands and counted in the result.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from string import Formatter
from typing import Literal, NamedTuple

from PIL import Image as PILImage

from ...borders import BorderStyle
from ...bounds import command_bounds, transformed_text_bounds
from ...fonts import FontRegistry, default_fonts
from ...geometry import Rect as Box
from ...scene import Circle, Line, Polyline, RasterImage, Rectangle, ScenePage, Text
from ...semantics import BORDER_ROLES, Kind, Role, Scope
from ...validation import TOLERANCE
from . import _model as xl
from ._numbers import classify_number
from ._package import save_workbook
from ._units import (FULL_SCALE_PRINTED_PT, PIXELS_PER_PT, excel_column_width_pt, full_scale_size_pt,
                     page_heights_pt, print_fit)

# The workbook's Normal font: only Yu Gothic 11 prints 21 px cells at the A4.pdf grid pitch (Step 7).
DEFAULT_FONT = xl.Font("游ゴシック", 11)
# Printed pt of one 11-30 px column and row at 100 % with that Normal font, Step 7's measurement
# (scripts/xlsx_probe/print_pitch.json: Yu Gothic 11, scale 100, "DocuWorks Printer"; the mean pitch of
# 6 cells, _units.FULL_SCALE_PRINTED_PT). 21 px prints 16.08 x 15.48 pt, the A4.pdf grid pitch. Other sizes
# use the 21 px ratio.
PRINTED_COLUMN_PT, PRINTED_ROW_PT = FULL_SCALE_PRINTED_PT[(DEFAULT_FONT.name, DEFAULT_FONT.size)]
PRINT_COLUMN_PT_PER_PX = PRINTED_COLUMN_PT[21] / 21
PRINT_ROW_PT_PER_PX = PRINTED_ROW_PT[21] / 21
SCREEN_PT_PER_PX = 1 / PIXELS_PER_PT
_HUNDREDTH_GUARD = 1e-6  # in hundredths of a pt
SPACE_GAP_EM = 0.08  # the space threshold of a font without a space glyph width (half a space otherwise)
_CELL_EPSILON = 1e-6  # in cells: an extent ending this close to a boundary does not reach the next cell
_BASELINE_NUDGE_PT = 1e-4  # a baseline on a boundary belongs to the cell above it (the glyphs' side)
_PITCH_TOLERANCE = 1e-9
_TERM_EDGE_TOLERANCE_PT = 1e-6  # a grid term's columns start this close to a page column boundary
_PADDING_TOLERANCE = 1e-9
_FRAME_TOLERANCE_PT = 1e-4  # a table cell's frame lies this close to page cell boundaries
# Where Excel prints a top- and a bottom-aligned line's box inside its cell, pt from the cell's top or bottom,
# in a workbook with this module's DEFAULT_FONT as the Normal font (another Normal font moves them; measure again).
# Upright: measured in Excel 16.0 (MS Mincho 10.5 pt in 15.48 pt rows, "DocuWorks Printer"): 1.37-1.39 pt and
# 3.50 pt with the printer's origin included, 1.10-1.19 pt and 3.47-3.76 pt from the printed borders. Turned text:
# not measured, one pixel each way; a turned piece in one column, outside an equation and without a table
# cell's valign (a one-line cell on the grid takes its cell's valign) uses it.
EXCEL_TOP_INSET_PT, EXCEL_BOTTOM_INSET_PT = 1.38, 3.5
EXCEL_TURNED_INSET_PT = 0.75
# Top or bottom only when nearer than the middle by this much: near ties stay in the middle, where Excel cuts no
# glyph (a bottom-aligned 12 pt heading and right-aligned turned lines had glyphs cut at the cell's edge in Step
# 10's comparison).
CROSS_ALIGN_MARGIN_PT = 1.0
_EDGE_TOLERANCE_PT = 1e-6
SHIFT_REASONS = ("overlap", "fraction", "fraction_in_script")
FALLBACK_KINDS = ("quarter_turn", "border_off_grid", "border_in_merge", "border_conflict", "rotated_text",
                  "fraction_in_script", "term_off_grid", "cell_padding_mismatch", "print_scale", "number_as_text",
                  "text_clipped")
_NOTE_KINDS = ("number_as_text", "text_clipped")  # recorded beside the fallbacks; strict does not refuse them
_TURNED_ROTATION = {0: 0, 1: 90, 2: 180, 3: 270}
_UNIT_KINDS = frozenset({Kind.FRACTION, Kind.EQUATION_PART, Kind.PARAGRAPH, Kind.CELL_LINES,
                         Kind.TABLE_CELL, Kind.MATH_BLOCK, Kind.DECORATION})
_EQUATION_ALIGN = {"lhs": "right", "relation": "center", "result_relation": "center", "result": "right",
                   "unit": "left", "label": "left", "rhs": "left"}


class XlsxError(ValueError):
    """The pages cannot be written as a grid Excel workbook."""


class XlsxStrictError(XlsxError):
    """``strict=True`` and a piece was moved or a command was not written the way its structure asks for."""

    def __init__(self, message: str, shifts: tuple[XlsxShift, ...] = (),
                 fallbacks: tuple[XlsxFallback, ...] = ()) -> None:
        super().__init__(message)
        self.shifts = _records(shifts, "shifts", XlsxShift)
        self.fallbacks = _records(fallbacks, "fallbacks", XlsxFallback)
        if any(item.kind in _NOTE_KINDS for item in self.fallbacks):
            raise ValueError("number_as_text and text_clipped records are not what strict refuses")

    def __reduce__(self):
        return type(self), (str(self), self.shifts, self.fallbacks)


def cell_ref(row: int, col: int) -> str:
    """Return Excel's A1 reference of a 0-based cell."""
    _count(row, "row")
    _count(col, "col")
    letters, number = "", col + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row + 1}"


def _count(value, name: str, low: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ValueError(f"{name} must be an integer of at least {low}")
    return value


def _string(value, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _cell(value, name: str) -> tuple[int, int]:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        raise ValueError(f"{name} must be a (row, col) pair")
    cell = tuple(value)
    if len(cell) != 2:
        raise ValueError(f"{name} must be a (row, col) pair")
    return _count(cell[0], f"{name} row"), _count(cell[1], f"{name} col")


@dataclass(frozen=True, slots=True)
class XlsxSheet:
    """One sheet: its name, the report, the report's pages (1-based, inclusive) on it and its print scale."""

    name: str
    report: str
    first_page: int
    last_page: int
    rows: int
    columns: int
    scale: int = 100

    def __post_init__(self) -> None:
        _string(self.name, "name")
        _string(self.report, "report")
        _count(self.first_page, "first_page", 1)
        if _count(self.last_page, "last_page", 1) < self.first_page:
            raise ValueError("last_page must not be before first_page")
        _count(self.rows, "rows", 1)
        _count(self.columns, "columns", 1)
        if not 10 <= _count(self.scale, "scale", 10) <= 400:
            raise ValueError("scale must be an Excel print scale from 10 to 400 percent")


@dataclass(frozen=True, slots=True)
class XlsxShift:
    """A piece moved from the cell it would fill; cells are 0-based (row, col) of the sheet.

    ``reason`` is "overlap" (moved along the reading direction to free
    cells), "fraction" (a denominator moved below its numerator's row) or
    "fraction_in_script" (the same, for a fraction in a superscript or
    subscript).
    """

    sheet: str
    page: int
    text: str
    from_cell: tuple[int, int]
    to_cell: tuple[int, int]
    reason: str

    def __post_init__(self) -> None:
        _string(self.sheet, "sheet")
        _count(self.page, "page", 1)
        _string(self.text, "text")
        object.__setattr__(self, "from_cell", _cell(self.from_cell, "from_cell"))
        object.__setattr__(self, "to_cell", _cell(self.to_cell, "to_cell"))
        if self.from_cell == self.to_cell:
            raise ValueError("a shift must move its piece")
        if self.reason not in SHIFT_REASONS:
            raise ValueError(f"reason must be one of {', '.join(SHIFT_REASONS)}")

    @property
    def from_ref(self) -> str:
        return cell_ref(*self.from_cell)

    @property
    def to_ref(self) -> str:
        return cell_ref(*self.to_cell)


@dataclass(frozen=True, slots=True)
class XlsxFallback:
    """Commands not written the way their structure asks for.

    ``kind`` is one of ``FALLBACK_KINDS``: "quarter_turn" (a QuarterTurn not
    on the swapped page grid, written as shapes), "border_off_grid" (a
    border line off the cell boundaries or shorter than its cells, a shape),
    "border_in_merge" (a border line inside a merged piece, a shape),
    "border_conflict" (two borders of one cell edge where the kept one, the
    thicker or else the solid or else the first, does not cover the other),
    "rotated_text" (text turned upside down outside a figure, a shape),
    "fraction_in_script" (a fraction in a superscript or subscript, which
    rich text cannot hold, written as full-size numerator and denominator
    cells), "term_off_grid" (a grid term whose columns do not start on a
    page column boundary, placed by its ink), "cell_padding_mismatch" (a
    grid term laid out with another cell padding than ``cell_padding_pt``),
    "print_scale" (the sheet prints under 100 %, so its grid prints smaller
    than the PDF's); only in ``XlsxResult.numbers_as_text``,
    "number_as_text" (a number kept as text because Excel would show it as
    ###), and only in ``XlsxResult.texts_clipped``, "text_clipped" (text
    whose cells are narrower than Excel draws it, so its end may be cut).
    """

    sheet: str
    page: int
    kind: str
    detail: str

    def __post_init__(self) -> None:
        _string(self.sheet, "sheet")
        _count(self.page, "page", 1)
        if self.kind not in FALLBACK_KINDS:
            raise ValueError(f"kind must be one of {', '.join(FALLBACK_KINDS)}")
        _string(self.detail, "detail")


def _records(value, name: str, kind: type) -> tuple:
    if isinstance(value, (str, bytes, Mapping)) or not hasattr(value, "__iter__"):
        raise ValueError(f"{name} must be a sequence of {kind.__name__}")
    items = tuple(value)
    if not all(isinstance(item, kind) for item in items):
        raise ValueError(f"{name} must contain only {kind.__name__} items")
    return items


@dataclass(frozen=True, slots=True)
class XlsxResult:
    """What ``render_xlsx`` wrote and every compromise it made.

    ``shifts`` and ``fallbacks`` are what ``strict=True`` refuses.
    ``numbers_as_text`` lists numbers kept as text (kind "number_as_text") and
    ``texts_clipped`` text whose cells cannot hold it in Excel (kind
    "text_clipped"); strict refuses neither. A number kept as text is
    recorded in ``numbers_as_text`` only; whether Excel may cut it is in that
    record's detail ("may be cut").
    ``untagged`` counts the commands without a semantic tag by command type,
    as sorted (type name, count) pairs (``dict(result.untagged)`` gives a
    mapping); they are mapped like user commands. ``dropped`` lists shapes
    of no extent (a zero-length line), which draw nothing and are not
    written.
    """

    path: Path | None
    sheets: tuple[XlsxSheet, ...]
    shifts: tuple[XlsxShift, ...] = ()
    fallbacks: tuple[XlsxFallback, ...] = ()
    untagged: tuple[tuple[str, int], ...] = ()
    dropped: tuple[str, ...] = ()
    numbers_as_text: tuple[XlsxFallback, ...] = ()
    texts_clipped: tuple[XlsxFallback, ...] = ()

    def __post_init__(self) -> None:
        if self.path is not None and not isinstance(self.path, Path):
            raise ValueError("path must be a pathlib.Path or None")
        object.__setattr__(self, "sheets", _records(self.sheets, "sheets", XlsxSheet))
        object.__setattr__(self, "shifts", _records(self.shifts, "shifts", XlsxShift))
        object.__setattr__(self, "fallbacks", _records(self.fallbacks, "fallbacks", XlsxFallback))
        if any(item.kind in _NOTE_KINDS for item in self.fallbacks):
            raise ValueError("number_as_text and text_clipped records belong in their own lists")
        clipped = _records(self.texts_clipped, "texts_clipped", XlsxFallback)
        if any(item.kind != "text_clipped" for item in clipped):
            raise ValueError("texts_clipped must contain only text_clipped records")
        object.__setattr__(self, "texts_clipped", clipped)
        numbers = _records(self.numbers_as_text, "numbers_as_text", XlsxFallback)
        if any(item.kind != "number_as_text" for item in numbers):
            raise ValueError("numbers_as_text must contain only number_as_text records")
        object.__setattr__(self, "numbers_as_text", numbers)
        for name in ("untagged", "dropped"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
                raise ValueError(f"{name} must be a sequence, not {type(value).__name__}")
        pairs = tuple(self.untagged.items() if isinstance(self.untagged, Mapping) else self.untagged)
        if not all(isinstance(pair, tuple) and len(pair) == 2 for pair in pairs):
            raise ValueError("untagged must hold (command type, count) pairs")
        untagged = tuple(sorted((_string(name, "untagged type"), _count(count, "untagged count", 1))
                                for name, count in pairs))
        if len({name for name, _ in untagged}) != len(untagged):
            raise ValueError("untagged must name each command type once")
        object.__setattr__(self, "untagged", untagged)
        object.__setattr__(self, "dropped", tuple(_string(item, "dropped") for item in self.dropped))

    @property
    def untagged_count(self) -> int:
        return sum(count for _, count in self.untagged)


PaddingFunction = Callable[[float], float]


def render_xlsx(reports: Iterable[tuple[str, Iterable[ScenePage]]], path: str | os.PathLike[str],
                fonts: FontRegistry | None = None, *, strict: bool = False,
                cell_padding_pt: PaddingFunction | None = None) -> XlsxResult:
    """Write ``reports`` (``(sheet name, ScenePage sequence)`` pairs) as one grid Excel workbook.

    ``fonts`` measures the text as it was laid out (the shared default
    registry when omitted). ``cell_padding_pt`` returns Excel's inner cell
    padding on one side for a font size in pt; by default the library's
    measured ``equations.excel_cell_padding_pt``, the padding that
    ``term_columns="grid"`` lays out with. Nothing is written when an error
    is raised.
    """
    if fonts is None:
        fonts = default_fonts()
    workbook, result = map_reports(reports, fonts, strict=strict,
                                   cell_padding_pt=_library_padding() if cell_padding_pt is None else cell_padding_pt)
    destination = Path(path)
    save_workbook(workbook, destination)
    return replace(result, path=destination)


def _library_padding() -> PaddingFunction:
    from ... import equations  # read when called, so the library's value is the one in use

    return equations.excel_cell_padding_pt


def map_reports(reports, fonts: FontRegistry, *, strict: bool = False,
                cell_padding_pt: PaddingFunction) -> tuple[xl.Workbook, XlsxResult]:
    """Return the workbook model of ``reports`` and the record of the mapping (``path`` is None)."""
    if not isinstance(fonts, FontRegistry):
        raise ValueError("fonts must be a FontRegistry")
    if not isinstance(strict, bool):
        raise ValueError("strict must be a boolean")
    if not callable(cell_padding_pt):
        raise ValueError("cell_padding_pt must be a function of the font size")
    sheets, infos, shifts, fallbacks, dropped, numbers, clipped = [], [], [], [], [], [], []
    untagged: Counter[str] = Counter()
    for name, pages in _reports(reports):
        try:
            runs = _sheet_runs(pages)
        except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:  # a page built by hand
            raise XlsxError(f"report {name!r}: a page's decoration metadata is incomplete: {exc!r}") from exc
        for number, (start, stop) in enumerate(runs, start=1):
            sheet_name = name if number == 1 else f"{name}_{number}"
            try:
                xl.validate_sheet_name(sheet_name)
            except ValueError as exc:
                raise XlsxError(f"report {name!r}: {exc}") from None
            builder = _SheetBuilder(sheet_name, pages[start:stop], start + 1, len(pages), fonts, cell_padding_pt)
            try:
                sheet = builder.build()
            except (KeyError, IndexError, TypeError, AttributeError) as exc:  # metadata of a page built by hand
                raise XlsxError(f"sheet {sheet_name!r}: a page's metadata is incomplete or malformed: "
                                f"{exc!r}") from exc
            sheets.append(sheet)
            infos.append(XlsxSheet(sheet_name, name, start + 1, stop, builder.total_rows, builder.columns,
                                   sheet.page.scale))
            shifts.extend(builder.shifts)
            fallbacks.extend(builder.fallbacks)
            numbers.extend(builder.numbers_as_text)
            clipped.extend(builder.texts_clipped)
            dropped.extend(builder.dropped)
            untagged.update(builder.untagged)
    try:
        workbook = xl.Workbook(sheets, default_font=DEFAULT_FONT)
    except ValueError as exc:
        raise XlsxError(f"workbook: {exc}") from None
    result = XlsxResult(None, infos, shifts, fallbacks, untagged, dropped, numbers, clipped)
    if strict and (shifts or fallbacks):
        details = [f"{shift.sheet} page {shift.page}: {shift.text!r} {shift.from_ref} -> {shift.to_ref} ({shift.reason})"
                   for shift in result.shifts[:5]]
        details += [f"{item.sheet} page {item.page}: {item.kind} {item.detail}" for item in result.fallbacks[:5]]
        raise XlsxStrictError(f"strict grid Excel output: {len(shifts)} shift(s) and {len(fallbacks)} "
                              f"fallback(s): " + "; ".join(details), result.shifts, result.fallbacks)
    return workbook, result


def _reports(reports) -> list[tuple[str, tuple[ScenePage, ...]]]:
    if isinstance(reports, (str, bytes, Mapping)) or not hasattr(reports, "__iter__"):
        raise ValueError("reports must be a sequence of (sheet name, pages) pairs")
    result = []
    for item in reports:
        try:
            name, pages = item
        except (TypeError, ValueError):
            raise ValueError("each report must be a (sheet name, pages) pair") from None
        if not isinstance(name, str):
            raise ValueError("a report's sheet name must be a string")
        if isinstance(pages, (str, bytes, Mapping)) or not hasattr(pages, "__iter__"):
            raise ValueError(f"report {name!r}: pages must be a sequence of ScenePage")
        pages = tuple(pages)
        if not pages or not all(isinstance(page, ScenePage) for page in pages):
            raise ValueError(f"report {name!r}: pages must be a nonempty sequence of ScenePage")
        result.append((name, pages))
    if not result:
        raise ValueError("reports must contain at least one report")
    return result


def _sheet_runs(pages: tuple[ScenePage, ...]) -> list[tuple[int, int]]:
    """Split pages where the paper, the grid or the decorations change (a return to an earlier one too)."""
    runs, start = [], 0
    for index in range(1, len(pages) + 1):
        if index == len(pages) or _sheet_key(pages[index]) != _sheet_key(pages[start]):
            runs.append((start, index))
            start = index
    return runs


def _sheet_key(page: ScenePage) -> tuple:
    profile = page.profile
    return profile.width, profile.height, profile.grid, _decoration_key(page, "header"), \
        _decoration_key(page, "footer")


def _decoration_key(page: ScenePage, side: str) -> tuple | None:
    """What one page's header or footer writes: template, alignment, font and frame."""
    record = page.metadata.get("decorations", {}).get(side)
    if record is None:
        return None
    start, stop = record["commands"]
    text = next((command for command in page.commands[start:stop] if isinstance(command, Text)), None)
    font = None if text is None else (text.style.font, text.style.size)
    return record["template"], record["align"], font, record["y_pt"], record["height"]


def _half_step(size: float) -> float:
    """A scaled script size on Excel's nearest 0.5 pt step.

    Every size but a script's is on the steps already (FR-023). A cell's
    script runs take the base size instead; only text that has no base, in a
    shape or in a fraction inside a script (recorded as fraction_in_script),
    is rounded here.
    """
    return max(1.0, math.floor(size * 2 + 0.5) / 2)


def _font(style) -> xl.Font:
    return xl.Font(style.font, _half_step(style.size))


@dataclass(frozen=True, slots=True)
class _Axis:
    """One page's columns or rows: whole Excel pixels whose boundaries print where the PDF grid's do.

    Each cell takes the pixel count, next to the even share, whose measured
    printed size (``printed``, a 21 px ratio outside 11-30 px) brings the
    printed boundary closest to the PDF's, so the error does not build up
    over the page (the A4.pdf grid stays 21 px). ``printed_starts`` are those
    predicted printed boundaries; ``sizes`` and ``starts`` are the pixels in
    the model's pt (Excel's screen, 0.75 pt per pixel). ``at`` keeps a point
    at its fraction of its cell.
    """

    pitch: float
    sizes: tuple[float, ...]
    starts: tuple[float, ...]
    printed_starts: tuple[float, ...]

    @classmethod
    def build(cls, pitch: float, count: int, printed: Mapping[int, float], ratio: float, what: str) -> _Axis:
        def printed_size(pixels: int) -> float:
            return printed.get(pixels, pixels * ratio)

        pixels, printed_starts = [], [0.0]
        for boundary in range(1, count + 1):
            target, done = boundary * pitch, printed_starts[-1]
            share = math.floor((target - done) / ratio + 0.5)
            choice = min((size for size in (share - 1, share, share + 1) if size >= 1),
                         key=lambda size: (abs(done + printed_size(size) - target), abs(size - share)))
            pixels.append(choice)
            printed_starts.append(done + printed_size(choice))
            if abs(printed_starts[-1] - target) > pitch / 2:
                raise XlsxError(f"a grid {what} of {pitch:g} pt cannot print within half a cell of the PDF "
                                "in whole Excel pixels")
        starts = [0.0]
        for size in pixels:
            starts.append(starts[-1] + size * SCREEN_PT_PER_PX)
        return cls(pitch, tuple(size * SCREEN_PT_PER_PX for size in pixels), tuple(starts), tuple(printed_starts))

    @property
    def length(self) -> float:
        return self.starts[-1]

    def at(self, offset: float) -> float:
        """Map pt from the grid origin to the model's pt (outside the grid, the edge cell's scale)."""
        index = min(max(math.floor(offset / self.pitch), 0), len(self.sizes) - 1)
        return self.starts[index] + (offset - index * self.pitch) / self.pitch * self.sizes[index]


class _FractionKey(NamedTuple):
    """One fraction of a sheet: tag paths are unique within one placement of one page."""

    page: int
    place: tuple
    path: tuple[Scope, ...]  # the scopes down to the fraction's own, its part removed


@dataclass(slots=True)
class _Atom:
    """One Text command of a piece."""

    index: int
    command: Text
    vert: str | None
    lo: float  # advance extent along the reading direction, in its own direction (pt)
    hi: float
    ink: tuple[float, float] | None  # glyph ink along the reading direction, None for blank text


@dataclass(slots=True)
class _Piece:
    """One cell (or merged range) of text, in page-local cells until placed."""

    page: int  # index within the sheet
    turns: int  # the commands' quarter turns: 0, 1 or 3
    atoms: list[_Atom]
    unit_path: tuple[Scope, ...]
    line_key: tuple | None
    in_fraction: bool
    fractions: tuple[tuple[_FractionKey, str], ...]  # (fraction, "numerator" | "denominator"), outermost first
    first_row: int = 0
    last_row: int = 0
    first_col: int = 0
    last_col: int = 0
    moved: int = 0
    term_padding: float | None = None  # a grid term column's cell padding, as the layout used it
    place: tuple = ()  # the placement that drew it
    valign: Literal["top", "middle", "bottom"] | None = None  # a table cell's valign, when the piece fills it
    relation_centre: float | None = None  # an equation relation's PDF centre, in columns from the grid origin

    @property
    def text(self) -> str:
        return "".join(atom.command.text for atom in self.atoms)


@dataclass(slots=True)
class _Edge:
    """A border edge of the sheet and where it came from."""

    border: xl.EdgeBorder
    style: BorderStyle
    source: tuple[int, int]  # (page, index of the line's first stroke command)


class _SheetBuilder:
    """Build one sheet; ``build`` runs once, its steps in order (each uses the previous ones' results)."""

    def __init__(self, name: str, pages: tuple[ScenePage, ...], first_number: int, total: int,
                 fonts: FontRegistry, padding: PaddingFunction) -> None:
        self.name, self.pages, self.first_number, self.total = name, pages, first_number, total
        self.fonts, self._padding = fonts, padding
        self.profile = pages[0].profile
        self.grid = self.profile.grid
        self.columns, self.page_rows = self.grid.columns, self.grid.rows
        self.total_rows = self.page_rows * len(pages)
        if self.columns > xl.MAX_COLUMNS:
            raise XlsxError(f"sheet {name!r}: {self.columns} grid columns are more than Excel's "
                            f"{xl.MAX_COLUMNS} columns")
        if self.total_rows > xl.MAX_ROWS:
            raise XlsxError(f"sheet {name!r}: {self.total_rows} grid rows are more than Excel's "
                            f"{xl.MAX_ROWS} rows")
        if len(pages) - 1 > xl.MAX_ROW_BREAKS:
            raise XlsxError(f"sheet {name!r}: {len(pages)} pages need {len(pages) - 1} row breaks, more than "
                            f"Excel's {xl.MAX_ROW_BREAKS} manual row breaks of one sheet")
        try:
            self.cols = _Axis.build(self.grid.pitch_x, self.columns, PRINTED_COLUMN_PT, PRINT_COLUMN_PT_PER_PX,
                                    "column")
            self.rows = _Axis.build(self.grid.pitch_y, self.page_rows, PRINTED_ROW_PT, PRINT_ROW_PT_PER_PX, "row")
        except XlsxError as exc:
            raise XlsxError(f"sheet {name!r}: {exc}") from None
        self.shifts: list[XlsxShift] = []
        self.fallbacks: list[XlsxFallback] = []
        self.numbers_as_text: list[XlsxFallback] = []
        self.texts_clipped: list[XlsxFallback] = []
        self.dropped: list[str] = []
        self.untagged: Counter[str] = Counter()
        self.pieces: list[_Piece] = []
        self.drawings: list[tuple[tuple[int, int], xl.Drawing]] = []  # ((page, command index), drawing)
        self.edges: dict[tuple, _Edge] = {}
        self.conflicts: set[tuple] = set()
        self.split_terms: set[tuple] = set()
        self.fraction_members: dict[tuple[_FractionKey, str], list[_Piece]] = {}
        self.bars: list[tuple[int, int, Line, _FractionKey]] = []  # (page, command index, bar, its fraction)
        self.built = False

    # --- helpers ---------------------------------------------------------------

    def padding(self, size: float) -> float:
        """Excel's inner cell padding on one side for ``size`` pt text (``cell_padding_pt``)."""
        padding = self._padding(size)
        if isinstance(padding, bool) or not isinstance(padding, (int, float)) or not math.isfinite(padding) \
                or padding < 0:
            raise ValueError(f"cell_padding_pt({size:g}) must return a finite length of at least 0 pt, "
                             f"not {padding!r}")
        return float(padding)

    def page_number(self, page: int) -> int:
        return self.first_number + page

    def where(self, page: int) -> str:
        return f"sheet {self.name!r} page {self.page_number(page)}"

    def point(self, page: int, x: float, y: float) -> tuple[float, float]:
        """Map page pt to sheet pt (the sheet origin is the first page's grid origin)."""
        return (self.cols.at(x - self.grid.origin_x),
                page * self.rows.length + self.rows.at(y - self.grid.origin_y))

    def box(self, page: int, x: float, y: float, width: float, height: float) -> tuple[float, float, float, float]:
        left, top = self.point(page, x, y)
        right, bottom = self.point(page, x + width, y + height)
        return left, top, right - left, bottom - top

    def fallback(self, page: int, kind: str, detail: str) -> None:
        self.fallbacks.append(XlsxFallback(self.name, self.page_number(page), kind, detail))

    def add_drawing(self, page: int, index: int, command) -> None:
        drawing = self.convert(command, page)
        if drawing is not None:
            self.drawings.append(((page, index), drawing))

    # --- the sheet ---------------------------------------------------------------

    def build(self) -> xl.Sheet:
        if self.built:
            raise RuntimeError("a sheet builder builds once")
        self.built = True
        for page_index, page in enumerate(self.pages):
            try:
                self.read_page(page_index, page)
            except XlsxError:
                raise
            except (ValueError, OSError) as exc:  # the model's checks and unreadable images
                raise XlsxError(f"{self.where(page_index)}: {exc}") from exc
        try:
            self.fraction_rows()
            self.equation_rows()
            self.table_cells()
            cells, merges = self.place()
            self.place_bars()
            borders = self.borders(merges)
            header = self.decoration("header")
            footer = self.decoration("footer")
            self.check_drawings()
            drawings = tuple(drawing for _, drawing in sorted(self.drawings, key=lambda item: item[0]))
            breaks = tuple(page * self.page_rows for page in range(1, len(self.pages)))
            sheet = xl.Sheet(self.name, self.cols.sizes, self.rows.sizes * len(self.pages), cells=cells,
                             merges=merges, borders=borders, row_breaks=breaks,
                             page=self.page_setup(header, footer),
                             header=header[0] if header else None, footer=footer[0] if footer else None,
                             drawings=drawings)
            return self.fit(sheet)
        except XlsxError:
            raise
        except ValueError as exc:
            raise XlsxError(f"sheet {self.name!r}: {exc}") from exc

    # --- reading the commands -------------------------------------------------

    def read_page(self, page_index: int, page: ScenePage) -> None:
        owners = _owners(page)
        skipped = _decoration_indices(page)
        groups: dict[tuple, list[tuple[int, object]]] = {}
        texts: list[tuple[int, Text, tuple]] = []
        bar_units: dict[tuple, list] = {}
        extents: dict[tuple, list[Box]] = {}  # the strokes of a unit's roots and brackets
        for index, command in enumerate(page.commands):
            if index in skipped:
                continue
            tag = command.tag
            if tag is None:
                self.untagged[type(command).__name__] += 1
            place = owners[index]
            turn = tag.scope(Kind.QUARTER_TURN) if tag is not None else None
            if turn is not None and not self.swapped(turn):
                groups.setdefault(("turn", place, tag.key(Kind.QUARTER_TURN)), []).append((index, command))
                continue
            role = tag.role if tag is not None else None
            if role is Role.FIGURE:
                groups.setdefault(("figure", place, tag.key(Kind.FIGURE)), []).append((index, command))
                continue
            if isinstance(command, Text):
                if not command.text.strip():
                    continue  # blank text draws nothing
                if command.quarter_turns == 2:
                    self.fallback(page_index, "rotated_text", repr(command.text))
                    self.add_drawing(page_index, index, command)
                    continue
                texts.append((index, command, place))
            elif role in BORDER_ROLES:
                self.read_border(page_index, index, command)
            elif role is Role.FRACTION_BAR and isinstance(command, Line):
                position = tag.find(Kind.FRACTION)
                if position is None:
                    raise XlsxError(f"{self.where(page_index)}: a fraction bar's tag names no fraction")
                fraction_key = _FractionKey(page_index, place, tag.key(Kind.FRACTION))
                parent = _unit_key(place, tag.path[:position])
                if parent is not None:
                    bar_units.setdefault(parent, []).append(command)
                self.bars.append((page_index, index, command, fraction_key))
            else:
                if role in (Role.RADICAL, Role.DELIMITER):
                    unit = _unit_key(place, tag.path)
                    if unit is not None:
                        extents.setdefault(unit, []).append(command_bounds(command, self.fonts))
                self.add_drawing(page_index, index, command)
        for (kind, _, _), members in groups.items():
            if kind == "turn":
                turn = members[0][1].tag.scope(Kind.QUARTER_TURN)
                local = turn.data.get("local_grid")
                pitches = (f"{local['pitch_x']:g} x {local['pitch_y']:g} pt" if isinstance(local, Mapping)
                           and {"pitch_x", "pitch_y"} <= set(local) else "unknown")
                self.fallback(page_index, "quarter_turn",
                              f"block {turn.data.get('block_id') or '(no id)'} with local grid {pitches}")
                children = [self.convert(command, page_index) for _, command in members]
            else:
                children = self.figure(page_index, members)
            children = [child for child in children if child is not None]
            if children:
                self.drawings.append(((page_index, members[0][0]), xl.Group(children)))
        self.read_texts(page_index, texts, bar_units, extents)

    def swapped(self, turn: Scope) -> bool:
        """Is a QuarterTurn laid out on the page grid with its pitches swapped?"""
        local = turn.data.get("local_grid")
        if not isinstance(local, Mapping) or not {"pitch_x", "pitch_y"} <= set(local):
            return False
        return (math.isclose(local["pitch_x"], self.grid.pitch_y, rel_tol=_PITCH_TOLERANCE)
                and math.isclose(local["pitch_y"], self.grid.pitch_x, rel_tol=_PITCH_TOLERANCE))

    # --- text pieces -------------------------------------------------------------

    def read_texts(self, page_index: int, texts: list[tuple[int, Text, tuple]],
                   bar_units: dict[tuple, list[Line]], extents: dict[tuple, list[Box]]) -> None:
        units: dict[tuple, list[tuple[int, Text, tuple]]] = {}
        for index, command, place in texts:
            path = command.tag.path if command.tag is not None else ()
            key = _unit_key(place, path) or ("solo", place, index)
            units.setdefault(key, []).append((index, command, place))
        for key, members in units.items():
            atoms = [self.atom(index, command) for index, command, _ in members]
            by_turn: dict[int, list[_Atom]] = {}
            for atom in atoms:
                by_turn.setdefault(atom.command.quarter_turns, []).append(atom)
            bars = bar_units.get(key, ())
            for turns, group in by_turn.items():
                group.sort(key=lambda atom: (atom.lo, atom.index))
                splits = sorted(_along(turns, (bar.x1 + bar.x2) / 2, (bar.y1 + bar.y2) / 2) for bar in bars)
                apart = (self.grid.pitch_x if turns == 0 else self.grid.pitch_y) / 2
                segment = [group[0]]
                for previous, atom in zip(group, group[1:]):
                    middle = ((previous.lo + previous.hi) / 2, (atom.lo + atom.hi) / 2)
                    plain = atom.vert is None and previous.vert is None
                    if (any(middle[0] < split < middle[1] for split in splits)
                            or (plain and self.cross(previous) != self.cross(atom))
                            or (plain and atom.lo - previous.hi >= apart)):
                        self.add_piece(page_index, turns, segment, members[0][2])
                        segment = []
                    segment.append(atom)
                whole = len(segment) == len(atoms) and not bars
                self.add_piece(page_index, turns, segment, members[0][2], extents.get(key, ()) if whole else None)

    def atom(self, index: int, command: Text) -> _Atom:
        metrics = self.fonts.measure(self.fonts.normalize_text(command.text), command.style)
        box = transformed_text_bounds(command, Box(0, -metrics.ascent, metrics.width,
                                                   metrics.ascent + metrics.descent))
        lo, hi = _reading_extent(command.quarter_turns, box)
        ink = metrics.ink_bounds
        if ink is not None and ink.width > 0 and ink.height > 0:
            ink = _reading_extent(command.quarter_turns, transformed_text_bounds(command, ink))
        else:
            ink = None
        tag = command.tag
        path = tag.path if tag is not None else ()
        position = _unit_position(path)
        vert = None
        for scope in path[(position + 1 if position is not None else 0):]:
            if scope.kind is Kind.SCRIPT and scope.part in ("superscript", "subscript"):
                vert = scope.part
                break
        return _Atom(index, command, vert, lo, hi, ink)

    def cross(self, atom: _Atom) -> int:
        """The page-local row (upright) or column (turned) holding the atom's baseline."""
        command, grid = atom.command, self.grid
        if command.quarter_turns == 0:
            return math.floor((command.y - _BASELINE_NUDGE_PT - grid.origin_y) / grid.pitch_y)
        nudge = -_BASELINE_NUDGE_PT if command.quarter_turns == 1 else _BASELINE_NUDGE_PT
        return math.floor((command.x + nudge - grid.origin_x) / grid.pitch_x)

    def cross_box(self, atom: _Atom, cross: int) -> tuple[float, float]:
        """An atom's line box (ascent to descent) across its cross cell, in pt from the cell's side that is
        the text's top: the page's top upright, its left for +1 turns, its right for -1 turns."""
        command, grid = atom.command, self.grid
        metrics = self.fonts.measure(self.fonts.normalize_text(command.text), command.style)
        if command.quarter_turns == 0:
            baseline = command.y - grid.y(cross)
        elif command.quarter_turns == 1:
            baseline = command.x - grid.x(cross)
        else:
            baseline = grid.x(cross + 1) - command.x
        return baseline - metrics.ascent, baseline + metrics.descent

    def add_piece(self, page_index: int, turns: int, atoms: list[_Atom], place,
                  extents: tuple[Box, ...] | list[Box] | None = None) -> None:
        """Add one piece; ``extents`` (the unit's other strokes) is given when the piece is its whole unit."""
        base = [atom for atom in atoms if atom.vert is None] or atoms
        first = base[0].command
        path = first.tag.path if first.tag is not None else ()
        position = _unit_position(path)
        unit_path = path[:position + 1] if position is not None else ()
        line_position = max((index for index, scope in enumerate(path)
                             if scope.kind in (Kind.EQUATION_LINE, Kind.MATH_BLOCK)), default=None)
        line_key = None
        in_fraction = False
        if line_position is not None:
            line_key = (place, path[:line_position], replace(path[line_position], part=None))
            in_fraction = any(scope.kind is Kind.FRACTION for scope in path[line_position + 1:])
        fractions = tuple((_FractionKey(page_index, place, (*path[:index], replace(scope, part=None))), scope.part)
                          for index, scope in enumerate(path)
                          if scope.kind is Kind.FRACTION and scope.part in ("numerator", "denominator"))
        piece = _Piece(page_index, turns, atoms, unit_path, line_key, in_fraction, fractions, place=place)
        grid = self.grid
        lo, hi = min(atom.lo for atom in atoms), max(atom.hi for atom in atoms)
        cross = self.cross(base[0])
        if turns == 0 and _is_relation(unit_path):
            # An equation's relation is centred on its anchor boundary: it takes the columns from that boundary.
            piece.first_row = piece.last_row = cross
            centre = ((lo + hi) / 2 - grid.origin_x) / grid.pitch_x
            piece.relation_centre = centre
            piece.first_col = math.floor(centre + _CELL_EPSILON)
            piece.last_col = piece.first_col + max(1, math.ceil((hi - lo) / grid.pitch_x - _CELL_EPSILON)) - 1
        else:
            # The cells the glyphs' ink touches (side bearings are blank); blank text takes its advance.
            inked = [atom.ink for atom in atoms if atom.ink is not None]
            if inked:
                lo, hi = min(ink[0] for ink in inked), max(ink[1] for ink in inked)
            if turns == 0:
                piece.first_row = piece.last_row = cross
                piece.first_col, piece.last_col = _cells(lo - grid.origin_x, hi - grid.origin_x, grid.pitch_x)
                if extents is not None:
                    self.grid_term(piece, extents, place)
            else:
                top, bottom = (-hi, -lo) if turns == 1 else (lo, hi)
                piece.first_col = piece.last_col = cross
                piece.first_row, piece.last_row = _cells(top - grid.origin_y, bottom - grid.origin_y, grid.pitch_y)
        term_position = next((index for index in range(len(unit_path) - 1, -1, -1)
                              if unit_path[index].kind is Kind.EQUATION_PART and unit_path[index].part == "term"),
                             None)
        term = unit_path[term_position] if term_position is not None else None
        whole_term = term_position == len(unit_path) - 1
        if (term is not None and term.data.get("columns")
                and (turns != 0 or extents is None or not whole_term)):
            reason = ("is turned" if turns else "holds a fraction" if not whole_term
                      else "is split into several pieces (a fraction, or atoms apart)")
            key = (page_index, place, unit_path[:term_position + 1])
            if key not in self.split_terms:
                self.split_terms.add(key)
                self.fallback(page_index, "term_off_grid", f"{self.cell_text(piece)[0]!r}: its grid term {reason}, "
                              "so its pieces keep the columns their ink touches")
        self.check_piece(piece, "lies outside")
        self.pieces.append(piece)

    def grid_term(self, piece: _Piece, extents, place) -> None:
        """Give a grid term (``term_columns="grid"``) the whole columns the layout sized for it (FR-025).

        The term tag's ``first_column`` counts from the equation block's left
        edge, which the page metadata places (``block_left``); the term's
        ink-inclusive box (its text and the strokes of its roots and brackets)
        must lie in those columns. A block whose left edge is not on a page
        column boundary (a pt indent, a table cell's padding) or is not
        known, and glyphs outside the columns, are recorded as term_off_grid
        and the piece keeps the columns its ink touches. A term laid out
        with another padding than ``cell_padding_pt`` is recorded too.
        """
        term = piece.unit_path[-1] if piece.unit_path else None
        if (term is None or term.kind is not Kind.EQUATION_PART or term.part != "term"
                or not {"columns", "first_column", "cell_padding_pt"} <= set(term.data)):
            return
        count, padding = term.data["columns"], term.data["cell_padding_pt"]
        if not count:
            return
        grid = self.grid
        base = next((atom for atom in piece.atoms if atom.vert is None), piece.atoms[0])
        expected = self.padding(base.command.style.size)
        text = self.cell_text(piece)[0]
        if abs(expected - padding) > _PADDING_TOLERANCE:
            self.fallback(piece.page, "cell_padding_mismatch",
                          f"{text!r}: the term was laid out with {padding:g} pt cell padding, "
                          f"not cell_padding_pt's {expected:g} pt")
        left = self.block_left(piece.page, place, base.command.tag.path)
        if left is None:
            self.fallback(piece.page, "term_off_grid", f"{text!r}: its block's left edge is not known (the "
                          "term lies in a table cell, a figure or another container the page metadata does "
                          "not place)")
            return
        start = (left - grid.origin_x) / grid.pitch_x
        if abs(start - round(start)) * grid.pitch_x > _TERM_EDGE_TOLERANCE_PT:
            self.fallback(piece.page, "term_off_grid",
                          f"{text!r}: its block starts {left - grid.origin_x:g} pt from the grid origin, "
                          "not on a page column boundary")
            return
        first = round(start) + term.data["first_column"]
        boxes = [command_bounds(atom.command, self.fonts) for atom in piece.atoms] + list(extents)
        low, high = grid.x(0) + first * grid.pitch_x, grid.x(0) + (first + count) * grid.pitch_x
        if min(box.x for box in boxes) < low - _TERM_EDGE_TOLERANCE_PT \
                or max(box.right for box in boxes) > high + _TERM_EDGE_TOLERANCE_PT:
            self.fallback(piece.page, "term_off_grid",
                          f"{text!r}: its glyphs leave its term columns {first} to {first + count - 1}")
            return
        piece.first_col, piece.last_col = first, first + count - 1
        piece.term_padding = padding

    def block_left(self, page: int, place, path: tuple[Scope, ...]) -> float | None:
        """The page x of the equation block a command lies in, from the page metadata, or None.

        The placement's column is followed through the Stack and Columns
        children (``x_pt``) and Indent offsets (``indent_pt``) that the path
        names before the equation; any other container is unknown.
        """
        if place[0] != "placement":
            return None
        placements = self.pages[page].metadata.get("placements", ())
        trace = placements[place[1]] if place[1] < len(placements) else {}
        col = trace.get("col")
        if isinstance(col, bool) or not isinstance(col, int) or not 0 <= col <= self.columns:
            return None
        x = self.grid.x(col)
        equation = next((index for index, scope in enumerate(path) if scope.kind is Kind.EQUATION), None)
        line = next((scope for scope in path if scope.kind is Kind.EQUATION_LINE), None)
        if equation is None or line is None:
            return None
        for scope in path[:equation]:
            if scope.kind not in (Kind.STACK, Kind.COLUMNS) or scope.index is None:
                return None
            part = next((part.get("metadata", {}) for part in _parts(trace)
                         if "children" in part.get("metadata", {})), None)
            if part is None or scope.index >= len(part["children"]) or "x_pt" not in part["children"][scope.index]:
                return None
            trace = part["children"][scope.index]
            x += part.get("indent_pt", 0.0) + trace["x_pt"]
        for part in _parts(trace):
            metadata = part.get("metadata", {})
            if metadata.get("equation_index") == path[equation].index and metadata.get("line_index") == line.index:
                return x + metadata.get("indent_pt", 0.0)
        return None

    def check_piece(self, piece: _Piece, verb: str) -> None:
        """Raise when a piece is not inside its page's grid."""
        edge = None
        if piece.first_col < 0:
            edge = "left"
        elif piece.last_col >= self.columns:
            edge = "right"
        elif piece.first_row < 0:
            edge = "top"
        elif piece.last_row >= self.page_rows:
            edge = "bottom"
        if edge is not None:
            raise XlsxError(f"{self.where(piece.page)}: {piece.text!r} {verb} the {edge} edge of the grid "
                            f"({self.columns} x {self.page_rows} cells)")

    def fraction_rows(self) -> None:
        """Give each numerator and denominator its own rows: a denominator sharing a row moves down.

        Inner fractions go first, so an outer fraction sees where its inner
        ones ended.
        """
        first_seen: dict[_FractionKey, int] = {}
        self.fraction_members = {}  # (fraction key, part) -> its pieces, read once (the pieces only move later)
        for number, piece in enumerate(self.pieces):
            for key, part in piece.fractions:
                first_seen.setdefault(key, number)
                self.fraction_members.setdefault((key, part), []).append(piece)
        # inner fractions first; one depth in the order the pieces were read (never a set's order)
        fractions = sorted(first_seen, key=lambda key: (-len(key.path), first_seen[key]))
        for key in fractions:
            numerators = self.fraction_members.get((key, "numerator"), [])
            denominators = self.fraction_members.get((key, "denominator"), [])
            # A script's rich text run cannot hold a fraction: its cells are written at full size.
            in_script = any(scope.kind is Kind.SCRIPT and scope.part in ("superscript", "subscript")
                            for scope in key.path)
            if in_script:
                piece = (numerators or denominators)[0]
                self.fallback(piece.page, "fraction_in_script",
                              f"{self.cell_text(piece)[0]!r}: a fraction in a superscript or subscript is "
                              "written as numerator and denominator cells")
            if not numerators or not denominators or any(piece.turns for piece in numerators + denominators):
                continue  # a turned fraction keeps the cells its numerator and denominator touch
            step = max(piece.last_row for piece in numerators) - min(piece.first_row for piece in denominators) + 1
            if step <= 0:
                continue
            for piece in denominators:
                before = (piece.first_row, piece.first_col)
                piece.first_row += step
                piece.last_row += step
                self.check_piece(piece, "moved below a numerator reaches")
                self.record_shift(piece, before, "fraction_in_script" if in_script else "fraction")

    def equation_rows(self) -> None:
        """Merge the pieces outside fractions over their equation line's rows."""
        lines: dict[tuple, list[_Piece]] = {}
        for piece in self.pieces:
            if piece.line_key is not None and piece.turns == 0:
                lines.setdefault((piece.page, piece.line_key), []).append(piece)
        for members in lines.values():
            # A label wrapped to several display lines keeps each line in its own row.
            labels = [piece for piece in members if _label_line(piece.unit_path) is not None]
            if len({_label_line(piece.unit_path) for piece in labels}) > 1:
                members = [piece for piece in members if _label_line(piece.unit_path) is None]
            if not members:
                continue
            top = min(piece.first_row for piece in members)
            bottom = max(piece.last_row for piece in members)
            if bottom > top:
                for piece in members:
                    if not piece.in_fraction:
                        piece.first_row, piece.last_row = top, bottom

    def table_cells(self) -> None:
        """Let the only piece of a table cell fill the cell's whole range with the cell's alignment.

        The library places a one-line cell's text in its frame by the cell's
        align and valign, so the merged range of the frame's grid cells, with
        the same alignment, prints it where the PDF does. Cells of several
        pieces keep a cell per piece (each display line in its own row).
        """
        cells: dict[tuple, list[_Piece]] = {}
        for piece in self.pieces:
            path = piece.atoms[0].command.tag.path if piece.atoms[0].command.tag is not None else ()
            position = next((index for index in range(len(path) - 1, -1, -1)
                             if path[index].kind is Kind.TABLE_CELL), None)
            if position is not None:
                cells.setdefault((piece.page, piece.place, path[:position + 1]), []).append(piece)
        for (page, place, path), members in cells.items():
            if len(members) != 1:
                continue
            piece = members[0]
            frame = self.cell_frame(page, place, path)
            if frame is None:
                continue
            first_row, last_row, first_col, last_col = frame
            if not (first_row <= piece.first_row <= piece.last_row <= last_row
                    and first_col <= piece.first_col <= piece.last_col <= last_col):
                continue  # the text does not lie in the frame the metadata gives
            valign = path[-1].data.get("valign")
            if piece.turns == 0 and not self.frame_keeps_place(piece, frame, valign):
                continue  # a cell padding far from Excel's: the text keeps its own cells
            piece.first_row, piece.last_row, piece.first_col, piece.last_col = frame
            piece.valign = valign

    def frame_keeps_place(self, piece: _Piece, frame: tuple[int, int, int, int], valign: str | None) -> bool:
        """Would Excel's alignment in the whole frame print the text within half a cell of the PDF's place?

        Excel aligns inside its own cell padding (``cell_padding_pt``) and
        the insets from the top or bottom (``EXCEL_TOP_INSET_PT``...); a
        table cell with a much larger padding puts the PDF's text elsewhere.
        """
        grid = self.grid
        first_row, last_row, first_col, last_col = frame
        left, right = grid.x(first_col), grid.x(last_col + 1)
        top, bottom = grid.y(first_row), grid.y(last_row + 1)
        inked = [atom.ink if atom.ink is not None else (atom.lo, atom.hi) for atom in piece.atoms]
        ink_left, ink_right = min(low for low, _ in inked), max(high for _, high in inked)
        base = next((atom for atom in piece.atoms if atom.vert is None), piece.atoms[0])
        metrics = self.fonts.measure(self.fonts.normalize_text(base.command.text), base.command.style)
        box_top, box_bottom = base.command.y - metrics.ascent, base.command.y + metrics.descent
        padding = self.padding(base.command.style.size)
        align = _alignment(piece.unit_path)
        dx = (ink_left - (left + padding) if align == "left" else ink_right - (right - padding) if align == "right"
              else (ink_left + ink_right - left - right) / 2)
        dy = (box_top - (top + EXCEL_TOP_INSET_PT) if valign == "top"
              else box_bottom - (bottom - EXCEL_BOTTOM_INSET_PT) if valign == "bottom"
              else (box_top + box_bottom - top - bottom) / 2)
        return abs(dx) <= grid.pitch_x / 2 and abs(dy) <= grid.pitch_y / 2

    def cell_frame(self, page: int, place, path: tuple[Scope, ...]) -> tuple[int, int, int, int] | None:
        """The page-local (first row, last row, first col, last col) of a table cell's frame, or None.

        The placement is followed through Stack and Columns children, Indent
        offsets and QuarterTurn's ``local_to_part`` (the page metadata) down
        to the table part that records the cell's frame.
        """
        if place[:1] != ("placement",):
            return None
        placements = self.pages[page].metadata.get("placements", ())
        trace = placements[place[1]] if place[1] < len(placements) else {}
        col, row = trace.get("col"), trace.get("row")
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in (col, row)):
            return None
        grid = self.grid
        matrix = (1.0, 0.0, 0.0, 1.0, grid.x(col), grid.y(row))  # local pt -> page pt: x' = a x + c y + e
        pitch = grid.pitch_y

        def then(inner: tuple) -> tuple:
            a, b, c, d, e, f = matrix
            a2, b2, c2, d2, e2, f2 = inner
            return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2,
                    a * e2 + c * f2 + e, b * e2 + d * f2 + f)

        def part_top(part: Mapping) -> float:
            return part["y_pt"] if "y_pt" in part else part["row"] * pitch

        cell = path[-1]
        for scope in path[:-1]:
            if scope.kind is Kind.TABLE:
                continue
            if scope.kind in (Kind.STACK, Kind.COLUMNS) and scope.index is not None:
                part = next((part for part in _parts(trace) if "children" in part.get("metadata", {})), None)
                if part is None or scope.index >= len(part["metadata"]["children"]):
                    return None
                child = part["metadata"]["children"][scope.index]
                matrix = then((1.0, 0.0, 0.0, 1.0, part["metadata"].get("indent_pt", 0.0) + child["x_pt"],
                               part_top(part) + child["y_pt"]))
                trace = child
            elif scope.kind is Kind.QUARTER_TURN:
                part = next((part for part in _parts(trace) if "local_to_part" in part.get("metadata", {})), None)
                local = scope.data.get("local_grid")
                if part is None or not isinstance(local, Mapping) or "pitch_y" not in local:
                    return None
                matrix = then((1.0, 0.0, 0.0, 1.0, part["metadata"].get("indent_pt", 0.0), part_top(part)))
                matrix = then(tuple(part["metadata"]["local_to_part"]))
                trace, pitch = part["metadata"]["child"], local["pitch_y"]
            else:
                return None
        for part in _parts(trace):
            metadata = part.get("metadata", {})
            for record in metadata.get("cells", ()):
                if record.get("cell_id") != cell.data.get("cell_id"):
                    continue
                box = record["frame"]
                left = metadata.get("indent_pt", 0.0) + box["x_pt"]
                top = part_top(part) + box["y_pt"]
                corners = [then((1.0, 0.0, 0.0, 1.0, x, y))[4:] for x in (left, left + box["width"])
                           for y in (top, top + box["height"])]
                xs, ys = [x for x, _ in corners], [y for _, y in corners]
                edges = []
                for low, high, origin, step in ((min(ys), max(ys), grid.origin_y, grid.pitch_y),
                                                (min(xs), max(xs), grid.origin_x, grid.pitch_x)):
                    first, stop = round((low - origin) / step), round((high - origin) / step)
                    if (abs(low - (origin + first * step)) > _FRAME_TOLERANCE_PT
                            or abs(high - (origin + stop * step)) > _FRAME_TOLERANCE_PT or stop <= first):
                        return None  # a frame off the page's cell boundaries keeps the piece's own cells
                    edges.append((first, stop - 1))
                (first_row, last_row), (first_col, last_col) = edges
                if first_row < 0 or first_col < 0 or last_row >= self.page_rows or last_col >= self.columns:
                    return None
                return first_row, last_row, first_col, last_col
        return None

    def record_shift(self, piece: _Piece, before: tuple[int, int], reason: str) -> None:
        base = piece.page * self.page_rows
        self.shifts.append(XlsxShift(self.name, self.page_number(piece.page), self.cell_text(piece)[0],
                                     (base + before[0], before[1]),
                                     (base + piece.first_row, piece.first_col), reason))

    def place(self) -> tuple[tuple[xl.CellValue, ...], tuple[xl.CellRange, ...]]:
        occupied: set[tuple[int, int]] = set()
        cells, merges = [], []
        planned: dict[tuple[int, int], int] = {}  # cells each piece will take unless it moves, by piece
        for number, piece in enumerate(self.pieces):
            base = piece.page * self.page_rows
            for row in range(piece.first_row, piece.last_row + 1):
                for col in range(piece.first_col, piece.last_col + 1):
                    planned.setdefault((base + row, col), number)
        numbers = {id(piece): number for number, piece in enumerate(self.pieces)}
        for piece in sorted(self.pieces, key=_reading_order):
            base = piece.page * self.page_rows
            if piece.relation_centre is not None:
                self.centre_relation(piece, occupied, planned, numbers[id(piece)])
            step_row, step_col = {0: (0, 1), 1: (-1, 0), 3: (1, 0)}[piece.turns]
            before = (piece.first_row, piece.first_col)
            while any((base + row, col) in occupied for row in range(piece.first_row, piece.last_row + 1)
                      for col in range(piece.first_col, piece.last_col + 1)):
                piece.first_row += step_row
                piece.last_row += step_row
                piece.first_col += step_col
                piece.last_col += step_col
                piece.moved += 1
                self.check_piece(piece, "moved to free cells passes")
            if piece.moved:
                self.record_shift(piece, before, "overlap")
            occupied.update((base + row, col) for row in range(piece.first_row, piece.last_row + 1)
                            for col in range(piece.first_col, piece.last_col + 1))
        edges = {edge.border.edge_key() for edge in self.edges.values()}
        for piece in sorted(self.pieces, key=_reading_order):
            base = piece.page * self.page_rows
            try:
                cells.append(self.cell(piece, base, occupied, edges))
            except XlsxError:
                raise
            except ValueError as exc:  # a font name or size Excel cannot hold
                raise XlsxError(f"{self.where(piece.page)}: {piece.text!r}: {exc}") from exc
            if piece.last_row > piece.first_row or piece.last_col > piece.first_col:
                merges.append(xl.CellRange(base + piece.first_row, piece.first_col,
                                           base + piece.last_row, piece.last_col))
        cells.sort(key=lambda cell: (cell.row, cell.col))
        merges.sort(key=lambda merge: (merge.first_row, merge.first_col))
        return tuple(cells), tuple(merges)

    def cross_alignment(self, piece: _Piece) -> str:
        """The vertical alignment (in the text's direction) that puts its line box nearest the PDF's.

        Excel puts a top-aligned line's box ``EXCEL_TOP_INSET_PT`` below the
        cell's top, a bottom-aligned one ``EXCEL_BOTTOM_INSET_PT`` above its
        bottom (turned text: ``EXCEL_TURNED_INSET_PT``) and a middle one in
        the middle; top or bottom wins only when its anchor lies nearer the
        same anchor of the PDF's line box than the middle's does by
        ``CROSS_ALIGN_MARGIN_PT`` (a fraction's numerator and denominator,
        high in their rows, take the top).
        """
        base = next((atom for atom in piece.atoms if atom.vert is None), piece.atoms[0])
        top, bottom = self.cross_box(base, piece.first_row if piece.turns == 0 else piece.first_col)
        size = self.grid.pitch_y if piece.turns == 0 else self.grid.pitch_x
        top_inset, bottom_inset = ((EXCEL_TOP_INSET_PT, EXCEL_BOTTOM_INSET_PT) if piece.turns == 0
                                   else (EXCEL_TURNED_INSET_PT, EXCEL_TURNED_INSET_PT))
        errors = {"middle": abs(size / 2 - (top + bottom) / 2),
                  "top": abs(top_inset - top),
                  "bottom": abs(size - bottom_inset - bottom)}
        best = min(("top", "bottom"), key=lambda name: errors[name])
        return best if errors[best] < errors["middle"] - CROSS_ALIGN_MARGIN_PT else "middle"

    def check_clipped(self, piece: _Piece, runs: list[xl.Run], font: xl.Font, base: int,
                      occupied: set[tuple[int, int]], edges: set[tuple], *, record: bool = True) -> str | None:
        """Grow text cells until Excel has room for the text, or record that its end may be cut.

        Excel draws glyphs in whole pixels (``screen_width``) inside the cell
        padding; text grows like a number (``widen``), a grid term keeps its
        term columns. Returns why the text may be cut, or None when it fits;
        ``record=False`` leaves the record to the caller.
        """
        # cell_text writes one run per atom, in order (a joining space belongs to the run after it)
        width = math.fsum(self.screen_width(run.text, atom.command.style)
                          for atom, run in zip(piece.atoms, runs, strict=True))
        need = width + 2 * (piece.term_padding if piece.term_padding is not None else self.padding(font.size))
        if self.room(piece) >= need - TOLERANCE:
            return None
        if piece.term_padding is None and self.widen(piece, need, occupied, edges):
            return None
        cells = ("its grid term columns (grid terms do not grow) are" if piece.term_padding is not None
                 else "its cells and the free cells beside them are")
        short = (f"its end may be cut; Excel may draw it in {need:g} pt with its padding (whole screen pixels "
                 f"per glyph, an estimate), {cells} {self.room(piece):g} pt")
        if record:
            text = "".join(run.text for run in runs)
            self.texts_clipped.append(XlsxFallback(
                self.name, self.page_number(piece.page), "text_clipped",
                f"{text!r} at {cell_ref(base + piece.first_row, piece.first_col)}: {short}"))
        return short

    def centre_relation(self, piece: _Piece, occupied: set[tuple[int, int]], planned: dict[tuple[int, int], int],
                        number: int) -> None:
        """Put a relation's columns where their centre is nearest its PDF centre, over free cells only.

        A relation wider than a column then straddles its anchor boundary as
        in the PDF; cells another piece takes or will take (the left-hand
        side, a fraction's denominator in a lower row) stay theirs.
        """
        base = piece.page * self.page_rows
        count = piece.last_col - piece.first_col + 1
        rows = range(piece.first_row, piece.last_row + 1)

        def free(cell: tuple[int, int]) -> bool:
            return cell not in occupied and planned.get(cell, number) == number

        candidates = [start for start in range(piece.first_col - count + 1, piece.first_col + 1)
                      if start >= 0 and start + count <= self.columns
                      and all(free((base + row, col)) for row in rows for col in range(start, start + count))]
        if candidates:
            start = min(candidates, key=lambda start: (abs(start + count / 2 - piece.relation_centre), -start))
            piece.first_col, piece.last_col = start, start + count - 1

    def cell_text(self, piece: _Piece) -> tuple[str, list[xl.Run], xl.Font]:
        """Return the piece's text, its runs and the cell font."""
        base = [atom for atom in piece.atoms if atom.vert is None] or piece.atoms
        style = base[0].command.style
        font = _font(style)
        space = self.fonts.measure(" ", style).width
        threshold = space / 2 if space > 0 else SPACE_GAP_EM * style.size
        runs, previous = [], None
        for atom in piece.atoms:
            command = atom.command
            text = command.text
            # a space where it is closer to the PDF's gap than no space is
            if (previous is not None and atom.vert is None and previous.vert is None
                    and atom.lo - previous.hi >= threshold):
                text = " " + text
            run_font = (replace(font, name=command.style.font) if atom.vert is not None
                        else _font(command.style))
            runs.append(xl.Run(text, None if run_font == font else run_font, atom.vert))
            previous = atom
        return "".join(run.text for run in runs), runs, font

    def screen_width(self, text: str, style) -> float:
        """The pt Excel's screen draws ``text`` in: each glyph takes whole pixels (rounded up)."""
        pixels = sum(math.ceil(self.fonts.measure(self.fonts.normalize_text(char), style).width * PIXELS_PER_PT
                               - 1e-9) for char in text)
        return pixels * SCREEN_PT_PER_PX

    def room(self, piece: _Piece) -> float:
        """The model pt (Excel's screen) of a piece's cells along its reading direction."""
        if piece.turns == 0:
            return math.fsum(self.cols.sizes[piece.first_col:piece.last_col + 1])
        return math.fsum(self.rows.sizes[piece.first_row:piece.last_row + 1])

    def widen(self, piece: _Piece, need: float, occupied: set[tuple[int, int]], edges: set[tuple]) -> bool:
        """Grow a piece's cells into free neighbours until Excel has room to show it, or leave them.

        A piece grows away from the side it is aligned to, a centred one by a
        cell on both sides at once (so its centre stays), only over cells no
        piece takes and never across or into a border, so the text stays
        where its alignment puts it.
        """
        base = piece.page * self.page_rows
        align = _alignment(piece.unit_path)
        steps = {"left": ("end",), "right": ("start",), "center": ("start", "end")}[align]
        span = (piece.first_row, piece.last_row, piece.first_col, piece.last_col)
        added: list[tuple[int, int]] = []
        while self.room(piece) < need - TOLERANCE:
            found = [self.neighbour(piece, side, base) for side in steps]
            if any(cells is None or any(cell in occupied for cell in cells) or any(key in edges for key in keys)
                   for cells, keys in found):
                occupied.difference_update(added)
                piece.first_row, piece.last_row, piece.first_col, piece.last_col = span
                return False
            for side, (cells, _) in zip(steps, found):
                self.grow(piece, side)
                occupied.update(cells)
                added.extend(cells)
        return True

    def neighbour(self, piece: _Piece, side: str, base: int) -> tuple[list | None, list]:
        """The cells next to a piece at the start or end of its reading direction, and the border edges
        a merge over them would cover (the edges between them and the piece, and between themselves)."""
        rows = range(piece.first_row, piece.last_row + 1)
        cols = range(piece.first_col, piece.last_col + 1)
        if piece.turns == 0:
            col = piece.first_col - 1 if side == "start" else piece.last_col + 1
            if not 0 <= col < self.columns:
                return None, []
            boundary = col + 1 if side == "start" else col
            keys = [("vertical", base + row, boundary) for row in rows]
            keys += [("horizontal", base + row, col) for row in rows[1:]]
            return [(base + row, col) for row in rows], keys
        upward = (piece.turns == 1) == (side == "end")  # +1 turns read upwards
        row = piece.first_row - 1 if upward else piece.last_row + 1
        if not 0 <= row < self.page_rows:
            return None, []
        boundary = base + (row + 1 if upward else row)
        keys = [("horizontal", boundary, col) for col in cols]
        keys += [("vertical", base + row, col) for col in cols[1:]]
        return [(base + row, col) for col in cols], keys

    @staticmethod
    def grow(piece: _Piece, side: str) -> None:
        if piece.turns == 0:
            if side == "start":
                piece.first_col -= 1
            else:
                piece.last_col += 1
        elif (piece.turns == 1) == (side == "end"):
            piece.first_row -= 1
        else:
            piece.last_row += 1

    def cell(self, piece: _Piece, base: int, occupied: set[tuple[int, int]], edges: set[tuple]) -> xl.CellValue:
        text, runs, font = self.cell_text(piece)
        rich = any(run.font is not None or run.vert_align is not None for run in runs)
        value: str | float | xl.RichText = xl.RichText(runs) if rich else text
        number_format = None
        kept_as_text = False
        if rich and not any(run.vert_align for run in runs) and classify_number(text) is not None:
            # it grows like any text; one record says why it is text and whether Excel may cut it
            kept_as_text = True
            short = self.check_clipped(piece, runs, font, base, occupied, edges, record=False)
            self.numbers_as_text.append(XlsxFallback(
                self.name, self.page_number(piece.page), "number_as_text",
                f"{text!r} at {cell_ref(base + piece.first_row, piece.first_col)}: its runs differ in font or "
                "script, so it stays rich text" + ("" if short is None else f"; {short}")))
        if not rich:
            number = classify_number(text)
            if number is not None:
                style = next(atom for atom in piece.atoms if atom.vert is None).command.style
                padding = piece.term_padding if piece.term_padding is not None else self.padding(style.size)
                need = self.screen_width(text, style) + 2 * padding
                # a grid term keeps the columns its term column has; anything else may grow
                if self.room(piece) >= need - TOLERANCE or (
                        piece.term_padding is None and self.widen(piece, need, occupied, edges)):
                    value, number_format = number.value, number.number_format
                else:
                    kept_as_text = True
                    cells = ("its grid term columns (grid terms do not grow) are" if piece.term_padding is not None
                             else "its cells and the free cells beside them are")
                    self.numbers_as_text.append(XlsxFallback(
                        self.name, self.page_number(piece.page), "number_as_text",
                        f"{text!r} at {cell_ref(base + piece.first_row, piece.first_col)}: Excel draws it in "
                        f"{need:g} pt with its padding, {cells} {self.room(piece):g} pt"))
        if number_format is None and not kept_as_text:  # a number kept as text has grown and is recorded already
            self.check_clipped(piece, runs, font, base, occupied, edges)
        align = _alignment(piece.unit_path)
        valign = piece.valign
        single = (piece.first_row == piece.last_row) if piece.turns == 0 else (piece.first_col == piece.last_col)
        # FR-021: an equation's pieces outside its fractions are centred in their rows
        equation = piece.line_key is not None and not piece.in_fraction
        if valign is None and single and not equation:
            valign = self.cross_alignment(piece)
        cross = {"top": "top", "middle": "center", "bottom": "bottom"}.get(valign, "center")
        if piece.turns == 0:
            h_align, v_align = align, cross
        else:
            reading = {"left": "bottom", "center": "center", "right": "top"}[align]
            v_align = reading if piece.turns == 1 else {"bottom": "top", "top": "bottom"}.get(reading, reading)
            # the cell's top turns to the page's left (+1 turns) or right (-1 turns)
            h_align = ({"top": "left", "center": "center", "bottom": "right"} if piece.turns == 1
                       else {"top": "right", "center": "center", "bottom": "left"})[cross]
        return xl.CellValue(base + piece.first_row, piece.first_col, value, number_format, font,
                            h_align, v_align, _TURNED_ROTATION[piece.turns])

    def place_bars(self) -> None:
        """Put each fraction bar on the boundary above its denominator's cells."""
        grid = self.grid
        for page, index, bar, key in self.bars:
            denominators = self.fraction_members.get((key, "denominator"), [])
            numerators = self.fraction_members.get((key, "numerator"), [])
            upright = bar.y1 == bar.y2 and all(piece.turns == 0 for piece in denominators + numerators)
            if not denominators or not upright:
                self.add_drawing(page, index, bar)
                continue
            y = page * self.rows.length + self.rows.starts[min(piece.first_row for piece in denominators)]
            moved = min(piece.moved for piece in numerators + denominators) * grid.pitch_x
            x1, _ = self.point(page, bar.x1 + moved, bar.y1)
            x2, _ = self.point(page, bar.x2 + moved, bar.y2)
            if x1 != x2:
                self.drawings.append(((page, index), xl.Line(x1, y, x2, y, stroke_width_pt=bar.width,
                                                             color=bar.color, dash=bar.dash)))
            else:
                self.drop(bar, page)

    # --- borders -------------------------------------------------------------------

    def read_border(self, page: int, index: int, command) -> None:
        """Turn a Table, Rule or SideRule line into cell edges, or into a recorded shape off the boundaries."""
        grid = self.grid
        try:
            style = BorderStyle(command.tag.data.get("style"))
        except ValueError:
            style = None
        color = command.color
        if isinstance(command, Rectangle):  # a SideRule bar, painted with its fill
            if not command.stroke and command.fill is not None:
                color = command.fill
            if command.width <= command.height:
                orientation, position = "vertical", command.x + command.width / 2
                along = (command.y, command.y + command.height)
            else:
                orientation, position = "horizontal", command.y + command.height / 2
                along = (command.x, command.x + command.width)
        elif isinstance(command, Line) and command.y1 == command.y2 and command.x1 != command.x2:
            orientation, position, along = "horizontal", command.y1, (command.x1, command.x2)
        elif isinstance(command, Line) and command.x1 == command.x2 and command.y1 != command.y2:
            orientation, position, along = "vertical", command.x1, (command.y1, command.y2)
        else:
            orientation = None
        if style is None or orientation is None:
            self.fallback(page, "border_off_grid", f"{type(command).__name__} is not a horizontal or vertical "
                          "line with a border style")
            self.add_drawing(page, index, command)
            return
        tolerance = style.thickness + _EDGE_TOLERANCE_PT
        start, end = min(along), max(along)
        if command.tag.data.get("drawn") == "continuing" and end - start <= tolerance:
            # a table seam's half-stroke bridge: the edge it completes is drawn by its own line
            self.dropped.append(f"{self.where(page)}: a table seam's {end - start:g} pt bridge (its edge is "
                                "drawn by the line it completes)")
            return
        horizontal = orientation == "horizontal"
        origin, pitch, count = ((grid.origin_y, grid.pitch_y, self.page_rows) if horizontal
                                else (grid.origin_x, grid.pitch_x, self.columns))
        along_origin, along_pitch, along_count = ((grid.origin_x, grid.pitch_x, self.columns) if horizontal
                                                  else (grid.origin_y, grid.pitch_y, self.page_rows))
        boundary = round((position - origin) / pitch)
        first = round((start - along_origin) / along_pitch)
        stop = round((end - along_origin) / along_pitch)
        problem = None
        if not (0 <= boundary <= count and abs(position - (origin + boundary * pitch)) <= tolerance):
            problem = f"lies {position - origin:g} pt from the grid origin, not on a cell boundary"
        elif (first >= stop or abs(start - (along_origin + first * along_pitch)) > tolerance
              or abs(end - (along_origin + stop * along_pitch)) > tolerance or first < 0 or stop > along_count):
            problem = (f"runs from {start - along_origin:g} to {end - along_origin:g} pt, not between "
                       "cell boundaries")
        if problem is not None:
            self.fallback(page, "border_off_grid", f"{orientation} {style.value} line {problem}")
            self.add_drawing(page, index, command)
            return
        base = page * self.page_rows
        stroke = command.tag.data.get("stroke", 0)
        valid = (isinstance(stroke, int) and not isinstance(stroke, bool)
                 and 0 <= stroke < len(style.offsets) and index - stroke >= 0)
        line = index - stroke if valid else index  # the strokes of one double line are one line
        for step in range(first, stop):
            if horizontal:
                edge = (xl.EdgeBorder(base + boundary - 1, step, "bottom", style.value, color)
                        if boundary == self.page_rows else xl.EdgeBorder(base + boundary, step, "top", style.value, color))
            else:
                edge = (xl.EdgeBorder(base + step, boundary - 1, "right", style.value, color)
                        if boundary == self.columns else xl.EdgeBorder(base + step, boundary, "left", style.value, color))
            # A page's top and bottom edges are its own: each page prints its side of a page break.
            key = edge.edge_key() + ((edge.side,) if horizontal and boundary in (0, self.page_rows) else ())
            self.add_edge(key, _Edge(edge, style, (page, line)))

    def add_edge(self, key: tuple, edge: _Edge) -> None:
        """Keep the thicker border of an edge (or else the solid, or else the first); record what is lost."""
        known = self.edges.get(key)
        if known is None:
            self.edges[key] = edge
            return
        rank = (edge.style.thickness, not edge.style.dash)
        winner, loser = (edge, known) if rank > (known.style.thickness, not known.style.dash) else (known, edge)
        self.edges[key] = winner
        # Only a single solid line covers a thinner single solid line; a double line's gap and a dash's
        # gaps leave the other line visible in the PDF.
        single = [len(item.style.offsets) == 1 and not item.style.dash for item in (winner, loser)]
        covered = _rgb(loser.border.color) == _rgb(winner.border.color) and (  # the colors Excel writes
            loser.style is winner.style or (all(single) and winner.style.thickness >= loser.style.thickness))
        pair = (winner.source, loser.source)  # sources name a whole line (the strokes of a double line once)
        if not covered and pair not in self.conflicts:
            self.conflicts.add(pair)
            self.fallback(loser.source[0], "border_conflict",
                          f"a {loser.style.value} border {_rgb(loser.border.color)} gives way to a "
                          f"{winner.style.value} border {_rgb(winner.border.color)} on the same cell edge")

    def borders(self, merges: tuple[xl.CellRange, ...]) -> tuple[xl.EdgeBorder, ...]:
        owners = {cell: merge for merge in merges for cell in merge.cells()}
        result, inside = [], {}
        for edge in self.edges.values():
            kind, row, col = edge.border.edge_key()
            before, after = ((row - 1, col), (row, col)) if kind == "horizontal" else ((row, col - 1), (row, col))
            merge = owners.get(before)
            if merge is not None and owners.get(after) == merge:
                inside.setdefault(edge.source, []).append(edge)
            else:
                result.append(edge.border)
        for (page, index), edges in inside.items():
            self.fallback(page, "border_in_merge", f"{len(edges)} edge(s) of a {edges[0].style.value} border lie "
                          "inside a merged piece")
            for edge in edges:
                kind, row, col = edge.border.edge_key()
                local = row - page * self.page_rows
                x1 = self.cols.starts[col]
                y1 = page * self.rows.length + self.rows.starts[local]
                if kind == "horizontal":
                    x2, y2 = self.cols.starts[col + 1], y1
                else:
                    x2, y2 = x1, page * self.rows.length + self.rows.starts[local + 1]
                self.drawings.append(((page, index), xl.Line(x1, y1, x2, y2, stroke_width_pt=edge.style.thickness,
                                                             color=edge.border.color, dash=edge.style.dash)))
        result.sort(key=lambda border: (border.edge_key(), border.side))
        return tuple(result)

    # --- shapes ------------------------------------------------------------------------

    def figure(self, page: int, members: list[tuple[int, object]]) -> list:
        items: dict[int | None, list] = {}
        for _, command in members:
            item = command.tag.scope(Kind.FIGURE_ITEM)
            items.setdefault(None if item is None else item.index, []).append(command)
        children = []
        for commands in items.values():
            item = commands[0].tag.scope(Kind.FIGURE_ITEM)
            kind = item.data.get("kind") if item is not None else None
            outline = commands[0]
            texts = [command for command in commands[1:] if isinstance(command, Text) and command.text]
            if kind in ("textbox", "diamond") and texts and isinstance(outline, (Rectangle, Polyline)):
                children.append(self.text_shape(page, outline, texts))
            elif kind == "label":
                children.extend(self.convert(command, page, item.data.get("align", "left")) for command in commands)
            else:
                children.extend(self.convert(command, page) for command in commands)
        return children

    def text_shape(self, page: int, outline, texts: list[Text]):
        frame = xl.TextFrame([[xl.Run(text.text)] for text in texts], font=_font(texts[0].style),
                             h_align="center", v_align="center")
        if isinstance(outline, Rectangle):
            return xl.Rect(*self.box(page, outline.x, outline.y, outline.width, outline.height),
                           corner_radius_pt=outline.corner_radius, stroke=outline.stroke,
                           stroke_width_pt=outline.stroke_width, color=outline.color, fill=outline.fill, text=frame)
        xs = [point.x for point in outline.points]
        ys = [point.y for point in outline.points]
        return xl.Diamond(*self.box(page, min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)),
                          stroke_width_pt=outline.width, color=outline.color, dash=outline.dash, text=frame)

    def convert(self, command, page: int, align: str = "left"):
        """Return the shape of one scene command in sheet pt, or None for a shape of no extent."""
        if isinstance(command, Line):
            start, end = self.point(page, command.x1, command.y1), self.point(page, command.x2, command.y2)
            if start == end:
                return self.drop(command, page)
            return xl.Line(*start, *end, stroke_width_pt=command.width, color=command.color, dash=command.dash)
        if isinstance(command, Polyline):
            points = [self.point(page, point.x, point.y) for point in command.points]
            distinct = len(set(points))
            if distinct < 2:
                return self.drop(command, page)
            if command.closed and distinct == 2:  # a closed shape of two points is the segment between them
                start = points[0]
                end = next(point for point in points if point != start)
                return xl.Line(*start, *end, stroke_width_pt=command.width, color=command.color, dash=command.dash)
            return xl.Polyline(points, closed=command.closed, stroke_width_pt=command.width,
                               color=command.color, dash=command.dash)
        if isinstance(command, Rectangle):
            x, y, width, height = self.box(page, command.x, command.y, command.width, command.height)
            if width == 0 or height == 0:
                if not command.stroke or (width == 0 and height == 0):
                    return self.drop(command, page)
                return xl.Line(x, y, x + width, y + height, stroke_width_pt=command.stroke_width,
                               color=command.color)
            return xl.Rect(x, y, width, height, corner_radius_pt=command.corner_radius, stroke=command.stroke,
                           stroke_width_pt=command.stroke_width, color=command.color, fill=command.fill)
        if isinstance(command, Circle):
            box = self.box(page, command.x - command.radius, command.y - command.radius,
                           2 * command.radius, 2 * command.radius)
            return xl.Ellipse(*box, stroke=command.stroke, stroke_width_pt=command.stroke_width,
                              color=command.color, fill=command.fill)
        if isinstance(command, RasterImage):
            data, image_format = _picture_data(command.data)
            return xl.Picture(*self.box(page, command.x, command.y, command.width, command.height),
                              data, image_format)
        if isinstance(command, Text):
            if not command.text:
                return None
            metrics = self.fonts.measure(self.fonts.normalize_text(command.text), command.style)
            bounds = transformed_text_bounds(command, Box(0, -metrics.ascent, metrics.width,
                                                          metrics.ascent + metrics.descent))
            box = self.box(page, bounds.x, bounds.y, bounds.width, bounds.height)
            if box[2] <= 0 or box[3] <= 0:
                return self.drop(command, page)
            frame = xl.TextFrame([[xl.Run(command.text)]], font=_font(command.style), h_align=align,
                                 v_align="center", rotation=_TURNED_ROTATION[command.quarter_turns])
            return xl.TextBox(*box, frame)
        raise XlsxError(f"unsupported drawing command {type(command).__name__}")

    def drop(self, command, page: int) -> None:
        self.dropped.append(f"{self.where(page)}: a {type(command).__name__} of no extent")
        return None

    def check_drawings(self) -> None:
        """Every shape lies inside its own page's grid (a margin drawing would land on the next page)."""
        width, height = self.cols.length, self.rows.length
        tolerance = 1e-6
        for (page, _), drawing in self.drawings:
            left, top, right, bottom = drawing.bounds()
            top_of_page = page * height
            if (left < -tolerance or right > width + tolerance or top < top_of_page - tolerance
                    or bottom > top_of_page + height + tolerance):
                raise XlsxError(f"{self.where(page)}: a {type(drawing).__name__} lies outside the page grid")

    # --- page setup, header and footer ---------------------------------------------

    def decoration(self, side: str) -> tuple[xl.HeaderFooter, float] | None:
        """Return the sheet's header or footer and its frame's distance from the paper edge.

        Every page of a sheet has the same decorations (``_sheet_runs``).
        """
        found = _decoration_key(self.pages[0], side)
        if found is None or found[2] is None:
            return None
        template, align, (font_name, size), y, height = found
        if not float(size).is_integer():
            raise XlsxError(f"sheet {self.name!r}: the {side} size {size:g} pt cannot be written; Excel's "
                            "header and footer text size must be a whole pt")
        parts: list = []
        for literal, name, spec, conversion in Formatter().parse(template):
            if literal:
                parts.append(literal)
            if name is None:
                continue
            if spec or conversion:
                raise XlsxError(f"sheet {self.name!r}: the {side} field {{{name}:{spec}}} has a format "
                                "specification, which Excel's header and footer cannot show")
            parts.append(xl.PageNumber() if name == "page" else str(self.total))
        merged: list = []
        for part in parts:
            if isinstance(part, str) and merged and isinstance(merged[-1], str):
                merged[-1] += part
            else:
                merged.append(part)
        if not merged:
            return None
        section = xl.HeaderSection(merged, font=xl.Font(font_name, size))
        distance = y if side == "header" else self.profile.height - y - height
        return xl.HeaderFooter(**{align: section}), max(0.0, distance)

    def page_setup(self, header, footer) -> xl.PageSetup:
        profile, grid = self.profile, self.grid
        try:
            paper, orientation = xl.paper_for_size(profile.width, profile.height)
        except ValueError as exc:
            raise XlsxError(f"sheet {self.name!r}: {exc}") from None
        left, top = grid.origin_x, grid.origin_y
        right = max(0.0, profile.width - left - self.columns * grid.pitch_x)
        bottom = max(0.0, profile.height - top - self.page_rows * grid.pitch_y)
        margins = xl.Margins(left, top, right, bottom,
                             header[1] if header else min(xl.DEFAULT_MARGINS.header, top),
                             footer[1] if footer else min(xl.DEFAULT_MARGINS.footer, bottom))
        return xl.PageSetup(paper, orientation, margins, first_page_number=self.first_number)

    def fit(self, sheet: xl.Sheet) -> xl.Sheet:
        """Print at the largest scale that keeps every page on one paper, at 100 % where the paper allows.

        The right and bottom margins only hold blank paper, so they shrink
        (never grow) until the pages fit at 100 % by ``_units.print_fit``; Excel
        aligns its header and footer sections with these margins, so each
        shrinks only as far as the smaller of the two needs, the top band's
        factor and the measured printed sizes (``full_scale_size_pt``). The
        grid's origin keeps the PDF's left and top margins.
        """
        page = sheet.page
        if print_fit(sheet, DEFAULT_FONT).scale < 100:
            tight = replace(sheet, page=replace(page, margins=replace(page.margins, right=0.0, bottom=0.0)))
            fit = print_fit(tight, DEFAULT_FONT)
            if fit.scale == 100:
                paper_width, paper_height = page.paper_size_pt
                width = math.fsum(excel_column_width_pt(width) for width in sheet.column_widths_pt)
                height = max(page_heights_pt(sheet.row_heights_pt, sheet.row_breaks))
                needs = [(width * fit.column_factor, height * fit.row_factor)]
                measured = full_scale_size_pt(sheet, DEFAULT_FONT)
                if measured is not None:
                    needs.append(measured)
                # whole hundredths, rounded down; just below a whole hundredth so that the print area,
                # computed back from the margin, is never 1 ulp short of the need
                right = math.floor((paper_width - page.margins.left - min(need[0] for need in needs)) * 100
                                   - _HUNDREDTH_GUARD) / 100
                bottom = math.floor((paper_height - page.margins.top - min(need[1] for need in needs)) * 100
                                    - _HUNDREDTH_GUARD) / 100
                margins = replace(page.margins, right=max(0.0, min(page.margins.right, right)),
                                  bottom=max(0.0, min(page.margins.bottom, bottom)))
                sheet = replace(sheet, page=replace(page, margins=margins))
        scale = print_fit(sheet, DEFAULT_FONT).scale
        if scale < 100:
            self.fallback(0, "print_scale", f"the pages print at {scale} %, not 100 %, so the cells print "
                          "smaller than the PDF's grid")
        return replace(sheet, page=replace(sheet.page, scale=scale))


def _parts(trace: Mapping) -> tuple:
    """The prefix and body part records of a placement or child block trace."""
    return (*trace.get("prefix", ()), *trace.get("parts", ()))


def _rgb(color) -> str:
    return "#" + "".join(f"{math.floor(component * 255 + 0.5):02X}" for component in color)


def _owners(page: ScenePage) -> list:
    """Name the placement that drew each command.

    Tag paths are unique within one placement; commands outside every
    placement (a page built by hand) share one name, so their tags alone
    tell their structures apart.
    """
    owners: list = [("page",)] * len(page.commands)
    for number, placement in enumerate(page.metadata.get("placements", ())):
        start, stop = placement["commands"]
        for index in range(start, stop):
            owners[index] = ("placement", number)
    return owners


def _decoration_indices(page: ScenePage) -> set[int]:
    indices = set()
    for record in page.metadata.get("decorations", {}).values():
        start, stop = record["commands"]
        indices.update(range(start, stop))
    return indices


def _unit_position(path: tuple[Scope, ...]) -> int | None:
    for position in range(len(path) - 1, -1, -1):
        scope = path[position]
        if scope.kind in _UNIT_KINDS and (scope.kind is not Kind.FRACTION
                                          or scope.part in ("numerator", "denominator")):
            return position
    return None


def _unit_key(place, path: tuple[Scope, ...]) -> tuple | None:
    position = _unit_position(path)
    return None if position is None else (place, path[:position + 1])


def _label_line(unit_path: tuple[Scope, ...]) -> int | None:
    """The display line of an equation label's piece, or None for any other piece."""
    if any(scope.kind is Kind.EQUATION_PART and scope.part == "label" for scope in unit_path):
        line = next((scope.index for scope in reversed(unit_path) if scope.kind is Kind.PARAGRAPH), None)
        return 0 if line is None else line
    return None


def _is_relation(unit_path: tuple[Scope, ...]) -> bool:
    return bool(unit_path) and unit_path[-1].kind is Kind.EQUATION_PART and unit_path[-1].part in (
        "relation", "result_relation")


def _alignment(unit_path: tuple[Scope, ...]) -> str:
    for scope in reversed(unit_path):
        if scope.kind is Kind.FRACTION:
            return "center"
        if scope.kind is Kind.EQUATION_PART:
            if scope.part == "term":
                align = scope.data.get("align")
                return align if align in ("left", "center", "right") else "left"
            return _EQUATION_ALIGN.get(scope.part, "left")
        if scope.kind in (Kind.CELL_LINES, Kind.PARAGRAPH, Kind.TABLE_CELL):
            align = scope.data.get("align")
            return align if align in ("left", "center", "right") else "left"
    return "left"


def _reading_extent(turns: int, box: Box) -> tuple[float, float]:
    """A box's extent along the reading direction (upward for +1 turns, so its coordinate is -y)."""
    if turns == 0:
        return box.x, box.right
    if turns == 1:
        return -box.bottom, -box.y
    return box.y, box.bottom


def _along(turns: int, x: float, y: float) -> float:
    return x if turns == 0 else -y if turns == 1 else y


def _cells(start: float, stop: float, pitch: float) -> tuple[int, int]:
    """Return the first and last cell an extent touches (a touch within float error is not a touch)."""
    first = math.floor(start / pitch + _CELL_EPSILON)
    last = math.ceil(stop / pitch - _CELL_EPSILON) - 1
    return first, max(first, last)


def _reading_order(piece: _Piece) -> tuple:
    if piece.turns == 0:
        return piece.page, 0, piece.first_row, piece.first_col
    return piece.page, 1, piece.first_col, -piece.last_row if piece.turns == 1 else piece.first_row


def _picture_data(data: bytes) -> tuple[bytes, str]:
    """Keep PNG and JPEG as they are; write any other image format as PNG."""
    with PILImage.open(BytesIO(data)) as image:
        image_format = image.format
        if image_format == "PNG":
            return data, "png"
        if image_format in ("JPEG", "MPO"):
            return data, "jpeg"
        converted = BytesIO()
        image.save(converted, "PNG")
    return converted.getvalue(), "png"
