"""Leading(overhang=...) keeps a fixed line advance when ink slightly exceeds it."""

from dataclasses import dataclass

import pytest

from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, LayoutContext, LayoutOverflowError, LayoutPart, Line, MeasuredBlock,
    ReportStyle, measure_block,
)
from gridlayoutpdf.containers import Indent, Leading
from gridlayoutpdf.equations import MathBlock
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.math import Script
from gridlayoutpdf.profiles import GridSpec, PageProfile


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * 0.6, style.size * 0.8, style.size * 0.2)


FINE = LayoutContext(FixedFonts(), PageProfile("fine", 595, 842, GridSpec(48, 72, .12, .12, 4400, 6000)),
                     ReportStyle())
CONTEXT = LayoutContext(FixedFonts(), A4_PORTRAIT_REFERENCE, ReportStyle())
PITCH = 15.48


@dataclass(frozen=True)
class FixedBlock:
    result: MeasuredBlock
    block_id: str = "child"

    def measure(self, context, available_width):
        return self.result


def parts(*rows, metadata=()):
    extra = dict(metadata)
    return MeasuredBlock(40, PITCH, tuple(LayoutPart(count, (Line(1, 2, 9, 2),), {"n": index, **extra})
                                          for index, count in enumerate(rows)), block_id="lines")


def test_subscript_line_keeps_the_fixed_advance_and_its_drawing():
    math = MathBlock(Script("N", subscript="d"))
    natural, = measure_block(math, FINE, 400).parts
    leading = natural.rows - 1
    held, = measure_block(Indent(Leading(math, leading, overhang=0.12), 1.2), FINE, 400).parts
    assert held.rows == leading
    assert held.commands == tuple(command.translated(1.2, 0) for command in natural.commands)
    assert held.metadata["overhang_pt"] == pytest.approx(0.12)
    with pytest.raises(LayoutOverflowError, match="leading"):
        Leading(math, leading).measure(FINE, 400)


def test_overhang_within_the_allowance_holds_the_rows_and_records_the_excess():
    original = parts(1, 3, 2)
    result = measure_block(Leading(FixedBlock(original), 2, overhang=PITCH), CONTEXT, 100)
    assert [part.rows for part in result.parts] == [2, 2, 2]
    assert [part.commands for part in result.parts] == [part.commands for part in original.parts]
    assert [part.metadata for part in result.parts] == [{"n": 0}, {"n": 1, "overhang_pt": PITCH}, {"n": 2}]


def test_nested_overhang_accumulates_against_the_outer_allowance():
    inner = Leading(FixedBlock(parts(3)), 2, overhang=PITCH)
    outer, = measure_block(Leading(inner, 1, overhang=2 * PITCH), CONTEXT, 100).parts
    assert (outer.rows, outer.metadata["overhang_pt"]) == (1, pytest.approx(2 * PITCH))
    with pytest.raises(LayoutOverflowError, match="leading"):
        Leading(inner, 1, overhang=PITCH).measure(CONTEXT, 100)


def test_excess_beyond_the_allowance_is_an_overflow_or_stays_raised():
    original = parts(1, 4)
    with pytest.raises(LayoutOverflowError, match="leading") as caught:
        Leading(FixedBlock(original), 2, overhang=PITCH).measure(CONTEXT, 100)
    assert caught.value.needed == pytest.approx(4 * PITCH)
    result = measure_block(Leading(FixedBlock(original), 2, minimum=True, overhang=PITCH), CONTEXT, 100)
    assert [part.rows for part in result.parts] == [2, 4]
    assert "overhang_pt" not in result.parts[1].metadata


def test_zero_overhang_is_the_previous_behaviour():
    original = parts(1, 3)
    for rows, minimum in ((3, False), (3, True), (2, True)):
        plain = Leading(FixedBlock(original), rows, minimum=minimum)
        zero = Leading(FixedBlock(original), rows, minimum=minimum, overhang=0)
        assert measure_block(zero, CONTEXT, 100) == measure_block(plain, CONTEXT, 100)
    with pytest.raises(LayoutOverflowError):
        Leading(FixedBlock(original), 2, overhang=0.0).measure(CONTEXT, 100)


@pytest.mark.parametrize("overhang", [-0.01, float("inf"), float("nan"), True, "0.1", None])
def test_invalid_overhang_is_rejected(overhang):
    with pytest.raises(ValueError, match="overhang"):
        Leading(FixedBlock(parts(1)), 1, overhang=overhang)


@pytest.mark.parametrize("value", [-1.0, "1", True])
def test_measure_block_rejects_an_invalid_recorded_overhang(value):
    with pytest.raises(ValueError, match="overhang_pt"):
        measure_block(FixedBlock(parts(1, metadata={"overhang_pt": value})), CONTEXT, 100)


def test_measure_block_still_rejects_ink_below_the_recorded_overhang():
    block = MeasuredBlock(40, PITCH, (LayoutPart(1, (Line(1, 2, 9, PITCH + 2),), {"overhang_pt": 1.0}),))
    with pytest.raises(LayoutOverflowError, match="exceed part"):
        measure_block(FixedBlock(block), CONTEXT, 100)
