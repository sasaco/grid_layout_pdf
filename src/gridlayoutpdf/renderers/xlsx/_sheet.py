"""Worksheet and shared string parts."""

import re

from ._model import CellValue, Font, RichText, Run, Sheet
from ._styles import CellFormat, StyleTable, font_xml
from ._units import column_width_chars, excel_row_height_pt
from ._xml import (
    RELATIONSHIPS_NS,
    SPREADSHEET_NS,
    XML_DECLARATION,
    cell_reference,
    element,
    escape_spreadsheet_text,
    number,
)


def _text_element(text: str) -> str:
    preserve = (("xml:space", "preserve"),) if text != text.strip() or "\n" in text or "\t" in text else ()
    return element("t", preserve, escape_spreadsheet_text(text))


def _resolved(rich: RichText, font: Font) -> RichText:
    """Give every run an explicit font so equal-looking texts share one entry."""
    return RichText(tuple(Run(run.text, run.font or font, run.vert_align) for run in rich.runs))


def _string_item_xml(item) -> str:
    if isinstance(item, str):
        return element("si", body=_text_element(item))
    runs = "".join(
        element("r", body=element("rPr", body=font_xml(run.font, "rFont", run.vert_align)) + _text_element(run.text))
        for run in item.runs)
    return element("si", body=runs)


class SharedStrings:
    """Deduplicated shared strings, numbered in order of first appearance."""

    def __init__(self) -> None:
        self.items: list = []
        self._index: dict = {}
        self.references = 0

    def add(self, value) -> int:
        self.references += 1
        index = self._index.get(value)
        if index is None:
            index = self._index[value] = len(self.items)
            self.items.append(value)
        return index

    def xml(self) -> str:
        body = "".join(_string_item_xml(item) for item in self.items)
        return XML_DECLARATION + element(
            "sst", (("xmlns", SPREADSHEET_NS), ("count", self.references), ("uniqueCount", len(self.items))), body)


def _columns(sheet: Sheet, styles: StyleTable) -> str:
    """Group equal neighbouring widths into one ``<col>`` element."""
    widths = [column_width_chars(width, styles.default_font) for width in sheet.column_widths_pt]
    groups = []
    start = 0
    for index in range(1, len(widths) + 1):
        if index == len(widths) or widths[index] != widths[start]:
            groups.append(element("col", (("min", start + 1), ("max", index), ("width", widths[start]),
                                          ("customWidth", True))))
            start = index
    return element("cols", body="".join(groups))


def _cell_borders(sheet: Sheet) -> dict[tuple[int, int], tuple]:
    sides: dict[tuple[int, int], list] = {}
    for border in sheet.borders:
        sides.setdefault((border.row, border.col), []).append((border.side, border.style, border.color))
    return {cell: tuple(sorted(items)) for cell, items in sides.items()}


def _cell_xml(row: int, col: int, cell: CellValue | None, border: tuple,
              styles: StyleTable, strings: SharedStrings) -> str:
    font = (cell.font if cell is not None else None) or styles.default_font
    if cell is None:
        cell_format = CellFormat(font, border=border)
    else:
        cell_format = CellFormat(font, cell.number_format, cell.fill, border, cell.h_align, cell.v_align,
                                 cell.rotation)
    attributes = [("r", cell_reference(row, col)), ("s", styles.index(cell_format))]
    value = None if cell is None else cell.value
    if value is None:
        return element("c", tuple(attributes))
    if isinstance(value, (str, RichText)):
        attributes.append(("t", "s"))
        index = strings.add(value if isinstance(value, str) else _resolved(value, font))
        return element("c", tuple(attributes), element("v", body=str(index)))
    return element("c", tuple(attributes), element("v", body=number(value)))


def _merges(sheet: Sheet) -> str:
    if not sheet.merges:
        return ""
    items = "".join(
        element("mergeCell", (("ref", f"{cell_reference(merge.first_row, merge.first_col)}:"
                                      f"{cell_reference(merge.last_row, merge.last_col)}"),))
        for merge in sheet.merges)
    return element("mergeCells", (("count", len(sheet.merges)),), items)


_PAPER_CODES = {"A4": 9, "A3": 8}


def _inches(value_pt: float) -> float:
    return round(value_pt / 72, 9)


def _print_settings(sheet: Sheet) -> str:
    page = sheet.page
    margins = page.margins
    parts = [
        element("printOptions", (("gridLines", page.print_gridlines),)),
        element("pageMargins", (
            ("left", _inches(margins.left)), ("right", _inches(margins.right)), ("top", _inches(margins.top)),
            ("bottom", _inches(margins.bottom)), ("header", _inches(margins.header)),
            ("footer", _inches(margins.footer)))),
        element("pageSetup", (
            ("paperSize", _PAPER_CODES[page.paper]), ("scale", page.scale),
            ("firstPageNumber", page.first_page_number), ("orientation", page.orientation),
            ("useFirstPageNumber", True if page.first_page_number is not None else None))),
    ]
    if sheet.header is not None or sheet.footer is not None:
        body = ""
        if sheet.header is not None:
            body += element("oddHeader", body=escape_spreadsheet_text(sheet.header.code()))
        if sheet.footer is not None:
            body += element("oddFooter", body=escape_spreadsheet_text(sheet.footer.code()))
        parts.append(element("headerFooter", body=body))
    if sheet.row_breaks:
        breaks = "".join(element("brk", (("id", row), ("max", 16383), ("man", True))) for row in sheet.row_breaks)
        parts.append(element("rowBreaks", (("count", len(sheet.row_breaks)),
                                           ("manualBreakCount", len(sheet.row_breaks))), breaks))
    return "".join(parts)


def sheet_xml(sheet: Sheet, styles: StyleTable, strings: SharedStrings, *, selected: bool = False,
              drawing_relationship: str | None = None) -> str:
    """Write one worksheet; elements follow the CT_Worksheet sequence."""
    values = {(cell.row, cell.col): cell for cell in sheet.cells}
    borders = _cell_borders(sheet)
    occupied: dict[int, list[int]] = {}
    for row, col in set(values) | set(borders):
        occupied.setdefault(row, []).append(col)
    rows = []
    for row, height in enumerate(sheet.row_heights_pt):
        cells = "".join(
            _cell_xml(row, col, values.get((row, col)), borders.get((row, col), ()), styles, strings)
            for col in sorted(occupied.get(row, ())))
        rows.append(element("row", (("r", row + 1), ("ht", excel_row_height_pt(height)), ("customHeight", True)),
                            cells or None))
    view = element("sheetView", (("showGridLines", False if not sheet.show_gridlines else None),
                                 ("tabSelected", True if selected else None), ("workbookViewId", 0)))
    body = (
        element("dimension", (("ref", f"A1:{last_cell(sheet)}"),))
        + element("sheetViews", body=view)
        + element("sheetFormatPr", (("defaultRowHeight", excel_row_height_pt(sheet.row_heights_pt[0])),))
        + _columns(sheet, styles)
        + element("sheetData", body="".join(rows))
        + _merges(sheet)
        + _print_settings(sheet)
        + (element("drawing", (("r:id", drawing_relationship),)) if drawing_relationship else "")
    )
    return XML_DECLARATION + element(
        "worksheet", (("xmlns", SPREADSHEET_NS), ("xmlns:r", RELATIONSHIPS_NS)), body)


def last_cell(sheet: Sheet) -> str:
    return cell_reference(len(sheet.row_heights_pt) - 1, len(sheet.column_widths_pt) - 1)


def print_area(sheet: Sheet) -> str:
    """Return the whole grid as an absolute reference for ``_xlnm.Print_Area``."""
    quoted = sheet.name.replace("'", "''")
    first, last = "$A$1", "$" + re.sub(r"(\d+)$", r"$\1", last_cell(sheet))
    return f"'{quoted}'!{first}:{last}"
