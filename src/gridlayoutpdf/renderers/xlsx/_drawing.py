"""DrawingML for a worksheet: lines, freeforms, preset shapes, text, groups, pictures.

Every top-level drawing gets a ``twoCellAnchor`` so it moves and sizes with
its cells. A coordinate is placed at the same fraction of its cell in Excel's
whole-pixel cell sizes (``_units``), so rounding a column or row to pixels
never moves a shape into a neighbouring cell. Shape transforms use the same
mapping, and groups use an identity child coordinate space.
"""

import bisect
from collections.abc import Callable, Sequence

from ._model import (
    Diamond,
    Ellipse,
    Font,
    Group,
    Line,
    Picture,
    Polyline,
    Rect,
    Run,
    Sheet,
    TextBox,
    TextFrame,
)
from ._units import EDGE_TOLERANCE_PT, EMU_PER_PT, dash_value, excel_column_width_pt, excel_row_height_pt, pt_to_emu
from ._xml import RELATIONSHIPS_NS, XML_DECLARATION, element, escape_text, rgb_hex

_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_ALIGN = {"left": "l", "center": "ctr", "right": "r"}
_ANCHOR = {"top": "t", "center": "ctr", "bottom": "b"}
_VERTICAL = {0: "horz", 90: "vert270", 180: "horz", 270: "vert"}
_BASELINE = {None: None, "superscript": 30000, "subscript": -25000}


def _running_sums(sizes: Sequence[float]) -> list[float]:
    """Return 0 and every prefix sum, compensated (Neumaier) to match ``math.fsum`` within an ulp."""
    sums, total, compensation = [0.0], 0.0, 0.0
    for size in sizes:
        updated = total + size
        if abs(total) >= abs(size):
            compensation += (total - updated) + size
        else:
            compensation += (size - updated) + total
        total = updated
        sums.append(total + compensation)
    return sums


class _Axis:
    """Map model pt along one axis to Excel's (cell, EMU offset) and absolute EMU."""

    def __init__(self, sizes: Sequence[float], actual: Callable[[float], float]) -> None:
        self.sizes = tuple(sizes)
        self.edges = _running_sums(self.sizes)
        self.actual = tuple(actual(size) for size in self.sizes)
        self.actual_edges = _running_sums(self.actual)

    def anchor(self, value: float) -> tuple[int, int]:
        """Return (cell, EMU offset); a value on a cell boundary starts the next cell.

        Values within ``EDGE_TOLERANCE_PT`` of a boundary are taken as on
        it, so a boundary computed with float error is still written as
        ``(k, 0)``; the sheet's far edge is the end of the last cell. Values
        outside the sheet (only float error passes the model's check) are
        held at its edges.
        """
        last = len(self.sizes) - 1
        index = min(max(bisect.bisect_right(self.edges, value) - 1, 0), last)
        if index < last and self.edges[index + 1] - value <= EDGE_TOLERANCE_PT:
            index += 1
        if value - self.edges[index] <= EDGE_TOLERANCE_PT:
            return index, 0
        if index == last and abs(value - self.edges[-1]) <= EDGE_TOLERANCE_PT:
            return index, round(self.actual[index] * EMU_PER_PT)
        fraction = min(max((value - self.edges[index]) / self.sizes[index], 0.0), 1.0)
        return index, round(fraction * self.actual[index] * EMU_PER_PT)

    def emu(self, value: float) -> int:
        index, offset = self.anchor(value)
        return pt_to_emu(self.actual_edges[index]) + offset


class SheetGeometry:
    """Cell geometry of one sheet in the model's pt and in Excel's pixels."""

    def __init__(self, sheet: Sheet) -> None:
        self.x = _Axis(sheet.column_widths_pt, excel_column_width_pt)
        self.y = _Axis(sheet.row_heights_pt, excel_row_height_pt)

    def point(self, x: float, y: float) -> tuple[int, int]:
        return self.x.emu(x), self.y.emu(y)

    def box(self, left: float, top: float, right: float, bottom: float) -> tuple[int, int, int, int]:
        x0, y0 = self.point(left, top)
        x1, y1 = self.point(right, bottom)
        return x0, y0, x1 - x0, y1 - y0


class MediaTable:
    """Workbook-wide images, deduplicated and numbered in order of first use."""

    def __init__(self) -> None:
        self.items: list[tuple[str, bytes]] = []
        self._index: dict[tuple[str, bytes], int] = {}

    def add(self, format_name: str, data: bytes) -> str:
        key = (format_name, data)
        index = self._index.get(key)
        if index is None:
            index = self._index[key] = len(self.items)
            self.items.append(key)
        return f"image{index + 1}.{format_name}"

    def parts(self) -> list[tuple[str, bytes]]:
        return [(f"xl/media/image{index}.{fmt}", data) for index, (fmt, data) in enumerate(self.items, start=1)]


def _color_fill(color) -> str:
    return element("a:solidFill", body=element("a:srgbClr", (("val", rgb_hex(color)),)))


def _dash_xml(dash: tuple[float, ...], width_pt: float) -> str:
    lengths = dash * 2 if len(dash) % 2 else dash  # an odd pattern repeats, as in PDF
    stops = "".join(
        element("a:ds", (("d", dash_value(lengths[index], width_pt)),
                         ("sp", dash_value(lengths[index + 1], width_pt))))
        for index in range(0, len(lengths), 2))
    return element("a:custDash", body=stops)


def _line_xml(drawing, stroke: bool = True) -> str:
    if not stroke:
        return element("a:ln", body="<a:noFill/>")
    body = _color_fill(drawing.color)
    if drawing.dash:
        body += _dash_xml(drawing.dash, drawing.stroke_width_pt)
    body += "<a:round/>"
    for tag, arrow in (("a:headEnd", getattr(drawing, "start_arrow", None)),
                       ("a:tailEnd", getattr(drawing, "end_arrow", None))):
        if arrow is not None:
            body += element(tag, (("type", arrow.kind), ("w", arrow.width), ("len", arrow.length)))
    return element("a:ln", (("w", pt_to_emu(drawing.stroke_width_pt)), ("cap", "flat")), body)


def _fill_xml(fill) -> str:
    return "<a:noFill/>" if fill is None else _color_fill(fill)


def _xfrm(x: int, y: int, cx: int, cy: int, *, flip_h: bool = False, flip_v: bool = False,
          child: bool = False) -> str:
    body = element("a:off", (("x", x), ("y", y))) + element("a:ext", (("cx", cx), ("cy", cy)))
    if child:
        body += element("a:chOff", (("x", x), ("y", y))) + element("a:chExt", (("cx", cx), ("cy", cy)))
    return element("a:xfrm", (("flipH", True if flip_h else None), ("flipV", True if flip_v else None)), body)


def _preset(name: str, guides: tuple[tuple[str, int], ...] = ()) -> str:
    body = "".join(element("a:gd", (("name", key), ("fmla", f"val {value}"))) for key, value in guides)
    return element("a:prstGeom", (("prst", name),), element("a:avLst", body=body or None))


def _run_properties(run_font: Font, vert_align: str | None, tag: str = "a:rPr") -> str:
    body = (_color_fill(run_font.color)
            + element("a:latin", (("typeface", run_font.name),))
            + element("a:ea", (("typeface", run_font.name),))
            + element("a:cs", (("typeface", run_font.name),)))
    return element(tag, (("lang", "ja-JP"), ("altLang", "en-US"), ("sz", round(run_font.size * 100)),
                         ("b", run_font.bold), ("i", run_font.italic), ("baseline", _BASELINE[vert_align])), body)


def _paragraph(runs: tuple[Run, ...], frame: TextFrame) -> str:
    body = element("a:pPr", (("algn", _ALIGN[frame.h_align]),))
    for run in runs:
        body += element("a:r", body=_run_properties(run.font or frame.font, run.vert_align)
                        + element("a:t", body=escape_text(run.text)))
    if not runs:
        body += _run_properties(frame.font, None, "a:endParaRPr")
    return element("a:p", body=body)


def _text_body(frame: TextFrame | None) -> str:
    if frame is None:
        return ""
    left, top, right, bottom = frame.insets_pt
    body_properties = element("a:bodyPr", (
        ("vertOverflow", "overflow"), ("horzOverflow", "overflow"), ("vert", _VERTICAL[frame.rotation]),
        ("wrap", "square" if frame.wrap else "none"), ("lIns", pt_to_emu(left)), ("tIns", pt_to_emu(top)),
        ("rIns", pt_to_emu(right)), ("bIns", pt_to_emu(bottom)), ("rtlCol", False),
        ("anchor", _ANCHOR[frame.v_align]), ("rot", 10_800_000 if frame.rotation == 180 else None)))
    paragraphs = "".join(_paragraph(runs, frame) for runs in frame.paragraphs)
    return element("xdr:txBody", body=body_properties + "<a:lstStyle/>" + paragraphs)


class _Writer:
    def __init__(self, sheet: Sheet, media: MediaTable) -> None:
        self.geometry = SheetGeometry(sheet)
        self.media = media
        self.relationships: list[str] = []  # media targets, in rId order
        self._next_id = 2

    def _identity(self, kind: str) -> str:
        shape_id = self._next_id
        self._next_id += 1
        return element("xdr:cNvPr", (("id", shape_id), ("name", f"{kind} {shape_id - 1}")))

    def shape(self, drawing) -> str:
        if isinstance(drawing, Line):
            return self._line(drawing)
        if isinstance(drawing, Polyline):
            return self._polyline(drawing)
        if isinstance(drawing, Picture):
            return self._picture(drawing)
        if isinstance(drawing, Group):
            return self._group(drawing)
        return self._area(drawing)

    def _line(self, line: Line) -> str:
        x1, y1 = self.geometry.point(line.x1, line.y1)
        x2, y2 = self.geometry.point(line.x2, line.y2)
        identity = self._identity("Straight Connector")
        properties = element("xdr:spPr", body=_xfrm(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1),
                                                     flip_h=x2 < x1, flip_v=y2 < y1)
                             + _preset("line") + _line_xml(line))
        return element("xdr:cxnSp", (("macro", ""),),
                       element("xdr:nvCxnSpPr", body=identity + "<xdr:cNvCxnSpPr/>") + properties)

    def _polyline(self, polyline: Polyline) -> str:
        points = [self.geometry.point(x, y) for x, y in polyline.points]
        left, top = min(x for x, _ in points), min(y for _, y in points)
        width = max(x for x, _ in points) - left
        height = max(y for _, y in points) - top
        commands = []
        for index, (x, y) in enumerate(points):
            point = element("a:pt", (("x", x - left), ("y", y - top)))
            commands.append(element("a:moveTo" if index == 0 else "a:lnTo", body=point))
        if polyline.closed:
            commands.append("<a:close/>")
        path = element("a:path", (("w", max(width, 1)), ("h", max(height, 1)),
                                  ("fill", None if polyline.closed else "none")), "".join(commands))
        geometry = element("a:custGeom", body=(
            "<a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/>"
            + element("a:rect", (("l", 0), ("t", 0), ("r", "r"), ("b", "b")))
            + element("a:pathLst", body=path)))
        identity = self._identity("Freeform")
        properties = element("xdr:spPr", body=_xfrm(left, top, width, height) + geometry
                             + _fill_xml(polyline.fill) + _line_xml(polyline, polyline.stroke))
        return element("xdr:sp", (("macro", ""), ("textlink", "")),
                       element("xdr:nvSpPr", body=identity + "<xdr:cNvSpPr/>") + properties)

    def _area(self, drawing) -> str:
        x, y, cx, cy = self.geometry.box(*drawing.bounds())
        if isinstance(drawing, TextBox):
            kind, geometry, fill, line = "TextBox", _preset("rect"), "<a:noFill/>", "<a:ln><a:noFill/></a:ln>"
        else:
            if isinstance(drawing, Rect) and drawing.corner_radius_pt > 0:
                shorter = min(cx, cy) / EMU_PER_PT
                adjust = min(50_000, round(drawing.corner_radius_pt / shorter * 100_000)) if shorter else 50_000
                kind, geometry = "Rounded Rectangle", _preset("roundRect", (("adj", adjust),))
            elif isinstance(drawing, Rect):
                kind, geometry = "Rectangle", _preset("rect")
            elif isinstance(drawing, Ellipse):
                kind, geometry = "Oval", _preset("ellipse")
            elif isinstance(drawing, Diamond):
                kind, geometry = "Diamond", _preset("diamond")
            else:
                raise ValueError(f"unknown drawing {type(drawing).__name__}")
            fill, line = _fill_xml(drawing.fill), _line_xml(drawing, drawing.stroke)
        identity = self._identity(kind)
        non_visual = "<xdr:cNvSpPr txBox=\"1\"/>" if isinstance(drawing, TextBox) else "<xdr:cNvSpPr/>"
        properties = element("xdr:spPr", body=_xfrm(x, y, cx, cy) + geometry + fill + line)
        return element("xdr:sp", (("macro", ""), ("textlink", "")),
                       element("xdr:nvSpPr", body=identity + non_visual) + properties + _text_body(drawing.text))

    def _picture(self, picture: Picture) -> str:
        target = self.media.add(picture.format, picture.data)
        if target not in self.relationships:
            self.relationships.append(target)
        relationship = f"rId{self.relationships.index(target) + 1}"
        x, y, cx, cy = self.geometry.box(*picture.bounds())
        identity = self._identity("Picture")
        return element("xdr:pic", body=(
            element("xdr:nvPicPr", body=identity + element(
                "xdr:cNvPicPr", body=element("a:picLocks", (("noChangeAspect", True),))))
            + element("xdr:blipFill", body=element("a:blip", (("r:embed", relationship),))
                      + "<a:stretch><a:fillRect/></a:stretch>")
            + element("xdr:spPr", body=_xfrm(x, y, cx, cy) + _preset("rect"))))

    def _group(self, group: Group) -> str:
        x, y, cx, cy = self.geometry.box(*group.bounds())
        identity = self._identity("Group")
        children = "".join(self.shape(child) for child in group.children)
        return element("xdr:grpSp", body=(
            element("xdr:nvGrpSpPr", body=identity + "<xdr:cNvGrpSpPr/>")
            + element("xdr:grpSpPr", body=_xfrm(x, y, cx, cy, child=True)) + children))

    def anchor(self, drawing) -> str:
        left, top, right, bottom = drawing.bounds()
        shape = self.shape(drawing)

        def marker(tag: str, x: float, y: float) -> str:
            col, col_offset = self.geometry.x.anchor(x)
            row, row_offset = self.geometry.y.anchor(y)
            return element(tag, body=element("xdr:col", body=str(col)) + element("xdr:colOff", body=str(col_offset))
                           + element("xdr:row", body=str(row)) + element("xdr:rowOff", body=str(row_offset)))

        return element("xdr:twoCellAnchor", body=marker("xdr:from", left, top) + marker("xdr:to", right, bottom)
                       + shape + "<xdr:clientData/>")


def drawing_xml(sheet: Sheet, media: MediaTable) -> tuple[str, list[str]]:
    """Return the drawing part and its image targets (``rId1`` first)."""
    writer = _Writer(sheet, media)
    anchors = "".join(writer.anchor(drawing) for drawing in sheet.drawings)
    namespaces = (("xmlns:xdr", _XDR), ("xmlns:a", _A), ("xmlns:r", RELATIONSHIPS_NS))
    xml = XML_DECLARATION + element("xdr:wsDr", namespaces, anchors)
    return xml, writer.relationships
