"""Opt-in aligned term columns in equation right-hand sides (TermStop)."""

import pytest

from gridlayoutpdf.equations import Equation, EquationAnchors, EquationGroup, MathBlock, wrap_math
from gridlayoutpdf.errors import LayoutError, LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.math import BreakHint, Operator, Row, TermStop
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.scene import Text
from gridlayoutpdf.styles import ReportStyle, TextStyle


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * 0.6, style.size * 0.8, style.size * 0.2)


FONTS = FixedFonts()
STYLE = TextStyle(size=10)
CONTEXT = LayoutContext(FONTS, A4_PORTRAIT_REFERENCE, ReportStyle())
PITCH = 16.08
WIDTH = 30 * PITCH
# first_equal 8 -> RHS starts at column 9; the result relation at column 18 leaves the
# normal RHS region up to column 17 (8 columns); the full RHS region is 21 columns.
ANCHORS = EquationAnchors(8, 18, 24, 25)
RHS = 9 * PITCH
NORMAL = 8 * PITCH
FULL = WIDTH - RHS


def find_text(part, text):
    return next(command for command in part.commands if isinstance(command, Text) and command.text == text)


def assert_columns(actual, expected):
    expected = tuple(expected)
    assert isinstance(actual, tuple) and len(actual) == len(expected)
    for (left, width, align), (e_left, e_width, e_align) in zip(actual, expected):
        assert (left, width, align) == (pytest.approx(e_left), pytest.approx(e_width), e_align)


def substitution(first, operator, second, third):
    return Row(first, TermStop("center"), Operator(operator), TermStop("right"), second,
               TermStop("center"), Operator(operator), TermStop("right"), third, gap=0)


def test_numeric_terms_right_align_and_operators_center_across_equations():
    group = EquationGroup(
        Equation("kv", substitution("5.1", "x", "0.5", "68600"), result="1", unit="m"),
        Equation("kh", substitution("5.1", "xx", "10.25", "6"), result="2", unit="m"),
        anchors=ANCHORS,
    )
    first, second = measure_block(group, CONTEXT, WIDTH).parts
    # Columns: "5.1" 18 left | ops max 12 center | 18/30 right | ops 12 center | 30/6 right.
    lefts = [RHS, RHS + 22, RHS + 38, RHS + 72, RHS + 88]
    assert_columns(first.metadata["term_columns_pt"], zip(
        lefts, (18, 12, 30, 12, 30), ("left", "center", "right", "center", "right")))
    assert second.metadata["term_columns_pt"] == first.metadata["term_columns_pt"]
    assert find_text(first, "5.1").x == pytest.approx(RHS)
    assert find_text(second, "5.1").x == pytest.approx(RHS)
    # Right-aligned numbers share the column's right edge.
    assert find_text(first, "0.5").x + 18 == pytest.approx(lefts[2] + 30)
    assert find_text(second, "10.25").x + 30 == pytest.approx(lefts[2] + 30)
    assert find_text(first, "68600").x + 30 == pytest.approx(lefts[4] + 30)
    assert find_text(second, "6").x + 6 == pytest.approx(lefts[4] + 30)
    # Centered operators share the column's centre.
    first_ops = [c for c in first.commands if isinstance(c, Text) and c.text == "x"]
    second_ops = [c for c in second.commands if isinstance(c, Text) and c.text == "xx"]
    assert [c.x + 3 for c in first_ops] == pytest.approx([lefts[1] + 6, lefts[3] + 6])
    assert [c.x + 6 for c in second_ops] == pytest.approx([lefts[1] + 6, lefts[3] + 6])
    # The result and unit stay on the same line at their anchors.
    assert [c.text for c in first.commands][-3:] == ["=", "1", "m"]
    assert find_text(first, "1").x + 6 == pytest.approx(24 * PITCH)
    assert not first.metadata["result_line"] and len(measure_block(group, CONTEXT, WIDTH).parts) == 2
    assert all(c.style.size == 10 for c in first.commands)


def test_minimum_width_and_term_gap_set_column_spacing():
    rhs = Row("a", TermStop("right", width=40), "bb", gap=0)
    part, = measure_block(EquationGroup(Equation("A", rhs), anchors=ANCHORS, term_gap=10), CONTEXT, WIDTH).parts
    left0, width0, _ = part.metadata["term_columns_pt"][0]
    left1, width1, align1 = part.metadata["term_columns_pt"][1]
    assert (width0, width1, align1) == (6, 40, "right")
    assert left1 - left0 == pytest.approx(width0 + 10)
    assert find_text(part, "bb").x + 12 == pytest.approx(left1 + 40)
    # A column wider than its minimum keeps its measured width; term_gap defaults to gap.
    wide = Row("a", TermStop("left", width=2), "bbbb", gap=0)
    part, = measure_block(EquationGroup(Equation("A", wide), anchors=ANCHORS, gap=5), CONTEXT, WIDTH).parts
    assert part.metadata["term_columns_pt"][1][1] == 24
    assert part.metadata["term_columns_pt"][1][0] == pytest.approx(RHS + 6 + 5)
    assert EquationGroup(term_gap=2).term_gap == 2 and EquationGroup().term_gap is None


def test_leading_term_stop_defines_column_zero_and_empty_segments_have_no_width():
    rhs = Row(TermStop("right", width=30), "abc", TermStop(), TermStop("center"), "d", gap=0)
    part, = measure_block(EquationGroup(Equation("A", rhs), anchors=ANCHORS, term_gap=0), CONTEXT, WIDTH).parts
    columns = part.metadata["term_columns_pt"]
    assert len(columns) == 3
    assert_columns(columns, ((RHS, 30, "right"), (RHS + 30, 0, "left"), (RHS + 30, 6, "center")))
    assert find_text(part, "abc").x == pytest.approx(RHS + 12)
    assert find_text(part, "d").x == pytest.approx(RHS + 30)


def test_segments_use_the_row_gap_and_keep_the_shared_axis():
    rhs = Row("a", "b", TermStop(), "c", gap=2)
    part, = measure_block(EquationGroup(Equation("A", rhs), anchors=ANCHORS, term_gap=0), CONTEXT, WIDTH).parts
    assert part.metadata["term_columns_pt"][0][1] == 14
    assert find_text(part, "b").x == pytest.approx(RHS + 8)
    assert find_text(part, "c").x == pytest.approx(RHS + 14)
    assert len({c.y for c in part.commands}) == 1
    default_gap = Row("a", "b", TermStop(), "c")
    part, = measure_block(EquationGroup(Equation("A", default_gap), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert part.metadata["term_columns_pt"][0][1] == pytest.approx(13.5)


@pytest.mark.parametrize("rows", [
    (Row("a", TermStop("right"), "b"), Row("a", TermStop("left"), "b")),
    (Row(TermStop("right"), "a"), Row("a", TermStop(), "b")),
])
def test_conflicting_column_alignment_is_ambiguous(rows):
    group = EquationGroup(*(Equation("A", row) for row in rows), anchors=ANCHORS)
    with pytest.raises(ValueError, match="align"):
        group.measure(CONTEXT, WIDTH)


@pytest.mark.parametrize("row", [Row("a", TermStop()), Row(TermStop())])
def test_column_equations_reject_trailing_stops(row):
    with pytest.raises(ValueError, match="TermStop"):
        EquationGroup(Equation("A", row), anchors=ANCHORS).measure(CONTEXT, WIDTH)


@pytest.mark.parametrize("hinted, plain", [
    (Row("a", TermStop(), "b", BreakHint(), "c", gap=1), Row("a", TermStop(), "b", "c", gap=1)),
    (Row("a", BreakHint("forced"), "b", TermStop(), "c", gap=1), Row("a", "b", TermStop(), "c", gap=1)),
    (Row("a", TermStop("right"), "bb", BreakHint("preferred"), "cc", gap=0),
     Row("a", TermStop("right"), "bb", "cc", gap=0)),
])
def test_break_hints_in_fitting_column_equations_take_no_space(hinted, plain):
    def parts(rhs):
        return measure_block(EquationGroup(Equation("A", rhs, result="1", unit="m"), anchors=ANCHORS),
                             CONTEXT, WIDTH).parts
    assert parts(hinted) == parts(plain)
    assert "term_fallback" not in parts(hinted)[0].metadata


def test_column_equation_too_wide_for_full_region_falls_back_to_wrapping():
    rhs = Row("A" * 30, TermStop("center"), Operator("+"), TermStop("right"), "B" * 30, gap=0)
    assert 180 + 6 + 180 + 2 * 4 > FULL  # one aligned line would overflow
    first, second, final = measure_block(
        EquationGroup(Equation("A", rhs, result="9", unit="m"), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert [c.text for c in first.commands] == ["A", "=", "A" * 30]
    assert [c.text for c in second.commands] == ["+", "B" * 30]
    assert [c.text for c in final.commands] == ["=", "9", "m"]
    assert find_text(second, "+").x == pytest.approx(RHS)
    assert find_text(second, "B" * 30).x == pytest.approx(RHS + 6)
    assert second.metadata["continuation"] and final.metadata["result_line"]
    for part in (first, second, final):
        assert part.metadata["term_fallback"] is True
        assert "term_columns_pt" not in part.metadata


def test_fallback_equation_does_not_widen_the_short_equations_columns():
    short = Row("a", TermStop("right"), "bb", gap=0)
    other = Row("ccc", TermStop("right"), "d", gap=0)
    long = Row("Z" * 40, TermStop("right"), "Y" * 30, gap=0)  # 240 + 4 + 180 > FULL
    group = EquationGroup(Equation("A", short), Equation("B", long), Equation("C", other),
                          anchors=ANCHORS)
    short_part, long_first, long_second, other_part = measure_block(group, CONTEXT, WIDTH).parts
    expected = ((RHS, 18, "left"), (RHS + 22, 12, "right"))
    assert_columns(short_part.metadata["term_columns_pt"], expected)
    assert other_part.metadata["term_columns_pt"] == short_part.metadata["term_columns_pt"]
    assert find_text(short_part, "bb").x == pytest.approx(RHS + 22)
    assert find_text(other_part, "d").x + 6 == pytest.approx(RHS + 34)
    assert [c.text for c in long_first.commands] == ["B", "=", "Z" * 40]
    assert [c.text for c in long_second.commands] == ["Y" * 30]
    assert long_first.metadata["term_fallback"] and "term_fallback" not in short_part.metadata


def test_fallback_breaks_at_a_preferred_hint_before_term_positions():
    rhs = Row("X" * 25, BreakHint("preferred"), "Y" * 25, TermStop(), "Z" * 25, gap=0)
    first, second = measure_block(EquationGroup(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert [c.text for c in first.commands] == ["A", "=", "X" * 25]
    assert [c.text for c in second.commands] == ["Y" * 25, "Z" * 25]
    assert find_text(second, "Z" * 25).x == pytest.approx(RHS + 150)
    assert first.metadata["term_fallback"] and second.metadata["term_fallback"]


@pytest.mark.parametrize("kwargs", [
    {"align": "middle"}, {"align": 1}, {"align": None},
    {"width": 0}, {"width": -1}, {"width": float("inf")}, {"width": float("nan")},
    {"width": True}, {"width": "3"},
])
def test_term_stop_rejects_invalid_alignment_and_width(kwargs):
    with pytest.raises(ValueError):
        TermStop(**kwargs)


@pytest.mark.parametrize("term_gap", [-1, float("inf"), float("nan"), True, "2"])
def test_group_rejects_invalid_term_gap(term_gap):
    with pytest.raises(ValueError, match="term_gap"):
        EquationGroup(term_gap=term_gap)


def test_term_stop_validates_and_normalizes_width():
    stop = TermStop("center", width=12)
    assert (stop.align, stop.width) == ("center", 12.0) and isinstance(stop.width, float)
    assert TermStop() == TermStop("left", None)


def test_column_line_too_wide_for_normal_region_moves_result_to_its_own_line():
    rhs = Row("X" * 20, TermStop("right"), "YYYYY", gap=0)  # 120 + 4 + 30 = 154 pt
    assert NORMAL < 154 < FULL
    measured = measure_block(EquationGroup(Equation("A", rhs, result="9", unit="m"), anchors=ANCHORS),
                             CONTEXT, WIDTH)
    first, final = measured.parts
    assert [c.text for c in first.commands] == ["A", "=", "X" * 20, "YYYYY"]
    assert [c.text for c in final.commands] == ["=", "9", "m"]
    assert final.metadata["result_line"] and not first.metadata["result_line"]
    assert final.metadata["term_columns_pt"] == first.metadata["term_columns_pt"]
    assert find_text(final, "9").x + 6 == pytest.approx(24 * PITCH)


def test_fallback_term_too_wide_for_full_region_overflows_with_its_source_path():
    rhs = Row("X" * 60, TermStop("right"), "Y" * 10, gap=0)  # the 360 pt term alone exceeds FULL
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("A", rhs, result="9", block_id="wide"), anchors=ANCHORS).measure(CONTEXT, WIDTH)
    assert caught.value.needed == pytest.approx(360)
    assert caught.value.available == pytest.approx(FULL)
    assert caught.value.block_id == "wide.rhs[0]"
    without_result = Row("X" * 60, TermStop(), "Y" * 10, gap=0)
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("A", without_result), anchors=ANCHORS).measure(CONTEXT, WIDTH)
    assert caught.value.block_id == "EquationGroup.equations[0].rhs[0]"
    assert caught.value.available == pytest.approx(FULL)


def test_overflow_names_the_equation_whose_fallback_term_does_not_fit():
    short = Row("a", TermStop(), "b", gap=0)
    long = Row("a", TermStop(), "b", TermStop(), "Z" * 60, gap=0)  # own extent 380 pt
    group = EquationGroup(Equation("A", short, block_id="short"), Equation("B", long, block_id="long"),
                          anchors=ANCHORS)
    with pytest.raises(LayoutOverflowError) as caught:
        group.measure(CONTEXT, WIDTH)
    assert caught.value.block_id == "long.rhs[4]"


def test_short_equation_keeps_its_result_beside_a_long_one_in_the_same_group():
    short = Row("a", TermStop(), "b", gap=0)
    long = Row("a", TermStop(), "b", TermStop(), "Z" * 20, gap=0)  # 6 + 6 + 120 = 132 pt
    assert NORMAL < 132 < FULL
    group = EquationGroup(Equation("A", short, result="1", unit="m"),
                          Equation("B", long, result="2", unit="m"), anchors=ANCHORS, term_gap=0)
    short_part, long_part, long_result = measure_block(group, CONTEXT, WIDTH).parts
    assert [c.text for c in short_part.commands][-3:] == ["=", "1", "m"]
    assert not short_part.metadata["result_line"]
    assert [c.text for c in long_result.commands] == ["=", "2", "m"]
    assert long_result.metadata["result_line"]
    # Column positions stay shared; each equation records only the columns it uses.
    assert_columns(long_part.metadata["term_columns_pt"],
                   ((RHS, 6, "left"), (RHS + 6, 6, "left"), (RHS + 12, 120, "left")))
    assert short_part.metadata["term_columns_pt"] == long_part.metadata["term_columns_pt"][:2]


@pytest.mark.parametrize("anchors", [ANCHORS, None])
def test_plain_equations_keep_their_layout_beside_column_equations(anchors):
    plain = (
        Equation("A", Row("aaaaa", Operator("+"), "bbbbb", Operator("+"), "ccccc", Operator("+"), "ddddd",
                          gap=0), label="式名", result="999", unit="m"),
        Equation("B", "X" * 30, result="9", unit="m"),
        Equation("C", Row("a", BreakHint("forced"), "b")),
    )
    column = Equation("D", Row("1", TermStop("right"), "22", gap=0), result="9", unit="m")
    alone = measure_block(EquationGroup(*plain, anchors=anchors), CONTEXT, WIDTH)
    mixed = measure_block(EquationGroup(*plain, column, anchors=anchors), CONTEXT, WIDTH)
    assert mixed.parts[:len(alone.parts)] == alone.parts
    assert all("term_columns_pt" not in part.metadata for part in alone.parts)
    assert "term_columns_pt" in mixed.parts[-1].metadata


def test_column_equation_keeps_its_label_and_single_equation_measure():
    equation = Equation("A", Row("1", TermStop("right", width=20), "2", gap=0), label="式名", block_id="eq")
    part, = equation.measure(CONTEXT, WIDTH).parts
    assert [c.text for c in part.commands] == ["式名", "A", "=", "1", "2"]
    left, width, _ = part.metadata["term_columns_pt"][1]
    assert find_text(part, "2").x + 6 == pytest.approx(left + width)


def test_term_stop_requires_equation_layout_and_is_public():
    import gridlayoutpdf

    with pytest.raises(LayoutError, match="TermStop requires equation layout"):
        TermStop().measure(FONTS, STYLE)
    with pytest.raises(LayoutError):
        MathBlock(Row("a", TermStop(), "b")).measure(CONTEXT, WIDTH)
    with pytest.raises(LayoutError):
        wrap_math(Row(Row("a", TermStop(), "b")), FONTS, STYLE, WIDTH)
    with pytest.raises(LayoutError):
        EquationGroup(Equation("A", Row(Row("a", TermStop(), "b"))), anchors=ANCHORS).measure(CONTEXT, WIDTH)
    assert gridlayoutpdf.TermStop is TermStop and "TermStop" in gridlayoutpdf.__all__


def test_rows_that_fit_alone_but_not_in_shared_columns_both_fall_back():
    wide_first = Row("Z" * 30, TermStop(), "a", gap=0)  # alone 190 pt; shared 364 pt > FULL
    wide_second = Row("a", TermStop(), "Y" * 30, gap=0)
    first, second = measure_block(EquationGroup(Equation("A", wide_first), Equation("B", wide_second),
                                                 anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert [c.text for c in first.commands] == ["A", "=", "Z" * 30, "a"]
    assert [c.text for c in second.commands] == ["B", "=", "a", "Y" * 30]
    assert find_text(second, "Y" * 30).x == pytest.approx(RHS + 6)
    assert first.metadata["term_fallback"] and second.metadata["term_fallback"]
    assert "term_columns_pt" not in first.metadata | second.metadata
