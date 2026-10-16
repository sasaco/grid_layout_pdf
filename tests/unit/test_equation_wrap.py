"""Semantic wrapping checked against independent, hand-derived widths."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from gridlayoutpdf.equations import wrap_math
from gridlayoutpdf.errors import FontError, LayoutError, LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.math import BreakHint, Delimited, Fraction, Literal, Operator, Root, Row, Script, as_math
from gridlayoutpdf.scene import Text
from gridlayoutpdf.styles import TextStyle


class FixedFonts:
    """Each character advances 6 pt at the ordinary 10 pt style."""

    normalize_text = staticmethod(FontRegistry.normalize_text)

    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * 0.6, style.size * 0.8, style.size * 0.2)


FONTS = FixedFonts()
STYLE = TextStyle(size=10)


def texts(lines):
    return [tuple(command.text for command in line.commands if isinstance(command, Text))
            for line in lines]


@pytest.mark.parametrize("node", ["abcdef", Literal("abcdef")])
def test_single_atom_exact_fit_preserves_text_size_and_baseline(node):
    lines = wrap_math(node, FONTS, STYLE, 36)
    assert len(lines) == 1
    assert (lines[0].width, lines[0].ascent, lines[0].descent, lines[0].axis) == (36, 8, 2, 2.5)
    assert lines[0].commands == (Text(0, 0, "abcdef", STYLE),)


@pytest.mark.parametrize("block_id, expected_path", [("eq-7", "eq-7.rhs"), ("", "rhs")])
def test_atomic_overflow_reports_required_width_available_width_and_path(block_id, expected_path):
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math("abcdef", FONTS, STYLE, 36 - 1e-9, block_id=block_id)
    assert caught.value.needed == 36
    assert caught.value.available == 36 - 1e-9
    assert caught.value.block_id == expected_path
    assert expected_path in str(caught.value)


@pytest.mark.parametrize("invalid", [0, -1, True, False, float("nan"), float("inf"), -float("inf"), "20", None])
def test_available_width_must_be_finite_positive_number(invalid):
    with pytest.raises(ValueError, match="available_width"):
        wrap_math("a", FONTS, STYLE, invalid)


@pytest.mark.parametrize("invalid", [None, 10, True])
def test_block_id_must_be_a_string(invalid):
    with pytest.raises(ValueError, match="block_id"):
        wrap_math("a", FONTS, STYLE, 20, block_id=invalid)


def test_empty_row_returns_no_lines_but_validates_context():
    assert wrap_math(Row(), FONTS, STYLE, 1) == ()
    with pytest.raises(ValueError, match="style"):
        wrap_math(Row(), FONTS, None, 1)
    with pytest.raises(ValueError, match="fonts"):
        wrap_math(Row(), None, STYLE, 1)


def test_non_math_input_is_rejected():
    with pytest.raises(ValueError, match="math node"):
        wrap_math(42, FONTS, STYLE, 20)


@pytest.mark.parametrize("gap", [None, 0, 2])
def test_row_exact_fit_and_narrower_width_preserve_order_size_and_original_gap(gap):
    node = Row("a", Operator("+"), "b", Operator("+"), "c", gap=gap)
    actual_gap = 1.5 if gap is None else gap
    exact_width = 30 + 4 * actual_gap
    assert texts(wrap_math(node, FONTS, STYLE, exact_width)) == [("a", "+", "b", "+", "c")]
    lines = wrap_math(node, FONTS, STYLE, exact_width - 1e-9)
    assert texts(lines) == [("a", "+", "b"), ("+", "c")]
    assert [line.width for line in lines] == [18 + 2 * actual_gap, 12 + actual_gap]
    for line in lines:
        assert [command.x for command in line.commands] == [i * (6 + actual_gap) for i in range(len(line.commands))]
        assert all(command.style.size == 10 and command.y == 0 for command in line.commands)
    narrower = wrap_math(node, FONTS, STYLE, 18 + 2 * actual_gap - 1e-9)
    assert texts(narrower) == [("a",), ("+", "b"), ("+", "c")]


@pytest.mark.parametrize("symbol", ["+", "-", "−"])
def test_additive_breaks_keep_operator_at_start_of_continuation(symbol):
    node = Row("a", Operator(symbol), "b", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 12)) == [("a",), (symbol, "b")]


def test_farthest_candidate_of_same_priority_is_selected():
    node = Row("a", Operator("+"), "b", Operator("+"), "c", Operator("+"), "d", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 30)) == [("a", "+", "b", "+", "c"), ("+", "d")]


def test_operator_at_start_is_not_an_empty_line_candidate():
    node = Row(Operator("+"), "a", Operator("+"), "b", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 18)) == [("+", "a"), ("+", "b")]
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(node, FONTS, STYLE, 10, block_id="eq")
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (12, 10, "eq.rhs[0:2]")


def test_unsplittable_row_chunk_reports_its_required_width_and_original_range():
    node = Row("a", "b", "c", gap=0)
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(node, FONTS, STYLE, 17, block_id="eq")
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (18, 17, "eq.rhs[0:3]")


def test_individual_wide_atom_is_identified_before_the_surrounding_chunk():
    node = Row("a", Operator("+"), "long", gap=0)
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(node, FONTS, STYLE, 12, block_id="eq")
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (24, 12, "eq.rhs[2]")


def test_continuation_operator_and_following_atom_form_an_unsplittable_chunk():
    node = Row("a", Operator("+"), "bb", gap=0)
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(node, FONTS, STYLE, 12, block_id="eq")
    assert (caught.value.needed, caught.value.available, caught.value.block_id) == (18, 12, "eq.rhs[1:3]")


@pytest.mark.parametrize("mode", ["forced", "preferred", "allowed"])
def test_break_hint_is_immutable_math_node_that_requires_equation_wrapping(mode):
    hint = BreakHint(mode)
    assert BreakHint().mode == "preferred"
    assert as_math(hint) is hint
    assert Row(hint).items == (hint,)
    with pytest.raises(FrozenInstanceError):
        hint.mode = "forced"
    with pytest.raises(LayoutError, match="^BreakHint requires equation wrapping$"):
        hint.measure(FONTS, STYLE)


@pytest.mark.parametrize("mode", ["", "auto", "Forced", None, True, 1, []])
def test_break_hint_rejects_unknown_modes(mode):
    with pytest.raises(ValueError, match="mode"):
        BreakHint(mode)


@pytest.mark.parametrize("container", [
    lambda hint: Fraction(Row("a", hint, "b"), "c"),
    lambda hint: Fraction("a", Row("b", hint, "c")),
    lambda hint: Root(Row("a", hint, "b")),
    lambda hint: Delimited(Row("a", hint, "b")),
    lambda hint: Script("a", superscript=Row("b", hint, "c")),
    lambda hint: Row(Row("a", hint, "b")),
])
def test_hints_inside_atomic_structures_are_not_silently_discarded(container):
    with pytest.raises(LayoutError, match="^BreakHint requires equation wrapping$"):
        wrap_math(container(BreakHint()), FONTS, STYLE, 1000)


@pytest.mark.parametrize("symbol", ["=", "<", ">", "≦", "≧", "≤", "≥", "≈", "≠"])
def test_top_level_relations_are_automatic_boundaries(symbol):
    assert texts(wrap_math(Row("a", Operator(symbol), "b", gap=0), FONTS, STYLE, 12)) == [("a",), (symbol, "b")]


def test_fullwidth_equal_is_a_relation_boundary_preserving_real_advance(real_fonts):
    node = Row("日", Operator("＝"), "本", gap=0)
    lines = wrap_math(node, real_fonts, STYLE, 20)
    assert texts(lines) == [("日",), ("＝", "本")]
    assert [line.width for line in lines] == [10, 20]
    assert lines[1].commands == (Text(0, 0, "＝", STYLE), Text(10, 0, "本", STYLE))
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(node, real_fonts, STYLE, 20 - 1e-9)
    assert caught.value.needed == 20


def test_preferred_hint_outranks_later_relation_and_additive_candidates():
    node = Row("a", BreakHint(), Operator("+"), "b", Operator("="), "c", Operator("+"), "d", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 36)) == [("a",), ("+", "b", "=", "c", "+", "d")]


def test_relation_outranks_later_additive_candidates():
    node = Row("a", Operator("="), "b", Operator("+"), "c", Operator("+"), "d", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 30)) == [("a",), ("=", "b", "+", "c"), ("+", "d")]


def test_additive_candidate_outranks_later_allowed_hint():
    node = Row("a", Operator("+"), "b", BreakHint("allowed"), Operator("×"), "c", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 24)) == [("a",), ("+", "b", "×", "c")]


def test_farthest_preferred_hint_wins_tie():
    node = Row("a", BreakHint(), Operator("+"), "b", BreakHint(), Operator("+"), "c", Operator("+"), "d", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 30)) == [("a", "+", "b"), ("+", "c", "+", "d")]


@pytest.mark.parametrize("symbol", ["×", "÷"])
def test_multiplication_and_division_require_an_explicit_boundary(symbol):
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(Row("a", Operator(symbol), "b", gap=0), FONTS, STYLE, 12)
    assert (caught.value.needed, caught.value.block_id) == (18, "rhs[0:3]")
    node = Row("a", BreakHint("allowed"), Operator(symbol), "b", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 12)) == [("a",), (symbol, "b")]


def test_hints_add_no_width_or_gap_and_do_not_force_break_when_all_fits():
    node = Row("a", BreakHint(), BreakHint("allowed"), Operator("+"), "b", gap=2)
    line, = wrap_math(node, FONTS, STYLE, 22)
    assert line.width == 22
    assert [command.x for command in line.commands] == [0, 8, 16]
    assert texts((line,)) == [("a", "+", "b")]


def test_literal_operator_characters_are_not_semantic_boundaries():
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(Row("a", "+", "b", gap=0), FONTS, STYLE, 12)
    assert caught.value.needed == 18


def test_nonfitting_preferred_boundary_does_not_produce_an_overwide_line():
    node = Row("a", "b", "c", BreakHint(), Operator("+"), "d", gap=0)
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(node, FONTS, STYLE, 12, block_id="eq")
    assert (caught.value.needed, caught.value.block_id) == (18, "eq.rhs[0:3]")


def test_hint_removal_preserves_original_atom_index_in_overflow_diagnostic():
    node = Row("a", BreakHint(), Operator("+"), "long", gap=0)
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(node, FONTS, STYLE, 12, block_id="eq")
    assert (caught.value.needed, caught.value.block_id) == (24, "eq.rhs[3]")


def test_forced_break_is_honored_even_when_the_entire_row_fits():
    node = Row("a", BreakHint("forced"), Operator("+"), "b", BreakHint("forced"), "c", gap=2)
    lines = wrap_math(node, FONTS, STYLE, 1000)
    assert texts(lines) == [("a",), ("+", "b"), ("c",)]
    assert [line.width for line in lines] == [6, 14, 6]


def test_forced_segment_that_fits_ignores_earlier_preferred_hint():
    node = Row("a", BreakHint(), "b", BreakHint("forced"), "c", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 1000)) == [("a", "b"), ("c",)]


def test_automatic_wrapping_operates_independently_inside_forced_segments():
    node = Row("a", Operator("+"), "b", BreakHint("forced"), "c", Operator("-"), "d", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 12)) == [("a",), ("+", "b"), ("c",), ("-", "d")]


@pytest.mark.parametrize("items", [
    (BreakHint("forced"), "a"),
    ("a", BreakHint("forced")),
    ("a", BreakHint("forced"), BreakHint("forced"), "b"),
    ("a", BreakHint("forced"), BreakHint(), BreakHint("forced"), "b"),
    (BreakHint("forced"),),
    (BreakHint(),),
    ("a", BreakHint()),
    ("a", BreakHint("allowed")),
    ("a", BreakHint(), BreakHint("allowed")),
])
def test_malformed_hints_cannot_create_empty_lines_or_dangle(items):
    with pytest.raises(ValueError, match="following atom|empty line"):
        wrap_math(Row(*items), FONTS, STYLE, 1000)


@pytest.mark.parametrize("mode", ["preferred", "allowed"])
def test_leading_optional_hint_is_never_an_empty_line_candidate(mode):
    node = Row(BreakHint(mode), "a", Operator("+"), "b", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 12)) == [("a",), ("+", "b")]


def test_an_allowed_hint_after_forced_break_does_not_create_empty_line():
    node = Row("a", BreakHint("forced"), BreakHint("allowed"), "b", gap=0)
    assert texts(wrap_math(node, FONTS, STYLE, 12)) == [("a",), ("b",)]


def test_unsplittable_chunk_diagnostic_stops_at_forced_boundary():
    node = Row("a", "b", BreakHint("forced"), "c", gap=0)
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(node, FONTS, STYLE, 10, block_id="eq")
    assert (caught.value.needed, caught.value.block_id) == (12, "eq.rhs[0:2]")


STRUCTURED_ATOMS = [
    (Fraction(Row("a", Operator("+"), "b", gap=0), "c"), 21),
    (Root(Row("a", Operator("+"), "b", gap=0)), 26.5),
    (Script("a", superscript=Row("b", Operator("+"), "c", gap=0)), 18.7),
    (Delimited(Row("a", Operator("+"), "b", gap=0)), 28),
    (Row("a", Operator("+"), "b", gap=0), 18),
]


@pytest.mark.parametrize("atom, expected_width", STRUCTURED_ATOMS)
def test_structured_atoms_are_kept_whole_on_continuation(atom, expected_width):
    node = Row("x", Operator("+"), atom, gap=0)
    lines = wrap_math(node, FONTS, STYLE, expected_width + 6 + 1e-9)
    assert len(lines) == 2
    assert texts(lines)[0] == ("x",)
    assert lines[1].width == pytest.approx(expected_width + 6)
    assert lines[1].commands[0] == Text(0, 0, "+", STYLE)
    assert lines[1].commands[1:] == atom.measure(FONTS, STYLE).translated(6, 0)


@pytest.mark.parametrize("atom, expected_width", STRUCTURED_ATOMS)
def test_structured_atom_overflow_does_not_cut_internal_operator(atom, expected_width):
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math(Row(atom), FONTS, STYLE, expected_width - 1, block_id="eq")
    assert caught.value.needed == pytest.approx(expected_width)
    assert caught.value.block_id == "eq.rhs[0]"


@pytest.fixture(scope="module")
def real_fonts():
    fonts = FontRegistry()
    fonts.register("body", Path(__file__).resolve().parents[1] / "fixtures/fonts/ipaexm.ttf")
    return fonts


@pytest.mark.parametrize("node, path", [
    (Literal("\U0010ffff"), "eq-font.rhs"),
    (Row("a", BreakHint(), Operator("+"), Fraction("b", "\U0010ffff")), "eq-font.rhs[3]"),
])
def test_missing_glyph_retains_font_error_type_cause_and_equation_path(real_fonts, node, path):
    with pytest.raises(FontError) as caught:
        wrap_math(node, real_fonts, STYLE, 1000, block_id="eq-font")
    assert path in str(caught.value)
    assert "10FFFF" in str(caught.value)
    assert isinstance(caught.value.__cause__, FontError)


def test_real_ipa_ink_overhang_determines_fit_not_only_text_advance(real_fonts):
    line, = wrap_math("j", real_fonts, STYLE, 3.583984375)
    assert line.width == 3.583984375
    assert line.commands == (Text(0.5419921875, 0, "j", STYLE),)
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_math("j", real_fonts, STYLE, 3.583984375 - 1e-9)
    assert caught.value.needed == 3.583984375
    node = Row("j", BreakHint("allowed"), "j", gap=0)
    assert texts(wrap_math(node, real_fonts, STYLE, 7)) == [("j",), ("j",)]


def test_repeated_wrap_calls_leave_immutable_input_tree_and_styles_unchanged():
    atom = Fraction(Root("α"), Script("x", superscript="2"))
    node = Row("a", BreakHint(), Operator("+"), atom, BreakHint("forced"), "b", gap=1)
    original_items = node.items
    original_repr = repr(node)
    first = wrap_math(node, FONTS, STYLE, 30)
    assert wrap_math(node, FONTS, STYLE, 30) == first
    assert node.items is original_items
    assert repr(node) == original_repr
    assert STYLE.size == 10 and node.gap == 1
    assert texts(first) == [("a",), ("+", "α", "x", "2"), ("b",)]
    with pytest.raises(FrozenInstanceError):
        node.items = ()
