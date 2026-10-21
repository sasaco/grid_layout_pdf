"""PdfFigure: one page of a vector PDF fitted into a grid frame (VectorPage command)."""

from dataclasses import FrozenInstanceError
from io import BytesIO

from PIL import Image as PILImage
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
import pytest

from gridlayoutpdf import PdfFigure, VectorPage
from gridlayoutpdf.bounds import command_bounds
from gridlayoutpdf.diagnostics import layout_trace
from gridlayoutpdf.errors import LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.geometry import GridSpec, Rect
from gridlayoutpdf.layout import LayoutContext, LayoutPart, MeasuredBlock, measure_block
from gridlayoutpdf.pdfpages import pdf_page_box
from gridlayoutpdf.profiles import PageProfile
from gridlayoutpdf.rotation import QuarterTurn
from gridlayoutpdf.scene import ScenePage
from gridlayoutpdf.semantics import Role
from gridlayoutpdf.styles import ReportStyle


@pytest.fixture
def context():
    return LayoutContext(FontRegistry(), PageProfile("pdf", 400, 400,
                         GridSpec(0, 0, 10, 10, 40, 40)), ReportStyle())


def source_pdf(*sizes):
    """A vector PDF: one line and one circle on each page of the given pt sizes."""
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=1, pageCompression=1)
    for width, height in sizes or ((200, 100),):
        canvas.setPageSize((width, height))
        canvas.line(10, 10, width - 10, height - 10)
        canvas.circle(width / 2, height / 2, 20)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def rewritten(data, change):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(data)))
    change(writer)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def png(size):
    output = BytesIO()
    PILImage.new("RGB", size, (255, 255, 255)).save(output, format="PNG")
    return output.getvalue()


# --- the page box -----------------------------------------------------------------------------

def test_the_page_box_is_the_crop_box_of_the_chosen_page():
    data = source_pdf((200, 100), (50, 80))
    assert pdf_page_box(data, 0) == (0, 0, 200, 100)
    assert pdf_page_box(data, 1) == (0, 0, 50, 80)

    def crop(writer):
        writer.pages[0].cropbox.lower_left = (20, 10)
        writer.pages[0].cropbox.upper_right = (120, 60)
    assert pdf_page_box(rewritten(data, crop), 0) == (20, 10, 100, 50)


@pytest.mark.parametrize("data, page, message", [
    (b"not a pdf at all", 0, "not a readable PDF"),
    (b"%PDF-1.4\n%%EOF", 0, "not a readable PDF"),
    (source_pdf(), 1, "has no page 1"),
])
def test_unreadable_data_and_missing_pages_are_value_errors(data, page, message):
    with pytest.raises(ValueError, match=message):
        pdf_page_box(data, page)


def test_a_pdf_without_pages_is_a_value_error():
    output = BytesIO()
    PdfWriter().write(output)
    with pytest.raises(ValueError, match="has no page 0"):
        pdf_page_box(output.getvalue(), 0)


def test_rotated_and_encrypted_pages_are_value_errors():
    rotated = rewritten(source_pdf(), lambda writer: writer.pages[0].rotate(90))
    with pytest.raises(ValueError, match="rotated"):
        pdf_page_box(rotated, 0)
    encrypted = rewritten(source_pdf(), lambda writer: writer.encrypt("secret", algorithm="RC4-128"))
    with pytest.raises(ValueError, match="encrypted"):
        pdf_page_box(encrypted, 0)


def test_a_page_of_no_area_is_a_value_error():
    def flatten(writer):
        writer.pages[0].mediabox.upper_right = (200, 0)
    with pytest.raises(ValueError, match="no area"):
        pdf_page_box(rewritten(source_pdf(), flatten), 0)


# --- the VectorPage command ------------------------------------------------------------------------

def test_vector_page_is_an_immutable_snapshot_with_box_bounds(context):
    data = bytearray(source_pdf())
    preview = png((20, 10))
    command = VectorPage(1, 2, 30, 15, data, preview=preview)
    snapshot = bytes(data)
    data[0] = 0
    assert command.data == snapshot and isinstance(command.data, bytes)
    assert command.page == 0 and command.preview == preview
    assert command_bounds(command, context.fonts) == Rect(1, 2, 30, 15)
    assert command.translated(4, 5) == VectorPage(5, 7, 30, 15, snapshot, preview=preview)
    assert ScenePage(context.profile, (command,)).commands == (command,)
    assert MeasuredBlock(40, 10, (LayoutPart(2, (command,)),)).commands == (command,)
    with pytest.raises(FrozenInstanceError):
        command.width = 2


@pytest.mark.parametrize("field, invalid", [
    ("x", True), ("y", float("nan")), ("width", 0), ("height", -1), ("data", "not bytes"),
    ("data", b""), ("page", -1), ("page", 1.0), ("page", True), ("preview", b""), ("preview", "x.png"),
])
def test_vector_page_validates_its_fields(field, invalid):
    values = {"x": 0, "y": 0, "width": 30, "height": 15, "data": source_pdf(), field: invalid}
    with pytest.raises(ValueError):
        VectorPage(**values)


def test_the_layout_trace_lists_digests_not_bytes(context):
    data = source_pdf()
    command = VectorPage(1, 2, 30, 15, data, page=0, preview=png((20, 10)))
    trace = layout_trace([ScenePage(context.profile, (command,))], context.fonts)
    entry = trace["pages"][0]["commands"][0]
    assert entry["type"] == "VectorPage"
    assert (entry["x"], entry["y"], entry["width"], entry["height"], entry["page"]) == (1, 2, 30, 15, 0)
    assert entry["byte_count"] == len(data) and len(entry["sha256"]) == 64
    assert len(entry["preview_sha256"]) == 64


# --- the PdfFigure block -------------------------------------------------------------------------

@pytest.mark.parametrize("col_span, rows, align, valign, expected", [
    (20, 5, "center", "middle", (50, 0, 100, 50)),     # height decides: 200 x 100 at 1/2
    (10, 10, "center", "middle", (0, 25, 100, 50)),    # width decides
    (20, 5, "left", "top", (0, 0, 100, 50)),
    (20, 5, "right", "bottom", (100, 0, 100, 50)),
    (10, 10, "left", "top", (0, 0, 100, 50)),
    (10, 10, "right", "bottom", (0, 50, 100, 50)),
    (40, 20, "center", "middle", (0, 0, 400, 200)),    # enlarged to fill the frame
])
def test_the_page_is_fitted_in_its_frame_keeping_its_aspect(context, col_span, rows, align, valign, expected):
    data = source_pdf((200, 100))
    block = PdfFigure(col_span, rows, data, align=align, valign=valign, block_id="drawing")
    measured = measure_block(block, context, 400)
    (command,) = measured.commands
    assert isinstance(command, VectorPage)
    assert (command.x, command.y, command.width, command.height) == pytest.approx(expected)
    assert command.data == data and command.page == 0 and command.preview is None
    assert command.tag.role is Role.IMAGE and command.tag.data == {"block_id": "drawing"}
    assert measured.width == col_span * 10 and measured.rows == rows
    assert measured.keep_together and measured.block_id == "drawing"


def test_a_cropped_page_and_a_later_page_are_fitted_by_their_own_box(context):
    data = source_pdf((200, 100), (50, 100))
    (command,) = measure_block(PdfFigure(10, 10, data, page=1), context, 400).commands
    assert (command.x, command.y, command.width, command.height) == pytest.approx((25, 0, 50, 100))
    assert command.page == 1


def test_the_preview_travels_with_the_command(context):
    preview = png((400, 200))
    (command,) = measure_block(PdfFigure(20, 5, source_pdf(), preview=preview), context, 400).commands
    assert command.preview == preview


@pytest.mark.parametrize("size", [(400, 199), (402, 200), (300, 200)])
def test_a_preview_of_another_aspect_is_refused(size):
    with pytest.raises(ValueError, match="preview"):
        PdfFigure(20, 5, source_pdf(), preview=png(size))


def test_a_preview_within_half_a_pixel_is_accepted():
    PdfFigure(20, 5, source_pdf((200, 100)), preview=png((201, 100)))
    PdfFigure(20, 5, source_pdf((200, 100)), preview=png((3, 1)))


@pytest.mark.parametrize("preview", [b"not an image", png((20, 10))[:-12]])
def test_a_preview_that_is_not_a_png_or_jpeg_is_refused(preview):
    with pytest.raises(ValueError, match="preview"):
        PdfFigure(20, 5, source_pdf(), preview=preview)


def test_a_gif_preview_is_refused():
    output = BytesIO()
    PILImage.new("RGB", (20, 10)).save(output, format="GIF")
    with pytest.raises(ValueError, match="PNG or JPEG"):
        PdfFigure(20, 5, source_pdf(), preview=output.getvalue())


def test_the_figure_snapshots_its_bytes():
    data = bytearray(source_pdf())
    block = PdfFigure(20, 5, data)
    data[:] = b"changed"
    assert block.data == source_pdf()
    with pytest.raises(FrozenInstanceError):
        block.page = 1


@pytest.mark.parametrize("arguments, keywords, message", [
    ((0, 5, source_pdf()), {}, "col_span"),
    ((20, 0, source_pdf()), {}, "rows"),
    ((20, 5, "drawing.pdf"), {}, "data"),
    ((20, 5, b"not a pdf"), {}, "not a readable PDF"),
    ((20, 5, source_pdf()), {"page": 3}, "has no page 3"),
    ((20, 5, source_pdf()), {"page": "0"}, "page"),
    ((20, 5, source_pdf()), {"align": "middle"}, "align"),
    ((20, 5, source_pdf()), {"valign": "center"}, "valign"),
    ((20, 5, source_pdf()), {"block_id": 3}, "block_id"),
])
def test_invalid_figures_are_refused_when_made(arguments, keywords, message):
    with pytest.raises(ValueError, match=message):
        PdfFigure(*arguments, **keywords)


def test_errors_name_the_block():
    with pytest.raises(ValueError, match="^drawing: "):
        PdfFigure(20, 5, b"not a pdf", block_id="drawing")


def test_a_frame_wider_than_the_space_is_an_overflow(context):
    with pytest.raises(LayoutOverflowError) as caught:
        measure_block(PdfFigure(30, 5, source_pdf(), block_id="drawing"), context, 200)
    assert (caught.value.needed, caught.value.available) == (300, 200)


def test_a_quarter_turn_refuses_a_pdf_figure(context):
    turned = QuarterTurn(PdfFigure(10, 5, source_pdf()), turns=1, local_grid=GridSpec(0, 0, 10, 10, 20, 20))
    with pytest.raises(ValueError, match="VectorPage"):
        measure_block(turned, context, 400)


# --- hand-made PDFs: what pypdf cannot read is a ValueError ------------------------------------

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


def one_page(extra=b"", media=b"[0 0 100 50]", kids=b"[3 0 R]", more=None):
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 2: b"<< /Type /Pages /Kids " + kids + b" /Count 1 >>",
               3: b"<< /Type /Page /Parent 2 0 R /MediaBox " + media + b" " + extra + b" >>"}
    objects.update(more or {})
    return handmade(objects)


def test_a_page_without_content_has_a_box():
    assert pdf_page_box(one_page(), 0) == (0, 0, 100, 50)


@pytest.mark.parametrize("data, message", [
    (one_page(kids=b"5"), "not a readable PDF"),
    (one_page(media=b"[0 0 100]"), "page box is not readable"),
    (one_page(b"/Contents 9 0 R"), "page content is not readable"),
    (one_page(b"/Rotate /X"), "not a readable PDF"),
])
def test_broken_structures_are_value_errors(data, message):
    with pytest.raises(ValueError, match=message):
        pdf_page_box(data, 0)


@pytest.mark.parametrize("page", [-1, True, 1.0])
def test_the_page_number_is_a_nonnegative_integer(page):
    with pytest.raises(ValueError, match="nonnegative integer"):
        pdf_page_box(source_pdf(), page)
