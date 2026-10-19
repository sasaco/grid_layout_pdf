"""styles.xml: fonts, fills, borders, number formats and cell formats.

Every table is deduplicated and numbered in order of first appearance, so the
same model always gives the same indexes.
"""

from dataclasses import dataclass

from ._model import BUILTIN_NUMBER_FORMATS, Color, Font
from ._xml import SPREADSHEET_NS, XML_DECLARATION, element, rgb_hex


_FIRST_CUSTOM_NUMBER_FORMAT = 164  # custom formats are numbered from here
_EXCEL_TEXT_ROTATION = {0: 0, 90: 90, 270: 180}  # counterclockwise degrees -> Excel's textRotation
_BORDER_SIDES = ("left", "right", "top", "bottom")

BorderSides = tuple[tuple[str, str, Color], ...]


def argb(color: Color) -> str:
    return "FF" + rgb_hex(color)


def font_xml(font: Font, tag: str = "name", vert_align: str | None = None) -> str:
    """Write a font body; ``tag`` is ``name`` in styles and ``rFont`` in runs."""
    parts = []
    if font.bold:
        parts.append("<b/>")
    if font.italic:
        parts.append("<i/>")
    if vert_align is not None:
        parts.append(element("vertAlign", (("val", vert_align),)))
    parts.append(element("sz", (("val", font.size),)))
    parts.append(element("color", (("rgb", argb(font.color)),)))
    parts.append(element(tag, (("val", font.name),)))
    return "".join(parts)


@dataclass(frozen=True, slots=True)
class CellFormat:
    """The hashable key of one ``cellXfs`` entry."""

    font: Font
    number_format: str | None = None
    fill: Color | None = None
    border: BorderSides = ()
    h_align: str = "left"
    v_align: str = "center"
    rotation: int = 0


class _Table:
    def __init__(self) -> None:
        self.items: list = []
        self._index: dict = {}

    def add(self, item) -> int:
        index = self._index.get(item)
        if index is None:
            index = self._index[item] = len(self.items)
            self.items.append(item)
        return index


class StyleTable:
    """Collect cell formats while the sheets are written."""

    def __init__(self, default_font: Font) -> None:
        self.default_font = default_font
        self._fonts = _Table()
        self._fonts.add(default_font)
        self._fills = _Table()
        self._fills.add("none")
        self._fills.add("gray125")
        self._borders = _Table()
        self._borders.add(())
        self._number_formats = _Table()
        self._xfs = _Table()
        self._xfs.add((0, 0, 0, 0, None))  # cellXfs 0 is the Normal style

    def _number_format_id(self, code: str | None) -> int:
        if code is None:
            return 0
        if code in BUILTIN_NUMBER_FORMATS:
            return BUILTIN_NUMBER_FORMATS[code]
        return _FIRST_CUSTOM_NUMBER_FORMAT + self._number_formats.add(code)

    def index(self, cell_format: CellFormat) -> int:
        """Return the ``s`` index of a cell format, registering its parts."""
        alignment = (cell_format.h_align, cell_format.v_align, _EXCEL_TEXT_ROTATION[cell_format.rotation])
        key = (
            self._number_format_id(cell_format.number_format),
            self._fonts.add(cell_format.font),
            0 if cell_format.fill is None else self._fills.add(cell_format.fill),
            self._borders.add(cell_format.border),
            alignment,
        )
        return self._xfs.add(key)

    def xml(self) -> str:
        number_formats = "".join(
            element("numFmt", (("numFmtId", _FIRST_CUSTOM_NUMBER_FORMAT + index), ("formatCode", code)))
            for index, code in enumerate(self._number_formats.items))
        fonts = "".join(element("font", body=font_xml(font)) for font in self._fonts.items)
        fills = "".join(_fill_xml(fill) for fill in self._fills.items)
        borders = "".join(_border_xml(border) for border in self._borders.items)
        xfs = "".join(_xf_xml(*key) for key in self._xfs.items)
        body = (
            (element("numFmts", (("count", len(self._number_formats.items)),), number_formats)
             if self._number_formats.items else "")
            + element("fonts", (("count", len(self._fonts.items)),), fonts)
            + element("fills", (("count", len(self._fills.items)),), fills)
            + element("borders", (("count", len(self._borders.items)),), borders)
            + element("cellStyleXfs", (("count", 1),),
                      element("xf", (("numFmtId", 0), ("fontId", 0), ("fillId", 0), ("borderId", 0))))
            + element("cellXfs", (("count", len(self._xfs.items)),), xfs)
            + element("cellStyles", (("count", 1),),
                      element("cellStyle", (("name", "Normal"), ("xfId", 0), ("builtinId", 0))))
        )
        return XML_DECLARATION + element("styleSheet", (("xmlns", SPREADSHEET_NS),), body)


def _fill_xml(fill) -> str:
    if isinstance(fill, str):
        return element("fill", body=element("patternFill", (("patternType", fill),)))
    return element("fill", body=element(
        "patternFill", (("patternType", "solid"),),
        element("fgColor", (("rgb", argb(fill)),)) + element("bgColor", (("indexed", 64),))))


def _border_xml(border: BorderSides) -> str:
    by_side = {side: (style, color) for side, style, color in border}
    parts = []
    for side in _BORDER_SIDES:
        if side in by_side:
            style, color = by_side[side]
            parts.append(element(side, (("style", style),), element("color", (("rgb", argb(color)),))))
        else:
            parts.append(element(side))
    parts.append(element("diagonal"))
    return element("border", body="".join(parts))


def _xf_xml(number_format_id: int, font_id: int, fill_id: int, border_id: int, alignment) -> str:
    attributes = [("numFmtId", number_format_id), ("fontId", font_id), ("fillId", fill_id),
                  ("borderId", border_id), ("xfId", 0)]
    if alignment is None:
        return element("xf", tuple(attributes))
    attributes += [("applyNumberFormat", number_format_id != 0), ("applyFont", True),
                   ("applyFill", fill_id != 0), ("applyBorder", border_id != 0), ("applyAlignment", True)]
    h_align, v_align, rotation = alignment
    return element("xf", tuple(attributes), element("alignment", (
        ("horizontal", h_align), ("vertical", v_align), ("textRotation", rotation or None))))
