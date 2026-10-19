"""Assemble the .xlsx ZIP package with fixed entry order, dates and compression."""

import io
import os
import tempfile
import zipfile
from pathlib import Path

from ._drawing import MediaTable, drawing_xml
from ._model import Workbook
from ._sheet import SharedStrings, print_area, sheet_xml
from ._styles import StyleTable
from ._xml import RELATIONSHIPS_NS, SPREADSHEET_NS, XML_DECLARATION, element, escape_text

_FIXED_DATE = (1980, 1, 1, 0, 0, 0)
_COMPRESS_LEVEL = 6
_PACKAGE_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
_SPREADSHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml"
_DRAWING_TYPE = "application/vnd.openxmlformats-officedocument.drawing+xml"


def _relationships(items: list[tuple[str, str, str]]) -> str:
    body = "".join(element("Relationship", (("Id", rid), ("Type", kind), ("Target", target)))
                   for rid, kind, target in items)
    return XML_DECLARATION + element("Relationships", (("xmlns", _PACKAGE_RELATIONSHIPS),), body)


def _parts(workbook: Workbook) -> list[tuple[str, bytes]]:
    styles = StyleTable(workbook.default_font)
    strings = SharedStrings()
    media = MediaTable()
    sheets, drawings = [], []
    for index, sheet in enumerate(workbook.sheets):
        relationship = None
        if sheet.drawings:
            drawings.append((index + 1, *drawing_xml(sheet, media)))
            relationship = "rId1"
        sheets.append(sheet_xml(sheet, styles, strings, selected=index == 0, drawing_relationship=relationship))

    overrides = [("/xl/workbook.xml", f"{_SPREADSHEET_TYPE}.sheet.main+xml"),
                 ("/xl/styles.xml", f"{_SPREADSHEET_TYPE}.styles+xml")]
    workbook_relationships = [
        (f"rId{index}", f"{RELATIONSHIPS_NS}/worksheet", f"worksheets/sheet{index}.xml")
        for index in range(1, len(sheets) + 1)
    ]
    next_id = len(sheets) + 1
    workbook_relationships.append((f"rId{next_id}", f"{RELATIONSHIPS_NS}/styles", "styles.xml"))
    if strings.items:
        overrides.append(("/xl/sharedStrings.xml", f"{_SPREADSHEET_TYPE}.sharedStrings+xml"))
        workbook_relationships.append(
            (f"rId{next_id + 1}", f"{RELATIONSHIPS_NS}/sharedStrings", "sharedStrings.xml"))
    for index in range(1, len(sheets) + 1):
        overrides.append((f"/xl/worksheets/sheet{index}.xml", f"{_SPREADSHEET_TYPE}.worksheet+xml"))
    for number in range(1, len(drawings) + 1):
        overrides.append((f"/xl/drawings/drawing{number}.xml", _DRAWING_TYPE))

    sheet_entries = "".join(
        element("sheet", (("name", sheet.name), ("sheetId", index), ("r:id", f"rId{index}")))
        for index, sheet in enumerate(workbook.sheets, start=1)
    )
    workbook_xml = XML_DECLARATION + element(
        "workbook", (("xmlns", SPREADSHEET_NS), ("xmlns:r", RELATIONSHIPS_NS)),
        element("bookViews", body=element("workbookView", ()))
        + element("sheets", body=sheet_entries)
        + element("definedNames", body="".join(
            element("definedName", (("name", "_xlnm.Print_Area"), ("localSheetId", index)),
                    escape_text(print_area(sheet)))
            for index, sheet in enumerate(workbook.sheets))),
    )
    image_types = sorted({format_name for format_name, _ in media.items})
    content_types = XML_DECLARATION + element(
        "Types", (("xmlns", _CONTENT_TYPES),),
        element("Default", (("Extension", "rels"),
                            ("ContentType", "application/vnd.openxmlformats-package.relationships+xml")))
        + element("Default", (("Extension", "xml"), ("ContentType", "application/xml")))
        + "".join(element("Default", (("Extension", name), ("ContentType", f"image/{name}"))) for name in image_types)
        + "".join(element("Override", (("PartName", name), ("ContentType", kind))) for name, kind in overrides),
    )
    parts = [
        ("[Content_Types].xml", content_types),
        ("_rels/.rels", _relationships([("rId1", f"{RELATIONSHIPS_NS}/officeDocument", "xl/workbook.xml")])),
        ("xl/workbook.xml", workbook_xml),
        ("xl/_rels/workbook.xml.rels", _relationships(workbook_relationships)),
        ("xl/styles.xml", styles.xml()),
    ]
    if strings.items:
        parts.append(("xl/sharedStrings.xml", strings.xml()))
    parts.extend((f"xl/worksheets/sheet{index}.xml", xml) for index, xml in enumerate(sheets, start=1))
    for number, (sheet_index, _, _) in enumerate(drawings, start=1):
        parts.append((f"xl/worksheets/_rels/sheet{sheet_index}.xml.rels", _relationships(
            [("rId1", f"{RELATIONSHIPS_NS}/drawing", f"../drawings/drawing{number}.xml")])))
    for number, (_, xml, images) in enumerate(drawings, start=1):
        parts.append((f"xl/drawings/drawing{number}.xml", xml))
        if images:
            parts.append((f"xl/drawings/_rels/drawing{number}.xml.rels", _relationships(
                [(f"rId{index}", f"{RELATIONSHIPS_NS}/image", f"../media/{target}")
                 for index, target in enumerate(images, 1)])))
    parts.extend(media.parts())
    return [(name, data.encode("utf-8") if isinstance(data, str) else data) for name, data in parts]


def write_workbook(workbook: Workbook) -> bytes:
    """Return the .xlsx bytes; the same model always gives the same bytes."""
    if not isinstance(workbook, Workbook):
        raise ValueError("write_workbook needs a Workbook")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in _parts(workbook):
            info = zipfile.ZipInfo(name, date_time=_FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o600 << 16  # what writestr would set; fixed for every platform
            archive.writestr(info, data, compresslevel=_COMPRESS_LEVEL)
    return buffer.getvalue()


def save_workbook(workbook: Workbook, path: str | os.PathLike) -> None:
    """Write the whole package first, then atomically replace ``path``."""
    data = write_workbook(workbook)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        if os.name == "posix":  # mkstemp creates 0600; give the file the usual permissions
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(temporary, 0o666 & ~umask)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
