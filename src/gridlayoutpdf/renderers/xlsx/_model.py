"""Immutable sheet model for the .xlsx writer.

The model knows nothing about ``ScenePage``. Rows and columns are 0-based and
colors are RGB tuples of three components in 0..1. Lengths are pt of two
kinds: positions and sizes of cells and drawings are measured with the
model's column widths and row heights (Excel's whole-pixel cells keep each
point at the same fraction of its cell), while line widths, font sizes,
margins, insets, corner radii and dash lengths are absolute pt.

Every dataclass validates on construction and raises ``ValueError``; nothing
is silently corrected. Sequences may be given as lists or tuples and are kept
as tuples; unordered collections (sets, mappings) are errors because their
order would reach the file.
"""

import math
import re
import struct
import unicodedata
from collections.abc import Mapping, Set
from dataclasses import KW_ONLY, dataclass, field
from io import BytesIO

from PIL import Image

from ._units import (
    EDGE_TOLERANCE_PT,
    EMU_PER_PT,
    MAX_COLUMN_WIDTH_CHARS,
    MAX_ROW_HEIGHT_PT,
    column_pixels,
    column_width_chars,
    dash_value,
    excel_row_height_pt,
    max_digit_width_px,
    pt_to_emu,
)
from ._xml import has_illegal_xml_characters, rgb_hex

Color = tuple[float, float, float]

MAX_COLUMNS = 16_384
MAX_ROWS = 1_048_576
MAX_CELL_TEXT = 32_767
MAX_FONT_NAME = 31  # Excel 16.0 opened a 31-character font name and refused 32
_INT32 = 2**31 - 1
# C0 and C1 controls and the Unicode line and paragraph separators.
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029]")


def _set(instance, name: str, value) -> None:
    object.__setattr__(instance, name, value)


def _finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _integer(value, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _integer_choice(value, name: str, choices: tuple[int, ...]) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in choices:
        raise ValueError(f"{name} must be one of {', '.join(map(str, choices))} (an int)")
    return value


def _boolean(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _choice(value, name: str, choices: tuple) -> object:
    if isinstance(value, bool) or value not in choices:
        raise ValueError(f"{name} must be one of {', '.join(map(repr, choices))}")
    return value


def _tuple(value, name: str) -> tuple:
    """Snapshot an ordered sequence; a generator's own order cannot be checked."""
    if isinstance(value, (str, bytes, bytearray, memoryview, Set, Mapping)) or not hasattr(value, "__iter__"):
        raise ValueError(f"{name} must be an ordered sequence such as a list or tuple")
    return tuple(value)


def _color(value, name: str) -> Color:
    color = tuple(_finite(component, name) for component in _tuple(value, name))
    if len(color) != 3 or any(not 0 <= component <= 1 for component in color):
        raise ValueError(f"{name} must contain three components between 0 and 1")
    return color


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _text(value, name: str, *, empty: bool = False, limit: int | None = None, controls: bool = True) -> str:
    """Check a string; ``limit`` counts UTF-16 units like Excel, ``controls=False`` rejects controls."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if not empty and not value:
        raise ValueError(f"{name} must not be empty")
    if has_illegal_xml_characters(value):
        raise ValueError(f"{name} contains a character that cannot be written to XML")
    if not controls and _CONTROL.search(value):
        raise ValueError(f"{name} {value!r} contains a control or line separator character")
    if limit is not None and _utf16_length(value) > limit:
        raise ValueError(f"{name} must be at most {limit} characters")
    return value


# SpreadsheetML reads _xHHHH_ in names and format codes as a character; such
# text is rejected there rather than escaped (Excel's handling is unmeasured).
_ENCODED_CHARACTER = re.compile("_x[0-9A-Fa-f]{4}_")


def _no_encoded_character(value: str, name: str) -> None:
    if _ENCODED_CHARACTER.search(value):
        raise ValueError(f"{name} {value!r} contains _xHHHH_, which Excel reads as an encoded character")


@dataclass(frozen=True, slots=True)
class Font:
    """A font by name; ``size`` is pt in 0.5 pt steps (FR-023).

    The name is written as is (Excel substitutes a font it does not have) and
    may have at most 31 characters, the most Excel 16.0 opened.
    """

    name: str
    size: float
    color: Color = (0.0, 0.0, 0.0)
    bold: bool = False
    italic: bool = False

    def __post_init__(self) -> None:
        _text(self.name, "font name", limit=MAX_FONT_NAME, controls=False)
        if not self.name.strip():
            raise ValueError("font name must not be blank")
        _no_encoded_character(self.name, "font name")
        size = _finite(self.size, "font size")
        if not 1 <= size <= 409 or not (size * 2).is_integer():
            raise ValueError("font size must be between 1 and 409 pt in 0.5 pt steps")
        _set(self, "size", size)
        _set(self, "color", _color(self.color, "font color"))
        _boolean(self.bold, "bold")
        _boolean(self.italic, "italic")


def _optional_font(value, name: str = "font") -> None:
    if value is not None and not isinstance(value, Font):
        raise ValueError(f"{name} must be a Font or None")


VERTICAL_ALIGNS = (None, "superscript", "subscript")


@dataclass(frozen=True, slots=True)
class Run:
    """A rich text run; ``font=None`` uses the cell (or text frame) font.

    Excel draws superscript and subscript runs at about 2/3 of the run's size
    (10.5 pt printed at 7.08 pt in Excel 16.0), so give them the size of the
    base text, not an already reduced script size.
    """

    text: str
    font: Font | None = None
    vert_align: str | None = None

    def __post_init__(self) -> None:
        _text(self.text, "run text")
        _optional_font(self.font)
        _choice(self.vert_align, "vert_align", VERTICAL_ALIGNS)


@dataclass(frozen=True, slots=True)
class RichText:
    """Runs written as one cell's rich text (subscripts and superscripts)."""

    runs: tuple[Run, ...]

    def __post_init__(self) -> None:
        runs = _tuple(self.runs, "runs")
        if not runs:
            raise ValueError("rich text needs at least one run")
        if not all(isinstance(run, Run) for run in runs):
            raise ValueError("rich text runs must be Run items")
        if _utf16_length("".join(run.text for run in runs)) > MAX_CELL_TEXT:
            raise ValueError(f"cell text must be at most {MAX_CELL_TEXT} characters")
        _set(self, "runs", runs)


# Built-in number formats that do not depend on the locale (ECMA-376 Part 1,
# 18.8.30); they are written by number. Any other code is a custom format.
BUILTIN_NUMBER_FORMATS = {
    "General": 0, "0": 1, "0.00": 2, "#,##0": 3, "#,##0.00": 4, "0%": 9, "0.00%": 10,
    "0.00E+00": 11, "@": 49,
}
MAX_CUSTOM_NUMBER_FORMATS = 206  # Excel 16.0 (ja-JP) opened 206 custom formats and refused 207
_BRACKETS = re.compile(
    r"(?i:black|blue|cyan|green|magenta|red|white|yellow|color(?:[1-9]|[1-4]\d|5[0-6]))"  # colors, Color1-56
    r"|(?:<=|>=|<>|<|>|=)-?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?"  # conditions
    r"|\$.*"  # currency and locale
    r"|(?i:h+|m+|s+)"  # elapsed time
    r"|(?i:dbnum|natnum)\d{1,2}",  # East Asian numerals
    re.DOTALL)


def _number_format(code) -> str:
    """Check the number format structure that Excel needs to open the file.

    Excel 16.0 refused to open workbooks with an unclosed quote or bracket.
    Quotes, brackets (colors, conditions, locales, elapsed time, DBNum and
    NatNum), backslash, ``_`` and ``*`` escapes, at most four sections and 255
    characters are checked here; other syntax errors are found only by Excel.
    """
    _text(code, "number_format", limit=255)
    _no_encoded_character(code, "number_format")
    sections, index = 1, 0
    while index < len(code):
        char = code[index]
        if char in ("\\", "_", "*"):
            if index + 1 >= len(code):
                raise ValueError(f"number_format {code!r} ends with {char!r} without its character")
            index += 2
            continue
        if char == '"':
            end = code.find('"', index + 1)
            if end < 0:
                raise ValueError(f"number_format {code!r} has an unclosed quote")
            index = end + 1
            continue
        if char == "[":
            end = code.find("]", index + 1)
            if end < 0:
                raise ValueError(f"number_format {code!r} has an unclosed [")
            if not _BRACKETS.fullmatch(code[index + 1:end]):
                raise ValueError(f"number_format {code!r} has an unknown [{code[index + 1:end]}]")
            index = end + 1
            continue
        if char == "]":
            raise ValueError(f"number_format {code!r} has a ] without [")
        if char == ";":
            sections += 1
        index += 1
    if sections > 4:
        raise ValueError(f"number_format {code!r} has more than four sections")
    return code


H_ALIGNS = ("left", "center", "right")
V_ALIGNS = ("top", "center", "bottom")
CELL_ROTATIONS = (0, 90, 270)  # counterclockwise degrees; Excel's textRotation 0, 90 and 180


@dataclass(frozen=True, slots=True)
class CellValue:
    """One cell's value and format.

    ``value`` is text, a number, ``RichText`` or ``None`` (a formatted blank
    cell). ``font=None`` uses the workbook default font and ``fill`` is the
    cell background. ``rotation`` turns the text counterclockwise by 0, 90
    (reads bottom to top) or 270 degrees (reads top to bottom), like
    ``TextFrame.rotation``; ``h_align`` and ``v_align`` stay in paper
    directions (Excel's alignment does not turn with the text).
    """

    row: int
    col: int
    value: str | float | RichText | None
    number_format: str | None = None
    font: Font | None = None
    h_align: str = "left"
    v_align: str = "center"
    rotation: int = 0
    fill: Color | None = None

    def __post_init__(self) -> None:
        _integer(self.row, "row", 0, MAX_ROWS - 1)
        _integer(self.col, "col", 0, MAX_COLUMNS - 1)
        value = self.value
        if isinstance(value, str):
            _text(value, "cell text", empty=True, limit=MAX_CELL_TEXT)
        elif value is not None and not isinstance(value, RichText):
            _set(self, "value", _finite(value, "cell value"))
        if self.number_format is not None:
            _number_format(self.number_format)
        _optional_font(self.font)
        _choice(self.h_align, "h_align", H_ALIGNS)
        _choice(self.v_align, "v_align", V_ALIGNS)
        _integer_choice(self.rotation, "rotation", CELL_ROTATIONS)
        if self.fill is not None:
            _set(self, "fill", _color(self.fill, "fill"))


@dataclass(frozen=True, slots=True)
class CellRange:
    """An inclusive block of at least two cells, 0-based."""

    first_row: int
    first_col: int
    last_row: int
    last_col: int

    def __post_init__(self) -> None:
        for name, high in (("first_row", MAX_ROWS - 1), ("first_col", MAX_COLUMNS - 1),
                           ("last_row", MAX_ROWS - 1), ("last_col", MAX_COLUMNS - 1)):
            _integer(getattr(self, name), name, 0, high)
        if self.last_row < self.first_row or self.last_col < self.first_col:
            raise ValueError("a cell range must not end before it starts")
        if self.last_row == self.first_row and self.last_col == self.first_col:
            raise ValueError("a merged range must span more than one cell")

    def cells(self):
        for row in range(self.first_row, self.last_row + 1):
            for col in range(self.first_col, self.last_col + 1):
                yield row, col


BORDER_STYLES = (
    "hair", "thin", "medium", "thick", "double", "dotted", "dashed", "dashDot", "dashDotDot",
    "mediumDashed", "mediumDashDot", "mediumDashDotDot", "slantDashDot",
)
SIDES = ("top", "bottom", "left", "right")
EdgeKey = tuple[str, int, int]


@dataclass(frozen=True, slots=True)
class EdgeBorder:
    """One side of one cell drawn with an Excel border style."""

    row: int
    col: int
    side: str
    style: str
    color: Color = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        _integer(self.row, "row", 0, MAX_ROWS - 1)
        _integer(self.col, "col", 0, MAX_COLUMNS - 1)
        _choice(self.side, "side", SIDES)
        _choice(self.style, "border style", BORDER_STYLES)
        _set(self, "color", _color(self.color, "border color"))

    def edge_key(self) -> EdgeKey:
        """Identify the physical edge: a cell's bottom is the next cell's top."""
        if self.side in ("top", "bottom"):
            return ("horizontal", self.row + (self.side == "bottom"), self.col)
        return ("vertical", self.row, self.col + (self.side == "right"))


def range_edges(cell_range: CellRange, side: str, style: str,
                color: Color = (0.0, 0.0, 0.0)) -> tuple[EdgeBorder, ...]:
    """Return one ``EdgeBorder`` per cell along a side of a (merged) range."""
    if not isinstance(cell_range, CellRange):
        raise ValueError("cell_range must be a CellRange")
    _choice(side, "side", SIDES)
    if side in ("top", "bottom"):
        row = cell_range.first_row if side == "top" else cell_range.last_row
        cells = [(row, col) for col in range(cell_range.first_col, cell_range.last_col + 1)]
    else:
        col = cell_range.first_col if side == "left" else cell_range.last_col
        cells = [(row, col) for row in range(cell_range.first_row, cell_range.last_row + 1)]
    return tuple(EdgeBorder(row, col, side, style, color) for row, col in cells)


PAPER_SIZES_PT = {"A4": (595.2756, 841.8898), "A3": (841.8898, 1190.5512)}  # portrait width, height
ORIENTATIONS = ("portrait", "landscape")
MAX_ROW_BREAKS = 1026  # Excel's documented limit of manual page breaks per sheet (not measured)


def paper_for_size(width_pt: float, height_pt: float, tolerance_pt: float = 1.0) -> tuple[str, str]:
    """Return (paper, orientation) of a page size, or raise for papers other than A4 and A3."""
    width, height = _finite(width_pt, "width_pt"), _finite(height_pt, "height_pt")
    tolerance = _finite(tolerance_pt, "tolerance_pt")
    if not 0 <= tolerance <= 10:
        raise ValueError("tolerance_pt must be between 0 and 10 pt")
    for paper, (short, long) in PAPER_SIZES_PT.items():
        for orientation, size in (("portrait", (short, long)), ("landscape", (long, short))):
            if abs(width - size[0]) <= tolerance and abs(height - size[1]) <= tolerance:
                return paper, orientation
    raise ValueError(f"a {width} x {height} pt page is not A4 or A3 (within {tolerance} pt)")


@dataclass(frozen=True, slots=True)
class Margins:
    """Print margins in pt; ``header``/``footer`` are from the paper edge."""

    left: float
    top: float
    right: float
    bottom: float
    header: float
    footer: float

    def __post_init__(self) -> None:
        for name in ("left", "top", "right", "bottom", "header", "footer"):
            value = _finite(getattr(self, name), f"{name} margin")
            if value < 0:
                raise ValueError(f"{name} margin must not be negative")
            _set(self, name, value)


# Excel's "Normal" margins: 0.7 in left/right, 0.75 in top/bottom, 0.3 in header/footer.
DEFAULT_MARGINS = Margins(left=50.4, top=54, right=50.4, bottom=54, header=21.6, footer=21.6)


@dataclass(frozen=True, slots=True)
class PageSetup:
    """Print settings; ``scale`` is Excel's percent zoom (10-400).

    ``first_page_number=None`` lets Excel number pages from 1 automatically.
    Excel accepted 1-32767 (32768 turned into "automatic" in Excel 16.0).
    """

    paper: str = "A4"
    orientation: str = "portrait"
    margins: Margins = DEFAULT_MARGINS
    scale: int = 100
    first_page_number: int | None = None
    print_gridlines: bool = False

    def __post_init__(self) -> None:
        _choice(self.paper, "paper", tuple(PAPER_SIZES_PT))
        _choice(self.orientation, "orientation", ORIENTATIONS)
        if not isinstance(self.margins, Margins):
            raise ValueError("margins must be Margins")
        _integer(self.scale, "scale", 10, 400)
        if self.first_page_number is not None:
            _integer(self.first_page_number, "first_page_number", 1, 32767)
        _boolean(self.print_gridlines, "print_gridlines")
        width, height = self.paper_size_pt
        margins = self.margins
        if margins.left + margins.right >= width or margins.top + margins.bottom >= height:
            raise ValueError("margins leave no printable area on the paper")

    @property
    def paper_size_pt(self) -> tuple[float, float]:
        """Return the paper (width, height) in pt for the orientation."""
        width, height = PAPER_SIZES_PT[self.paper]
        return (width, height) if self.orientation == "portrait" else (height, width)

    @property
    def printable_size_pt(self) -> tuple[float, float]:
        """Return the (width, height) inside the margins in pt."""
        width, height = self.paper_size_pt
        margins = self.margins
        return width - margins.left - margins.right, height - margins.top - margins.bottom


@dataclass(frozen=True, slots=True)
class PageNumber:
    """The page number field (``&P``), counted from ``PageSetup.first_page_number``."""


@dataclass(frozen=True, slots=True)
class SheetPageCount:
    """The number of pages of this sheet (``&N``).

    It is not the total of a report split over several sheets; write that
    total as text.
    """


HeaderPart = str | PageNumber | SheetPageCount
_HEADER_STYLES = {  # (bold, italic); English style names worked in Japanese Excel 16.0
    (False, False): "Regular", (True, False): "Bold", (False, True): "Italic", (True, True): "Bold Italic",
}
MAX_HEADER_FOOTER = 255


@dataclass(frozen=True, slots=True)
class HeaderSection:
    """One of the left, center and right sections of a header or footer.

    ``parts`` are plain text (``&`` is escaped on writing), ``PageNumber()``
    and ``SheetPageCount()``. ``font`` must have a whole pt size and a name
    without ``"``, ``,`` or ``&``: Excel's header codes cannot express anything
    else (``&10.5`` printed size 10 followed by ".5" in Excel 16.0).
    """

    parts: tuple[HeaderPart, ...]
    font: Font | None = None

    def __post_init__(self) -> None:
        parts = _tuple(self.parts, "header parts")
        if not parts:
            raise ValueError("a header section needs at least one part")
        for part in parts:
            if isinstance(part, str):
                _text(part, "header text")
            elif not isinstance(part, (PageNumber, SheetPageCount)):
                raise ValueError("header parts must be text, PageNumber() or SheetPageCount()")
        _set(self, "parts", parts)
        font = self.font
        _optional_font(font)
        if font is not None:
            if not font.size.is_integer():
                raise ValueError("a header font size must be a whole pt")
            if any(char in font.name for char in '",&') or font.name == "-":
                raise ValueError('a header font name must not contain ", "," or "&" nor be "-" (the default font)')

    def code(self) -> str:
        """Return Excel's header code for this section."""
        font = self.font
        if font is None:
            prefix = ""
            reset = '&"-,Regular"'
        else:
            reset = f'&"{font.name},{_HEADER_STYLES[(font.bold, font.italic)]}"'
            # The font code ends with a quote, so text starting with a digit or A-F stays text.
            prefix = f"&{int(font.size)}&K{rgb_hex(font.color)}{reset}"
        pieces = [prefix]
        previous_field = False
        for part in self.parts:
            if isinstance(part, PageNumber):
                pieces.append("&P")
            elif isinstance(part, SheetPageCount):
                pieces.append("&N")
            else:
                # Excel reads "&P+1" and "&P-1" as page arithmetic; a font code ends the field.
                if previous_field and part[0] in "+-":
                    pieces.append(reset)
                pieces.append(part.replace("&", "&&"))
            previous_field = not isinstance(part, str)
        return "".join(pieces)


@dataclass(frozen=True, slots=True)
class HeaderFooter:
    """Left, center and right sections of a page header or footer."""

    left: HeaderSection | None = None
    center: HeaderSection | None = None
    right: HeaderSection | None = None

    def __post_init__(self) -> None:
        sections = (self.left, self.center, self.right)
        if all(section is None for section in sections):
            raise ValueError("a header or footer needs at least one section")
        for section in sections:
            if section is not None and not isinstance(section, HeaderSection):
                raise ValueError("header and footer sections must be HeaderSection or None")
        if _utf16_length(self.code()) > MAX_HEADER_FOOTER:
            raise ValueError(f"a header or footer must be at most {MAX_HEADER_FOOTER} characters of Excel code")

    def code(self) -> str:
        return "".join(f"&{key}{section.code()}" for key, section in
                       (("L", self.left), ("C", self.center), ("R", self.right)) if section is not None)


# --- drawings ----------------------------------------------------------------
# Drawing coordinates are pt from the top-left corner of cell A1, measured with
# the model's column widths and row heights (y grows downward).

MAX_LINE_WIDTH_PT = 1584  # DrawingML ST_LineWidth: 20116800 EMU
ARROW_KINDS = ("triangle", "stealth", "diamond", "oval", "arrow")
ARROW_SIZES = ("sm", "med", "lg")
TEXT_FRAME_ROTATIONS = (0, 90, 180, 270)  # counterclockwise degrees


def _point(value, name: str) -> tuple[float, float]:
    pair = _tuple(value, name)
    if len(pair) != 2:
        raise ValueError(f"{name} must be an (x, y) pair")
    return _finite(pair[0], f"{name} x"), _finite(pair[1], f"{name} y")


def _box(instance) -> None:
    for name in ("x", "y", "width", "height"):
        _set(instance, name, _finite(getattr(instance, name), name))
    if instance.width <= 0 or instance.height <= 0:
        raise ValueError("width and height must be positive")


def _stroke(instance) -> None:
    """Check the outline: DrawingML stores the width in whole EMU and dashes in 1/1000 % of it."""
    width = _finite(instance.stroke_width_pt, "stroke_width_pt")
    if not 0 < width <= MAX_LINE_WIDTH_PT or pt_to_emu(width) < 1:
        raise ValueError(f"stroke_width_pt must be at least 1 EMU (1/12700 pt) and at most {MAX_LINE_WIDTH_PT} pt")
    _set(instance, "stroke_width_pt", width)
    _set(instance, "color", _color(instance.color, "color"))
    lengths = tuple(_finite(length, "dash") for length in _tuple(instance.dash, "dash"))
    for length in lengths:
        # The value written (1/1000 % of the line width) must be a whole number from 1 to 2^31 - 1.
        if not 0 < length <= width * 21_475 or not 1 <= dash_value(length, width) <= _INT32:
            raise ValueError("dash lengths must be between about 0.00001 and 21474 times the stroke width")
    _set(instance, "dash", lengths)


def _area(instance) -> None:
    _box(instance)
    _boolean(instance.stroke, "stroke")
    _stroke(instance)
    if instance.fill is not None:
        _set(instance, "fill", _color(instance.fill, "fill"))
    if instance.text is not None and not isinstance(instance.text, TextFrame):
        raise ValueError("text must be a TextFrame or None")
    frame = instance.text
    has_text = frame is not None and any(run.text for paragraph in frame.paragraphs for run in paragraph)
    if not instance.stroke and instance.fill is None and not has_text:
        raise ValueError("a shape needs a stroke, a fill or text")


@dataclass(frozen=True, slots=True)
class Arrowhead:
    """A DrawingML line end: ``kind`` and its width and length (sm, med, lg)."""

    kind: str = "triangle"
    width: str = "med"
    length: str = "med"

    def __post_init__(self) -> None:
        _choice(self.kind, "arrowhead kind", ARROW_KINDS)
        _choice(self.width, "arrowhead width", ARROW_SIZES)
        _choice(self.length, "arrowhead length", ARROW_SIZES)


@dataclass(frozen=True, slots=True)
class TextFrame:
    """Text of a shape: paragraphs of runs, alignment and rotation.

    ``font`` is used by runs without one. Each paragraph is one line of runs
    (an empty paragraph is an empty line); run text must not contain control
    characters such as newlines or tabs. ``rotation`` turns the text
    counterclockwise (90 reads bottom to top, 270 top to bottom).
    ``h_align`` and ``v_align`` follow the reading direction of the turned
    text: at 90 degrees "top" is the left side of the box on paper.
    ``insets_pt`` are (left, top, right, bottom). ``wrap=False`` keeps every
    paragraph on one line.
    """

    paragraphs: tuple[tuple[Run, ...], ...]
    _: KW_ONLY
    font: Font
    h_align: str = "left"
    v_align: str = "top"
    rotation: int = 0
    insets_pt: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    wrap: bool = False

    def __post_init__(self) -> None:
        paragraphs = tuple(_tuple(paragraph, "paragraph") for paragraph in _tuple(self.paragraphs, "paragraphs"))
        if not paragraphs:
            raise ValueError("a text frame needs at least one paragraph")
        for paragraph in paragraphs:
            for run in paragraph:
                if not isinstance(run, Run):
                    raise ValueError("paragraphs must contain Run items")
                _text(run.text, "text frame run", controls=False)
        _set(self, "paragraphs", paragraphs)
        if not isinstance(self.font, Font):
            raise ValueError("a text frame needs a Font")
        _choice(self.h_align, "h_align", H_ALIGNS)
        _choice(self.v_align, "v_align", V_ALIGNS)
        _integer_choice(self.rotation, "rotation", TEXT_FRAME_ROTATIONS)
        insets = tuple(_finite(inset, "inset") for inset in _tuple(self.insets_pt, "insets_pt"))
        if len(insets) != 4 or any(not 0 <= inset <= _INT32 / EMU_PER_PT for inset in insets):
            raise ValueError("insets_pt must be four lengths between 0 and 169093 pt")
        _set(self, "insets_pt", insets)
        _boolean(self.wrap, "wrap")


Box = tuple[float, float, float, float]  # left, top, right, bottom


@dataclass(frozen=True, slots=True)
class Line:
    """A straight line; ``start_arrow`` is at (x1, y1), ``end_arrow`` at (x2, y2).

    ``dash`` holds on/off lengths in pt; ``()`` is a solid line, and an odd
    number of lengths repeats as in PDF.
    """

    x1: float
    y1: float
    x2: float
    y2: float
    _: KW_ONLY
    stroke_width_pt: float = 0.5
    color: Color = (0.0, 0.0, 0.0)
    dash: tuple[float, ...] = ()
    start_arrow: Arrowhead | None = None
    end_arrow: Arrowhead | None = None

    def __post_init__(self) -> None:
        for name in ("x1", "y1", "x2", "y2"):
            _set(self, name, _finite(getattr(self, name), name))
        if (self.x1, self.y1) == (self.x2, self.y2):
            raise ValueError("a line needs two different end points")
        _stroke(self)
        for name in ("start_arrow", "end_arrow"):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), Arrowhead):
                raise ValueError(f"{name} must be an Arrowhead or None")

    def bounds(self) -> Box:
        return min(self.x1, self.x2), min(self.y1, self.y2), max(self.x1, self.x2), max(self.y1, self.y2)


@dataclass(frozen=True, slots=True)
class Polyline:
    """Connected straight segments; only a closed polyline can be filled."""

    points: tuple[tuple[float, float], ...]
    _: KW_ONLY
    closed: bool = False
    stroke_width_pt: float = 0.5
    color: Color = (0.0, 0.0, 0.0)
    fill: Color | None = None
    dash: tuple[float, ...] = ()
    stroke: bool = True

    def __post_init__(self) -> None:
        points = tuple(_point(point, "point") for point in _tuple(self.points, "points"))
        if len(points) < 2:
            raise ValueError("a polyline needs at least two points")
        _set(self, "points", points)
        _boolean(self.closed, "closed")
        if self.closed and len(points) < 3:
            raise ValueError("a closed polyline needs at least three points")
        _boolean(self.stroke, "stroke")
        _stroke(self)
        if self.fill is not None:
            if not self.closed:
                raise ValueError("only a closed polyline can have a fill")
            _set(self, "fill", _color(self.fill, "fill"))
        if not self.stroke and self.fill is None:
            raise ValueError("a polyline needs a stroke or a fill")
        left, top, right, bottom = self.bounds()
        if left == right and top == bottom:
            raise ValueError("a polyline needs points at different positions")

    def bounds(self) -> Box:
        xs = [x for x, _ in self.points]
        ys = [y for _, y in self.points]
        return min(xs), min(ys), max(xs), max(ys)


def _box_bounds(instance) -> Box:
    return instance.x, instance.y, instance.x + instance.width, instance.y + instance.height


@dataclass(frozen=True, slots=True)
class Rect:
    """A rectangle; ``corner_radius_pt > 0`` rounds its corners."""

    x: float
    y: float
    width: float
    height: float
    _: KW_ONLY
    corner_radius_pt: float = 0.0
    stroke: bool = True
    stroke_width_pt: float = 0.5
    color: Color = (0.0, 0.0, 0.0)
    fill: Color | None = None
    text: TextFrame | None = None
    dash: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        _area(self)
        radius = _finite(self.corner_radius_pt, "corner_radius_pt")
        if not 0 <= radius <= min(self.width, self.height) / 2:
            raise ValueError("corner_radius_pt must be between 0 and half of the shorter side")
        _set(self, "corner_radius_pt", radius)

    bounds = _box_bounds


@dataclass(frozen=True, slots=True)
class Ellipse:
    """An ellipse inscribed in its box."""

    x: float
    y: float
    width: float
    height: float
    _: KW_ONLY
    stroke: bool = True
    stroke_width_pt: float = 0.5
    color: Color = (0.0, 0.0, 0.0)
    fill: Color | None = None
    text: TextFrame | None = None
    dash: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        _area(self)

    bounds = _box_bounds


@dataclass(frozen=True, slots=True)
class Diamond:
    """A diamond touching the middles of its box's sides."""

    x: float
    y: float
    width: float
    height: float
    _: KW_ONLY
    stroke: bool = True
    stroke_width_pt: float = 0.5
    color: Color = (0.0, 0.0, 0.0)
    fill: Color | None = None
    text: TextFrame | None = None
    dash: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        _area(self)

    bounds = _box_bounds


@dataclass(frozen=True, slots=True)
class TextBox:
    """Text without an outline or fill."""

    x: float
    y: float
    width: float
    height: float
    text: TextFrame

    def __post_init__(self) -> None:
        _box(self)
        if not isinstance(self.text, TextFrame):
            raise ValueError("a text box needs a TextFrame")

    bounds = _box_bounds


def _jpeg_frame_end(data: bytes, start: int) -> int | None:
    """Return the index after the EOI of the JPEG frame starting at ``start``, or None if it is cut.

    Markers are followed from SOI: segments by their length, and after each
    SOS the entropy-coded data up to the next marker (FF00 and RST markers are
    part of the data). Stray bytes between segments are skipped, as libjpeg
    does. Data after EOI (camera trailers) is not looked at.
    """
    if data[start:start + 2] != b"\xff\xd8":
        return None
    index, size = start + 2, len(data)
    while True:
        if index < size and data[index] != 0xFF:  # stray bytes before a marker, skipped as libjpeg does
            index = data.find(b"\xff", index)
            if index < 0:
                return None
        if index >= size:
            return None
        while index < size and data[index] == 0xFF:  # fill bytes before a marker
            index += 1
        if index >= size:
            return None
        marker = data[index]
        index += 1
        if marker == 0xD9:
            return index
        if marker == 0x00:  # FF 00 between segments is not a marker; libjpeg skips it
            continue
        if marker == 0xD8:  # a second SOI inside a frame: not one complete frame
            return None
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > size:
            return None
        length = int.from_bytes(data[index:index + 2], "big")
        end = index + length
        if length < 2 or end > size:
            return None
        index = end
        if marker == 0xDA:  # entropy-coded data until a marker that is not FF00 or RST
            while index < size:
                if data[index] != 0xFF:
                    index += 1
                    continue
                following = data[index + 1] if index + 1 < size else None
                if following is None:
                    return None
                if following == 0x00 or 0xD0 <= following <= 0xD7:
                    index += 2
                elif following == 0xFF:
                    index += 1
                else:
                    break


def _complete_jpeg_frames(data: bytes) -> int:
    """Count the complete JPEG frames from the start, each beginning at the next SOI after the last EOI.

    An MPO stores its frames after one another, possibly with other bytes
    between them.
    """
    count, start = 0, 0
    while True:
        end = _jpeg_frame_end(data, start)
        if end is None:
            return count
        count += 1
        start = data.find(b"\xff\xd8\xff", end)
        if start < 0:
            return count


# Pillow's names for each format; JPEG files with an MPO extension (camera photos) are JPEG.
_IMAGE_FORMATS = {"png": ("PNG",), "jpeg": ("JPEG", "MPO")}


@dataclass(frozen=True, slots=True)
class Picture:
    """An encoded PNG or JPEG image stretched over its box.

    ``data`` (bytes, bytearray or memoryview, kept as bytes) must decode with
    Pillow as the named format, so Excel does not show a broken picture.
    """

    x: float
    y: float
    width: float
    height: float
    data: bytes
    format: str

    def __post_init__(self) -> None:
        _box(self)
        _choice(self.format, "image format", tuple(_IMAGE_FORMATS))
        if not isinstance(self.data, (bytes, bytearray, memoryview)) or not self.data:
            raise ValueError("data must contain image bytes")
        data = bytes(self.data)
        try:
            with Image.open(BytesIO(data)) as image:
                found = image.format
                frames = getattr(image, "n_frames", 1)
                image.load()
            # verify() checks the PNG chunk checksums and does not follow ImageFile.LOAD_TRUNCATED_IMAGES.
            with Image.open(BytesIO(data)) as image:
                image.verify()
        except (OSError, SyntaxError, ValueError, EOFError, struct.error, Image.DecompressionBombError) as exc:
            raise ValueError(f"data is not a readable {self.format} image: {exc}") from exc
        if found not in _IMAGE_FORMATS[self.format]:
            raise ValueError(f"data is a {found} image, not {self.format}")
        # Pillow's verify() does not check JPEG data, and ImageFile.LOAD_TRUNCATED_IMAGES lets load()
        # accept a cut file; every frame of a complete JPEG (or MPO) reaches its EOI marker.
        if self.format == "jpeg" and _complete_jpeg_frames(data) < frames:
            raise ValueError("data is a JPEG image whose markers do not reach its end marker "
                             "(the file is cut, or its marker layout is not supported)")
        _set(self, "data", data)

    bounds = _box_bounds


@dataclass(frozen=True, slots=True)
class Group:
    """Drawings grouped into one Excel shape group (groups may nest)."""

    children: tuple["Drawing", ...]

    def __post_init__(self) -> None:
        children = _tuple(self.children, "children")
        if not children:
            raise ValueError("a group needs at least one drawing")
        if not all(isinstance(child, DRAWING_TYPES) for child in children):
            raise ValueError("group children must be drawing items")
        _set(self, "children", children)

    def bounds(self) -> Box:
        boxes = [child.bounds() for child in self.children]
        return (min(box[0] for box in boxes), min(box[1] for box in boxes),
                max(box[2] for box in boxes), max(box[3] for box in boxes))


Drawing = Line | Polyline | Rect | Ellipse | Diamond | TextBox | Picture | Group
DRAWING_TYPES = (Line, Polyline, Rect, Ellipse, Diamond, TextBox, Picture, Group)


@dataclass(frozen=True, slots=True)
class Sheet:
    """One worksheet; column widths and row heights are pt.

    Excel shows them rounded to whole pixels (``_units``). Row breaks are rows
    a manual page break goes above. The print area is always every cell.
    """

    name: str
    column_widths_pt: tuple[float, ...]
    row_heights_pt: tuple[float, ...]
    cells: tuple[CellValue, ...] = ()
    merges: tuple[CellRange, ...] = ()
    borders: tuple[EdgeBorder, ...] = ()
    row_breaks: tuple[int, ...] = ()
    page: PageSetup = PageSetup()
    header: HeaderFooter | None = None
    footer: HeaderFooter | None = None
    drawings: tuple[Drawing, ...] = ()
    show_gridlines: bool = True

    def __post_init__(self) -> None:
        _set(self, "name", validate_sheet_name(self.name))
        widths = tuple(_finite(width, "column width") for width in _tuple(self.column_widths_pt, "column_widths_pt"))
        heights = tuple(_finite(height, "row height") for height in _tuple(self.row_heights_pt, "row_heights_pt"))
        if not 1 <= len(widths) <= MAX_COLUMNS:
            raise ValueError(f"a sheet must have between 1 and {MAX_COLUMNS} columns")
        if not 1 <= len(heights) <= MAX_ROWS:
            raise ValueError(f"a sheet must have between 1 and {MAX_ROWS} rows")
        for width in widths:
            column_pixels(width)
        for height in heights:
            if excel_row_height_pt(height) > MAX_ROW_HEIGHT_PT:
                raise ValueError(f"row height {height} pt is above Excel's {MAX_ROW_HEIGHT_PT} pt")
        _set(self, "column_widths_pt", widths)
        _set(self, "row_heights_pt", heights)
        owners = self._check_merges()
        self._check_cells(owners)
        self._check_borders(owners)
        self._check_row_breaks()
        if not isinstance(self.page, PageSetup):
            raise ValueError("page must be a PageSetup")
        for name in ("header", "footer"):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), HeaderFooter):
                raise ValueError(f"{name} must be a HeaderFooter or None")
        _boolean(self.show_gridlines, "show_gridlines")
        self._check_drawings()

    @property
    def width_pt(self) -> float:
        """The sum of the model's column widths (not Excel's pixel widths)."""
        return math.fsum(self.column_widths_pt)

    @property
    def height_pt(self) -> float:
        """The sum of the model's row heights (not Excel's pixel heights)."""
        return math.fsum(self.row_heights_pt)

    def _check_inside(self, row: int, col: int, what: str) -> None:
        if row >= len(self.row_heights_pt) or col >= len(self.column_widths_pt):
            raise ValueError(f"{what} ({row}, {col}) is outside the sheet's rows and columns")

    def _check_merges(self) -> dict[tuple[int, int], CellRange]:
        """Return the merged range that covers each merged cell."""
        merges = _tuple(self.merges, "merges")
        owners: dict[tuple[int, int], CellRange] = {}
        numbers: dict[tuple[int, int], int] = {}
        for number, merge in enumerate(merges):
            if not isinstance(merge, CellRange):
                raise ValueError("merges must contain CellRange items")
            self._check_inside(merge.last_row, merge.last_col, "merged range end")
            for cell in merge.cells():
                if numbers.setdefault(cell, number) != number:
                    raise ValueError(f"merged ranges {owners[cell]} and {merge} overlap")
                owners[cell] = merge
        _set(self, "merges", merges)
        return owners

    def _check_cells(self, owners: dict[tuple[int, int], CellRange]) -> None:
        cells = _tuple(self.cells, "cells")
        seen = set()
        for cell in cells:
            if not isinstance(cell, CellValue):
                raise ValueError("cells must contain CellValue items")
            self._check_inside(cell.row, cell.col, "cell")
            position = (cell.row, cell.col)
            if position in seen:
                raise ValueError(f"cell {position} is given more than once")
            seen.add(position)
            merge = owners.get(position)
            if cell.value is not None and merge is not None and position != (merge.first_row, merge.first_col):
                raise ValueError(f"cell {position} has a value inside {merge} but not at its top-left cell")
        _set(self, "cells", cells)

    def _check_borders(self, owners: dict[tuple[int, int], CellRange]) -> None:
        borders = _tuple(self.borders, "borders")
        seen: dict[EdgeKey, EdgeBorder] = {}
        for border in borders:
            if not isinstance(border, EdgeBorder):
                raise ValueError("borders must contain EdgeBorder items")
            self._check_inside(border.row, border.col, "border cell")
            key = border.edge_key()
            if key in seen:
                raise ValueError(f"{border} and {seen[key]} describe the same edge")
            seen[key] = border
            kind, row, col = key
            before, after = ((row - 1, col), (row, col)) if kind == "horizontal" else ((row, col - 1), (row, col))
            merge = owners.get(before)
            if merge is not None and owners.get(after) == merge:
                raise ValueError(f"{border} lies inside the merged range {merge}")
        _set(self, "borders", borders)

    def _check_row_breaks(self) -> None:
        breaks = _tuple(self.row_breaks, "row_breaks")
        if len(breaks) > MAX_ROW_BREAKS:
            raise ValueError(f"a sheet can have at most {MAX_ROW_BREAKS} manual row breaks")
        previous = 0
        for row in breaks:
            if isinstance(row, bool) or not isinstance(row, int) or not previous < row < len(self.row_heights_pt):
                raise ValueError(
                    "row breaks must be increasing rows between 1 and the last row (a break goes above its row)")
            previous = row
        _set(self, "row_breaks", breaks)

    def _check_drawings(self) -> None:
        drawings = _tuple(self.drawings, "drawings")
        width, height = self.width_pt, self.height_pt
        tolerance = EDGE_TOLERANCE_PT  # float error allowed when a drawing touches the sheet's edge
        for drawing in drawings:
            if not isinstance(drawing, DRAWING_TYPES):
                raise ValueError("drawings must contain drawing items")
            left, top, right, bottom = drawing.bounds()
            if left < -tolerance or top < -tolerance or right > width + tolerance or bottom > height + tolerance:
                raise ValueError(f"{type(drawing).__name__} at ({left}, {top})-({right}, {bottom}) pt "
                                 f"is outside the sheet's {width} x {height} pt")
        _set(self, "drawings", drawings)


_FORBIDDEN_IN_SHEET_NAME = set("[]:*?/\\")


def validate_sheet_name(name: str) -> str:
    """Check Excel's sheet name rules; never rename.

    Control characters are rejected too: Excel's own dialog does not accept
    them, although COM and files with tabs or newlines opened.
    """
    _text(name, "sheet name", limit=31, controls=False)
    _no_encoded_character(name, "sheet name")
    if _FORBIDDEN_IN_SHEET_NAME & set(name):
        raise ValueError(f"sheet name {name!r} contains one of []:*?/\\")
    if name.startswith("'") or name.endswith("'"):
        raise ValueError(f"sheet name {name!r} must not start or end with an apostrophe")
    return name


def sheet_name_key(name: str) -> str:
    """Return the comparison key for Excel's duplicate sheet name check.

    Excel ignores case and character width (A/Ａ, ア/ｱ, ß/SS, ①/1 and ﬁ/fi
    were rejected as duplicates in Excel 16.0). NFKC with case folding covers
    every measured pair; it is stricter than Excel for a few compatibility
    characters (㌔/キロ, Ⅰ/I), which then raise instead of being accepted.
    """
    if not isinstance(name, str):
        raise ValueError("a sheet name must be a string")
    return unicodedata.normalize("NFKC", name).casefold()


@dataclass(frozen=True, slots=True)
class Workbook:
    """Ordered sheets; ``default_font`` is Excel's Normal style font.

    The Normal font sets the unit of column widths, so only fonts whose digit
    width was measured in Excel are accepted (see ``_units``), in their plain
    black style.
    """

    sheets: tuple[Sheet, ...]
    default_font: Font = field(default_factory=lambda: Font("游ゴシック", 11))

    def __post_init__(self) -> None:
        sheets = _tuple(self.sheets, "sheets")
        if not sheets:
            raise ValueError("a workbook must have at least one sheet")
        font = self.default_font
        if not isinstance(font, Font):
            raise ValueError("default_font must be a Font")
        if font.bold or font.italic or font.color != (0.0, 0.0, 0.0):
            raise ValueError("default_font must be plain black: only that style's digit width was measured")
        max_digit_width_px(font)
        names: dict[str, str] = {}
        custom_formats: set[str] = set()
        for sheet in sheets:
            if not isinstance(sheet, Sheet):
                raise ValueError("sheets must contain Sheet items")
            key = sheet_name_key(sheet.name)
            if key in names:
                raise ValueError(
                    f"sheet name {sheet.name!r} is used twice: Excel treats it as {names[key]!r}")
            names[key] = sheet.name
            for width in sheet.column_widths_pt:
                if column_width_chars(width, font) > MAX_COLUMN_WIDTH_CHARS:
                    raise ValueError(f"column width {width} pt is above Excel's 255 characters")
            custom_formats.update(cell.number_format for cell in sheet.cells
                                  if cell.number_format is not None
                                  and cell.number_format not in BUILTIN_NUMBER_FORMATS)
        if len(custom_formats) > MAX_CUSTOM_NUMBER_FORMATS:
            raise ValueError(f"a workbook can have at most {MAX_CUSTOM_NUMBER_FORMATS} custom number formats "
                             f"(Excel would not open it); this one has {len(custom_formats)}")
        _set(self, "sheets", sheets)
