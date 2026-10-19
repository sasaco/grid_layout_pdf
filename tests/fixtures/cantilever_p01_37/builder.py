"""Semantic, display-only input assembly for the fixed-page cantilever fixture.

This module never reads the independent expected/ directory. The fixture is not
a calculator, PDF parser, or a general serialization API for the library.
"""

from dataclasses import dataclass, replace
from collections.abc import Mapping
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import importlib.util
import sys
from copy import deepcopy

from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, Cell, CellLines, Columns, Document, Equation, EquationAnchors,
    EquationGroup, Figure, FontRegistry, Fraction, GridSpec, KeepTogether,
    LayoutOverflowError, LayoutPart, Line, Literal, MathBlock, MeasuredBlock,
    Operator, PageBreak, PageProfile, Paragraph, RasterImage, ReportStyle, Row, Script, Spacer, Stack,
    Table, TextStyle, Insets, Image as LayoutImage,
)


FIXTURE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = FIXTURE_ROOT.parents[2]
SOURCE_PAGES = tuple(range(1, 38))
PROOF_PAGES = (16, 17, 26, 30, 36)
SOURCE_PROFILE = PageProfile("CANTILEVER_SOURCE_A4",595,842,GridSpec(50.88,54.598,16.08,15.48,31,48))


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


def font_profile():
    return json.loads((FIXTURE_ROOT / "font-profile.json").read_text(encoding="utf-8"))


def load_manifest():
    return json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))


def _selection(source_pages):
    pages = tuple(source_pages)
    if (not pages or any(type(number) is not int or number not in SOURCE_PAGES for number in pages)
            or tuple(sorted(set(pages))) != pages):
        raise ValueError("source_pages must be unique, increasing original pages 1..37")
    return pages


def math_node(value):
    """Decode explicitly authored math, without interpreting display strings."""
    if isinstance(value, str):
        return _appearance().SourceLiteral(value)
    kind = value["type"]
    if kind == "row":
        return Row(*(math_node(item) for item in value["items"]), gap=0)
    if kind == "script":
        return _appearance().SourceScript(math_node(value["base"]),
                      subscript=math_node(value["sub"]) if "sub" in value else None,
                      superscript=math_node(value["sup"]) if "sup" in value else None)
    if kind == "operator":
        return Operator(value["text"])
    if kind == "fraction":
        return Fraction(math_node(value["numerator"]), math_node(value["denominator"]))
    raise ValueError(f"unknown fixture math node {kind!r}")


@dataclass(frozen=True)
class CompactCell:
    """Decode authored JSON lines; public CellLines owns point layout and safety."""

    lines: tuple
    style: TextStyle = TextStyle(BODY_FONT)
    line_advance: float = 10.8
    min_height: float = 0
    block_id: str = ""
    line_sizes: tuple = ()
    inline_padding: float = 0

    def measure(self, context, available_width):
        if self.line_sizes and len(self.line_sizes) != len(self.lines):
            raise ValueError(f"{self.block_id}: line_sizes must match lines")
        styles = (tuple(replace(self.style, size=size) for size in self.line_sizes)
                  if self.line_sizes else None)
        return CellLines(tuple(math_node(line) for line in self.lines), style=self.style,
                         line_styles=styles, line_advance=self.line_advance, min_height=self.min_height,
                         inner_padding=Insets(left=self.inline_padding, right=self.inline_padding),
                         align="center", block_id=self.block_id).measure(context, available_width)


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
    source = font_profile()["items"].get(data.get("id"), {})
    return TextStyle(font=data.get("font",source.get("font",BODY_FONT)),
                     size=source.get("size",data.get("size",10)), tracking=data.get("tracking",0))


def build_block(data, geometry=None):
    kind, identifier = data["type"], data["id"]
    if kind == "spacer":
        return KeepTogether(Spacer(data["rows"]), block_id=identifier)
    if kind == "paragraph":
        return Paragraph(data["text"], style=_style(data), block_id=identifier)
    if kind == "math":
        return MathBlock(math_node(data["content"]), style=_style(data), block_id=identifier)
    if kind == "image":
        entries = [figure for figure in load_manifest()["figures"] if figure["id"] == data["image_id"]]
        if len(entries) != 1:
            raise ValueError(f"{identifier}: image_id must identify one registered figure")
        return SourceFigure(entries[0], block_id=identifier)
    if kind == "stack":
        return Stack(*(build_block(child) for child in data["children"]), block_id=identifier)
    if kind == "columns":
        return Columns(*(build_block(child) for child in data["children"]),
                       col_spans=data["col_spans"], gap_cols=data.get("gap_cols", 0), block_id=identifier)
    if kind == "rule":
        if geometry is not None:
            pitch=_appearance().PITCH
            width,height=geometry["width"],geometry["height"]
            return Figure(round(width/pitch),round(height/pitch),
                          Line(width/2,width/2,width/2,height-width/2,width=width),block_id=identifier)
        height = data["rows"] * A4_PORTRAIT_REFERENCE.grid.pitch_y
        return Figure(1, data["rows"], Line(1, .5, 1, height - .5, width=.5), block_id=identifier)
    if kind == "equations":
        equations = []
        for index, item in enumerate(data["equations"]):
            options = {key: math_node(item[key]) for key in ("result", "unit") if key in item}
            options.update({key: item[key] for key in ("relation", "result_relation", "label") if key in item})
            equations.append(Equation(math_node(item["lhs"]), math_node(item["rhs"]),
                                      block_id=f"{identifier}-{index}", **options))
        return EquationGroup(*equations, anchors=EquationAnchors(**data["anchors"]) if "anchors" in data else None,
                             label_columns=data.get("label_columns"),
                             style=_style(data), gap=data.get("gap", 2), block_id=identifier)
    if kind == "table":
        if geometry is not None:
            return _source_table(data,geometry)
        rows = []
        for row_index, source_row in enumerate(data["rows"]):
            cells = []
            for index, raw in enumerate(source_row):
                cell = {"lines": [raw]} if isinstance(raw, str) else raw
                content = CompactCell(tuple(cell.get("lines", ())),
                                      style=TextStyle(BODY_FONT, size=cell.get("size", data.get("size", 10))),
                                      line_advance=cell.get("line_advance", data.get("line_advance", 10.8)),
                                      min_height=cell.get("min_height", data.get("cell_min_height", 0)),
                                      line_sizes=tuple(cell.get("line_sizes", ())),
                                      inline_padding=cell.get("inline_padding", data.get("inline_padding", 0)),
                                      block_id=f"{identifier}-r{row_index}-cell{index}")
                cells.append(Cell(content, colspan=cell.get("colspan", 1), rowspan=cell.get("rowspan", 1),
                                  align=cell.get("align", "center"), padding=cell.get("padding", data.get("padding", .6))))
            rows.append(cells)
        rules = {key: tuple(data[key]) for key in ("horizontal_rules", "vertical_rules") if key in data}
        table = Table(tuple(data["columns"]), tuple(rows), header_rows=data.get("header_rows", 0),
                      border_width=data.get("border_width", .4), block_id=identifier, **rules)
        if data.get("turns"):
            from gridlayoutpdf import QuarterTurn
            grid = GridSpec(0, 0, **data["local_grid"])
            return QuarterTurn(table, turns=data["turns"], local_grid=grid,
                               block_id=data["rotation_id"])
        return table
    raise ValueError(f"{identifier}: unsupported fixture block {kind!r}")


def _source_table(data,geometry):
    from gridlayoutpdf import QuarterTurn
    appearance = _appearance()
    identifier=data["id"]
    by_position={(cell["row"],cell["col"]):cell for cell in geometry["cells"]}
    occupancy=set()
    row_spans=[]
    rows=[]
    typography=font_profile()
    profiles=typography["items"]
    for row_index,source_row in enumerate(data["rows"]):
        cells=[]
        col=0
        for raw in source_row:
            while (row_index,col) in occupancy:col+=1
            cell={"lines":[raw]} if isinstance(raw,str) else raw
            rowspan,colspan=cell.get("rowspan",1),cell.get("colspan",1)
            row_spans.append((row_index,row_index+rowspan))
            descriptor=by_position[(row_index,col)]
            anchors=deepcopy(descriptor["lines"])
            for anchor in anchors:
                anchor["local_quarter_turns"]=(anchor.get("quarter_turns",geometry.get("turns",0))-geometry.get("turns",0))%4
            profile=profiles.get(descriptor["id"],{})
            style=TextStyle(profile.get("font",BODY_FONT),profile.get("size",10))
            raw_lines=cell.get("lines",())
            styles=tuple(replace(style,size=size) for size in profile.get("line_sizes",cell.get("line_sizes",[style.size]*len(raw_lines))))
            nodes=tuple(appearance.shear_atoms(math_node(line),profile.get("shear_atoms",())) for line in raw_lines)
            content=appearance.SourceCell(nodes,styles,
                                          tuple(anchors),sum(geometry["row_heights"][row_index:row_index+rowspan]),
                                          block_id=f"{identifier}-r{row_index}-cell{len(cells)}",
                                          vertical_glyphs=typography.get("vertical_glyphs"),
                                          clearance=(geometry["vertical_rules"][col]/(1 if col==0 else 2)+.001,
                                                     geometry["horizontal_rules"][row_index]+.001,
                                                     geometry["vertical_rules"][col+colspan]/(1 if col+colspan==len(geometry["columns"]) else 2)+.001,
                                                     geometry["horizontal_rules"][row_index+rowspan]+.001))
            cells.append(Cell(content,colspan=colspan,rowspan=rowspan,align="left",padding=0))
            occupancy.update((r,c) for r in range(row_index,row_index+rowspan) for c in range(col,col+colspan))
            col+=colspan
        rows.append(cells)
    seams={boundary for boundary in range(1,len(rows)) if not any(start<boundary<stop for start,stop in row_spans)}
    horizontal=tuple(width/2 if boundary in seams else width for boundary,width in enumerate(geometry["horizontal_rules"]))
    rows=tuple(tuple(replace(cell,content=replace(cell.content,clearance=(cell.content.clearance[0],
                horizontal[r]+.001,cell.content.clearance[2],horizontal[r+cell.rowspan]+.001)))
                for cell in row) for r,row in enumerate(rows))
    table=Table(tuple(round(width/appearance.PITCH) for width in geometry["columns"]),rows,
                header_rows=data.get("header_rows",0),border_width=data.get("border_width",.4),
                horizontal_rules=horizontal,vertical_rules=tuple(geometry["vertical_rules"]),
                row_heights=tuple(round(height/appearance.PITCH) for height in geometry["row_heights"]),block_id=identifier)
    if geometry.get("turns"):
        grid=GridSpec(0,0,appearance.PITCH,appearance.PITCH,
                      sum(round(v/appearance.PITCH) for v in geometry["columns"]),
                      sum(round(v/appearance.PITCH) for v in geometry["row_heights"]))
        return QuarterTurn(table,turns=geometry["turns"],local_grid=grid,block_id=data["rotation_id"])
    return table


def _table_outer_edges(source):
    """Convert authored source rule centres into Table's outside frame edges."""
    geometry=deepcopy(source)
    top,bottom=geometry["horizontal_rules"][0]/2,geometry["horizontal_rules"][-1]/2
    left,right=geometry["vertical_rules"][0]/2,geometry["vertical_rules"][-1]/2
    geometry["row_heights"][0]+=top
    geometry["row_heights"][-1]+=bottom
    geometry["columns"][0]+=left
    geometry["columns"][-1]+=right
    for cell in geometry["cells"]:
        for line in cell["lines"]:
            if cell["row"]==0:line["baseline"]+=top
            if cell["col"]==0:line["start_x"]+=left
            for run in line.get("semantic_runs",[]):
                if cell["row"]==0 and "baseline" in run:run["baseline"]+=top
                if cell["col"]==0:run["start_x"]+=left
            for relation in line.get("relations",[]):
                if cell["row"]==0:relation["baseline"]+=top
                if cell["col"]==0:relation["center"]+=left
            if "source_bbox" in line:
                dx=left if cell["col"]==0 else 0
                dy=top if cell["row"]==0 else 0
                line["source_bbox"]=[line["source_bbox"][0]+dx,line["source_bbox"][1]+dy,
                                     line["source_bbox"][2]+dx,line["source_bbox"][3]+dy]
    if geometry.get("turns"):
        geometry["x"]-=top;geometry["y"]-=right
        geometry["width"]+=top+bottom;geometry["height"]+=left+right
    else:
        geometry["x"]-=left;geometry["y"]-=top
        geometry["width"]+=left+right;geometry["height"]+=top+bottom
    return geometry


def _rule_outer_edges(source):
    """Reserve the stroke envelope around authored centreline endpoints."""
    geometry=dict(source)
    half=source["width"]/2
    geometry["x"]-=half
    geometry["y"]-=half
    geometry["height"]+=source["width"]
    return geometry


def _load_pages(source_pages, pages_root):
    result = []
    all_ids = set()
    appearance = _appearance()
    layout=json.loads((FIXTURE_ROOT / "source-layout.json").read_text(encoding="utf-8"))
    source_layout={page["source_page"]:page for page in layout["pages"]}
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
        leaves={}
        declared=[]
        def collect(blocks):
            for block in blocks:
                declared.append(block["id"])
                if block["type"] in ("stack","columns"):
                    collect(block["children"])
                elif block["type"]!="spacer":
                    leaves[block["id"]]=block
        collect(data["blocks"])
        placements=[]
        for geometry in source_layout[number]["blocks"]:
            typography=font_profile()["items"].get(geometry["id"],{})
            if "font_runs" in typography:
                geometry={**geometry,"font_runs":typography["font_runs"]}
            if geometry["kind"]=="table":geometry=_table_outer_edges(geometry)
            if geometry["kind"]=="rule":geometry=_rule_outer_edges(geometry)
            if geometry["id"] not in leaves:
                raise LayoutOverflowError(f"原本再現できず: p{number:02} missing declared source block {geometry['id']}",block_id=f"p{number:02}")
            placements.append((build_block(leaves.pop(geometry["id"]),geometry),geometry))
        if leaves:
            raise LayoutOverflowError(f"原本再現できず: p{number:02} unplaced content {sorted(leaves)}",block_id=f"p{number:02}")
        # Custom manuscripts cannot silently add blank overflow after the fixed source frame.
        if pages_root.resolve()!=(FIXTURE_ROOT / "pages").resolve():
            original=json.loads((FIXTURE_ROOT / f"pages/p{number:02}.json").read_text("utf-8"))
            if data!=original:
                raise LayoutOverflowError(f"原本再現できず: p{number:02} modified manuscript requires reviewed source placement",block_id=f"p{number:02}")
        frame = appearance.PageFrame(number,tuple(placements),tuple([f"p{number:02}-content",*declared]))
        result.append((number,[frame]))
    return result


def build_document(fonts, *, source_pages=SOURCE_PAGES, pages_root=None):
    pages = _selection(source_pages)
    groups = _load_pages(pages, Path(pages_root) if pages_root is not None else FIXTURE_ROOT / "pages")
    return _document(fonts, groups)


def _document(fonts, groups):
    if fonts is None:
        raise ValueError("fixture documents need fixture_fonts(), which pins the original font files")
    groups=tuple(groups)
    source_frame=any(isinstance(block,_appearance().PageFrame) for _,content in groups for block in content)
    blocks = []
    for index, (number, content) in enumerate(groups):
        if index:
            blocks.append(PageBreak())
        inner=content[0] if len(content)==1 and isinstance(content[0],_appearance().PageFrame) else Stack(*content,block_id=f"p{number:02}-content")
        blocks.append(KeepTogether(inner,block_id=f"p{number:02}"))
    return Document(*blocks, fonts=fonts, profile=SOURCE_PROFILE if source_frame else A4_PORTRAIT_REFERENCE, style=SOURCE_STYLE)


def guard_fixed_pages(pages, source_pages, declared_blocks=None):
    expected = _selection(source_pages)
    if len(pages) != len(expected):
        raise LayoutOverflowError(f"原本再現できず: expected {len(expected)} pages, got {len(pages)}",
                                  needed=len(pages), available=len(expected))
    for page, source in zip(pages, expected):
        placements = page.metadata.get("placements", ())
        if (page.profile not in (A4_PORTRAIT_REFERENCE,SOURCE_PROFILE) or not page.commands or len(placements) != 1
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
    for child in getattr(block, "children", ()):
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
    groups = _load_pages(selected, Path(pages_root) if pages_root else FIXTURE_ROOT / "pages")
    return layout_blocks(fonts, groups)


def fixture_fonts():
    """Resolve the original faces by name and pin each resolved file and face."""
    fonts = FontRegistry()
    for name,definition in font_profile()["fonts"].items():
        face=fonts.resolve(name)
        if face.path.name.lower()!=definition["file"] or face.face_index!=definition["face_index"]:
            raise ValueError(f"Original font moved: {name} resolved to {face.path} face {face.face_index}")
        if face.sha256!=definition["sha256"]:
            raise ValueError(f"Original font hash changed: {name} at {face.path}")
    return fonts
