"""A PdfFigure in a grid Excel sheet: its preview as a picture, or a recorded frame."""

from io import BytesIO
import zipfile

from PIL import Image as PILImage
from reportlab.pdfgen.canvas import Canvas
import pytest

from gridlayoutpdf import Document, PdfFigure, VectorPage
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.renderers.xlsx import XlsxStrictError, render_xlsx
from gridlayoutpdf.renderers.xlsx import _model as xl
from gridlayoutpdf.renderers.xlsx._map import FALLBACK_KINDS, map_reports
from gridlayoutpdf.scene import ScenePage
from gridlayoutpdf.semantics import Role, Tag
from gridlayoutpdf.styles import ReportStyle, TextStyle


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * 0.6, style.size * 0.8, style.size * 0.2)


FONTS = FixedFonts()
A4 = A4_PORTRAIT_REFERENCE
OX, OY, PX, PY = 50.88, 54.598, 16.08, 15.48
CELL = 15.75  # the A4 grid's cells are 21 Excel pixels


def padding(size):
    return 2.4


def source_pdf(width=200, height=100):
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=1, pageCompression=1)
    canvas.setPageSize((width, height))
    canvas.line(10, 10, width - 10, height - 10)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def png(size):
    output = BytesIO()
    PILImage.new("RGB", size, (255, 255, 255)).save(output, format="PNG")
    return output.getvalue()


def mapped(*blocks, strict=False):
    pages = Document(*blocks, fonts=FONTS, style=ReportStyle(body=TextStyle(size=10)), profile=A4).layout()
    return map_reports([("図", pages)], FONTS, strict=strict, cell_padding_pt=padding)


def test_the_preview_is_a_picture_over_the_fitted_box():
    preview = png((400, 200))
    workbook, result = mapped(PdfFigure(4, 2, source_pdf(), preview=preview))
    (picture,) = workbook.sheets[0].drawings
    assert isinstance(picture, xl.Picture) and picture.format == "png" and picture.data == preview
    # a 4 x 2 cell frame (64.32 x 30.96 pt) holds a 61.92 x 30.96 pt box: Excel's cells keep the fractions
    assert (picture.x, picture.y) == pytest.approx(((64.32 - 61.92) / 2 / PX * CELL, 0))
    assert (picture.width, picture.height) == pytest.approx((61.92 / PX * CELL, 2 * CELL))
    assert result.fallbacks == ()


def test_without_a_preview_the_box_is_a_frame_and_recorded():
    workbook, result = mapped(PdfFigure(4, 2, source_pdf(), block_id="drawing"))
    (frame,) = workbook.sheets[0].drawings
    assert isinstance(frame, xl.Rect) and frame.fill is None and frame.stroke
    assert (frame.width, frame.height) == pytest.approx((61.92 / PX * CELL, 2 * CELL))
    (record,) = result.fallbacks
    assert (record.sheet, record.page, record.kind) == ("図", 1, "pdf_figure_frame")
    assert "drawing" in record.detail
    assert "pdf_figure_frame" in FALLBACK_KINDS


def test_strict_refuses_a_figure_without_a_preview(tmp_path):
    with pytest.raises(XlsxStrictError, match="pdf_figure_frame") as caught:
        mapped(PdfFigure(4, 2, source_pdf()), strict=True)
    assert [record.kind for record in caught.value.fallbacks] == ["pdf_figure_frame"]
    workbook, result = mapped(PdfFigure(4, 2, source_pdf(), preview=png((40, 20))), strict=True)
    assert result.fallbacks == ()


def test_a_workbook_with_a_preview_is_written_with_the_picture(tmp_path):
    preview = png((400, 200))
    pages = Document(PdfFigure(4, 2, source_pdf(), preview=preview), fonts=FONTS, profile=A4).layout()
    path = tmp_path / "out.xlsx"
    render_xlsx([("図", pages)], path, FONTS, strict=True, cell_padding_pt=padding)
    with zipfile.ZipFile(path) as package:
        assert package.read("xl/media/image1.png") == preview
    first = path.read_bytes()
    render_xlsx([("図", pages)], path, FONTS, strict=True, cell_padding_pt=padding)
    assert path.read_bytes() == first


def test_an_untagged_vector_page_is_mapped_like_a_user_command():
    page = ScenePage(A4, (VectorPage(OX, OY, 2 * PX, PY, source_pdf()),))
    workbook, result = map_reports([("R", (page,))], FONTS, cell_padding_pt=padding)
    (frame,) = workbook.sheets[0].drawings
    assert isinstance(frame, xl.Rect)
    assert dict(result.untagged) == {"VectorPage": 1}
    assert [record.kind for record in result.fallbacks] == ["pdf_figure_frame"]
    tagged = ScenePage(A4, (VectorPage(OX, OY, 2 * PX, PY, source_pdf(), preview=png((20, 10)),
                                       tag=Tag(Role.IMAGE)),))
    workbook, result = map_reports([("R", (tagged,))], FONTS, cell_padding_pt=padding)
    (picture,) = workbook.sheets[0].drawings
    assert isinstance(picture, xl.Picture) and result.fallbacks == ()
