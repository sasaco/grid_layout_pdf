"""Independent layout arithmetic for baseline-relative math components."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.math import Delimited, Fraction, Literal, MathBox, Operator, Root, Row, Script, Symbol, as_math
from gridlayoutpdf.scene import Line, Polyline, Rectangle, Text
from gridlayoutpdf.styles import TextStyle


class FixedFonts:
    """Predictable advances for hand-derived geometric expectations."""

    normalize_text = staticmethod(FontRegistry.normalize_text)

    def measure(self, text, style):
        return TextMetrics(
            len(text) * style.size * 0.6 + max(0, len(text) - 1) * style.tracking,
            style.size * 0.8,
            style.size * 0.2,
        )


FONTS = FixedFonts()
STYLE = TextStyle(size=10)


def command_bounds(command, fonts=FONTS):
    """Conservative stroke-inclusive bounds independently from math layout."""
    if isinstance(command, Text):
        metrics = fonts.measure(command.text, command.style)
        bounds = metrics.bounds
        return (command.x + bounds.x, command.y + bounds.y,
                command.x + bounds.right, command.y + bounds.bottom)
    if isinstance(command, Line):
        half = command.width / 2
        return (min(command.x1, command.x2) - half,
                min(command.y1, command.y2) - half,
                max(command.x1, command.x2) + half,
                max(command.y1, command.y2) + half)
    if isinstance(command, Polyline):
        half = command.width / 2
        return (min(p.x for p in command.points) - half,
                min(p.y for p in command.points) - half,
                max(p.x for p in command.points) + half,
                max(p.y for p in command.points) + half)
    if isinstance(command, Rectangle):
        half = command.stroke_width / 2
        return (command.x - half, command.y - half,
                command.x + command.width + half,
                command.y + command.height + half)
    raise AssertionError(type(command))


def assert_commands_fit(box, fonts=FONTS):
    for command in box.commands:
        left, top, right, bottom = command_bounds(command, fonts)
        assert left >= -1e-9
        assert right <= box.width + 1e-9
        assert top >= -box.ascent - 1e-9
        assert bottom <= box.descent + 1e-9


@pytest.mark.parametrize("node_type", [Literal, Symbol, Operator])
def test_text_nodes_use_shared_metrics_and_preserve_baseline_style(node_type):
    style = TextStyle(size=10, tracking=0.25)
    node = node_type("αβ")
    box = node.measure(FONTS, style)
    assert (box.width, box.ascent, box.descent, box.axis) == (12.25, 8, 2, 2.5)
    assert box.height == 10
    assert box.commands == (Text(0, 0, "αβ", style),)
    assert box.translated(40, 50) == (Text(40, 50, "αβ", style),)
    assert node.measure(FONTS, style) == box
    assert_commands_fit(box)
    with pytest.raises(FrozenInstanceError):
        node.text = "different"
    with pytest.raises(FrozenInstanceError):
        box.width = 1


def test_literal_normalizes_text_once_before_measuring_and_drawing():
    box = Literal("か\u3099").measure(FONTS, STYLE)
    assert box.width == 6
    assert box.commands[0].text == "が"


@pytest.mark.parametrize("field", ["width", "ascent", "descent", "axis"])
@pytest.mark.parametrize("invalid", [-1, True, float("inf"), float("nan"), "1", None])
def test_mathbox_rejects_invalid_dimensions(field, invalid):
    values = dict(width=12, ascent=8, descent=2, commands=(), axis=2.5)
    values[field] = invalid
    with pytest.raises(ValueError, match=field):
        MathBox(**values)


def test_mathbox_snapshots_commands_and_validates_empty_translation():
    commands = [Text(0, 0, "a", STYLE)]
    box = MathBox(6, 8, 2, commands, 2.5)
    commands.clear()
    assert box.commands == (Text(0, 0, "a", STYLE),)
    for commands in (None, ["wrong"]):
        with pytest.raises(ValueError, match="commands"):
            MathBox(0, 0, 0, commands, 0)
    with pytest.raises(ValueError, match="height"):
        MathBox(0, 1e308, 1e308, (), 0)
    empty = MathBox(0, 0, 0, (), 0)
    with pytest.raises(ValueError, match="dx"):
        empty.translated(True, 0)
    with pytest.raises(ValueError, match="dy"):
        empty.translated(0, float("nan"))
    assert empty.height == 0


@pytest.mark.parametrize("invalid", [None, 1, True, [], "a\nb", "a\rb", "a\tb"])
def test_literal_rejects_nontext_and_multiline_atoms(invalid):
    with pytest.raises(ValueError, match="text"):
        Literal(invalid)


def test_as_math_lifts_strings_without_parsing_and_preserves_nodes():
    node = Operator("+")
    assert as_math(node) is node
    assert as_math(r"x^{2}") == Literal(r"x^{2}")
    assert as_math("").measure(FONTS, STYLE).width == 0
    for invalid in (None, True, 12, [node], object()):
        with pytest.raises(ValueError, match="math"):
            as_math(invalid)


def test_row_preserves_atom_order_baselines_and_default_gap():
    source = [Symbol("x"), Operator("="), "12"]
    row = Row(*source)
    source.clear()
    assert row.items == (Symbol("x"), Operator("="), Literal("12"))
    box = row.measure(FONTS, STYLE)
    assert (box.width, box.ascent, box.descent, box.axis) == (27, 8, 2, 2.5)
    assert [(c.text, c.x, c.y) for c in box.commands] == [("x", 0, 0), ("=", 7.5, 0), ("12", 15, 0)]
    assert Row("x", "y", gap=0).measure(FONTS, STYLE).width == 12
    assert Row("x", "y", gap=2).measure(FONTS, STYLE).width == 14
    assert Row().measure(FONTS, STYLE).commands == ()
    assert Row().measure(FONTS, STYLE).width == 0
    assert_commands_fit(box)
    with pytest.raises(FrozenInstanceError):
        row.items = ()


def test_row_aligns_a_child_with_a_different_axis():
    class RaisedAxisNode:
        def measure(self, fonts, style):
            return MathBox(6, 8, 2, (Text(0, 0, "z", style),), 4.5)

    box = Row("x", RaisedAxisNode(), gap=1).measure(FONTS, STYLE)
    assert (box.width, box.ascent, box.descent, box.axis) == (13, 8, 4, 2.5)
    assert box.commands[1] == Text(7, 2, "z", STYLE)
    assert_commands_fit(box)


@pytest.mark.parametrize("gap", [-0.01, True, float("inf"), float("nan"), "1"])
def test_row_rejects_invalid_gap(gap):
    with pytest.raises(ValueError, match="gap"):
        Row("x", gap=gap)


def test_row_rejects_invalid_children():
    with pytest.raises(ValueError, match="math"):
        Row("x", object())


def test_fraction_has_hand_derived_baselines_and_stroke_clearance():
    fraction = Fraction("ab", "c")
    box = fraction.measure(FONTS, STYLE)
    assert (box.width, box.ascent, box.descent, box.axis) == (15, 14.25, 9.25, 2.5)
    assert box.height == 23.5
    texts = [command for command in box.commands if isinstance(command, Text)]
    assert texts == [Text(1.5, -6.25, "ab", STYLE), Text(4.5, 7.25, "c", STYLE)]
    line, = [command for command in box.commands if isinstance(command, Line)]
    assert line == Line(0.25, -2.5, 14.75, -2.5, width=0.5)
    assert command_bounds(texts[0])[3] == line.y1 - line.width / 2 - 1.5
    assert command_bounds(texts[1])[1] == line.y1 + line.width / 2 + 1.5
    assert fraction.numerator == Literal("ab")
    assert fraction.denominator == Literal("c")
    assert fraction.measure(FONTS, STYLE) == box
    assert_commands_fit(box)
    with pytest.raises(FrozenInstanceError):
        fraction.numerator = Literal("z")


def test_nested_fraction_grows_height_without_shrinking_text():
    simple = Fraction("a", "b").measure(FONTS, STYLE)
    box = Fraction(Fraction("a", "b"), "c").measure(FONTS, STYLE)
    assert box.height == 37
    assert box.height > simple.height
    assert box.width == 12
    assert [c.style.size for c in box.commands if isinstance(c, Text)] == [10, 10, 10]
    assert_commands_fit(box)


@pytest.mark.parametrize(("numerator", "denominator"), [(None, "x"), ("x", True), ([], "x")])
def test_fraction_rejects_invalid_children(numerator, denominator):
    with pytest.raises(ValueError, match="math"):
        Fraction(numerator, denominator)


def test_script_uses_explicit_size_ratio_and_separates_superscript_subscript():
    node = Script("x", superscript="2", subscript="i")
    box = node.measure(FONTS, STYLE)
    assert box.width == pytest.approx(10.9)
    assert box.ascent == pytest.approx(11.2)
    assert box.descent == pytest.approx(5.5)
    base, upper, lower = box.commands
    assert base == Text(0, 0, "x", STYLE)
    assert (upper.x, upper.y, upper.style.size) == (7, -6, 6.5)
    assert lower.x == 7
    assert lower.y == pytest.approx(4.2)
    assert lower.style.size == 6.5
    assert command_bounds(lower)[1] - command_bounds(upper)[3] >= 1.5
    assert box.axis == 2.5
    assert_commands_fit(box)
    assert Script("x").measure(FONTS, STYLE) == Literal("x").measure(FONTS, STYLE)


def test_script_sizes_are_exempt_from_the_half_point_rule():
    """FR-023: 12 pt x 0.65 = 7.8 pt and nested scripts are built internally."""
    style = TextStyle(size=12)
    box = Script("x", superscript=Script("y", superscript="z"), subscript="i").measure(FONTS, style)
    sizes = {c.text: c.style.size for c in box.commands if isinstance(c, Text)}
    assert sizes["x"] == 12
    assert sizes["y"] == pytest.approx(7.8)
    assert sizes["i"] == pytest.approx(7.8)
    assert sizes["z"] == pytest.approx(12 * .65 * .65)
    assert all(c.style.font == style.font for c in box.commands if isinstance(c, Text))
    with pytest.raises(ValueError, match=r"multiple of 0\.5 pt"):
        TextStyle(size=sizes["y"])


def test_explicit_script_scale_may_produce_a_size_off_the_half_point_steps():
    box = Script("x", superscript="2", scale=.66).measure(FONTS, TextStyle(size=9.5))
    assert box.commands[1].style.size == pytest.approx(9.5 * .66)


def test_fraction_in_exponent_keeps_its_script_context_size():
    node = Script(Fraction("a", "b"), superscript=Fraction("1", "2"))
    box = node.measure(FONTS, STYLE)
    text = [c for c in box.commands if isinstance(c, Text)]
    assert [c.text for c in text] == ["a", "b", "1", "2"]
    assert [c.style.size for c in text] == [10, 10, 6.5, 6.5]
    assert min(c.y for c in text[2:]) < min(c.y for c in text[:2])
    assert box.height > Fraction("a", "b").measure(FONTS, STYLE).height
    assert_commands_fit(box)


def test_tall_scripts_cannot_overlap_each_other():
    box = Script("x", superscript=Fraction("a", "b"), subscript=Fraction("c", "d")).measure(FONTS, STYLE)
    upper = [c for c in box.commands if isinstance(c, Text) and c.text in "ab"]
    lower = [c for c in box.commands if isinstance(c, Text) and c.text in "cd"]
    assert min(command_bounds(c)[1] for c in lower) - max(command_bounds(c)[3] for c in upper) >= 1.5 - 1e-9
    assert_commands_fit(box)


@pytest.mark.parametrize("values", [(None, None, None), ("x", True, None), ("x", None, [])])
def test_script_rejects_invalid_children(values):
    with pytest.raises(ValueError, match="math"):
        Script(*values)


def test_script_explicit_scale_and_baseline_offsets_preserve_requested_values():
    assert {"scale", "superscript_rise", "subscript_drop"} <= Script.__dataclass_fields__.keys()
    box = Script("x", "2", "i", scale=.8,
                 superscript_rise=7.25, subscript_drop=4.75).measure(FONTS, STYLE)
    base, upper, lower = box.commands
    assert (upper.y, lower.y) == (-7.25, 4.75)
    assert (upper.style.size, lower.style.size) == (8, 8)
    assert (base.x, base.y, base.style.size) == (0, 0, 10)
    assert (box.width, box.ascent, box.descent) == pytest.approx((11.8, 13.65, 6.35))
    assert_commands_fit(box)


@pytest.mark.parametrize("field, invalid", [
    *(('scale', value) for value in (True, 0, -1, 1.01, float('inf'), float('nan'), '0.5')),
    *((field, value) for field in ('superscript_rise', 'subscript_drop')
      for value in (True, 0, -1, float('inf'), float('nan'), '2')),
])
def test_script_rejects_invalid_explicit_style(field, invalid):
    with pytest.raises(ValueError, match=field):
        Script("x", "2", "i", **{field: invalid})


@pytest.mark.parametrize("kwargs", [{"superscript_rise": 4}, {"subscript_drop": 4}])
def test_script_rejects_offset_without_corresponding_child(kwargs):
    with pytest.raises(ValueError, match="requires"):
        Script("x", **kwargs)


def test_script_explicit_arguments_are_keyword_only():
    with pytest.raises(TypeError):
        Script("x", "2", "i", .5)


@pytest.mark.parametrize("kwargs", [
    {"superscript": "2", "superscript_rise": .01},
    {"subscript": "2", "scale": 1, "subscript_drop": .01},
])
def test_script_rejects_explicit_ink_on_wrong_side_of_math_axis(kwargs):
    from gridlayoutpdf.errors import LayoutError
    with pytest.raises(LayoutError, match="role"):
        Script("x", **kwargs).measure(FONTS, STYLE)


def test_script_explicit_scripts_must_have_clearance_without_changing_offsets():
    from gridlayoutpdf.errors import LayoutError
    with pytest.raises(LayoutError, match="clearance"):
        Script("x", "2", "i", superscript_rise=2, subscript_drop=.1).measure(FONTS, STYLE)


@pytest.mark.parametrize("fixed_side", ["upper", "lower"])
def test_script_moves_only_auto_side_to_preserve_clearance(fixed_side):
    kwargs = {"superscript_rise": 2} if fixed_side == "upper" else {"subscript_drop": .1}
    box = Script("x", "2", "i", **kwargs).measure(FONTS, STYLE)
    base, upper, lower = box.commands
    assert upper.y == -2 if fixed_side == "upper" else lower.y == .1
    assert command_bounds(lower)[1] - command_bounds(upper)[3] >= 1.5 - 1e-9
    assert_commands_fit(box)


def test_script_explicit_offsets_follow_base_baseline_when_axis_differs():
    class ShiftedBase:
        def measure(self, fonts, style):
            return MathBox(6, 8, 2, (Text(0, 0, "x", style),), 4.5)
    box = Script(ShiftedBase(), "2", "i", superscript_rise=7, subscript_drop=4).measure(FONTS, STYLE)
    assert [command.y for command in box.commands] == [2, -5, 6]
    assert_commands_fit(box)


def test_script_default_keywords_have_exact_legacy_output():
    implicit = Script(Fraction("a", "b"), Fraction("c", "d"), Root("e"))
    explicit = Script(Fraction("a", "b"), Fraction("c", "d"), Root("e"), scale=.65,
                      superscript_rise=None, subscript_drop=None)
    assert implicit.measure(FONTS, STYLE) == explicit.measure(FONTS, STYLE)


@pytest.mark.parametrize("node", [
    Script("j", "Å", "g", scale=.8, superscript_rise=8, subscript_drop=6),
    Script(Fraction("a", "b"), Root("j"), "g", scale=.7, superscript_rise=16, subscript_drop=8),
    Script(Root("x"), Script("j", "2"), Fraction("1", "g"), scale=.75,
           superscript_rise=14, subscript_drop=12),
    Script("x", "", " ", scale=1, superscript_rise=1, subscript_drop=1),
])
def test_explicit_scripts_keep_real_glyph_and_nested_stroke_extents(real_fonts, node):
    box = node.measure(real_fonts, STYLE)
    assert_commands_fit(box, real_fonts)
    assert box == node.measure(real_fonts, STYLE)


def test_explicit_role_uses_glyph_ink_instead_of_typographic_rectangle(real_fonts):
    # A small serif digit's real ink lies above the axis, though its conservative
    # typographic rectangle has its center below it at this requested rise.
    box = Script("x", "2", superscript_rise=.5).measure(real_fonts, STYLE)
    assert box.commands[1].y == -.5
    assert_commands_fit(box, real_fonts)
    from gridlayoutpdf.errors import LayoutError
    with pytest.raises(LayoutError, match="role"):
        Script("x", "g", superscript_rise=.01).measure(real_fonts, STYLE)


@pytest.mark.parametrize("side", ["upper", "lower"])
def test_explicit_script_rejects_base_ink_contact_from_custom_node(side):
    from gridlayoutpdf.errors import LayoutError
    class OverhangingBase:
        def measure(self, fonts, style):
            # Deliberately underspecified custom box: the public Script still
            # checks its rendered commands instead of trusting width alone.
            return MathBox(1, 8, 2, (Text(0, 0, "base", style),), 2.5)
    kwargs = {"superscript": "2", "superscript_rise": 4} if side == "upper" else {
        "subscript": "g", "subscript_drop": 3}
    with pytest.raises(LayoutError, match="contacts the base"):
        Script(OverhangingBase(), **kwargs).measure(FONTS, STYLE)


@pytest.mark.parametrize("scale", [.5, 1])
def test_explicit_scale_with_auto_offsets_preserves_roles_and_clearance(scale):
    box = Script("x", Fraction("1", "2"), Fraction("3", "4"), scale=scale).measure(FONTS, STYLE)
    assert_commands_fit(box)
    assert {c.style.size for c in box.commands[1:] if isinstance(c, Text)} == {10 * scale}
    upper = [command_bounds(c) for c in box.commands[1:4]]
    lower = [command_bounds(c) for c in box.commands[4:]]
    assert min(r[1] for r in lower) - max(r[3] for r in upper) >= 1.5 - 1e-9


def test_root_uses_a_vector_checkmark_and_overbar_above_greek_text():
    root = Root("αβ")
    box = root.measure(FONTS, STYLE)
    assert (box.width, box.ascent, box.descent, box.axis) == (20.5, 10, 2, 2.5)
    text, = [c for c in box.commands if isinstance(c, Text)]
    assert text == Text(7.5, 0, "αβ", STYLE)
    radical, = [c for c in box.commands if isinstance(c, Polyline)]
    assert len(radical.points) >= 5
    assert radical.width == 0.5
    assert radical.points[-1].y == -9.75
    assert radical.points[-2].y == -9.75
    assert command_bounds(text)[1] - (radical.points[-1].y + radical.width / 2) == 1.5
    assert root.body == Literal("αβ")
    assert_commands_fit(box)


def test_root_grows_with_tall_radicand_and_preserves_text_sizes():
    box = Root(Fraction("α", "β")).measure(FONTS, STYLE)
    assert box.ascent == 16.25
    assert [c.style.size for c in box.commands if isinstance(c, Text)] == [10, 10]
    assert_commands_fit(box)
    assert_commands_fit(Root(Row()).measure(FONTS, STYLE))
    with pytest.raises(ValueError, match="math"):
        Root(None)


def test_tall_parentheses_are_curved_vectors_without_stretching_text():
    box = Delimited(Fraction("a", "b")).measure(FONTS, STYLE)
    assert (box.width, box.ascent, box.descent) == (19, 15.25, 10.25)
    brackets = [c for c in box.commands if isinstance(c, Polyline)]
    assert len(brackets) == 2
    assert all(len(c.points) >= 25 for c in brackets)
    left, right = brackets
    assert left.points[0].x == pytest.approx(left.points[-1].x)
    assert min(p.x for p in left.points) < left.points[0].x
    assert max(p.x for p in right.points) > right.points[0].x
    assert [c.style.size for c in box.commands if isinstance(c, Text)] == [10, 10]
    assert [c.text for c in box.commands if isinstance(c, Text)] == ["a", "b"]
    assert_commands_fit(box)


@pytest.mark.parametrize(("left", "right"), [("[", "]"), ("|", "|"), ("", ")"), ("(", ""), ("", "")])
def test_explicit_delimiters_and_omitted_sides_fit_their_boxes(left, right):
    node = Delimited(Root(Fraction("α", "β")), left=left, right=right)
    box = node.measure(FONTS, STYLE)
    assert_commands_fit(box)
    assert box == node.measure(FONTS, STYLE)
    assert sum(isinstance(c, Polyline) for c in box.commands) == 1 + bool(left) + bool(right)


@pytest.mark.parametrize(("left", "right"), [("{", "}"), (None, ")"), ("(", []), (")", "(")])
def test_delimited_rejects_unsupported_delimiters(left, right):
    with pytest.raises(ValueError, match="delimiter"):
        Delimited("x", left=left, right=right)


def test_delimited_rejects_invalid_body():
    with pytest.raises(ValueError, match="math"):
        Delimited(None)


@pytest.fixture(scope="module")
def real_fonts():
    fonts = FontRegistry()
    return fonts


@pytest.mark.parametrize(
    ("text", "width", "ascent", "descent", "origin_x"),
    [
        ("j", 3.583984375, 8.798828125, 1.9873046875, 0.5419921875),
        # glyf bbox x=-6..1497 at 2048 units/em: include both overhangs.
        ("Å", 7.3388671875, 9.150390625, 1.201171875, 0.029296875),
    ],
)
def test_literal_reserves_actual_ipa_glyph_overhang(real_fonts, text, width, ascent, descent, origin_x):
    box = Literal(text).measure(real_fonts, STYLE)
    assert box.width == pytest.approx(width)
    assert box.ascent == pytest.approx(ascent)
    assert box.descent == pytest.approx(descent)
    assert box.commands[0].x == pytest.approx(origin_x)
    assert box.commands[0].style.size == 10
    assert_commands_fit(box, real_fonts)


def test_nested_real_font_math_keeps_all_ink_and_strokes_inside_boxes(real_fonts):
    node = Row(
        Symbol("σ"), Operator("="),
        Script(Delimited(Fraction(Root(Row("j", Operator("+"), "Å")), "β")),
               superscript=Fraction("1", "2"), subscript="i"),
        Literal("日本語"),
    )
    before = repr(node)
    box = node.measure(real_fonts, STYLE)
    assert_commands_fit(box, real_fonts)
    assert box == node.measure(real_fonts, STYLE)
    assert repr(node) == before
    assert {c.style.size for c in box.commands if isinstance(c, Text)} == {10, 6.5}
    assert not any(c.text in ("(", ")", "√") for c in box.commands if isinstance(c, Text))


def test_fraction_clearance_uses_actual_descender_and_capital_ink(real_fonts):
    box = Fraction("j", "Å").measure(real_fonts, STYLE)
    numerator, denominator = [c for c in box.commands if isinstance(c, Text)]
    rule, = [c for c in box.commands if isinstance(c, Line)]
    assert rule.y1 - rule.width / 2 - command_bounds(numerator, real_fonts)[3] == pytest.approx(1.5)
    assert command_bounds(denominator, real_fonts)[1] - rule.y1 - rule.width / 2 == pytest.approx(1.5)
    assert_commands_fit(box, real_fonts)


@pytest.mark.parametrize("node", [Literal("x"), Row(), Fraction("x", "y"), Script("x", "2"), Root("x"), Delimited("x")])
@pytest.mark.parametrize("invalid", [None, True, 10, {}])
def test_math_nodes_report_invalid_style_as_value_error(node, invalid):
    with pytest.raises(ValueError, match="style"):
        node.measure(FONTS, invalid)


@pytest.mark.parametrize("node", [Literal("x"), Row(), Fraction("x", "y"), Script("x", "2"), Root("x"), Delimited("x")])
def test_math_nodes_report_missing_font_measurer_even_when_empty(node):
    with pytest.raises(ValueError, match="fonts"):
        node.measure(None, STYLE)


class _RestyledLiteral:
    """A custom MathNode that changes only font and tracking (FR-023 review H1)."""

    def __init__(self, text, **changes):
        self.text, self.changes = text, changes

    def measure(self, fonts, style):
        from dataclasses import replace as restyle
        return Literal(self.text).measure(fonts, restyle(style, **self.changes))


@pytest.mark.parametrize("changes", [{"font": "IPAexゴシック"}, {"tracking": .2}])
def test_custom_nodes_may_restyle_scripts_without_changing_their_size(changes):
    box = Script("M", _RestyledLiteral("max", **changes), Script("x", _RestyledLiteral("n", **changes)),
                 ).measure(FONTS, TextStyle(size=12))
    sizes = sorted(c.style.size for c in box.commands if isinstance(c, Text))
    assert sizes == pytest.approx([12 * .65 * .65, 12 * .65, 12 * .65, 12])
    for command in box.commands:
        if isinstance(command, Text) and command.text in ("max", "n"):
            assert all(getattr(command.style, key) == value for key, value in changes.items())


def test_custom_nodes_cannot_choose_an_off_step_size_inside_a_script():
    with pytest.raises(ValueError, match=r"multiple of 0\.5 pt"):
        Script("M", _RestyledLiteral("max", size=7.7)).measure(FONTS, TextStyle(size=12))
