from dataclasses import FrozenInstanceError
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
import pytest

from gridlayoutpdf.bounds import command_bounds
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.figures import Image
from gridlayoutpdf.geometry import GridSpec, Rect
from gridlayoutpdf.layout import LayoutContext, LayoutPart, MeasuredBlock, measure_block
from gridlayoutpdf.profiles import PageProfile
from gridlayoutpdf.scene import RasterImage, ScenePage
from gridlayoutpdf.styles import ReportStyle


@pytest.fixture
def context():
    return LayoutContext(FontRegistry(), PageProfile("image", 200, 200,
                         GridSpec(0, 0, 10, 10, 20, 20)), ReportStyle())


def image_bytes(size=(40, 20), mode="RGBA", color=(255, 0, 0, 128), format="PNG", **kwargs):
    output = BytesIO()
    PILImage.new(mode, size, color).save(output, format=format, **kwargs)
    return output.getvalue()


def test_raster_image_is_immutable_translated_and_accepted_at_common_boundaries(context):
    mutable = bytearray(image_bytes())
    command = RasterImage(1, 2, 30, 15, mutable)
    snapshot = bytes(mutable)
    mutable[0] = 0
    assert command.data == snapshot and isinstance(command.data, bytes)
    assert command_bounds(command, context.fonts) == Rect(1, 2, 30, 15)
    assert command.translated(4, 5) == RasterImage(5, 7, 30, 15, snapshot)
    assert ScenePage(context.profile, (command,)).commands == (command,)
    measured = MeasuredBlock(40, 10, (LayoutPart(2, (command,)),))
    assert measured.commands == (command,)
    with pytest.raises(FrozenInstanceError):
        command.width = 2


@pytest.mark.parametrize("field, invalid", [
    ("x", True), ("y", float("nan")), ("width", 0), ("width", -1),
    ("height", float("inf")), ("height", False), ("data", "not bytes"), ("data", b""),
])
def test_raster_image_validates_coordinates_and_byte_snapshot(field, invalid):
    with pytest.raises(ValueError):
        RasterImage(**{"x": 0, "y": 0, "width": 30, "height": 15, "data": image_bytes(), field: invalid})


@pytest.mark.parametrize("size, expected", [((80, 20), (0, 15, 40, 10)), ((20, 80), (15, 0, 10, 40))])
def test_image_fits_grid_frame_without_distortion_and_snapshots_content(context, tmp_path, size, expected):
    path = tmp_path / "input.png"
    path.write_bytes(image_bytes(size=size))
    block = Image(path, col_span=4, rows=4, block_id="photo")
    measured = measure_block(block, context, 50)
    command, = measured.commands
    assert (command.x, command.y, command.width, command.height) == expected
    assert (measured.width, measured.rows, measured.height) == (40, 4, 40)
    assert measured.keep_together and measured.block_id == "photo"
    assert measured.split(2) is None
    assert measure_block(block, context, 50) == measured
    path.write_bytes(b"replaced after measurement")
    with PILImage.open(BytesIO(command.data)) as decoded:
        assert decoded.size == size
        assert decoded.getpixel((0, 0)) == (255, 0, 0, 128)
    with pytest.raises(FrozenInstanceError):
        block.rows = 8


@pytest.mark.parametrize("align, expected", [("left", 0), ("center", 15), ("right", 30)])
def test_portrait_image_horizontal_alignment(context, tmp_path, align, expected):
    path = tmp_path / "portrait.png"
    path.write_bytes(image_bytes(size=(20, 80)))
    command, = Image(path, col_span=4, rows=4, align=align).measure(context, 40).commands
    assert command.x == expected and command.y == 0


@pytest.mark.parametrize("valign, expected", [("top", 0), ("middle", 15), ("bottom", 30)])
def test_landscape_image_vertical_alignment(context, tmp_path, valign, expected):
    path = tmp_path / "landscape.png"
    path.write_bytes(image_bytes(size=(80, 20)))
    command, = Image(path, col_span=4, rows=4, valign=valign).measure(context, 40).commands
    assert command.y == expected and command.x == 0


@pytest.mark.parametrize("kwargs", [
    {"path": None}, {"col_span": 0}, {"rows": 0}, {"col_span": True},
    {"rows": 1.5}, {"align": "justify"}, {"valign": "center"}, {"block_id": 2},
])
def test_image_validates_frame_and_options_at_construction(kwargs):
    with pytest.raises(ValueError):
        Image(**{"path": "unused.png", "col_span": 4, "rows": 4, **kwargs})


def test_image_decode_failures_include_path_source_and_cause(context, tmp_path):
    path = tmp_path / "broken.png"
    for data in (None, b"not an image", image_bytes(mode="RGB", color="red", format="BMP")):
        if data is not None:
            path.write_bytes(data)
        with pytest.raises(ValueError) as caught:
            Image(path, col_span=4, rows=4, block_id="photo").measure(context, 40)
        assert "photo" in str(caught.value) and "broken.png" in str(caught.value)
        assert caught.value.__cause__ is not None


def test_animated_png_is_explicitly_rejected(context, tmp_path):
    path = tmp_path / "animated.png"
    PILImage.new("RGB", (20, 20), "red").save(path, save_all=True,
        append_images=[PILImage.new("RGB", (20, 20), "blue")], duration=50, loop=0)
    with pytest.raises(ValueError, match="frame"):
        Image(path, col_span=4, rows=4).measure(context, 40)


def test_exif_orientation_is_normalized_before_measurement(context, tmp_path):
    path = tmp_path / "oriented.jpg"
    exif = PILImage.Exif()
    exif[274] = 6
    PILImage.new("RGB", (80, 20), "red").save(path, exif=exif)
    command, = Image(path, col_span=4, rows=4).measure(context, 40).commands
    assert (command.x, command.y, command.width, command.height) == (15, 0, 10, 40)
    with PILImage.open(BytesIO(command.data)) as normalized:
        assert normalized.size == (20, 80)
        assert normalized.format == "PNG"
        assert normalized.getexif().get(274, 1) == 1


def test_palette_transparency_is_preserved_in_normalized_bytes(context, tmp_path):
    path = tmp_path / "palette.png"
    source = PILImage.new("P", (20, 20))
    source.putpalette([255, 0, 0] + [0, 0, 0] * 255)
    source.save(path, transparency=0)
    command, = Image(path, col_span=4, rows=4).measure(context, 40).commands
    with PILImage.open(BytesIO(command.data)) as normalized:
        assert normalized.mode == "RGBA"
        assert normalized.getpixel((0, 0)) == (255, 0, 0, 0)


def test_image_measure_rejects_frame_before_reading_missing_path(context):
    from gridlayoutpdf.errors import LayoutOverflowError
    block = Image("not-read.png", col_span=4, rows=4)
    with pytest.raises(ValueError, match="context"):
        block.measure(None, 40)
    for width in (0, -1, True, float("inf")):
        with pytest.raises(ValueError, match="available_width"):
            block.measure(context, width)
    with pytest.raises(LayoutOverflowError) as caught:
        block.measure(context, 30)
    assert (caught.value.needed, caught.value.available) == (40, 30)


def test_raster_image_rejects_nonfinite_derived_edges_and_translation():
    with pytest.raises(ValueError, match="right"):
        RasterImage(1e308, 0, 1e308, 10, image_bytes())
    with pytest.raises(ValueError):
        RasterImage(0, 0, 10, 10, image_bytes()).translated(float("inf"), 0)
