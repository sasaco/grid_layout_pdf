"""Sheet layout and print settings read back with openpyxl and from the XML."""

import io
import re
import zipfile

import openpyxl
import pytest

from gridlayoutpdf.renderers.xlsx._model import (
    MAX_ROW_BREAKS,
    CellValue,
    Font,
    HeaderFooter,
    HeaderSection,
    Margins,
    SheetPageCount,
    PageNumber,
    PageSetup,
    Sheet,
    Workbook,
)
from gridlayoutpdf.renderers.xlsx._package import write_workbook


def _sheet(**kwargs):
    kwargs.setdefault("column_widths_pt", (16.08,) * 4)
    kwargs.setdefault("row_heights_pt", (15.48,) * 6)
    return Sheet(kwargs.pop("name", "計算書"), **kwargs)


def _bytes(*sheets):
    return write_workbook(Workbook(sheets))


def _read(*sheets):
    return openpyxl.load_workbook(io.BytesIO(_bytes(*sheets)))


def _part(data, name):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read(name).decode("utf-8")


def test_column_widths_and_row_heights_are_whole_pixels_in_excel_units():
    sheet = _read(_sheet(column_widths_pt=(16.08, 16.08, 8.04, 100), row_heights_pt=(15.48, 20.64, 12)))["計算書"]
    # 21 px = 2.625 characters of the 8 px digit width of 游ゴシック 11 pt.
    assert [sheet.column_dimensions[letter].width for letter in "AD"] == [2.625, 16.625]
    assert (sheet.column_dimensions["A"].min, sheet.column_dimensions["A"].max) == (1, 2)
    assert sheet.column_dimensions["C"].width == 1.375
    assert [sheet.row_dimensions[row].height for row in (1, 2, 3)] == [15.75, 21, 12]


def test_equal_neighbouring_column_widths_share_one_col_element():
    xml = _part(_bytes(_sheet(column_widths_pt=(16.08, 16.08, 8.04, 16.08))), "xl/worksheets/sheet1.xml")
    assert re.findall(r'<col min="(\d+)" max="(\d+)"', xml) == [("1", "2"), ("3", "3"), ("4", "4")]


def test_row_breaks_are_manual_breaks_above_the_given_rows():
    sheet = _read(_sheet(row_breaks=(2, 4)))["計算書"]
    assert [brk.id for brk in sheet.row_breaks.brk] == [2, 4]
    assert all(brk.man for brk in sheet.row_breaks.brk)


@pytest.mark.parametrize(("paper", "orientation", "code"), [
    ("A4", "portrait", 9), ("A3", "landscape", 8), ("A4", "landscape", 9),
])
def test_paper_and_orientation(paper, orientation, code):
    setup = _read(_sheet(page=PageSetup(paper=paper, orientation=orientation)))["計算書"].page_setup
    assert (int(setup.paperSize), setup.orientation) == (code, orientation)


def test_margins_in_pt_are_written_in_inches():
    margins = Margins(left=36, top=72, right=18, bottom=54, header=9, footer=27)
    read = _read(_sheet(page=PageSetup(margins=margins)))["計算書"].page_margins
    assert (read.left, read.top, read.right, read.bottom, read.header, read.footer) == (
        0.5, 1.0, 0.25, 0.75, 0.125, 0.375)


def test_scale_and_first_page_number():
    sheet = _read(_sheet(page=PageSetup(scale=85, first_page_number=7)))["計算書"]
    assert int(sheet.page_setup.scale) == 85
    assert int(sheet.page_setup.firstPageNumber) == 7
    assert sheet.page_setup.useFirstPageNumber
    assert sheet.sheet_properties.pageSetUpPr is None or not sheet.sheet_properties.pageSetUpPr.fitToPage


def test_without_first_page_number_excel_numbers_automatically():
    sheet = _read(_sheet())["計算書"]
    assert not sheet.page_setup.useFirstPageNumber


def test_gridlines_show_on_screen_and_not_in_print_by_default():
    sheet = _read(_sheet())["計算書"]
    assert sheet.sheet_view.showGridLines is not False
    assert not sheet.print_options.gridLines
    hidden = _read(_sheet(show_gridlines=False, page=PageSetup(print_gridlines=True)))["計算書"]
    assert hidden.sheet_view.showGridLines is False
    assert hidden.print_options.gridLines


def test_print_area_is_the_whole_grid():
    book = _read(_sheet(), _sheet(name="it's", column_widths_pt=(10,) * 30, row_heights_pt=(12,) * 3))
    assert book["計算書"].print_area == "'計算書'!$A$1:$D$6"
    assert book["it's"].print_area == "'it''s'!$A$1:$AD$3"


def test_header_and_footer_sections_with_page_number_and_escaped_ampersand():
    header = HeaderFooter(
        left=HeaderSection(("A&B ",)),
        center=HeaderSection(("- ", PageNumber(), " -")),
        right=HeaderSection((PageNumber(), "/", SheetPageCount())),
    )
    footer = HeaderFooter(center=HeaderSection(("計算書",), font=Font("ＭＳ 明朝", 9, bold=True, color=(1, 0, 0))))
    sheet = _read(_sheet(header=header, footer=footer))["計算書"]
    assert sheet.oddHeader.left.text == "A&&B "
    assert sheet.oddHeader.center.text == "- &P -"
    assert sheet.oddHeader.right.text == "&P/&N"
    assert sheet.oddFooter.center.text == "計算書"
    assert (sheet.oddFooter.center.font, sheet.oddFooter.center.size, sheet.oddFooter.center.color) == (
        "ＭＳ 明朝,Bold", 9, "FF0000")


def test_header_code_string_is_exact():
    header = HeaderFooter(left=HeaderSection(("x",), font=Font("Arial", 10, italic=True)),
                          right=HeaderSection((PageNumber(),)))
    assert header.code() == '&L&10&K000000&"Arial,Italic"x&R&P'


@pytest.mark.parametrize(("parts", "code"), [
    ((PageNumber(), "+1"), '&C&P&"-,Regular"+1'),
    ((SheetPageCount(), "-2"), '&C&N&"-,Regular"-2'),
    ((PageNumber(), "1"), "&C&P1"),
])
def test_text_after_a_page_field_never_becomes_page_arithmetic(parts, code):
    # Excel prints "&P+1" as the page number plus one (measured in Excel 16.0).
    assert HeaderFooter(center=HeaderSection(parts)).code() == code


def test_text_after_a_page_field_keeps_the_section_font():
    section = HeaderSection((PageNumber(), "+1"), font=Font("Arial", 10, bold=True))
    assert HeaderFooter(center=section).code() == '&C&10&K000000&"Arial,Bold"&P&"Arial,Bold"+1'


def test_sheet_xml_elements_follow_the_schema_order():
    sheet = _sheet(cells=(CellValue(0, 0, "x"),), row_breaks=(3,), show_gridlines=False,
                   header=HeaderFooter(center=HeaderSection(("h",))))
    xml = _part(_bytes(sheet), "xl/worksheets/sheet1.xml")
    order = ["<dimension", "<sheetViews", "<sheetFormatPr", "<cols", "<sheetData", "<printOptions",
             "<pageMargins", "<pageSetup", "<headerFooter", "<rowBreaks"]
    positions = [xml.index(tag) for tag in order]
    assert positions == sorted(positions)


# --- validation -----------------------------------------------------------


@pytest.mark.parametrize("breaks", [(0,), (6,), (3, 3), (4, 2), (1.0,), (True,)])
def test_row_breaks_must_be_increasing_rows_inside_the_sheet(breaks):
    with pytest.raises(ValueError, match="row break"):
        _sheet(row_breaks=breaks)


def test_row_breaks_above_excel_limit_are_errors():
    rows = (15.0,) * (MAX_ROW_BREAKS + 2)
    assert MAX_ROW_BREAKS == 1026
    assert len(_sheet(row_heights_pt=rows, row_breaks=tuple(range(1, MAX_ROW_BREAKS + 1))).row_breaks) == 1026
    with pytest.raises(ValueError, match="1026"):
        _sheet(row_heights_pt=rows, row_breaks=tuple(range(1, MAX_ROW_BREAKS + 2)))


@pytest.mark.parametrize("kwargs", [
    {"paper": "Letter"}, {"orientation": "up"}, {"scale": 9}, {"scale": 401}, {"scale": 85.0},
    {"first_page_number": 0}, {"first_page_number": 32768}, {"print_gridlines": 1}, {"margins": (0, 0, 0, 0, 0, 0)},
    {"margins": Margins(300, 0, 300, 0, 0, 0)}, {"margins": Margins(0, 450, 0, 450, 0, 0)},
])
def test_page_setup_rejects_values_excel_cannot_use(kwargs):
    with pytest.raises(ValueError):
        PageSetup(**kwargs)


@pytest.mark.parametrize("kwargs", [{"left": -1}, {"footer": float("nan")}, {"top": "1"}])
def test_margins_must_be_finite_and_not_negative(kwargs):
    arguments = {"left": 1, "top": 1, "right": 1, "bottom": 1, "header": 1, "footer": 1} | kwargs
    with pytest.raises(ValueError):
        Margins(**arguments)


@pytest.mark.parametrize("parts", [(), ("",), (3,), ("a\x01",)])
def test_header_sections_need_text_or_page_fields(parts):
    with pytest.raises(ValueError):
        HeaderSection(parts)


@pytest.mark.parametrize("font", [Font("Arial", 10.5), Font('A"B', 10), Font("A,B", 10), Font("-", 10)])
def test_header_font_must_be_expressible_in_header_codes(font):
    with pytest.raises(ValueError, match="header"):
        HeaderSection(("x",), font=font)


def test_header_longer_than_255_characters_is_an_error():
    with pytest.raises(ValueError, match="255"):
        HeaderFooter(center=HeaderSection(("&" * 128,)))


def test_header_footer_needs_at_least_one_section_and_sheet_needs_header_footer_type():
    with pytest.raises(ValueError):
        HeaderFooter()
    with pytest.raises(ValueError):
        _sheet(header="&P")
    with pytest.raises(ValueError):
        _sheet(page="A4")
    with pytest.raises(ValueError):
        _sheet(show_gridlines=None)


def test_header_font_name_with_an_ampersand_is_an_error():
    with pytest.raises(ValueError, match="header"):
        HeaderSection(("x",), font=Font("A&B", 10))


# --- review round 1 ----------------------------------------------------------


def test_header_text_is_escaped_for_spreadsheetml():
    header = HeaderFooter(center=HeaderSection(("M_x0030_",)))
    assert _read(_sheet(header=header))["計算書"].oddHeader.center.text == "M_x0030_"
    assert "M_x005F_x0030_" in _part(_bytes(_sheet(header=header)), "xl/worksheets/sheet1.xml")


def test_sheet_page_count_is_named_for_the_sheet():
    assert HeaderFooter(center=HeaderSection((SheetPageCount(),))).code() == "&C&N"


# --- review round 3 ----------------------------------------------------------


@pytest.mark.parametrize("text", ["12", "AB", "F0"])
def test_text_after_a_section_font_is_separated_from_the_color_code(text):
    # &KRRGGBB takes six hex digits; the quoted font name after it ends the codes.
    code = HeaderFooter(left=HeaderSection((text,), font=Font("ＭＳ 明朝", 9))).code()
    assert code == f'&L&9&K000000&"ＭＳ 明朝,Regular"{text}'
