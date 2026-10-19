"""The reproduction fixture fails closed before any accepted output changes."""

from dataclasses import replace
import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from gridlayoutpdf import LayoutOverflowError, Spacer


ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests/fixtures/cantilever_p01_37"


def module(name):
    path = FIXTURE / f"{name}.py"
    assert path.is_file(), f"missing cantilever fixture {name}"
    key = f"cantilever_fixture_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        result = importlib.util.module_from_spec(spec)
        sys.modules[key] = result
        spec.loader.exec_module(result)
    return sys.modules[key]


@pytest.fixture
def fonts():
    return module("builder").fixture_fonts()


def test_manifest_registers_all_37_pages_without_claiming_unfinished_data():
    manifest = module("builder").load_manifest()
    assert [page["source_page"] for page in manifest["pages"]] == list(range(1, 38))
    assert manifest["source"]["sha256"] == "e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e"
    assert manifest["page_numbers"] == "omitted"


def test_missing_input_page_fails_before_layout(fonts, tmp_path):
    with pytest.raises(ValueError, match="p01.*missing"):
        module("builder").build_document(fonts, source_pages=(1,), pages_root=tmp_path)


def test_duplicate_or_invalid_page_selection_is_rejected(fonts):
    builder = module("builder")
    for pages in ((16, 16), (0,), (38,), (True,), (), (17, 16)):
        with pytest.raises(ValueError):
            builder.build_document(fonts, source_pages=pages)


def test_fixed_page_wrapper_reports_original_page_on_overflow(fonts):
    builder = module("builder")
    with pytest.raises(LayoutOverflowError, match="原本再現できず.*p16") as error:
        builder.layout_blocks(fonts, [(16, [Spacer(48)])])
    assert error.value.needed > error.value.available


def test_fixed_page_guard_rejects_same_count_page_swaps(fonts):
    builder = module("builder")
    from gridlayoutpdf import Paragraph
    pages = builder.layout_blocks(fonts, [(16, [Paragraph("first")]), (17, [Paragraph("second")])])
    with pytest.raises(LayoutOverflowError, match="原本再現できず"):
        builder.guard_fixed_pages(tuple(reversed(pages)), (16, 17))


def test_compact_cell_preserves_font_size_and_rejects_overwide_content(fonts):
    from gridlayoutpdf import A4_PORTRAIT_REFERENCE, GridSpec, LayoutContext, PageProfile, ReportStyle, Text, TextStyle, measure_block
    builder = module("builder")
    local = PageProfile("test-local", 700, 480, GridSpec(0, 0, .12, .12, 5800, 4000))
    context = LayoutContext(fonts, local, module("builder").SOURCE_STYLE)
    cell = builder.CompactCell(("1.35", "3679.84"), style=TextStyle("MS Mincho", size=10), line_advance=10.8)
    measured = measure_block(cell, context, 48)
    texts = [command for command in measured.commands if isinstance(command, Text)]
    assert [command.text for command in texts] == ["1.35", "3679.84"]
    assert {command.style.size for command in texts} == {10}
    assert texts[1].y - texts[0].y == pytest.approx(10.8)
    with pytest.raises(LayoutOverflowError):
        measure_block(cell, context, 10)


def test_compact_empty_cells_reserve_width_without_printing_fake_zero(fonts):
    from gridlayoutpdf import A4_PORTRAIT_REFERENCE, LayoutContext, ReportStyle, measure_block
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, module("builder").SOURCE_STYLE)
    for lines in ((), ("",)):
        result = measure_block(module("builder").CompactCell(lines), context, 30)
        assert result.width > 0
        assert not any(getattr(command, "text", "") for command in result.commands)


def test_compact_cell_keeps_source_line_sizes_and_horizontal_clearance(fonts):
    from gridlayoutpdf import GridSpec, LayoutContext, PageProfile, ReportStyle, Text, measure_block
    context = LayoutContext(fonts, PageProfile("local", 100, 100, GridSpec(0, 0, .12, .12, 800, 800)), module("builder").SOURCE_STYLE)
    builder = module("builder")
    plain = builder.CompactCell(("ABC", "short"), line_sizes=(10, 8))
    padded = replace(plain, inline_padding=.6)
    first, second = (measure_block(cell, context, 50) for cell in (plain, padded))
    assert second.width - first.width == pytest.approx(1.2)
    assert second.height == first.height
    text = [command for command in second.commands if isinstance(command, Text)]
    assert [command.style.size for command in text] == [10, 8]
    assert [new.x - old.x for new, old in zip(second.commands, first.commands)] == pytest.approx([.6, .6])


def test_compact_adapter_exposes_public_single_rounding_and_edge_padding(fonts):
    from gridlayoutpdf import A4_PORTRAIT_REFERENCE, LayoutContext, ReportStyle, measure_block
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, module("builder").SOURCE_STYLE)
    cell = module("builder").CompactCell(("1.35", "3679.84"), line_sizes=(10, 8),
                                         line_advance=12.8, inline_padding=.6, min_height=40)
    measured = measure_block(cell, context, 60)
    metadata = measured.parts[0].metadata
    assert metadata.get("height_rounding") == "single"
    assert metadata["minimum_height_pt"] == 40
    assert dict(metadata["inner_padding_pt"]) == {"top": 0, "right": .6, "bottom": 0, "left": .6}
    assert metadata["baselines_pt"][1] - metadata["baselines_pt"][0] == pytest.approx(12.8)


def test_compact_adapter_rejects_touching_explicit_lines_instead_of_moving_them(fonts):
    from gridlayoutpdf import A4_PORTRAIT_REFERENCE, LayoutContext, ReportStyle, measure_block
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, module("builder").SOURCE_STYLE)
    cell = module("builder").CompactCell(("888", "888"), line_advance=1, block_id="touching")
    with pytest.raises(LayoutOverflowError, match="touching.*line 2.*line 1"):
        measure_block(cell, context, 40)


def test_guard_catches_wrong_page_descendant_despite_correct_wrapper(fonts):
    from gridlayoutpdf import Paragraph
    with pytest.raises(LayoutOverflowError, match="p16.*p17-content"):
        module("builder").layout_blocks(fonts, [(16, [Paragraph("wrong page", block_id="p17-content")])])


def test_guard_catches_declared_block_omission_before_rendering(fonts):
    from gridlayoutpdf import Paragraph
    builder = module("builder")
    pages = builder.layout_blocks(fonts, [(16, [Paragraph("present", block_id="p16-present")])])
    with pytest.raises(LayoutOverflowError, match="missing blocks.*p16-omitted"):
        builder.guard_fixed_pages(pages, (16,), {16: {"p16-present", "p16-omitted"}})


# p30 is deferred to FR-027 Step 9 (2026-10-20 user decision c); the other proofs still run.
@pytest.mark.parametrize("selection", module("deferred").selections((16, 17, 26, 30, 36)))
def test_all_five_complete_proofs_fit_one_original_page_each(fonts, selection):
    builder = module("builder")
    assert builder.PROOF_PAGES == (16, 17, 26, 30, 36)
    pages = builder.layout_report(fonts, source_pages=selection)
    assert len(pages) == len(selection)
    assert [page.metadata["placements"][0]["block_id"] for page in pages] == [f"p{n:02}" for n in selection]
    assert all(page.profile.width == 595 and page.profile.height == 842 for page in pages)
    assert all(page.metadata["placements"][0]["rows"] <= page.profile.grid.rows for page in pages)
    assert all(page.profile == builder.SOURCE_PROFILE for page in pages)


def test_actual_proof_overflow_is_an_error_without_pagination(fonts, tmp_path):
    source = json.loads((FIXTURE / "pages/p16.json").read_text(encoding="utf-8"))
    source["blocks"].append({"id": "p16-intentional-overflow", "type": "spacer", "rows": 3})
    (tmp_path / "p16.json").write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(LayoutOverflowError, match="原本再現できず.*p16"):
        module("builder").layout_report(fonts, source_pages=(16,), pages_root=tmp_path)


def test_snow_subscript_and_next_cell_line_have_separate_ink(fonts):
    from gridlayoutpdf import GridSpec, LayoutContext, PageProfile, Rect, ReportStyle, measure_block
    context = LayoutContext(fonts, PageProfile("local", 100, 100, GridSpec(0, 0, .12, .12, 800, 800)), module("builder").SOURCE_STYLE)
    cell = module("builder").CompactCell((
        {"type": "row", "items": ["1.0", {"type": "script", "base": "S", "sub": "30"}]},
        "703.13"), line_advance=12.8)
    result = measure_block(cell, context, 50)
    # command_bounds intentionally includes typographic reserve; the question
    # here is whether the actual visible outlines intersect between baselines.
    def ink(command):
        bounds = fonts.measure(command.text, command.style).ink_bounds
        return Rect(bounds.x + command.x, bounds.y + command.y, bounds.width, bounds.height)
    upper = [ink(command) for command in result.commands[:-1]]
    lower = ink(result.commands[-1])
    assert max(rect.bottom for rect in upper) < lower.y


def test_source_figure_preserves_physical_size_and_normalized_pixels(fonts, tmp_path):
    from io import BytesIO
    from PIL import Image
    from gridlayoutpdf import A4_PORTRAIT_REFERENCE, LayoutContext, RasterImage, ReportStyle, measure_block
    asset = tmp_path / "figure.png"
    Image.new("RGB", (240, 80), "white").save(asset)
    content = asset.read_bytes()
    metadata = {"id": "test-figure", "file": asset.name, "source_page": 1,
                "source_bbox": [70, 100, 190, 140], "sha256": sha256(content).hexdigest(),
                "pixel_width": 240, "pixel_height": 80,
                "decoded_pixel_sha256": sha256(Image.new("RGB", (240, 80), "white").tobytes()).hexdigest()}
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, module("builder").SOURCE_STYLE)
    assert hasattr(module("builder"), "SourceFigure"), "source-sized figure block is not implemented"
    source = module("builder").SourceFigure(metadata, asset_root=tmp_path, block_id="p01-test-figure")
    measured = measure_block(source, context, 200)
    command, = measured.commands
    assert isinstance(command, RasterImage)
    assert (command.width, command.height) == (120, 40)
    assert measured.rows == 3
    assert sha256(Image.open(BytesIO(command.data)).convert("RGB").tobytes()).hexdigest() == metadata["decoded_pixel_sha256"]
    with pytest.raises(LayoutOverflowError):
        measure_block(source, context, 119)
    asset.write_bytes(b"modified")
    with pytest.raises(ValueError, match="hash"):
        measure_block(source, context, 200)


def test_source_figure_checks_measured_snapshot_after_asset_race(fonts, tmp_path, monkeypatch):
    from PIL import Image as PILImage
    from gridlayoutpdf import A4_PORTRAIT_REFERENCE, Image, LayoutContext, ReportStyle, measure_block
    asset = tmp_path / "figure.png"
    PILImage.new("RGB", (240, 80), "white").save(asset)
    metadata = {"id": "race", "file": asset.name, "source_page": 1,
                "source_bbox": [70, 100, 190, 140], "sha256": sha256(asset.read_bytes()).hexdigest(),
                "pixel_width": 240, "pixel_height": 80,
                "decoded_pixel_sha256": sha256(PILImage.new("RGB", (240, 80), "white").tobytes()).hexdigest()}
    snapshot = Image._snapshot
    calls = []
    def substitute(self):
        calls.append(self.path)
        PILImage.new("RGB", (240, 80), "black").save(asset)
        return snapshot(self)
    monkeypatch.setattr(Image, "_snapshot", substitute)
    source = module("builder").SourceFigure(metadata, asset_root=tmp_path, block_id="race")
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, module("builder").SOURCE_STYLE)
    with pytest.raises(ValueError, match="measured.*pixel hash"):
        measure_block(source, context, 200)
    assert calls == [asset]


def _bundle_test_environment(monkeypatch, fonts):
    from gridlayoutpdf import Paragraph
    builder, writer = module("builder"), module("render")
    monkeypatch.setattr(writer, "_input_hashes", lambda *args: {})
    monkeypatch.setattr(writer._sibling("verify"), "verify_scene_images", lambda *args, **kwargs: 0)
    monkeypatch.setattr(writer.builder, "layout_report", lambda registry, source_pages, **kwargs:
                        builder.layout_blocks(registry, [(n, [Paragraph(f"test page {n}", block_id=f"p{n:02}-test")])
                                                         for n in source_pages]))
    monkeypatch.setattr(writer, "_verify_pdf", lambda *args, **kwargs: {
        "source_pages": list(kwargs["source_pages"]),
        "complete_37_pages": tuple(kwargs["source_pages"]) == builder.SOURCE_PAGES,
        "variant": "grid" if kwargs.get("grid") else "normal", "verified_items": 37})
    def previews(directory, source_pages):
        target = directory / "previews"
        target.mkdir()
        for variant in ("normal", "grid"):
            for number in source_pages:
                (target / f"{variant}-p{number:02}.png").write_bytes(b"unit-test-preview")
    monkeypatch.setattr(writer, "_previews", previews)
    return writer


def _tree_hashes(path):
    return {str(file.relative_to(path)): sha256(file.read_bytes()).hexdigest()
            for file in path.rglob("*") if file.is_file()}


def _review(bundle):
    return {"reviewer": "unit-test-only", "reviewed_at": "2026-10-17T00:00:00+09:00",
            "artifacts": json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))["artifacts"],
            "result": "pass"}


def test_subset_bundle_never_becomes_current(tmp_path, monkeypatch, fonts):
    writer = _bundle_test_environment(monkeypatch, fonts)
    bundle = writer.prepare_bundle(tmp_path, fonts, source_pages=(16,))
    assert bundle.parent.name == ".staging"
    assert not (tmp_path / "current.json").exists()
    with pytest.raises(ValueError, match="37"):
        writer.activate_bundle(tmp_path, bundle, _review(bundle))
    assert not (tmp_path / "current.json").exists()


def test_scene_image_allowlist_is_checked_before_any_pdf_is_created(tmp_path, monkeypatch, fonts):
    writer = _bundle_test_environment(monkeypatch, fonts)
    called = []
    def reject(pages, *, source_pages, manifest):
        called.append(tuple(source_pages))
        raise ValueError("unapproved scene image")
    monkeypatch.setattr(writer._sibling("verify"), "verify_scene_images", reject)
    with pytest.raises(ValueError, match="unapproved scene image"):
        writer.prepare_bundle(tmp_path, fonts, source_pages=(16,))
    assert called == [(16,)]
    assert not list(tmp_path.rglob("*.pdf"))


@pytest.mark.parametrize("stage", ["grid", "json", "previews", "verify", "pointer"])
def test_every_late_failure_preserves_previous_accepted_bundle(tmp_path, monkeypatch, fonts, stage):
    writer = _bundle_test_environment(monkeypatch, fonts)
    first = writer.prepare_bundle(tmp_path, fonts)
    accepted = writer.activate_bundle(tmp_path, first, _review(first))
    old_pointer = (tmp_path / "current.json").read_bytes()
    old_hashes = _tree_hashes(accepted)
    def fail(*args, **kwargs):
        raise OSError("injected late failure")
    if stage == "grid":
        original = writer.render_pdf
        def grid_fail(*args, **kwargs):
            if kwargs.get("debug_grid"):
                fail()
            return original(*args, **kwargs)
        monkeypatch.setattr(writer, "render_pdf", grid_fail)
    else:
        monkeypatch.setattr(writer, {"json": "_write_json", "previews": "_previews",
                                    "verify": "_verify_pdf", "pointer": "_commit_pointer"}[stage], fail)
    with pytest.raises(OSError, match="injected"):
        second = writer.prepare_bundle(tmp_path, fonts)
        writer.activate_bundle(tmp_path, second, _review(second))
    assert (tmp_path / "current.json").read_bytes() == old_pointer
    assert _tree_hashes(accepted) == old_hashes
    assert writer.resolve_current(tmp_path) == accepted


def test_first_failure_creates_no_current_and_unreviewed_or_changed_bundle_cannot_activate(tmp_path, monkeypatch, fonts):
    writer = _bundle_test_environment(monkeypatch, fonts)
    original = writer._verify_pdf
    monkeypatch.setattr(writer, "_verify_pdf", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad extraction")))
    with pytest.raises(ValueError, match="bad extraction"):
        writer.prepare_bundle(tmp_path, fonts)
    assert not (tmp_path / "current.json").exists()
    monkeypatch.setattr(writer, "_verify_pdf", original)
    bundle = writer.prepare_bundle(tmp_path, fonts)
    with pytest.raises(ValueError, match="review"):
        writer.activate_bundle(tmp_path, bundle, {})
    review = _review(bundle)
    (bundle / "normal.pdf").write_bytes(b"changed after review")
    with pytest.raises(ValueError, match="hash"):
        writer.activate_bundle(tmp_path, bundle, review)
    assert not (tmp_path / "current.json").exists()


def test_subset_manifest_cannot_be_relabelled_as_a_complete_bundle(tmp_path, monkeypatch, fonts):
    writer = _bundle_test_environment(monkeypatch, fonts)
    bundle = writer.prepare_bundle(tmp_path, fonts, source_pages=(16,))
    path = bundle / "bundle.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["source_pages"] = list(range(1, 38))
    for variant in ("normal", "grid"):
        for number in range(1, 38):
            relative = f"previews/{variant}-p{number:02}.png"
            (bundle / relative).write_bytes(b"unit-test-preview")
            manifest["artifacts"][relative] = sha256(b"unit-test-preview").hexdigest()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="content verification"):
        writer.activate_bundle(tmp_path, bundle, _review(bundle))
    assert not (tmp_path / "current.json").exists()


def test_activation_independently_reverifies_both_pdfs(tmp_path, monkeypatch, fonts):
    writer = _bundle_test_environment(monkeypatch, fonts)
    bundle = writer.prepare_bundle(tmp_path, fonts)
    seen = []
    def reject(path, **kwargs):
        seen.append(Path(path).name)
        if kwargs.get("grid"):
            raise ValueError("independent final check rejected grid")
    monkeypatch.setattr(writer, "_verify_pdf", reject)
    with pytest.raises(ValueError, match="independent final check"):
        writer.activate_bundle(tmp_path, bundle, _review(bundle))
    assert seen == ["normal.pdf", "grid.pdf"]
    assert not (tmp_path / "current.json").exists()


@pytest.mark.parametrize("number", module("deferred").DEFERRED_PAGES)
def test_deferred_pages_still_stop_for_the_recorded_header_clearance(fonts, number):
    """The strict xfails defer exactly this failure; a changed reason or a fixed page fails here."""
    table = {30: "md", 31: "md", 32: "vd", 33: "vd", 34: "mt", 35: "mt"}[number]
    with pytest.raises(LayoutOverflowError, match=(
            rf"原本再現できず: .*p{number}-combinations-{table}-r0-cell1: "
            rf"source glyph ink clearance exceeds 0\.05 pt$")):
        module("builder").layout_report(fonts, source_pages=(number,))
