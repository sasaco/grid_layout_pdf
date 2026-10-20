"""The semantic tag contract on drawing commands (Step 5).

A tag says what a command means (its role), where it sits in the structure
that produced it (its path of scopes, outermost first) and any data of its
own. Tags never take part in equality, hashing or drawing.
"""

from dataclasses import FrozenInstanceError, replace
import importlib
import json
import pickle

import pytest

from gridlayoutpdf.diagnostics import layout_trace
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.geometry import GridSpec
from gridlayoutpdf.layout import LayoutContext
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.scene import Circle, Line, Polyline, RasterImage, Rectangle, ScenePage, Text
from gridlayoutpdf.styles import ReportStyle, TextStyle


def semantics():
    return importlib.import_module("gridlayoutpdf.semantics")


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * 0.6, style.size * 0.8, style.size * 0.2)


STYLE = TextStyle(size=10)
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
       b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef"
       b"\x00\x00\x00\x00IEND\xaeB`\x82")


def commands(tag=None):
    keyword = {} if tag is None else {"tag": tag}
    return (
        Text(1, 2, "a", STYLE, **keyword),
        Line(0, 0, 5, 0, **keyword),
        Polyline(((0, 0), (1, 1)), **keyword),
        Rectangle(0, 0, 2, 2, **keyword),
        Circle(1, 1, 1, **keyword),
        RasterImage(0, 0, 1, 1, PNG, **keyword),
    )


def sample_tag():
    s = semantics()
    return s.Tag(s.Role.MATH, (s.Scope(s.Kind.EQUATION, index=3),
                               s.Scope(s.Kind.EQUATION_LINE, index=0, data={"continuation": False}),
                               s.Scope(s.Kind.FRACTION, part="numerator")),
                 {"atom": "symbol"})


def test_every_drawing_command_accepts_an_optional_keyword_tag_defaulting_to_none():
    tag = sample_tag()
    for untagged, tagged in zip(commands(), commands(tag)):
        assert untagged.tag is None
        assert tagged.tag is tag


@pytest.mark.parametrize("bad", ["math", 1, {"role": "math"}])
def test_a_command_rejects_a_tag_that_is_not_a_tag(bad):
    with pytest.raises(ValueError, match="tag"):
        Line(0, 0, 1, 0, tag=bad)


def test_tags_never_take_part_in_command_equality_or_hashing():
    tag = sample_tag()
    for untagged, tagged in zip(commands(), commands(tag)):
        assert untagged == tagged
        assert hash(untagged) == hash(tagged)
    assert ScenePage(A4_PORTRAIT_REFERENCE, commands()) == ScenePage(A4_PORTRAIT_REFERENCE, commands(tag))


def test_text_and_image_keep_their_positional_fields_and_take_the_tag_by_keyword():
    text = Text(1, 2, "a", STYLE, 1, 0.5, tag=sample_tag())
    assert (text.quarter_turns, text.shear_x) == (1, 0.5)
    with pytest.raises(TypeError):
        Text(1, 2, "a", STYLE, 0, 0.0, sample_tag())
    with pytest.raises(TypeError):
        RasterImage(0, 0, 1, 1, PNG, sample_tag())


def test_translation_replace_and_pickling_keep_the_tag():
    tag = sample_tag()
    for command in commands(tag):
        assert command.translated(3, 4).tag == tag
        assert pickle.loads(pickle.dumps(command)).tag == tag
    assert replace(commands(tag)[0], x=9).tag == tag


def test_tag_and_scope_are_frozen_hashable_values():
    s = semantics()
    tag = sample_tag()
    assert tag == sample_tag() and hash(tag) == hash(sample_tag())
    assert {tag: 1}[sample_tag()] == 1
    with pytest.raises(FrozenInstanceError):
        tag.role = s.Role.TEXT
    with pytest.raises(FrozenInstanceError):
        tag.path[0].index = 1
    assert tag != s.Tag(s.Role.MATH, tag.path, {"atom": "operator"})
    assert pickle.loads(pickle.dumps(tag)) == tag


def test_tag_data_is_a_deeply_frozen_json_compatible_mapping():
    s = semantics()
    tag = s.Tag(s.Role.TABLE_BORDER, (), {"range": [0, 2], "style": s.Role.TEXT,
                                          "nested": {"a": [1, {"b": None}]}, "flag": True, "pt": 0.5})
    assert tag.data["range"] == (0, 2)
    assert type(tag.data["style"]) is str and tag.data["style"] == "text"
    assert tag.data["nested"]["a"][1]["b"] is None
    with pytest.raises(TypeError):
        tag.data["range"] = (1,)
    with pytest.raises(TypeError):
        tag.data["nested"]["a"] = ()
    hash(tag)
    assert json.loads(json.dumps(tag.to_json())) == tag.to_json()


@pytest.mark.parametrize("data", [
    {"a": {1, 2}}, {"a": object()}, {"a": float("nan")}, {"a": float("inf")}, {1: "key"}, {"a": b"x"},
])
def test_tag_data_rejects_values_that_are_not_json_compatible(data):
    s = semantics()
    with pytest.raises(ValueError):
        s.Tag(s.Role.TEXT, (), data)
    with pytest.raises(ValueError):
        s.Scope(s.Kind.PARAGRAPH, data=data)


def test_roles_and_scope_kinds_are_closed_string_constants():
    s = semantics()
    assert s.Tag("text").role is s.Role.TEXT
    assert s.Scope("table_cell").kind is s.Kind.TABLE_CELL
    with pytest.raises(ValueError, match="role"):
        s.Tag("border")
    with pytest.raises(ValueError, match="kind"):
        s.Scope("cell")
    assert {role.value for role in s.Role} == {
        "text", "math", "fraction_bar", "radical", "delimiter", "table_border", "rule", "side_rule",
        "figure", "image", "other"}
    assert s.BORDER_ROLES == {s.Role.TABLE_BORDER, s.Role.RULE, s.Role.SIDE_RULE}


@pytest.mark.parametrize("keyword", [{"index": -1}, {"index": True}, {"index": 1.0}, {"part": ""}, {"part": 3}])
def test_scope_rejects_a_malformed_index_or_part(keyword):
    s = semantics()
    with pytest.raises(ValueError):
        s.Scope(s.Kind.ROW, **keyword)


def test_tag_path_must_hold_scopes():
    s = semantics()
    with pytest.raises(ValueError, match="path"):
        s.Tag(s.Role.TEXT, ("paragraph",))
    assert s.Tag(s.Role.TEXT, [s.Scope(s.Kind.PARAGRAPH)]).path == (s.Scope(s.Kind.PARAGRAPH),)


def test_within_prepends_outer_scopes_and_lookup_finds_the_innermost_structure():
    s = semantics()
    inner = s.Tag(s.Role.FRACTION_BAR, (s.Scope(s.Kind.FRACTION, part="numerator"),
                                        s.Scope(s.Kind.FRACTION, part="bar")))
    outer = inner.within(s.Scope(s.Kind.EQUATION, index=1), s.Scope(s.Kind.EQUATION_LINE, index=0))
    assert [scope.kind for scope in outer.path] == ["equation", "equation_line", "fraction", "fraction"]
    assert outer.role is s.Role.FRACTION_BAR
    assert outer.find(s.Kind.FRACTION) == 3
    assert outer.scope(s.Kind.FRACTION).part == "bar"
    assert outer.scope(s.Kind.TABLE) is None and outer.find(s.Kind.TABLE) is None
    # key(): the path that identifies the innermost structure of a kind, without the part.
    numerator = s.Tag(s.Role.MATH, (s.Scope(s.Kind.FRACTION, part="numerator"),
                                    s.Scope(s.Kind.FRACTION, part="numerator")))
    assert numerator.key(s.Kind.FRACTION) == inner.key(s.Kind.FRACTION) == (
        s.Scope(s.Kind.FRACTION, part="numerator"), s.Scope(s.Kind.FRACTION))
    assert inner.key(s.Kind.TABLE) is None


def test_scoping_helpers_retag_commands_and_mark_untagged_ones_as_other():
    s = semantics()
    scope = s.Scope(s.Kind.TABLE_CELL, data={"row": 0})
    tagged = Text(0, 0, "a", STYLE, tag=s.Tag(s.Role.TEXT))
    result = s.within((tagged, Line(0, 0, 1, 0)), scope)
    assert result[0].tag == s.Tag(s.Role.TEXT, (scope,))
    assert result[1].tag == s.Tag(s.Role.OTHER, (scope,))
    assert result == (tagged, Line(0, 0, 1, 0))
    assert s.tagged((Line(0, 0, 1, 0, tag=s.Tag(s.Role.TABLE_BORDER)),), s.Tag(s.Role.FIGURE))[0].tag == s.Tag(s.Role.FIGURE)


def test_tag_json_lists_only_what_is_set():
    s = semantics()
    tag = s.Tag(s.Role.MATH, (s.Scope(s.Kind.EQUATION, index=0),
                              s.Scope(s.Kind.EQUATION_PART, part="term", index=2, data={"align": "right"}),
                              s.Scope(s.Kind.FRACTION, part="numerator")))
    assert tag.to_json() == {
        "role": "math",
        "path": [{"kind": "equation", "index": 0},
                 {"kind": "equation_part", "part": "term", "index": 2, "data": {"align": "right"}},
                 {"kind": "fraction", "part": "numerator"}],
    }
    assert s.Tag(s.Role.RULE, (), {"style": "thin"}).to_json() == {"role": "rule", "path": [], "data": {"style": "thin"}}


def test_layout_trace_lists_a_tag_only_when_a_command_has_one():
    tag = sample_tag()
    page = ScenePage(A4_PORTRAIT_REFERENCE, (Line(0, 0, 5, 0), Line(0, 0, 5, 0, tag=tag)))
    trace = layout_trace((page,), FixedFonts())
    untagged, tagged = trace["pages"][0]["commands"]
    assert "tag" not in untagged
    assert tagged.pop("tag") == tag.to_json()
    assert tagged == untagged | {"index": 1}


def test_quarter_turn_rotation_keeps_the_childs_tags():
    from gridlayoutpdf.blocks import Paragraph
    from gridlayoutpdf.rotation import QuarterTurn
    s = semantics()
    context = LayoutContext(FixedFonts(), A4_PORTRAIT_REFERENCE, ReportStyle())
    measured = QuarterTurn(Paragraph("ab"), turns=1, local_grid=GridSpec(0, 0, 10, 10, 4, 3)).measure(context, 200)
    text, = measured.commands
    assert text.quarter_turns == 1
    assert text.tag.role is s.Role.TEXT
    assert [scope.kind for scope in text.tag.path] == ["quarter_turn", "paragraph"]
