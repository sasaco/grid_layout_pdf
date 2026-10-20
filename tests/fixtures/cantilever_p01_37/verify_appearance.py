"""Compare native output appearance with the original PDF, and check the FR-027 grid rules.

Authored layout/font profiles are deliberately not imported. The content oracle
supplies semantic regions; fonts and rules are read from the two PDFs. A
self-generated golden is not source appearance evidence.

FR-027 keeps the comparison with the original for content, reading order,
page and font (``font``: family, glyph direction, glyph shape, 0.5 pt size).
Positions, row heights, rule widths and sizes are no longer compared with the
original: they are checked against the new rules instead, read from the
output PDF and its layout trace (``position``, ``equals``, ``table``,
``rotation``). ``placement`` ties the two: the PDF draws exactly the
trace's commands, where they put them, so the rules read from the trace's
tagged commands (terms in their grid columns, left-hand sides, labels,
paragraph lines, cell lines, side rules) hold for the PDF too. The
original's own rule widths still say which border style each output rule
must have.
"""

from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import re
import struct

import pymupdf


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent
_spec = importlib.util.spec_from_file_location("cantilever_content_appearance", FIXTURE / "verify.py")
_content = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_content)

SOURCE_CATEGORIES = ("font",)
GRID_CATEGORIES = ("position", "equals", "table", "rotation", "placement")
CATEGORIES = SOURCE_CATEGORIES + GRID_CATEGORIES
# PDF extraction stores coordinates as float32; this is far below any grid or rule step.
_GRID_TOLERANCE_PT = .01
# Distinct original indentation levels differ by at least 10 pt (one level is 14.52 pt).
_INDENT_LEVEL_PT = 10
# A drawn glyph or rule is where its trace command put it within this (PDF float32 coordinates).
_PLACEMENT_TOLERANCE_PT = .02
# render_pdf(debug_grid=True) draws each page grid line in this stroke and colour.
_DEBUG_GRID_STROKE = .96
_DEBUG_GRID_COLOR = (.84, .87, .9)
# CellLines' side padding in the fixture: 2 pt plus the boundary rule's thickness (builder._table).
_CELL_PADDING_PT = 2.0
# The fixture keeps a cell line this far clear of the rule it would touch (Table needs strictly clear).
_STROKE_MARGIN_PT = .01
# The p21, p22 vertical headings: the original's Identity-V parentheses have origins off their line,
# so only these items skip the line structure comparison.
_IDENTITY_V_ITEMS = frozenset({"p21-origin-table.r1.c0", "p21-end-table.r1.c0",
                               "p22-origin-table.r1.c0", "p22-end-table.r1.c0"})


def _embedded_family(data):
    count = struct.unpack_from(">H", data, 4)[0]
    for index in range(count):
        tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + index * 16)
        if tag == b"name":
            table = data[offset:offset + length]
            _, records, strings = struct.unpack_from(">HHH", table)
            names = []
            for record in range(records):
                platform, _, language, name_id, size, start = struct.unpack_from(">6H", table, 6 + record * 12)
                if name_id == 6:
                    raw = table[strings + start:strings + start + size]
                    names.append((platform == 3, language == 1033,
                                  raw.decode("utf-16-be" if platform in (0, 3) else "latin1")))
            if names:
                return sorted(names, reverse=True)[0][2]
    raise ValueError("Embedded TrueType font has no PostScript family name")


def _characters(page, *, trusted_source=False):
    aliases = []
    for xref, _, _, name, *_ in page.get_fonts(full=True):
        _, extension, _, data = page.parent.extract_font(xref)
        if data and extension == "ttf":
            try:
                family = _embedded_family(data)
            except ValueError:
                if not trusted_source:
                    raise
                # This checksum-pinned original omits its embedded name table.
                # Its PDF BaseFont is the source evidence, never output evidence.
                family = name
        else:
            family = name
        aliases.append((re.sub(r"^[A-Z]{6}\+", "", name), re.sub(r"^[A-Z]{6}\+", "", family)))

    def family(name):
        # PyMuPDF's span name truncates our hash-based PDF aliases at 24 chars.
        name = re.sub(r"^[A-Z]{6}\+", "", name)
        matches = {value for alias, value in aliases if alias.startswith(name)}
        if len(matches) > 1:
            raise ValueError(f"Ambiguous embedded font alias {name}")
        return next(iter(matches)) if matches else name

    return [{**char, "font": family(span["font"]), "size": span["size"], "direction": tuple(line["dir"])}
            for block in page.get_text("rawdict")["blocks"]
            for line in block.get("lines", []) for span in line["spans"]
            for char in span["chars"] if not char["c"].isspace() and char["c"] != "※"]


def _half_point_size(size):
    """Read a size at the library's 0.5 pt step (FR-023): 9.9/9.8 -> 10, 9.058 -> 9, 8.056 -> 8."""
    return math.floor(size * 2 + .5) / 2


def _family(name):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^[A-Z]{6}\+", "", name).lower())


def _ordered(chars, direction):
    return [char for line, _ in _content._ordered_lines(chars, direction) for char in line]


def _rule_centers(page):
    """Black rules: filled narrow rectangles (the original, SideRule) and stroked lines (Table)."""
    result = []
    for drawing in page.get_drawings():
        fill = drawing.get("fill")
        if fill is None or max(fill) > .05 or drawing.get("fill_opacity", 1) < .99:
            continue
        box = drawing["rect"]
        if 0 < box.height <= 2 and box.width > 3:
            result.append((1, (box.y0 + box.y1) / 2, box.x0, box.x1, box.height))
        elif 0 < box.width <= 2 and box.height > 3:
            result.append((0, (box.x0 + box.x1) / 2, box.y0, box.y1, box.width))
    for drawing in page.get_drawings():
        color = drawing.get("color")
        if color is None or max(color) > .01:
            continue
        for item in drawing["items"]:
            if item[0] != "l":
                continue
            (x0, y0), (x1, y1) = item[1:3]
            if abs(y0 - y1) < .001 and abs(x1 - x0) > 3:
                result.append((1, (y0 + y1) / 2, min(x0, x1), max(x0, x1), drawing["width"]))
            elif abs(x0 - x1) < .001 and abs(y1 - y0) > 3:
                result.append((0, (x0 + x1) / 2, min(y0, y1), max(y0, y1), drawing["width"]))
    return result


# The original's rule widths and the border style thickness that replaces each
# (FR-022, FR-027): 0.12 pt hairlines draw as hair 0.25 pt, 0.96 pt rules as
# medium 1.0 pt. The original's own widths are not a tolerance for the output.
_SOURCE_RULE_STYLE_THICKNESS = ((.12, .25), (.96, 1.0))
_SOURCE_RULE_MATCH_PT = .08
_STYLE_THICKNESS_TOLERANCE_PT = .01


def _style_thickness(source_width):
    """Return the border style thickness assigned to a source rule width, or None."""
    for width, thickness in _SOURCE_RULE_STYLE_THICKNESS:
        if abs(source_width - width) <= _SOURCE_RULE_MATCH_PT:
            return thickness
    return None


def _edge_bands(box, rules):
    """For each edge of box: the band (low, high) of the rule ink along it, or None."""
    bands = []
    for index, coordinate in enumerate(box):
        axis = index % 2
        lo, hi = (box[1], box[3]) if axis == 0 else (box[0], box[2])
        candidates = sorted((position - width / 2, position + width / 2)
                            for rule_axis, position, start, end, width in rules
                            if rule_axis == axis and abs(position - coordinate) <= .7
                            and min(hi, end) - max(lo, start) > 2)
        merged = []
        for low, high in candidates:
            if merged and low <= merged[-1][1] + .02:
                merged[-1][1] = max(merged[-1][1], high)
            else:
                merged.append([low, high])
        bands.append(min(merged, key=lambda band: abs(sum(band) / 2 - coordinate)) if merged else None)
    return bands


def _on_grid(value, origin, pitch):
    steps = (value - origin) / pitch
    return abs(steps - round(steps)) * pitch <= _GRID_TOLERANCE_PT


def _swapped(grid):
    return {"pitch_x": grid["pitch_y"], "pitch_y": grid["pitch_x"],
            "columns": grid["rows"], "rows": grid["columns"], "origin_x": 0, "origin_y": 0}


def _rotations(value):
    """Every QuarterTurn record (turns, local_grid) in a trace placement tree."""
    if isinstance(value, dict):
        if "local_grid" in value and "turns" in value:
            yield value
        for child in value.values():
            yield from _rotations(child)
    elif isinstance(value, list):
        for child in value:
            yield from _rotations(child)


def _containers(trace_page):
    """Block IDs of unindented trace nodes that hold child blocks (Stack, Columns).

    Their region starts at their container's left edge, not at their content's;
    an indented container (an Indent around it) starts where it was placed.
    """
    found = set()

    def walk(value):
        if isinstance(value, dict):
            parts = [*value.get("prefix", []), *value.get("parts", [])]
            if (value.get("block_id") and any(part["metadata"].get("children") for part in parts)
                    and not any(part["metadata"].get("indent_pt") for part in parts)):
                found.add(value["block_id"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(trace_page["metadata"]["placements"])
    return found


def _equation_holders(trace_page):
    """Block IDs of the trace nodes that hold equation lines (an EquationGroup, or a Stack of them)."""
    found = set()

    def walk(value):
        holds = False
        if isinstance(value, dict):
            holds = "anchors_pt" in value
            for child in value.values():
                holds = walk(child) or holds
            if holds and value.get("block_id"):
                found.add(value["block_id"])
        elif isinstance(value, list):
            for child in value:
                holds = walk(child) or holds
        return holds
    walk(trace_page["metadata"]["placements"])
    return found


def _equation_lines(trace_page):
    """(block ID, page box, anchors) of every EquationGroup line in a native trace page.

    Walks the placements as verify._trace_regions does (Indent's indent_pt
    included). ``anchors`` holds the line's anchors_pt and its rhs_start_pt
    (as "rhs_start"), pt from the group's left edge, the box's left.
    """
    grid = trace_page["profile"]["grid"]
    found = []

    def walk(node, parent, default_pitch):
        matrix = _content._compose(parent, _content._translation(node.get("x_pt", 0), node.get("y_pt", 0)))
        pitch = node.get("row_pitch", default_pitch)
        parts = [*node.get("prefix", []), *node.get("parts", [])]
        indent = next(iter({part["metadata"].get("indent_pt", 0) for part in parts}), 0)
        for part in parts:
            placed = _content._compose(matrix, _content._translation(indent, part["row"] * pitch))
            metadata = part["metadata"]
            if isinstance(metadata.get("anchors_pt"), dict):
                box = _content._box(placed, 0, 0, node["width"] - indent, part["rows"] * pitch)
                anchors = dict(metadata["anchors_pt"])
                anchors["rhs_start"] = metadata.get("rhs_start_pt")
                # Grid term columns record where the right-hand side ends (FR-025).
                columns = metadata.get("term_columns_pt") or ()
                anchors["rhs_end"] = max((column[0] + column[1] for column in columns), default=None)
                found.append((node.get("block_id", ""), box, anchors))
            for child in metadata.get("children", []):
                walk(child, placed, pitch)
            if "local_to_part" in metadata:
                walk(metadata["child"], _content._compose(placed, metadata["local_to_part"]),
                     metadata["local_grid"]["pitch_y"])

    for placement in trace_page["metadata"]["placements"]:
        origin = _content._translation(grid["origin_x"] + placement["col"] * grid["pitch_x"],
                                       grid["origin_y"] + placement["row"] * grid["pitch_y"])
        walk(placement, origin, grid["pitch_y"])
    return found


def _drawn(page):
    """The output page as drawn: glyphs (spaces excluded, ※ included), straight lines, rectangles.

    A glyph is (char, origin x, origin y, bbox right); a line (x0, y0, x1, y1,
    width, colour, solid); a rectangle (x0, y0, x1, y1, fill).
    """
    glyphs = [(char["c"], char["origin"][0], char["origin"][1], char["bbox"][2])
              for block in page.get_text("rawdict")["blocks"] for line in block.get("lines", [])
              for span in line["spans"] for char in span["chars"] if not char["c"].isspace()]
    lines, rects = [], []
    for drawing in page.get_drawings():
        solid = drawing.get("dashes") in (None, "") or drawing["dashes"].startswith("[]")
        for item in drawing["items"]:
            if item[0] == "l":
                lines.append((item[1].x, item[1].y, item[2].x, item[2].y, drawing.get("width") or 0.0,
                              tuple(drawing.get("color") or ()), solid))
            elif item[0] == "re":
                rects.append((item[1].x0, item[1].y0, item[1].x1, item[1].y1, tuple(drawing.get("fill") or ())))
            else:
                lines.append((None, item[0]))
    return glyphs, lines, rects


def _direction(command):
    return tuple(command.get("direction", (1, 0)))


def _advance(command):
    """A Text command's extent along its direction (its bounds are axis-aligned)."""
    return command["bounds"]["width"] if _direction(command)[0] else command["bounds"]["height"]


def _same_colour(drawn, wanted):
    return len(drawn) == len(wanted) and all(abs(a - b) < .005 for a, b in zip(drawn, wanted))


def _placement(trace_page, page):
    """({rule: checks}, errors): the output page draws exactly its trace's commands, where they put them.

    A Text command's glyphs run along its direction from its origin: the
    first on the origin (unless the text starts with a space) and, for
    horizontal unsheared text not ending in a space, the last ending at the
    origin plus the advance. A Line has its ends, width, colour and dash, a
    Rectangle its box and fill. Every command carries a semantic tag, and
    nothing else is drawn (a debug-grid PDF's grid lines aside; images are
    checked by verify.py).
    """
    glyphs, lines, rects = _drawn(page)
    used_glyphs, used_lines, used_rects = set(), set(), set()
    counts = {"placement.text": 0, "placement.rule": 0, "placement.tag": 0, "placement.grid_lines": 0}
    # A debug-grid PDF draws the page grid's lines under the content (render_pdf(debug_grid=True)).
    grid = trace_page["profile"]["grid"]
    right = grid["origin_x"] + grid["columns"] * grid["pitch_x"]
    bottom = grid["origin_y"] + grid["rows"] * grid["pitch_y"]
    debug = [(x, grid["origin_y"], x, bottom) for x in
             (grid["origin_x"] + column * grid["pitch_x"] for column in range(grid["columns"] + 1))]
    debug += [(grid["origin_x"], y, right, y) for y in
              (grid["origin_y"] + row * grid["pitch_y"] for row in range(grid["rows"] + 1))]
    for index, line in enumerate(lines):
        if (line[0] is not None and abs(line[4] - _DEBUG_GRID_STROKE) < .005 and _same_colour(line[5], _DEBUG_GRID_COLOR)
                and any(all(abs(u - v) < _PLACEMENT_TOLERANCE_PT for u, v in zip(want, line[:4])) for want in debug)):
            used_lines.add(index)
            counts["placement.grid_lines"] += 1
    errors = []
    tolerance = _PLACEMENT_TOLERANCE_PT

    def error(command, detail, **extra):
        errors.append({"category": "placement", "id": f"p{trace_page['page_number']}:{command['index']}",
                       "detail": detail, **extra})

    for command in trace_page["commands"]:
        if command["type"] in ("Text", "Line", "Rectangle"):
            counts["placement.tag"] += 1
            if not (command.get("tag") or {}).get("role"):
                error(command, "command without a semantic tag")
        if command["type"] == "Text":
            text = "".join(c for c in command["text"] if not c.isspace())
            if not text:
                continue
            counts["placement.text"] += 1
            dx, dy = _direction(command)
            ox, oy = command["x"], command["baseline_y"]
            advance = _advance(command)
            found = sorted(((gx - ox) * dx + (gy - oy) * dy, index) for index, (c, gx, gy, _) in enumerate(glyphs)
                           if index not in used_glyphs and abs((gy - oy) * dx - (gx - ox) * dy) < tolerance
                           and -tolerance <= (gx - ox) * dx + (gy - oy) * dy < advance - .05)
            drawn = "".join(glyphs[index][0] for _, index in found)
            starts = not command["text"][0].isspace()
            # Horizontal unsheared text ends at its advance (a sheared glyph's box is not its advance).
            ends = (_direction(command) == (1, 0) and not command.get("shear_x") and not command["text"][-1].isspace()
                    and not command.get("quarter_turns"))
            if (drawn != text or (starts and abs(found[0][0]) > tolerance)
                    or (ends and abs(glyphs[found[-1][1]][3] - (ox + advance)) > tolerance)):
                error(command, "glyphs are not where their layout command put them",
                      actual=drawn, expected=text, origin=[ox, oy])
                continue
            used_glyphs.update(index for _, index in found)
        elif command["type"] == "Line":
            counts["placement.rule"] += 1
            want = (command["x1"], command["y1"], command["x2"], command["y2"])
            solid = not command.get("dash")
            hit = next((index for index, line in enumerate(lines) if index not in used_lines and line[0] is not None
                        and abs(line[4] - command["width"]) < .005 and _same_colour(line[5], command["color"])
                        and line[6] == solid
                        and (all(abs(u - v) < tolerance for u, v in zip(want, line[:4]))
                             or all(abs(u - v) < tolerance for u, v in zip(want, line[2:4] + line[:2])))), None)
            if hit is None:
                error(command, "rule is not where its layout command put it", expected=list(want))
            else:
                used_lines.add(hit)
        elif command["type"] == "Rectangle":
            counts["placement.rule"] += 1
            want = (command["x"], command["y"], command["x"] + command["width"], command["y"] + command["height"])
            fill = tuple(command.get("fill") or ())
            hit = next((index for index, rect in enumerate(rects) if index not in used_rects
                        and all(abs(u - v) < tolerance for u, v in zip(want, rect)) and _same_colour(rect[4], fill)), None)
            if hit is None:
                error(command, "rule is not where its layout command put it", expected=list(want))
            else:
                used_rects.add(hit)
    stray = "".join(glyphs[index][0] for index in range(len(glyphs)) if index not in used_glyphs)
    if stray:
        errors.append({"category": "placement", "id": f"p{trace_page['page_number']}",
                       "detail": "glyphs without a layout command", "actual": stray[:200]})
    extra = len(lines) - len(used_lines) + len(rects) - len(used_rects)
    if extra:
        errors.append({"category": "placement", "id": f"p{trace_page['page_number']}",
                       "detail": "drawings without a layout command", "actual": extra})
    return counts, errors


def _step(command, kind):
    """The index of the command's innermost tag scope of ``kind`` (None without one)."""
    path = (command.get("tag") or {}).get("path", [])
    found = [index for index, step in enumerate(path) if step["kind"] == kind]
    return found[-1] if found else None


def _main_glyphs(command, after):
    """Whether a Text command is set on its line's baseline: full size, outside scripts and fractions."""
    path = command["tag"]["path"][after + 1:]
    return command["style"]["size"] >= 8 and not any(step["kind"] in ("script", "fraction") for step in path)


def _equation_commands(trace_page, box):
    """The page's tagged equation Text commands whose origin lies in an equation line's box."""
    return [command for command in trace_page["commands"] if command["type"] == "Text"
            and _step(command, "equation_line") is not None
            and box[0] - _GRID_TOLERANCE_PT <= command["x"] <= box[2] + _GRID_TOLERANCE_PT
            and box[1] < command["baseline_y"] <= box[3] + _GRID_TOLERANCE_PT]


def _part(command):
    return command["tag"]["path"][_step(command, "equation_part")]


def _extent(commands):
    return (min(c["bounds"]["x"] for c in commands), max(c["bounds"]["x"] + c["bounds"]["width"] for c in commands))


_TERM_ALIGNS = ("left", "right", "center")


def _line_rules(identifier, box, commands, grid):
    """({rule: checks}, errors) of one equation line's tagged parts: labels and grid term columns."""
    errors = []
    counts = {"equals.label": 0, "equals.term": 0}
    pitch = grid["pitch_x"]
    labels = [c for c in commands if _part(c).get("part") == "label"]
    if labels:
        counts["equals.label"] += 1
        start = min(c["x"] for c in labels)
        if abs(start - box[0]) > _GRID_TOLERANCE_PT:
            errors.append({"category": "equals", "id": identifier, "detail": "label does not start at its group's left edge",
                           "actual": start, "expected": box[0]})
    terms = {}
    for command in commands:
        part = _part(command)
        if part.get("part") == "term":
            if "columns" not in part.get("data", {}):
                errors.append({"category": "equals", "id": identifier, "detail": "term without grid columns"})
                continue
            terms.setdefault(part["index"], []).append(command)
    for index, found in sorted(terms.items()):
        counts["equals.term"] += 1
        data = _part(found[0])["data"]
        if data["align"] not in _TERM_ALIGNS:
            raise ValueError(f"{identifier}: unknown term alignment {data['align']!r}")
        low, high = _extent(found)
        left = box[0] + data["first_column"] * pitch
        right = left + data["columns"] * pitch
        padding = data["cell_padding_pt"]
        wanted = {"left": (low, left + padding), "right": (high, right - padding),
                  "center": ((low + high) / 2, (left + right) / 2)}[data["align"]]
        if (abs(wanted[0] - wanted[1]) > _GRID_TOLERANCE_PT or low < left + padding - _GRID_TOLERANCE_PT
                or high > right - padding + _GRID_TOLERANCE_PT):
            errors.append({"category": "equals", "id": identifier, "detail": "term is off its grid columns",
                           "term": index, "actual": [low, high], "expected": [left + padding, right - padding],
                           "align": data["align"]})
    return counts, errors


def _authored_gaps(number):
    """{equations block ID: gap (pt)} as the page's manuscript asks (builder._groups' default 2)."""
    data = json.loads((FIXTURE / f"pages/p{number:02}.json").read_text(encoding="utf-8"))
    gaps = {}

    def walk(blocks):
        for block in blocks:
            if block.get("type") == "equations":
                gaps[block["id"]] = block.get("gap", 2)
            walk(block.get("children", ()))
    walk(data["blocks"])
    return gaps


def _lhs_rules(groups, gaps):
    """({rule: checks}, errors) of the left-hand sides of each EquationGroup's lines.

    EquationGroup ends every left-hand side one gap before the left side of
    the group's widest relation (first_equal - max relation left - gap): so
    each line's ends with its group's, ``gaps[ID]`` before that relation side.
    ``groups`` maps a group ID to its lines' (box, anchors, tagged commands).
    """
    errors, counts = [], {"equals.lhs_gap": 0, "equals.lhs_group": 0}
    for identifier, lines in groups.items():
        gap = gaps.get(re.sub(r"-run\d+$", "", identifier))
        if gap is None:
            raise ValueError(f"{identifier}: no authored equations block")
        sides = [box[0] + anchors["first_equal"] - min(c["x"] for c in commands if _part(c).get("part") == "relation")
                 for box, anchors, commands in lines if anchors.get("first_equal") is not None
                 and any(_part(c).get("part") == "relation" for c in commands)]
        ends = []
        for box, anchors, commands in lines:
            lhs = [c for c in commands if _part(c).get("part") == "lhs"]
            if not lhs:
                continue
            end = _extent(lhs)[1]
            ends.append(end)
            if sides and anchors.get("first_equal") is not None:
                counts["equals.lhs_gap"] += 1
                wanted = box[0] + anchors["first_equal"] - max(sides) - gap
                if abs(end - wanted) > _GRID_TOLERANCE_PT:
                    errors.append({"category": "equals", "id": identifier,
                                   "detail": "left-hand side does not end one gap before its relation",
                                   "actual": end, "expected": wanted})
        for end in ends:
            counts["equals.lhs_group"] += 1
            if abs(end - max(ends)) > _GRID_TOLERANCE_PT:
                errors.append({"category": "equals", "id": identifier,
                               "detail": "left-hand side does not end with its group's", "actual": end,
                               "expected": max(ends)})
    return counts, errors


_PARAGRAPH_ALIGNS = ("left", "center", "right", "justify")


def _paragraph_rules(trace_page, grid):
    """Every line of a left-aligned paragraph or math block (outside equations and tables) starts on a grid column."""
    lines = {}
    for command in trace_page["commands"]:
        if command["type"] != "Text" or _direction(command) != (1, 0) or command.get("quarter_turns"):
            continue
        if _step(command, "table_cell") is not None or _step(command, "equation_line") is not None:
            continue
        block = max((index for index in (_step(command, "paragraph"), _step(command, "math_block")) if index is not None),
                    default=None)
        if block is None or not _main_glyphs(command, block):
            continue
        align = command["tag"]["path"][block].get("data", {}).get("align", "left")
        if align not in _PARAGRAPH_ALIGNS:
            raise ValueError(f"p{trace_page['page_number']}: unknown paragraph alignment {align!r}")
        if align != "left":
            continue
        key = (json.dumps(command["tag"]["path"][:block + 1]), round(command["baseline_y"], 2))
        lines.setdefault(key, []).append(command["x"])
    errors = []
    for (path, baseline), starts in lines.items():
        if not _on_grid(min(starts), grid["origin_x"], grid["pitch_x"]):
            errors.append({"category": "position", "id": f"p{trace_page['page_number']}",
                           "detail": "line does not start on a grid column", "actual": min(starts), "baseline": baseline})
    return {"position.paragraph": len(lines)}, errors


def _side_rule_rules(trace_page, grid):
    """A side rule's bar centres on a grid column line and runs between grid row lines."""
    errors, checks = [], 0
    for command in trace_page["commands"]:
        if command["type"] != "Rectangle" or (command.get("tag") or {}).get("role") != "side_rule":
            continue
        checks += 1
        centre = command["x"] + command["width"] / 2
        if not (_on_grid(centre, grid["origin_x"], grid["pitch_x"]) and _on_grid(command["y"], grid["origin_y"], grid["pitch_y"])
                and _on_grid(command["y"] + command["height"], grid["origin_y"], grid["pitch_y"])):
            errors.append({"category": "position", "id": f"p{trace_page['page_number']}:{command['index']}",
                           "detail": "side rule is off the page grid", "actual": [centre, command["y"], command["height"]]})
    return {"position.side_rule": checks}, errors


def _boundary_rules(trace_page):
    """{table ID: {(orientation, boundary): thickness}}: the widest drawn rule on each table boundary."""
    found = {}
    for command in trace_page["commands"]:
        tag = command.get("tag") or {}
        if command["type"] != "Line" or tag.get("role") != "table_border":
            continue
        table = tag["path"][_step(command, "table")]["data"]["block_id"]
        key = (tag["data"]["orientation"], tag["data"]["boundary"])
        rules = found.setdefault(table, {})
        rules[key] = max(rules.get(key, 0.0), command["width"])
    return found


def _top_aligned_rules(key, record, along, n, across, pad_top, pad_bottom, baselines, counts, error):
    """The rules of a top-aligned cell's lines (every multi-line cell, FR-027).

    Each line's glyph boxes lie inside one grid row (on p30-p37 a local row,
    a page column), the lines in consecutive rows, all at one baseline offset
    in their rows (a line without a full-size baseline, p21/p22's turned
    parentheses, is centred on that baseline's em box like the cell's other
    glyphs). The rows and the offset are the ones builder._row_placement
    picks, rebuilt from the glyph boxes: the first rows nearest the cell's
    middle (ties upward) where every line keeps inside its row and the end
    lines clear of the cell's rules, and the middle of the offsets that fit.
    """
    pitch = record["pitch"]
    total = round((across[1] - across[0]) / pitch)
    lines = sorted(record["lines"].items())
    count = lines[-1][0] + 1
    if [index for index, _ in lines] != list(range(count)):
        error(key, "cell line missing", actual=[index for index, _ in lines])
        return
    if count == 1:
        error(key, "a one-line cell is not centred in its whole cell")
        return
    boxes = {index: (min(along(c, n)[0] for c, _, _ in found) - across[0],
                     max(along(c, n)[1] for c, _, _ in found) - across[0]) for index, found in lines}
    first = math.floor(boxes[0][0] / pitch + 1e-9) if 0 in boxes else None
    for index, (lo, hi) in boxes.items():
        counts["table.cell_rows"] += 1
        row = math.floor(lo / pitch + 1e-9)
        if first is None or math.floor(hi / pitch - 1e-9) != row or row != first + index:
            error(key, "cell line is not inside its own grid row", line=index, actual=[lo, hi])
            return
    offsets = {index: baselines[index] - across[0] - (first + index) * pitch for index in boxes if index in baselines}
    if not offsets:
        error(key, "cell lines without a baseline")
        return
    offset = offsets[min(offsets)]
    counts["table.cell_room"] += 1
    if max(abs(value - offset) for value in offsets.values()) > _GRID_TOLERANCE_PT:
        error(key, "cell lines are not at one offset in their rows", actual=list(offsets.values()))
        return
    # The em box centre of the cell's full-size glyphs, from their baseline (a turned parenthesis is
    # drawn centred on it, appearance.VerticalGlyph).
    centres = [(lo + hi) / 2 - (first + index) * pitch - offset for index, (lo, hi) in boxes.items() if index in offsets]
    for index, (lo, hi) in boxes.items():
        if index in offsets:
            continue
        counts["table.cell_turned"] += 1
        centre = (lo + hi) / 2 - (first + index) * pitch - offset
        if max(centres) - min(centres) > _GRID_TOLERANCE_PT or abs(centre - centres[0]) > _GRID_TOLERANCE_PT:
            error(key, "cell line without a baseline is off its row's em box", line=index, actual=centre,
                  expected=centres)
    # Ascent and descent of each line from the shared baseline, as builder._row_placement reads them.
    reach = {index: (offset + (first + index) * pitch - lo, hi - offset - (first + index) * pitch)
             for index, (lo, hi) in boxes.items()}
    wanted = None
    for start in sorted(range(total - count + 1), key=lambda start: (abs(start - (total - count) / 2), start)):
        low = max([up for up, _ in reach.values()] + ([reach[0][0] + pad_top + _STROKE_MARGIN_PT] if start == 0 else []))
        high = min([pitch - down for _, down in reach.values()]
                   + ([pitch - reach[count - 1][1] - pad_bottom - _STROKE_MARGIN_PT] if start + count == total else []))
        if low <= high + 1e-9:
            wanted = (start, (low + high) / 2)
            break
    counts["table.cell_centre"] += 1
    if wanted is None:
        error(key, "cell lines do not fit their rows and rules")
    elif first != wanted[0]:
        error(key, "cell lines are not centred in their cell by whole rows", actual=first, expected=wanted[0])
    elif abs(offset - wanted[1]) > _GRID_TOLERANCE_PT:
        error(key, "cell lines are not in the middle of the room in their rows", actual=offset, expected=wanted[1])


_CELL_ALIGNS = ("left", "right", "center")
_CELL_VALIGNS = ("top", "middle")


def _cell_rules(trace_page, regions, grid, chars):
    """({rule: checks}, errors) of the table cells' lines.

    CellLines pads a cell by its boundary rules (top and bottom: the rule's
    thickness; left and right: 2 pt plus the rule's): a line sits at that
    padding at its alignment (centred: off the cell's centre by half the
    difference of its sides' padding); the lines step one row pitch; the
    lines together centre between the top and bottom padding of a
    middle-aligned cell (every one-line cell) and stay inside it; a
    top-aligned one (every multi-line cell, ``first_baseline``) follows
    ``_top_aligned_rules``. A cell with text in the PDF must have tagged
    cell lines.
    """
    cells = {}
    for command in trace_page["commands"]:
        if command["type"] != "Text":
            continue
        cell_step, line_step = _step(command, "table_cell"), _step(command, "cell_lines")
        if cell_step is None or line_step is None:
            continue
        path = command["tag"]["path"]
        table = path[_step(command, "table")]["data"]["block_id"]
        cell = path[cell_step]["data"]
        turn = _step(command, "quarter_turn")
        pitch = path[turn]["data"]["local_grid"]["pitch_y"] if turn is not None else grid["pitch_y"]
        key = f"{table}.r{cell['row']}.c{cell['col']}"
        record = cells.setdefault(key, {"table": table, "cell": cell, "pitch": pitch, "lines": {},
                                        "turned": turn is not None})
        record["lines"].setdefault(path[line_step]["index"], []).append((command, path[line_step]["data"]["align"], line_step))
    boundaries = _boundary_rules(trace_page)
    errors = []
    counts = {name: 0 for name in ("table.cell_align", "table.cell_baseline", "table.cell_spacing",
                                   "table.cell_rows", "table.cell_room", "table.cell_turned", "table.cell_centre",
                                   "table.cell_coverage")}

    def error(key, detail, **extra):
        errors.append({"category": "table", "id": key, "detail": detail, **extra})

    for key, record in cells.items():
        box = regions[key]
        cell = record["cell"]
        if cell["valign"] not in _CELL_VALIGNS:
            raise ValueError(f"{key}: unknown cell vertical alignment {cell['valign']!r}")
        rules = boundaries.get(record["table"], {})
        pad_top = rules.get(("horizontal", cell["row"]), 0.0)
        pad_bottom = rules.get(("horizontal", cell["row"] + cell["rowspan"]), 0.0)
        pad_left = _CELL_PADDING_PT + rules.get(("vertical", cell["col"]), 0.0)
        pad_right = _CELL_PADDING_PT + rules.get(("vertical", cell["col"] + cell["colspan"]), 0.0)
        # The cell's text runs along -y in a rotated table and along x otherwise; its lines step across.
        d = (0, -1) if record["turned"] else (1, 0)
        n = (-d[1], d[0])

        def along(command, vector):
            """The command's bounds as an interval along ``vector``."""
            bounds = command["bounds"]
            values = [x * vector[0] + y * vector[1] for x in (bounds["x"], bounds["x"] + bounds["width"])
                      for y in (bounds["y"], bounds["y"] + bounds["height"])]
            return min(values), max(values)

        corners = [(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
        span = (min(x * d[0] + y * d[1] for x, y in corners), max(x * d[0] + y * d[1] for x, y in corners))
        across = (min(x * n[0] + y * n[1] for x, y in corners), max(x * n[0] + y * n[1] for x, y in corners))
        baselines = {}
        for index, found in sorted(record["lines"].items()):
            low = min(along(c, d)[0] for c, _, _ in found)
            high = max(along(c, d)[1] for c, _, _ in found)
            counts["table.cell_align"] += 1
            align = found[0][1]
            if align not in _CELL_ALIGNS:
                raise ValueError(f"{key}: unknown cell line alignment {align!r}")
            wanted = {"left": (low, span[0] + pad_left), "right": (high, span[1] - pad_right),
                      "center": ((low + high) / 2, (span[0] + pad_left + span[1] - pad_right) / 2)}[align]
            if not (span[0] - _GRID_TOLERANCE_PT <= low and high <= span[1] + _GRID_TOLERANCE_PT):
                error(key, "cell text leaves its cell", line=index, actual=[low, high], expected=list(span))
            elif abs(wanted[0] - wanted[1]) > _GRID_TOLERANCE_PT:
                error(key, f"cell line is not {'centred' if align == 'center' else 'aligned ' + align} in its padding",
                      line=index, actual=wanted[0], expected=wanted[1])
            main = {round(c["x"] * n[0] + c["baseline_y"] * n[1], 3) for c, _, step in found
                    if _direction(c) == d and _main_glyphs(c, step)}
            if main:
                counts["table.cell_baseline"] += 1
                if max(main) - min(main) > _GRID_TOLERANCE_PT:
                    error(key, "cell line leaves its baseline", line=index)
                baselines[index] = min(main)
        ordered = sorted(baselines.items())
        for (first, a), (second, b) in zip(ordered, ordered[1:]):
            counts["table.cell_spacing"] += 1
            if abs(b - a - (second - first) * record["pitch"]) > _GRID_TOLERANCE_PT:
                error(key, "cell line is off its rows", line=second, actual=b - a,
                      expected=(second - first) * record["pitch"])
        commands = [c for found in record["lines"].values() for c, _, _ in found]
        low = min(along(c, n)[0] for c in commands)
        high = max(along(c, n)[1] for c in commands)
        if cell["valign"] == "middle":
            # A one-line cell stays centred in its whole cell (the grid Excel merges it over its
            # range, lead 2026-10-20): inside the cell, centred between its top and bottom padding.
            counts["table.cell_centre"] += 1
            if len(record["lines"]) != 1:
                error(key, "a multi-line cell is not set row by row", actual=len(record["lines"]))
            if low < across[0] - _GRID_TOLERANCE_PT or high > across[1] + _GRID_TOLERANCE_PT:
                error(key, "cell text leaves its cell across its lines", actual=[low, high], expected=list(across))
            centre = (across[0] + pad_top + across[1] - pad_bottom) / 2
            if abs((low + high) / 2 - centre) > _GRID_TOLERANCE_PT:
                error(key, "cell lines are not centred between their cell's top and bottom",
                      actual=(low + high) / 2, expected=centre)
        else:
            _top_aligned_rules(key, record, along, n, across, pad_top, pad_bottom, baselines, counts, error)
    # A cell with text in the PDF has tagged cell lines (a rule cannot pass by checking nothing).
    for key, box in regions.items():
        if key in cells or not re.search(r"\.r\d+\.c\d+$", key):
            continue
        counts["table.cell_coverage"] += 1
        if _content._inside(chars, box):
            error(key, "cell text without tagged cell lines")
    return counts, errors


def appearance_report(path, *, source_pages, trace, categories=None):
    """Return all mismatches so a failed full-page repair is diagnosable.

    ``categories`` selects among ``CATEGORIES``; content and reading order
    are always checked. The grid categories need a native layout trace;
    without one (an ``oracle_regions`` control) only ``font`` is checked.
    """
    selected = tuple(source_pages)
    if not selected or selected != tuple(sorted(set(selected))) or any(type(n) is not int or not 1 <= n <= 37 for n in selected):
        raise ValueError("source_pages must be unique increasing pages in 1..37")
    if isinstance(trace, (str, Path)):
        trace = json.loads(Path(trace).read_text(encoding="utf-8"))
    native = "pages" in trace
    enabled = set(categories or (CATEGORIES if native else SOURCE_CATEGORIES))
    if not enabled <= set(CATEGORIES):
        raise ValueError("unknown appearance category")
    if not native and enabled & set(GRID_CATEGORIES):
        raise ValueError("grid categories need a native layout trace")
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    source_path = ROOT / manifest["source"]["path"]
    if sha256(source_path.read_bytes()).hexdigest() != manifest["source"]["sha256"]:
        raise ValueError("original source PDF hash changed")
    errors, counts, maxima = [], {name: 0 for name in enabled}, {}
    # Checks per rule (category.rule), so a rule that checks nothing shows as 0.
    rules = {}

    def add(found):
        checks, found_errors = found
        for name, value in checks.items():
            rules[name] = rules.get(name, 0) + value
            counts[name.split(".")[0]] += value
        errors.extend(found_errors)

    def compare(category, identifier, actual, expected, tolerance, detail):
        counts[category] += 1
        delta = abs(actual - expected)
        maxima[category] = max(maxima.get(category, 0), delta)
        if delta > tolerance:
            errors.append({"category": category, "id": identifier, "detail": detail,
                           "actual": actual, "expected": expected, "delta": delta, "tolerance": tolerance})

    def on_grid(category, identifier, value, origin, pitch, detail):
        counts[category] += 1
        if not _on_grid(value, origin, pitch):
            errors.append({"category": category, "id": identifier, "detail": detail + " is off the page grid",
                           "actual": value, "origin": origin, "pitch": pitch})

    with pymupdf.open(source_path) as source, pymupdf.open(path) as output:
        if len(output) != len(selected) and path != source_path:
            raise ValueError("appearance output page count mismatch")
        for index, number in enumerate(selected):
            reference_page = source[number - 1]
            actual_page = output[number - 1] if Path(path).resolve() == source_path.resolve() else output[index]
            trusted = Path(path).resolve() == source_path.resolve()
            wanted_chars = _characters(reference_page, trusted_source=True)
            actual_chars = _characters(actual_page, trusted_source=trusted)
            expected = json.loads((FIXTURE / f"expected/p{number:02}.json").read_text(encoding="utf-8"))
            if native:
                trace_page = trace["pages"][index]
                regions, spans = _content._trace_regions(trace_page)
                grid = trace_page["profile"]["grid"]
                containers = _containers(trace_page)
                equation_blocks = _equation_holders(trace_page)
            else:
                regions, spans, grid = trace["oracle_regions"][index], {}, None
            source_rules = _rule_centers(reference_page)
            actual_rules = _rule_centers(actual_page)
            lefts = []
            for block in expected["blocks"]:
                table = block["kind"] == "table"
                for item in block["cells"] if table else (block,):
                    key, direction = item["id"], tuple(item["direction"])
                    if key not in regions:
                        errors.append({"category": "region", "id": key, "detail": "missing output region"})
                        continue
                    actual = _ordered(_content._inside(actual_chars, regions[key]), direction)
                    wanted = _ordered(_content._inside(wanted_chars, item["source_bbox"]), direction)
                    if "".join(c["c"] for c in actual) != "".join(c["c"] for c in wanted):
                        errors.append({"category": "content", "id": key, "detail": "semantic text mismatch"})
                        continue
                    actual_lines = _content._ordered_lines(actual, direction)
                    source_lines = _content._ordered_lines(wanted, direction)
                    if bool(item.get("source_direction_overrides")) != (key in _IDENTITY_V_ITEMS):
                        errors.append({"category": "content", "id": key,
                                       "detail": "direction overrides outside the known Identity-V items"})
                    if (key not in _IDENTITY_V_ITEMS
                            and [len(line) for line, _ in actual_lines] != [len(line) for line, _ in source_lines]):
                        errors.append({"category": "content", "id": key, "detail": "source line structure",
                                       "actual": [len(line) for line, _ in actual_lines],
                                       "expected": [len(line) for line, _ in source_lines]})
                    if "font" in enabled:
                        for char_index, (a, w) in enumerate(zip(actual, wanted)):
                            counts["font"] += 1
                            if _family(a["font"]) != _family(w["font"]):
                                errors.append({"category": "font", "id": key, "character_index": char_index,
                                               "actual": a["font"], "expected": w["font"], "detail": "font family"})
                            if any(abs(v - u) > .001 for v, u in zip(a["direction"], w["direction"])):
                                errors.append({"category": "font", "id": key, "character_index": char_index,
                                               "actual": a["direction"], "expected": w["direction"], "detail": "glyph direction"})
                            # Forward glyph extent reveals synthetic italic while
                            # avoiding the original subset's clamped left bbox.
                            # Identity-V punctuation has a different origin
                            # convention, so compare its full inline extent.
                            axis = 0 if abs(w["direction"][0]) > .5 else 1

                            def inline_extent(char):
                                if axis == 0:
                                    return (char["bbox"][2] - char["origin"][0] if w["direction"][0] > 0
                                            else char["origin"][0] - char["bbox"][0])
                                return char["bbox"][3] - char["bbox"][1]
                            compare("font", key, inline_extent(a), inline_extent(w), .20, "glyph inline extent")
                            if a["size"] >= 8 and w["size"] >= 8:
                                # FR-023/FR-027: the original's size is read at its 0.5 pt
                                # step. Output sizes are compared unrounded; the original
                                # compared with itself (positive control) is read the same way.
                                actual_size = _half_point_size(a["size"]) if trusted else a["size"]
                                compare("font", key, actual_size, _half_point_size(w["size"]), .02,
                                        "body size (0.5 pt step)")
                    if grid is None:
                        continue
                    box = regions[key]
                    if "position" in enabled:
                        edges = (0, 1, 2, 3) if key in spans else (0, 1)
                        for edge in edges:
                            axis = edge % 2
                            on_grid("position", key, box[edge], grid["origin_y" if axis else "origin_x"],
                                    grid["pitch_y" if axis else "pitch_x"], ("left", "top", "right", "bottom")[edge])
                        if not table and actual and direction == (1, 0):
                            # A block's left edge is its region's (an EquationGroup sets its left-hand
                            # side against its first relation); a container's is its first glyph's.
                            left = min(c["bbox"][0] for c in actual) if key in containers else box[0]
                            lefts.append((key, min(c["bbox"][0] for c in wanted), left))
                        # A library line sets its full-size glyphs on one baseline, without overlapping
                        # advances; a plain text block's lines start at the block's left edge.
                        dx, dy = direction
                        plain = (not table and key not in containers and key not in equation_blocks
                                 and direction == (1, 0) and key not in _IDENTITY_V_ITEMS)
                        for line_index, (line, _) in enumerate(actual_lines):
                            inline = sorted((c for c in line if tuple(c["direction"]) == direction),
                                            key=lambda c: dx * c["origin"][0] + dy * c["origin"][1])
                            for a, b in zip(inline, inline[1:]):
                                if abs(a["size"] - b["size"]) > .01:
                                    continue  # a script beside its base (a sheared base's extracted box is wider)
                                counts["position"] += 1
                                ends = (a["bbox"][2], b["bbox"][0]) if dx else ((a["bbox"][3], b["bbox"][1]) if dy > 0
                                                                                else (b["bbox"][3], a["bbox"][1]))
                                if dx < 0 or ends[0] - ends[1] > _GRID_TOLERANCE_PT:
                                    errors.append({"category": "position", "id": key,
                                                   "detail": f"line {line_index} glyphs overlap",
                                                   "actual": [a["c"], b["c"]]})
                            if plain and line:
                                counts["position"] += 1
                                if abs(min(c["bbox"][0] for c in line) - box[0]) > _GRID_TOLERANCE_PT:
                                    errors.append({"category": "position", "id": key,
                                                   "detail": f"line {line_index} does not start at its block's left edge",
                                                   "actual": min(c["bbox"][0] for c in line), "expected": box[0]})
                            origins = [-dy * c["origin"][0] + dx * c["origin"][1] for c in line
                                       if c["size"] >= 8 and tuple(c["direction"]) == direction]
                            if origins:
                                counts["position"] += 1
                                if max(origins) - min(origins) > _GRID_TOLERANCE_PT:
                                    errors.append({"category": "position", "id": key,
                                                   "detail": f"line {line_index} glyphs leave its baseline",
                                                   "actual": max(origins) - min(origins)})
                    if table and "table" in enabled:
                        source_bands = _edge_bands(item["source_bbox"], source_rules)
                        output_bands = _edge_bands(box, actual_rules)
                        for edge, (band, source_band) in enumerate(zip(output_bands, source_bands)):
                            label = ("left", "top", "right", "bottom")[edge]
                            if source_band is None:
                                continue
                            if band is None:
                                errors.append({"category": "table", "id": key, "detail": label + " original rule is absent"})
                                continue
                            counts["table"] += 1
                            # The cell edge lies on the grid (position) and inside its rule's ink.
                            if not band[0] - _GRID_TOLERANCE_PT <= box[edge] <= band[1] + _GRID_TOLERANCE_PT:
                                errors.append({"category": "table", "id": key, "detail": label + " rule is off the cell edge",
                                               "actual": band, "expected": box[edge]})
                            width = source_band[1] - source_band[0]
                            style = width if trusted else _style_thickness(width)
                            if style is None:
                                errors.append({"category": "table", "id": key,
                                               "detail": label + " original rule width has no border style",
                                               "actual": band[1] - band[0], "expected": width})
                            else:
                                compare("table", key, band[1] - band[0], style, _STYLE_THICKNESS_TOLERANCE_PT,
                                        label + " rule thickness (border style)")
            if grid is not None:
                trace_page = trace["pages"][index]
                if "placement" in enabled:
                    add(_placement(trace_page, actual_page))
                if "position" in enabled:
                    add(_paragraph_rules(trace_page, grid))
                    add(_side_rule_rules(trace_page, grid))
                if "table" in enabled:
                    add(_cell_rules(trace_page, regions, grid, actual_chars))
            if "position" in enabled:
                # The original's indentation levels keep their order on the grid columns.
                for key_a, source_a, output_a in lefts:
                    for key_b, source_b, output_b in lefts:
                        if source_a + _INDENT_LEVEL_PT < source_b:
                            counts["position"] += 1
                            if not output_a < output_b:
                                errors.append({"category": "position", "id": key_b,
                                               "detail": f"indent is not right of {key_a}",
                                               "actual": output_b, "expected": output_a})
            if grid is not None and "equals" in enabled:
                # Every EquationGroup line records its anchors (pt from the group's left edge, which
                # "position" puts on the grid): equals, result end and unit start are whole columns.
                groups = {}
                for identifier, line_box, anchors in _equation_lines(trace["pages"][index]):
                    # The line's tagged commands ("placement" ties them to the PDF): labels at the
                    # group's left edge, terms in their grid columns, left-hand sides ending together.
                    tagged = _equation_commands(trace["pages"][index], line_box)
                    rules["equals.coverage"] = rules.get("equals.coverage", 0) + 1
                    if not tagged and _content._inside(actual_chars, line_box):
                        errors.append({"category": "equals", "id": identifier,
                                       "detail": "equation line without tagged commands"})
                    add(_line_rules(identifier, line_box, tagged, grid))
                    groups.setdefault(identifier, []).append((line_box, anchors, tagged))
                    has_result = any(_part(command).get("part") == "result" for command in tagged)
                    for name, value in ((name, value) for name, value in anchors.items()
                                        if value is not None and name not in ("rhs_start", "rhs_end")):
                        counts["equals"] += 1
                        steps = value / grid["pitch_x"]
                        if abs(steps - round(steps)) * grid["pitch_x"] > _GRID_TOLERANCE_PT:
                            errors.append({"category": "equals", "id": identifier, "detail": f"{name} anchor is off the grid",
                                           "actual": value, "pitch": grid["pitch_x"]})
                    line = [c for c in _ordered(_content._inside(actual_chars, line_box), (1, 0)) if c["size"] >= 8]
                    relations = []
                    for position, char in enumerate(line):
                        if char["c"] in "=＝":
                            following = line[position + 1] if position + 1 < len(line) else None
                            right = following["bbox"][2] if following is not None and following["c"] == "±" else char["bbox"][2]
                            relations.append((char["bbox"][0] + right) / 2)

                    def relation_at(centre, name):
                        counts["equals"] += 1
                        target = line_box[0] + anchors[name]
                        if abs(centre - target) > _GRID_TOLERANCE_PT:
                            errors.append({"category": "equals", "id": identifier, "detail": "relation is off its anchors",
                                           "anchor": name, "actual": centre, "expected": target})
                    # Left of the right-hand side, an equals can only be the first relation;
                    # equals inside the right-hand side are its content.
                    rhs_start = line_box[0] + anchors["rhs_start"] if anchors.get("rhs_start") is not None else None
                    before = [centre for centre in relations if rhs_start is not None and centre < rhs_start]
                    if before and anchors.get("first_equal") is None:
                        errors.append({"category": "equals", "id": identifier, "detail": "relation is off its anchors",
                                       "actual": before})
                    for centre in before if anchors.get("first_equal") is not None else ():
                        relation_at(centre, "first_equal")
                    # Right of the second relation come the result, ending on result_right, and the
                    # unit, starting on unit_start.
                    if anchors.get("second_equal") is None:
                        content = [(c["bbox"][0] + c["bbox"][2]) / 2 for c in line if c["c"] not in "=＝±"
                                   and rhs_start is not None and (c["bbox"][0] + c["bbox"][2]) / 2 >= rhs_start]
                        for centre in (centre for centre in relations if rhs_start is not None and centre >= rhs_start):
                            counts["equals"] += 1
                            if not (any(other < centre for other in content) and any(other > centre for other in content)):
                                errors.append({"category": "equals", "id": identifier,
                                               "detail": "relation is off its anchors", "actual": centre})
                        continue
                    second = line_box[0] + anchors["second_equal"]
                    # A right-hand side that runs across the second relation's column (an equation
                    # without a result takes the full width) leaves no result on this line; on a
                    # line with a result nothing may cross it.
                    if any(c["bbox"][0] < second < c["bbox"][2] for c in line if c["c"] not in "=＝±"):
                        counts["equals"] += 1
                        if has_result:
                            errors.append({"category": "equals", "id": identifier,
                                           "detail": "a glyph runs across the second relation", "actual": second})
                        continue
                    unit_start = line_box[0] + anchors["unit_start"] if anchors.get("unit_start") is not None else None
                    rhs_end = line_box[0] + anchors["rhs_end"] if anchors.get("rhs_end") is not None else second
                    tail = [c for c in line if (c["bbox"][0] + c["bbox"][2]) / 2 > max(second, rhs_end) + _GRID_TOLERANCE_PT
                            and c["c"] not in "=＝±"]
                    unit = [c for c in tail if unit_start is not None and c["origin"][0] >= unit_start - _GRID_TOLERANCE_PT]
                    result = [c for c in tail if c not in unit]
                    # On a line with a result, the rightmost equals right of the right-hand side's
                    # start is the second relation (a blank second relation leaves none there).
                    after = [centre for centre in relations if rhs_start is None or centre >= rhs_start]
                    if result and after:
                        relation_at(after[-1], "second_equal")
                        after = after[:-1]
                    # Any other equals is the right-hand side's own content, between its glyphs.
                    content = [(c["bbox"][0] + c["bbox"][2]) / 2 for c in line if c["c"] not in "=＝±"
                               and (rhs_start is None or (c["bbox"][0] + c["bbox"][2]) / 2 >= rhs_start)
                               and (c["bbox"][0] + c["bbox"][2]) / 2 < second]
                    for centre in after:
                        counts["equals"] += 1
                        if not (any(other < centre for other in content) and any(other > centre for other in content)):
                            errors.append({"category": "equals", "id": identifier, "detail": "relation is off its anchors",
                                           "actual": centre})
                    if result:
                        counts["equals"] += 1
                        end = max(c["bbox"][2] for c in result)
                        if abs(end - (line_box[0] + anchors["result_right"])) > _GRID_TOLERANCE_PT:
                            errors.append({"category": "equals", "id": identifier,
                                           "detail": "result_right anchor is not the result's end",
                                           "actual": end, "expected": line_box[0] + anchors["result_right"]})
                    if unit:
                        counts["equals"] += 1
                        start = min(c["origin"][0] for c in unit)
                        if abs(start - unit_start) > _GRID_TOLERANCE_PT:
                            errors.append({"category": "equals", "id": identifier,
                                           "detail": "unit_start anchor is not the unit's start",
                                           "actual": start, "expected": unit_start})
                add(_lhs_rules(groups, _authored_gaps(number)))
            if grid is not None and "rotation" in enabled:
                turned = [item for block in expected["blocks"] for item in block.get("cells", [block])
                          if tuple(item["direction"]) not in ((1, 0),) and not item.get("source_direction_overrides")]
                records = list(_rotations(trace["pages"][index]["metadata"]["placements"]))
                counts["rotation"] += 1
                if turned and not records:
                    errors.append({"category": "rotation", "id": f"p{number:02}", "detail": "rotated items without a rotation"})
                for record in records:
                    counts["rotation"] += 1
                    if record["turns"] != 1:
                        errors.append({"category": "rotation", "id": f"p{number:02}", "detail": "rotation is not +1",
                                       "actual": record["turns"]})
                    local = {name: record["local_grid"][name] for name in _swapped(grid)}
                    if local != _swapped(grid):
                        errors.append({"category": "rotation", "id": f"p{number:02}",
                                       "detail": "local grid is not the swapped page grid",
                                       "actual": local, "expected": _swapped(grid)})
    return {"source_pages": list(selected), "checks": counts, "rule_checks": rules, "max_delta_pt": maxima,
            "error_count": len(errors), "errors": errors,
            "source_sha256": manifest["source"]["sha256"]}


def verify_appearance(path, *, source_pages, trace):
    report = appearance_report(path, source_pages=source_pages, trace=trace)
    if report["errors"]:
        sample = json.dumps(report["errors"][:8], ensure_ascii=False)
        raise ValueError(f"原本の外観不一致: {report['error_count']} differences; {sample}")
    return {key: value for key, value in report.items() if key != "errors"}
