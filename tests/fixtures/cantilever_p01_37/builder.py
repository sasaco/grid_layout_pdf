"""Semantic, display-only input assembly for the fixed-page cantilever fixture.

FR-027: every page is laid out by the library's own parts on the page grid.
p1-p29 use the A4.pdf grid (CANTILEVER_SOURCE_A4); p30-p37 use a page grid
whose swapped local grid has the original rotated tables' 14.52 pt columns and
10.8 pt rows (user decision, 2026-10-20). The authored pages/*.json give the
content and the vertical flow (Stack, Spacer); source-layout.json gives where
the original placed each block, which is snapped to whole grid columns:
indents, equals/result/unit anchors, table column widths and row heights. The
original's own coordinates are never replayed.

This module never reads the independent expected/ directory. The fixture is not
a calculator, PDF parser, or a general serialization API for the library.
"""

from dataclasses import dataclass, field, replace
from collections.abc import Mapping
from hashlib import sha256
from io import BytesIO
from copy import deepcopy
import functools
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

from gridlayoutpdf import (
    BorderStyle, Cell, CellLines, Columns, Document, Equation, EquationAnchors, EquationGroup, LayoutContext,
    FontRegistry, Fraction, GridSpec, Indent, Insets, KeepTogether, LayoutOverflowError, Literal,
    MathBlock, Operator, PageBreak, PageProfile, PageSection, Paragraph, QuarterTurn, RasterImage,
    ReportStyle, Row, Script, SideRule, Spacer, Stack, Table, TableBorders, TermStop, Text, TextStyle, measure_block,
    Image as LayoutImage,
)
from gridlayoutpdf.equations import excel_cell_padding_pt
from gridlayoutpdf.renderers.xlsx._units import PIXELS_PER_PT, excel_column_width_pt


FIXTURE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = FIXTURE_ROOT.parents[2]
SOURCE_PAGES = tuple(range(1, 38))
PROOF_PAGES = (16, 17, 26, 30, 36)
ROTATED_PAGES = tuple(range(30, 38))
# The A4.pdf grid (pitch 16.08 x 15.48) with 31 x 48 cells: the original's p24 table bottom and
# figure widths need one more column and row than the product's A4_PORTRAIT_REFERENCE.
SOURCE_PROFILE = PageProfile("CANTILEVER_SOURCE_A4", 595, 842, GridSpec(50.88, 54.598, 16.08, 15.48, 31, 48))
# p30-p37 (2026-10-20 user decision): the swapped local grid has the original rotated tables'
# 14.52 pt columns and 10.8 pt rows. Same origin; the largest whole columns and rows inside the
# CANTILEVER_SOURCE_A4 body (right 549.36, bottom 797.638 pt).
ROTATED_PROFILE = PageProfile("CANTILEVER_ROTATED_A4", 595, 842, GridSpec(50.88, 54.598, 10.8, 14.52, 46, 51))

# The original's left text edge (p1 title) and indentation step, read from source-layout.json:
# its heading levels sit at 53.52 + 14.52 k pt. Level k is placed k grid columns in (FR-027).
_SOURCE_LEFT, _SOURCE_INDENT_STEP = 53.52, 14.52
# Horizontal cell padding of table text, between the text and its rule's ink.
_CELL_PADDING = 2.0
# Script offsets of the original (pt below / above the base's baseline).
_SUBSCRIPT_DROP, _SUPERSCRIPT_RISE = 1.92, 2.4
# On p30-p37 a cell line takes one 10.8 pt local row, and its glyph boxes must stay in it (FR-027:
# the grid Excel puts a line in one row). A 10 pt base (8.59 pt ascent) with the original's 1.92 pt
# drop of a 6.5 pt subscript (0.92 pt descent) needs 11.43 pt; 1.0 pt leaves 0.29 pt to spare.
_ROTATED_SUBSCRIPT_DROP = 1.0
# The library Script starts its scripts 0.1 em after the base advance (math.Script).
_SCRIPT_X_EM = .1


def _appearance():
    key = "cantilever_fixture_appearance"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, FIXTURE_ROOT / "appearance.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


# Font names from the original PDF; resolved from the Windows font folder (FR-024).
BODY_FONT, HEADING_FONT = "MS Mincho", "MS Gothic"
SOURCE_STYLE = ReportStyle(body=TextStyle(BODY_FONT), heading=TextStyle(BODY_FONT, size=12))


# Source rule widths in pt become border styles (FR-022, FR-027): the original's
# 0.12 pt hairlines become hair (0.25 pt, the minimum) and its 0.96 pt rules
# medium (1.0 pt). The hand-authored pages/*.json widths map the same way:
# 0.24 -> hair, 0.4/0.5 -> thin, 0.7 and 1 (the source's heavy rules) -> medium.
_RULE_STYLES = ((0.0, None), (0.12, BorderStyle.HAIR), (0.1201, BorderStyle.HAIR),
                (0.24, BorderStyle.HAIR), (0.4, BorderStyle.THIN), (0.5, BorderStyle.THIN),
                (0.7, BorderStyle.MEDIUM), (0.96, BorderStyle.MEDIUM), (1.0, BorderStyle.MEDIUM))


def rule_style(width):
    """Return the border style that replaces an authored rule width, or None for 0."""
    for source, style in _RULE_STYLES:
        if abs(width - source) < 1e-9:
            return style
    raise ValueError(f"no border style is assigned to the authored rule width {width} pt")


def rule_thickness(width):
    style = rule_style(width)
    return 0.0 if style is None else style.thickness


def _rule_borders(data, default):
    """Boundary styles for every authored rule, over the table's default style."""
    for key, count in (("horizontal_rules", len(data.get("rows", data.get("row_heights", ()))) + 1),
                       ("vertical_rules", len(data["columns"]) + 1)):
        if key in data and len(data[key]) != count:
            raise ValueError(f"{data.get('id', 'table')}: {key} must list {count} boundary widths")
    return TableBorders(rule_style(default),
                        horizontal={index: rule_style(width) for index, width in enumerate(data.get("horizontal_rules", ()))},
                        vertical={index: rule_style(width) for index, width in enumerate(data.get("vertical_rules", ()))})


@functools.cache
def _fixture_json(name):
    """One fixture input, parsed once. Read-only: the public loaders hand out copies."""
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


# Profile keys the page grid (sizes, spacing) and the library Script (script size and offsets) replace.
_OBSOLETE_PROFILE_KEYS = frozenset({"body_size", "rotated_body_size", "spacing_ratio", "script_size_ratio",
                                    "subscript_offset", "superscript_offset"})


def _reject_obsolete_profile_keys(profile):
    found = _OBSOLETE_PROFILE_KEYS & set(profile)
    if found:
        raise ValueError(f"obsolete font-profile key(s) {sorted(found)}")


def font_profile():
    profile = deepcopy(_fixture_json("font-profile.json"))
    _reject_obsolete_profile_keys(profile)
    return profile


def load_manifest():
    return deepcopy(_fixture_json("manifest.json"))


def source_layout():
    return deepcopy(_fixture_json("source-layout.json"))


def _profiles():
    """The read-only font-profile items (see _fixture_json)."""
    return _fixture_json("font-profile.json")["items"]


def page_profile(number):
    """The fixed page profile of one original page."""
    return ROTATED_PROFILE if number in ROTATED_PAGES else SOURCE_PROFILE


def _selection(source_pages):
    pages = tuple(source_pages)
    if (not pages or any(type(number) is not int or number not in SOURCE_PAGES for number in pages)
            or tuple(sorted(set(pages))) != pages):
        raise ValueError("source_pages must be unique, increasing original pages 1..37")
    return pages


def _nearest(value):
    """The nearest whole number, halves rounded up (Python's round() rounds them to even)."""
    return math.floor(value + .5)


def indent_columns(x, number):
    """Grid columns from the body's left edge for a text block the original placed at x pt.

    A4 pages map the original's indentation levels (53.52 + 14.52 k pt) to k
    columns, so the heading levels and the lines under them keep their order
    and distinct levels stay distinct (the nearest column would merge 140.64
    and 155.16 pt). The rotated pages use the nearest column of their own grid.
    Figures take their nearest column (``anchor_column``).
    """
    if number in ROTATED_PAGES:
        return max(0, anchor_column(x, number))
    return max(0, _nearest((x - _SOURCE_LEFT) / _SOURCE_INDENT_STEP))


def anchor_column(x, number):
    """The nearest page grid column boundary (from the body's left edge) to x pt."""
    grid = page_profile(number).grid
    return _nearest((x - grid.origin_x) / grid.pitch_x)


def math_node(value):
    """Decode explicitly authored math into library nodes, without interpreting display strings."""
    if isinstance(value, str):
        return Literal(value)
    kind = value["type"]
    if kind == "row":
        return Row(*(math_node(item) for item in value["items"]), gap=value.get("gap", 0))
    if kind == "script":
        sub = math_node(value["sub"]) if "sub" in value else None
        sup = math_node(value["sup"]) if "sup" in value else None
        # The library Script (scale 0.65: 6.5 pt at 10 pt) at the original's script offsets.
        return Script(math_node(value["base"]), superscript=sup, subscript=sub,
                      superscript_rise=_SUPERSCRIPT_RISE if sup is not None else None,
                      subscript_drop=_SUBSCRIPT_DROP if sub is not None else None)
    if kind == "operator":
        return Operator(value["text"])
    if kind == "fraction":
        return Fraction(math_node(value["numerator"]), math_node(value["denominator"]))
    raise ValueError(f"unknown fixture math node {kind!r}")


def _with_subscript_drop(node, drop):
    """``node`` with every subscript set ``drop`` pt below its base (rows and scripts inside it too)."""
    if isinstance(node, Row):
        return Row(*(_with_subscript_drop(item, drop) for item in node.items), gap=node.gap)
    if isinstance(node, Script):
        return replace(node, base=_with_subscript_drop(node.base, drop),
                       subscript=None if node.subscript is None else _with_subscript_drop(node.subscript, drop),
                       superscript=None if node.superscript is None else _with_subscript_drop(node.superscript, drop),
                       subscript_drop=drop if node.subscript is not None else node.subscript_drop)
    if isinstance(node, Fraction):
        return replace(node, numerator=_with_subscript_drop(node.numerator, drop),
                       denominator=_with_subscript_drop(node.denominator, drop))
    return node


def _flatten(value):
    if isinstance(value, str):
        return value
    kind = value["type"]
    if kind == "row":
        return "".join(_flatten(item) for item in value["items"])
    if kind == "script":
        return "".join(_flatten(value[key]) for key in ("base", "sub", "sup") if key in value)
    if kind == "operator":
        return value["text"]
    if kind == "fraction":
        return _flatten(value["numerator"]) + _flatten(value["denominator"])
    raise ValueError(f"unknown fixture math node {kind!r}")


def _shear(node, value, atoms):
    """Apply the authored synthetic italic to whole semantic atoms (p1 D), never glyph positions."""
    if not atoms:
        return node
    if isinstance(value, str):
        atom = next((atom for atom in atoms if atom["text"] == value), None)
        if atom is None:
            return node
        # The original's script gap, measured from the base advance (the library Script
        # already leaves 0.1 em; Sheared widens the base by the rest at the measured size).
        return _appearance().Sheared(node, atom["shear_x"], script_gap=atom.get("script_gap"),
                                     script_em=_SCRIPT_X_EM)
    kind = value["type"]
    if kind == "row":
        return Row(*(_shear(child, item, atoms) for child, item in zip(node.items, value["items"])), gap=node.gap)
    if kind == "script":
        return replace(node, base=_shear(node.base, value["base"], atoms))
    return node


def _cell_line(value, profile, *, turned=False):
    """One authored cell line: a glyph the original turned in a vertical heading, or a library node."""
    if turned:
        if not (isinstance(value, str) and value in _fixture_json("font-profile.json")["vertical_glyphs"]):
            raise ValueError(f"no vertical glyph is defined for the turned cell line {value!r}")
        return _appearance().VerticalGlyph(value)
    return _shear(math_node(value), value, profile.get("shear_atoms", ()))


@dataclass(frozen=True)
class SourceFigure:
    """An allowed figure crop at its original physical dimensions, without fit scaling."""

    metadata: dict
    asset_root: Path = FIXTURE_ROOT
    block_id: str = ""

    def measure(self, context, available_width):
        from PIL import Image, ImageOps
        asset_root = self.asset_root.resolve()
        path = (asset_root / self.metadata["file"]).resolve()
        if asset_root not in path.parents:
            raise ValueError(f"{self.block_id}: figure asset escapes its directory")
        data = path.read_bytes()
        if sha256(data).hexdigest() != self.metadata["sha256"]:
            raise ValueError(f"{self.block_id}: figure asset hash changed")
        with Image.open(BytesIO(data)) as source:
            normalized = ImageOps.exif_transpose(source).convert("RGB")
            if (normalized.width, normalized.height) != (self.metadata["pixel_width"], self.metadata["pixel_height"]):
                raise ValueError(f"{self.block_id}: figure pixel dimensions changed")
            if sha256(normalized.tobytes()).hexdigest() != self.metadata["decoded_pixel_sha256"]:
                raise ValueError(f"{self.block_id}: figure decoded pixel hash changed")
            output = BytesIO()
            normalized.save(output, format="PNG")
        normalized_data = output.getvalue()
        if ("normalized_byte_sha256" in self.metadata
                and sha256(normalized_data).hexdigest() != self.metadata["normalized_byte_sha256"]):
            raise ValueError(f"{self.block_id}: figure normalized byte hash changed")
        x0, y0, x1, y1 = self.metadata["source_bbox"]
        width, height = x1 - x0, y1 - y0
        measured = LayoutImage(path, width_pt=width, height_pt=height, align="left", valign="top",
                               block_id=self.block_id).measure(context, available_width)
        # Validate the bytes actually retained by Image, not only our earlier
        # read: the asset could have changed between provenance and measurement.
        if len(measured.commands) != 1 or not isinstance(measured.commands[0], RasterImage):
            raise ValueError(f"{self.block_id}: measured figure must contain one raster snapshot")
        command = measured.commands[0]
        if (command.x, command.y, command.width, command.height) != (0, 0, width, height):
            raise ValueError(f"{self.block_id}: measured figure physical dimensions changed")
        with Image.open(BytesIO(command.data)) as snapshot:
            if snapshot.size != (self.metadata["pixel_width"], self.metadata["pixel_height"]):
                raise ValueError(f"{self.block_id}: measured figure pixel dimensions changed")
            if sha256(snapshot.convert("RGB").tobytes()).hexdigest() != self.metadata["decoded_pixel_sha256"]:
                raise ValueError(f"{self.block_id}: measured figure pixel hash changed")
        normalized_hash = self.metadata.get("normalized_byte_sha256", sha256(normalized_data).hexdigest())
        if sha256(command.data).hexdigest() != normalized_hash:
            raise ValueError(f"{self.block_id}: measured figure normalized byte hash changed")
        return replace(measured, parts=tuple(replace(part, metadata={**part.metadata,
                       "figure_id": self.metadata["id"], "source_page": self.metadata["source_page"]})
                       for part in measured.parts))


def _style(data):
    source = _profiles().get(data.get("id"), {})
    return TextStyle(font=data.get("font", source.get("font", BODY_FONT)),
                     size=source.get("size", data.get("size", 10)), tracking=data.get("tracking", 0))


@dataclass(frozen=True)
class _Page:
    """Inputs of one original page: its number, fonts, profile and source geometry by block ID."""

    number: int
    fonts: FontRegistry
    geometry: Mapping
    leaves: tuple = ()
    # Anchors of a family of sibling equation groups, found once (see _equations).
    anchors: dict = field(default_factory=dict, compare=False, repr=False)

    @property
    def grid(self):
        return page_profile(self.number).grid

    def place(self, data, block, container, columns):
        """Indent ``block`` from its container's left edge to the original's grid column."""
        column = self.column(data, container) - container
        if column < 0:
            raise LayoutOverflowError(f"原本再現できず: {data['id']} lies left of its container",
                                      block_id=data["id"], needed=-column, available=0)
        if column >= columns:
            raise LayoutOverflowError(f"原本再現できず: {data['id']} starts outside the body",
                                      block_id=data["id"], needed=column + 1, available=columns)
        return Indent(block, column * self.grid.pitch_x) if column else block

    def column(self, data, container):
        """The grid column (from the body's left edge) of a leaf the original placed."""
        geometry = self.geometry.get(data["id"])
        if geometry is None or "x" not in geometry:
            raise ValueError(f"{data['id']}: the original's position is missing from source-layout.json")
        if geometry["kind"] == "image":
            return max(0, anchor_column(geometry["x"], self.number))
        x = equation_left(geometry) if geometry["kind"] == "equations" else geometry["x"]
        return indent_columns(x, self.number)


def build_block(data, page, *, container=0, columns=None):
    """Build one authored block whose container starts ``container`` columns into the body."""
    kind, identifier = data["type"], data["id"]
    columns = page.grid.columns - container if columns is None else columns
    if kind == "spacer":
        return KeepTogether(Spacer(data["rows"]), block_id=identifier)
    if kind == "stack":
        return Stack(*(build_block(child, page, container=container, columns=columns)
                       for child in data["children"]), block_id=identifier)
    if kind == "columns":
        rules = [child for child in data["children"] if child["type"] == "rule"]
        if rules:
            return _side_rule(data, rules, page, container, columns)
        children, start = [], container
        for child, span in zip(data["children"], data["col_spans"]):
            children.append(build_block(child, page, container=start, columns=span))
            start += span + data.get("gap_cols", 0)
        return Columns(*children, col_spans=data["col_spans"], gap_cols=data.get("gap_cols", 0), block_id=identifier)
    if kind == "rule":
        raise ValueError(f"{identifier}: a source rule must bracket its derivation in a columns block")
    leaf_columns = columns - max(0, page.column(data, container) - container)
    return page.place(data, _leaf(data, page, container, leaf_columns), container, columns)


def _side_rule(data, rules, page, container, columns):
    """A source bracket bar (Figure+Line before FR-026) becomes a library SideRule on a column line."""
    if len(rules) != 1 or len(data["children"]) != 2:
        raise ValueError(f"{data['id']}: a ruled columns block needs one rule and one derivation")
    body = next(child for child in data["children"] if child["type"] != "rule")
    if body["type"] != "stack":
        raise ValueError(f"{data['id']}: a source rule brackets a stack of derivation lines")
    derivation = build_block(body, page, container=container, columns=columns)
    bar = page.geometry[rules[0]["id"]]
    # The bar stays left of the derivation it brackets, on a column line.
    content = min(page.column(leaf, container) for leaf in _leaves(body)) - container
    x = min(indent_columns(bar["x"], page.number) - container, content - 1)
    if x < 1:
        raise LayoutOverflowError(f"原本再現できず: {data['id']} bar has no column between its container and "
                                  "its derivation",
                                  block_id=data["id"], needed=1, available=x)
    # SideRule reports its child's parts under its own ID, so it carries the derivation's ID
    # and an outer Stack keeps the authored columns ID.
    ruled = SideRule(Stack(*derivation.children), x * page.grid.pitch_x, style=BorderStyle.THIN,
                     block_id=body["id"])
    return Stack(ruled, block_id=data["id"])


def _leaves(data):
    if data["type"] in ("stack", "columns"):
        for child in data["children"]:
            yield from _leaves(child)
    elif data["type"] != "spacer":
        yield data


def _leaf(data, page, container, columns):
    kind, identifier = data["type"], data["id"]
    if kind == "paragraph":
        runs = _profiles().get(identifier, {}).get("font_runs")
        if runs:
            return _font_runs(data, runs, page, container, columns)
        return Paragraph(data["text"], style=_style(data), block_id=identifier)
    if kind == "math":
        runs = _profiles().get(identifier, {}).get("font_runs")
        if runs:
            return _font_runs(data, runs, page, container, columns)
        return MathBlock(math_node(data["content"]), style=_style(data), block_id=identifier)
    if kind == "image":
        entries = [figure for figure in _fixture_json("manifest.json")["figures"] if figure["id"] == data["image_id"]]
        if len(entries) != 1:
            raise ValueError(f"{identifier}: image_id must identify one registered figure")
        return SourceFigure(deepcopy(entries[0]), block_id=identifier)
    if kind == "equations":
        return _equations(data, page, container, columns)
    if kind == "table":
        return _table(data, page)
    raise ValueError(f"{identifier}: unsupported fixture block {kind!r}")


def _run_pieces(data, runs):
    """Split a mixed-font heading at its runs' character boundaries (spaces not counted).

    A paragraph splits its text; a math heading splits its top-level Row items,
    and a run boundary inside an item is an error.
    """
    boundaries = [run["stop"] for run in runs[:-1]]
    if data["type"] == "paragraph":
        text, pieces, start, count = data["text"], [], 0, 0
        for stop, char in enumerate(text, 1):
            count += not char.isspace()
            if boundaries and count == boundaries[0]:
                pieces.append(text[start:stop])
                start, boundaries = stop, boundaries[1:]
        pieces.append(text[start:])
        return [piece.strip() for piece in pieces]
    content = data["content"]
    if not (isinstance(content, dict) and content.get("type") == "row"):
        content = {"type": "row", "items": [content], "gap": 0}
    items = content["items"]
    pieces, current, count = [], [], 0
    for item in items:
        current.append(item)
        count += len(re.sub(r"\s", "", _flatten(item)))
        if boundaries and count >= boundaries[0]:
            if count != boundaries[0]:
                raise ValueError(f"{data['id']}: a font run boundary cuts a math item")
            pieces.append(current)
            current, boundaries = [], boundaries[1:]
    pieces.append(current)
    return [{"type": "row", "items": piece, "gap": content.get("gap", 0)} for piece in pieces]


def _font_runs(data, runs, page, container, columns):
    """A heading whose original changes font mid-line: one block per run, each from a column line.

    A run with an authored "x" starts at the original's nearest column; any
    other run starts at the first column after the previous run.
    """
    pieces = _run_pieces(data, runs)
    if len(pieces) != len(runs) or any(not (piece.strip() if isinstance(piece, str) else piece["items"])
                                       for piece in pieces):
        raise ValueError(f"{data['id']}: font runs do not cover the heading")
    style = _style(data)
    blocks, spans, cursor = [], [], 0
    for index, (piece, run) in enumerate(zip(pieces, runs)):
        run_style = replace(style, font=run["font"])
        identifier = f"{data['id']}-run{index}"
        if isinstance(piece, str):
            blocks.append(Paragraph(piece, style=run_style, block_id=identifier))
            width = page.fonts.measure(piece, run_style).width
        else:
            node = math_node(piece)
            blocks.append(MathBlock(node, style=run_style, block_id=identifier))
            width = node.measure(page.fonts, run_style).width
        if index + 1 < len(runs):
            following = runs[index + 1]
            fit = cursor + math.ceil(width / page.grid.pitch_x - 1e-9)
            # A run the original started at x keeps that distance from the heading's left edge.
            end = (_nearest((following["x"] - page.geometry[data["id"]]["x"]) / page.grid.pitch_x)
                   if "x" in following else fit)
            if end < fit:
                raise LayoutOverflowError(f"原本再現できず: {data['id']} font runs do not fit their columns",
                                          block_id=data["id"], needed=fit, available=end)
            spans.append(end - cursor)
            cursor = end
        else:
            spans.append(columns - cursor)
    if any(span < 1 for span in spans):
        raise LayoutOverflowError(f"原本再現できず: {data['id']} font runs do not fit their columns",
                                  block_id=data["id"], needed=sum(max(1, span) for span in spans), available=columns)
    return Columns(*blocks, col_spans=tuple(spans), gap_cols=0, block_id=data["id"])


def _source_lines(rhs, record, identifier):
    """The right-hand side split where the original started a new line (spaces not counted).

    The original's line texts must end at Row item boundaries. One line gives
    the right-hand side unchanged.
    """
    lines = [line.get("text") for line in record.get("rhs_lines", ())]
    if len(lines) > 1 and any(line is None for line in lines):
        raise ValueError(f"{identifier}: an original right-hand-side line has no text")
    node = math_node(rhs)
    if len(lines) <= 1:
        return [node]
    if not (isinstance(rhs, dict) and rhs.get("type") == "row"):
        raise ValueError(f"{identifier}: a multi-line right-hand side must be an authored row")
    boundaries, total = [], 0
    for line in lines[:-1]:
        total += len(re.sub(r"\s", "", line))
        boundaries.append(total)
    pieces, current, count = [], [], 0
    for item, child in zip(rhs["items"], node.items):
        current.append(child)
        count += len(re.sub(r"\s", "", _flatten(item)))
        if boundaries and count >= boundaries[0]:
            if count != boundaries[0]:
                raise ValueError(f"{identifier}: an original line break cuts a math item")
            pieces.append(current)
            current, boundaries = [], boundaries[1:]
    if boundaries or not current:
        raise ValueError(f"{identifier}: original line breaks do not split the right-hand side")
    pieces.append(current)
    return [Row(*piece, gap=node.gap) for piece in pieces]


def _equation_list(data, page):
    """The Equations of one authored group, each original line of a wrapped right-hand side its own.

    The library places a wrapped equation's result on its last line, but the
    original puts it on the first (p1, p2 R_B). Such an equation is written as
    its first line with the result, followed by one equation per further line
    with no left-hand side and a blank relation: the same characters in the
    original's reading order, the continuation starting at the shared
    right-hand-side column. A result the original set on a line of its own
    (p9-p11 horizontal forces) becomes an equation of its own in the same way.
    """
    identifier = data["id"]
    records = page.geometry[identifier].get("equations", ())
    if len(records) != len(data["equations"]):
        raise ValueError(f"{identifier}: {len(data['equations'])} authored equations, "
                         f"{len(records)} in the original's layout")
    equations = []
    for index, (item, record) in enumerate(zip(data["equations"], records)):
        result = {key: math_node(item[key]) for key in ("result", "unit") if key in item}
        if "result_relation" in item:
            result["result_relation"] = item["result_relation"]
        options = {key: item[key] for key in ("relation", "label") if key in item}
        lines = _source_lines(item["rhs"], record, f"{identifier}-{index}")
        # The original set this result on a line of its own, below the right-hand side.
        own_line = "result_baseline" in record and abs(record["result_baseline"] - record["baseline"]) > 4
        name = f"{identifier}-{index}"
        equations.append(Equation(math_node(item["lhs"]), lines[0], block_id=name,
                                  **options, **({} if own_line else result)))
        equations.extend(Equation(Literal(""), line, relation=" ", block_id=f"{name}-line{number}")
                         for number, line in enumerate(lines[1:], 2))
        if own_line and "result" not in result:
            raise ValueError(f"{name}: the original's separate result line has no result")
        if own_line:
            equations.append(Equation(Literal(""), Literal(""), relation=" ", block_id=f"{name}-result", **result))
    return equations


# Original anchors this close (pt) were one alignment: the original's right-aligned results end
# up to 5.04 pt apart in one column (p3: 345.32, 347.84, 350.36 pt), less than a third of a column.
ALIGNED_SOURCE_PT = 6.0


def _source_positions(geometry):
    """Each anchor of a group in the original (pt): the median over its equations."""
    values = {}
    for name in ("first_equal", "second_equal", "result_right", "unit_start", "rhs_start"):
        found = sorted(record[name] for record in geometry["equations"] if name in record)
        if found:
            values[name] = found[len(found) // 2]
    return values


def _source_anchors(geometry, number):
    """Each anchor of a group as the page column nearest the original's position (most common)."""
    values = {}
    for name in ("first_equal", "second_equal", "result_right", "unit_start", "rhs_start"):
        found = [anchor_column(record[name], number) for record in geometry["equations"] if name in record]
        if found:
            values[name] = max(set(found), key=lambda value: (found.count(value), value))
    return values


# Right-hand-side tokens drawn as operators (the authored rows give most of them as plain strings).
_OPERATOR_TOKENS = frozenset({"×", "x", "＋", "+", "-", "−", "/", "／", "÷", "±"})
_NUMBER_TOKEN = re.compile(r"[-+−]?(?:[\d ]+(?:\.\d+)?|#+)")


def _term_segments(rhs):
    """The terms of a right-hand side: each top-level item, a script joined to the item before it.

    FR-025: each term takes whole grid columns of its own (one grid-Excel cell; a
    script stays in its base's cell as rich text). One segment means no terms.
    """
    items = list(rhs.items) if isinstance(rhs, Row) else [rhs]
    if any(isinstance(item, TermStop) for item in items):
        # Already in terms: the segments between the TermStops.
        segments = []
        for item in items:
            if isinstance(item, TermStop):
                segments.append([])
            else:
                segments[-1].append(item)
        return segments
    segments = []
    for item in items:
        if isinstance(item, Script) and segments:
            segments[-1].append(item)
        else:
            segments.append([item])
    return segments


def _term_align(segment):
    """Operators centre in their column and numbers align right; other text aligns left."""
    if len(segment) == 1:
        item = segment[0]
        text = item.text.strip() if isinstance(item, Literal) else (item.text.strip() if isinstance(item, Operator) else None)
        if isinstance(item, Operator) or text in _OPERATOR_TOKENS:
            return "center"
        if text is not None and _NUMBER_TOKEN.fullmatch(text):
            return "right"
    return "left"


def _segment_width(item, segment, style, fonts):
    return Row(*segment, gap=item.rhs.gap if isinstance(item.rhs, Row) else 0).measure(fonts, style).width


def _shared_term_widths(data, page):
    """{(number of terms, index): widest term (pt)} over the groups whose terms the original aligned.

    Groups whose right-hand sides (and first relations, if any) the original
    started within ``ALIGNED_SOURCE_PT`` of this one's (the p3-p7 per-girder lines)
    give their like-shaped equations' terms the same minimum widths, so the
    same term starts in the same column in each (TermStop.width).
    """
    key = ("widths", data["id"])
    if key not in page.anchors:
        source = _source_positions(page.geometry[data["id"]])
        widths = {}
        for block in page.leaves:
            if block["type"] != "equations":
                continue
            other = _source_positions(page.geometry[block["id"]])
            # The right-hand sides start together, and so do the first relations where there are any
            # (the p3-p8 train equations have none).
            close = [name in source and name in other and abs(source[name] - other[name]) <= ALIGNED_SOURCE_PT
                     for name in ("first_equal", "rhs_start") if name in source or name in other]
            if "rhs_start" not in source or not all(close) or _style(block) != _style(data):
                continue
            for item in _equation_list(block, page):
                segments = _term_segments(item.rhs)
                if len(segments) > 1:
                    for index, segment in enumerate(segments):
                        width = _segment_width(item, segment, _style(block), page.fonts)
                        widths[len(segments), index] = max(widths.get((len(segments), index), 0.0), width)
        page.anchors[key] = widths
    return page.anchors[key]


def _grid_terms(equations, *, whole=False, widths=None):
    """The group's equations with TermStops between their terms, for term_columns="grid".

    A column's alignment is shared by the group (EquationGroup rejects a
    mismatch): the terms' own alignment where every equation using that
    column agrees, otherwise left. With ``whole`` each right-hand side is one
    term (a nested Row: one grid-Excel cell), for groups whose terms do not
    fit the original's lines. ``widths`` (``_shared_term_widths``) are the
    terms' minimum widths.
    """
    if whole:
        return [replace(item, rhs=Row(TermStop("left"), item.rhs, gap=0))
                if isinstance(item.rhs, Row) and len(item.rhs.items) > 1 else item for item in equations]
    segmented = [_term_segments(item.rhs) for item in equations]
    aligns = {}
    for segments in segmented:
        if len(segments) > 1:
            for index, segment in enumerate(segments):
                aligns.setdefault(index, set()).add(_term_align(segment))
    shared = {index: next(iter(values)) if len(values) == 1 else "left" for index, values in aligns.items()}
    result = []
    for item, segments in zip(equations, segmented):
        if len(segments) <= 1:
            result.append(item)
            continue
        parts = []
        for index, segment in enumerate(segments):
            parts.append(TermStop(shared[index], width=(widths or {}).get((len(segments), index)) or None))
            parts.extend(segment)
        result.append(replace(item, rhs=Row(*parts, gap=item.rhs.gap)))
    return result


def _grid_width(equations, style, page, *, with_result=False, widths=None):
    """The width (pt) of the widest right-hand side as whole grid term columns shared by ``equations``.

    With ``with_result`` only the right-hand sides of equations with a result
    count (the columns are still shared by all): a right-hand side without a
    result may run on across the second relation's column (the library gives
    it the full width).
    """
    pitch = page.grid.pitch_x
    padding = 2 * excel_cell_padding_pt(style.size)
    columns = {}
    for item in equations:
        segments = _term_segments(item.rhs)
        for index, segment in enumerate(segments):
            width = _segment_width(item, segment, style, page.fonts)
            if len(segments) > 1:
                width = max(width, (widths or {}).get((len(segments), index), 0.0))
            count = math.ceil((width + padding) / pitch - 1e-9) if width else 0
            columns[index] = max(columns.get(index, 0), count)
    return max((sum(columns[index] for index in range(len(_term_segments(item.rhs)))) * pitch
                for item in equations if not with_result or item.result is not None), default=0.0)


def _anchor_family(data, page):
    """The page's equation groups whose original anchors are all on the same page columns as this one's.

    The original aligned them (e.g. the p3 per-girder lines), so their anchors
    are found together, in page columns. Groups that share only some anchors
    with the original are aligned afterwards (``_equation_anchors``).
    """
    def key(block):
        return tuple(sorted(_source_anchors(page.geometry[block["id"]], page.number).items()))
    wanted = key(data)
    return [block for block in page.leaves if block["type"] == "equations" and key(block) == wanted]


def _equations(data, page, container, columns):
    """An EquationGroup at the original's anchors, shared with the groups the original aligned.

    ``columns`` is the width the group is measured in (its container's, less its
    indent). The right-hand sides use grid term columns (FR-025, FR-027).
    """
    column = page.column(data, container)
    if column + columns != page.grid.columns:
        raise ValueError(f"{data['id']}: an equation group must reach the body's right edge "
                         "(its anchors are found in page columns)")
    anchors, _ = _equation_anchors(data, page)
    groups, _ = _groups(data, page, {name: value - column for name, value in anchors.items()}, columns)
    return groups[0] if len(groups) == 1 else Stack(*groups, block_id=data["id"])


def _groups(data, page, anchors, columns):
    """The group's EquationGroups at ``anchors`` (from its left edge), and whether all keep the original's lines.

    Each run of like-shaped equations (``_term_runs``) is one group; its terms
    take their own grid columns where that keeps the original's lines, else
    each right-hand side is one term.
    """
    identifier = data["id"]
    values = dict(anchors)
    plain = _equation_list(data, page)
    # A group keeps only the anchors its own parts use.
    if all(item.result is None for item in plain):
        values = {"first_equal": values["first_equal"]}
    elif all(item.unit is None for item in plain):
        values.pop("unit_start", None)
    runs = _term_runs(plain)
    shared = _shared_term_widths(data, page)
    groups, keeps = [], True
    for index, run in enumerate(runs):
        name = identifier if len(runs) == 1 else f"{identifier}-run{index}"
        # The terms' widths shared with the groups the original aligned, else the run's own, else one term.
        for widths, whole in ((shared, False), (None, False), (None, True)):
            group = EquationGroup(*_grid_terms(run, whole=whole, widths=widths), anchors=EquationAnchors(**values),
                                  label_columns=data.get("label_columns"), style=_style(data),
                                  gap=data.get("gap", 2), term_columns="grid", block_id=name)
            kept = _keeps_original_lines(group, page, columns)
            if kept or whole:
                groups.append(group)
                keeps = keeps and kept
                break
    return groups, keeps


@dataclass(frozen=True)
class _Member:
    """One equation group of a family: its page column and its equations' measured needs."""

    data: Mapping
    column: int
    equations: tuple
    runs: tuple
    style: TextStyle
    gap: float
    label_reserve: float
    widths: Mapping


def _member(data, page):
    plain = _equation_list(data, page)
    labels = data.get("label_columns") or 0
    gap = data.get("gap", 2)
    return _Member(data, page.column(data, 0), tuple(plain), tuple(tuple(run) for run in _term_runs(plain)),
                   _style(data), gap, labels * page.grid.pitch_x + gap if labels else 0.0,
                   _shared_term_widths(data, page))


def _equation_anchors(data, page):
    """(page-column anchors of a group's family, whether a result lacks its grid-Excel cells).

    First each family on its own (``_family_anchors``). Then each anchor the
    original put on the same page column as another family's (T1, T2 and the
    stopper lines on p16-p19, at different indentation levels) takes the
    rightmost of their columns, where every member still keeps the original's
    lines and its result's grid-Excel cells; otherwise the family keeps its own.
    """
    family = _anchor_family(data, page)
    key = ("aligned", tuple(block["id"] for block in family))
    if key not in page.anchors:
        base, narrow, cells = _family_anchors(family, page)
        source = _source_positions(page.geometry[data["id"]])
        peers = [block for block in page.leaves if block["type"] == "equations"]
        aligned = dict(base)
        for name in base:
            if name not in source:
                continue
            for block in peers:
                other = _source_positions(page.geometry[block["id"]])
                if name in other and abs(other[name] - source[name]) <= ALIGNED_SOURCE_PT:
                    value = _family_anchors(_anchor_family(block, page), page)[0].get(name)
                    if value is not None:
                        aligned[name] = max(aligned[name], value)
        chosen = (base, narrow)
        if aligned != base:
            members = [_member(block, page) for block in family]
            values, _ = _anchors(aligned, members, page, cells=cells)
            if _members_keep_lines(members, values, page):
                chosen = (values, narrow)
        page.anchors[key] = chosen
    return page.anchors[key]


def _family_anchors(family, page):
    """(page-column anchors of one family, whether a result lacks cells, the cells it was given).

    The result first gets all the grid-Excel cells it needs (so the grid
    Excel can show it as a number); where that costs the original's lines
    (reading order comes first, FR-027), fewer cells, measured with the
    library, down to none.
    """
    key = tuple(block["id"] for block in family)
    if key not in page.anchors:
        members = [_member(block, page) for block in family]
        source = _source_anchors(page.geometry[family[0]["id"]], page.number)
        values, full = _anchors(source, members, page)
        chosen = None
        for cells in range(full, -1, -1):
            values, _ = _anchors(source, members, page, cells=cells)
            if _members_keep_lines(members, values, page):
                chosen = (values, cells < full, cells)
                break
        page.anchors[key] = chosen or (values, True, 0)
    return page.anchors[key]


def _members_keep_lines(members, values, page):
    """Whether every member, at the page-column ``values``, keeps the original's lines."""
    return all(_groups(member.data, page, {name: value - member.column for name, value in values.items()},
                       page.grid.columns - member.column)[1] for member in members)


def _term_runs(equations):
    """Consecutive equations with the same number of terms: each run shares its term columns.

    EquationGroup shares a column index across all its equations, so a long
    one-term right-hand side would widen the first column of every other
    equation; equations of another shape go in a group of their own (with the
    same anchors, so the equals stay aligned).
    """
    runs = []
    for item in equations:
        count = len(_term_segments(item.rhs))
        if runs and len(_term_segments(runs[-1][-1].rhs)) == count:
            runs[-1].append(item)
        else:
            runs.append([item])
    return runs


def _keeps_original_lines(group, page, columns):
    """Whether every equation keeps its grid term columns on one line with its result, as the original did."""
    context = LayoutContext(page.fonts, page_profile(page.number), SOURCE_STYLE)
    try:
        measured = measure_block(group, context, columns * page.grid.pitch_x)
    except LayoutOverflowError:
        return False
    # No equation falls back, moves its result to a line of its own or wraps its right-hand side.
    return all(not part.metadata.get(flag) for part in measured.parts
               for flag in ("term_fallback", "result_line", "continuation"))


def equation_left(geometry):
    """The original left edge of an equation group: its labels, markers or left-hand sides."""
    edges = [geometry["x"]]
    for record in geometry.get("equations", ()):
        edges.extend(record[name] for name in ("lhs_start", "label_start") if name in record)
        if "lhs_marker" in record:
            edges.append(record["lhs_marker"]["x"])
    return min(edges)


def _relation_sides(relation, style, fonts):
    """A relation's ink extent left and right of its advance centre, as EquationGroup measures it."""
    metrics = fonts.measure(fonts.normalize_text(relation), style)
    return metrics.width / 2 - metrics.bounds.x, metrics.bounds.right - metrics.width / 2


def _anchors(source, members, page, *, cells=None):
    """(Equation anchors in page columns, the grid-Excel cells the widest result needs).

    ``source`` holds the page columns nearest the original's anchors. A column
    is raised only as far as some member's measured parts need (the library
    would otherwise stop with LayoutOverflowError), never left of the
    original's; the space before the second relation widens so every
    member's right-hand side stays on one line while the parts to its right
    still fit the body. ``cells`` (default: those it needs) are the cells the
    result is given between the second relation's cells and result_right.
    """
    pitch = page.grid.pitch_x
    right = page.grid.columns
    values = {name: source[name] for name in ("first_equal", "second_equal", "result_right", "unit_start") if name in source}
    if "first_equal" not in values:
        # An equation without a visible first relation: its right-hand side start sets the column.
        values["first_equal"] = source["rhs_start"] - 1 if "rhs_start" in source else min(m.column for m in members) + 1

    def width(node, member):
        return node.measure(page.fonts, member.style).width if node is not None else 0.0

    def sides(relation, member):
        return _relation_sides(relation, member.style, page.fonts)

    for member in members:
        need = max(member.label_reserve + width(item.lhs, member) + member.gap + sides(item.relation, member)[0]
                   for item in member.equations)
        values["first_equal"] = max(values["first_equal"], member.column + math.ceil(need / pitch - 1e-9))
    first = values["first_equal"]
    with_result = [(member, item) for member in members for item in member.equations if item.result is not None]
    if not with_result:
        return {"first_equal": first}, 0
    values["second_equal"] = max(values.get("second_equal", first + 1), first + 1)
    lines = []
    for member in members:
        start = math.ceil((first * pitch + max(sides(item.relation, member)[1] for item in member.equations)
                           + member.gap) / pitch - 1e-9)
        # The right-hand sides with a result as grid term columns, each run sharing its columns.
        wanted = max(_grid_width(run, member.style, page, with_result=True, widths=member.widths)
                     for run in member.runs)
        left_of_second = max((sides(item.result_relation, member)[0] for item in member.equations
                              if item.result is not None), default=0.0)
        lines.append((start, wanted, left_of_second, member.gap))
    result_need = max(width(item.result, member) + member.gap + sides(item.result_relation, member)[1]
                      for member, item in with_result)
    # In the grid Excel the result takes the cells between the second relation's cells (from its
    # anchor boundary, as many as its advance spans) and result_right.
    result_cells = max(_excel_cells(item.result, member.style, page) for member, item in with_result)
    relation_cells = max((max(1, math.ceil(page.fonts.measure(page.fonts.normalize_text(item.result_relation),
                                                              member.style).width / pitch - 1e-9))
                          for member, item in with_result if item.result_relation.strip()), default=0)
    units = [(member, item.unit) for member, item in with_result if item.unit is not None]
    unit_width = max((width(unit, member) for member, unit in units), default=0.0)

    def tail(second, given):
        """The result end and unit start for a second relation at ``second``, and whether they fit."""
        result_right = max(values.get("result_right", second + 1), second + relation_cells + given,
                           math.ceil((second * pitch + result_need) / pitch - 1e-9))
        if not units:
            return result_right, None, result_right <= right
        unit_start = max(values.get("unit_start", result_right + 1), result_right + 1)
        return result_right, unit_start, unit_start * pitch + unit_width <= right * pitch + 1e-9

    def rhs_fits(second):
        # An empty right-hand side still needs a column, or the library moves the result down.
        return all((math.floor((second * pitch - left - gap) / pitch + 1e-9) - start) * pitch >= max(wanted, pitch) - 1e-9
                   for start, wanted, left, gap in lines)

    cells = result_cells if cells is None else cells
    while not rhs_fits(values["second_equal"]) and tail(values["second_equal"] + 1, cells)[2]:
        values["second_equal"] += 1
    values["result_right"], unit_start, _ = tail(values["second_equal"], cells)
    if unit_start is None:
        values.pop("unit_start", None)
    else:
        values["unit_start"] = unit_start
    return values, result_cells


def _excel_cells(node, style, page):
    """Grid columns a result needs in the grid Excel: its screen width and cell padding (see _map.cell)."""
    texts = [command for command in node.measure(page.fonts, style).commands if isinstance(command, Text)]
    screen = sum(math.ceil(page.fonts.measure(page.fonts.normalize_text(char), command.style).width
                           * PIXELS_PER_PT - 1e-9) / PIXELS_PER_PT
                 for command in texts for char in command.text)
    need = screen + 2 * excel_cell_padding_pt(style.size)
    return max(1, math.ceil(need / excel_column_width_pt(page.grid.pitch_x) - 1e-9))


def _grid_spans(sizes, minimums, pitch):
    """Whole grid steps for consecutive original sizes (pt), each at least its minimum (pt).

    Each boundary is the original's cumulative boundary rounded to the grid,
    so rounding does not add up along a table. A span its content needs is
    widened; the next boundary is again the original's, so a following span
    may shrink (to its own minimum, and at least one step).
    """
    spans, total, placed = [], 0.0, 0
    for size, minimum in zip(sizes, minimums):
        total += size
        span = max(1, _nearest(total / pitch) - placed, math.ceil(minimum / pitch - 1e-9))
        spans.append(span)
        placed += span
    return tuple(spans)


def _widen_for_spans(spans, merged, pitch):
    """Widen the last spanned step of each merged cell (start, count, minimum pt) its steps do not hold."""
    spans = list(spans)
    for start, count, minimum in merged:
        missing = math.ceil(minimum / pitch - 1e-9) - sum(spans[start:start + count])
        if missing > 0:
            spans[start + count - 1] += missing
    return tuple(spans)


def _cell_source_lines(lines, geometry, cell_id):
    """The authored cell lines, broken where the original broke a plain-text cell line.

    The authored manuscript sometimes joins two original lines of a header
    (p32, p33: 「せん断」「力」). When every authored line is plain text and the
    original's lines hold the same characters, the original's lines are used.
    """
    source = [line.get("text_with_spaces", line.get("text", "")) for line in (geometry or {}).get("lines", ())]
    visible = [line for line in lines if not isinstance(line, str) or line.strip()]
    if not source or len(source) == len(visible) or not all(isinstance(line, str) for line in lines):
        return lines
    if re.sub(r"\s", "", "".join(lines)) != re.sub(r"\s", "", "".join(source)):
        raise ValueError(f"{cell_id}: authored cell text differs from the original's lines")
    return tuple(source)


def _same_columns(data, page):
    """The page's tables the original drew at the same x with the same column widths (p26, p27)."""
    geometry = page.geometry[data["id"]]

    def shape(block):
        other = page.geometry[block["id"]]
        return (round(other["x"], 2), tuple(round(width, 2) for width in other["columns"]), bool(other.get("turns")))
    return [block for block in page.leaves if block["type"] == "table" and shape(block) == shape(data)] \
        if geometry.get("columns") else [data]


def _table(data, page, *, needs_only=False):
    """A source table on the page grid (or the swapped page grid, turned, on p30-p37).

    Each cell line takes one grid row (CellLines line advance = row pitch).
    Column boundaries are the original's rounded to whole grid columns, a
    column widened only where the 10 pt content needs it; a row is the
    original's height rounded to whole grid rows, raised to what it holds.
    """
    identifier = data["id"]
    geometry = page.geometry[identifier]
    turned = bool(geometry.get("turns"))
    page_grid = page.grid
    local = (GridSpec(0, 0, page_grid.pitch_y, page_grid.pitch_x, page_grid.rows, page_grid.columns)
             if turned else page_grid)
    profiles = _profiles()
    widest = [0.0] * len(geometry["columns"])
    merged = []
    horizontal = [rule_thickness(width) for width in geometry["horizontal_rules"]]
    vertical = [rule_thickness(width) for width in geometry["vertical_rules"]]
    needs = [1] * len(geometry["row_heights"])
    spanned = []
    cells_geometry = {(cell["row"], cell["col"]): cell for cell in geometry["cells"]}
    placed = []
    occupied = set()
    rows = []
    for row_index, source_row in enumerate(data["rows"]):
        cells, column = [], 0
        for raw in source_row:
            while (row_index, column) in occupied:
                column += 1
            cell = {"lines": [raw]} if isinstance(raw, str) else raw
            rowspan, colspan = cell.get("rowspan", 1), cell.get("colspan", 1)
            occupied.update((r, c) for r in range(row_index, row_index + rowspan)
                            for c in range(column, column + colspan))
            cell_id = f"{identifier}.r{row_index}.c{column}"
            profile = profiles.get(cell_id, {})
            style = TextStyle(profile.get("font", BODY_FONT), profile.get("size", 10))
            source_cell = cells_geometry.get((row_index, column))
            raw_lines = _cell_source_lines(tuple(cell.get("lines", ())), source_cell, cell_id)
            sizes = profile.get("line_sizes", cell.get("line_sizes"))
            line_styles = tuple(replace(style, size=size) for size in sizes) if sizes else None
            # A line the original turned within the cell (p21, p22: the vertical heading's parentheses).
            source_lines = (source_cell or {}).get("lines", ())
            turns = [(line.get("quarter_turns", geometry.get("turns", 0)) - geometry.get("turns", 0)) % 4
                     for line in source_lines] if len(source_lines) == len(raw_lines) else [0] * len(raw_lines)
            lines = tuple(_cell_line(line, profile, turned=bool(turn)) for line, turn in zip(raw_lines, turns)) or ("",)
            if turned:
                lines = tuple(_with_subscript_drop(line, _ROTATED_SUBSCRIPT_DROP) for line in lines)
            if line_styles and len(line_styles) != len(lines):
                raise ValueError(f"{cell_id}: line sizes must match lines")
            # Keep the whole thickness of every rule the cell can meet clear of its text.
            padding = Insets(top=horizontal[row_index], bottom=horizontal[row_index + rowspan],
                             left=_CELL_PADDING + vertical[column], right=_CELL_PADDING + vertical[column + colspan])
            boxes = [Row(line, gap=0).measure(page.fonts, line_styles[index] if line_styles else style)
                     for index, line in enumerate(lines)]
            content_width = max(box.width for box in boxes) + padding.left + padding.right
            if colspan == 1:
                widest[column] = max(widest[column], content_width)
            else:
                merged.append((column, colspan, content_width))
            # CellLines' own height: first ascent, line advances, last descent, and the padding.
            top = min(boxes[0].ascent + index * local.pitch_y - box.ascent for index, box in enumerate(boxes))
            bottom = max(boxes[0].ascent + index * local.pitch_y + box.descent for index, box in enumerate(boxes))
            need = math.ceil((bottom - top + padding.top + padding.bottom) / local.pitch_y - 1e-9)
            if rowspan == 1:
                needs[row_index] = max(needs[row_index], need)
            else:
                spanned.append((row_index, rowspan, need))
            align = cell.get("align", "center")
            content = CellLines(lines, style=style, line_styles=line_styles, line_advance=local.pitch_y,
                                align=align, inner_padding=padding,
                                block_id=f"{identifier}-r{row_index}-cell{len(cells)}")
            placed.append((row_index, len(cells), rowspan, len(lines), boxes))
            cells.append(Cell(content, colspan=colspan, rowspan=rowspan, align=align, padding=0))
            column += colspan
        rows.append(cells)
    if needs_only:
        return widest, merged
    # Tables the original drew with the same columns keep the same columns: each column as wide
    # as the widest content any of them puts in it.
    for peer in _same_columns(data, page):
        if peer is not data:
            other, spans = _table(peer, page, needs_only=True)
            widest = [max(a, b) for a, b in zip(widest, other)]
            merged = merged + spans
    # Merged cells widen in one order whichever table of the group this is.
    merged = sorted(set(merged))
    columns = _widen_for_spans(_grid_spans(geometry["columns"], widest, local.pitch_x), merged, local.pitch_x)
    # Rows round one by one, so rows the original made equal stay equal; columns keep the
    # original's boundaries, so a wide table does not grow to the right.
    row_heights = [max(1, _nearest(height / local.pitch_y), need)
                   for height, need in zip(geometry["row_heights"], needs)]
    # A merged cell that its rows still do not hold adds the rest to its last row (as Table does).
    for row_index, rowspan, need in spanned:
        missing = need - sum(row_heights[row_index:row_index + rowspan])
        if missing > 0:
            row_heights[row_index + rowspan - 1] += missing
    row_heights = tuple(row_heights)
    for row_index, index, rowspan, count, boxes in placed:
        if count == 1:
            # A one-line cell stays centred in its whole cell: the grid Excel merges such a cell
            # over its range and keeps its vertical alignment (lead, 2026-10-20).
            continue
        # Each line of a multi-line cell sits in its own grid row (on p30-p37 the local row is a
        # page column), the lines centred in the cell by whole rows: the grid Excel gives each line
        # one row, so a line must not cross a row boundary (FR-027, lead 2026-10-20). The rows were
        # sized with the rules' thickness as padding; a line placed in its row needs none (its glyph
        # box stays in the row and clear of the rules).
        total = sum(row_heights[row_index:row_index + rowspan])
        start, offset = _row_placement(count, total, local.pitch_y, boxes,
                                       top=_stroke_clearance(horizontal, row_index),
                                       bottom=_stroke_clearance(horizontal, row_index + rowspan),
                                       where=f"{identifier}.r{row_index}")
        baseline = start * local.pitch_y + offset
        cell = rows[row_index][index]
        padding = replace(cell.content.inner_padding, top=0.0, bottom=0.0)
        rows[row_index][index] = replace(cell, valign="top", content=replace(
            cell.content, first_baseline=baseline, inner_padding=padding))
    table = Table(columns, tuple(rows), header_rows=data.get("header_rows", 0),
                  borders=_rule_borders(geometry, 0.0),
                  row_heights=row_heights, block_id=identifier)
    if turned:
        return QuarterTurn(table, turns=geometry["turns"], local_grid=local, block_id=data["rotation_id"])
    return table


def _stroke_clearance(rules, boundary):
    """How far a cell's content keeps from a boundary's rule: its whole thickness.

    Table lays each row out as its own part and keeps content clear of the
    whole thickness of a rule on a part's edge (tables._inner_edges).
    """
    return rules[boundary]


# Table keeps content strictly clear of a rule's stroke (tables._check_clearance).
_STROKE_MARGIN = .01


def _row_placement(count, total, pitch, boxes, *, top, bottom, where):
    """(first row, baseline offset in it) setting ``count`` lines one per row in ``total`` rows.

    Every line's ascent and descent stay inside its own row (FR-027: the grid
    Excel puts a line in one row); the first line clears the cell's top rule
    when it is in the cell's first row, the last its bottom rule in the last
    row. The rows nearest the middle of the cell come first, the offset is
    the middle of the ones that fit.
    """
    starts = sorted(range(total - count + 1), key=lambda start: (abs(start - (total - count) / 2), start))
    for start in starts:
        low = max([box.ascent for box in boxes] + ([boxes[0].ascent + top + _STROKE_MARGIN] if start == 0 else []))
        high = min([pitch - box.descent for box in boxes]
                   + ([pitch - boxes[-1].descent - bottom - _STROKE_MARGIN] if start + count == total else []))
        if low <= high + 1e-9:
            return start, (low + high) / 2
    needed = max(box.ascent + box.descent for box in boxes)
    raise LayoutOverflowError(f"原本再現できず: {where}: {count} lines of {needed:.2f} pt do not fit "
                              f"{total} rows of {pitch} pt with their rules", block_id=where,
                              needed=needed, available=pitch)


def _load_pages(source_pages, pages_root, fonts):
    result = []
    all_ids = set()
    layout = {page["source_page"]: page for page in _fixture_json("source-layout.json")["pages"]}
    for number in source_pages:
        path = pages_root / f"p{number:02}.json"
        if not path.is_file():
            raise ValueError(f"p{number:02}: missing input page {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("source_page") != number or data.get("schema_version") != 1:
            raise ValueError(f"p{number:02}: invalid source-page identity/schema")
        if not data.get("blocks"):
            raise ValueError(f"p{number:02}: no source content")

        def check_ids(items):
            for block in items:
                identifier = block.get("id", "")
                if not identifier.startswith(f"p{number:02}-") or identifier in all_ids:
                    raise ValueError(f"p{number:02}: invalid or duplicate block ID {identifier!r}")
                all_ids.add(identifier)
                check_ids(block.get("children", ()))
        check_ids(data["blocks"])
        _reject_obsolete_keys(data["blocks"], number)
        geometry = {block["id"]: block for block in layout[number]["blocks"]}
        leaves = {leaf["id"] for leaf in _leaves({"type": "stack", "children": data["blocks"]})}
        missing = sorted(set(geometry) - leaves)
        if missing:
            raise LayoutOverflowError(f"原本再現できず: p{number:02} missing declared source block {missing[0]}",
                                      block_id=f"p{number:02}")
        unplaced = sorted(leaves - set(geometry))
        if unplaced:
            raise LayoutOverflowError(f"原本再現できず: p{number:02} unplaced content {unplaced}",
                                      block_id=f"p{number:02}")
        # Custom manuscripts cannot silently add blank overflow after the fixed source frame.
        if pages_root.resolve() != (FIXTURE_ROOT / "pages").resolve():
            original = json.loads((FIXTURE_ROOT / f"pages/p{number:02}.json").read_text("utf-8"))
            if data != original:
                raise LayoutOverflowError(f"原本再現できず: p{number:02} modified manuscript requires reviewed source placement",
                                          block_id=f"p{number:02}")
        page = _Page(number, fonts, geometry, tuple(_leaves({"type": "stack", "children": data["blocks"]})))
        result.append((number, [build_block(block, page) for block in data["blocks"]]))
    return result


# Layout values the manuscript held before FR-027; the layout now comes from the page grid and the
# original's positions (source-layout.json), so any of these in a manuscript is an error.
_OBSOLETE_KEYS = {
    "table": {"local_grid", "columns", "horizontal_rules", "vertical_rules", "border_width", "padding",
              "inline_padding", "cell_min_height", "line_advance", "size", "turns"},
    "cell": {"padding", "size", "line_advance"},
    "equations": {"anchors"},
    "rule": {"rows"},
}


def _reject_obsolete_keys(blocks, number):
    for block in blocks:
        found = _OBSOLETE_KEYS.get(block["type"], set()) & set(block)
        if block["type"] == "table":
            for row in block["rows"]:
                for cell in row:
                    found |= _OBSOLETE_KEYS["cell"] & set(cell if isinstance(cell, dict) else ())
        if found:
            raise ValueError(f"p{number:02}: {block['id']} has obsolete layout key(s) {sorted(found)}")
        _reject_obsolete_keys(block.get("children", ()), number)


def build_document(fonts, *, source_pages=SOURCE_PAGES, pages_root=None):
    pages = _selection(source_pages)
    if fonts is None:
        raise ValueError("fixture documents need fixture_fonts(), which pins the original font files")
    groups = _load_pages(pages, Path(pages_root) if pages_root is not None else FIXTURE_ROOT / "pages", fonts)
    return _document(fonts, groups)


def _document(fonts, groups):
    """One KeepTogether per original page, each on its fixed page profile."""
    if fonts is None:
        raise ValueError("fixture documents need fixture_fonts(), which pins the original font files")
    groups = tuple(groups)
    first = page_profile(groups[0][0]) if groups else SOURCE_PROFILE
    blocks = []
    for index, (number, content) in enumerate(groups):
        if index:
            blocks.append(PageBreak())
        page = KeepTogether(Stack(*content, block_id=f"p{number:02}-content"), block_id=f"p{number:02}")
        profile = page_profile(number)
        blocks.append(page if profile == first else PageSection(profile, page))
    return Document(*blocks, fonts=fonts, profile=first, style=SOURCE_STYLE)


def guard_fixed_pages(pages, source_pages, declared_blocks=None):
    expected = _selection(source_pages)
    if len(pages) != len(expected):
        raise LayoutOverflowError(f"原本再現できず: expected {len(expected)} pages, got {len(pages)}",
                                  needed=len(pages), available=len(expected))
    for page, source in zip(pages, expected):
        placements = page.metadata.get("placements", ())
        if (page.profile != page_profile(source) or not page.commands or len(placements) != 1
                or placements[0].get("block_id") != f"p{source:02}"):
            raise LayoutOverflowError(f"原本再現できず: p{source:02} content moved, missing, or decorated",
                                      block_id=f"p{source:02}")
        identifiers = set(_metadata_ids(placements))
        if declared_blocks is not None:
            missing = set(declared_blocks[source]) - identifiers
            if missing:
                raise LayoutOverflowError(f"原本再現できず: p{source:02} missing blocks {sorted(missing)}",
                                          block_id=f"p{source:02}")
        for identifier in identifiers:
            match = re.match(r"^p(\d{2})(?:-|$)", identifier)
            if match and int(match[1]) != source:
                raise LayoutOverflowError(f"原本再現できず: p{source:02} contains {identifier}",
                                          block_id=identifier)


def _metadata_ids(value):
    if isinstance(value, Mapping):
        if isinstance(value.get("block_id"), str):
            yield value["block_id"]
        for child in value.values():
            yield from _metadata_ids(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from _metadata_ids(child)


def _block_ids(block):
    identifier = getattr(block, "block_id", "")
    if identifier:
        yield identifier
    for child in getattr(block, "children", ()) or getattr(block, "blocks", ()):
        yield from _block_ids(child)
    if hasattr(block, "block"):
        yield from _block_ids(block.block)


def layout_blocks(fonts, groups):
    """Layout complete source-page groups, then validate their identity."""
    groups = tuple(groups)
    source_pages = _selection(number for number, _ in groups)
    try:
        pages = _document(fonts, groups).layout()
    except LayoutOverflowError as exc:
        raise LayoutOverflowError(f"原本再現できず: {exc}", block_id=exc.block_id,
                                  needed=exc.needed, available=exc.available) from exc
    declared = {number: set(identifier for block in content for identifier in _block_ids(block))
                for number, content in groups}
    guard_fixed_pages(pages, source_pages, declared)
    return pages


def layout_report(fonts, *, source_pages=SOURCE_PAGES, pages_root=None):
    selected = _selection(source_pages)
    groups = _load_pages(selected, Path(pages_root) if pages_root else FIXTURE_ROOT / "pages", fonts)
    return layout_blocks(fonts, groups)


def fixture_fonts():
    """Resolve the original faces by name and pin each resolved file and face."""
    fonts = FontRegistry()
    for name, definition in font_profile()["fonts"].items():  # a fresh read: tests may patch font_profile
        face = fonts.resolve(name)
        if face.path.name.lower() != definition["file"] or face.face_index != definition["face_index"]:
            raise ValueError(f"Original font moved: {name} resolved to {face.path} face {face.face_index}")
        if face.sha256 != definition["sha256"]:
            raise ValueError(f"Original font hash changed: {name} at {face.path}")
    return fonts
