"""FR-021: which text pieces become number cells, and the number format that shows them unchanged.

The Excel results quoted here were read from Excel 16.0 (ja-JP) with
``Range.Text``; ``tests/integration/test_xlsx_numbers_excel.py`` checks them
again on a real Excel.
"""

import decimal
import itertools
import random
import subprocess
import sys
from decimal import Decimal

import pytest

from gridlayoutpdf.renderers.xlsx import _numbers
from gridlayoutpdf.renderers.xlsx._model import (
    BUILTIN_NUMBER_FORMATS,
    MAX_CUSTOM_NUMBER_FORMATS,
    CellValue,
    Sheet,
    Workbook,
)
from gridlayoutpdf.renderers.xlsx._numbers import NumericCell, classify_number, excel_display

MINUS = "\u2212"


# The examples confirmed with the user (FR-021).
@pytest.mark.parametrize(("text", "value", "number_format"), [
    ("7.381125", 7.381125, "0.000000"),
    ("1,234.5", 1234.5, "#,##0.0"),
    (MINUS + "2.000", -2.0, '0.000;"' + MINUS + '"0.000'),
    ("12", 12.0, "0"),
    ("+2.50", 2.5, '"+"0.00;"-"0.00'),
])
def test_confirmed_examples(text, value, number_format):
    cell = classify_number(text)
    assert cell == NumericCell(value, number_format)
    assert type(cell.value) is float
    assert excel_display(cell.value, cell.number_format) == text


@pytest.mark.parametrize(("text", "value", "number_format"), [
    ("0", 0.0, "0"),
    ("0.0", 0.0, "0.0"),
    ("0.5", 0.5, "0.0"),
    ("+0", 0.0, '"+"0;"-"0'),
    ("+0.0", 0.0, '"+"0.0;"-"0.0'),
    ("-0.5", -0.5, '0.0;"-"0.0'),
    (MINUS + "0.5", -0.5, '0.0;"' + MINUS + '"0.0'),
    ("-2.000", -2.0, '0.000;"-"0.000'),
    ("1234", 1234.0, "0"),
    ("1,234", 1234.0, "#,##0"),
    ("123", 123.0, "0"),
    ("12,345,678", 12345678.0, "#,##0"),
    ("1,234,567.891", 1234567.891, "#,##0.000"),
    ("-1,234", -1234.0, '#,##0;"-"#,##0'),
    ("+1,234.50", 1234.5, '"+"#,##0.00;"-"#,##0.00'),
    (MINUS + "999,999,999,999,999", -999999999999999.0, '#,##0;"' + MINUS + '"#,##0'),
])
def test_numbers_and_their_formats(text, value, number_format):
    cell = classify_number(text)
    assert cell == NumericCell(value, number_format)
    assert excel_display(cell.value, cell.number_format) == text


@pytest.mark.parametrize("text", [
    # numbers with other characters, units or spaces
    "(1)", "No.3", "OK", "5kN", "5 kN", "1 234", " 12", "12 ", "12\n", "\n12", "\t12", "\u00a012", "12\u3000",
    "1.5%", "\u00a5100", "1/2", "1:2", "\u00b2", "\u00bd", "1.2.3", "1..2",
    # leading zeros of a numbering
    "0500", "00", "00.5", "007", "-007", "+00",
    # negative zero (Excel has no signed zero to show)
    "-0", MINUS + "0", "-0.000", MINUS + "0.000", MINUS + "0.0", "-0.00", MINUS + "0.00000",
    # exponents, full-width and other digits, odd decimal points
    "1.2e3", "1E3", "1e-3", "\uff11\uff12", "\uff11.\uff15", "\u0661\u0662", "\u0967", ".5", "5.", "-.5", "+.5",
    "inf", "-inf", "nan", "Infinity", "1_000", "0x10", "0b1", "1j",
    # separators not in threes, or misplaced
    "1,23", "1,2345", "12,34", "1,234,56", ",123", "123,", "1,,234", "1,234.5,6", "1,234.567,8", "0,123", "0,000",
    "-0,000",
    "1.234,5", "1\uff0c234", "1\u3001234",
    # signs that are not one plain sign before the digits
    "--1", "+-1", MINUS + "-1", "-" + MINUS + "1", "++1", "1-", "1+", "- 1", "+ 1", "\uff0b1", "\uff0d1",
    "\u20101", "\u20111", "\u20121", "\u20131", "\u20141", "\ufe631", "\u02d71",
    # nothing to read
    "", "-", "+", MINUS, ".", ",", " ",
])
def test_text_stays_text(text):
    assert classify_number(text) is None


@pytest.mark.parametrize(("text", "expected"), [
    # 15 significant digits are what Excel shows; a 16th would come back as 0
    ("999999999999999", True),
    ("123456789012345", True),
    ("100000000000000", True),
    ("1000000000000000", False),  # 16 integer digits
    ("9999999999999999", False),
    ("0.123456789012345", True),
    ("0.1234567890123456", False),  # Excel shows 0.1234567890123460
    ("123456789012.345", True),
    ("1234567890123.456", False),
    ("123456789012345.6", False),
    ("-0.000123456789012345", True),
    ("-0.0001234567890123456", False),
    ("999,999,999,999,999", True),
    ("9,999,999,999,999,999", False),
    # trailing zeros are not significant: Excel shows them from the format
    ("1.000000000000000000", True),
    ("100000000000000.000000000000000", True),
    # at most 20 decimal places, so that all formats fit in one workbook with room to spare
    ("0." + "0" * 19 + "1", True),
    ("0." + "0" * 20, True),
    ("1." + "0" * 20, True),
    ("0." + "0" * 20 + "1", False),
    ("0." + "0" * 21, False),
    ("0." + "0" * 29 + "1", False),  # Excel shows 30 places, but they do not fit the format budget
])
def test_digit_limits(text, expected):
    cell = classify_number(text)
    assert (cell is not None) is expected
    if cell is not None:
        assert excel_display(cell.value, cell.number_format) == text


def test_formats_depend_only_on_sign_separators_and_places():
    assert classify_number("1.5").number_format == classify_number("27.0").number_format
    assert classify_number("1,234.5").number_format == classify_number("9,999,999.0").number_format
    assert classify_number("+1").number_format == classify_number("+9").number_format
    assert classify_number("-1").number_format == classify_number("-7").number_format
    assert classify_number("-1.5").number_format != classify_number(MINUS + "1.5").number_format
    assert classify_number("1.5").number_format != classify_number("1.50").number_format
    # deterministic: the same text always gives the same cell
    assert classify_number(MINUS + "2.000") == classify_number(MINUS + "2.000")


def test_all_formats_fit_in_one_workbook_and_are_valid():
    texts = []
    for sign, thousands, places in itertools.product(("", "+", "-", MINUS), (False, True), range(21)):
        integer = "1,234" if thousands else "1"
        texts.append(sign + integer + ("." + "0" * places if places else ""))
    formats, cells = set(), []
    for row, text in enumerate(texts):
        cell = classify_number(text)
        assert cell is not None, text
        cells.append(CellValue(row, 0, cell.value, number_format=cell.number_format))
        formats.add(cell.number_format)
    # the model accepts every format, all of them in one workbook
    Workbook((Sheet("s", (100.0,), (15.0,) * len(cells), tuple(cells)),))
    # each sign has its own formats: 4 signs x 2 separators x 21 places
    assert len(formats) == 4 * 2 * 21 == _numbers.MAX_NUMBER_FORMATS
    custom = formats - set(BUILTIN_NUMBER_FORMATS)
    assert len(custom) == 4 * 2 * 21 - 4 == 164
    assert MAX_CUSTOM_NUMBER_FORMATS - len(custom) == 42  # left for other custom formats of a workbook
    assert {"0", "0.00", "#,##0", "#,##0.00"} <= formats  # written as built-in formats


def test_text_must_be_str():
    with pytest.raises(TypeError):
        classify_number(1.5)
    with pytest.raises(TypeError):
        classify_number(None)


def test_round_trip_check_rejects_a_mismatched_display(monkeypatch):
    monkeypatch.setattr(_numbers, "excel_display", lambda value, number_format: "something else")
    assert classify_number("7.381125") is None


def test_numeric_cell_is_frozen():
    cell = classify_number("12")
    with pytest.raises(AttributeError):
        cell.value = 13.0


# excel_display is a small model of how Excel shows a number in the formats this module writes.
@pytest.mark.parametrize(("value", "number_format", "shown"), [
    # read from Excel 16.0 (ja-JP) with Range.Text
    (-2.0, "0.000", "-2.000"),
    (-2.0, '0.000;"' + MINUS + '"0.000', MINUS + "2.000"),
    (-2.0, '0.000;"-"0.000', "-2.000"),
    (2.5, '"+"0.00', "+2.50"),
    (-2.0, '"+"0.00;"-"0.00', "-2.00"),
    (0.0, '"+"0', "+0"),
    (1e-30, "0." + "0" * 30, "0." + "0" * 29 + "1"),
    (123456789012.345, "0.000", "123456789012.345"),
    (999999999999999.0, "0", "999999999999999"),
    (0.123456789012345, "0." + "0" * 15, "0.123456789012345"),
    (0.1234567890123456, "0." + "0" * 16, "0.1234567890123460"),
    (123456789012345678.0, "0", "123456789012346000"),
    (1.0, "0." + "0" * 20, "1." + "0" * 20),
    (1234.5, "#,##0.0", "1,234.5"),
    (1234567.25, "#,##0.00", "1,234,567.25"),
    (2.5, "0", "3"),
    (0.5, "0", "1"),
    (-0.5, '0;"' + MINUS + '"0', MINUS + "1"),
    (1.25, "0.0", "1.3"),
    (-1.25, "0.0", "-1.3"),
    (2.675, "0.00", "2.68"),
    # 15 significant digits: the nearest to the exact binary value, an exact half toward zero
    (100000000000000.5, "0", "100000000000000"),
    (100000000000001.5, "0", "100000000000001"),  # format(x, ".15g") gives ...002
    (-100000000000000.5, "0", "-100000000000000"),
    (1000000000000002.5, "0", "1000000000000000"),
    (10000000000000.25, "0.0", "10000000000000.2"),
    (12345678901234.25, "0.0", "12345678901234.2"),
    (7462911.561158455, "0.000000000", "7462911.561158450"),
    (0.30000000000000004, "0." + "0" * 16, "0.3" + "0" * 15),
    (1.0000000000000002, "0." + "0" * 16, "1." + "0" * 16),
    (2.0000000000000004, "0." + "0" * 15, "2." + "0" * 15),
    (0.1, "0." + "0" * 19, "0.1" + "0" * 18),
    # from the exact value, not from a 17-digit decimal (that would give ...08, ...09, ...10, ...11)
    (1.000000000000085, "0." + "0" * 14, "1.00000000000009"),
    (-1.000000000000095, "0." + "0" * 14, "-1.00000000000010"),
    (1.000000000000105, "0." + "0" * 14, "1.00000000000011"),
    (1.000000000000115, "0." + "0" * 14, "1.00000000000012"),
])
def test_excel_display_matches_excel(value, number_format, shown):
    assert excel_display(value, number_format) == shown


# The model's rules on values not read from Excel (the extremes are outside what classify_number gives).
@pytest.mark.parametrize(("value", "number_format", "shown"), [
    (0.0, "0.000", "0.000"),
    (12.0, "#,##0", "12"),
    (1234567.0, "#,##0", "1,234,567"),
    (-1234.5, "#,##0.0", "-1,234.5"),
    (-1234.5, '#,##0.0;"' + MINUS + '"#,##0.0', MINUS + "1,234.5"),
    (0.0, '0.0;"-"0.0', "0.0"),  # zero takes the first section
    (1e300, "0", "1" + "0" * 300),  # 15 digits, then zeros
    (0.5, "0.0", "0.5"),
    (5e-324, "0." + "0" * 30, "0." + "0" * 30),
])
def test_excel_display_rules(value, number_format, shown):
    assert excel_display(value, number_format) == shown


def test_excel_display_of_the_largest_float():
    shown = excel_display(sys.float_info.max, "#,##0." + "0" * 30)
    assert shown.startswith("179,769,313,486,232,000,") and shown.endswith("." + "0" * 30)


@pytest.mark.parametrize("number_format", [
    "General", "0%", "0.00E+00", "@", "0;0;0", "0.0#", "#,##0;", "[Red]0", "0.0 kN", "0_)", "0,", "00", "#",
    '0"kN"', "0.", "", '"+', "0,000", "##,##0",
])
def test_excel_display_refuses_formats_it_does_not_model(number_format):
    with pytest.raises(ValueError):
        excel_display(1.0, number_format)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_excel_display_refuses_non_finite_values(value):
    with pytest.raises(ValueError):
        excel_display(value, "0")


def test_excel_display_number_format_must_be_str():
    with pytest.raises(TypeError):
        excel_display(1.0, None)


@pytest.mark.parametrize("value", [True, False, "1.0", None, Decimal("1.5"), 1])
def test_excel_display_value_must_be_float(value):
    with pytest.raises(TypeError):
        excel_display(value, "0")


def test_excel_display_refuses_more_places_than_excel_shows():
    assert excel_display(1.0, "0." + "0" * 30) == "1." + "0" * 30
    with pytest.raises(ValueError):
        excel_display(1.0, "0." + "0" * 31)


@pytest.mark.parametrize(("value", "number_format", "error"), [
    (float("nan"), "0", ValueError),
    (float("inf"), "0", ValueError),
    (1, "0", TypeError),
    (True, "0", TypeError),
    (1.0, None, TypeError),
    (1.0, '"', ValueError),
    (1.0, "0;0;0;0;0", ValueError),
    (-0.0, "0", ValueError),
])
def test_numeric_cell_checks_its_fields(value, number_format, error):
    with pytest.raises(error):
        NumericCell(value, number_format)


def _random_number_like(rng: random.Random) -> str:
    alphabet = "0123456789,.-+" + MINUS
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 20)))


def _random_grammar_number(rng: random.Random) -> str:
    sign = rng.choice(("", "", "+", "-", MINUS))
    integer = rng.choice(("0", str(rng.randint(1, 10 ** rng.randint(1, 16)))))
    if rng.random() < 0.5 and integer != "0":
        integer = f"{int(integer):,}"
    places = rng.choice((0, 0, rng.randint(1, 22)))
    fraction = "".join(rng.choice("0123456789") for _ in range(places))
    return sign + integer + ("." + fraction if fraction else "")


def test_random_texts_keep_their_display():
    """Whatever is classified shows back as written; the value and format follow the text alone."""
    rng = random.Random(20261020)
    texts = [_random_number_like(rng) for _ in range(20000)] + [_random_grammar_number(rng) for _ in range(20000)]
    classified = 0
    for index, text in enumerate(texts):
        cell = classify_number(text)
        if cell is None:
            if index >= 20000:  # a grammar number stays text only for its digits or a negative zero
                sign = text[0] if text[0] in "+-" + MINUS else ""
                integer, _, fraction = text[len(sign):].partition(".")
                digits = integer.replace(",", "")
                significant = (digits + fraction).strip("0")
                assert (len(digits) > 15 or len(fraction) > 20 or len(significant) > 15
                        or (sign in ("-", MINUS) and not significant)), text
            continue
        classified += 1
        sign = text[0] if text[0] in "+-" + MINUS else ""
        body = text[len(sign):]
        integer, _, fraction = body.partition(".")
        assert Decimal(cell.value) == Decimal(float(("-" if sign in ("-", MINUS) else "") + body.replace(",", "")))
        assert Decimal(repr(cell.value)) == Decimal(("-" if sign in ("-", MINUS) else "") + body.replace(",", ""))
        pattern = ("#,##0" if "," in integer else "0") + ("." + "0" * len(fraction) if fraction else "")
        expected_format = {"": pattern, "+": f'"+"{pattern};"-"{pattern}'}.get(sign, f'{pattern};"{sign}"{pattern}')
        assert cell.number_format == expected_format
        assert excel_display(cell.value, cell.number_format) == text
    assert classified > 10000


def test_custom_format_budget_of_this_module():
    assert _numbers.MAX_CUSTOM_NUMBER_FORMATS_USED == _numbers.MAX_NUMBER_FORMATS - 4 == 164


def test_results_do_not_depend_on_the_thread_decimal_context():
    expected = (classify_number("1,234.5"), excel_display(1e200, "0"), excel_display(5e-324, "0.0"))
    with decimal.localcontext() as context:
        context.traps[decimal.FloatOperation] = True
        context.Emin, context.Emax, context.prec = -20, 20, 5
        assert (classify_number("1,234.5"), excel_display(1e200, "0"), excel_display(5e-324, "0.0")) == expected


def test_excel_display_checks_every_section():
    number_format = '0.0;"-"0.' + "0" * 31
    for value in (1.0, -1.0):
        with pytest.raises(ValueError):
            excel_display(value, number_format)


def test_exact_context_does_not_take_the_default_context():
    """``_EXACT`` names every setting, so a changed ``decimal.DefaultContext`` before the import does not reach it."""
    script = "; ".join((
        "import decimal",
        "decimal.DefaultContext.traps[decimal.Inexact] = True",
        "decimal.DefaultContext.Emax = 20",
        "from gridlayoutpdf.renderers.xlsx._numbers import NumericCell, classify_number, excel_display",
        "assert classify_number('0.1') == NumericCell(0.1, '0.0')",
        "assert excel_display(1e200, '0') == '1' + '0' * 200",
    ))
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
