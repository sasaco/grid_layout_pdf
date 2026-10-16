from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
import struct

import pytest
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from gridlayoutpdf.errors import FontError
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.geometry import Rect
from gridlayoutpdf.styles import TextStyle


FONT_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "fonts" / "ipaexm.ttf"


def _different_font(tmp_path):
    """A valid temporary derivative with the same names and a wider ASCII A."""
    data = bytearray(FONT_PATH.read_bytes())
    records = {}
    for index in range(struct.unpack_from(">H", data, 4)[0]):
        record = 12 + 16 * index
        tag, _, offset, length = struct.unpack_from(">4sIII", data, record)
        records[tag] = (record, offset, length)
    original = TTFont("original-fixture", str(FONT_PATH))
    glyph = original.face.charToGlyph[ord("A")]
    width_offset = records[b"hmtx"][1] + 4 * glyph
    advance = struct.unpack_from(">H", data, width_offset)[0]
    struct.pack_into(">H", data, width_offset, advance + 64)

    def checksum(raw):
        raw = bytes(raw) + b"\x00" * ((-len(raw)) % 4)
        return sum(struct.unpack(f">{len(raw) // 4}I", raw)) & 0xFFFFFFFF

    record, offset, length = records[b"hmtx"]
    struct.pack_into(">I", data, record + 4, checksum(data[offset : offset + length]))
    head = records[b"head"][1]
    struct.pack_into(">I", data, head + 8, 0)
    struct.pack_into(">I", data, head + 8, (0xB1B0AFBA - checksum(data)) & 0xFFFFFFFF)
    result = tmp_path / "changed.ttf"
    result.write_bytes(data)
    return result


@pytest.fixture
def fonts():
    registry = FontRegistry()
    registry.register("body", FONT_PATH)
    return registry


def test_registration_records_exact_face_and_is_idempotent(fonts):
    face = fonts.resolve("body")
    assert (face.name, face.path, face.face_index) == ("body", FONT_PATH.resolve(), 0)
    assert face.sha256 == sha256(FONT_PATH.read_bytes()).hexdigest()
    assert face.sha256 in face.pdf_name
    assert pdfmetrics.getFont(face.pdf_name).face.name == face.pdf_name.encode("ascii")
    fonts.register("body", FONT_PATH)
    assert fonts.resolve("body") is face
    other = FontRegistry()
    other.register("same-file-another-name", FONT_PATH)
    assert other.resolve("same-file-another-name").pdf_name == face.pdf_name
    with pytest.raises(FrozenInstanceError):
        face.name = "different"


def test_registration_rejects_missing_unreadable_or_unsupported_font(tmp_path):
    registry = FontRegistry()
    with pytest.raises(FontError, match="missing.ttf"):
        registry.register("missing", tmp_path / "missing.ttf")
    with pytest.raises(FontError):
        registry.register("directory", tmp_path)
    for data in (b"not a font", b"OTTO" + bytes(32), b"\x00\x01\x00\x00" + bytes(32)):
        invalid = tmp_path / "invalid.ttf"
        invalid.write_bytes(data)
        with pytest.raises(FontError, match="invalid.ttf"):
            registry.register("invalid", invalid)


@pytest.mark.parametrize("index", [-1, True, 1.5, 1, 99])
def test_registration_rejects_invalid_or_nonexistent_face(index):
    with pytest.raises(FontError, match="face"):
        FontRegistry().register("body", FONT_PATH, face_index=index)


@pytest.mark.parametrize("name", ["", " ", None, 2])
def test_registration_rejects_invalid_logical_name(name):
    with pytest.raises(FontError, match="name"):
        FontRegistry().register(name, FONT_PATH)


def test_unknown_name_and_conflicting_re_registration_are_diagnostic(fonts, tmp_path):
    with pytest.raises(FontError, match="unknown"):
        fonts.resolve("unknown")
    original = fonts.resolve("body")
    with pytest.raises(FontError, match="body"):
        fonts.register("body", _different_font(tmp_path))
    assert fonts.resolve("body") is original


def test_measure_uses_the_registered_face_and_positive_vertical_extents(fonts):
    style = TextStyle()
    text = "日本語 橋脚 計算書 σ τ φ Σ √ × ÷ ≦ ≧ ± = ＝ α β γ μ ² ³ − ABC xyz 123"
    metrics = fonts.measure(text, style)
    registered = pdfmetrics.getFont(fonts.resolve("body").pdf_name)
    assert metrics.width == pytest.approx(registered.stringWidth(text, 10))
    assert metrics.ascent == pytest.approx(8.798828125)
    assert metrics.descent == pytest.approx(1.9482421875)  # The y ink exceeds OS/2 descent.
    assert fonts.measure(text, style) == metrics
    assert fonts.measure("日本", style).width == pytest.approx(20)
    assert fonts.measure("=", style).width < fonts.measure("＝", style).width
    with pytest.raises(FrozenInstanceError):
        metrics.width = 0


def test_tracking_adds_only_the_gaps_between_characters(fonts):
    style = TextStyle(tracking=0.25)
    assert fonts.measure("日本語", style).width == pytest.approx(30.5)
    assert fonts.measure("日", style).width == pytest.approx(10)
    assert fonts.measure("", style).width == 0


def test_different_files_with_same_postscript_name_do_not_collide(fonts, tmp_path):
    second = FontRegistry()
    second.register("body", _different_font(tmp_path))
    first_face = fonts.resolve("body")
    second_face = second.resolve("body")
    assert first_face.pdf_name != second_face.pdf_name
    first_registered = pdfmetrics.getFont(first_face.pdf_name)
    second_registered = pdfmetrics.getFont(second_face.pdf_name)
    assert first_registered is not second_registered
    assert first_registered.face is not second_registered.face
    assert second.measure("A", TextStyle()).width - fonts.measure("A", TextStyle()).width == pytest.approx(0.3125)
    assert second_registered.stringWidth("A", 10) == second.measure("A", TextStyle()).width


def test_nfc_normalization_is_shared_and_tracking_counts_composed_characters(fonts):
    decomposed = "か\u3099e\u0301"
    assert fonts.normalize_text(decomposed) == "がé"
    style = TextStyle(tracking=0.25)
    assert fonts.measure(decomposed, style) == fonts.measure("がé", style)


@pytest.mark.parametrize("text", ["\U0010ffff", "日本\U0010ffff", "\n", "\t"])
def test_missing_glyphs_are_reported_before_any_width_is_returned(fonts, text):
    for _ in range(2):
        with pytest.raises(FontError, match="U\\+") as caught:
            fonts.measure(text, TextStyle())
        assert "body" in str(caught.value)


def test_unknown_font_and_invalid_text_input_are_diagnostic(fonts):
    with pytest.raises(FontError, match="unknown"):
        fonts.measure("日本", TextStyle(font="unknown"))
    with pytest.raises(ValueError, match="text"):
        fonts.normalize_text(None)
    with pytest.raises(ValueError, match="style"):
        fonts.measure("日本", None)


def test_uncomposable_combining_marks_are_explicitly_unsupported(fonts):
    with pytest.raises(FontError, match="combining"):
        fonts.measure("x\u3099", TextStyle())


def test_metric_overflow_is_rejected_instead_of_returning_infinity(fonts):
    with pytest.raises(ValueError, match="finite"):
        fonts.measure("日本", TextStyle(size=1e308))


def test_text_metrics_bounds_combine_advance_typographic_extents_and_ink():
    legacy = TextMetrics(7, 8, 2)
    assert legacy.ink_bounds is None
    assert legacy.bounds == Rect(0, -8, 7, 10)
    overhanging = TextMetrics(7, 8, 2, ink_bounds=Rect(-0.5, -9, 8, 12))
    assert overhanging.width == 7
    assert overhanging.bounds == Rect(-0.5, -9, 8, 12)
    inset = TextMetrics(7, 8, 2, ink_bounds=Rect(1, -7, 4, 6))
    assert inset.bounds == legacy.bounds
    with pytest.raises(ValueError, match="ink_bounds"):
        TextMetrics(7, 8, 2, ink_bounds=[])


def test_glyph_ink_can_extend_below_the_typographic_descender(fonts):
    metrics = fonts.measure("g", TextStyle())
    assert metrics.descent == pytest.approx(1.9775390625)
    assert metrics.ink_bounds.bottom == pytest.approx(1.9775390625)


def test_j_keeps_its_advance_and_includes_its_left_overhang(fonts):
    metrics = fonts.measure("j", TextStyle())
    assert metrics.width == pytest.approx(3.0419921875)
    assert metrics.ink_bounds.x == pytest.approx(-0.5419921875)
    assert metrics.bounds.x == pytest.approx(-0.5419921875)
    assert metrics.bounds.right == pytest.approx(metrics.width)
    assert metrics.descent == pytest.approx(1.9873046875)


def test_accented_capital_and_radical_include_right_overhang(fonts):
    capital = fonts.measure("Å", TextStyle())
    assert capital.width == pytest.approx(7.2412109375)
    assert capital.ascent == pytest.approx(9.150390625)
    assert capital.ink_bounds.right == pytest.approx(7.3095703125)
    assert capital.bounds.right == pytest.approx(7.3095703125)
    radical = fonts.measure("√", TextStyle())
    assert radical.width == pytest.approx(5.3515625)
    assert radical.ink_bounds.right == pytest.approx(5.44921875)
    assert radical.bounds.right == pytest.approx(5.44921875)


def test_multiple_glyph_ink_uses_each_advance_and_intercharacter_tracking(fonts):
    metrics = fonts.measure("jÅ", TextStyle(tracking=0.25))
    assert metrics.width == pytest.approx(10.533203125)
    assert metrics.ink_bounds == Rect(-0.5419921875, -9.150390625, 11.1435546875, 11.1376953125)
    assert metrics.bounds == metrics.ink_bounds
    assert fonts.measure("jA\u030a", TextStyle(tracking=0.25)) == metrics
    assert fonts.measure("jÅ", TextStyle(size=20, tracking=0.5)).ink_bounds == Rect(
        -1.083984375, -18.30078125, 22.287109375, 22.275390625
    )


@pytest.mark.parametrize("text", ["", " ", "   "])
def test_empty_and_space_runs_have_zero_ink_but_retain_typographic_extents(fonts, text):
    metrics = fonts.measure(text, TextStyle(tracking=0.25))
    assert metrics.ink_bounds == Rect(0, 0, 0, 0)
    assert metrics.bounds == Rect(0, -8.798828125, metrics.width, 10)


def test_each_registry_caches_boxes_from_the_registered_face_not_the_later_path(
    fonts, tmp_path, monkeypatch
):
    copied = tmp_path / "copied.ttf"
    copied.write_bytes(FONT_PATH.read_bytes())
    second = FontRegistry()
    second.register("body", copied)
    first_face = fonts.resolve("body")
    second_face = second.resolve("body")
    assert second_face.pdf_name == first_face.pdf_name
    assert second_face.path == copied.resolve()
    copied.write_bytes(b"file changed after registration")

    def unexpected_read(*args, **kwargs):
        raise AssertionError("Measuring must use the previously cached glyph boxes")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    monkeypatch.setattr(pdfmetrics.getFont(first_face.pdf_name).face, "get_table", unexpected_read)
    measured = second.measure("jÅ", TextStyle(tracking=0.25))
    assert measured.ink_bounds == Rect(-0.5419921875, -9.150390625, 11.1435546875, 11.1376953125)
    assert measured == fonts.measure("jÅ", TextStyle(tracking=0.25))
    assert second.resolve("body").sha256 == first_face.sha256


def test_zero_units_per_em_is_a_chained_font_error_and_registration_is_atomic(fonts, tmp_path):
    data = bytearray(FONT_PATH.read_bytes())
    for index in range(struct.unpack_from(">H", data, 4)[0]):
        tag, _, offset, _ = struct.unpack_from(">4sIII", data, 12 + 16 * index)
        if tag == b"head":
            struct.pack_into(">H", data, offset + 18, 0)
            break
    else:
        pytest.fail("The pinned test font must have a head table")
    invalid = tmp_path / "zero-units.ttf"
    invalid.write_bytes(data)
    original = fonts.resolve("body")
    invalid_pdf_name = f"GLP_{sha256(data).hexdigest()}_f0"
    with pytest.raises(FontError) as caught:
        fonts.register("bad-metrics", invalid)
    message = str(caught.value)
    assert "bad-metrics" in message
    assert str(invalid) in message
    assert "face 0" in message
    assert isinstance(caught.value.__cause__, ZeroDivisionError)
    assert fonts.resolve("body") is original
    with pytest.raises(FontError, match="bad-metrics"):
        fonts.resolve("bad-metrics")
    assert invalid_pdf_name not in pdfmetrics.getRegisteredFontNames()
    fonts.register("bad-metrics", FONT_PATH)
    assert fonts.measure("j", TextStyle(font="bad-metrics")) == fonts.measure("j", TextStyle())
