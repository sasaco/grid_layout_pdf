"""FR-021: Excel opens reports written by render_xlsx without repair, reads them back and prints them (Step 8).

The Excel driver (hidden Excel through PowerShell COM, always quit, the
started process stopped if it stays) is the one of
``test_xlsx_excel_core.py``. Without Excel the tests are skipped with the
reason, or fail when GRIDLAYOUTPDF_REQUIRE_EXCEL=1. The print checks export
a PDF with Excel's active printer (never changed here) and record its name:
every grid boundary within half a cell of the PDF, a split table's top
border on the next page, and number cells that never show ###.
"""

import importlib.util
from pathlib import Path

from PIL import Image as PILImage
import pytest

from gridlayoutpdf import (
    A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE, Cell, Document, Equation, EquationAnchors, EquationGroup,
    Figure, Fraction, Image, Label, Operator, PageDecoration, PageProfile, PageSection, Paragraph,
    QuarterTurn, Row, Rule, Script, Table, TextBox, GridSpec,
)

_SPEC = importlib.util.spec_from_file_location("_xlsx_excel_core", Path(__file__).with_name("test_xlsx_excel_core.py"))
_core = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_core)

pytestmark = pytest.mark.skipif(_core._MISSING is not None and not _core._REQUIRED, reason=_core._MISSING or "")
A4 = PageProfile("A4 body", 595, 842, A4_PORTRAIT_REFERENCE.grid, 2, 45)
A3 = PageProfile("A3 body", 1191, 842, A3_LANDSCAPE_REFERENCE.grid, 2, 45)
PY, PX = A4.grid.pitch_y, A4.grid.pitch_x


@pytest.fixture(autouse=True)
def _excel_is_required():
    if _core._MISSING is not None:
        pytest.fail(f"GRIDLAYOUTPDF_REQUIRE_EXCEL=1 but {_core._MISSING}")


def padding(size):
    return 2.4 * max(1, size / 12)


_READ = r"""
  $book = $xl.Workbooks.Open($params.path, 0, $true)
  $sheets = @()
  foreach ($ws in $book.Worksheets) {
    $cells = @()
    foreach ($c in $ws.UsedRange.Cells) {
      if ($c.MergeCells -and $c.MergeArea.Cells.Item(1).Address() -ne $c.Address()) { continue }
      if ($null -eq $c.Value2) { continue }
      $runs = @()
      for ($k = 1; $k -le $c.Characters().Count; $k++) {
        $f = $c.Characters($k, 1).Font
        $runs += [ordered]@{ sup = $f.Superscript; sub = $f.Subscript }
      }
      $cells += [ordered]@{ address = $c.Address($false, $false); value = $c.Value2; text = $c.Text;
        format = $c.NumberFormat; h = $c.HorizontalAlignment; orientation = $c.Orientation;
        font = $c.Font.Name; size = $c.Font.Size; merge = $c.MergeArea.Address($false, $false); runs = $runs }
    }
    $edges = @(); foreach ($c in $ws.UsedRange.Cells) { if ($c.Borders.Item(8).LineStyle -eq 1) {
      $edges += [ordered]@{ address = $c.Address($false, $false); weight = $c.Borders.Item(8).Weight } } }
    $shapes = @(); foreach ($s in $ws.Shapes) { $shapes += [ordered]@{ type = $s.Type; text = $null; items = $null }
      if ($s.Type -eq 6) { $shapes[-1].items = $s.GroupItems.Count } }
    $p = $ws.PageSetup
    $sheets += [ordered]@{ name = $ws.Name; cells = $cells; edges = $edges; shapes = $shapes; zoom = $p.Zoom; first = $p.FirstPageNumber;
      paper = $p.PaperSize; orientation = $p.Orientation;
      header = @($p.LeftHeader, $p.CenterHeader, $p.RightHeader); footer = @($p.LeftFooter, $p.CenterFooter, $p.RightFooter) }
  }
  [ordered]@{ sheets = $sheets; count = $book.Worksheets.Count }
"""


@pytest.fixture(scope="module")
def excel(tmp_path_factory):
    directory = tmp_path_factory.mktemp("xlsx_map_excel")
    image = directory / "dot.png"
    PILImage.new("RGB", (8, 8), "blue").save(image)
    document = Document(
        Paragraph("1. 断面の諸元"),
        EquationGroup(
            Equation("I", Fraction(Row("4.50", Operator("×"), Script("2.70", superscript="3")), "12"),
                     result="7.381", unit=Script("m", superscript="4")),
            anchors=EquationAnchors(3, 15, 21, 22)),
        Paragraph("−2.000"),
        Table([4, 4], [[Cell("荷重"), Cell("12.150")]], numeric_columns=(1,)),
        Rule("medium"),
        QuarterTurn(Paragraph("回転"), turns=1, local_grid=GridSpec(0, 0, PY, PX, 4, 1)),
        PageSection(A3, Paragraph("横の頁")),
        Figure(10, 5, TextBox(4, 4, 80, 30, ("箱",)), Label(100, 20, "ラベル")),
        Image(image, col_span=2, rows=2),
        profile=A4,
        header=PageDecoration("計算書 {page}/{pages}", align="right"),
        footer=PageDecoration("- {page} -", align="center"),
    )
    path = directory / "report.xlsx"
    result = document.render_xlsx(path, "断面", strict=True, cell_padding_pt=padding)
    read = _core._run_excel(directory, _READ, {"path": str(path)})
    return result, read


def cell(read, sheet, text):
    return next(item for item in read["sheets"][sheet]["cells"] if item["text"] == text)


def test_excel_opens_every_sheet_without_repair(excel):
    result, read = excel
    assert read["count"] == 3
    assert [sheet["name"] for sheet in read["sheets"]] == [info.name for info in result.sheets]


def test_numbers_show_the_pdf_text(excel):
    _, read = excel
    for text, value in (("−2.000", -2.0), ("12.150", 12.15), ("7.381", 7.381)):
        item = cell(read, 0, text)
        assert item["value"] == value, item


def test_text_fonts_merges_and_scripts(excel):
    _, read = excel
    heading = cell(read, 0, "1. 断面の諸元")
    assert heading["font"] == "IPAex明朝" and heading["size"] == 10
    lhs = cell(read, 0, "I")
    assert ":" in lhs["merge"] and lhs["h"] == -4152  # xlRight
    numerator = next(item for item in read["sheets"][0]["cells"] if item["text"].startswith("4.50"))
    assert numerator["runs"][-1]["sup"] is True and not numerator["runs"][0]["sup"]
    turned = cell(read, 0, "回転")
    assert turned["orientation"] == -4171  # xlUpward: reads bottom to top


def test_borders_and_shapes(excel):
    _, read = excel
    weights = {edge["weight"] for edge in read["sheets"][0]["edges"]}
    assert weights == {2, -4138}  # xlThin (the table) and xlMedium (the rule)
    first = read["sheets"][0]["shapes"]
    assert [shape["type"] for shape in first] == [9]  # the fraction bar (msoLine)
    third = read["sheets"][2]["shapes"]
    assert sorted(shape["type"] for shape in third) == [6, 13]  # the figure group and the picture


def test_page_setup_header_and_footer(excel):
    _, read = excel
    first, second = read["sheets"][0], read["sheets"][1]
    assert first["zoom"] == 100 and second["first"] == 2
    assert first["paper"] == 9 and second["paper"] == 8 and second["orientation"] == 2  # A4, A3, landscape
    assert "&P/3" in first["header"][2] and "&P" in first["footer"][1]


# --- printed grid positions (FR-021, Step 8 lead decision A) ------------------------------------------

def _grid_page(grid):
    from gridlayoutpdf.scene import Line as SceneLine, ScenePage
    from gridlayoutpdf.semantics import Role, Tag

    def border(x1, y1, x2, y2):
        return SceneLine(x1, y1, x2, y2, 0.25, tag=Tag(Role.TABLE_BORDER, (), {"style": "hair", "stroke": 0}))

    left, top = grid.x(0), grid.y(0)
    right, bottom = grid.x(grid.columns), grid.y(grid.rows)
    lines = [border(grid.x(col), top, grid.x(col), bottom) for col in range(grid.columns + 1)]
    lines += [border(left, grid.y(row), right, grid.y(row)) for row in range(grid.rows + 1)]
    return ScenePage(PageProfile("grid", 595, 842, grid), lines, {})


def _merged(values):
    groups = []
    for value in sorted(values):
        if groups and value - groups[-1][-1] < 1.5:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(group) / len(group) for group in groups]


@pytest.mark.parametrize("grid", [A4_PORTRAIT_REFERENCE.grid, GridSpec(50.88, 54.598, 10.8, 14.52, 46, 51)],
                         ids=["a4-reference", "cantilever-turned"])
def test_every_grid_boundary_prints_within_half_a_cell_of_the_pdf(tmp_path, grid, record_property):
    """Whole-pixel cells distributed over the grid print each boundary near its PDF position (active printer)."""
    pymupdf = pytest.importorskip("pymupdf")
    from gridlayoutpdf import render_xlsx

    path, pdf = tmp_path / "grid.xlsx", tmp_path / "grid.pdf"
    result = render_xlsx([("S", (_grid_page(grid),))], path, strict=True, cell_padding_pt=padding)
    assert result.sheets[0].scale == 100
    printer = _core._run_excel(tmp_path, _core._EXPORT_PDF, {"books": [{"path": str(path), "pdf": str(pdf)}]})["printer"]
    record_property("printer", printer)
    with pymupdf.open(pdf) as document:
        assert len(document) == 1
        xs, ys = [], []
        for drawing in document[0].get_drawings():
            box = drawing["rect"]
            if box.height > 2 * box.width:
                xs.append(box.x0 + box.width / 2)
            elif box.width > 2 * box.height:
                ys.append(box.y0 + box.height / 2)
    xs, ys = _merged(xs), _merged(ys)
    assert len(xs) == grid.columns + 1 and len(ys) == grid.rows + 1
    dx = [x - grid.x(col) for col, x in enumerate(xs)]
    dy = [y - grid.y(row) for row, y in enumerate(ys)]
    record_property("max_dx_pt", max(map(abs, dx)))
    record_property("max_dy_pt", max(map(abs, dy)))
    print(f"{printer}: last column {dx[-1]:+.2f} pt (max {max(map(abs, dx)):.2f}), "
          f"last row {dy[-1]:+.2f} pt (max {max(map(abs, dy)):.2f})")
    # within half a cell (Step 10), and, from the first boundary (the printer's origin moves all of them by
    # 0.1-0.8 pt), within 1 pt: an error building up over the page would show
    assert max(map(abs, dx)) <= grid.pitch_x / 2 and max(map(abs, dy)) <= grid.pitch_y / 2
    assert max(abs(value - dx[0]) for value in dx) <= 1.0 and max(abs(value - dy[0]) for value in dy) <= 1.0


def test_a_table_split_at_a_page_break_prints_its_top_border_on_the_next_page(tmp_path):
    """The page above keeps its last row's bottom border and the page below its first row's top border."""
    pymupdf = pytest.importorskip("pymupdf")
    document = Document(Paragraph("x"), Table([2], [[Cell(f"r{index}")] for index in range(60)]))
    path, pdf = tmp_path / "split.xlsx", tmp_path / "split.pdf"
    document.render_xlsx(path, "S", strict=True, cell_padding_pt=padding)
    _core._run_excel(tmp_path, _core._EXPORT_PDF, {"books": [{"path": str(path), "pdf": str(pdf)}]})
    top, bottom = A4_PORTRAIT_REFERENCE.grid.y(0), A4_PORTRAIT_REFERENCE.grid.y(47)
    with pymupdf.open(pdf) as printed:
        assert len(printed) >= 2

        def horizontal(page):
            return [drawing["rect"].y0 for drawing in printed[page].get_drawings()
                    if drawing["rect"].width > 2 * drawing["rect"].height]

        assert any(abs(y - bottom) < 2 for y in horizontal(0)), "page 1 lost its bottom border"
        assert any(abs(y - top) < 2 for y in horizontal(1)), "page 2 lost its top border"


def test_number_cells_never_show_hashes(tmp_path):
    """Numbers in the tightest table cells: Excel shows each number cell's text, never ###."""
    import math

    from gridlayoutpdf import TextStyle
    from gridlayoutpdf.errors import FontError
    from gridlayoutpdf.fonts import default_fonts

    fonts = default_fonts()
    numbers = ("−888888888", "88888888.88", "1234.567", "12.150", "−2.000", "7.381125", "1,234,567.8")
    blocks = []
    for name, size in (("MS Mincho", 8), ("MS Mincho", 10), ("MS Mincho", 10.5), ("IPAex明朝", 10)):
        style = TextStyle(font=name, size=size)
        try:
            widths = [fonts.measure(text, style).width for text in numbers]
        except FontError as exc:
            pytest.skip(f"{name} is not available: {exc}")
        for text, width in zip(numbers, widths):
            columns = math.ceil((width + 6.5) / A4_PORTRAIT_REFERENCE.grid.pitch_x)  # 3 pt cell padding a side
            blocks.append(Table([columns], [[Cell(text, style=style, align="right")]]))
            blocks.append(Table([columns + 1], [[Cell(text, style=style, align="center")]]))  # grows both ways
    document = Document(*blocks)
    path = tmp_path / "numbers.xlsx"
    result = document.render_xlsx(path, "N", cell_padding_pt=padding)
    read = _core._run_excel(tmp_path, _READ, {"path": str(path)})
    shown = [item for sheet in read["sheets"] for item in sheet["cells"] if isinstance(item["value"], (int, float))]
    assert shown, "no number cells were written"
    # Excel shows ### for a number too wide for its cells, and nothing when not even one # fits (11 px)
    assert [item for item in shown if "#" in item["text"] or not item["text"].strip()] == []
    assert len(shown) + len(result.numbers_as_text) == len(blocks)


# --- printing at 100 % with the measured printed cell sizes (the A3 footer fix) -------------------------

_EXPORT_SHEETS = r"""
  foreach ($item in $params.books) {
    $book = $xl.Workbooks.Open($item.path, 0, $true)
    $index = 0
    foreach ($ws in $book.Worksheets) { $index++; $ws.ExportAsFixedFormat(0, "$($item.pdf)-$index.pdf") }
    $book.Close($false)
  }
  [ordered]@{ printer = $xl.ActivePrinter }
"""


def _measured_printer(printer):
    """As in test_xlsx_excel_core.py: an unmeasured printer is an xfail (a failure when Excel is required).

    The printed sizes and the room at 100 % were measured only with "DocuWorks Printer" ("DocuWorks PDF":
    only the 21 px column pitch).
    """
    if not printer.startswith("DocuWorks Printer on "):
        message = f"printing at 100 % was measured only with DocuWorks Printer, not {printer}"
        if _core._REQUIRED:
            pytest.fail(message)
        pytest.xfail(message)


def _full_scale_cases():
    from gridlayoutpdf.renderers.xlsx._model import CellValue, Font, Margins, PageSetup, Sheet
    from gridlayoutpdf.renderers.xlsx._units import full_scale_size_pt, print_fit

    cases = {}
    for font in (Font("游ゴシック", 11), Font("ＭＳ 明朝", 10.5)):
        for pixels in (12, 21, 30):  # 12 px has the largest measured column factor
            for kind in ("columns", "rows"):
                for count in (2, 20):
                    size = pixels * 0.75
                    widths, heights = ((size,) * count, (15.75,) * 3) if kind == "columns" else ((15.75,) * 3, (size,) * count)
                    mark = CellValue(0, count - 1, "X") if kind == "columns" else CellValue(count - 1, 0, "X")
                    probe = Sheet("S", widths, heights, cells=(mark,))
                    need_width, need_height = full_scale_size_pt(probe, font)
                    paper_width, paper_height = probe.page.paper_size_pt
                    # the measured size and 0.005 pt to spare; the other extent has plenty of room
                    right = paper_width - 36 - need_width - 0.005 if kind == "columns" else 36
                    bottom = paper_height - 36 - need_height - 0.005 if kind == "rows" else 36
                    sheet = Sheet("S", widths, heights, cells=(mark,),
                                  page=PageSetup(margins=Margins(36, 36, right, bottom, 18, 18)))
                    assert print_fit(sheet, font).scale == 100
                    cases[f"{font.name}-{pixels}px-{count}-{kind}"] = (sheet, font)
    return cases


def test_pages_cut_at_the_measured_full_scale_size_print_on_one_paper(tmp_path, record_property):
    """At 100 % a print area just as wide (or tall) as full_scale_size_pt keeps its cells on one paper."""
    pymupdf = pytest.importorskip("pymupdf")
    from gridlayoutpdf.renderers.xlsx._model import Workbook
    from gridlayoutpdf.renderers.xlsx._package import save_workbook

    books = []
    for name, (sheet, font) in _full_scale_cases().items():
        path = tmp_path / f"{name}.xlsx"
        save_workbook(Workbook((sheet,), default_font=font), path)
        books.append({"path": str(path), "pdf": str(tmp_path / name)})
    printer = _core._run_excel(tmp_path, _EXPORT_SHEETS, {"books": books}, timeout=600)["printer"]
    record_property("printer", printer)
    _measured_printer(printer)
    split = []
    for book in books:
        with pymupdf.open(f"{book['pdf']}-1.pdf") as printed:
            if len(printed) != 1 or "X" not in printed[0].get_text():
                split.append(Path(book["path"]).stem)
    assert split == [], f"split with {printer}"


def _lines(page):
    """(text, bbox) of each printed line of a pymupdf page."""
    found = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                found.append((text, line["bbox"]))
    return found


@pytest.mark.parametrize("align", ["left", "center", "right"])
def test_headers_and_footers_print_within_a_cell_of_the_pdf(tmp_path, align, record_property):
    """A4 and A3 pages at 100 %, no extra pages, every header and footer section within a cell of the PDF."""
    pymupdf = pytest.importorskip("pymupdf")
    document = Document(
        Paragraph("縦の頁"), PageSection(A3_LANDSCAPE_REFERENCE, Paragraph("横の頁")),
        profile=A4_PORTRAIT_REFERENCE,
        header=PageDecoration("見出し{page}", align=align), footer=PageDecoration("{page}/{pages}", align=align))
    library, path = tmp_path / "library.pdf", tmp_path / "report.xlsx"
    document.render(library)
    result = document.render_xlsx(path, "S", strict=True, cell_padding_pt=padding)
    assert [sheet.scale for sheet in result.sheets] == [100, 100]
    printer = _core._run_excel(tmp_path, _EXPORT_SHEETS, {"books": [{"path": str(path), "pdf": str(tmp_path / "x")}]})[
        "printer"]
    record_property("printer", printer)
    _measured_printer(printer)
    anchor = {"left": lambda box: box[0], "center": lambda box: (box[0] + box[2]) / 2, "right": lambda box: box[2]}[align]
    pitch = A4_PORTRAIT_REFERENCE.grid.pitch_x
    with pymupdf.open(library) as expected:
        for number, page in enumerate(expected, start=1):
            with pymupdf.open(tmp_path / f"x-{number}.pdf") as printed:
                assert len(printed) == 1, f"sheet {number} printed {len(printed)} pages with {printer}"
                lines = dict(_lines(printed[0]))
                for text in (f"見出し{number}", f"{number}/2"):
                    want = dict(_lines(page))[text]
                    got = lines[text]
                    record_property(f"{text} dx", round(anchor(got) - anchor(want), 2))
                    assert abs(anchor(got) - anchor(want)) <= pitch, (text, want, got, printer)
