"""The fixture builds every page from library parts placed on the page grid (FR-027).

Original typography (faces, synthetic italic, vertical parentheses, mixed-font
headings) is kept; positions come from the original's layout snapped to whole
grid columns, never replayed as coordinates.
"""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from gridlayoutpdf import (
    Columns, EquationGroup, LayoutContext, Literal, Paragraph, Row, SideRule, Stack, Text, TextStyle,
    command_bounds, measure_block,
)
from gridlayoutpdf.semantics import Kind, Role

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests/fixtures/cantilever_p01_37"


def module(name):
    key = f"cantilever_fixture_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, FIXTURE / f"{name}.py")
        result = importlib.util.module_from_spec(spec)
        sys.modules[key] = result
        spec.loader.exec_module(result)
    return sys.modules[key]


@pytest.fixture(scope="module")
def fonts():
    return module("builder").fixture_fonts()


def _page(fonts, number):
    builder = module("builder")
    data = json.loads((FIXTURE / f"pages/p{number:02}.json").read_text(encoding="utf-8"))
    layout = {page["source_page"]: page for page in builder.source_layout()["pages"]}[number]
    leaves = tuple(builder._leaves({"type": "stack", "children": data["blocks"]}))
    page = builder._Page(number, fonts, {block["id"]: block for block in layout["blocks"]}, leaves)
    return page, data, {block["id"]: block for block in leaves}


def _groups(built):
    """The EquationGroups an authored equations block becomes (one, or runs in a Stack)."""
    return [built] if isinstance(built, EquationGroup) else [child for child in built.children]


def _equations_of(built):
    return [item for group in _groups(built) for item in group.equations]


def _find(block, kind, identifier=None):
    """The first block of a type (and ID) inside a built block tree."""
    if isinstance(block, kind) and (identifier is None or block.block_id == identifier):
        return block
    for child in (*getattr(block, "children", ()), *((block.block,) if hasattr(block, "block") else ())):
        found = _find(child, kind, identifier)
        if found is not None:
            return found
    return None


def test_default_fixture_resolves_the_two_original_fixed_width_faces_by_name(fonts):
    assert fonts.resolve("MS Mincho").path.name.lower() == "msmincho.ttc"
    assert fonts.resolve("MS Gothic").path.name.lower() == "msgothic.ttc"
    assert fonts.resolve("MS Mincho").face_index == fonts.resolve("MS Gothic").face_index == 0
    assert fonts.measure("Wi", TextStyle("MS Mincho")).width == 10


def test_changed_original_font_hash_is_rejected(monkeypatch):
    builder = module("builder")
    profile = builder.font_profile()
    profile["fonts"]["MS Gothic"]["sha256"] = "0" * 64
    monkeypatch.setattr(builder, "font_profile", lambda: profile)
    with pytest.raises(ValueError, match="Original font hash changed: MS Gothic"):
        builder.fixture_fonts()


def test_authored_scripts_are_library_scripts_at_the_original_offsets(fonts):
    builder = module("builder")
    box = builder.math_node({"type": "script", "base": "S", "sub": "10"}).measure(fonts, TextStyle("MS Mincho", 10))
    base, script = [command for command in box.commands if isinstance(command, Text)]
    assert (base.style.size, script.style.size) == (10, 6.5)
    assert script.y - base.y == pytest.approx(1.92)
    assert script.tag.scope(Kind.SCRIPT).part == "subscript"
    upper = builder.math_node({"type": "script", "base": "m", "sup": "2"}).measure(fonts, TextStyle("MS Mincho", 10))
    base, script = [command for command in upper.commands if isinstance(command, Text)]
    assert base.y - script.y == pytest.approx(2.4)


def test_synthetic_italic_leans_only_the_authored_base_and_clears_its_script(fonts):
    builder = module("builder")
    atoms = ({"text": "D", "shear_x": .342, "script_gap": 1.68},)
    value = {"type": "script", "base": "D", "sub": "1"}
    plain = builder.math_node(value).measure(fonts, TextStyle("MS Mincho", 10))
    leaning = builder._shear(builder.math_node(value), value, atoms).measure(fonts, TextStyle("MS Mincho", 10))
    texts = [command for command in leaning.commands if isinstance(command, Text)]
    assert (texts[0].text, texts[0].shear_x) == ("D", .342)
    assert (texts[1].text, texts[1].shear_x) == ("1", 0)
    # The original's 1.68 pt script gap: the library leaves 1.0 pt, the base widens by the rest.
    plain_script = [command for command in plain.commands if isinstance(command, Text)][1]
    assert texts[1].x - plain_script.x == pytest.approx(.68)
    assert texts[0].tag == [command for command in plain.commands if isinstance(command, Text)][0].tag


def test_vertical_parenthesis_turns_clockwise_and_centres_its_ink_on_one_character(fonts):
    builder = module("builder")
    style = TextStyle("MS Mincho", 10)
    assert set(builder.font_profile()["vertical_glyphs"]) == {"（", "）"}
    glyph = builder._cell_line("（", {}, turned=True)
    box = glyph.measure(fonts, style)
    command, = box.commands
    assert command.quarter_turns == 3 and command.style == style and command.text == "（"
    assert command.tag.role == Role.MATH
    ink = command_bounds(command, fonts)
    metrics = fonts.measure("（", style)
    assert box.width == 10
    assert (ink.x + ink.right) / 2 == pytest.approx(5)
    assert (ink.y + ink.bottom) / 2 == pytest.approx((metrics.descent - metrics.ascent) / 2)
    assert not isinstance(builder._cell_line("破", {}), type(glyph))


def test_original_indentation_levels_become_distinct_grid_columns():
    builder = module("builder")
    # The original's heading levels: 53.52 + 14.52 k pt.
    levels = [53.52, 68.04, 78.36, 97.92, 111.6, 126.12, 140.64, 155.16, 169.68, 184.2]
    assert [builder.indent_columns(x, 1) for x in levels] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    # Rotated pages use the nearest column of their own 10.8 pt grid.
    assert builder.indent_columns(66.12, 30) == 1
    assert builder.anchor_column(175.54, 1) == 8
    assert builder._nearest(4.5) == 5 and builder._nearest(-0.5) == 0


def test_equation_anchors_come_from_the_original_and_shared_siblings(fonts):
    builder = module("builder")
    page, data, leaves = _page(fonts, 1)
    group = _groups(builder._equations(leaves["p01-reactions"], page, 0,
                                       page.grid.columns - page.column(leaves["p01-reactions"], 0)))[0]
    left = builder.equation_left(page.geometry["p01-reactions"])
    record = page.geometry["p01-reactions"]["equations"][0]
    anchors = group.anchors
    # Never left of the original's nearest column (from the group's original left edge).
    assert anchors.first_equal >= builder._nearest((record["first_equal"] - left) / page.grid.pitch_x)
    assert anchors.second_equal >= builder._nearest((record["second_equal"] - left) / page.grid.pitch_x)
    assert anchors.unit_start > anchors.result_right > anchors.second_equal > anchors.first_equal
    # p3: the per-girder groups share their anchors.
    page, data, leaves = _page(fonts, 3)
    groups = [group for index in range(1, 5) for group in _groups(builder._equations(
        leaves[f"p03-equation-00{index}"], page, 0, page.grid.columns - page.column(leaves[f"p03-equation-00{index}"], 0)))]
    assert len({group.anchors for group in groups}) == 1


def test_wrapped_and_separate_results_keep_the_original_reading_order(fonts):
    builder = module("builder")
    page, data, leaves = _page(fonts, 1)
    equations = _equations_of(builder._equations(leaves["p01-reactions"], page, 0,
                                                  page.grid.columns - page.column(leaves["p01-reactions"], 0)))
    names = [equation.block_id for equation in equations]
    assert names == ["p01-reactions-0", "p01-reactions-1", "p01-reactions-1-line2", "p01-reactions-2", "p01-reactions-3"]
    continued = equations[2]
    assert continued.lhs == Literal("") and continued.relation == " " and continued.result is None
    assert equations[1].result is not None
    page, data, leaves = _page(fonts, 11)
    equations = _equations_of(builder._equations(leaves["p11-origin-forces"], page, 0,
                                                  page.grid.columns - page.column(leaves["p11-origin-forces"], 0)))
    first, result = equations[0], equations[1]
    assert first.result is None and result.block_id == "p11-origin-forces-0-result"
    assert result.result is not None and result.rhs == Literal("")


def test_original_line_breaks_must_fall_between_math_items():
    builder = module("builder")
    rhs = {"type": "row", "items": ["1", {"type": "operator", "text": "+"}, "23", "45"]}
    lines = builder._source_lines(rhs, {"rhs_lines": [{"text": "1+"}, {"text": "2345"}]}, "probe")
    assert len(lines) == 2 and len(lines[0].items) == 2 and len(lines[1].items) == 2
    with pytest.raises(ValueError, match="cuts a math item"):
        builder._source_lines(rhs, {"rhs_lines": [{"text": "1+2"}, {"text": "345"}]}, "probe")
    assert builder._source_lines(rhs, {}, "probe") == [builder.math_node(rhs)]


def test_mixed_font_headings_split_into_runs_on_column_lines(fonts):
    builder = module("builder")
    page, data, leaves = _page(fonts, 21)
    heading = builder._leaf(leaves["p21-origin-title"], page, 0, 31)
    assert isinstance(heading, Columns)
    first, second = heading.children
    assert (first.text, first.style.font) == ("a) 起点桁", "MS Gothic")
    assert (second.text, second.style.font) == ("4 箇所", "MS Mincho")
    block = page.column(leaves["p21-origin-title"], 0)
    assert heading.col_spans[0] == builder.anchor_column(204.6, 21) - block
    page, data, leaves = _page(fonts, 28)
    title = builder._leaf(leaves["p28-horizontal9-title"], page, 0, 31)
    assert [child.style.font for child in title.children] == ["MS Gothic", "MS Mincho"]
    with pytest.raises(ValueError, match="cuts a math item"):
        builder._run_pieces({"id": "x", "type": "math", "content": {"type": "row", "items": ["ab", "cd"]}},
                            [{"start": 0, "stop": 3, "font": "MS Gothic"}, {"start": 3, "stop": 4, "font": "MS Mincho"}])


def test_source_bracket_bar_is_a_side_rule_left_of_its_derivation(fonts):
    builder = module("builder")
    page, data, leaves = _page(fonts, 16)
    columns = next(block for block in data["blocks"] if block["id"] == "p16-movable-with-rule")
    built = builder.build_block(columns, page)
    rule = _find(built, SideRule)
    assert rule.block_id == "p16-movable-derivation" and rule.style == "thin"
    content = min(page.column(leaf, 0) for leaf in builder._leaves(columns["children"][1]))
    bar = builder.indent_columns(page.geometry["p16-movable-rule"]["x"], 16)
    assert bar < content
    assert rule.x == pytest.approx(bar * page.grid.pitch_x)


def test_blocks_are_indented_by_whole_columns_and_never_outside_the_body(fonts):
    from gridlayoutpdf import Indent, LayoutOverflowError
    builder = module("builder")
    page, data, leaves = _page(fonts, 1)
    section = builder.build_block(leaves["p01-section"], page)
    assert isinstance(section, Indent) and section.left == page.grid.pitch_x
    assert isinstance(section.block, Paragraph)
    with pytest.raises(LayoutOverflowError, match="left of its container"):
        page.place(leaves["p01-section"], section.block, 5, 26)
    with pytest.raises(LayoutOverflowError, match="outside the body"):
        page.place(leaves["p01-section"], section.block, 0, 1)
    context = LayoutContext(fonts, builder.SOURCE_PROFILE, builder.SOURCE_STYLE)
    measured = measure_block(section, context, builder.SOURCE_PROFILE.body_rect.width)
    text = next(command for command in measured.commands if isinstance(command, Text))
    assert text.x == pytest.approx(page.grid.pitch_x)
    assert isinstance(_find(builder.build_block(leaves["p01-reactions"], page), EquationGroup), EquationGroup)


def _all_equation_groups(fonts):
    builder = module("builder")
    for number in builder.SOURCE_PAGES:
        page, data, leaves = _page(fonts, number)
        for leaf in leaves.values():
            if leaf["type"] == "equations":
                built = builder._equations(leaf, page, 0, page.grid.columns - page.column(leaf, 0))
                yield number, page, leaf, _groups(built)[0]


def test_every_equation_anchor_is_at_or_right_of_its_own_original_column(fonts):
    """Anchors are the page columns nearest the original's (most common per group); never further left."""
    builder = module("builder")
    checked = 0
    for number, page, leaf, group in _all_equation_groups(fonts):
        geometry = page.geometry[leaf["id"]]
        column = page.column(leaf, 0)
        source = builder._source_anchors(geometry, number)
        for name in ("first_equal", "second_equal", "result_right", "unit_start"):
            built = getattr(group.anchors, name)
            if name in source and built is not None:
                assert column + built >= source[name], (leaf["id"], name, column + built, source[name])
                checked += 1
    assert checked > 200


def _source_and_output_anchors(fonts):
    """Per page 1-29: each equation group's original anchors (pt) and built anchors (page columns)."""
    builder = module("builder")
    for number in range(1, 30):
        page, data, leaves = _page(fonts, number)
        groups = [leaf for leaf in leaves.values() if leaf["type"] == "equations"]
        yield number, page, groups, {leaf["id"]: builder._source_positions(page.geometry[leaf["id"]])
                                     for leaf in groups}, {leaf["id"]: builder._equation_anchors(leaf, page)[0]
                                                           for leaf in groups}


# The one alignment the original has that the grid cannot keep: on p13 the reactions need
# column 25 for their second equals (their right-hand sides), and the forces' units would
# not fit the body if their second equals moved there too.
UNSHARED_ORIGINAL_ANCHORS = {(13, "p13-origin-forces", "p13-origin-reactions", "second_equal"),
                             (13, "p13-origin-reactions", "p13-end-forces", "second_equal")}


def test_anchors_the_original_aligned_stay_aligned_across_groups(fonts):
    """M2: equals, result ends and unit starts the original set within 6 pt of each other share a
    column (p16-p19: T1, T2 and the stopper lines at different levels; p13, p14: forces and
    reactions; p3-p8: right-aligned results up to 5.04 pt apart)."""
    builder = module("builder")
    unshared, checked = set(), 0
    for number, page, groups, source, output in _source_and_output_anchors(fonts):
        for index, first in enumerate(groups):
            for second in groups[index + 1:]:
                for name in ("first_equal", "second_equal", "result_right", "unit_start"):
                    a, b = first["id"], second["id"]
                    if name in source[a] and name in source[b] \
                            and abs(source[a][name] - source[b][name]) <= builder.ALIGNED_SOURCE_PT \
                            and name in output[a] and name in output[b]:
                        checked += 1
                        if output[a][name] != output[b][name]:
                            unshared.add((number, a, b, name))
    assert checked > 3000
    assert unshared == UNSHARED_ORIGINAL_ANCHORS
    # The exception is forced: the forces at the reactions' column lose the original's lines.
    page, data, leaves = _page(fonts, 13)
    forces = leaves["p13-origin-forces"]
    base, _, cells = builder._family_anchors(builder._anchor_family(forces, page), page)
    member = builder._member(forces, page)
    values, _ = builder._anchors({**base, "second_equal": 25}, [member], page, cells=cells)
    assert not builder._members_keep_lines([member], values, page)


def test_groups_with_the_same_original_left_take_the_same_column(fonts):
    """M1: p14's origin and end reactions start at the same original x, so in the same column."""
    builder = module("builder")
    checked = 0
    for number in range(1, 30):
        page, data, leaves = _page(fonts, number)
        groups = [leaf for leaf in leaves.values() if leaf["type"] == "equations"]
        lefts = {}
        for leaf in groups:
            lefts.setdefault(round(builder.equation_left(page.geometry[leaf["id"]]), 2), set()).add(page.column(leaf, 0))
        for columns in lefts.values():
            checked += 1
            assert len(columns) == 1, (number, columns)
    assert checked > 40
    page, data, leaves = _page(fonts, 14)
    assert page.column(leaves["p14-origin-reactions"], 0) == page.column(leaves["p14-end-reactions"], 0)


def test_figures_take_their_nearest_column_and_text_keeps_the_levels(fonts):
    """Text blocks keep the original's level order; a figure has no level and takes its nearest column."""
    builder = module("builder")
    for number, identifier in ((23, "p23-figure-front"), (24, "p24-figure-front"), (1, "p01-load-figure")):
        page, data, leaves = _page(fonts, number)
        x = page.geometry[identifier]["x"]
        assert page.column(leaves[identifier], 0) == builder.anchor_column(x, number)
    assert builder.anchor_column(310, 24) == 16
    page, data, leaves = _page(fonts, 3)
    assert page.column(leaves["p03-b-single-title"], 0) < page.column(leaves["p03-equation-001"], 0)


def test_merged_cells_widen_the_columns_they_span():
    builder = module("builder")
    # Tables sharing columns add their merged cells in one sorted order, so the result is the same.
    spans = [(0, 2, 30), (1, 2, 30)]
    assert builder._widen_for_spans((1, 1, 1), sorted(spans), 16) == builder._widen_for_spans(
        (1, 1, 1), sorted(reversed(spans)), 16)
    assert builder._widen_for_spans((1, 1, 1), [(0, 2, 40)], 16) == (1, 2, 1)
    assert builder._widen_for_spans((2, 1), [(0, 2, 40)], 16) == (2, 1)
    assert builder._widen_for_spans((1, 1), [], 16) == (1, 1)


def test_a_font_run_with_a_fixed_start_must_fit_its_columns(fonts):
    from gridlayoutpdf import LayoutOverflowError
    builder = module("builder")
    page, data, leaves = _page(fonts, 21)
    heading = dict(leaves["p21-origin-title"])
    runs = [{"start": 0, "stop": 5, "font": "MS Gothic"}, {"start": 5, "stop": 8, "font": "MS Mincho", "x": 130}]
    with pytest.raises(LayoutOverflowError, match="font runs do not fit"):
        builder._font_runs(heading, runs, page, 0, 31)


def test_a_plain_string_math_heading_splits_into_runs():
    builder = module("builder")
    pieces = builder._run_pieces({"id": "x", "type": "math", "content": "ab"},
                                 [{"start": 0, "stop": 2, "font": "MS Gothic"}])
    assert pieces == [{"type": "row", "items": ["ab"], "gap": 0}]


@pytest.mark.parametrize("key", ["body_size", "rotated_body_size", "spacing_ratio", "script_size_ratio",
                                 "subscript_offset", "superscript_offset"])
def test_obsolete_font_profile_keys_are_rejected(key):
    """The page grid and the library Script replace the profile's former sizes and offsets."""
    builder = module("builder")
    profile = builder.font_profile()
    builder._reject_obsolete_profile_keys(profile)
    with pytest.raises(ValueError, match=f"obsolete font-profile key.*{key}"):
        builder._reject_obsolete_profile_keys({**profile, key: 1})


@pytest.mark.parametrize("key,where", [("local_grid", "table"), ("anchors", "equations"), ("border_width", "table")])
def test_obsolete_layout_keys_are_rejected(fonts, tmp_path, key, where):
    builder = module("builder")
    number = 30 if where == "table" else 1
    data = json.loads((FIXTURE / f"pages/p{number:02}.json").read_text(encoding="utf-8"))
    block = next(block for block in builder._leaves({"type": "stack", "children": data["blocks"]}) if block["type"] == where)
    block[key] = {"pitch_x": .01} if key == "local_grid" else ({"first_equal": 3} if key == "anchors" else .4)
    (tmp_path / f"p{number:02}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="obsolete layout key"):
        builder.layout_report(fonts, source_pages=(number,), pages_root=tmp_path)


def test_fixture_inputs_are_read_once_and_handed_out_as_copies(fonts):
    builder = module("builder")
    builder._fixture_json.cache_clear()
    builder.layout_report(fonts, source_pages=(16,))
    assert builder._fixture_json.cache_info().misses <= 3
    profile = builder.font_profile()
    profile["items"].clear()
    assert builder.font_profile()["items"]


def test_only_the_original_vertical_glyph_lines_turn():
    builder = module("builder")
    assert isinstance(builder._cell_line("（", {}, turned=True), module("appearance").VerticalGlyph)
    assert isinstance(builder._cell_line("（", {}, turned=False), Literal)


def test_right_hand_sides_split_into_terms_with_scripts_kept_on_their_base():
    from gridlayoutpdf import Operator, TermStop
    builder = module("builder")
    rhs = builder.math_node({"type": "row", "items": ["1.1", {"type": "script", "base": "D", "sub": "1"},
                                                     "+", "1.2", {"type": "operator", "text": "×"}, "#######"]})
    segments = builder._term_segments(rhs)
    assert [len(segment) for segment in segments] == [2, 1, 1, 1, 1]
    assert [builder._term_align(segment) for segment in segments] == ["left", "center", "right", "center", "right"]
    assert builder._term_segments(builder.math_node("517.77")) == [[Literal("517.77")]]
    # Rows already in terms split at their TermStops.
    assert builder._term_segments(Row(TermStop("left"), "a", "b", TermStop("right"), "c")) == [
        [Literal("a"), Literal("b")], [Literal("c")]]


def test_term_alignment_is_shared_per_column_and_whole_mode_keeps_one_term(fonts):
    from gridlayoutpdf import Equation, TermStop
    builder = module("builder")
    first = Equation("a", builder.math_node({"type": "row", "items": ["1.0", "×", "2.0"]}))
    second = Equation("b", builder.math_node({"type": "row", "items": ["(", "×", "3.0"]}))
    split = builder._grid_terms([first, second])
    stops = [[item.align for item in equation.rhs.items if isinstance(item, TermStop)] for equation in split]
    # Column 0 disagrees (right vs left), so it aligns left in both; the others agree.
    assert stops == [["left", "center", "right"], ["left", "center", "right"]]
    whole = builder._grid_terms([first], whole=True)[0].rhs
    assert len(whole.items) == 2 and isinstance(whole.items[0], TermStop) and isinstance(whole.items[1], Row)
    single = Equation("c", builder.math_node("517.77"))
    assert builder._grid_terms([single]) == [single]


def test_equations_of_another_shape_get_their_own_term_columns():
    from gridlayoutpdf import Equation
    builder = module("builder")
    long = Equation("a", builder.math_node({"type": "row", "items": ["32.00", "×", "(18.850)", "/", "18.850"]}))
    one = Equation("b", builder.math_node("103.55"))
    three = Equation("c", builder.math_node({"type": "row", "items": ["103.55", "x", "3.850"]}))
    runs = builder._term_runs([long, one, three, three])
    assert [len(run) for run in runs] == [1, 1, 2]


def test_p09_groups_split_into_runs_with_the_same_anchors(fonts):
    from gridlayoutpdf import EquationGroup, Stack
    builder = module("builder")
    page, data, leaves = _page(fonts, 9)
    built = builder._equations(leaves["p09-forces"], page, 0, page.grid.columns - page.column(leaves["p09-forces"], 0))
    assert isinstance(built, Stack) and built.block_id == "p09-forces"
    groups = [child for child in built.children if isinstance(child, EquationGroup)]
    assert len(groups) == len(built.children) > 1
    # Every anchor a run uses is the one the other runs use (a run without results keeps only first_equal).
    for name in ("first_equal", "second_equal", "result_right", "unit_start"):
        assert len({getattr(group.anchors, name) for group in groups} - {None}) == 1, name
    assert all(group.term_columns == "grid" for group in groups)
