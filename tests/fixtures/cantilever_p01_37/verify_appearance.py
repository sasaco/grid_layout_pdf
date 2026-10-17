"""Compare native output appearance directly with the original PDF.

Authored layout/font profiles are deliberately not imported. The content oracle
supplies semantic regions; fonts, origins, equals and rule centers are read from
the two PDFs. A self-generated golden is not source appearance evidence.
"""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import struct

import pymupdf


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent
_spec = importlib.util.spec_from_file_location("cantilever_content_appearance", FIXTURE / "verify.py")
_content = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_content)


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


def _family(name):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^[A-Z]{6}\+", "", name).lower())


def _ordered(chars, direction):
    return [char for line, _ in _content._ordered_lines(chars, direction) for char in line]


def _rule_centers(page):
    """Original black rules are filled narrow rectangles, not PDF strokes."""
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


def _edge_evidence(box, rules):
    refined = [(value, None) for value in box]
    for index, coordinate in enumerate(box):
        axis = index % 2
        lo, hi = (box[1], box[3]) if axis == 0 else (box[0], box[2])
        candidates = [(position - width / 2, position + width / 2)
                      for rule_axis, position, start, end, width in rules
                      if rule_axis == axis and abs(position - coordinate) <= .7
                      and min(hi, end) - max(lo, start) > 2]
        if candidates:
            bands = []
            for low, high in sorted(candidates):
                if bands and low <= bands[-1][1] + .02:
                    bands[-1][1] = max(bands[-1][1], high)
                else:
                    bands.append([low, high])
            low, high = min(bands, key=lambda band: abs(sum(band) / 2 - coordinate))
            refined[index] = ((low + high) / 2, high - low)
    return refined


def appearance_report(path, *, source_pages, trace, categories=None):
    """Return all mismatches so a failed full-page repair is diagnosable."""
    selected = tuple(source_pages)
    if not selected or selected != tuple(sorted(set(selected))) or any(type(n) is not int or not 1 <= n <= 37 for n in selected):
        raise ValueError("source_pages must be unique increasing pages in 1..37")
    if isinstance(trace, (str, Path)):
        trace = json.loads(Path(trace).read_text(encoding="utf-8"))
    enabled = set(categories or ("font", "indent", "equals", "table", "spacing", "baseline"))
    if not enabled <= {"font", "indent", "equals", "table", "spacing", "baseline"}:
        raise ValueError("unknown appearance category")
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    source_path = ROOT / manifest["source"]["path"]
    if sha256(source_path.read_bytes()).hexdigest() != manifest["source"]["sha256"]:
        raise ValueError("original source PDF hash changed")
    errors, counts, maxima = [], {name: 0 for name in enabled}, {}

    def compare(category, identifier, actual, expected, tolerance, detail):
        counts[category] += 1
        delta = abs(actual - expected)
        maxima[category] = max(maxima.get(category, 0), delta)
        if delta > tolerance:
            errors.append({"category": category, "id": identifier, "detail": detail,
                           "actual": actual, "expected": expected, "delta": delta, "tolerance": tolerance})

    with pymupdf.open(source_path) as source, pymupdf.open(path) as output:
        if len(output) != len(selected) and path != source_path:
            raise ValueError("appearance output page count mismatch")
        for index, number in enumerate(selected):
            reference_page = source[number - 1]
            actual_page = output[number - 1] if Path(path).resolve() == source_path.resolve() else output[index]
            wanted_chars = _characters(reference_page, trusted_source=True)
            actual_chars = _characters(actual_page, trusted_source=Path(path).resolve() == source_path.resolve())
            expected = json.loads((FIXTURE / f"expected/p{number:02}.json").read_text(encoding="utf-8"))
            regions = (_content._trace_regions(trace["pages"][index])[0] if "pages" in trace
                       else trace["oracle_regions"][index])
            source_rules = _rule_centers(reference_page)
            actual_rules = _rule_centers(actual_page)
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
                    if "baseline" in enabled:
                        for char_index, (a, w) in enumerate(zip(actual, wanted)):
                            # These eight original Identity-V parentheses have
                            # origins that differ from a rotated horizontal
                            # glyph. Their actual ink is compared at 8x scale in
                            # test_vertical_parenthesis_visible_ink_matches_original,
                            # with positive and displaced controls for all eight.
                            identity_v_parenthesis = (
                                key in {"p21-origin-table.r1.c0", "p21-end-table.r1.c0",
                                        "p22-origin-table.r1.c0", "p22-end-table.r1.c0"}
                                and w["c"] in ("（", "）")
                                and w["direction"] == (0.0, 1.0) and direction == (1, 0))
                            if identity_v_parenthesis:
                                continue
                            dx, dy = w["direction"]
                            compare("baseline", key,
                                    -dy * a["origin"][0] + dx * a["origin"][1],
                                    -dy * w["origin"][0] + dx * w["origin"][1], .20,
                                    f"character {char_index} perpendicular origin")
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
                                compare("font", key, a["size"], w["size"], .16, "body size")
                    if actual and not table and "indent" in enabled:
                        actual_lines = _content._ordered_lines(actual, direction)
                        source_lines = _content._ordered_lines(wanted, direction)
                        if len(actual_lines) != len(source_lines):
                            errors.append({"category": "indent", "id": key, "detail": "source line count",
                                           "actual": len(actual_lines), "expected": len(source_lines)})
                        for line_index, ((line, _), (source_line, _)) in enumerate(zip(actual_lines, source_lines)):
                            compare("indent", key, line[0]["origin"][0], source_line[0]["origin"][0], .25,
                                    f"line {line_index} first visible origin x")
                    if not table and "equals" in enabled:
                        for a, w in zip(actual, wanted):
                            if w["c"] in "=＝":
                                compare("equals", key, (a["bbox"][0] + a["bbox"][2]) / 2,
                                        (w["bbox"][0] + w["bbox"][2]) / 2, .20, "equals center x")
                    if "spacing" in enabled:
                        for a, w in zip(actual, wanted):
                            axis = 0 if abs(w["direction"][0]) > .5 else 1
                            if tuple(w["direction"]) == direction:
                                # A generous whole-run guard catches displaced
                                # operands/labels missed by relation-only checks.
                                # Identity-V ink is checked separately because
                                # its extraction origin uses another convention.
                                compare("spacing", key, a["origin"][axis], w["origin"][axis],
                                        1.5, "inline character origin")
                            if w["c"] in "×÷+＋-−－x":
                                compare("spacing", key, a["origin"][axis], w["origin"][axis],
                                        .25, "operator inline origin")
                    if table and "table" in enabled:
                        frame = _edge_evidence(item["source_bbox"], source_rules)
                        # Outer Table reservations include half-stroke clearance;
                        # compare the visible rule centers, not that reservation.
                        actual_frame = _edge_evidence(regions[key], actual_rules)
                        for edge, ((a, aw), (w, ww)) in enumerate(zip(actual_frame, frame)):
                            label = ("left", "top", "right", "bottom")[edge]
                            compare("table", key, a, w, .20, label + " rule center")
                            if aw is not None and ww is not None:
                                compare("table", key, aw, ww, .08, label + " rule thickness")
                            elif ww is not None and aw is None:
                                errors.append({"category": "table", "id": key,
                                               "detail": label + " original rule is absent"})
    return {"source_pages": list(selected), "checks": counts, "max_delta_pt": maxima,
            "error_count": len(errors), "errors": errors, "source_sha256": manifest["source"]["sha256"]}


def verify_appearance(path, *, source_pages, trace):
    report = appearance_report(path, source_pages=source_pages, trace=trace)
    if report["errors"]:
        sample = json.dumps(report["errors"][:8], ensure_ascii=False)
        raise ValueError(f"原本の外観不一致: {report['error_count']} differences; {sample}")
    return {key: value for key, value in report.items() if key != "errors"}
