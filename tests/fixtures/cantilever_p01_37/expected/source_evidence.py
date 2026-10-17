"""Maintainer-only source transcription aid; never import builder or its input.

All 37 source pages and all table boundaries were visually inspected by the
independent oracle author. Regeneration is deliberately not a test fixture.
"""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

import pymupdf

ROOT = Path(__file__).resolve().parents[4]
SOURCE = next((ROOT / "tests/output").glob("13_*.pdf"))
SOURCE_SHA256 = "e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e"


def compact(text):
    return "".join(c for c in text if not c.isspace())


def characters(page):
    result = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    result.append({**char, "size": span["size"], "dir": line["dir"]})
    return result


def ordered_lines(chars, turns=0):
    """Independent source-axis ordering; group small scripts with their base."""
    if not chars:
        return []
    def uv(c):
        x, y = c["origin"]
        return (-y, x) if turns else (x, y)
    major = [c for c in chars if c["size"] >= 8 and not c["c"].isspace()]
    baselines = []
    for c in sorted(major, key=lambda c: uv(c)[1]):
        y = uv(c)[1]
        if not baselines or y - baselines[-1] > 4:
            baselines.append(y)
    if not baselines:
        baselines = [min(uv(c)[1] for c in chars)]
    lines = [[] for _ in baselines]
    for c in chars:
        row = min(range(len(baselines)), key=lambda i: abs(uv(c)[1] - baselines[i]))
        lines[row].append(c)
    return [(sorted(line, key=lambda c: uv(c)[0]), baseline) for line, baseline in zip(lines, baselines)]


def reading(chars, turns=0):
    return "\n".join("".join(c["c"] for c in line) for line, _ in ordered_lines(chars, turns))


def in_box(chars, box):
    x0, y0, x1, y1 = box
    return [c for c in chars if x0 <= (c["bbox"][0] + c["bbox"][2]) / 2 < x1
            and y0 <= (c["bbox"][1] + c["bbox"][3]) / 2 < y1]


def record(item_id, chars, box, *, turns=0, **extra):
    selected = in_box(chars, box)
    text = reading(selected, turns)
    ordered = [(c, baseline) for line, baseline in ordered_lines(selected, turns)
               for c in line if not c["c"].isspace()]
    scripts = []
    for index, (c, baseline) in enumerate(ordered):
        if c["size"] < 8:
            delta = c["origin"][0 if turns else 1] - baseline
            scripts.append({"text": c["c"], "size": round(c["size"], 3),
                            "character_index": index, "baseline_delta": round(delta, 3),
                            "role": "subscript" if delta > 0 else "superscript"})
    body_sizes = [c["size"] for c in selected if not c["c"].isspace() and c["size"] >= 8]
    minimum = min(body_sizes, default=9.959)
    direction = [0, -1] if turns else [1, 0]
    direction_overrides = [{"character_index": index, "direction": list(c["dir"])}
                           for index, (c, _) in enumerate(ordered) if list(c["dir"]) != direction]
    return {"id": item_id, "source_bbox": box, "text": text,
            "direction": direction,
            "minimum_body_size": 9.7 if minimum >= 9.7 else (9.0 if minimum >= 9 else 8.0),
            "source_scripts": scripts,
            **({"source_direction_overrides": direction_overrides} if direction_overrides else {}),
            **extra}


def rotated_table(number, chars):
    summary = number >= 36
    quantity = "summary" if summary else ("md" if number <= 31 else "vd" if number <= 33 else "mt")
    block_id = f"p{number}-combinations-{quantity}"
    edges = ([776.4, 746.82, 717.78, 688.74, 645.18, 616.14, 587.1,
              558.06, 529.02, 470.94, 441.9, 383.82, 325.74, 267.66, 209.58, 151.5, 63.96]
             if summary else [776.4, 746.82, 703.26, 659.7, 616.14, 572.58,
                               529.02, 485.46, 441.9, 383.82, 340.26, 296.7, 238.62, 180.54, 93.0])
    top, split, body = ((67.68, 83.1, 127.74) if summary else
                        ((65.64, 76.98, 98.58) if number == 30 else (64.92, 76.26, 97.86)))
    # Two source header rows, with all spans represented exactly once.
    header_cells = [(0, 0, 2, 1), (0, 1, 1, 9)]
    if summary:
        header_cells += [(0, 10, 1, 3), (0, 13, 2, 1), (0, 14, 2, 1), (0, 15, 2, 1)]
        header_cells += [(1, c, 1, 1) for c in range(1, 13)]
    else:
        header_cells += [(0, c, 2, 1) for c in range(10, 14)]
        header_cells += [(1, c, 1, 1) for c in range(1, 10)]
    cells = []
    for row, col, rowspan, colspan in header_cells:
        box = [top if row == 0 else split, edges[col + colspan],
               body if row + rowspan == 2 else split, edges[col]]
        cells.append(record(f"{block_id}.r{row}.c{col}", chars, box, turns=1,
                            row=row, col=col, rowspan=rowspan, colspan=colspan))
    count = 18 if number % 2 == 0 else 13
    first_case = 1 if number % 2 == 0 else 19
    for case in range(count):
        for col in range(len(edges) - 1):
            box = [body + case * 21.6, edges[col + 1], body + (case + 1) * 21.6, edges[col]]
            cells.append(record(f"{block_id}.r{case + 2}.c{col}", chars, box, turns=1,
                                row=case + 2, col=col, rowspan=1, colspan=1, case=case + first_case))
    return {"id": block_id, "kind": "table", "direction": [0, -1], "cells": cells,
            "header_rows": 2, "body_rows": count, "columns": len(edges) - 1}


def prose(number, chars):
    offset = 0 if number == 16 else -51
    regions = [
        ("condition", 117, 135), ("t1", 145, 166), ("movable", 172, 188),
        ("movable-rm", 188, 261), ("movable-hbd", 268, 300),
        ("movable-hsd", 307, 336), ("t2", 376, 396), ("fixed", 402, 419),
        ("fixed-rm", 419, 490), ("fixed-hbd", 498, 531),
        ("stopper", 539, 601), ("hsd", 605, 620),
    ]
    result = []
    if number == 16:
        result += [record("p16-title", chars, [0, 65, 595, 88], kind="text"),
                   record("p16-subtitle", chars, [0, 95, 595, 114], kind="text")]
    for label, start, end in regions:
        item = record(f"p{number}-{label}", chars, [0, start + offset, 595, end + offset], kind="text")
        item["text"] = item["text"].replace("※", "")
        result.append(item)
    return result


def load_tables(chars):
    result = [record("p26-title", chars, [0, 65, 595, 90], kind="text"),
              record("p26-safety", chars, [0, 90, 595, 107], kind="text"),
              record("p26-service", chars, [0, 432, 595, 451], kind="text")]
    # No body vertical rules; column boundaries below are midpoint cells
    # between source headings/values and were reviewed against all six tables.
    xs = [124.32, 207, 240.54, 284.1, 327.66, 371.22, 414.78, 458.34, 501.96]
    tops = [133.56, 240.96, 348.36, 477.48, 584.88, 692.28]
    for tag, top in zip(("safety-b", "safety-c", "safety-bc", "service-b", "service-c", "service-bc"), tops):
        block_id = f"p26-{tag}"
        result.append(record(f"{block_id}-title", chars, [0, top - 22, 595, top - 5], kind="text"))
        cells = []
        for col in [0, *range(2, 8)]:
            colspan = 2 if col == 0 else 1
            cells.append(record(f"{block_id}.r0.c{col}", chars,
                                [xs[col], top, xs[col + colspan], top + 29.1],
                                row=0, col=col, rowspan=1, colspan=colspan))
        for row in range(1, 4):
            for col in range(8):
                # Empty label cells remain explicit; no ditto expansion.
                cells.append(record(f"{block_id}.r{row}.c{col}", chars,
                                    [xs[col], top + 29.1 + (row - 1) * 14.2,
                                     xs[col + 1], top + 29.1 + row * 14.2],
                                    row=row, col=col, rowspan=1, colspan=1))
        result.append({"id": block_id, "kind": "table", "direction": [1, 0],
                       "header_rows": 1, "body_rows": 3, "columns": 8, "cells": cells,
                       "selective_rules": {"horizontal_boundaries": [0, 1, 4], "vertical_boundaries": [2]}})
    return result


def train_equations(number, chars):
    headings = {
        3: ["title", "subtitle", "b", "b-single-title", "b-double-title", "c", "c-single-title", "c-double-title"],
        4: ["bc", "bc-single-title", "bc-double-title"],
        5: ["title", "subtitle", "b", "b-single-title", "b-double-title", "c", "c-single-title", "c-double-title"],
        6: ["bc", "bc-single-title", "bc-double-title"],
        7: ["title", "b", "b-single-title", "b-double-title", "c", "c-single-title", "c-double-title"],
        8: ["bc", "bc-single-title", "bc-double-title", "seismic-title"],
    }
    labels = iter(headings[number])
    formula = 0
    result = []
    for line, baseline in ordered_lines(chars):
        text = compact("".join(c["c"] for c in line))
        if text.startswith("Ｇ"):
            formula += 1
            label = f"equation-{formula:03}"
            kind = "equation"
        else:
            label = next(labels)
            kind = "text"
        box = [0, min(c["bbox"][1] for c in line) - .3,
               595, max(c["bbox"][3] for c in line) + .3]
        result.append(record(f"p{number:02}-{label}", chars, box, kind=kind))
    assert formula == {3: 24, 4: 12, 5: 24, 6: 12, 7: 24, 8: 18}[number]
    assert next(labels, None) is None
    return result


def remaining_headings(number, chars, occupied, labels):
    uncovered = [c for c in chars if not any(c in in_box([c], box) for box in occupied)]
    lines = ordered_lines(uncovered)
    assert len(lines) == len(labels), (number, len(lines), labels,
                                     [reading(line) for line, _ in lines])
    return [record(f"p{number:02}-{label}", chars,
                   [0, min(c["bbox"][1] for c in line)-.2, 595, max(c["bbox"][3] for c in line)+.2], kind="text")
            for (line, _), label in zip(lines, labels)]


def bearing_summary(number, chars):
    xs = [123.84, 153.42, 342.18, 414.78, 487.8]
    ys = [121.92, 149.58, 176.1, 202.62, 229.14, 255.66, 295.44]
    tables = []
    boxes = []
    for tag, shift in (("origin", 0), ("end", 226.8)):
        key = f"p{number}-{tag}-table"
        table_box = [xs[0], ys[0]+shift, xs[-1], ys[-1]+shift]
        boxes.append(table_box)
        addresses = [(0, 0, 1, 2), (0, 2, 1, 1), (0, 3, 1, 1), (1, 0, 4, 1), (5, 0, 1, 1)]
        addresses += [(r, c, 1, 1) for r in range(1, 6) for c in range(1, 4)]
        cells = [record(f"{key}.r{r}.c{c}", chars, [xs[c], ys[r]+shift, xs[c+cs], ys[r+rs]+shift],
                        row=r, col=c, rowspan=rs, colspan=cs) for r, c, rs, cs in addresses]
        tables.append({"id": key, "kind": "table", "direction": [1, 0], "cells": cells,
                       "header_rows": 1, "body_rows": 5, "columns": 4, "rule_style": "full"})
    return remaining_headings(number, chars, boxes, ["title", "origin-title", "end-title"]) + tables


def weight_table(chars):
    key = "p23-weight-table"
    xs = [109, 125, 336, 395, 453, 519]
    ys = [326, 355, 371.7, 386, 401]
    cells = [record(f"{key}.r{r}.c{c}", chars, [xs[c], ys[r], xs[c+1], ys[r+1]],
                    row=r, col=c, rowspan=1, colspan=1) for r in range(4) for c in range(5)]
    box = [xs[0], ys[0], xs[-1], ys[-1]]
    return remaining_headings(23, chars, [box], ["title"]) + [{
        "id": key, "kind": "table", "direction": [1,0], "cells": cells,
        "header_rows": 1, "body_rows": 3, "columns": 5,
        "selective_rules": {"horizontal_boundaries": [], "vertical_boundaries": []}}]


def small_load_tables(number, chars):
    definitions = {
        24: [("dead1", 432.84, 95.28, 4), ("dead2", 568.8, 95.28, 3), ("snow2", 712.2, 109.8, 3)],
        25: [("snow10", 90.12, 109.8, 3), ("snow30", 197.52, 109.8, 3),
             ("train-b", 340.92, 109.8, 3), ("train-c", 448.32, 109.8, 3),
             ("train-bc", 555.72, 109.8, 3), ("train-eq", 663.12, 109.8, 3)],
        27: [("lateral-b", 111.84, 109.8, 3), ("lateral-c", 219.24, 109.8, 3),
             ("lateral-bc", 326.64, 109.8, 3), ("wind-with", 470.04, 109.8, 3),
             ("wind-without", 577.44, 109.8, 3)],
        28: [("eq", 90.12, 95.28, 5), ("horizontal9", 240.36, 95.28, 5),
             ("horizontal10", 389.88, 95.28, 5), ("horizontal11", 539.4, 95.28, 5)],
        29: [("horizontal12", 89.4, 95.28, 5), ("eq", 239.64, 95.28, 5)],
    }[number]
    headings = {
        24: ["title", "dead1-title", "dead2-title", "snow-title", "snow2-title"],
        25: ["snow10-title", "snow30-title", "train-title", "train-b-title", "train-c-title", "train-bc-title", "train-eq-title"],
        27: ["lateral-title", "lateral-b-title", "lateral-c-title", "lateral-bc-title", "wind-title", "wind-with-title", "wind-without-title"],
        28: ["eq-title", "horizontal9-title", "horizontal10-title", "horizontal11-title"],
        29: ["horizontal12-title", "eq-title"],
    }[number]
    tables, boxes = [], []
    for tag, top, left, count in definitions:
        key = f"p{number}-{tag}-table"
        xs = [left+x for x in (0, 82.68, 116.22, 159.78, 203.34, 246.9, 290.46, 334.02, 377.64)]
        if tag.startswith("horizontal") or number == 29:
            xs[1] = left + 43.56
        ys = [top, *[top+29.1+r*14.28 for r in range(count+1)]]
        boxes.append([xs[0], ys[0], xs[-1], ys[-1]])
        addresses = [(0, 0, 1, 2), *[(0, c, 1, 1) for c in range(2, 8)],
                     *[(r, c, 1, 1) for r in range(1, count+1) for c in range(8)]]
        cells = [record(f"{key}.r{r}.c{c}", chars, [xs[c], ys[r], xs[c+cs], ys[r+rs]],
                        row=r, col=c, rowspan=rs, colspan=cs) for r,c,rs,cs in addresses]
        tables.append({"id": key, "kind": "table", "direction": [1, 0], "cells": cells,
                       "header_rows": 1, "body_rows": count, "columns": 8,
                       "selective_rules": {"horizontal_boundaries": [0, 1, count+1], "vertical_boundaries": [2]}})
    return remaining_headings(number, chars, boxes, headings) + tables


def line_groups(number, chars, definitions):
    result = []
    lines = ordered_lines([c for c in chars if c["c"] != "※"])
    for label, indexes in definitions:
        picked = [c for i in indexes for c in lines[i][0]]
        box = [0, min(c["bbox"][1] for c in picked)-.1, 595, max(c["bbox"][3] for c in picked)+.1]
        result.append(record(f"p{number:02}-{label}", [c for c in chars if c["c"] != "※"], box, kind="text"))
    return result


def bearing_short(number, chars):
    if number == 19:
        definitions = [("condition",[0]),("t1",[1]),("movable",[2]),("movable-rm",range(3,6)),
                       ("movable-hbd",range(6,8)),("movable-hsd",range(8,10)),("t2",[10]),("fixed",[11]),
                       ("fixed-rm",range(12,15)),("fixed-hbd",range(15,17)),("stopper",range(17,21)),("hsd",[21])]
    else:
        definitions = [("title",[0]),("t1",[1]),("movable",[2]),("movable-rm",range(3,6)),
                       ("movable-hbd-title",[6]),("movable-hbd-equation",[7]),
                       ("movable-hsd-title",[8]),("movable-hsd-equation",[9]),("t2",[10]),
                       ("fixed-hbd-title",[11]),("fixed-hbd-equation",[12]),
                       ("fixed-hsd-title",[13]),("fixed-hsd-equation",[14])]
    return line_groups(number, chars, definitions)


def torque_pages(number, chars):
    definitions = {
        9: [("title",[0]),("subtitle",[1]),("forces",range(2,6)),("torque-title",[6]),("sum-x2",[7]),("reactions",range(8,10))],
        10: [("subtitle",[0]),("forces",range(1,5)),("torque-title",[5]),("reactions",[6])],
        11: [("title",[0]),("origin-title",[1]),("origin-forces",range(2,6)),("origin-torque-title",[6]),("origin-reactions",range(7,9)),
             ("end-title",[9]),("end-forces",range(10,14)),("end-torque-title",[14]),("end-reactions",[15])],
        12: [("title",[0]),("with-train-title",[1]),("with-origin-title",[2]),("with-origin-moment",[3]),
             ("with-origin-torque-title",[4]),("with-origin-reactions",range(5,9)),("with-end-title",[9]),
             ("with-end-moment",[10]),("with-end-torque-title",[11]),("with-end-reactions",range(12,14)),
             ("without-train-title",[14]),("without-origin-title",[15]),("without-origin-moment",[16]),
             ("without-origin-torque-title",[17]),("without-origin-reactions",range(18,22)),("without-end-title",[22]),
             ("without-end-moment",[23]),("without-end-torque-title",[24]),("without-end-reactions",range(25,27))],
        15: [("title",[0]),("girder-title",[1]),("rail-title",[2]),("rail-safety-title",[3]),("rail-safety-note",[4]),
             ("rail-safety",range(5,7)),("rail-service-title",[7]),("rail-service-note",[8]),("rail-service",range(9,11)),
             ("brake-title",[11]),("brake-note",[12]),("brake",range(13,15)),("dead-eq-title",[15]),
             ("dead-response",[16]),("dead-eq",range(17,19)),("train-eq-title",[19]),("train-response",[20]),("train-eq",range(21,23))],
    }
    if number in (13,14):
        definitions[number] = [("title",[0]),("response",[1]),("origin-title",[2]),("origin-forces",range(3,6)),
                               ("origin-torque-title",[6]),("origin-reactions",range(7,11)),("end-title",[11]),
                               ("end-forces",range(12,15)),("end-torque-title",[15]),("end-reactions",range(16,18))]
    return line_groups(number, chars, definitions[number])


def reactions_record(key, chars, bounds):
    # Results printed beside the first RHS line precede the continuation in
    # physical reading order. Use the same baseline order as every other item;
    # this display transcript is not a parsed mathematical expression.
    item = record(key,chars,[0,bounds[0],595,bounds[-1]],kind="text")
    item["source_reading"] = "physical baseline order: top-to-bottom, then left-to-right including the result column"
    return item


def introductory_pages(number, chars):
    if number == 2:
        return [record("p02-c-title",chars,[0,65,595,90],kind="text"),
                reactions_record("p02-c-reactions",chars,[235,260,290,327,360]),
                record("p02-bc-title",chars,[0,382,595,400],kind="text"),
                reactions_record("p02-bc-reactions",chars,[550,575,613,640,675])]
    xs=[109.8,182.46,226.02,284.04,327.66,371.22,414.78,458.34,501.96]
    ys=[167.16,181.44,195.78,210.06,224.34,238.62,252.84,267.18,281.46,295.74,310.02,324.24]
    addresses=[(0,0,1,3),*[(0,c,1,1) for c in range(3,8)]]
    for r in (1,6):
        addresses += [(r,0,5,1),(r,1,1,2),(r+1,1,1,2),(r+2,1,3,1)]
        addresses += [(row,2,1,1) for row in range(r+2,r+5)]
        addresses += [(row,c,1,1) for row in range(r,r+5) for c in range(3,8)]
    key="p01-dead-loads"
    cells=[record(f"{key}.r{r}.c{c}",chars,[xs[c],ys[r],xs[c+cs],ys[r+rs]],row=r,col=c,rowspan=rs,colspan=cs)
           for r,c,rs,cs in addresses]
    headings=[record(f"p01-{tag}",chars,[0,y-12,595,y+4],kind="text") for tag,y in
              (("title",79.68),("section",100.68),("vertical",121.68),("dead-title",142.68),("table-title",163.68),
               ("train-title",363.6),("service-title",392.76),("b-title",419.88))]
    return [*headings,{"id":key,"kind":"table","direction":[1,0],"cells":cells,"header_rows":1,"body_rows":10,"columns":8,
                     "cell_edge_rules": {"horizontal_boundaries":list(range(12)),"vertical_boundaries":list(range(1,8))}},
            reactions_record("p01-reactions",chars,[575,600,640,670,700])]


def main():
    actual_hash = sha256(SOURCE.read_bytes()).hexdigest()
    assert actual_hash == SOURCE_SHA256, actual_hash
    with pymupdf.open(SOURCE) as pdf:
        for number in (tuple(int(arg) for arg in sys.argv[1:]) or (16, 17, 26, 30, 36)):
            chars = characters(pdf[number - 1])
            content = [c for c in chars if not (500 <= c["bbox"][0] and c["bbox"][1] < 60)]
            figures = json.loads(Path(__file__).parents[1].joinpath("assets/metadata.json").read_text(encoding="utf-8"))["figures"]
            figure_boxes = [f["source_bbox"] for f in figures if f["source_page"] == number]
            content = [c for c in content if not any(in_box([c], box) for box in figure_boxes)]
            if 30 <= number <= 37:
                blocks = [rotated_table(number, content)]
                if number == 30:
                    blocks.insert(0, record("p30-title", chars, [0, 62, 500, 85], kind="text"))
            elif number == 26:
                blocks = load_tables(content)
            elif 3 <= number <= 8:
                blocks = train_equations(number, content)
            elif number in (21, 22):
                blocks = bearing_summary(number, content)
            elif number == 23:
                blocks = weight_table(content)
            elif number in (24, 25, 27, 28, 29):
                blocks = small_load_tables(number, content)
            elif number in (19,20):
                blocks = bearing_short(number,content)
            elif 9 <= number <= 15:
                blocks = torque_pages(number,content)
            elif number in (1,2):
                blocks = introductory_pages(number,content)
            else:
                blocks = prose(number, content)
            expected = {
                "schema_version": 1, "source_page": number, "source_sha256": actual_hash,
                "provenance": {"author": "oracle", "method": "independent source glyph transcription and visual comparison",
                               "reviewed_source_image": f"source-survey/p{number:02}.png", "review_status": "source-reviewed"},
                "omitted_page_number": f"13 - {number}",
                "source_character_inventory": dict(sorted(Counter(compact("".join(c["c"] for c in content))).items())),
                "marker_count": 4 if number in (16, 17, 18, 19, 20) else 0,
                "hash_placeholder_count": {9: 1, 12: 6, 13: 7, 16: 12, 17: 12, 18: 12, 19: 10, 20: 3}.get(number, 0),
                "blocks": blocks,
            }
            Path(__file__).with_name(f"p{number:02}.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
