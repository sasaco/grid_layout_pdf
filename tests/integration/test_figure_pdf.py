from io import BytesIO
import importlib.util
import json
from pathlib import Path

from PIL import Image as PILImage
import pymupdf
import pytest

from gridlayoutpdf.figures import Arrow, Figure, Image, Label
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.geometry import GridSpec
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.profiles import PageProfile
from gridlayoutpdf.renderers import reportlab as backend
from gridlayoutpdf.scene import RasterImage, Rectangle, ScenePage
from gridlayoutpdf.styles import ReportStyle, TextStyle


@pytest.fixture
def context():
    fonts = FontRegistry()
    fonts.register("body", Path(__file__).resolve().parents[1] / "fixtures/fonts/ipaexm.ttf")
    return LayoutContext(fonts, PageProfile("proof", 200, 200,
                         GridSpec(0, 0, 10, 10, 20, 20)), ReportStyle())


def test_vector_figure_and_image_snapshot_render_at_independent_pdf_coordinates(context, tmp_path):
    source = tmp_path / "source.png"
    PILImage.new("RGBA", (80, 40), (255, 0, 0, 128)).save(source)
    figure = measure_block(Figure(3, 3, Rectangle(2, 2, 26, 26, 1),
        Arrow(5, 20, 25, 20), Label(5, 12, "日本", style=TextStyle(size=8))), context, 30)
    picture = measure_block(Image(source, col_span=4, rows=4), context, 40)
    page = ScenePage(context.profile, (*figure.translated(10, 10), *picture.translated(50, 60)))
    before = page.commands
    PILImage.new("RGB", (10, 80), "blue").save(source)
    output = tmp_path / "figure.pdf"
    backend.render_pdf((page,), output, context.fonts)
    assert page.commands == before
    with pymupdf.open(output) as document:
        pdfpage = document[0]
        assert tuple(pdfpage.rect) == (0, 0, 200, 200)
        assert "日本" in pdfpage.get_text()
        drawings = pdfpage.get_drawings()
        assert len(drawings) == 3
        assert tuple(drawings[0]["rect"]) == pytest.approx((12, 12, 38, 38))
        image, = pdfpage.get_image_info()
        assert image["bbox"] == pytest.approx((50, 70, 90, 90))
        assert (image["width"], image["height"]) == (80, 40)
        image_ref, mask_ref = pdfpage.get_images()[0][:2]
        assert mask_ref > 0  # independent PDF soft-mask object
        assert pymupdf.Pixmap(document, image_ref).pixel(0, 0) == (255, 0, 0)
        assert pymupdf.Pixmap(document, mask_ref).pixel(0, 0) == (128,)
        pixel = pdfpage.get_pixmap().pixel(60, 80)
        # MuPDF's integer alpha compositing may round an opaque channel down by 1.
        assert 254 <= pixel[0] <= 255 and 120 <= pixel[1] <= 135 and 120 <= pixel[2] <= 135


@pytest.mark.parametrize("bad_data", [b"not an image", b"\x89PNG\r\n\x1a\n" + bytes(64)])
def test_bad_direct_raster_image_is_rejected_before_any_output_write(context, tmp_path, monkeypatch, bad_data):
    output = tmp_path / "existing.pdf"
    output.write_bytes(b"previous PDF")
    good = ScenePage(context.profile, (Rectangle(1, 1, 10, 10),))
    bad = ScenePage(context.profile, (RasterImage(1, 1, 10, 10, bad_data),))
    canvas_calls = []
    original = backend.Canvas
    def recording_canvas(*args, **kwargs):
        canvas_calls.append(args)
        return original(*args, **kwargs)
    monkeypatch.setattr(backend, "Canvas", recording_canvas)
    with pytest.raises(ValueError, match=r"page\[2\].commands\[0\]") as caught:
        backend.render_pdf((good, bad), output, context.fonts)
    assert caught.value.__cause__ is not None
    assert canvas_calls == []
    assert output.read_bytes() == b"previous PDF"
    assert not list(tmp_path.glob(".existing.pdf.*.tmp"))
    destination = tmp_path / "new-directory" / "bad.pdf"
    with pytest.raises(ValueError):
        backend.render_pdf((bad,), destination, context.fonts)
    assert not destination.parent.exists()


@pytest.mark.parametrize("failure", ["draw", "save", "replace"])
def test_image_output_failures_preserve_destination_and_clean_temporary(context, tmp_path, monkeypatch, failure):
    buffer = BytesIO()
    PILImage.new("RGB", (10, 10), "red").save(buffer, format="PNG")
    page = ScenePage(context.profile, (RasterImage(10, 20, 30, 30, buffer.getvalue()),))
    output = tmp_path / "kept.pdf"
    output.write_bytes(b"existing")
    def fail(*args, **kwargs):
        raise OSError("injected image output failure")
    if failure == "replace":
        monkeypatch.setattr(backend.os, "replace", fail)
    else:
        monkeypatch.setattr(backend.Canvas, "drawImage" if failure == "draw" else "save", fail)
    with pytest.raises(OSError, match="injected"):
        backend.render_pdf((page,), output, context.fonts)
    assert output.read_bytes() == b"existing"
    assert not list(tmp_path.glob(".kept.pdf.*.tmp"))


@pytest.mark.parametrize("format", ["BMP", "APNG"])
def test_direct_raster_rejects_unsupported_or_multiframe_image(context, tmp_path, format):
    buffer = BytesIO()
    source = PILImage.new("RGB", (10, 10), "red")
    if format == "APNG":
        source.save(buffer, format="PNG", save_all=True,
                    append_images=[PILImage.new("RGB", (10, 10), "blue")])
    else:
        source.save(buffer, format=format)
    page = ScenePage(context.profile, (RasterImage(10, 20, 30, 30, buffer.getvalue()),))
    with pytest.raises(ValueError, match="page"):
        backend.render_pdf((page,), tmp_path / "bad.pdf", context.fonts)


def test_image_outside_paper_is_rejected_before_writing(context, tmp_path):
    buffer = BytesIO()
    PILImage.new("RGB", (10, 10), "red").save(buffer, format="PNG")
    page = ScenePage(context.profile, (RasterImage(190, 20, 30, 30, buffer.getvalue()),))
    from gridlayoutpdf.errors import LayoutOverflowError
    with pytest.raises(LayoutOverflowError):
        backend.render_pdf((page,), tmp_path / "bad.pdf", context.fonts)
    assert not (tmp_path / "bad.pdf").exists()


def test_standalone_figure_proof_has_vector_dimensions_and_undistorted_image(tmp_path):
    root = Path(__file__).resolve().parents[2]
    example = root / "examples/figure_proof.py"
    assert example.is_file(), "standalone figure proof has not been implemented"
    spec = importlib.util.spec_from_file_location("figure_proof", example)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plain, grid, trace_path = module.write_proof(tmp_path, root / "tests/fixtures/fonts/ipaexm.ttf")
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["font_sha256"] == "7a306386f930fee80922f71eebf4ffe0f1ff2817da8e619230953487673d71c7"
    with pymupdf.open(plain) as document, pymupdf.open(grid) as debug:
        assert len(document) == len(debug) == 1
        page = document[0]
        assert tuple(page.rect) == (0, 0, 595, 842)
        assert page.get_text() == debug[0].get_text()
        for value in ("等分布荷重", "梁幅", "5.00 m", "柱高", "3.00 m", "透過PNG"):
            assert value in page.get_text()
        assert len(page.get_drawings()) >= 25
        assert len(debug[0].get_drawings()) == len(page.get_drawings()) + 79
        image, = page.get_image_info()
        assert image["bbox"] == pytest.approx((179.52, 478.198, 404.64, 590.758), abs=.01)
        assert (image["width"], image["height"]) == (240, 120)
        assert (image["bbox"][2] - image["bbox"][0]) / (image["bbox"][3] - image["bbox"][1]) == pytest.approx(2, abs=.001)
    assert (tmp_path / "previews/figure-proof-page-1.png").is_file()
    assert (tmp_path / "previews/figure-proof-grid-page-1.png").is_file()
