from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest
from reportlab.pdfbase import pdfmetrics

from gridlayoutpdf import fontfinder
from gridlayoutpdf.errors import FontError
from gridlayoutpdf.fonts import FontRegistry, TextMetrics, default_fonts
from gridlayoutpdf.geometry import Rect
from gridlayoutpdf.styles import TextStyle

from _sfnt import FIXTURE_FONT, renamed, widened_capital_a, write_font, zero_units_per_em


BUNDLED_MINCHO = Path(__file__).resolve().parents[2] / "src" / "gridlayoutpdf" / "font_data" / "ipaexm.ttf"


@pytest.fixture
def windows(tmp_path, monkeypatch):
    """A temporary Windows font folder searched after the bundled fonts."""
    system = tmp_path / "windir" / "Fonts"
    system.mkdir(parents=True)
    monkeypatch.setenv("WINDIR", str(tmp_path / "windir"))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(fontfinder, "_is_windows", lambda: True)
    return system


@pytest.fixture
def fonts():
    return FontRegistry()


def test_resolve_records_the_named_face_and_is_idempotent(fonts):
    face = fonts.resolve("IPAex明朝")
    assert (face.name, face.path, face.face_index, face.family) == (
        "IPAex明朝", BUNDLED_MINCHO.resolve(), 0, "IPAexMincho")
    assert face.sha256 == sha256(FIXTURE_FONT.read_bytes()).hexdigest()
    assert face.sha256 in face.pdf_name
    assert pdfmetrics.getFont(face.pdf_name).face.name == face.pdf_name.encode("ascii")
    assert fonts.resolve("IPAex明朝") is face
    english = fonts.resolve("IPAexMincho")
    assert english.name == "IPAexMincho" and english.pdf_name == face.pdf_name
    assert FontRegistry().resolve("IPAex明朝").pdf_name == face.pdf_name
    with pytest.raises(FrozenInstanceError):
        face.name = "different"


def test_register_is_no_longer_part_of_the_resolver():
    assert not hasattr(FontRegistry, "register")


def test_default_registry_is_shared_and_lazy():
    assert default_fonts() is default_fonts()
    assert isinstance(default_fonts(), FontRegistry)


def test_bundled_gothic_measures_with_its_own_face(fonts):
    gothic = fonts.resolve("IPAexゴシック")
    assert gothic.path.name == "ipaexg.ttf" and gothic.family == "IPAexGothic"
    assert gothic.pdf_name != fonts.resolve("IPAex明朝").pdf_name
    assert fonts.measure("日本", TextStyle(font="IPAexゴシック")).width == pytest.approx(20)


def test_cff_outlines_found_by_name_are_rejected(fonts, windows):
    write_font(windows / "cff.otf", renamed("GLP CFF Face"), version=b"OTTO")
    with pytest.raises(FontError, match="cff.otf") as caught:
        fonts.resolve("GLP CFF Face")
    assert "Unsupported" in str(caught.value)


@pytest.mark.parametrize("name", ["", " ", None, 2])
def test_resolve_rejects_invalid_names(fonts, name):
    with pytest.raises(FontError, match="name"):
        fonts.resolve(name)


def test_unknown_name_is_diagnostic_and_not_cached(fonts, windows):
    with pytest.raises(FontError, match="GLP Unknown"):
        fonts.resolve("GLP Unknown")
    write_font(windows / "late.ttf", renamed("GLP Unknown"))
    assert fonts.resolve("GLP Unknown").path.name == "late.ttf"


def test_bundled_font_bytes_must_match_the_manifest(fonts, monkeypatch, tmp_path):
    import json
    import shutil

    copy = tmp_path / "font_data"
    shutil.copytree(BUNDLED_MINCHO.parent, copy)
    manifest = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["fonts"]:
        if entry["file"] == "ipaexg.ttf":
            entry["sha256"] = "0" * 64
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(fontfinder, "BUNDLED_DIRECTORY", copy)
    fontfinder._bundled_manifest.cache_clear()
    try:
        with pytest.raises(FontError, match="bundled"):
            fonts.resolve("IPAexGothic")
    finally:
        fontfinder._bundled_manifest.cache_clear()


def test_measure_uses_the_registered_face_and_positive_vertical_extents(fonts):
    style = TextStyle()
    text = "日本語 橋脚 計算書 σ τ φ Σ √ × ÷ ≦ ≧ ± = ＝ α β γ μ ² ³ − ABC xyz 123"
    metrics = fonts.measure(text, style)
    registered = pdfmetrics.getFont(fonts.resolve("IPAex明朝").pdf_name)
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


def test_different_files_with_same_postscript_name_do_not_collide(fonts, windows):
    write_font(windows / "wide.ttf", widened_capital_a(renamed("GLP Wide Mincho")))
    first_face = fonts.resolve("IPAex明朝")
    second_face = fonts.resolve("GLP Wide Mincho")
    assert first_face.pdf_name != second_face.pdf_name
    first_registered = pdfmetrics.getFont(first_face.pdf_name)
    second_registered = pdfmetrics.getFont(second_face.pdf_name)
    assert first_registered is not second_registered
    assert first_registered.face is not second_registered.face
    wide = TextStyle(font="GLP Wide Mincho")
    assert fonts.measure("A", wide).width - fonts.measure("A", TextStyle()).width == pytest.approx(0.3125)
    assert second_registered.stringWidth("A", 10) == fonts.measure("A", wide).width


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
        assert "IPAex明朝" in str(caught.value)


def test_unknown_font_and_invalid_text_input_are_diagnostic(fonts, windows):
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


def test_resolved_faces_measure_from_cached_boxes_after_the_file_changes(fonts, windows, monkeypatch):
    copied = write_font(windows / "copied.ttf", renamed("GLP Copied Mincho"))
    second_face = fonts.resolve("GLP Copied Mincho")
    assert second_face.path == copied.resolve()
    copied.write_bytes(b"file changed after resolution")

    def unexpected_read(*args, **kwargs):
        raise AssertionError("Measuring must use the previously cached glyph boxes")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    monkeypatch.setattr(pdfmetrics.getFont(second_face.pdf_name).face, "get_table", unexpected_read)
    measured = fonts.measure("jÅ", TextStyle(font="GLP Copied Mincho", tracking=0.25))
    assert measured.ink_bounds == Rect(-0.5419921875, -9.150390625, 11.1435546875, 11.1376953125)
    assert fonts.resolve("GLP Copied Mincho") is second_face


def test_zero_units_per_em_is_a_chained_font_error_and_resolution_is_atomic(fonts, windows):
    invalid = write_font(windows / "zero-units.ttf", zero_units_per_em(renamed("GLP Bad Metrics")))
    original = fonts.resolve("IPAex明朝")
    invalid_pdf_name = f"GLP_{sha256(invalid.read_bytes()).hexdigest()}_f0"
    with pytest.raises(FontError) as caught:
        fonts.resolve("GLP Bad Metrics")
    message = str(caught.value)
    assert "GLP Bad Metrics" in message
    assert str(invalid.resolve()) in message
    assert "face 0" in message
    assert isinstance(caught.value.__cause__, ZeroDivisionError)
    assert fonts.resolve("IPAex明朝") is original
    assert invalid_pdf_name not in pdfmetrics.getRegisteredFontNames()
    write_font(invalid, renamed("GLP Bad Metrics"))
    assert fonts.measure("j", TextStyle(font="GLP Bad Metrics")) == fonts.measure("j", TextStyle())


def test_collection_faces_load_and_measure_by_name(fonts, windows, tmp_path):
    from _sfnt import build_collection
    import pymupdf

    from gridlayoutpdf import A4_PORTRAIT_REFERENCE, ScenePage, Text, render_pdf

    (windows / "pair.ttc").write_bytes(build_collection([
        renamed("GLP Pair Alpha"), widened_capital_a(renamed("GLP Pair Beta"))]))
    alpha, beta = fonts.resolve("GLP Pair Alpha"), fonts.resolve("GLP Pair Beta")
    assert (alpha.face_index, beta.face_index) == (0, 1)
    assert alpha.pdf_name.endswith("_f0") and beta.pdf_name.endswith("_f1")
    assert alpha.sha256 == beta.sha256
    width = fonts.measure("A", TextStyle(font="GLP Pair Beta")).width
    assert width - fonts.measure("A", TextStyle(font="GLP Pair Alpha")).width == pytest.approx(0.3125)
    output = tmp_path / "beta.pdf"
    render_pdf((ScenePage(A4_PORTRAIT_REFERENCE, (Text(60, 80, "A", TextStyle(font="GLP Pair Beta")),)),),
               output, fonts)
    with pymupdf.open(output) as pdf:
        assert any(beta.pdf_name in entry[3] for entry in pdf[0].get_fonts(full=True))


def test_decomposed_names_resolve_to_the_composed_face(fonts):
    import unicodedata

    decomposed = unicodedata.normalize("NFD", "IPAexゴシック")
    assert decomposed != "IPAexゴシック"
    assert fonts.resolve(decomposed) is fonts.resolve("IPAexゴシック")
    assert fonts.resolve(decomposed).name == "IPAexゴシック"


def test_a_file_renamed_after_indexing_is_rejected_by_its_loaded_names(fonts, windows):
    import os

    path = write_font(windows / "same.ttf", renamed("GLP AAAA"))
    from gridlayoutpdf import fontfinder as finder

    assert finder.find_font("GLP AAAA").path.name == "same.ttf"
    stat = path.stat()
    write_font(path, renamed("GLP BBBB"))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_size == stat.st_size
    with pytest.raises(FontError, match="no longer named"):
        fonts.resolve("GLP AAAA")
    assert fonts.resolve("GLP BBBB").path.name == "same.ttf"


def test_a_stale_index_is_dropped_for_every_folder_spelling(fonts, windows):
    """A junction may make the resolved file's parent differ from the indexed folder."""
    import os

    from gridlayoutpdf import fontfinder as finder

    path = write_font(windows / "spelled.ttf", renamed("GLP CCCC"))
    assert finder.find_font("GLP CCCC").path.name == "spelled.ttf"
    assert finder._INDEXES
    stat = path.stat()
    write_font(path, renamed("GLP DDDD"))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises(FontError, match="no longer named"):
        fonts.resolve("GLP CCCC")
    assert not finder._INDEXES
    assert fonts.resolve("GLP DDDD").path.name == "spelled.ttf"


def test_a_subclass_returning_an_unloaded_face_gets_a_font_error():
    from gridlayoutpdf.fonts import FontFace

    class Foreign(FontRegistry):
        def resolve(self, name):
            return FontFace(name, Path("x.ttf").resolve(), 0, "0" * 64, "Helvetica")

    with pytest.raises(FontError, match="did not load"):
        Foreign().measure("A", TextStyle())


def test_a_requested_face_damaged_after_indexing_is_a_wrapped_font_error(fonts, windows):
    import os
    import struct

    from _sfnt import build_collection

    from gridlayoutpdf import fontfinder as finder

    path = windows / "pair.ttc"
    data = bytearray(build_collection([renamed("GLP X0"), renamed("GLP X1")]))
    path.write_bytes(bytes(data))
    assert finder.find_font("GLP X1").face_index == 1
    stat = path.stat()
    struct.pack_into(">I", data, 16, len(data) + 1000)  # Face 1 now points outside the file.
    path.write_bytes(bytes(data))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises(FontError, match="GLP X1") as caught:
        fonts.resolve("GLP X1")
    assert str(path.resolve()) in str(caught.value) and "face 1" in str(caught.value)
    assert isinstance(caught.value.__cause__, FontError)
    assert not finder._INDEXES
    with pytest.raises(FontError, match="unreadable"):
        finder.find_font("GLP X1")
    assert fonts.resolve("GLP X0").face_index == 0
