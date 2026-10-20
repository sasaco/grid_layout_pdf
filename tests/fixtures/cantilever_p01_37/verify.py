"""Independent PDF oracle; trace supplies regions, never expected content.

No builder, scene bounds, or production transform helper is imported here.
The checked glyphs, sizes, directions, image pixels and rules come from PDF.
"""

# The fixture writer uses this assertion-based test oracle as a publication
# gate. Refuse optimized execution instead of silently disabling those checks.
if not __debug__:
    raise RuntimeError("Cantilever verification requires assertions enabled; do not use -O or PYTHONOPTIMIZE")

from collections import Counter
from collections.abc import Iterable
from hashlib import sha256
from io import BytesIO
import json
from math import isfinite
from pathlib import Path
import re

import pymupdf
from PIL import Image


EXPECTED = Path(__file__).with_name("expected")
IDENTITY = (1, 0, 0, 1, 0, 0)
_SOURCE_SHA256 = "e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e"
# Independently frozen ID -> original-region assignments from reviewed commit
# 3da8b7cb71803c463029c68e155798f377c62e07, expected/p01.json ... p37.json.
# Each digest covers only sorted [item id, four float coordinates] pairs,
# serialized as ASCII JSON with separators=(",", ":") and allow_nan=False.
# Text, directions and scripts are deliberately excluded: they must still be
# checked against the actual original glyphs below. Do not regenerate these
# pins from a candidate expected record; a region change needs source review.
_SOURCE_REGION_SHA256 = {
    1: "2ec91e0965546c3f007e2b04a96d4e51d65ca565dd0e689861ba63a2c790630f",
    2: "e6eb4dd96dcedf031306a93297be000e4de71682b30e0a255fa5278ac2662ae6",
    3: "c808a067cfc86f21c6fb47bbd14fda6339c7928e57382a791aab13e9616a736a",
    4: "557712eb55d73efb2574524bdd00a6d6e64c926c6229af56291fbe3d5e87c3a3",
    5: "5765b0e990899ea5b965ae21824fc24378457c7e5fd3bd879b990999d79b8dbc",
    6: "61a6c5a0e0d38a23ab8b27dbffbe857a3010cf4e390947d49954677e05ccb615",
    7: "eef4ac51bc01942a951a4dcfac5b43bd7bd1952f76c47568206330515e7b4beb",
    8: "be6e47d11388335bfd6a9caebda41f66a0b3d44d433781899cc0c01aee5dc6f6",
    9: "20101987ea94bd28ddafd189c514abacace5be627227b328146891200ca4eed3",
    10: "d102139d117585a21643fefcb58335a3bd09688cb430586b7a80a1be3b253c34",
    11: "30a2c377ca8a1bc50e3bcd29ec9548dad54250a1c3019bd420e61b798fb991f9",
    12: "235881991913aaef812d75fdebf56aec00e6bb3d06ac6a44b825a8110c49bdbd",
    13: "70aad582523216d5660f1dcbfda55d43af5efe55a72eca8dc0b5daeec8d845b4",
    14: "a9db0c845d5e3badfe466d825087f6bfedcda0220254fe369e84fc4d174fb710",
    15: "c629d97370ba98d66684cf6dca705108e341b508a415172589b6dfc72875641c",
    16: "bb38b224649b859bf92780bdde43d03a0e1cf4d637e5366ee0618e81a4c1836d",
    17: "3607c007df4b1669154f3ea94a394e50bc71c199c7c5fe36f19d99a9702f58ad",
    18: "ee11b7fb8f0ca19c98fc78c69371e5bbbb5d7a01d3994f217925ffc36921e3a1",
    19: "9eb8f759e778516f6013091e512ea60e45de0c4bbd7df101841dce35f4c6c26e",
    20: "a2b112ae59ca414ae54c4e7ad16767c83d3aed4c94a3bbe8c9d6cedde415c625",
    21: "9f3900373918cc62f18b88f7e6523db29a755e835d7af274d56ca6896704e011",
    22: "513cb0312da9002594e971d9fb16f5c7017c97a518b3757d8924504e317c6b2e",
    23: "4717a71f0c1f28d10e065f07581b12564973d88dbaa10a0945937c827e3ebdf9",
    24: "23ac6477a1814dc8b002c4bdc436a664d2efca90184ccb8e41f8e1b84ed0b4d4",
    25: "f97036fc404a9ae3b713315ed4747a7d86705d04e8b5839c05c421310ab1a594",
    26: "d40e767ec27ed9c259572832299809ab73372baebffcde1b7c81aaad3516f615",
    27: "5c7ed59fcf69673d9ed025598045067c5602eadc5a0497c4bd0868e6b04abafd",
    28: "28ee4372ea5ad4a81c59310929ba0b05cfcfa35b210688d61e73b9758c5e005e",
    29: "2c33b6d659bc89799fa1b20f71b3f1f5eecef4d02704b5dc885978ec7eb8d23c",
    30: "b942c06e92567d1f24fef07d360d797f4aaf0a750fc00cb6e2ad5462f8d96eaf",
    31: "615f03cd1691dc81b30f1eabc9c869ae5fd9f9f086570809015691310d5c3bf3",
    32: "e6a804dbb2c47cb8ba1ff1c4d2bbea2778d82a6c2ddabd459e17b5410b4a3f7f",
    33: "bc4533a1f6cf30ab6c4a330e073e8d071f68bc89facf18aed037e63a8955a3b0",
    34: "fdbde4aef72d3f58d04279b808093c7c29be1eb6f1bc0f51ac89975a5db59e70",
    35: "dcc8a61d0ed98ec64a33994a2bf9c2a8d91c33c6bef6e78522c9445bc5df171e",
    36: "15c5e8b1a656baa787e8f2f9fec9113afae2d3f9cf9acafb69f5d8f9b70fc3af",
    37: "927afb397fe4178875424c9398fbc14d08589a756d39dd1e449af82205ff5a1b",
}
# Two original anchors this close are one alignment the output keeps (as builder.ALIGNED_SOURCE_PT:
# the original right-aligns results up to 5.04 pt apart in one column, p3 345.32-350.36 pt).
_ALIGNED_PT = 6.0
# PDF stroke widths of the border styles (FR-022): hair, thin, medium, thick.
_BORDER_STROKES = (.25, .5, 1.0, 1.5)
# A bracket bar spans at least two text lines (p20's shortest is 77 pt); a table rule is not filled.
_BAR_MIN_HEIGHT_PT = 20


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
        parts = [*node.get("prefix", []), *node.get("parts", [])]
        # Indent shifts its child right and records the shift as each part's indent_pt;
        # the child's own metadata (cells, children) stays relative to the child.
        indents = {part["metadata"].get("indent_pt", 0) for part in parts}
        assert len(indents) <= 1, f"{block_id}: parts with different indents"
        indent = next(iter(indents), 0)
        add(block_id, _box(matrix, indent, 0, node["width"] - indent, node["rows"] * pitch))
        for part in parts:
            placed = _compose(matrix, _translation(indent, part["row"] * pitch))
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


def _on_grid(value, origin, pitch, tolerance=.01):
    """Whether a page coordinate lies on a grid line (PDF extraction rounds to float32)."""
    steps = (value - origin) / pitch
    return abs(steps - round(steps)) * pitch <= tolerance


def _figure_corners(page):
    """{figure id: (x, y)} the top-left corner of each SourceFigure part placed in a native trace page."""
    corners = {}
    grid = page["profile"]["grid"]

    def walk(node, parent, default_pitch):
        matrix = _compose(parent, _translation(node.get("x_pt", 0), node.get("y_pt", 0)))
        pitch = node.get("row_pitch", default_pitch)
        parts = [*node.get("prefix", []), *node.get("parts", [])]
        indent = next(iter({part["metadata"].get("indent_pt", 0) for part in parts}), 0)
        for part in parts:
            placed = _compose(matrix, _translation(indent, part["row"] * pitch))
            metadata = part["metadata"]
            if "figure_id" in metadata:
                assert metadata["figure_id"] not in corners, f"duplicate figure {metadata['figure_id']}"
                corners[metadata["figure_id"]] = tuple(_box(placed, 0, 0, 0, 0)[:2])
            for child in metadata.get("children", []):
                walk(child, placed, pitch)

    for placement in page["metadata"]["placements"]:
        walk(placement, _translation(grid["origin_x"] + placement["col"] * grid["pitch_x"],
                                     grid["origin_y"] + placement["row"] * grid["pitch_y"]), grid["pitch_y"])
    return corners


def _images(page, source_page, manifest, grid, corners=None):
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
        _image_geometry(info["bbox"], match, source_page, grid)
        if corners is not None:
            # The drawn image is where its own figure block was placed.
            corner = corners.get(match["id"])
            assert corner is not None and all(abs(a - b) <= .01 for a, b in zip(info["bbox"][:2], corner)), \
                f"p{source_page:02}: image is not at its figure block"
        remaining.remove(match)


def _image_geometry(box, asset, source_page, grid):
    """The original crop at its physical size, its top-left corner on the page grid (FR-027).

    The figure's position follows the grid rules, not the original's
    coordinates (manifest target_bbox records where the original had it).
    An oracle_regions control has no page grid (``grid`` None).
    """
    x0,y0,x1,y1 = box
    source = asset["source_bbox"]
    assert 0 <= x0 < x1 <= 595 and 0 <= y0 < y1 <= 842, f"p{source_page:02}: image page bounds"
    assert abs(x1-x0-(source[2]-source[0])) < .1 and abs(y1-y0-(source[3]-source[1])) < .1, f"p{source_page:02}: image source physical dimensions"
    assert source[2]-source[0] < 500 and source[3]-source[1] < 500, f"p{source_page:02}: full-page image prohibited"
    assert grid is None or (_on_grid(x0, grid["origin_x"], grid["pitch_x"])
                            and _on_grid(y0, grid["origin_y"], grid["pitch_y"])), \
        f"p{source_page:02}: image region is off the page grid"


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
            grid = {"origin_x": page.profile.grid.origin_x, "origin_y": page.profile.grid.origin_y,
                    "pitch_x": page.profile.grid.pitch_x, "pitch_y": page.profile.grid.pitch_y}
            _image_geometry((command.x,command.y,command.x+command.width,command.y+command.height),match,source_page,grid)
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


def _side_bars(page):
    """Black filled vertical bars (SideRule draws solid styles as filled rectangles): (x, top, bottom, width)."""
    bars = []
    for drawing in page.get_drawings():
        fill = drawing.get("fill")
        if fill is None or max(fill) > .05 or drawing.get("color") is not None:
            continue
        for item in drawing["items"]:
            if item[0] == "re":
                box = item[1]
                if 0 < box.width <= 2 and box.height > _BAR_MIN_HEIGHT_PT:
                    bars.append(((box.x0 + box.x1) / 2, box.y0, box.y1, box.width))
    return _union_bars(bars)


def _union_bars(bars):
    """Join the per-part pieces of one bar (same x and width, touching ends)."""
    merged = []
    for x, top, bottom, width in sorted(bars, key=lambda bar: (round(bar[0], 3), bar[1])):
        if merged and abs(merged[-1][0] - x) < .01 and abs(merged[-1][3] - width) < .01 and top <= merged[-1][2] + .01:
            merged[-1] = (x, merged[-1][1], max(merged[-1][2], bottom), width)
        else:
            merged.append((x, top, bottom, width))
    return sorted(merged, key=lambda bar: (bar[1], bar[0]))


def _dense_anchors(chars, regions, record, grid):
    """The p16-p19 derivations: shared equation anchors on the page grid.

    Within each Rm group the three equals share one centre; the T1 and T2
    results and units share their columns, which are column lines (FR-027).
    """
    prefix = f"p{record['source_page']:02}"
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
    assert _on_grid(results[0], grid["origin_x"], grid["pitch_x"]), f"{prefix}: result anchor is off the grid"
    assert _on_grid(units[0], grid["origin_x"], grid["pitch_x"]), f"{prefix}: unit anchor is off the grid"


def _group_bars(chars, bars, regions, record, grid):
    """The p16-p20 bracket bars: one SideRule bar per derivation, on the page grid (FR-026, FR-027).

    Each derivation (the items between T1 and T2, and the items after T2) is
    bracketed by one bar of a border style's width, on a page grid column
    line, left of every glyph of those items and spanning their regions.
    """
    prefix = f"p{record['source_page']:02}"
    identifiers = [block["id"] for block in record["blocks"]]
    t1, t2 = identifiers.index(f"{prefix}-t1"), identifiers.index(f"{prefix}-t2")
    groups = (identifiers[t1 + 1:t2], identifiers[t2 + 1:])
    assert len(bars) == 2, f"{prefix}: group bar count {len(bars)}"
    for index, (bar, group) in enumerate(zip(bars, groups)):
        x, top, bottom, width = bar
        boxes = [regions[key] for key in group]
        assert any(abs(width - stroke) < .01 for stroke in _BORDER_STROKES), f"{prefix}: group bar {index} width"
        assert _on_grid(x, grid["origin_x"], grid["pitch_x"]), f"{prefix}: group bar {index} is off the grid"
        glyphs = [c for box in boxes for c in _inside(chars, box) if not c["c"].isspace()]
        assert glyphs and x + width / 2 < min(c["bbox"][0] for c in glyphs), f"{prefix}: group bar {index} is not left of its group"
        assert top <= min(box[1] for box in boxes) + .01 and bottom >= max(box[3] for box in boxes) - .01, \
            f"{prefix}: group bar {index} does not span its group"


def _source_bytes() -> bytes:
    """Read independently hashed source bytes, never authored placement data."""
    sources = tuple((Path(__file__).resolve().parents[2] / "output").glob("13_*.pdf"))
    assert len(sources) == 1, "source PDF identity is ambiguous or missing"
    data = sources[0].read_bytes()
    assert sha256(data).hexdigest() == _SOURCE_SHA256, "source PDF hash mismatch"
    return data


def _source_pages(source_pages: Iterable[int]) -> tuple[int, ...]:
    pages = tuple(source_pages)
    if (not pages or any(type(n) is not int or not 1 <= n <= 37 for n in pages)
            or len(set(pages)) != len(pages) or pages != tuple(sorted(pages))):
        raise ValueError("source pages must be unique, increasing integers in 1..37")
    return pages


def _source_records(pages: Iterable[int]) -> list[dict]:
    records = []
    for number in pages:
        file = EXPECTED / f"p{number:02}.json"
        if not file.is_file():
            raise ValueError(f"source oracle missing for p{number:02}")
        records.append(json.loads(file.read_text(encoding="utf-8")))
    return records


def _check_source_regions(record: dict) -> None:
    """Pin semantic identity before using a candidate record's glyph regions."""
    number = record["source_page"]
    message = f"p{number:02}: original region assignment differs from reviewed source"
    regions = []
    for block in record["blocks"]:
        for item in block.get("cells", [block]):
            box = item["source_bbox"]
            assert isinstance(item["id"], str), message
            assert isinstance(box, (tuple, list)) and len(box) == 4, message
            assert all(type(value) in (int, float) and isfinite(value) for value in box), message
            regions.append((item["id"], [float(value) for value in box]))
    canonical = json.dumps(sorted(regions), ensure_ascii=True,
                           separators=(",", ":"), allow_nan=False).encode("ascii")
    assert sha256(canonical).hexdigest() == _SOURCE_REGION_SHA256[number], message


def _original_item(chars: list[dict], item: dict) -> None:
    """Check transcription against geometric reading order, including scripts.

    Direction is inferred from the original full-size glyphs. Expected text,
    script roles, and authored placement data never determine the ordering.
    """
    key = item["id"]
    if not chars:
        assert not _compact(item["text"]), f"{key}: original text order: empty region"
        assert not item["source_scripts"], f"{key}: original script in empty region"
        return
    major = [char for char in chars if char["size"] >= 8]
    directions = Counter(char["direction"] for char in major or chars)
    direction = max(directions, key=lambda value: (directions[value], value))
    assert tuple(item["direction"]) == direction, f"{key}: original direction"
    ordered = [(char, baseline) for line, baseline in _ordered_lines(chars, direction)
               for char in line]
    actual = "".join(char["c"] for char, _ in ordered)
    wanted = _compact(item["text"])
    assert actual == wanted, f"{key}: original text order {actual!r} != expected {wanted!r}"
    overrides = {entry["character_index"]: tuple(entry["direction"])
                 for entry in item.get("source_direction_overrides", [])}
    assert len(overrides) == len(item.get("source_direction_overrides", [])), f"{key}: original direction duplicates"
    assert all(type(index) is int and 0 <= index < len(ordered) for index in overrides), f"{key}: original direction index"
    scripts = []
    dx, dy = direction
    for index, (char, baseline) in enumerate(ordered):
        assert char["direction"] == overrides.get(index, direction), f"{key}: original direction at {index}"
        if char["size"] < 8:
            x, y = char["origin"]
            delta = -dy*x + dx*y - baseline
            assert abs(delta) >= .5, f"{key}: original script has ambiguous baseline"
            scripts.append((index, char["c"], "subscript" if delta > 0 else "superscript"))
    expected_scripts = [(script["character_index"], script["text"], script["role"])
                        for script in item["source_scripts"]]
    assert scripts == expected_scripts, f"{key}: original script order, text or role"


def verify_source_order(source_pages: Iterable[int], *, records: Iterable[dict] | None = None) -> dict:
    """Validate expected records directly against the immutable original PDF.

    This is additional to output-PDF checks. It retains the source inventory,
    marker/figure/page-number exclusions, and once-only glyph coverage, so a
    coordinated change to authored content and expected text cannot pass.
    Reviewed ID-to-region pins are checked before selecting original glyphs.
    ``records`` supports inspecting a proposed oracle without writing it.
    """
    pages = _source_pages(source_pages)
    records = _source_records(pages) if records is None else list(records)
    assert len(records) == len(pages), "original source record count"
    assets = json.loads(Path(__file__).with_name("assets").joinpath("metadata.json").read_text(encoding="utf-8"))["figures"]
    verified_items = 0
    with pymupdf.open(stream=_source_bytes(), filetype="pdf") as source:
        for number, record in zip(pages, records):
            prefix = f"p{number:02}"
            assert record["source_page"] == number, f"{prefix}: original source page identity"
            assert record["source_sha256"] == _SOURCE_SHA256, f"{prefix}: original source PDF hash"
            _check_source_regions(record)
            chars = [char for char in _chars(source[number-1]) if not char["c"].isspace()]
            omitted = _inside(chars, (500, 30, 570, 62))
            assert _compact(_reading(omitted, (1, 0))) == f"13-{number}", f"{prefix}: original page number"
            figure_boxes = [asset["source_bbox"] for asset in assets if asset["source_page"] == number]
            excluded = {id(char) for char in omitted}
            excluded.update(id(char) for box in figure_boxes for char in _inside(chars, box))
            chars = [char for char in chars if id(char) not in excluded]
            assert Counter(char["c"] for char in chars) == Counter(record["source_character_inventory"]), f"{prefix}: original character inventory"
            assert sum(char["c"] == "※" for char in chars) == record["marker_count"], f"{prefix}: original marker count"
            content = [char for char in chars if char["c"] != "※"]
            covered = Counter()
            identifiers = set()
            for block in record["blocks"]:
                for item in block.get("cells", [block]):
                    assert item["id"] not in identifiers, f"{prefix}: duplicate original item identity"
                    identifiers.add(item["id"])
                    selected = _inside(content, item["source_bbox"])
                    _original_item(selected, item)
                    covered.update(id(char) for char in selected)
                    verified_items += 1
            assert covered == Counter({id(char): 1 for char in content}), f"{prefix}: original glyph coverage"
    return {"source_pages": list(pages), "verified_items": verified_items,
            "complete_37_pages": pages == tuple(range(1, 38))}


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


def _train_anchors(chars, record, regions, grid, source_chars=None):
    """p3-p8 train equations: result end, unit start and equals centre on page grid column lines.

    Where the original drew two equations' anchor at the same place (within
    _ALIGNED_PT, 6 pt), the output shares that anchor's column too (FR-027 replaces the
    original's positions with the grid, not the original's alignment).
    ``source_chars`` are the original page's glyphs.
    """
    found = []
    for item in record["blocks"]:
        if item["kind"] != "equation":
            continue
        anchors = _train_item_anchors(_inside(chars, regions[item["id"]]), item["id"])
        for label, value in zip(("result", "unit", "equal"), anchors):
            assert _on_grid(value, grid["origin_x"], grid["pitch_x"]), f"{item['id']}: {label} anchor is off the grid"
        original = (_train_item_anchors(_inside(source_chars, item["source_bbox"]), item["id"])
                    if source_chars is not None else None)
        found.append((item["id"], anchors, original))
    for index, label in enumerate(("result", "unit", "equal")):
        # Every pair, not only neighbours: an unaligned equation between two aligned ones hides nothing.
        for position, (key_a, out_a, src_a) in enumerate(found):
            for key_b, out_b, src_b in found[position + 1:]:
                if src_a is not None and abs(src_a[index] - src_b[index]) <= _ALIGNED_PT:
                    assert abs(out_a[index] - out_b[index]) < .05, \
                        f"{key_b}: {label} anchor is not shared with {key_a} as in the original"


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
    pages = _source_pages(source_pages)
    if not isinstance(grid, bool):
        raise ValueError("grid must be boolean")
    if trace is None:
        raise ValueError("source item regions require a layout trace")
    if isinstance(trace, (str, Path)):
        trace = json.loads(Path(trace).read_text(encoding="utf-8"))
    expected = _source_records(pages)
    source_order = verify_source_order(pages, records=expected)
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
            _images(page, source, manifest, trace_page["profile"]["grid"] if native_trace else None,
                    _figure_corners(trace_page) if native_trace else None)
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
                _dense_anchors(chars, regions, record, trace_page["profile"]["grid"])
            if native_trace and source in (16, 17, 18, 19, 20):
                _group_bars(chars, _side_bars(page), regions, record, trace_page["profile"]["grid"])
            if native_trace and 3 <= source <= 8:
                with pymupdf.open(stream=_source_bytes(), filetype="pdf") as original:
                    source_chars = _chars(original[source - 1])
                _train_anchors(chars, record, regions, trace_page["profile"]["grid"], source_chars)
    return {"source_pages": list(pages), "verified_items": verified_items,
            "complete_37_pages": pages == tuple(range(1, 38)), "variant": "grid" if grid else "normal",
            "source_order": source_order}
