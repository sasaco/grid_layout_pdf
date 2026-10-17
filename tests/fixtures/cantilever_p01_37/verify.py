"""Independent PDF oracle; trace supplies regions, never expected content.

No builder, scene bounds, or production transform helper is imported here.
The checked glyphs, sizes, directions, image pixels and rules come from PDF.
"""

# The fixture writer uses this assertion-based test oracle as a publication
# gate. Refuse optimized execution instead of silently disabling those checks.
if not __debug__:
    raise RuntimeError("Cantilever verification requires assertions enabled; do not use -O or PYTHONOPTIMIZE")

from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re

import pymupdf
from PIL import Image


EXPECTED = Path(__file__).with_name("expected")
IDENTITY = (1, 0, 0, 1, 0, 0)
_SOURCE_SHA256 = "e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e"
# The original 9.94/9.96 pt text and explicitly authored 10 pt text differ by
# <=0.040 pt at these numeric advance endpoints; PDF extraction adds <0.001 pt.
_ANCHOR_TOLERANCE_PT = .1


def _compact(text):
    return "".join(c for c in text if not c.isspace())


def _chars(page):
    return [{**char, "size": span["size"], "direction": tuple(line["dir"])}
            for block in page.get_text("rawdict")["blocks"]
            for line in block.get("lines", []) for span in line["spans"]
            for char in span["chars"]]


def _inside(chars, rect):
    x0, y0, x1, y1 = rect
    return [c for c in chars if x0 <= (c["bbox"][0] + c["bbox"][2]) / 2 < x1
            and y0 <= (c["bbox"][1] + c["bbox"][3]) / 2 < y1]


def _ordered_lines(chars, direction):
    if not chars:
        return []
    dx, dy = direction
    def project(c):
        x, y = c["origin"]
        return dx * x + dy * y, -dy * x + dx * y
    # Baseline ordering derives from actual PDF geometry. Small scripts join
    # their nearest full-size baseline; all glyphs are retained, even repeats.
    rows = []
    major = [c for c in chars if c["size"] >= 8 and not c["c"].isspace()]
    for char in sorted(major, key=lambda c: project(c)[1]):
        y = project(char)[1]
        if not rows or y - rows[-1] > 4:
            rows.append(y)
    if not rows:
        rows = [min(project(c)[1] for c in chars)]
    lines = [[] for _ in rows]
    for char in chars:
        row = min(range(len(rows)), key=lambda i: abs(project(char)[1] - rows[i]))
        lines[row].append(char)
    return [(sorted(line, key=lambda c: project(c)[0]), baseline) for line, baseline in zip(lines, rows)]


def _reading(chars, direction):
    return "\n".join("".join(c["c"] for c in line) for line, _ in _ordered_lines(chars, direction))


def _script_positions(chars, item):
    direction = item["direction"]
    ordered = [(c, baseline) for line, baseline in _ordered_lines(chars, direction)
               for c in line if not c["c"].isspace()]
    indexes = {index for index, (c, _) in enumerate(ordered) if c["size"] < 8}
    assert indexes == {s["character_index"] for s in item["source_scripts"]}, f"{item['id']}: script order"
    for script in item["source_scripts"]:
        char, baseline = ordered[script["character_index"]]
        dx, dy = direction
        x, y = char["origin"]
        delta = -dy*x + dx*y - baseline
        sign = 1 if script["role"] == "subscript" else -1
        # Baseline displacement must remain on the correct side, separated by
        # >=0.05 em; upper marks stay within 0.8 em, lower marks within 0.6 em
        # of the 10 pt body. This allows font metric
        # differences without admitting flattened, reversed or detached marks.
        limit = 6 if script["role"] == "subscript" else 8
        assert .5 <= sign*delta <= limit, f"{item['id']}: {script['role']} baseline position"


def _compose(parent, child):
    a, b, c, d, e, f = parent
    g, h, i, j, k, l = child
    return (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f)


def _translation(x, y):
    return (1, 0, 0, 1, x, y)


def _box(matrix, x, y, width, height):
    a, b, c, d, e, f = matrix
    points = [(a*u+c*v+e, b*u+d*v+f) for u, v in
              ((x, y), (x+width, y), (x, y+height), (x+width, y+height))]
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def _trace_regions(page):
    regions, spans = {}, {}
    grid = page["profile"]["grid"]
    def add(key, box, span=None):
        if not key:
            return
        assert key not in regions, f"duplicate trace item {key}"
        regions[key] = box
        if span is not None:
            spans[key] = span
    def walk(node, parent, default_pitch):
        matrix = _compose(parent, _translation(node.get("x_pt", 0), node.get("y_pt", 0)))
        pitch = node.get("row_pitch", default_pitch)
        block_id = node.get("block_id", "")
        add(block_id, _box(matrix, 0, 0, node["width"], node["rows"] * pitch))
        for part in [*node.get("prefix", []), *node.get("parts", [])]:
            placed = _compose(matrix, _translation(0, part["row"] * pitch))
            metadata = part["metadata"]
            for child in metadata.get("children", []):
                walk(child, placed, pitch)
            if "local_to_part" in metadata:
                transform = metadata["local_to_part"]
                assert len(transform) == 6, f"invalid transform for {block_id}"
                walk(metadata["child"], _compose(placed, transform), metadata["local_grid"]["pitch_y"])
            for cell in metadata.get("cells", []):
                frame = cell["frame"]
                key = f"{block_id}.r{cell['row']}.c{cell['col']}"
                add(key, _box(placed, frame["x_pt"], frame["y_pt"], frame["width"], frame["height"]),
                    (cell["rowspan"], cell["colspan"]))
    assert not page["metadata"].get("decorations"), "page number decorations are prohibited"
    for placement in page["metadata"]["placements"]:
        origin = _translation(grid["origin_x"] + placement["col"] * grid["pitch_x"],
                              grid["origin_y"] + placement["row"] * grid["pitch_y"])
        walk(placement, origin, grid["pitch_y"])
    return regions, spans


def _figure_allowlist(manifest):
    if manifest is None:
        return []
    reviewed = json.loads(EXPECTED.parent.joinpath("assets/metadata.json").read_text(encoding="utf-8"))["figures"]
    allowed = manifest.get("figures", [])
    assert len(allowed) == len(reviewed), "figure allowlist count"
    assert len({a["id"] for a in allowed}) == len(allowed), "duplicate figure allowlist identity"
    for asset in allowed:
        source = next((r for r in reviewed if r["id"] == asset["id"]), None)
        assert source is not None, "unreviewed figure identity"
        for field in ("source_page", "source_bbox", "source_sha256", "sha256", "normalized_byte_sha256",
                      "decoded_pixel_sha256", "pixel_width", "pixel_height", "occurrence_count", "source_review"):
            assert asset[field] == source[field], f"{asset['id']}: figure source provenance {field}"
    return allowed


def _images(page, source_page, manifest):
    allowed = [a for a in _figure_allowlist(manifest) if a["source_page"] == source_page]
    infos = page.get_image_info(xrefs=True)
    assert len(infos) == sum(a.get("occurrence_count", 1) for a in allowed), f"p{source_page:02}: image occurrence count"
    remaining = list(allowed)
    for info in infos:
        assert info["xref"] > 0, f"p{source_page:02}: untracked inline image"
        pixmap = pymupdf.Pixmap(page.parent, info["xref"])
        if pixmap.colorspace is None or pixmap.colorspace.n != 3:
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
        if pixmap.alpha:
            pixmap = pymupdf.Pixmap(pixmap, 0)
        pixel_hash = sha256(pixmap.samples).hexdigest()
        match = next((a for a in remaining if a["decoded_pixel_sha256"] == pixel_hash
                      and a["pixel_width"] == pixmap.width and a["pixel_height"] == pixmap.height), None)
        assert match is not None, f"p{source_page:02}: image pixels are not allowlisted"
        _image_geometry(info["bbox"], match, source_page)
        assert all(abs(a-b) <= .1 for a, b in zip(info["bbox"], match["target_bbox"])), f"p{source_page:02}: image region"
        remaining.remove(match)


def _image_geometry(box, asset, source_page):
    x0,y0,x1,y1 = box
    source = asset["source_bbox"]
    assert 0 <= x0 < x1 <= 595 and 0 <= y0 < y1 <= 842, f"p{source_page:02}: image page bounds"
    assert abs(x1-x0-(source[2]-source[0])) < .1 and abs(y1-y0-(source[3]-source[1])) < .1, f"p{source_page:02}: image source physical dimensions"
    assert source[2]-source[0] < 500 and source[3]-source[1] < 500, f"p{source_page:02}: full-page image prohibited"
    assert all(abs(a-b) <= .1 for a,b in zip(box,asset["target_bbox"])), f"p{source_page:02}: image region"


def verify_scene_images(pages, source_pages, manifest):
    """Independent byte, pixel, source-page and physical-box allowlist gate."""
    source_pages = tuple(source_pages)
    assert len(pages) == len(source_pages), "scene image page count"
    total = 0
    allowlist = _figure_allowlist(manifest)
    for page, source_page in zip(pages, source_pages):
        allowed = [a for a in allowlist if a["source_page"] == source_page]
        commands = [c for c in page.commands if type(c).__name__ == "RasterImage"]
        assert len(commands) == sum(a.get("occurrence_count",1) for a in allowed), f"p{source_page:02}: scene image occurrence count"
        remaining = list(allowed)
        for command in commands:
            byte_hash = sha256(command.data).hexdigest()
            match = next((a for a in remaining if a["normalized_byte_sha256"] == byte_hash), None)
            assert match is not None, f"p{source_page:02}: scene image bytes are not allowlisted"
            with Image.open(BytesIO(command.data)) as encoded:
                rgb = encoded.convert("RGB")
                assert rgb.size == (match["pixel_width"],match["pixel_height"]), f"p{source_page:02}: scene image pixel dimensions"
                assert sha256(rgb.tobytes()).hexdigest() == match["decoded_pixel_sha256"], f"p{source_page:02}: scene image pixels"
            assert match["source_sha256"] == "e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e", "image source identity"
            assert match["source_review"]["result"] == "pass", "image source review missing"
            _image_geometry((command.x,command.y,command.x+command.width,command.y+command.height),match,source_page)
            remaining.remove(match)
            total += 1
    return total


def _black_rules(page):
    result = []
    for drawing in page.get_drawings():
        color = drawing.get("color")
        if color is None or any(abs(channel) > .01 for channel in color):
            continue
        for item in drawing["items"]:
            if item[0] == "l":
                result.append((*item[1], *item[2]))
            elif item[0] == "re":
                x0, y0, x1, y1 = item[1]
                result.extend(((x0, y0, x1, y0), (x1, y0, x1, y1),
                               (x1, y1, x0, y1), (x0, y1, x0, y0)))
    return result


def _edge_present(rules, start, end):
    vertical = abs(start[0] - end[0]) < .001
    fixed = 0 if vertical else 1
    along = 1 - fixed
    intervals = []
    for x0, y0, x1, y1 in rules:
        a, b = (x0, y0), (x1, y1)
        if abs(a[fixed] - start[fixed]) <= .6 and abs(b[fixed] - start[fixed]) <= .6:
            intervals.append(sorted((a[along], b[along])))
    cursor, stop = sorted((start[along], end[along]))
    for low, high in sorted(intervals):
        if low > cursor + .7:
            break
        if high >= cursor:
            cursor = high
    return cursor >= stop - .7


def _cell_rules(rules, rect, key, required=(True,True,True,True)):
    x0, y0, x1, y1 = rect
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    for index, start in enumerate(corners):
        present = _edge_present(rules, start, corners[(index + 1) % 4])
        assert present == required[index], f"{key}: {'missing' if required[index] else 'unexpected'} vector rule"
    for ax, ay, bx, by in rules:
        if abs(ax-bx) < .01 and x0+.6 < ax < x1-.6:
            overlap = min(max(ay, by), y1-.6) - max(min(ay, by), y0+.6)
            assert overlap < 1, f"{key}: unexpected internal vector rule"
        if abs(ay-by) < .01 and y0+.6 < ay < y1-.6:
            overlap = min(max(ax, bx), x1-.6) - max(min(ax, bx), x0+.6)
            assert overlap < 1, f"{key}: unexpected internal vector rule"


def _selective_rules(rules, block, regions):
    """Source-derived sparse rules, independent of Table's stroke metadata."""
    key = block["id"]
    cells = block["cells"]
    boxes = [regions[c["id"]] for c in cells]
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    horizontal, vertical = [], []
    for row in block["selective_rules"]["horizontal_boundaries"]:
        y = y1 if row == block["header_rows"] + block["body_rows"] else min(
            regions[c["id"]][1] for c in cells if c["row"] == row)
        horizontal.append(y)
        assert _edge_present(rules, (x0, y), (x1, y)), f"{key}: missing horizontal rule"
    for col in block["selective_rules"]["vertical_boundaries"]:
        x = min(regions[c["id"]][0] for c in cells if c["col"] == col)
        vertical.append(x)
        assert _edge_present(rules, (x, y0), (x, y1)), f"{key}: missing vertical rule"
    for ax, ay, bx, by in rules:
        if abs(ax-bx) < .01 and x0-.6 <= ax <= x1+.6:
            overlap = min(max(ay, by), y1) - max(min(ay, by), y0)
            if overlap > 1:
                assert any(abs(ax-x) <= .6 for x in vertical), f"{key}: unexpected vertical rule"
        if abs(ay-by) < .01 and y0-.6 <= ay <= y1+.6:
            overlap = min(max(ax, bx), x1) - max(min(ax, bx), x0)
            if overlap > 1:
                assert any(abs(ay-y) <= .6 for y in horizontal), f"{key}: unexpected horizontal rule"


def _dense_anchors(chars, rules, regions, prefix):
    for side in ("movable", "fixed"):
        key = f"{prefix}-{side}-rm"
        equals = [c for c in _inside(chars, regions[key]) if c["c"] == "＝"]
        centers = [(c["bbox"][0]+c["bbox"][2])/2 for c in equals]
        assert len(centers) == 3 and max(centers)-min(centers) < .05, f"{key}: equal anchors"
    results, units = [], []
    for side in ("t1", "t2"):
        key = f"{prefix}-{side}"
        ordered = [c for line, _ in _ordered_lines(_inside(chars, regions[key]), (1, 0))
                   for c in line if not c["c"].isspace()]
        text = "".join(c["c"] for c in ordered)
        match = re.search(r"(\d+\.\d+)kN$", text)
        assert match, f"{key}: result anchor missing"
        results.append(max(c["bbox"][2] for c in ordered[match.start(1):match.end(1)]))
        units.append(ordered[-2]["origin"][0])
    assert max(results)-min(results) < .05, f"{prefix}: result anchors"
    assert max(units)-min(units) < .05, f"{prefix}: unit anchors"
    _, source_rules = _source_reference(int(prefix[1:]))
    wanted_bars, actual_bars = _group_bars(source_rules), _group_bars(rules)
    assert len(actual_bars) == len(wanted_bars) == 2, f"{prefix}: group bar count"
    for index, (actual, wanted) in enumerate(zip(actual_bars, wanted_bars)):
        for coordinate, observed, expected in zip(("center", "start", "end"), actual, wanted):
            assert abs(observed-expected) <= _ANCHOR_TOLERANCE_PT, f"{prefix}: group bar {index} {coordinate} differs from source"


def _source_reference(number):
    """Read independently hashed source bytes, never authored placement data."""
    sources = tuple((Path(__file__).resolve().parents[2] / "output").glob("13_*.pdf"))
    assert len(sources) == 1, "source PDF identity is ambiguous or missing"
    data = sources[0].read_bytes()
    assert sha256(data).hexdigest() == _SOURCE_SHA256, "source PDF hash mismatch"
    with pymupdf.open(stream=data, filetype="pdf") as source:
        return _chars(source[number-1]), _black_rules(source[number-1])


def _group_bars(rules):
    """Union duplicated/overlapping native centerline strokes, without moving them.

    Original p18 repeats one stroke; p19 has overlapping strokes in each group.
    Their visible union is the reference, not the number of PDF paint commands.
    """
    intervals = sorted((x0, min(y0, y1), max(y0, y1)) for x0, y0, x1, y1 in rules
                       if abs(x0-x1) < .01 and abs(y1-y0) > 100)
    merged = []
    for x, low, high in intervals:
        if merged and abs(x-merged[-1][0]) < .01 and low <= merged[-1][2] + .01:
            px, start, stop = merged[-1]
            merged[-1] = (px, start, max(stop, high))
        else:
            merged.append((x, low, high))
    return sorted(merged, key=lambda bar: (bar[1], bar[0]))


def _source_block_order(record, regions):
    ordered = []
    for block in record["blocks"]:
        if block["kind"] == "table":
            source_top = min(c["source_bbox"][1] for c in block["cells"])
        else:
            source_top = block["source_bbox"][1]
        ordered.append((source_top,block["id"]))
    actual = [regions[key][1] for _,key in sorted(ordered)]
    assert all(a <= b+.1 for a,b in zip(actual,actual[1:])), f"p{record['source_page']:02}: source block order"


def _train_anchors(chars,record,regions):
    source_chars, _ = _source_reference(record["source_page"])
    for item in record["blocks"]:
        if item["kind"] != "equation":
            continue
        actual = _train_item_anchors(_inside(chars,regions[item["id"]]), item["id"])
        wanted = _train_item_anchors(_inside(source_chars,item["source_bbox"]), item["id"])
        for label, observed, expected in zip(("result", "unit", "equal"), actual, wanted):
            assert abs(observed-expected) <= _ANCHOR_TOLERANCE_PT, f"{item['id']}: {label} anchor differs from source"


def _train_item_anchors(chars, identifier):
    ordered = [char for line,_ in _ordered_lines(chars,(1,0))
               for char in line if not char["c"].isspace()]
    text = "".join(char["c"] for char in ordered)
    result = re.search(r"(\d+\.\d+)kN$",text)
    assert result, f"{identifier}: result anchor missing"
    relation = next((char for char in ordered if char["c"] == "＝"), None)
    assert relation is not None, f"{identifier}: equal anchor missing"
    return (ordered[result.end(1)-1]["bbox"][2], ordered[-2]["origin"][0],
            (relation["bbox"][0]+relation["bbox"][2])/2)


def verify_pdf(path, *, source_pages, trace=None, grid=False, manifest=None):
    """Assert complete item/cell content and geometry for an explicit page set.

    A subset returns complete_37_pages=False. Missing expected files fail; this
    function never treats a partial fixture as the final 37-page acceptance.
    ``oracle_regions`` is a test-only shape used to inspect source controls.
    Real generated output supplies the native ``layout_trace`` structure.
    """
    pages = tuple(source_pages)
    if (not pages or any(type(n) is not int or not 1 <= n <= 37 for n in pages)
            or len(set(pages)) != len(pages) or pages != tuple(sorted(pages))):
        raise ValueError("source pages must be unique, increasing integers in 1..37")
    if not isinstance(grid, bool):
        raise ValueError("grid must be boolean")
    if trace is None:
        raise ValueError("source item regions require a layout trace")
    if isinstance(trace, (str, Path)):
        trace = json.loads(Path(trace).read_text(encoding="utf-8"))
    expected = []
    for n in pages:
        file = EXPECTED / f"p{n:02}.json"
        if not file.is_file():
            raise ValueError(f"source oracle missing for p{n:02}")
        expected.append(json.loads(file.read_text(encoding="utf-8")))
    native_trace = "oracle_regions" not in trace
    regions_by_page = trace["pages"] if native_trace else trace["oracle_regions"]
    assert len(regions_by_page) == len(pages), "trace page count"
    verified_items = 0
    with pymupdf.open(path) as pdf:
        assert len(pdf) == len(pages), f"page count {len(pdf)} != source count {len(pages)}"
        for page, source, record, trace_page in zip(pdf, pages, expected, regions_by_page):
            prefix = f"p{source:02}"
            assert tuple(page.mediabox) == (0, 0, 595, 842), f"{prefix}: page geometry"
            assert page.rotation == 0, f"{prefix}: page rotation"
            chars = _chars(page)
            corner = _reading(_inside(chars, (500, 30, 570, 62)), (1, 0))
            assert not re.search(r"13\s*[-−－–]\s*\d+", corner), f"{prefix}: page number is present"
            _images(page, source, manifest)
            regions, spans = _trace_regions(trace_page) if native_trace else (trace_page, {})
            rules = _black_rules(page)
            if native_trace:
                _source_block_order(record,regions)
            for block in record["blocks"]:
                items = block["cells"] if block["kind"] == "table" else [block]
                if block["kind"] == "table" and native_trace:
                    actual_ids = {key for key in regions if key.startswith(block["id"] + ".r")}
                    assert actual_ids == {item["id"] for item in items}, f"{prefix}: table cell coverage {block['id']}"
                    if "selective_rules" in block:
                        _selective_rules(rules, block, regions)
                for item in items:
                    key = item["id"]
                    assert key in regions, f"{prefix}: missing item region {key}"
                    rect = regions[key]
                    assert 0 <= rect[0] < rect[2] <= 595 and 0 <= rect[1] < rect[3] <= 842, f"{key}: invalid region"
                    selected = [c for c in _inside(chars, rect) if c["c"] != "※"]
                    direction = tuple(item["direction"])
                    actual = _compact(_reading(selected, direction))
                    wanted = _compact(item["text"])
                    assert actual == wanted, f"{key}: PDF text {actual!r} != source {wanted!r}"
                    direction_overrides = {entry["character_index"]: tuple(entry["direction"])
                                           for entry in item.get("source_direction_overrides", [])}
                    ordered = [char for line, _ in _ordered_lines(selected, direction)
                               for char in line if not char["c"].isspace()]
                    for index, char in enumerate(ordered):
                        required_direction = direction_overrides.get(index, direction)
                        assert all(abs(a-b) < .001 for a, b in zip(char["direction"], required_direction)), f"{key}: direction"
                    for char in selected:
                        if char["c"].isspace():
                            continue
                        if char["size"] >= 8:
                            assert char["size"] >= item["minimum_body_size"] - .02, f"{key}: shrunk body text"
                    expected_scripts = Counter(c["text"] for c in item["source_scripts"])
                    actual_scripts = Counter(c["c"] for c in selected if c["size"] < 8 and not c["c"].isspace())
                    assert expected_scripts == actual_scripts, f"{key}: body/script size mismatch"
                    assert all(c["size"] >= 6.45 for c in selected if not c["c"].isspace()), f"{key}: shrunk script"
                    _script_positions(selected, item)
                    if native_trace and "row" in item:
                        assert spans[key] == (item["rowspan"], item["colspan"]), f"{key}: merged cell geometry"
                        if source >= 30 or block.get("rule_style") == "full":
                            _cell_rules(rules, rect, key)
                        elif "cell_edge_rules" in block:
                            hs = block["cell_edge_rules"]["horizontal_boundaries"]
                            vs = block["cell_edge_rules"]["vertical_boundaries"]
                            _cell_rules(rules,rect,key,(item["row"] in hs,item["col"]+item["colspan"] in vs,
                                                       item["row"]+item["rowspan"] in hs,item["col"] in vs))
                    verified_items += 1
            # Whole-page inventory supplements, rather than replaces, ordered
            # per-item equality. It catches stray extra text outside regions.
            actual_inventory = Counter(c["c"] for c in chars if not c["c"].isspace())
            wanted_inventory = Counter(record["source_character_inventory"])
            assert actual_inventory == wanted_inventory, f"{prefix}: page character inventory mismatch"
            if native_trace and source in (16, 17, 18, 19):
                _dense_anchors(chars, rules, regions, prefix)
            if native_trace and 3 <= source <= 8:
                _train_anchors(chars,record,regions)
    return {"source_pages": list(pages), "verified_items": verified_items,
            "complete_37_pages": pages == tuple(range(1, 38)), "variant": "grid" if grid else "normal"}
