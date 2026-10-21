"""A PdfFigure is drawn as vector artwork: the source page becomes one form XObject."""

from io import BytesIO
import zlib

from PIL import Image as PILImage
import pymupdf
from pypdf import PdfReader
from pypdf.generic import NullObject
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
import pytest

from gridlayoutpdf import Document, Paragraph, PdfFigure, VectorPage
from gridlayoutpdf.errors import LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.geometry import GridSpec
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.profiles import PageProfile
from gridlayoutpdf.renderers.reportlab import render_pdf
from gridlayoutpdf.scene import ScenePage
from gridlayoutpdf.styles import ReportStyle


PROFILE = PageProfile("pdf", 400, 400, GridSpec(0, 0, 10, 10, 40, 40))


@pytest.fixture
def context():
    return LayoutContext(FontRegistry(), PROFILE, ReportStyle())


def source_pdf(width=200, height=100, *, text=None, image=False, pages=1):
    """One line from (10, 10) to (w-10, h-10) and one circle of radius 20 at the centre, PDF coordinates."""
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=1, pageCompression=1)
    for _ in range(pages):
        canvas.setPageSize((width, height))
        canvas.setLineWidth(2)
        canvas.line(10, 10, width - 10, height - 10)
        canvas.circle(width / 2, height / 2, 20)
        if text:
            canvas.setFont("Helvetica", 12)
            canvas.drawString(10, height - 30, text)
        if image:
            raster = BytesIO()
            PILImage.new("RGBA", (8, 4), (255, 0, 0, 128)).save(raster, format="PNG")
            canvas.drawImage(ImageReader(raster), 150, 10, 40, 20, mask="auto")
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def placed(context, block, dx=40, dy=60):
    measured = measure_block(block, context, 400)
    return ScenePage(PROFILE, tuple(command.translated(dx, dy) for command in measured.commands))


def test_the_page_is_vector_artwork_at_its_fitted_place(context, tmp_path):
    # 200 x 100 pt in a 200 x 50 pt frame: scale 1/2, centred at x 50, placed at (40, 60) on the page
    page = placed(context, PdfFigure(20, 5, source_pdf(), block_id="drawing"))
    render_pdf([page], tmp_path / "out.pdf", context.fonts, invariant=True)
    with pymupdf.open(tmp_path / "out.pdf") as document:
        output = document[0]
        assert output.get_images(full=True) == []
        drawings = output.get_drawings()
    lines = [item for drawing in drawings for item in drawing["items"] if item[0] == "l"]
    (line,) = lines
    # the source line runs from PDF (10, 10) to (190, 90): top-down (10, 90) to (190, 10), halved and moved
    assert (line[1].x, line[1].y, line[2].x, line[2].y) == pytest.approx((95, 105, 185, 65), abs=1e-3)
    circle = next(drawing for drawing in drawings if any(item[0] == "c" for item in drawing["items"]))
    rect = circle["rect"]
    # the circle is centred at (140, 85) with radius 10; its stroke is 2 pt scaled to 1 pt
    assert (rect.x0, rect.y0, rect.x1, rect.y1) == pytest.approx((130, 75, 150, 95), abs=1e-2)
    assert circle["width"] == pytest.approx(1)


def test_the_page_is_one_form_xobject_shared_by_every_use(context, tmp_path):
    data = source_pdf()
    first = measure_block(PdfFigure(20, 5, data), context, 400).commands[0]
    commands = (first.translated(0, 0), first.translated(0, 100), first.translated(0, 200))
    pages = [ScenePage(PROFILE, commands), ScenePage(PROFILE, commands[:1])]
    render_pdf(pages, tmp_path / "out.pdf", context.fonts, invariant=True)
    reader = PdfReader(tmp_path / "out.pdf")
    forms = []
    for output in reader.pages:
        xobjects = output["/Resources"]["/XObject"]
        assert len(xobjects) == 1
        forms.extend(xobjects[name].indirect_reference for name in xobjects)
        form = next(iter(xobjects.values())).get_object()
        assert form["/Subtype"] == "/Form" and list(form["/BBox"]) == [0, 0, 200, 100]
    assert len(set((ref.idnum, ref.generation) for ref in forms)) == 1
    assert reader.pages[0].extract_text() == "" and b"Do" in reader.pages[0].get_contents().get_data()
    assert reader.pages[0].get_contents().get_data().count(b" Do") == 3


def test_fonts_and_images_of_the_source_page_are_carried_over(context, tmp_path):
    page = placed(context, PdfFigure(40, 20, source_pdf(text="Hello PDF", image=True)), dx=0)
    render_pdf([page], tmp_path / "out.pdf", context.fonts, invariant=True)
    with pymupdf.open(tmp_path / "out.pdf") as document:
        output = document[0]
        assert "Hello PDF" in output.get_text()
        (image,) = output.get_images(full=True)
        assert (image[2], image[3]) == (8, 4) and image[1] != 0  # width, height and a soft mask
        pixmap = output.get_pixmap(dpi=72)
    # the image lands at PDF (150, 10, 190, 30) x2 = top-down (300, 140)-(380, 180), moved down by 60
    red = pixmap.pixel(340, 220)
    assert red[0] > 200 and red[1] < 200


def test_the_bytes_are_the_same_every_time(context, tmp_path):
    def render(path):
        document = Document(Paragraph("図"), PdfFigure(20, 5, source_pdf(text="A"), block_id="drawing"),
                            fonts=context.fonts)
        document.render(path, invariant=True)
        return path.read_bytes()

    first, second = render(tmp_path / "a.pdf"), render(tmp_path / "b.pdf")
    assert first == second


def test_a_later_page_and_a_cropped_page_are_drawn_by_their_own_box(context, tmp_path):
    from pypdf import PdfWriter

    writer = PdfWriter(clone_from=PdfReader(BytesIO(source_pdf(pages=2))))
    writer.pages[1].cropbox.lower_left = (100, 50)
    writer.pages[1].cropbox.upper_right = (200, 100)
    buffer = BytesIO()
    writer.write(buffer)
    page = placed(context, PdfFigure(10, 5, buffer.getvalue(), page=1), dx=0, dy=0)
    (command,) = page.commands
    assert (command.x, command.y, command.width, command.height) == (0, 0, 100, 50)
    render_pdf([page], tmp_path / "out.pdf", context.fonts, invariant=True)
    reader = PdfReader(tmp_path / "out.pdf")
    form = next(iter(reader.pages[0]["/Resources"]["/XObject"].values())).get_object()
    assert list(form["/BBox"]) == [100, 50, 200, 100]
    with pymupdf.open(tmp_path / "out.pdf") as document:
        drawings = document[0].get_drawings()
    (line,) = [item for drawing in drawings for item in drawing["items"] if item[0] == "l"]
    # only the part of the line inside the crop box shows; its ends keep their full-page positions
    assert (line[1].x, line[1].y, line[2].x, line[2].y) == pytest.approx((-90, 90, 90, 10), abs=1e-3)


def test_content_split_over_several_streams_is_joined(context, tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, NameObject

    writer = PdfWriter(clone_from=PdfReader(BytesIO(source_pdf())))
    first, second = DecodedStreamObject(), DecodedStreamObject()
    first.set_data(b"q 1 0 0 RG 4 w 0 0 m")
    second.set_data(b"200 100 l S Q")
    writer.pages[0][NameObject("/Contents")] = ArrayObject(
        [writer._add_object(first), writer._add_object(second)])
    buffer = BytesIO()
    writer.write(buffer)
    page = placed(context, PdfFigure(20, 10, buffer.getvalue()), dx=0, dy=0)
    render_pdf([page], tmp_path / "out.pdf", context.fonts, invariant=True)
    form = next(iter(PdfReader(tmp_path / "out.pdf").pages[0]["/Resources"]["/XObject"].values())).get_object()
    assert form.get_data() == b"q 1 0 0 RG 4 w 0 0 m\n200 100 l S Q"


def test_bad_pdf_bytes_are_refused_before_writing(context, tmp_path):
    destination = tmp_path / "out.pdf"
    destination.write_bytes(b"old")
    page = ScenePage(PROFILE, (VectorPage(0, 0, 100, 50, b"not a pdf"),))
    with pytest.raises(ValueError, match=r"page\[1\]\.commands\[0\]: .*not a readable PDF"):
        render_pdf([page], destination, invariant=True)
    page = ScenePage(PROFILE, (VectorPage(0, 0, 100, 50, source_pdf(), page=2),))
    with pytest.raises(ValueError, match="has no page 2"):
        render_pdf([page], destination, invariant=True)
    assert destination.read_bytes() == b"old"
    assert [path.name for path in tmp_path.iterdir()] == ["out.pdf"]


def test_a_vector_page_outside_the_paper_is_an_overflow(tmp_path):
    page = ScenePage(PROFILE, (VectorPage(350, 0, 100, 50, source_pdf()),))
    with pytest.raises(LayoutOverflowError):
        render_pdf([page], tmp_path / "out.pdf", invariant=True)


def test_a_direct_vector_page_is_stretched_over_its_box(context, tmp_path):
    page = ScenePage(PROFILE, (VectorPage(0, 0, 100, 100, source_pdf()),))
    render_pdf([page], tmp_path / "out.pdf", context.fonts, invariant=True)
    content = PdfReader(tmp_path / "out.pdf").pages[0].get_contents().get_data()
    # x by 100/200, y by 100/100; the box's bottom edge is at PDF y 300
    assert b"cm" in content and b".5 0 0 1 0 300 cm" in content


def test_the_form_stream_is_flate_compressed(context, tmp_path):
    page = placed(context, PdfFigure(20, 5, source_pdf()))
    render_pdf([page], tmp_path / "out.pdf", context.fonts, invariant=True)
    form = next(iter(PdfReader(tmp_path / "out.pdf").pages[0]["/Resources"]["/XObject"].values())).get_object()
    assert form["/Filter"] == "/FlateDecode"
    assert zlib.decompress(form._data) == form.get_data()


def test_a_pymupdf_page_with_compressed_object_streams_is_drawn(context, tmp_path):
    # PyMuPDF writes the drawings of ezdxf's PDF backend; object streams hide the objects in compressed streams.
    source = pymupdf.open()
    sheet = source.new_page(width=300, height=150)
    sheet.draw_line((10, 10), (290, 140), width=1)
    sheet.draw_circle((150, 75), 30, width=1)
    sheet.insert_text((20, 130), "D25 ctc 150", fontsize=12)
    data = source.tobytes(garbage=4, deflate=True, use_objstms=1)
    source.close()
    page = placed(context, PdfFigure(30, 15, data), dx=0, dy=0)
    render_pdf([page], tmp_path / "a.pdf", context.fonts, invariant=True)
    render_pdf([page], tmp_path / "b.pdf", context.fonts, invariant=True)
    assert (tmp_path / "a.pdf").read_bytes() == (tmp_path / "b.pdf").read_bytes()
    with pymupdf.open(tmp_path / "a.pdf") as document:
        output = document[0]
        assert output.get_images() == [] and "D25 ctc 150" in output.get_text()
        (line,) = [item for drawing in output.get_drawings() for item in drawing["items"] if item[0] == "l"]
    assert (line[1].x, line[1].y, line[2].x, line[2].y) == pytest.approx((10, 10, 290, 140), abs=1e-3)


def handmade(objects):
    """A PDF of the given numbered object bodies with a correct cross-reference table."""
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = {}
    for number, body in objects.items():
        offsets[number] = output.tell()
        output.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref, size = output.tell(), max(objects) + 1
    output.write(b"xref\n0 %d\n0000000000 65535 f \n" % size)
    for number in range(1, size):
        output.write(b"%010d 00000 n \n" % offsets[number] if number in offsets else b"0000000000 65535 f \n")
    output.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref))
    return output.getvalue()


def test_shared_cyclic_and_missing_objects_and_the_group_are_copied(context, tmp_path):
    data = handmade({
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 50] /Resources 4 0 R "
           b"/Group << /S /Transparency /CS /DeviceRGB >> >>",
        4: b"<< /Me 4 0 R /A 5 0 R /B 5 0 R /N 6 0 R /M 9 0 R /S (text) >>",
        5: b"[1 2.5 5 0 R]",
        6: b"42",
    })
    page = ScenePage(PROFILE, (VectorPage(0, 0, 100, 50, data),))
    render_pdf([page], tmp_path / "out.pdf", context.fonts, invariant=True)
    form = next(iter(PdfReader(tmp_path / "out.pdf").pages[0]["/Resources"]["/XObject"].values())).get_object()
    assert form.get_data() == b""
    assert form["/Group"] == {"/S": "/Transparency", "/CS": "/DeviceRGB"}
    resources = form["/Resources"]
    assert resources["/Me"]["/N"] == 42 and resources["/S"] == "text"
    assert resources.raw_get("/A") == resources.raw_get("/B")  # one shared object
    array = resources["/A"]
    assert (array[0], array[1]) == (1, 2.5) and array[2] == resources.raw_get("/A")  # refers to itself
    assert isinstance(resources["/M"], NullObject)  # the missing object 9
