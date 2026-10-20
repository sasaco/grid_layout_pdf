"""Original-vs-output appearance checks and the FR-027 grid rules, independent of authored placement.

The original is compared for content, reading order, page and font. Positions,
rule widths, equals and the rotated tables are checked against the new rules
(``verify_appearance.GRID_CATEGORIES``), never against the original's
coordinates or against a self-generated golden.
"""

import importlib.util
import json
from pathlib import Path
import sys
from dataclasses import replace

import pytest

from gridlayoutpdf import Line, Rectangle, ScenePage, Text, command_bounds, layout_trace, render_pdf
from gridlayoutpdf.semantics import Kind


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/cantilever_p01_37"


def module(name):
    key = "cantilever_source_appearance_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, FIXTURE / f"{name}.py")
        result = importlib.util.module_from_spec(spec)
        sys.modules[key] = result
        spec.loader.exec_module(result)
    return sys.modules[key]


# Prose, train equations, superscripts, bracketed derivations, the vertical heading,
# dense tables and both rotated table layouts.
REPRODUCTION_PAGES = (1, 3, 9, 16, 21, 26, 30, 36)


def _reproduce(path, source_pages):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=source_pages)
    render_pdf(pages, path, fonts)
    return path, layout_trace(pages, fonts)


@pytest.fixture(scope="module")
def reproduction(tmp_path_factory):
    return _reproduce(tmp_path_factory.mktemp("source-appearance") / "normal.pdf", REPRODUCTION_PAGES)


def _source():
    return next((FIXTURE.parents[1] / "output").glob("13_*.pdf"))


def _oracle_trace(numbers):
    records = [json.loads((FIXTURE / f"expected/p{n:02}.json").read_text(encoding="utf-8")) for n in numbers]
    return {"oracle_regions": [{item["id"]: item["source_bbox"] for block in record["blocks"]
                                for item in block.get("cells", [block])} for record in records]}


def _mutated(number, change, tmp_path, name):
    """Lay out one page, apply ``change`` to its command list, render it; return path and trace."""
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(number,))
    commands = change(list(pages[0].commands), pages, fonts)
    path = tmp_path / f"{name}.pdf"
    render_pdf([ScenePage(pages[0].profile, tuple(commands), pages[0].metadata)], path, fonts)
    return path, layout_trace(pages, fonts)


@pytest.mark.parametrize("category", module("verify_appearance").CATEGORIES)
def test_reproduction_matches_original_and_grid_rules(reproduction, category):
    path, trace = reproduction
    report = module("verify_appearance").appearance_report(
        path, source_pages=REPRODUCTION_PAGES, trace=trace, categories=(category,))
    assert not report["errors"], json.dumps(report["errors"][:8], ensure_ascii=False)
    assert report["checks"][category] > 0


def test_categories_are_the_kept_source_comparison_and_the_new_rules():
    verifier = module("verify_appearance")
    assert verifier.SOURCE_CATEGORIES == ("font",)
    assert verifier.GRID_CATEGORIES == ("position", "equals", "table", "rotation", "placement")
    with pytest.raises(ValueError, match="unknown appearance category"):
        verifier.appearance_report(_source(), source_pages=(1,), trace=_oracle_trace((1,)), categories=("baseline",))
    # The grid rules are read from a native layout trace; the original has none.
    with pytest.raises(ValueError, match="native layout trace"):
        verifier.appearance_report(_source(), source_pages=(1,), trace=_oracle_trace((1,)), categories=("position",))


@pytest.mark.parametrize("number", range(1, 38))
def test_original_content_and_fonts_are_positive_controls(number):
    verifier = module("verify_appearance")
    report = verifier.appearance_report(_source(), source_pages=(number,), trace=_oracle_trace((number,)))
    assert not report["errors"], report
    assert report["checks"]["font"] > 0


def test_output_p09_superscripts_stay_raised_above_their_line(tmp_path):
    import pymupdf

    builder, verifier = module("builder"), module("verify_appearance")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(9,))
    path = tmp_path / "p09-superscripts.pdf"
    render_pdf(pages, path, fonts)
    item = next(block for block in json.loads((FIXTURE / "expected/p09.json").read_text(encoding="utf-8"))["blocks"]
                if block["id"] == "p09-sum-x2")
    regions, _ = verifier._content._trace_regions(layout_trace(pages, fonts)["pages"][0])
    with pymupdf.open(_source()) as original, pymupdf.open(path) as actual_pdf:
        wanted = [char for char in verifier._content._inside(verifier._characters(original[8], trusted_source=True), item["source_bbox"])
                  if char["size"] < 8]
        chars = verifier._content._inside(verifier._characters(actual_pdf[0]), regions[item["id"]])
    actual = [char for char in chars if char["size"] < 8]
    baseline = next(char["origin"][1] for char in chars if char["size"] >= 8)
    assert [char["c"] for char in actual] == [char["c"] for char in wanted] == ["2"] * 4
    # The library Script raises them by the original's 2.4 pt (FR-027: no longer the original's position).
    assert [baseline - char["origin"][1] for char in actual] == pytest.approx([2.4] * 4, abs=.01)


@pytest.mark.parametrize("number", range(1, 38))
def test_expected_reading_order_matches_original_geometry(number):
    import pymupdf

    content = module("verify")
    expected = json.loads((FIXTURE / f"expected/p{number:02}.json").read_text(encoding="utf-8"))
    with pymupdf.open(_source()) as pdf:
        chars = [char for char in content._chars(pdf[number - 1]) if char["c"] != "※"]
        for block in expected["blocks"]:
            for item in block["cells"] if block["kind"] == "table" else [block]:
                selected = content._inside(chars, item["source_bbox"])
                actual = content._compact(content._reading(selected, tuple(item["direction"])))
                assert actual == content._compact(item["text"]), item["id"]
                overrides = {entry["character_index"]: entry["direction"]
                             for entry in item.get("source_direction_overrides", [])}
                ordered = [char for line, _ in content._ordered_lines(selected, item["direction"])
                           for char in line if not char["c"].isspace()]
                for index, char in enumerate(ordered):
                    assert tuple(char["direction"]) == tuple(overrides.get(index, item["direction"])), item["id"]


def _first_text(commands, predicate=lambda command: True):
    return next(index for index, command in enumerate(commands) if isinstance(command, Text) and predicate(command))


@pytest.mark.parametrize("category", ["font", "position", "equals", "table"])
def test_native_appearance_mutations_are_rejected(category, tmp_path):
    def change(commands, pages, fonts):
        if category == "font":
            index = _first_text(commands)
            commands[index] = replace(commands[index], style=replace(commands[index].style, font="MS Mincho"))
        elif category == "position":
            # One operand drops 2 pt off its line's baseline.
            index = _first_text(commands, lambda command: command.text == "×")
            commands[index] = replace(commands[index], y=commands[index].y + 2)
        elif category == "equals":
            index = _first_text(commands, lambda command: command.text == "=")
            commands[index] = replace(commands[index], x=commands[index].x + 2)
        else:
            # Move an actual drawn row boundary, leaving trace and text untouched.
            boundary = min(command.y1 for command in commands
                           if isinstance(command, Line) and abs(command.y1 - command.y2) < .001)
            commands = [replace(command, y1=command.y1 + 1, y2=command.y2 + 1)
                        if isinstance(command, Line) and abs(command.y1 - boundary) < .001
                        and abs(command.y1 - command.y2) < .001 else command for command in commands]
        return commands
    path, trace = _mutated(1, change, tmp_path, f"bad-{category}")
    report = module("verify_appearance").appearance_report(path, source_pages=(1,), trace=trace, categories=(category,))
    assert any(error["category"] == category for error in report["errors"]), report


@pytest.mark.parametrize("shift", [2, 6, 16.08, -16.08])
def test_relation_moved_off_its_anchor_by_any_distance_is_rejected(shift, tmp_path):
    """Every equals of an equation line sits on one of the line's anchors, however far it moves."""
    def change(commands, pages, fonts):
        index = _first_text(commands, lambda command: command.text == "=")
        commands[index] = replace(commands[index], x=commands[index].x + shift)
        return commands
    path, trace = _mutated(1, change, tmp_path, "moved-equals")
    report = module("verify_appearance").appearance_report(path, source_pages=(1,), trace=trace, categories=("equals",))
    assert any(error["detail"] == "relation is off its anchors" for error in report["errors"]), report


@pytest.mark.parametrize("part,text", [("result", "-73.30"), ("unit", "kN")])
def test_result_and_unit_moved_off_their_anchors_are_rejected(part, text, tmp_path):
    def change(commands, pages, fonts):
        index = _first_text(commands, lambda command: command.text == text
                            and command.tag is not None and command.tag.scope(Kind.EQUATION_PART).part == part)
        commands[index] = replace(commands[index], x=commands[index].x - 6)
        return commands
    path, trace = _mutated(12, change, tmp_path, f"moved-{part}")
    report = module("verify_appearance").appearance_report(path, source_pages=(12,), trace=trace, categories=("equals",))
    assert any(error["detail"] in ("result_right anchor is not the result's end", "unit_start anchor is not the unit's start")
               for error in report["errors"]), report


def _trace_mutation_report(reproduction, category, mutate):
    path, trace = reproduction
    broken = json.loads(json.dumps(trace))
    mutate(broken)
    return module("verify_appearance").appearance_report(
        path, source_pages=REPRODUCTION_PAGES, trace=broken, categories=(category,))


def test_item_off_the_page_grid_is_rejected(reproduction):
    def mutate(trace):
        node = trace["pages"][REPRODUCTION_PAGES.index(1)]["metadata"]["placements"][0]
        node["x_pt"] = node.get("x_pt", 0) + .5
    report = _trace_mutation_report(reproduction, "position", mutate)
    assert any("off the page grid" in error["detail"] for error in report["errors"]), report


def _walk_trace(value, visit):
    if isinstance(value, dict):
        visit(value)
        for child in value.values():
            _walk_trace(child, visit)
    elif isinstance(value, list):
        for child in value:
            _walk_trace(child, visit)


def test_equation_anchor_off_the_column_grid_is_rejected(reproduction):
    def mutate(trace):
        def visit(value):
            if isinstance(value.get("anchors_pt"), dict) and value["anchors_pt"].get("first_equal") is not None:
                value["anchors_pt"]["first_equal"] += .3
        _walk_trace(trace["pages"][REPRODUCTION_PAGES.index(3)], visit)
    report = _trace_mutation_report(reproduction, "equals", mutate)
    assert any(error["detail"] == "first_equal anchor is off the grid" for error in report["errors"]), report


def test_rotated_items_without_a_rotation_are_rejected(reproduction):
    verifier = module("verify_appearance")

    def mutate(trace):
        for record in verifier._rotations(trace["pages"][REPRODUCTION_PAGES.index(36)]["metadata"]["placements"]):
            record.pop("turns")
    report = _trace_mutation_report(reproduction, "rotation", mutate)
    assert [error["detail"] for error in report["errors"]] == ["rotated items without a rotation"]
    assert report["checks"]["rotation"] > len(REPRODUCTION_PAGES)


def test_original_rule_missing_from_the_output_is_rejected(tmp_path):
    def change(commands, pages, fonts):
        # Drop the table's lowest horizontal rule (the original has a rule there).
        index = max((i for i, command in enumerate(commands) if isinstance(command, Line)
                     and abs(command.y1 - command.y2) < .001), key=lambda i: commands[i].y1)
        commands.pop(index)
        return commands
    path, trace = _mutated(1, change, tmp_path, "missing-rule")
    report = module("verify_appearance").appearance_report(path, source_pages=(1,), trace=trace, categories=("table",))
    assert any(error["detail"].endswith("original rule is absent") for error in report["errors"]), report


def test_indentation_levels_must_keep_their_order(tmp_path):
    """p1's headings step right level by level; moving one right of its deeper neighbour fails."""
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(1,))
    regions, _ = module("verify")._trace_regions(layout_trace(pages, fonts)["pages"][0])
    x0, y0, x1, y1 = regions["p01-vertical"]

    shift = 2 * builder.SOURCE_PROFILE.grid.pitch_x

    def change(commands, pages, fonts):
        # 「(1) 鉛直荷重」 (level 2) moves two columns right, past 「1) 死荷重」 (level 3): text and block together.
        return [replace(command, x=command.x + shift)
                if isinstance(command, Text) and x0 <= command.x <= x1 and y0 <= command.y <= y1 else command
                for command in commands]
    path, trace = _mutated(1, change, tmp_path, "bad-indent")

    def visit(value):
        if value.get("block_id") == "p01-vertical" and "x_pt" in value:
            value["x_pt"] += shift
    _walk_trace(trace, visit)
    report = module("verify_appearance").appearance_report(path, source_pages=(1,), trace=trace, categories=("position",))
    assert [error["detail"] for error in report["errors"] if error["id"] == "p01-dead-title"] == [
        "indent is not right of p01-vertical"], report


def test_text_moved_inside_its_own_block_is_rejected(tmp_path):
    """A paragraph's lines start at its block's left edge: its text cannot drift inside the block."""
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(1,))
    regions, _ = module("verify")._trace_regions(layout_trace(pages, fonts)["pages"][0])
    x0, y0, x1, y1 = regions["p01-vertical"]

    def change(commands, pages, fonts):
        return [replace(command, x=command.x + 3) if isinstance(command, Text)
                and x0 <= command.x <= x1 and y0 <= command.y <= y1 else command for command in commands]
    path, trace = _mutated(1, change, tmp_path, "drifted-text")
    report = module("verify_appearance").appearance_report(path, source_pages=(1,), trace=trace, categories=("position",))
    assert any(error["id"] == "p01-vertical" and "left edge" in error["detail"] for error in report["errors"]), report


def test_rotated_tables_must_be_laid_out_on_the_swapped_page_grid(reproduction):
    path, trace = reproduction
    verifier = module("verify_appearance")
    broken = json.loads(json.dumps(trace))
    index = REPRODUCTION_PAGES.index(30)
    record = next(verifier._rotations(broken["pages"][index]["metadata"]["placements"]))
    record["local_grid"]["pitch_x"] = .01
    report = verifier.appearance_report(path, source_pages=REPRODUCTION_PAGES, trace=broken, categories=("rotation",))
    assert [error["detail"] for error in report["errors"]] == ["local grid is not the swapped page grid"]


def test_removing_original_synthetic_italic_is_rejected(tmp_path):
    def change(commands, pages, fonts):
        assert sum(isinstance(command, Text) and bool(command.shear_x) for command in commands) == 4
        return [replace(command, shear_x=0) if isinstance(command, Text) and command.shear_x else command
                for command in commands]
    path, trace = _mutated(1, change, tmp_path, "missing-original-italic")
    report = module("verify_appearance").appearance_report(path, source_pages=(1,), trace=trace, categories=("font",))
    assert sum(error["detail"] == "glyph inline extent" for error in report["errors"]) == 4


# Crops of the two original Identity-V parentheses (x 132-145 pt; the second heading is 226.8 pt lower).
ORIGINAL_PARENTHESIS_CROPS = {"（": (200.5, 207.5), "）": (229.5, 234.5)}


@pytest.mark.parametrize("number", [21, 22])
@pytest.mark.parametrize("mark", ["（", "）"])
def test_vertical_parenthesis_ink_matches_the_original_glyph_and_sits_in_its_column(number, mark, tmp_path):
    """The turned parenthesis has the original's ink shape and stays between its neighbouring kanji."""
    import pymupdf
    from PIL import Image

    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(number,))
    commands = pages[0].commands
    turned = [command for command in commands if isinstance(command, Text) and command.text == mark
              and command.quarter_turns == 3]
    assert len(turned) == 2
    path = tmp_path / "parenthesis.pdf"
    render_pdf(pages, path, fonts)

    def ink(pdf_path, page_number, box):
        with pymupdf.open(pdf_path) as pdf:
            pixmap = pdf[page_number].get_pixmap(matrix=pymupdf.Matrix(8, 8), clip=pymupdf.Rect(*box),
                                                colorspace=pymupdf.csGRAY, alpha=False)
        with Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples) as image:
            with image.point(lambda value: 255 if value < 128 else 0) as mask:
                bbox = mask.getbbox()
                return (bbox[2] - bbox[0], bbox[3] - bbox[1]), mask.histogram()[255]

    top, bottom = ORIGINAL_PARENTHESIS_CROPS[mark]
    for side, command in enumerate(sorted(turned, key=lambda c: c.y)):
        bounds = command_bounds(command, fonts)
        out_size, out_pixels = ink(path, 0, (bounds.x - 1, bounds.y - 1, bounds.right + 1, bounds.bottom + 1))
        src_size, src_pixels = ink(_source(), number - 1, (132, top + side * 226.8, 145, bottom + side * 226.8))
        # 10.0 pt against the original's 9.9 pt: the same glyph, within a few 1/8 pt pixels.
        assert max(abs(a - b) for a, b in zip(out_size, src_size)) <= 3
        assert abs(out_pixels - src_pixels) / src_pixels < .10
        # Centred on the kanji column, between the characters above and below.
        column = [other for other in commands if isinstance(other, Text) and other.quarter_turns == 0
                  and len(other.text) == 1 and abs(other.x - command.x) < 12]
        above = max((command_bounds(other, fonts) for other in column if other.y < command.y), key=lambda b: b.y)
        below = min((command_bounds(other, fonts) for other in column if other.y > command.y), key=lambda b: b.y)
        ink_box = module("appearance").VerticalGlyph(mark).measure(fonts, command.style)
        assert ink_box.width == 10
        assert above.bottom <= bounds.y and bounds.bottom <= below.y
        assert (bounds.x + bounds.right) / 2 == pytest.approx((above.x + above.right) / 2, abs=.5)
    # Negative control: a parenthesis moved 8 pt up overlaps the kanji above it.
    moved = replace(turned[0], y=turned[0].y - 8)
    bounds = command_bounds(moved, fonts)
    above = max((command_bounds(other, fonts) for other in commands if isinstance(other, Text)
                 and other.quarter_turns == 0 and len(other.text) == 1 and abs(other.x - moved.x) < 12
                 and other.y < turned[0].y), key=lambda b: b.y)
    assert bounds.y < above.bottom


@pytest.mark.parametrize("size", [9.5, 10.5])
def test_native_body_size_off_by_one_step_is_rejected(size, tmp_path):
    def change(commands, pages, fonts):
        index = _first_text(commands, lambda command: command.style.size == 10)
        commands[index] = replace(commands[index], style=replace(commands[index].style, size=size))
        return commands
    path, trace = _mutated(1, change, tmp_path, "bad-size")
    report = module("verify_appearance").appearance_report(path, source_pages=(1,), trace=trace, categories=("font",))
    assert any(error["detail"] == "body size (0.5 pt step)" for error in report["errors"]), report


def test_output_rules_must_have_their_border_styles_thickness(tmp_path):
    """FR-027: the original's 0.12 pt is not a tolerance; output hairlines are hair 0.25 pt."""
    def change(commands, pages, fonts):
        changed = [replace(command, width=.12) if isinstance(command, Line) and command.width == .25 else command
                   for command in commands]
        assert changed != commands
        return changed
    path, trace = _mutated(1, change, tmp_path, "source-width-rules")
    verifier = module("verify_appearance")
    report = verifier.appearance_report(path, source_pages=(1,), trace=trace, categories=("table",))
    wrong = [error for error in report["errors"] if error["detail"].endswith("rule thickness (border style)")]
    assert wrong and all(error["expected"] == .25 and error["actual"] == pytest.approx(.12) for error in wrong)
    native, trace = _mutated(1, lambda commands, pages, fonts: commands, tmp_path, "native")
    assert not verifier.appearance_report(native, source_pages=(1,), trace=trace, categories=("table",))["errors"]


def _relaid(number, change, tmp_path, name):
    """Like ``_mutated``, but the trace is made from the changed commands too.

    The PDF then draws exactly what its trace says ("placement" passes), so
    only the layout rules can reject the change.
    """
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(number,))
    changed = [ScenePage(pages[0].profile, tuple(change(list(pages[0].commands), pages, fonts)), pages[0].metadata)]
    path = tmp_path / f"{name}.pdf"
    render_pdf(changed, path, fonts)
    return path, layout_trace(changed, fonts)


def _part_is(command, part, text=None):
    if not isinstance(command, Text) or command.tag is None or (text is not None and command.text != text):
        return False
    scope = command.tag.scope(Kind.EQUATION_PART)
    return scope is not None and scope.part == part


def _report(path, trace, number, category):
    return module("verify_appearance").appearance_report(path, source_pages=(number,), trace=trace, categories=(category,))


def _moved(predicate, dx=0.0, dy=0.0):
    def change(commands, pages, fonts):
        index = _first_text(commands, predicate)
        commands[index] = replace(commands[index], x=commands[index].x + dx, y=commands[index].y + dy)
        return commands
    return change


@pytest.mark.parametrize("dx,dy", [(64.1, 0), (1, 0), (-1, 0), (0, .5)])
def test_glyph_not_where_its_layout_command_put_it_is_rejected(dx, dy, tmp_path):
    """FR-027 placement: each output glyph is where the layout trace drew it (p15 13580.00 moved)."""
    path, trace = _mutated(15, _moved(lambda c: _part_is(c, "term", "13580.00"), dx, dy), tmp_path, "moved-term")
    details = {error["detail"] for error in _report(path, trace, 15, "placement")["errors"]}
    assert "glyphs are not where their layout command put them" in details


def test_glyph_without_a_layout_command_is_rejected(tmp_path):
    def change(commands, pages, fonts):
        index = _first_text(commands, lambda c: _part_is(c, "term", "13580.00"))
        return [*commands, replace(commands[index], y=commands[index].y + 200)]
    path, trace = _mutated(15, change, tmp_path, "extra-glyphs")
    details = {error["detail"] for error in _report(path, trace, 15, "placement")["errors"]}
    assert "glyphs without a layout command" in details


@pytest.mark.parametrize("kind", ["moved", "missing"])
def test_side_rule_bar_not_where_its_layout_command_put_it_is_rejected(kind, tmp_path):
    def change(commands, pages, fonts):
        index = next(i for i, c in enumerate(commands) if isinstance(c, Rectangle))
        if kind == "missing":
            return commands[:index] + commands[index + 1:]
        commands[index] = replace(commands[index], x=commands[index].x + 1)
        return commands
    path, trace = _mutated(16, change, tmp_path, f"bar-{kind}")
    details = {error["detail"] for error in _report(path, trace, 16, "placement")["errors"]}
    assert "rule is not where its layout command put it" in details


def test_table_rule_not_where_its_layout_command_put_it_is_rejected(tmp_path):
    def change(commands, pages, fonts):
        index = next(i for i, c in enumerate(commands) if isinstance(c, Line))
        commands[index] = replace(commands[index], x1=commands[index].x1 + .5, x2=commands[index].x2 + .5)
        return commands
    path, trace = _mutated(26, change, tmp_path, "moved-rule")
    details = {error["detail"] for error in _report(path, trace, 26, "placement")["errors"]}
    assert "rule is not where its layout command put it" in details


@pytest.mark.parametrize("text,dx", [("13580.00", 1), ("13580.00", -1), ("×", 1), ("13580.00", 64.1)])
def test_term_off_its_grid_column_is_rejected(text, dx, tmp_path):
    """FR-025: each term sits in its own grid columns at its alignment, even when the trace agrees."""
    path, trace = _relaid(15, _moved(lambda c: _part_is(c, "term", text), dx), tmp_path, "term-off-column")
    details = {error["detail"] for error in _report(path, trace, 15, "equals")["errors"]}
    assert "term is off its grid columns" in details, details


def test_left_hand_side_off_its_groups_right_edge_is_rejected(tmp_path):
    def change(commands, pages, fonts):
        # The command that ends the first line's left-hand side moves 2 pt left.
        first = _first_text(commands, lambda c: _part_is(c, "lhs"))
        line = commands[first].tag.key(Kind.EQUATION_LINE)
        index = max((i for i, c in enumerate(commands) if _part_is(c, "lhs") and c.tag.key(Kind.EQUATION_LINE) == line),
                    key=lambda i: commands[i].x)
        commands[index] = replace(commands[index], x=commands[index].x - 2)
        return commands
    path, trace = _relaid(15, change, tmp_path, "lhs-moved")
    details = {error["detail"] for error in _report(path, trace, 15, "equals")["errors"]}
    assert "left-hand side does not end with its group's" in details, details


def test_label_off_its_groups_left_edge_is_rejected(tmp_path):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    number = next(n for n in range(1, 30) if any(_part_is(c, "label")
                                                 for c in builder.layout_report(fonts, source_pages=(n,))[0].commands))
    path, trace = _relaid(number, _moved(lambda c: _part_is(c, "label"), 2), tmp_path, "label-moved")
    details = {error["detail"] for error in _report(path, trace, number, "equals")["errors"]}
    assert "label does not start at its group's left edge" in details, details


def test_paragraph_inside_a_container_off_the_column_grid_is_rejected(tmp_path):
    """p16: the bracketed derivations' titles are paragraphs inside Stacks (no region edge of their own)."""
    path, trace = _relaid(16, _moved(lambda c: c.text == "可動支承に働く鉛直荷重", 3), tmp_path, "title-moved")
    errors = _report(path, trace, 16, "position")["errors"]
    assert any(error["detail"] == "line does not start on a grid column" for error in errors), errors


@pytest.mark.parametrize("dx,dy,detail", [(0, 2, "cell line is off its rows"), (0, -15.48, "cell line is off its rows"),
                                          (3, 0, "cell line is not centred in its padding")])
def test_cell_text_off_its_cell_lines_is_rejected(dx, dy, detail, tmp_path):
    path, trace = _relaid(26, _moved(lambda c: c.text == "(KN)", dx, dy), tmp_path, "cell-moved")
    errors = _report(path, trace, 26, "table")["errors"]
    assert any(error["detail"] == detail for error in errors), errors


def test_side_rule_bar_off_the_grid_is_rejected(tmp_path):
    def change(commands, pages, fonts):
        index = next(i for i, c in enumerate(commands) if isinstance(c, Rectangle))
        commands[index] = replace(commands[index], x=commands[index].x + 1)
        return commands
    path, trace = _relaid(16, change, tmp_path, "bar-off-grid")
    errors = _report(path, trace, 16, "position")["errors"]
    assert any(error["detail"] == "side rule is off the page grid" for error in errors), errors


def test_glyph_across_the_second_relation_on_a_line_with_a_result_is_rejected(tmp_path):
    """Only a line without a result may run across the second relation's column; a result moved
    onto it (reading order kept) is not skipped."""
    def change(commands, pages, fonts):
        index = _first_text(commands, lambda c: _part_is(c, "result", "-73.30"))
        line = commands[index].tag.key(Kind.EQUATION_LINE)
        second = next(c for c in commands if _part_is(c, "result_relation") and c.tag.key(Kind.EQUATION_LINE) == line)
        commands[index] = replace(commands[index], x=second.x + 2)
        return commands
    path, trace = _mutated(12, change, tmp_path, "result-across-second")
    details = {error["detail"] for error in _report(path, trace, 12, "equals")["errors"]}
    assert "a glyph runs across the second relation" in details, details


@pytest.mark.parametrize("dx", [-8, -2])
def test_command_starting_with_a_space_moved_is_rejected(dx, tmp_path):
    """p28 '\u3000[': its first glyph is not at the origin, so its end ties it down."""
    path, trace = _mutated(28, _moved(lambda c: c.text == "\u3000[", dx), tmp_path, "space-start")
    details = {error["detail"] for error in _report(path, trace, 28, "placement")["errors"]}
    assert "glyphs are not where their layout command put them" in details, details


def test_rule_drawn_dashed_instead_of_solid_is_rejected(tmp_path):
    def change(commands, pages, fonts):
        index = next(i for i, c in enumerate(commands) if isinstance(c, Line))
        commands[index] = replace(commands[index], dash=(1, 1))
        return commands
    path, trace = _mutated(26, change, tmp_path, "dashed-rule")
    details = {error["detail"] for error in _report(path, trace, 26, "placement")["errors"]}
    assert "rule is not where its layout command put it" in details, details


def test_commands_without_semantic_tags_are_rejected(reproduction):
    def mutate(trace):
        for command in trace["pages"][REPRODUCTION_PAGES.index(16)]["commands"]:
            command.pop("tag", None)
    report = _trace_mutation_report(reproduction, "placement", mutate)
    assert any(error["detail"] == "command without a semantic tag" for error in report["errors"]), report


def test_cells_whose_lines_lost_their_tags_are_rejected(reproduction):
    """The cell rules cannot pass by checking nothing: rotated tables without cell-line tags fail."""
    def mutate(trace):
        for number in (30, 36):
            for command in trace["pages"][REPRODUCTION_PAGES.index(number)]["commands"]:
                if command.get("tag"):
                    command["tag"]["path"] = [step for step in command["tag"]["path"] if step["kind"] != "cell_lines"]
    report = _trace_mutation_report(reproduction, "table", mutate)
    assert any(error["detail"] == "cell text without tagged cell lines" for error in report["errors"]), report


def test_equation_lines_whose_commands_lost_their_tags_are_rejected(reproduction):
    def mutate(trace):
        for command in trace["pages"][REPRODUCTION_PAGES.index(9)]["commands"]:
            if command.get("tag"):
                command["tag"]["path"] = [step for step in command["tag"]["path"] if step["kind"] != "equation_line"]
    report = _trace_mutation_report(reproduction, "equals", mutate)
    assert any(error["detail"] == "equation line without tagged commands" for error in report["errors"]), report


def test_left_hand_side_of_a_one_line_group_moved_is_rejected(tmp_path):
    """p3's one-line groups: the left-hand side ends one gap before its relation, not just with its group."""
    def change(commands, pages, fonts):
        first = _first_text(commands, lambda c: _part_is(c, "lhs"))
        line = commands[first].tag.key(Kind.EQUATION_LINE)
        return [replace(c, x=c.x - 2) if _part_is(c, "lhs") and c.tag.key(Kind.EQUATION_LINE) == line else c
                for c in commands]
    path, trace = _relaid(3, change, tmp_path, "lhs-one-line")
    details = {error["detail"] for error in _report(path, trace, 3, "equals")["errors"]}
    assert "left-hand side does not end one gap before its relation" in details, details


@pytest.mark.parametrize("number,text,dx,dy,detail", [
    (1, "G2", .7, 0, "cell line is not centred in its padding"),
    (1, "G2", 0, .7, "cell lines are not centred between their cell's top and bottom"),
    (1, "520.0", -1.4, 0, "cell line is not aligned right in its padding"),
    (26, "0.00", -1.4, 0, "cell line is not aligned right in its padding")])
def test_cell_text_off_its_padding_by_less_than_a_point_is_rejected(number, text, dx, dy, detail, tmp_path):
    path, trace = _relaid(number, _moved(lambda c: c.text == text and c.tag is not None
                                         and c.tag.scope(Kind.TABLE_CELL) is not None, dx, dy), tmp_path, "cell-pad")
    errors = _report(path, trace, number, "table")["errors"]
    assert any(error["detail"] == detail for error in errors), errors


def test_debug_grid_pdf_draws_only_its_commands_and_the_grid(tmp_path):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(16,))
    path = tmp_path / "grid.pdf"
    render_pdf(pages, path, fonts, debug_grid=True)
    report = _report(path, layout_trace(pages, fonts), 16, "placement")
    assert not report["errors"], report["errors"][:3]
    assert report["rule_checks"]["placement.grid_lines"] == (31 + 1) + (48 + 1)


@pytest.mark.parametrize("dy", [1.0, -1.0])
def test_rotated_cell_line_across_its_local_row_is_rejected(dy, tmp_path):
    """p30: a cell line moved 1 pt across (a page column in the turned table) leaves its local row."""
    def predicate(command):
        return (isinstance(command, Text) and command.text.strip() and command.tag is not None
                and command.tag.scope(Kind.QUARTER_TURN) is not None)
    # The turned table's lines run up the page: across them is x.
    path, trace = _relaid(30, _moved(predicate, dy, 0), tmp_path, "rotated-row")
    errors = _report(path, trace, 30, "table")["errors"]
    assert any(error["detail"] in ("cell line is not inside its own grid row", "cell line leaves its baseline",
                                   "cell lines are not centred between their cell's top and bottom")
               for error in errors), errors


@pytest.mark.parametrize("number", [1, 30])
def test_cell_lines_moved_a_whole_row_are_rejected(number, tmp_path, monkeypatch):
    """A multi-line cell's rows are the ones nearest the cell's middle (ties upward): a builder that
    puts them one row lower where it can is rejected, though every line is still inside a row."""
    builder = module("builder")
    placement = builder._row_placement

    def lower(count, total, pitch, boxes, *, top, bottom, where):
        start, offset = placement(count, total, pitch, boxes, top=top, bottom=bottom, where=where)
        if start + count < total:
            # One row lower, at the offset that row would need (clear of the bottom rule if it is the last).
            low = max(box.ascent for box in boxes)
            high = min([pitch - box.descent for box in boxes]
                       + ([pitch - boxes[-1].descent - bottom - .01] if start + 1 + count == total else []))
            if low <= high:
                return start + 1, (low + high) / 2
        return start, offset
    monkeypatch.setattr(builder, "_row_placement", lower)
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(number,))
    path = tmp_path / "lower.pdf"
    render_pdf(pages, path, fonts)
    errors = _report(path, layout_trace(pages, fonts), number, "table")["errors"]
    assert any(error["detail"] == "cell lines are not centred in their cell by whole rows" for error in errors), errors[:3]


@pytest.mark.parametrize("dy", [2.0, -2.0, .3])
def test_turned_parenthesis_moved_in_its_row_is_rejected(dy, tmp_path):
    """p21: a line without a full-size baseline (the turned parenthesis) is centred on its row's em box."""
    path, trace = _relaid(21, _moved(lambda c: c.text in ("（", "）") and c.quarter_turns == 3, 0, dy),
                          tmp_path, "turned-parenthesis")
    errors = _report(path, trace, 21, "table")["errors"]
    assert any(error["detail"] in ("cell line without a baseline is off its row's em box",
                                   "cell line is not inside its own grid row") for error in errors), errors


def test_verifier_and_builder_keep_the_same_rule_margin():
    """The verifiers do not import the builder; the values both use must stay the same."""
    builder, verifier = module("builder"), module("verify_appearance")
    assert verifier._STROKE_MARGIN_PT == builder._STROKE_MARGIN
    assert verifier._CELL_PADDING_PT == builder._CELL_PADDING
    assert module("verify")._ALIGNED_PT == builder.ALIGNED_SOURCE_PT
