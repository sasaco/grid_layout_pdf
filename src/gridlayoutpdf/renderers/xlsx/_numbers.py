"""FR-021: number cells for text pieces that are written as numbers.

A text piece becomes a number cell only when the whole piece is a plain
decimal (``7.381125``, ``1,234.5``, ``−2.000``, ``+2.50``, ``12``) that Excel
shows back unchanged. Anything else stays text, so a wrong guess can only
leave a number as text and never changes what is shown:

- characters other than one sign, ASCII digits, ``,`` and ``.`` (units,
  spaces, brackets, full-width or other digits, exponents);
- a leading ``0`` before more integer digits (``0500``) and ``,`` that is not
  every three digits from ``.`` (``1,23``, ``1,234,56``, ``0,123``);
- ``.5`` and ``5.``;
- a negative zero (``-0``, ``−0.000``): Excel's numbers have no signed zero;
- more than 15 integer digits, more than 15 significant digits (Excel keeps
  15 and shows the rest as 0), or more than 20 decimal places;
- any text that ``excel_display`` does not show back exactly.

The sign is kept by the format: ``+`` and each minus character (ASCII ``-``
or U+2212 ``−``) are quoted literally, so formats are the same for the same
sign, separators and decimal places: at most 4 signs (none, ``+``, ``-``,
``−``) × 2 (with or without ``,``) × 21 (0 to 20 places) = 168 codes, 4 of
them built in, so at most 164 custom codes of the 206 a workbook can hold
(``_model.MAX_CUSTOM_NUMBER_FORMATS``), leaving 42 for other formats.

What the caller must also give (checked in Excel 16.0 ja-JP, not here):

- a cell range at least as wide as the text in Excel's font with the cell's
  inner margins (as tall, for text turned 90 or 270 degrees): Excel shows a
  number that does not fit as ``###`` (text would run over or be cut), so a
  number cell that cannot be made large enough must stay text;
- the alignment of the source as ``CellValue.h_align`` (it is always written,
  so Excel's default right alignment of numbers does not apply);
- Excel's decimal point ``.`` and thousands separator ``,`` (the ja-JP
  default): the ``.`` and ``,`` of a number format are shown as Excel's
  separators, so other settings would change the display.

Wrong argument types raise ``TypeError``; unsupported values raise ``ValueError``.
"""

import math
import re
from dataclasses import dataclass
from decimal import (ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Context, Decimal, DivisionByZero,
                     InvalidOperation, Overflow)

from ._model import BUILTIN_NUMBER_FORMATS, _number_format

MINUS_SIGN = "\u2212"  # U+2212, the minus of printed reports
MAX_SIGNIFICANT_DIGITS = 15  # Excel shows a 16th significant digit as 0 (Excel 16.0)
MAX_INTEGER_DIGITS = 15
# Excel 16.0 showed 30 places of 1e-30 exactly; 20 keeps every format of this
# module within one workbook's custom format limit with room for others
# (see the module docstring). Reports do not print more places.
MAX_DECIMAL_PLACES = 20
MAX_NUMBER_FORMATS = 4 * 2 * (MAX_DECIMAL_PLACES + 1)  # signs x separators x places
# the unsigned "0", "0.00", "#,##0" and "#,##0.00" are built-in formats, written by number
MAX_CUSTOM_NUMBER_FORMATS_USED = MAX_NUMBER_FORMATS - sum(
    integer + ("." + "0" * places if places else "") in BUILTIN_NUMBER_FORMATS
    for integer in ("0", "#,##0") for places in range(MAX_DECIMAL_PLACES + 1))
MAX_MODELLED_PLACES = 30  # excel_display was checked in Excel up to 30 places

# ASCII digits only: ``\d`` would accept full-width and other scripts' digits.
_NUMBER = re.compile(
    r"(?P<sign>[-+\u2212])?"
    r"(?P<integer>0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)"
    r"(?:\.(?P<fraction>[0-9]+))?")
# holds any finite float's integer part with 30 places; every setting is named,
# since unnamed ones would come from decimal.DefaultContext as it is at import
_EXACT = Context(prec=800, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999, capitals=1, clamp=0,
                 flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])


@dataclass(frozen=True, slots=True)
class NumericCell:
    """A number cell's value and the number format that shows it as the text was written."""

    value: float
    number_format: str

    def __post_init__(self) -> None:
        if type(self.value) is not float:
            raise TypeError(f"value must be float, not {type(self.value).__name__}")
        if not math.isfinite(self.value):
            raise ValueError(f"value must be finite, not {self.value!r}")
        if self.value == 0 and math.copysign(1.0, self.value) < 0:
            raise ValueError("value must not be a negative zero: Excel has no signed zero to show")
        if not isinstance(self.number_format, str):
            raise TypeError(f"number_format must be str, not {type(self.number_format).__name__}")
        _number_format(self.number_format)


def classify_number(text: str) -> NumericCell | None:
    """Return the number cell for ``text``, or ``None`` when it must stay text."""
    if not isinstance(text, str):
        raise TypeError(f"text must be str, not {type(text).__name__}")
    match = _NUMBER.fullmatch(text)
    if match is None:
        return None
    sign, integer, fraction = match.group("sign"), match.group("integer"), match.group("fraction") or ""
    digits = integer.replace(",", "")
    if len(digits) > MAX_INTEGER_DIGITS or len(fraction) > MAX_DECIMAL_PLACES:
        return None
    if len((digits + fraction).strip("0")) > MAX_SIGNIFICANT_DIGITS:
        return None
    negative = sign in ("-", MINUS_SIGN)
    if negative and not (digits + fraction).strip("0"):
        return None  # negative zero
    value = float(("-" if negative else "") + digits + ("." + fraction if fraction else ""))
    pattern = ("#,##0" if "," in integer else "0") + ("." + "0" * len(fraction) if fraction else "")
    if sign is None:
        number_format = pattern
    elif sign == "+":
        number_format = f'"+"{pattern};"-"{pattern}'
    else:
        number_format = f'{pattern};"{sign}"{pattern}'
    if excel_display(value, number_format) != text:
        return None
    return NumericCell(value, number_format)


_SECTION = re.compile(r'(?:"(?P<literal>[^"]*)")?(?P<integer>0|#,##0)(?:\.(?P<places>0+))?')


def excel_display(value: float, number_format: str) -> str:
    """Show ``value`` the way Excel does in a number format this module writes.

    Only one or two sections of an optional quoted prefix, ``0`` or ``#,##0``
    and up to 30 decimal places are modelled; any other code is a
    ``ValueError``. As measured in Excel 16.0, the exact binary value is
    first rounded to the nearest 15 significant digits with an exact half
    toward zero (``100000000000001.5`` shows ``100000000000001``, where
    ``format(x, ".15g")`` would round to even, and ``1.000000000000085`` in 14
    places shows ``1.00000000000009``, where its 17-digit decimal would give
    ``...08``), and that decimal to the format's places with a half away
    from zero (``2.5`` in ``0`` shows ``3``).
    A single section shows negatives with ``-`` before everything; with two,
    the second section shows the magnitude of negatives and zero takes the
    first.
    """
    if type(value) is not float:
        raise TypeError(f"value must be float, not {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"value must be finite, not {value!r}")
    sections = _split_sections(number_format)
    if len(sections) > 2:
        raise ValueError(f"number format {number_format!r} has more than two sections")
    parsed = []
    for section in sections:
        match = _SECTION.fullmatch(section)
        if match is None:
            raise ValueError(f"number format {number_format!r} is not one this module writes")
        if len(match.group("places") or "") > MAX_MODELLED_PLACES:
            raise ValueError(f"number format {number_format!r} has more than {MAX_MODELLED_PLACES} decimal places")
        parsed.append(match)
    lead = ""
    if value < 0:
        if len(parsed) == 1:
            lead = "-"
        else:
            parsed = parsed[1:]
    section = parsed[0]
    places = len(section.group("places") or "")
    # every Decimal step names _EXACT, so the thread's decimal context does not matter
    magnitude = Decimal.from_float(abs(value))  # exact
    if magnitude:
        step = Decimal(1).scaleb(magnitude.adjusted() - MAX_SIGNIFICANT_DIGITS + 1, context=_EXACT)
        magnitude = magnitude.quantize(step, rounding=ROUND_HALF_DOWN, context=_EXACT)
    shown = magnitude.quantize(Decimal(1).scaleb(-places, context=_EXACT), rounding=ROUND_HALF_UP, context=_EXACT)
    body = format(shown, ",f" if section.group("integer") == "#,##0" else "f")
    return lead + (section.group("literal") or "") + body


def _split_sections(number_format: str) -> list[str]:
    """Split a format at ``;`` outside quotes."""
    if not isinstance(number_format, str):
        raise TypeError(f"number format must be str, not {type(number_format).__name__}")
    sections, start, quoted = [], 0, False
    for index, char in enumerate(number_format):
        if char == '"':
            quoted = not quoted
        elif char == ";" and not quoted:
            sections.append(number_format[start:index])
            start = index + 1
    if quoted:
        raise ValueError(f"number format {number_format!r} has an unclosed quote")
    sections.append(number_format[start:])
    return sections
