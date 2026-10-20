"""FR-027: the cantilever p1-p37 reproduction follows the grid rules of FR-021-026.

These checks replace the former position/row-height/rule-width/size comparisons
with the original: every placement, table row and column, indent and equals
position lies on the page grid; rules are border styles drawn by library parts;
sizes are 0.5 pt steps (scripts excepted); the rotated tables are laid out on
the page grid with its axes swapped. The page grids are the user's choice
(2026-10-20): the A4.pdf grid for p1-p29 and 10.8 x 14.52 pt for p30-p37.
Content, order, page and font are still compared with the original elsewhere.
"""

import importlib.util
import json
import math
from pathlib import Path
import sys

import pytest

from gridlayoutpdf import GridSpec, Line, Rectangle, Text, layout_trace
from gridlayoutpdf.semantics import BORDER_ROLES, Kind, Role


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/cantilever_p01_37"
A4_GRID = GridSpec(50.88, 54.598, 16.08, 15.48, 31, 48)
ROTATED_GRID = GridSpec(50.88, 54.598, 10.8, 14.52, 46, 51)
ROTATED_PAGES = tuple(range(30, 38))
# Stroke widths of the border styles in PDF (FR-022): hair, thin, medium, thick (double is two thin).
BORDER_STROKES = (.25, .5, 1.0, 1.5)
EPSILON = 1e-6


def _module(name):
    key = f"cantilever_fixture_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, FIXTURE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


@pytest.fixture(scope="module")
def layouts():
    """The whole report, and each original page alone (so one failing page cannot hide the rest)."""
    builder = _module("builder")
    fonts = builder.fixture_fonts()
    try:
        whole = builder.layout_report(fonts)
    except Exception as exc:  # noqa: BLE001 - reported by test_all_37_pages_lay_out_one_per_original_page
        whole = exc
    single = {}
    for number in range(1, 38):
        try:
            single[number] = builder.layout_report(fonts, source_pages=(number,))[0]
        except Exception as exc:  # noqa: BLE001 - reported by test_every_original_page_lays_out_alone
            single[number] = exc
    return fonts, whole, single


@pytest.fixture(scope="module")
def report(layouts):
    """Every page that lays out alone, with its number, and the trace of those pages."""
    fonts, _, single = layouts
    numbers = [number for number, page in single.items() if not isinstance(page, Exception)]
    pages = [single[number] for number in numbers]
    return fonts, list(zip(numbers, pages)), layout_trace(pages, fonts)


def test_every_original_page_lays_out_alone(layouts):
    _, _, single = layouts
    failures = {number: str(page)[:160] for number, page in single.items() if isinstance(page, Exception)}
    assert not failures


def _on_lines(value, origin, pitch):
    steps = (value - origin) / pitch
    return abs(steps - round(steps)) <= EPSILON * max(1, abs(steps))


def _swapped(grid):
    return {"origin_x": 0, "origin_y": 0, "pitch_x": grid.pitch_y, "pitch_y": grid.pitch_x,
            "columns": grid.rows, "rows": grid.columns}


def test_all_37_pages_lay_out_one_per_original_page(layouts):
    _, pages, _ = layouts
    assert not isinstance(pages, Exception), str(pages)[:300]
    assert len(pages) == 37
    assert [page.metadata["placements"][0]["block_id"] for page in pages] == [f"p{n:02}" for n in range(1, 38)]


def test_page_grids_are_the_a4_grid_and_the_rotated_table_grid(report):
    _, pages, _ = report
    for number, page in pages:
        wanted = ROTATED_GRID if number in ROTATED_PAGES else A4_GRID
        assert page.profile.grid == wanted, f"p{number:02}: page grid"
        assert (page.profile.width, page.profile.height) == (595, 842), f"p{number:02}: A4 portrait"


def test_rotated_tables_use_the_swapped_page_grid(report):
    _, pages, _ = report
    for number, page in pages:
        turned = [command for command in page.commands
                  if command.tag is not None and command.tag.scope(Kind.QUARTER_TURN) is not None]
        if number not in ROTATED_PAGES:
            assert not turned, f"p{number:02}: unexpected rotation"
            continue
        assert turned, f"p{number:02}: rotated table missing"
        for command in turned:
            scope = command.tag.scope(Kind.QUARTER_TURN)
            assert dict(scope.data["local_grid"]) == _swapped(page.profile.grid), f"p{number:02}: local grid"
            assert scope.data["turns"] == 1


def test_placements_items_and_table_cells_lie_on_the_page_grid(report):
    verify = _module("verify")
    _, pages, trace = report
    for (number, page), trace_page in zip(pages, trace["pages"]):
        grid = page.profile.grid
        regions, spans = verify._trace_regions(trace_page)
        assert regions, f"p{number:02}: no regions"
        for key, (x0, y0, x1, y1) in regions.items():
            if key in (f"p{number:02}", f"p{number:02}-content"):
                continue
            edges = (x0, y0, x1, y1) if key in spans else (x0, y0)
            for index, value in enumerate(edges):
                origin, pitch = (grid.origin_x, grid.pitch_x) if index % 2 == 0 else (grid.origin_y, grid.pitch_y)
                assert _on_lines(value, origin, pitch), f"{key}: edge {index} at {value} is off the page grid"


def test_rules_are_border_styles_of_library_parts(report):
    _, pages, _ = report
    for number, page in pages:
        for command in page.commands:
            if not isinstance(command, (Line, Rectangle)):
                continue
            role = command.tag.role if command.tag is not None else None
            assert role in BORDER_ROLES | {Role.FRACTION_BAR}, f"p{number:02}: {role} line is not a library rule"
            if role in BORDER_ROLES and isinstance(command, Line):
                assert any(abs(command.width - width) < EPSILON for width in BORDER_STROKES), \
                    f"p{number:02}: rule width {command.width} is not a border style"


def _equation_parts(value):
    if isinstance(value, dict):
        if "anchors_pt" in value:
            yield value
        for child in value.values():
            yield from _equation_parts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _equation_parts(child)


def test_equations_use_grid_term_columns_without_fallback_or_moved_results(report):
    """FR-025/FR-027: every equation line with terms has grid term columns; none falls back or drops its result."""
    _, pages, trace = report
    grid_lines = 0
    for (number, page), trace_page in zip(pages, trace["pages"]):
        for part in _equation_parts(trace_page["metadata"]["placements"]):
            assert not part.get("term_fallback"), f"p{number:02}: equation {part['equation_index']} fell back"
            assert not part.get("result_line"), f"p{number:02}: equation {part['equation_index']} moved its result"
            grid_lines += "term_columns_grid" in part
        terms = [command for command in page.commands if command.tag is not None
                 and (part := command.tag.scope(Kind.EQUATION_PART)) is not None and part.part == "term"]
        for command in terms:
            data = command.tag.scope(Kind.EQUATION_PART).data
            assert "first_column" in data and "columns" in data, f"p{number:02}: a term is not on grid columns"
    assert grid_lines > 200


# Equation runs whose split terms do not fit the original's lines: each right-hand side is one
# term (one grid-Excel cell) instead (builder._groups); (page, group, lines).
WHOLE_TERM_RUNS = {(1, "p01-reactions-run1", 1), (2, "p02-c-reactions-run1", 1), (2, "p02-c-reactions-run2", 1),
                   (2, "p02-bc-reactions-run1", 1), (12, "p12-with-origin-reactions", 4),
                   (13, "p13-origin-reactions", 4), (13, "p13-end-reactions", 2),
                   (19, "p19-movable-rm-run1", 1), (19, "p19-fixed-rm-run1", 1)}


def test_only_the_pinned_runs_keep_each_right_hand_side_as_one_term(report):
    """M4: a whole-term run is not a library term_fallback, so it is pinned here; any other run
    whose terms fit takes one grid column per term."""
    from gridlayoutpdf import EquationGroup, Row, TermStop
    builder = _module("builder")
    fonts, pages, _ = report
    found = set()
    for number, page in pages:
        if number in ROTATED_PAGES:
            continue
        geometry = {block["id"]: block for block in
                    {item["source_page"]: item for item in builder.source_layout()["pages"]}[number]["blocks"]}
        data = json.loads((FIXTURE / f"pages/p{number:02}.json").read_text(encoding="utf-8"))
        leaves = tuple(builder._leaves({"type": "stack", "children": data["blocks"]}))
        state = builder._Page(number, fonts, geometry, leaves)
        for leaf in leaves:
            if leaf["type"] != "equations":
                continue
            built = builder._equations(leaf, state, 0, state.grid.columns - state.column(leaf, 0))
            for group in [built] if isinstance(built, EquationGroup) else built.children:
                whole = [item for item in group.equations if isinstance(item.rhs, Row) and len(item.rhs.items) == 2
                         and isinstance(item.rhs.items[0], TermStop) and isinstance(item.rhs.items[1], Row)
                         and len(builder._term_segments(item.rhs.items[1])) > 1]
                if whole:
                    found.add((number, group.block_id, len(whole)))
    assert found == WHOLE_TERM_RUNS


def test_results_stay_near_what_precedes_them(report):
    """A result (with its grid-Excel cells) is at most 4.5 columns right of the glyph before it.

    A right-hand side without a result does not push the second relation right
    (it may run on across it), so the result-only lines of p16-p20 stay near
    their relation: the gap left is the empty right-hand side's one column,
    the blank relation and the cells the family's widest result needs.
    """
    import json as _json
    _, pages, trace = report
    widest, checked = 0.0, 0
    for trace_page in trace["pages"]:
        pitch = trace_page["profile"]["grid"]["pitch_x"]
        lines = {}
        for command in trace_page["commands"]:
            path = (command.get("tag") or {}).get("path", [])
            kinds = [step["kind"] for step in path]
            if command["type"] != "Text" or "equation_line" not in kinds:
                continue
            index = kinds.index("equation_line")
            lines.setdefault(_json.dumps(path[:index + 1]), []).append((path[index + 1].get("part"), command))
        for found in lines.values():
            results = [command for part, command in found if part == "result"]
            if not results:
                continue
            start = min(command["x"] for command in results)
            before = [command["x"] + command["bounds"]["width"] for part, command in found
                      if part not in ("result", "unit") and command["text"].strip() and command["x"] < start]
            if before:
                checked += 1
                widest = max(widest, (start - max(before)) / pitch)
    assert checked > 200 and widest <= 4.5, (checked, widest)


def test_rotated_tables_drop_subscripts_one_point_and_other_pages_keep_the_original():
    """p30-p37 subscripts sit 1.0 pt below their base so a line fits its 10.8 pt local row;
    elsewhere the original's 1.92 pt stays (builder._with_subscript_drop)."""
    from gridlayoutpdf import Script
    builder = _module("builder")
    fonts = builder.fixture_fonts()
    drops = {}

    def walk(node, found):
        if isinstance(node, Script):
            found.add(node.subscript_drop if node.subscript is not None else None)
            walk(node.base, found)
        for child in getattr(node, "items", ()) or ():
            walk(child, found)
        for name in ("numerator", "denominator"):
            if hasattr(node, name):
                walk(getattr(node, name), found)
    import json as _json
    for number in (1, 21, 30, 36):
        data = _json.loads((FIXTURE / f"pages/p{number:02}.json").read_text(encoding="utf-8"))
        page = builder._Page(number, fonts, {block["id"]: block for block in
                                             {item["source_page"]: item for item in builder.source_layout()["pages"]}[number]["blocks"]},
                             tuple(builder._leaves({"type": "stack", "children": data["blocks"]})))
        found = set()
        for leaf in page.leaves:
            if leaf["type"] == "table":
                table = builder._table(leaf, page)
                table = getattr(table, "block", table)
                for row in table.rows:
                    for cell in row:
                        for line in cell.content.lines:
                            walk(line, found)
        drops[number] = found - {None}
    # p36's tables have no subscript.
    assert drops[30] == {builder._ROTATED_SUBSCRIPT_DROP} == {1.0} and drops[36] == set()
    assert drops[1] <= {1.92} and drops[21] <= {1.92}


def test_operators_the_original_set_in_one_column_share_a_column(report):
    """p3-p7: the per-girder lines' × sit in one column in the original (242.3 pt on p3); their
    groups share the terms' widths, so the × stay in one grid column."""
    _, pages, _ = report
    for number, page in pages:
        if number in (3, 4, 5, 6, 7):
            columns = {round(command.x, 3) for command in page.commands
                       if isinstance(command, Text) and command.text in ("×", "x")}
            assert len(columns) == 1, (number, columns)


def _table_lines(trace):
    """{(page, cell): {line index: [Text commands]}} of every tagged table cell line in a trace."""
    import json as _json
    cells = {}
    for page in trace["pages"]:
        for command in page["commands"]:
            path = (command.get("tag") or {}).get("path", [])
            cell = [step for step in path if step["kind"] == "table_cell"]
            line = [step for step in path if step["kind"] == "cell_lines"]
            table = [step for step in path if step["kind"] == "table"]
            if command["type"] == "Text" and cell and line:
                key = (page["page_number"], table[-1]["data"]["block_id"], cell[-1]["data"]["row"], cell[-1]["data"]["col"],
                       any(step["kind"] == "quarter_turn" for step in path))
                cells.setdefault(key, {}).setdefault(line[-1]["index"], []).append(command)
    return cells


def test_each_line_of_a_multi_line_cell_keeps_its_glyphs_inside_one_local_row(report):
    """FR-027 (lead, 2026-10-20): the grid Excel puts each line of a multi-line cell in a row of its
    own, so each such line's Text (its bounds) lies inside one local row: a page row, or on p30-p37
    a page column (the turned table's 10.8 pt row), the lines in consecutive rows. A one-line cell
    is merged over its range in the grid Excel and stays centred in its cell: its text lies inside
    the cell."""
    _, pages, trace = report
    regions = {}
    for page in trace["pages"]:
        found, _ = _module("verify")._trace_regions(page)
        regions[page["page_number"]] = found
    grids = {page["page_number"]: page["profile"]["grid"] for page in trace["pages"]}
    checked = {"multi": 0, "single": 0}
    for (number, table, row, col, turned), lines in _table_lines(trace).items():
        grid = grids[number]
        origin, pitch = (grid["origin_x"], grid["pitch_x"]) if turned else (grid["origin_y"], grid["pitch_y"])

        def extent(commands):
            if turned:
                return (min(c["bounds"]["x"] for c in commands), max(c["bounds"]["x"] + c["bounds"]["width"] for c in commands))
            return (min(c["bounds"]["y"] for c in commands), max(c["bounds"]["y"] + c["bounds"]["height"] for c in commands))
        if len(lines) == 1:
            box = regions[number][f"{table}.r{row}.c{col}"]
            low, high = extent(lines[0])
            inside = (box[0], box[2]) if turned else (box[1], box[3])
            assert inside[0] - EPSILON <= low and high <= inside[1] + EPSILON, (number, table, row, col)
            checked["single"] += 1
            continue
        rows = []
        for index, commands in sorted(lines.items()):
            low, high = extent(commands)
            first = math.floor((low - origin) / pitch + EPSILON)
            assert first == math.floor((high - origin) / pitch - EPSILON), (number, table, row, col, index, low, high)
            rows.append(first)
        assert rows == list(range(rows[0], rows[0] + len(rows))), (number, table, row, col, rows)
        checked["multi"] += 1
    assert checked == {"multi": 682, "single": 2322}


def test_one_line_cells_stay_centred_and_multi_line_cells_are_set_row_by_row():
    """builder._table: a one-line cell keeps its vertical centring (no first_baseline); a multi-line
    cell is top-aligned at a first_baseline from builder._row_placement. 6 rotated header cells
    move one row off the middle to clear the frame rule."""
    builder = _module("builder")
    placement = builder._row_placement
    seen = {"placed": 0, "moved": 0}

    def counting(count, total, pitch, boxes, *, top, bottom, where):
        assert count > 1, where
        start, offset = placement(count, total, pitch, boxes, top=top, bottom=bottom, where=where)
        seen["placed"] += 1
        if start != min(range(total - count + 1), key=lambda s: (abs(s - (total - count) / 2), s)):
            seen["moved"] += 1
        return start, offset
    builder._row_placement = counting
    try:
        builder.layout_report(builder.fixture_fonts())
    finally:
        builder._row_placement = placement
    assert seen == {"placed": 682, "moved": 6}


def test_grid_excel_of_all_37_pages_is_strict(layouts, tmp_path):
    """FR-027: the grid Excel of p1-p37 has no shifted text and no shape fallback (strict=True).

    p30-p37 have their own grid, so they are the second sheet. Numbers the
    grid Excel keeps as text (outside strict) are pinned so a change is noticed.
    """
    from gridlayoutpdf import render_xlsx
    fonts, whole, _ = layouts
    assert not isinstance(whole, Exception), str(whole)[:300]
    result = render_xlsx([("片持ち梁", whole)], tmp_path / "cantilever.xlsx", fonts, strict=True)
    assert [(sheet.name, sheet.first_page, sheet.last_page) for sheet in result.sheets] == [
        ("片持ち梁", 1, 29), ("片持ち梁_2", 30, 37)]
    assert not result.shifts and not result.fallbacks
    assert not result.untagged
    assert all("table seam" in item for item in result.dropped)
    # p2's results get two grid-Excel cells where Excel's screen needs 36.3 pt (two cells are 31.5 pt):
    # the builder gives a result fewer cells only where all of them would cost the original's lines.
    assert sorted((item.page, item.detail.split("'")[1]) for item in result.numbers_as_text) == [
        (2, "102.71"), (2, "223.14"), (2, "272.47"), (2, "294.92"), (2, "367.53"), (2, "416.86"), (2, "537.29")]


def test_bracket_bars_are_side_rules_of_a_border_style_on_column_lines(report):
    """The ten bars of p16-p20 are SideRule bars (filled rectangles) of a border style, on column lines.

    Each sits on the column line of the original bar's indentation level (builder._side_rule), two
    per page: column 6 on p16-p19, column 5 on p20.
    """
    builder = _module("builder")
    layout = {page["source_page"]: page for page in builder.source_layout()["pages"]}
    _, pages, _ = report
    bars = {}
    for number, page in pages:
        grid = page.profile.grid
        for command in page.commands:
            if isinstance(command, Rectangle) and command.tag is not None and command.tag.role == Role.SIDE_RULE:
                centre = command.x + command.width / 2
                assert any(abs(command.width - width) < EPSILON for width in BORDER_STROKES), f"p{number:02}: bar width"
                assert _on_lines(centre, grid.origin_x, grid.pitch_x), f"p{number:02}: bar off the column lines"
                bars.setdefault(number, []).append(round((centre - grid.origin_x) / grid.pitch_x, 6))
    assert bars == {16: [6, 6], 17: [6, 6], 18: [6, 6], 19: [6, 6], 20: [5, 5]}
    for number, columns in bars.items():
        levels = [builder.indent_columns(block["x"], number) for block in layout[number]["blocks"]
                  if block["kind"] == "rule"]
        assert columns == levels


def test_the_whole_report_lays_out_each_page_as_it_does_alone(layouts):
    _, whole, single = layouts
    assert not isinstance(whole, Exception)
    for number, page in enumerate(whole, 1):
        assert page.profile == single[number].profile, f"p{number:02}"
        assert page.commands == single[number].commands, f"p{number:02}"


def test_text_uses_original_fonts_half_point_sizes_and_library_scripts(report):
    _, pages, _ = report
    for number, page in pages:
        for command in page.commands:
            if not isinstance(command, Text):
                continue
            assert command.style.font in ("MS Mincho", "MS Gothic"), f"p{number:02}: font {command.style.font}"
            script = command.tag.scope(Kind.SCRIPT) if command.tag is not None else None
            if script is not None and script.part in ("superscript", "subscript"):
                assert 6.45 <= command.style.size < 8, f"p{number:02}: script size {command.style.size}"
                continue
            assert command.style.size >= 8, f"p{number:02}: {command.text!r} is small but not a library Script"
            assert math.isclose(command.style.size * 2, round(command.style.size * 2)), \
                f"p{number:02}: size {command.style.size} is not a 0.5 pt step"


def test_equals_of_equation_groups_are_centred_on_grid_columns(report):
    fonts, pages, _ = report
    checked = 0
    for number, page in pages:
        grid = page.profile.grid
        for command in page.commands:
            if not isinstance(command, Text) or command.tag is None:
                continue
            part = command.tag.scope(Kind.EQUATION_PART)
            if part is None or part.part not in ("relation", "result_relation"):
                continue
            if not command.text.strip():
                continue  # an invisible relation (a space) still takes its column, but has no centre to see
            # EquationGroup centres the relation's whole advance on the anchor column line.
            centre = command.x + fonts.measure(command.text, command.style).width / 2
            assert _on_lines(centre, grid.origin_x, grid.pitch_x), f"p{number:02}: {command.text} centre {centre}"
            checked += 1
    assert checked > 100
