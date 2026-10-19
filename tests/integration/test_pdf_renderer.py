"""Inspect renderer output through an independent PDF implementation."""

import importlib
from pathlib import Path
import re

import pymupdf
import pytest

from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.errors import FontError, LayoutOverflowError
from gridlayoutpdf.geometry import GridSpec, Point
from gridlayoutpdf.profiles import PageProfile
from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE as A3
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE as A4
from gridlayoutpdf.scene import Line, Polyline, Rectangle, ScenePage, Text
from gridlayoutpdf.styles import TextStyle


@pytest.fixture
def fonts():
    registry = FontRegistry()
    return registry


def backend():
    try:
        return importlib.import_module("gridlayoutpdf.renderers.reportlab")
    except ModuleNotFoundError as exc:
        pytest.fail(f"PDF backend is not implemented: {exc}")


def characters(page):
    return [
        character
        for block in page.get_text("rawdict")["blocks"] if "lines" in block
        for line in block["lines"] for span in line["spans"]
        for character in span["chars"]
    ]


def spans(page):
    return [
        span
        for block in page.get_text("dict")["blocks"] if "lines" in block
        for line in block["lines"] for span in line["spans"]
    ]


def test_japanese_roundtrip_baseline_font_size_and_page_sizes(fonts, tmp_path):
    text = "日本語 α β γ = 12.50"
    pages = [
        ScenePage(profile, (Text(50.88, 90, text, TextStyle()),))
        for profile in (A4, A3, A4)
    ]
    output = tmp_path / "mixed.pdf"
    backend().render_pdf(pages, output, fonts)
    with pymupdf.open(output) as pdf:
        assert len(pdf) == 3
        assert [(p.rect.width, p.rect.height) for p in pdf] == [(595, 842), (1191, 842), (595, 842)]
        for page in pdf:
            assert page.get_text().strip() == text
            run = spans(page)[0]
            assert run["size"] == pytest.approx(10, abs=0.01)
            assert run["origin"] == pytest.approx((50.88, 90), abs=0.01)
            assert run["color"] == 0


def test_tracking_moves_origins_without_stretching_and_nfc_is_drawn(fonts, tmp_path):
    output = tmp_path / "tracking.pdf"
    page = ScenePage(A4, (
        Text(60, 90, "日本語", TextStyle(tracking=0.5)),
        Text(60, 120, "か\u3099e\u0301", TextStyle(tracking=0.5)),
        Text(60, 150, "日本語", TextStyle()),
    ))
    backend().render_pdf([page], output, fonts)
    with pymupdf.open(output) as pdf:
        chars = characters(pdf[0])
        top = [char for char in chars if abs(char["origin"][1] - 90) < 0.01]
        bottom = [char for char in chars if abs(char["origin"][1] - 150) < 0.01]
        assert [char["origin"][0] for char in top] == pytest.approx([60, 70.5, 81], abs=0.01)
        assert [char["origin"][0] for char in bottom] == pytest.approx([60, 70, 80], abs=0.01)
        assert [char["bbox"][2] - char["bbox"][0] for char in top] == pytest.approx([10] * 3, abs=0.01)
        assert "がé" in pdf[0].get_text()


@pytest.mark.parametrize("turns", range(4))
@pytest.mark.parametrize("shear", [-.342, .342])
def test_native_shear_matrix_preserves_baseline_advance_font_and_following_run(fonts, tmp_path, turns, shear):
    assert "shear_x" in Text.__dataclass_fields__, "Text must support native glyph shear"
    output = tmp_path / "shear.pdf"
    style = TextStyle(size=10, tracking=.25)
    page = ScenePage(A4, (
        Text(150, 200, "jÅ", style, quarter_turns=turns, shear_x=shear),
        Text(150, 240, "jÅ", style),
    ))
    backend().render_pdf((page,), output, fonts)
    with pymupdf.open(output) as pdf:
        page = pdf[0]
        stream = page.read_contents().decode("latin-1")
        number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))"
        matrices = [tuple(map(float, match)) for match in re.findall(r"\s+".join([number]*6)+r"\s+Tm", stream)]
        linear = ((1, 0, shear, 1), (0, 1, -1, shear),
                  (-1, 0, -shear, -1), (0, -1, 1, -shear))[turns]
        assert any(matrix == pytest.approx((*linear, 150, 642)) for matrix in matrices)
        assert "100 Tz" in stream and ".25 Tc" in stream
        chars = characters(page)
        assert [char["c"] for char in chars] == list("jÅjÅ")
        direction = ((1, 0), (0, -1), (-1, 0), (0, 1))[turns]
        # Compare against the same embedded font's plain PDF run: its width
        # table rounds glyph advances independently of the source font metrics.
        advance = chars[3]["origin"][0] - chars[2]["origin"][0]
        assert advance == pytest.approx(fonts.measure("j", style).width + style.tracking, abs=.003)
        assert chars[0]["origin"] == pytest.approx((150, 200), abs=.001)
        assert chars[1]["origin"] == pytest.approx((150+direction[0]*advance, 200+direction[1]*advance), abs=.0001)
        assert chars[2]["origin"] == pytest.approx((150, 240), abs=.001)
        assert chars[3]["origin"][1] == pytest.approx(240, abs=.001)
        assert all(span["size"] == pytest.approx(10, abs=.001) for span in spans(page))
        assert not page.get_images() and not page.get_drawings()
        # ReportLab also declares an unused standard Helvetica resource.
        for name in {span["font"] for span in spans(page)}:
            matches = [item for item in page.get_fonts() if item[3].split("+", 1)[-1].startswith(name)]
            assert len(matches) == 1
            assert pdf.extract_font(matches[0][0])[3]


def test_sheared_ink_overflow_does_not_replace_existing_pdf(fonts, tmp_path):
    assert "shear_x" in Text.__dataclass_fields__
    output = tmp_path / "keep.pdf"
    output.write_bytes(b"existing PDF bytes")
    style = TextStyle()
    x = A4.width - fonts.measure("D", style).bounds.right - .1
    command = Text(x, 100, "D", style, shear_x=.342)
    with pytest.raises(LayoutOverflowError, match="Text bounds"):
        backend().render_pdf((ScenePage(A4, (command,)),), output, fonts)
    assert output.read_bytes() == b"existing PDF bytes"


def test_vector_top_origin_colors_widths_and_page_state_are_independent(fonts, tmp_path):
    output = tmp_path / "vectors.pdf"
    page = ScenePage(A4, (
        Line(60, 80, 90, 100, width=2, color=(1, 0, 0)),
        Rectangle(120, 80, 30, 20, stroke_width=0.75, color=(0, 0, 1)),
        Polyline((Point(170, 80), Point(180, 100), Point(190, 80)), width=1.25, color=(0, 0.5, 0), closed=True),
        Line(210, 80, 230, 100),
        Text(60, 130, "黒", TextStyle()),
    ))
    backend().render_pdf([page, ScenePage(A3, (Line(60, 80, 90, 100),))], output, fonts)
    with pymupdf.open(output) as pdf:
        drawings = pdf[0].get_drawings()
        assert [drawing["width"] for drawing in drawings] == pytest.approx([2, 0.75, 1.25, 0.5])
        assert [drawing["color"] for drawing in drawings] == [(1, 0, 0), (0, 0, 1), (0, 0.5, 0), (0, 0, 0)]
        assert tuple(drawings[0]["items"][0][1]) == pytest.approx((60, 80))
        assert tuple(drawings[0]["items"][0][2]) == pytest.approx((90, 100))
        assert tuple(drawings[1]["rect"]) == pytest.approx((120, 80, 150, 100))
        assert drawings[1]["fill"] is None
        assert spans(pdf[0])[0]["color"] == 0
        assert pdf[1].get_drawings()[0]["color"] == (0, 0, 0)
        assert pdf[1].get_drawings()[0]["width"] == pytest.approx(0.5)


def test_debug_grid_is_opt_in_and_an_explicit_blank_page_is_retained(fonts, tmp_path):
    plain, debug = tmp_path / "plain.pdf", tmp_path / "debug.pdf"
    pages = [ScenePage(A4), ScenePage(A3)]
    backend().render_pdf(pages, plain, fonts)
    backend().render_pdf(pages, debug, fonts, debug_grid=True)
    with pymupdf.open(plain) as pdf:
        assert len(pdf) == 2
        assert all(not page.get_drawings() for page in pdf)
    with pymupdf.open(debug) as pdf:
        assert [len(page.get_drawings()) for page in pdf] == [31 + 48, 68 + 48]
        first = pdf[0].get_drawings()[0]
        assert first["width"] == pytest.approx(0.96)
        assert tuple(first["items"][0][1]) == pytest.approx((50.88, 54.598), abs=0.01)
        assert tuple(first["items"][0][2]) == pytest.approx((50.88, 782.158), abs=0.01)


@pytest.mark.parametrize("bad_text,bad_style", [
    ("\U0010ffff", TextStyle()),
    ("日本", TextStyle(font="absent")),
])
def test_all_glyphs_and_font_names_are_validated_before_opening_output(
    fonts, tmp_path, monkeypatch, bad_text, bad_style,
):
    module = backend()
    output = tmp_path / "report.pdf"
    output.write_bytes(b"previous completed PDF")
    constructed = []
    original = module.Canvas

    def tracked_canvas(*args, **kwargs):
        constructed.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "Canvas", tracked_canvas)
    pages = [ScenePage(A4, (Text(60, 90, "日本", TextStyle()),)),
             ScenePage(A3, (Text(60, 90, bad_text, bad_style),))]
    with pytest.raises(FontError):
        module.render_pdf(pages, output, fonts)
    assert constructed == []
    assert output.read_bytes() == b"previous completed PDF"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("command", [
    Text(60, 1, "日本", TextStyle()),
    Text(590, 90, "日本", TextStyle()),
    Text(60, 841, "日本", TextStyle()),
    Line(0, 20, 40, 20, width=2),
    Rectangle(594, 20, 1, 10, stroke_width=1),
    Polyline((Point(20, 841.8), Point(40, 841.8)), width=1),
])
def test_out_of_page_font_and_stroke_extents_are_diagnostic_and_preserve_output(
    fonts, tmp_path, command,
):
    output = tmp_path / "report.pdf"
    output.write_bytes(b"previous completed PDF")
    with pytest.raises(LayoutOverflowError, match="page\\[1\\].commands\\[0\\]") as caught:
        backend().render_pdf([ScenePage(A4, (command,))], output, fonts)
    assert caught.value.block_id == "page[1].commands[0]"
    assert type(command).__name__ in str(caught.value)
    assert "bounds" in str(caught.value)
    assert output.read_bytes() == b"previous completed PDF"
    assert list(tmp_path.iterdir()) == [output]


def test_grid_stroke_extent_is_also_validated(fonts, tmp_path):
    profile = PageProfile("edge-grid", 100, 100, GridSpec(0, 0, 10, 10, 10, 10))
    with pytest.raises(LayoutOverflowError, match="grid"):
        backend().render_pdf([ScenePage(profile)], tmp_path / "bad.pdf", fonts, debug_grid=True)
    assert not list(tmp_path.iterdir())


def test_invariant_output_is_byte_identical_across_renders(fonts, tmp_path, monkeypatch):
    import time

    pages = [ScenePage(A4, (Text(60, 80, "再現 Same", TextStyle("IPAex明朝", 10)),))]
    first, second, stamped = tmp_path / "first.pdf", tmp_path / "second.pdf", tmp_path / "stamped.pdf"
    backend().render_pdf(pages, first, fonts, invariant=True)
    clock = time.time()
    monkeypatch.setattr(time, "time", lambda: clock + 86400 * 400)
    backend().render_pdf(pages, second, fonts, invariant=True)
    backend().render_pdf(pages, stamped, fonts)
    assert first.read_bytes() == second.read_bytes()
    # The default keeps ReportLab's timestamped metadata.
    assert stamped.read_bytes() != first.read_bytes()
    with pymupdf.open(first) as pdf, pymupdf.open(stamped) as dated:
        assert pdf[0].get_text() == dated[0].get_text()


@pytest.mark.parametrize("value", [1, "yes", None])
def test_invariant_flag_must_be_boolean(fonts, tmp_path, value):
    with pytest.raises(ValueError, match="invariant"):
        backend().render_pdf([ScenePage(A4)], tmp_path / "bad.pdf", fonts, invariant=value)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("pages", [[], iter(()), [object()], None])
def test_empty_or_invalid_page_sequence_fails_without_creating_output(fonts, tmp_path, pages):
    with pytest.raises(ValueError, match="pages"):
        backend().render_pdf(pages, tmp_path / "bad.pdf", fonts)
    assert not list(tmp_path.iterdir())


def test_unsupported_command_is_not_ignored_at_the_backend_boundary(fonts, tmp_path):
    page = ScenePage(A4)
    # Model a corrupted scene from a caller that bypassed the frozen constructor.
    object.__setattr__(page, "commands", (object(),))
    with pytest.raises(ValueError, match="Unsupported.*page\\[1\\]"):
        backend().render_pdf([page], tmp_path / "bad.pdf", fonts)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure_stage", ["draw", "save", "replace"])
def test_failed_output_is_atomic_and_temporary_files_are_removed(
    fonts, tmp_path, monkeypatch, failure_stage,
):
    module = backend()
    output = tmp_path / "report.pdf"
    output.write_bytes(b"previous completed PDF")
    attempts = []
    original = module.Canvas

    class FailingCanvas(original):
        def __init__(self, filename, *args, **kwargs):
            attempts.append(Path(filename))
            super().__init__(filename, *args, **kwargs)

        def line(self, *args, **kwargs):
            if failure_stage == "draw":
                Path(self._filename).write_bytes(b"partial drawing")
                raise OSError("injected draw failure")
            return super().line(*args, **kwargs)

        def save(self):
            if failure_stage == "save":
                Path(self._filename).write_bytes(b"partial PDF")
                raise OSError("injected save failure")
            return super().save()

    monkeypatch.setattr(module, "Canvas", FailingCanvas)
    if failure_stage == "replace":
        import os

        def fail_replace(source, destination):
            raise OSError("injected replace failure")

        monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        module.render_pdf([ScenePage(A4, (Line(60, 80, 90, 80),))], output, fonts)
    assert output.read_bytes() == b"previous completed PDF"
    assert attempts[0].parent == output.parent
    assert attempts[0] != output
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("command", [
    Text(0.01, 90, "j", TextStyle()),
    Text(60, 840.5, "g", TextStyle()),
])
def test_real_glyph_ink_overhang_is_rejected_before_replacing_output(fonts, tmp_path, command):
    output = tmp_path / "report.pdf"
    output.write_bytes(b"previous completed PDF")
    with pytest.raises(LayoutOverflowError, match="Text bounds"):
        backend().render_pdf([ScenePage(A4, (command,))], output, fonts)
    assert output.read_bytes() == b"previous completed PDF"
    assert list(tmp_path.iterdir()) == [output]


def test_missing_glyph_diagnostic_identifies_page_command_and_keeps_cause(fonts, tmp_path):
    output = tmp_path / "report.pdf"
    output.write_bytes(b"previous completed PDF")
    pages = [ScenePage(A4), ScenePage(A3, (Text(60, 90, "\U0010ffff", TextStyle()),))]
    with pytest.raises(FontError, match="page\\[2\\].commands\\[0\\].*U\\+10FFFF") as caught:
        backend().render_pdf(pages, output, fonts)
    assert isinstance(caught.value.__cause__, FontError)
    assert output.read_bytes() == b"previous completed PDF"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("turns,direction", [(1, (0, -1)), (2, (-1, 0)), (3, (0, 1))])
def test_rotated_text_is_native_size_tracking_and_state_isolation(fonts, tmp_path, turns, direction):
    assert "quarter_turns" in Text.__dataclass_fields__
    output = tmp_path / "rotated.pdf"
    style = TextStyle(tracking=0.5)
    backend().render_pdf([ScenePage(A4, (
        Text(200, 300, "日本語", style, quarter_turns=turns),
        Text(60, 400, "か\u3099Ａ", TextStyle()),
    ))], output, fonts)
    with pymupdf.open(output) as pdf:
        page = pdf[0]
        assert page.rotation == 0 and (page.rect.width, page.rect.height) == (595, 842)
        lines = [line for block in page.get_text("rawdict")["blocks"] for line in block.get("lines", [])]
        assert len(lines) == 2
        assert lines[0]["dir"] == pytest.approx(direction)
        assert lines[1]["dir"] == pytest.approx((1, 0))
        run = lines[0]["spans"][0]
        assert run["size"] == pytest.approx(10)
        assert "".join(c["c"] for c in run["chars"]) == "日本語"
        for index, char in enumerate(run["chars"]):
            assert char["origin"] == pytest.approx((200 + index * 10.5 * direction[0],
                                                    300 + index * 10.5 * direction[1]), abs=0.001)
            axis_width = char["bbox"][2] - char["bbox"][0] if direction[0] else char["bbox"][3] - char["bbox"][1]
            assert axis_width == pytest.approx(10, abs=0.001)
        assert "がＡ" in page.get_text()


@pytest.mark.parametrize("failure", ["ink", "glyph", "direction"])
def test_rotated_text_preflight_preserves_existing_pdf(fonts, tmp_path, monkeypatch, failure):
    assert "quarter_turns" in Text.__dataclass_fields__
    output = tmp_path / "existing.pdf"
    output.write_bytes(b"previous completed PDF")
    command = Text(20, 30, "j", TextStyle(), quarter_turns=1)
    if failure == "ink":
        command = Text(0.01, 30, "j", TextStyle(), quarter_turns=1)
    elif failure == "glyph":
        command = Text(20, 30, "\U0010ffff", TextStyle(), quarter_turns=1)
    else:
        object.__setattr__(command, "quarter_turns", 4)
    monkeypatch.setattr(backend(), "Canvas", lambda *args, **kwargs: pytest.fail("Canvas before validation"))
    error = {"ink": LayoutOverflowError, "glyph": FontError, "direction": ValueError}[failure]
    with pytest.raises(error):
        backend().render_pdf([ScenePage(A4, (command,))], output, fonts)
    assert output.read_bytes() == b"previous completed PDF"
    assert list(tmp_path.iterdir()) == [output]


def test_dash_patterns_fills_and_circles_render_as_native_vector_paint(fonts, tmp_path):
    from gridlayoutpdf.scene import Circle

    output = tmp_path / "paint.pdf"
    page = ScenePage(A4, (
        Line(60, 80, 100, 80, width=.35, dash=(2, 2)),
        Polyline((Point(60, 90), Point(80, 90), Point(80, 110)), width=.5, dash=(3, 1)),
        Rectangle(120, 80, 30, 20, fill=(1, 1, 1), stroke=False),
        Rectangle(160, 80, 30, 20, stroke_width=.75, fill=(0, 0, 0)),
        Circle(220, 90, 1.7, fill=(0, 0, 0), stroke=False),
        Circle(240, 90, 5, stroke_width=.5),
        Line(60, 120, 100, 120),
    ))
    backend().render_pdf([page], output, fonts)
    with pymupdf.open(output) as pdf:
        drawings = pdf[0].get_drawings()
        assert [drawing["type"] for drawing in drawings] == ["s", "s", "f", "fs", "f", "s", "s"]
        assert [drawing["dashes"] for drawing in (drawings[0], drawings[1], drawings[6])] == [
            "[ 2 2 ] 0", "[ 3 1 ] 0", "[] 0"]
        assert drawings[2]["fill"] == (1, 1, 1) and tuple(drawings[2]["rect"]) == pytest.approx((120, 80, 150, 100))
        assert drawings[3]["fill"] == (0, 0, 0) and drawings[3]["color"] == (0, 0, 0)
        assert tuple(drawings[4]["rect"]) == pytest.approx((218.3, 88.3, 221.7, 91.7), abs=.01)
        assert drawings[4]["fill"] == (0, 0, 0)
        assert tuple(drawings[5]["rect"]) == pytest.approx((235, 85, 245, 95), abs=.01)
        assert drawings[5]["fill"] is None


def test_undashed_unfilled_vectors_keep_their_existing_pdf_operators(fonts, tmp_path):
    output = tmp_path / "plain.pdf"
    page = ScenePage(A4, (Line(60, 80, 100, 80), Rectangle(120, 80, 30, 20)))
    backend().render_pdf([page], output, fonts, invariant=True)
    with pymupdf.open(output) as pdf:
        stream = pdf[0].read_contents().decode("latin-1")
    assert " rg" not in stream and " f\n" not in stream and "[] 0 d" in stream


def test_render_without_fonts_uses_the_shared_default_registry(fonts, tmp_path):
    pages = [ScenePage(A4, (Text(60, 80, "再現 Same", TextStyle()),))]
    explicit, implicit = tmp_path / "explicit.pdf", tmp_path / "implicit.pdf"
    backend().render_pdf(pages, explicit, fonts, invariant=True)
    backend().render_pdf(pages, implicit, invariant=True)
    assert explicit.read_bytes() == implicit.read_bytes()
