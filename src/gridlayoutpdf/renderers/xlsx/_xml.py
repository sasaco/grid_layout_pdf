"""Small, deterministic XML text helpers shared by the part writers."""

import math
import re

# XML 1.0 forbids C0 controls except tab, newline and carriage return, lone
# surrogates and U+FFFE/U+FFFF. The model rejects them before writing.
_ILLEGAL_XML = re.compile("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\ud800-\\udfff\\ufffe\\uffff]")
# An underscore that a reader would take as the start of _xHHHH_, also when the
# closing underscore comes from the _x000D_ written for a following CR.
_SPREADSHEET_ESCAPE = re.compile("_(?=x[0-9A-Fa-f]{4}(?:_|\r))")

XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def has_illegal_xml_characters(text: str) -> bool:
    return _ILLEGAL_XML.search(text) is not None


def escape_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_spreadsheet_text(text: str) -> str:
    """Escape SpreadsheetML string text (shared strings, header and footer).

    SpreadsheetML reads ``_xHHHH_`` as the character U+HHHH (ECMA-376 Part 1,
    22.9.2.19), so a literal one is written as ``_x005F_xHHHH_``. A carriage
    return would become a newline by XML end-of-line handling, so it is
    written as ``_x000D_``.
    """
    return escape_text(_SPREADSHEET_ESCAPE.sub("_x005F_", text).replace("\r", "_x000D_"))


def escape_attribute(text: str) -> str:
    return (escape_text(text).replace('"', "&quot;").replace("\n", "&#10;")
            .replace("\r", "&#13;").replace("\t", "&#9;"))


def rgb_hex(color: tuple[float, float, float]) -> str:
    """Return RRGGBB for components in 0..1, rounding halves up."""
    return "".join(f"{math.floor(component * 255 + 0.5):02X}" for component in color)


def number(value: float) -> str:
    """Return the shortest round-tripping decimal without a trailing ``.0``."""
    if not math.isfinite(value):
        raise ValueError("XML numbers must be finite")
    if float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def element(name: str, attributes: tuple[tuple[str, object], ...] = (), body: str | None = None) -> str:
    """Write one element with attributes in the given (fixed) order."""
    parts = [name]
    for key, value in attributes:
        if value is None:
            continue
        if isinstance(value, bool):
            text = "1" if value else "0"
        elif isinstance(value, (int, float)):
            text = number(value)
        else:
            text = escape_attribute(str(value))
        parts.append(f'{key}="{text}"')
    opening = " ".join(parts)
    if body is None:
        return f"<{opening}/>"
    return f"<{opening}>{body}</{name}>"


def column_letter(index: int) -> str:
    """Return the A1 column letters for a 0-based column index."""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def cell_reference(row: int, col: int) -> str:
    return f"{column_letter(col)}{row + 1}"
