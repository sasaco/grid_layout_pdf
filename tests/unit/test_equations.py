"""Equation adapters: independent point arithmetic and grid-boundary checks."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from gridlayoutpdf.equations import Equation, EquationAnchors, EquationGroup, MathBlock
from gridlayoutpdf.errors import FontError, LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.geometry import Rect
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.math import BreakHint, Fraction, Literal, MathBox, Operator, Row
from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE
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


def test_mathblock_reserves_natural_width_and_grid_height_without_splitting():
    block = MathBlock(Fraction("ab", "c"), block_id="math-1")
    measured = measure_block(block, CONTEXT, 100)
    # Fraction width = 12 + 3, ascent = 14.25, descent = 9.25.
    assert measured.width == 15
    assert measured.rows == 3
    assert measured.keep_together
    assert measured.block_id == "math-1"
    assert measured.parts[0].metadata["baseline_pt"] == 26.48
    assert measured.split(2) is None
    assert measured.commands == block.expression.measure(FONTS, STYLE).translated(0, 26.48)
    assert block.measure(CONTEXT, 100) == measured


def test_mathblock_defaults_or_overrides_style_and_lifts_strings():
    assert isinstance(MathBlock("abc").expression, Literal)
    default = MathBlock("abc").measure(CONTEXT, 100)
    override = MathBlock("abc", style=TextStyle(size=12)).measure(CONTEXT, 100)
    assert default.width == 18 and default.commands == (Text(0, 11, "abc", STYLE),)
    assert override.width == pytest.approx(21.6)
    assert override.commands[0].style.size == 12
    with pytest.raises(FrozenInstanceError):
        MathBlock("a").style = STYLE


def test_empty_mathblock_has_no_parts_and_keeps_positive_reserved_width():
    measured = MathBlock(Row()).measure(CONTEXT, 80)
    assert measured.width == 80
    assert measured.parts == () and measured.rows == 0 and measured.commands == ()


def test_mathblock_does_not_wrap_a_row_and_reports_width():
    with pytest.raises(LayoutOverflowError) as caught:
        MathBlock(Row("a", Operator("+"), "b", gap=0), block_id="cell.math").measure(CONTEXT, 12)
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (18, 12, "cell.math")


@pytest.mark.parametrize("kwargs", [{"expression": 3}, {"expression": "a", "style": 1}, {"expression": "a", "block_id": None}])
def test_mathblock_rejects_invalid_construction(kwargs):
    with pytest.raises(ValueError):
        MathBlock(**kwargs)


@pytest.mark.parametrize("width", [True, 0, -1, float("inf"), float("nan"), None])
def test_mathblock_rejects_invalid_width(width):
    with pytest.raises(ValueError, match="available_width"):
        MathBlock("a").measure(CONTEXT, width)


def test_mathblock_rejects_invalid_context():
    with pytest.raises(ValueError, match="context"):
        MathBlock("a").measure(None, 100)


def test_equation_and_group_normalize_inputs_and_are_immutable():
    equation = Equation("A", "2 * 3", result="6.000", unit="m", label="面積")
    assert all(isinstance(getattr(equation, field), Literal) for field in ("lhs", "rhs", "result", "unit"))
    assert equation.rhs.text == "2 * 3" and equation.result.text == "6.000"
    group = EquationGroup(equation, anchors=EquationAnchors(3, 15, 20, 22), label_columns=1)
    assert group.equations == (equation,) and group.gap == 4
    for obj, name, value in [(equation, "label", "changed"), (group, "gap", 0), (group.anchors, "first_equal", 4)]:
        with pytest.raises(FrozenInstanceError):
            setattr(obj, name, value)


@pytest.mark.parametrize("values", [
    {"lhs": 2}, {"rhs": object()}, {"result": 3}, {"unit": "m"},
    {"label": 2}, {"label": "a\tb"}, {"relation": 2}, {"relation": ""},
    {"relation": "=\n="}, {"result_relation": "\t"}, {"style": 10}, {"block_id": None},
])
def test_equation_rejects_invalid_fields(values):
    kwargs = {"lhs": "a", "rhs": "b", **values}
    with pytest.raises(ValueError):
        Equation(**kwargs)


@pytest.mark.parametrize("values", [
    {"first_equal": True}, {"first_equal": -1}, {"first_equal": 1.5},
    {"second_equal": float("inf")}, {"result_right": False}, {"unit_start": "20"},
    {"second_equal": 2}, {"second_equal": 8, "result_right": 7},
    {"result_right": 10, "unit_start": 9},
])
def test_anchor_columns_are_nonnegative_integers_in_strict_order(values):
    with pytest.raises(ValueError):
        EquationAnchors(**{"first_equal": 3, **values})


@pytest.mark.parametrize("values", [
    {"anchors": (3, 10)}, {"label_columns": True}, {"label_columns": -1},
    {"label_columns": 1.5}, {"gap": True}, {"gap": -1}, {"gap": float("nan")},
    {"style": "body"}, {"block_id": 4},
])
def test_group_rejects_invalid_configuration(values):
    with pytest.raises(ValueError):
        EquationGroup(Equation("a", "b"), **values)


def test_group_rejects_non_equation_children():
    with pytest.raises(ValueError, match="Equation"):
        EquationGroup("a")


def test_empty_group_is_zero_rows_and_still_validates_measurement_arguments():
    measured = EquationGroup(block_id="empty").measure(CONTEXT, WIDTH)
    assert measured.width == WIDTH and measured.parts == () and measured.rows == 0
    assert measured.prefer_keep and measured.block_id == "empty"
    with pytest.raises(ValueError, match="context"):
        EquationGroup().measure(None, WIDTH)
    with pytest.raises(ValueError, match="available_width"):
        EquationGroup().measure(CONTEXT, 0)


ANCHORS = EquationAnchors(8, 18, 24, 25)


def find_text(part, text):
    return next(command for command in part.commands if isinstance(command, Text) and command.text == text)


def test_explicit_two_relation_columns_results_and_units_share_anchors():
    group = EquationGroup(
        Equation("A", "2×3", result="6.000", unit="m"),
        Equation("BB", "4×5", result="20.00", unit="mm", relation="==", result_relation="=="),
        anchors=ANCHORS, block_id="eq-set",
    )
    measured = measure_block(group, CONTEXT, WIDTH)
    assert measured.width == WIDTH and measured.prefer_keep and len(measured.parts) == 2
    assert measured.block_id == "eq-set"
    for index, part in enumerate(measured.parts):
        relation = "=" if index == 0 else "=="
        relation_texts = [c for c in part.commands if isinstance(c, Text) and c.text == relation]
        assert [c.x + FONTS.measure(c.text, c.style).width / 2 for c in relation_texts] == pytest.approx([8 * PITCH, 18 * PITCH])
        result = find_text(part, ("6.000", "20.00")[index])
        assert result.x + FONTS.measure(result.text, result.style).width == pytest.approx(24 * PITCH)
        assert find_text(part, ("m", "mm")[index]).x == pytest.approx(25 * PITCH)
        assert find_text(part, ("2×3", "4×5")[index]).x == pytest.approx(9 * PITCH)
        assert part.metadata["equation_index"] == index
        assert part.metadata["anchors_pt"] == {"first_equal": 8 * PITCH, "second_equal": 18 * PITCH, "result_right": 24 * PITCH, "unit_start": 25 * PITCH}
        assert part.metadata["baseline_pt"] == 11
        assert part.metadata["rhs_start_pt"] == 9 * PITCH
        assert not part.metadata["continuation"] and not part.metadata["result_line"]


def test_equation_style_overrides_group_then_context_and_keeps_shared_centers():
    group = EquationGroup(Equation("a", "b"), Equation("c", "d", style=TextStyle(size=12)),
                          anchors=EquationAnchors(4), style=TextStyle(size=11))
    measured = measure_block(group, CONTEXT, WIDTH)
    for part, size in zip(measured.parts, (11, 12)):
        relation = find_text(part, "=")
        assert relation.x + size * .3 == pytest.approx(4 * PITCH)
        assert all(command.style.size == size for command in part.commands)
    default = EquationGroup(Equation("a", "b"), anchors=EquationAnchors(4)).measure(CONTEXT, WIDTH)
    assert all(command.style.size == 10 for command in default.commands)


@pytest.mark.parametrize("anchors, equation, message", [
    (EquationAnchors(4), Equation("a", "b", result="1"), "second_equal.*result_right"),
    (EquationAnchors(4, 10), Equation("a", "b", result="1"), "result_right"),
    (EquationAnchors(4, 10, 20), Equation("a", "b", result="1", unit="m"), "unit_start"),
])
def test_explicit_partial_result_anchors_are_errors_not_guesses(anchors, equation, message):
    with pytest.raises(ValueError, match=message):
        EquationGroup(equation, anchors=anchors).measure(CONTEXT, WIDTH)


@pytest.mark.parametrize("equation, anchors, target", [
    (Equation("a", "b"), EquationAnchors(31), "anchors"),
    (Equation("long" * 8, "b", block_id="long-lhs"), EquationAnchors(2), "lhs"),
    (Equation("a", "b", result="1" * 20), EquationAnchors(4, 18, 20), "result"),
    (Equation("a", "b", result="1", unit="m" * 10), EquationAnchors(4, 18, 24, 29), "unit"),
    (Equation("a", "b", relation="=" * 20), EquationAnchors(1), "lhs"),
])
def test_explicit_anchor_regions_detect_width_collisions(equation, anchors, target):
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(equation, anchors=anchors, block_id="set").measure(CONTEXT, WIDTH)
    assert target in caught.value.block_id
    assert caught.value.needed > caught.value.available >= 0


@pytest.mark.parametrize("has_unit, expected", [
    (True, {"first_equal": 1, "second_equal": 25, "result_right": 28, "unit_start": 29}),
    (False, {"first_equal": 1, "second_equal": 27, "result_right": 30, "unit_start": None}),
])
def test_automatic_anchors_reserve_result_and_unit_from_the_right(has_unit, expected):
    equation = Equation("A", "b", result="12345", unit="mm" if has_unit else None)
    measured = measure_block(EquationGroup(equation), CONTEXT, WIDTH)
    points = measured.parts[0].metadata["anchors_pt"]
    assert points == {key: value * PITCH if value is not None else None for key, value in expected.items()}
    assert measured.parts[0].metadata["rhs_start_pt"] == 2 * PITCH


def test_single_equation_delegates_to_group_and_no_result_uses_remaining_width():
    equation = Equation("a", "b", block_id="single")
    assert equation.measure(CONTEXT, WIDTH) == EquationGroup(equation, block_id="single").measure(CONTEXT, WIDTH)
    part, = measure_block(equation, CONTEXT, WIDTH).parts
    assert part.metadata["anchors_pt"] == {"first_equal": PITCH, "second_equal": None, "result_right": None, "unit_start": None}
    assert find_text(part, "b").x == 2 * PITCH


def test_automatic_anchors_remeasure_for_a3_without_mutating_group():
    group = EquationGroup(Equation("A", "b", result="12345", unit="mm"))
    original = repr(group)
    a4 = measure_block(group, CONTEXT, WIDTH)
    a3_context = LayoutContext(FONTS, A3_LANDSCAPE_REFERENCE, ReportStyle())
    a3 = measure_block(group, a3_context, 67 * PITCH)
    assert a3.parts[0].metadata["anchors_pt"] == {"first_equal": PITCH, "second_equal": 62 * PITCH, "result_right": 65 * PITCH, "unit_start": 66 * PITCH}
    assert group.anchors is None and repr(group) == original
    assert group.measure(CONTEXT, WIDTH) == a4


@pytest.mark.parametrize("equation, target", [
    (Equation("a" * 20, "b"), "lhs"),
    (Equation("a", "b", result="1" * 20), "result"),
    (Equation("a", "b", result="1", unit="m" * 20), "unit"),
    (Equation("a" * 6, "b", result="1" * 5), "rhs"),
])
def test_automatic_regions_fail_explicitly_when_reservations_exceed_width(equation, target):
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(equation, block_id="small").measure(CONTEXT, 80)
    assert target in caught.value.block_id
    assert caught.value.needed > caught.value.available >= 0


def test_label_wraps_inside_explicit_columns_and_extends_first_part_height():
    group = EquationGroup(Equation("A", Fraction("a", "b"), label="日本語見出"),
                          anchors=EquationAnchors(4), label_columns=1)
    part, = measure_block(group, CONTEXT, WIDTH).parts
    labels = [find_text(part, text) for text in ("日本", "語見", "出")]
    assert [c.x for c in labels] == [0, 0, 0]
    assert [c.y for c in labels] == pytest.approx([26.48, 41.96, 57.44])
    assert part.rows == 4
    assert part.metadata["baseline_pt"] == 26.48
    assert part.metadata["label_width_pt"] == PITCH
    assert find_text(part, "A").y == labels[0].y


def test_automatic_label_reservation_rounds_up_and_caps_at_six_columns():
    group = EquationGroup(Equation("A", "b", label="日" * 20))
    part, = measure_block(group, CONTEXT, WIDTH).parts
    assert part.metadata["label_width_pt"] == 6 * PITCH
    assert part.metadata["anchors_pt"]["first_equal"] == 8 * PITCH
    assert part.rows == 2
    assert [c.text for c in part.commands if isinstance(c, Text) and c.text.startswith("日")] == ["日" * 16, "日" * 4]


def test_explicit_anchors_limit_automatic_label_columns_to_available_left_region():
    group = EquationGroup(Equation("A", "b", label="日本語表記名"), anchors=EquationAnchors(4))
    part, = measure_block(group, CONTEXT, WIDTH).parts
    assert part.metadata["label_width_pt"] == 2 * PITCH
    assert part.rows == 2


def test_zero_label_columns_with_a_label_is_an_explicit_error():
    with pytest.raises(ValueError, match="label_columns"):
        EquationGroup(Equation("a", "b", label="名"), label_columns=0).measure(CONTEXT, WIDTH)


def test_label_reservation_cannot_overlap_lhs():
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("a", "b", label="名"), anchors=EquationAnchors(2), label_columns=2).measure(CONTEXT, WIDTH)
    assert "lhs" in caught.value.block_id
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("a", "b", label="名"), anchors=EquationAnchors(2)).measure(CONTEXT, WIDTH)
    assert "label" in caught.value.block_id


def test_explicit_label_newlines_and_initial_empty_line_preserve_height():
    group = EquationGroup(Equation("a", "b", label="\n名\n称"), label_columns=1)
    part, = measure_block(group, CONTEXT, WIDTH).parts
    assert part.rows == 3
    assert find_text(part, "名").y == pytest.approx(26.48)
    assert find_text(part, "称").y == pytest.approx(41.96)


def test_relation_anchor_uses_advance_center_with_overhanging_ink():
    class InkFonts(FixedFonts):
        def measure(self, text, style):
            return TextMetrics(6, 8, 2, Rect(-2, -8, 10, 10)) if text == "j" else super().measure(text, style)
    context = LayoutContext(InkFonts(), A4_PORTRAIT_REFERENCE, ReportStyle())
    group = EquationGroup(Equation("a", "b", relation="j"), anchors=EquationAnchors(4))
    part, = measure_block(group, context, WIDTH).parts
    relation = find_text(part, "j")
    assert relation.x + 3 == 4 * PITCH
    assert relation.x - 2 >= 0


def test_rhs_continuations_keep_start_order_size_and_result_on_last_rhs_line():
    rhs = Row("aaaaa", Operator("+"), "bbbbb", Operator("+"), "ccccc", Operator("+"), "ddddd", gap=0)
    group = EquationGroup(Equation("A", rhs, label="式名", result="999", unit="m"), anchors=ANCHORS)
    measured = measure_block(group, CONTEXT, WIDTH)
    assert len(measured.parts) == 2
    first, continuation = measured.parts
    assert [c.text for c in first.commands] == ["式名", "A", "=", "aaaaa", "+", "bbbbb", "+", "ccccc"]
    assert [c.text for c in continuation.commands] == ["+", "ddddd", "=", "999", "m"]
    assert find_text(first, "aaaaa").x == 9 * PITCH
    assert continuation.commands[0].x == 9 * PITCH
    assert not first.metadata["continuation"] and continuation.metadata["continuation"]
    assert continuation.metadata["line_index"] == 1 and not continuation.metadata["result_line"]
    assert all(c.style.size == 10 for c in measured.commands)


def test_wide_atomic_rhs_moves_result_and_unit_to_anchored_final_line():
    group = EquationGroup(Equation("A", "X" * 30, result="999", unit="m"), anchors=ANCHORS)
    measured = measure_block(group, CONTEXT, WIDTH)
    first, final = measured.parts
    assert [c.text for c in first.commands] == ["A", "=", "X" * 30]
    assert [c.text for c in final.commands] == ["=", "999", "m"]
    assert final.metadata["result_line"] and not final.metadata["continuation"]
    relation = find_text(final, "=")
    assert relation.x + 3 == 18 * PITCH
    assert find_text(final, "999").x + 18 == 24 * PITCH
    assert find_text(final, "m").x == 25 * PITCH
    assert all(c.style.size == 10 for c in measured.commands)


def test_fallback_full_width_can_itself_wrap_before_result_line():
    rhs = Row("X" * 30, Operator("+"), "Y" * 30, gap=0)
    measured = measure_block(EquationGroup(Equation("A", rhs, result="9"), anchors=ANCHORS), CONTEXT, WIDTH)
    assert len(measured.parts) == 3
    assert [c.text for c in measured.parts[1].commands] == ["+", "Y" * 30]
    assert measured.parts[1].commands[0].x == 9 * PITCH
    assert measured.parts[1].metadata["continuation"]
    assert measured.parts[2].metadata["result_line"]


def test_rhs_too_wide_even_without_result_reservation_reports_full_width():
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("A", "X" * 60, result="9", block_id="wide"), anchors=ANCHORS).measure(CONTEXT, WIDTH)
    assert caught.value.needed == 360
    assert caught.value.available == pytest.approx(WIDTH - 9 * PITCH)
    assert caught.value.block_id == "wide.rhs"


def test_explicit_rhs_breaks_and_group_split_preserve_local_anchors():
    rhs = Row("a", BreakHint("forced"), "b", BreakHint("forced"), "c")
    measured = measure_block(EquationGroup(Equation("A", rhs, result="9"), anchors=ANCHORS), CONTEXT, WIDTH)
    assert len(measured.parts) == 3 and measured.prefer_keep
    head, tail = measured.split(1)
    assert len(head.parts) == 1 and len(tail.parts) == 2
    assert all(p.metadata["anchors_pt"] == measured.parts[0].metadata["anchors_pt"] for p in (*head.parts, *tail.parts))
    assert tail.parts[0].commands[0].x == 9 * PITCH
    shifted = tail.translated(50, 100)
    assert shifted[0].x == 50 + 9 * PITCH
    assert tail.parts[0].metadata["rhs_start_pt"] == 9 * PITCH


def test_empty_rhs_still_draws_lhs_relation_and_result():
    part, = measure_block(EquationGroup(Equation("a", Row(), result="9"), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert [c.text for c in part.commands] == ["a", "=", "=", "9"]


def test_zero_normal_rhs_region_can_use_full_width_and_result_line():
    anchors = EquationAnchors(8, 10, 24, 25)
    measured = measure_block(EquationGroup(Equation("a", "b", result="9"), anchors=anchors), CONTEXT, WIDTH)
    assert len(measured.parts) == 2 and measured.parts[-1].metadata["result_line"]


def test_relation_ink_cannot_cross_block_edges_even_before_shared_validation():
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("a", "b", block_id="edge"), anchors=EquationAnchors(30)).measure(CONTEXT, WIDTH)
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (3, 0, "edge.relation")
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("a", "b", result="9", result_relation="=" * 20, block_id="edge"),
                      anchors=EquationAnchors(1, 2, 25)).measure(CONTEXT, WIDTH)
    assert caught.value.needed == 60
    assert caught.value.available == 2 * PITCH
    assert caught.value.block_id == "edge.result_relation"


def test_label_automatic_width_normalizes_cr_linebreaks_like_paragraph():
    part, = measure_block(EquationGroup(Equation("a", "b", label="名\r称")), CONTEXT, WIDTH).parts
    assert part.metadata["label_width_pt"] == PITCH
    assert part.rows == 2
    assert find_text(part, "称").y == pytest.approx(26.48)


def test_empty_rhs_needs_no_horizontal_space_at_exact_right_boundary():
    part, = measure_block(EquationGroup(Equation("a", Row()), anchors=EquationAnchors(29)), CONTEXT, WIDTH).parts
    assert [c.text for c in part.commands] == ["a", "="]
    assert part.metadata["rhs_start_pt"] == WIDTH


def test_each_math_axis_aligns_even_when_a_custom_atom_axis_differs():
    class ShiftedAxis:
        def measure(self, fonts, style):
            return MathBox(6, 8, 2, (Text(0, 0, "x", style),), 7)
    part, = measure_block(EquationGroup(Equation("a", ShiftedAxis()), anchors=EquationAnchors(4)), CONTEXT, WIDTH).parts
    assert find_text(part, "x").y - 7 == find_text(part, "=").y - 2.5
    assert part.rows == 2


def test_font_error_in_auto_label_measurement_keeps_label_path_and_cause():
    class MissingLabel(FixedFonts):
        def measure(self, text, style):
            if text == "bad-label":
                raise FontError("missing glyph")
            return super().measure(text, style)
    context = LayoutContext(MissingLabel(), A4_PORTRAIT_REFERENCE, ReportStyle())
    with pytest.raises(FontError) as caught:
        EquationGroup(Equation("a", "b", label="bad-label", block_id="source")).measure(context, WIDTH)
    assert "source.label" in str(caught.value)
    assert isinstance(caught.value.__cause__, FontError)


def test_no_result_rhs_overflow_retains_actual_available_width_and_path():
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("a", "b" * 80, block_id="rhs"), anchors=EquationAnchors(4)).measure(CONTEXT, WIDTH)
    assert caught.value.needed == 480
    assert caught.value.available == pytest.approx(WIDTH - 5 * PITCH)
    assert caught.value.block_id == "rhs.rhs"


@pytest.mark.parametrize("rhs, path", [("b", "empty-region.rhs"), (Row("b", Operator("+"), "c"), "empty-region.rhs[0]")])
def test_no_rhs_space_reports_real_atom_width_instead_of_an_arbitrary_grid_width(rhs, path):
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("a", rhs, block_id="empty-region"), anchors=EquationAnchors(29)).measure(CONTEXT, WIDTH)
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (6, 0, path)


def test_zero_width_literal_is_allowed_at_exact_rhs_boundary():
    part, = measure_block(EquationGroup(Equation("a", ""), anchors=EquationAnchors(29)), CONTEXT, WIDTH).parts
    assert part.commands[-1] == Text(WIDTH, 11, "", STYLE)


def test_zero_width_atoms_still_reserve_nonzero_gaps_at_rhs_boundary():
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("a", Row("", ""), block_id="zero"), anchors=EquationAnchors(29)).measure(CONTEXT, WIDTH)
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (1.5, 0, "zero.rhs")


@pytest.mark.parametrize("gap", [0, 1e-15])
@pytest.mark.parametrize("unit", ["m", Row()])
def test_zero_or_tiny_gap_keeps_automatic_result_and_unit_anchors_distinct(gap, unit):
    fonts = FontRegistry()
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())
    group = EquationGroup(Equation("A", "2", result="2", unit=unit),
                          Equation("B", "3", result="3", unit=unit, style=TextStyle(size=12)), gap=gap)
    measured = measure_block(group, context, WIDTH)
    for part in measured.parts:
        anchors = part.metadata["anchors_pt"]
        assert anchors["result_right"] <= anchors["unit_start"] - PITCH + 1e-9
        assert anchors["result_right"] / PITCH == pytest.approx(round(anchors["result_right"] / PITCH))


@pytest.mark.parametrize("gap", [0, 1e-15])
def test_zero_gap_scarce_width_reports_layout_overflow_not_anchor_constructor_failure(gap):
    with pytest.raises(LayoutOverflowError) as caught:
        EquationGroup(Equation("A", "2", result="2", unit="m"), gap=gap).measure(CONTEXT, 3 * PITCH)
    assert caught.value.needed > caught.value.available >= 0


def test_automatic_label_cap_is_a_paper_width_so_fine_grids_keep_their_labels():
    """The cap is 96.48 pt (six 16.08 pt reference columns) on every grid, not six columns of any pitch."""
    from gridlayoutpdf.profiles import GridSpec, PageProfile

    fine = LayoutContext(FONTS, PageProfile("fine", 595, 842, GridSpec(48, 72, .12, .12, 4400, 6000)), ReportStyle())
    short, = measure_block(EquationGroup(Equation("", "b", label="T / n")), fine, 528).parts
    assert short.metadata["label_width_pt"] == pytest.approx(30.0)  # natural 5 × 6 pt, on whole 0.12 pt columns
    assert [c.text for c in short.commands if isinstance(c, Text)][0] == "T / n"
    long, = measure_block(EquationGroup(Equation("", "b", label="日" * 20)), fine, 528).parts
    assert long.metadata["label_width_pt"] == pytest.approx(96.48)
    anchored, = measure_block(EquationGroup(Equation("", "b", label="T / n"), anchors=EquationAnchors(840)),
                              fine, 528).parts
    assert anchored.metadata["label_width_pt"] == pytest.approx(30.0)  # the anchors leave room: no extra limit
