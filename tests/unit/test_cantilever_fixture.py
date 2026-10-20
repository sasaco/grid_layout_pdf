"""The reproduction fixture fails closed before any accepted output changes."""

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
        builder.layout_blocks(fonts, [(16, [Spacer(builder.SOURCE_PROFILE.grid.rows + 1)])])
    assert error.value.needed > error.value.available


def test_fixed_page_guard_rejects_same_count_page_swaps(fonts):
    builder = module("builder")
    from gridlayoutpdf import Paragraph
    pages = builder.layout_blocks(fonts, [(16, [Paragraph("first")]), (17, [Paragraph("second")])])
    with pytest.raises(LayoutOverflowError, match="原本再現できず"):
        builder.guard_fixed_pages(tuple(reversed(pages)), (16, 17))


def _table_page(fonts, number, table_id):
    """The builder's page inputs and the authored table block of one original page."""
    builder = module("builder")
    data = json.loads((FIXTURE / f"pages/p{number:02}.json").read_text(encoding="utf-8"))
    layout = {page["source_page"]: page for page in builder.source_layout()["pages"]}[number]
    leaves = tuple(builder._leaves({"type": "stack", "children": data["blocks"]}))
    page = builder._Page(number, fonts, {block["id"]: block for block in layout["blocks"]}, leaves)
    return page, next(block for block in leaves if block["id"] == table_id)


def _cells(table):
    return [cell for row in table.rows for cell in row]


def test_table_cell_lines_advance_one_grid_row_and_clear_their_rules(fonts):
    """FR-027: each cell line takes one grid row; the text keeps every rule it can meet clear."""
    builder = module("builder")
    page, data = _table_page(fonts, 1, "p01-dead-loads")
    table = builder._table(data, page)
    geometry = page.geometry["p01-dead-loads"]
    horizontal = [builder.rule_thickness(width) for width in geometry["horizontal_rules"]]
    vertical = [builder.rule_thickness(width) for width in geometry["vertical_rules"]]
    cell = _cells(table)[0]
    first = cell.content
    assert first.line_advance == builder.SOURCE_PROFILE.grid.pitch_y
    # A one-line cell stays centred in its whole cell, padded by its rules.
    assert len(first.lines) == 1 and cell.valign == "middle" and first.first_baseline is None
    assert first.inner_padding.top == horizontal[0] and first.inner_padding.bottom == horizontal[1]
    assert first.inner_padding.left == pytest.approx(builder._CELL_PADDING + vertical[0])
    # A multi-line cell sets each line in its own grid row (FR-027): top-aligned at a first baseline
    # that keeps the glyphs inside the row and clear of the cell's rules; no top or bottom padding.
    multi = next(cell for cell in _cells(table) if len(cell.content.lines) > 1)
    content = multi.content
    assert multi.valign == "top" and content.inner_padding.top == content.inner_padding.bottom == 0
    box = builder.Row(content.lines[0], gap=0).measure(fonts, content.style)
    pitch = builder.SOURCE_PROFILE.grid.pitch_y
    offset = content.first_baseline % pitch
    assert box.ascent <= offset and offset + box.descent <= pitch
    assert all(isinstance(span, int) and span >= 1 for span in (*table.columns, *table.row_heights))


def test_table_columns_follow_the_original_boundaries_and_widen_only_for_content():
    builder = module("builder")
    # Cumulative boundaries: 3 x 24 pt on a 16 pt grid is 4.5 columns, not 3 x 2 = 6.
    assert builder._grid_spans((24, 24, 24), (0, 0, 0), 16) == (2, 1, 2)
    # A span its content needs is widened; later boundaries move with it.
    assert builder._grid_spans((16, 16, 16), (0, 40, 0), 16) == (1, 3, 1)
    assert builder._grid_spans((1, 1), (0, 0), 16) == (1, 1)


def test_rows_the_original_made_equal_stay_equal_under_a_merged_heading(fonts):
    """p21: 「安全性（破壊）」 (7 lines) spans four 26.52 pt rows; they are 2 grid rows each, not 2/2/2/4."""
    builder = module("builder")
    page, data = _table_page(fonts, 21, "p21-origin-table")
    table = builder._table(data, page)
    assert page.geometry["p21-origin-table"]["row_heights"][1:5] == [26.52] * 4
    assert table.row_heights == (2, 2, 2, 2, 2, 3)
    # A merged cell that its rows cannot hold still widens its last row.
    assert builder._grid_spans((10,), (0,), 16) == (1,)


def test_empty_table_cells_reserve_their_frame_without_printing_text(fonts):
    from gridlayoutpdf import LayoutContext, Text, measure_block
    builder = module("builder")
    page, data = _table_page(fonts, 1, "p01-dead-loads")
    empty = [cell for cell in _cells(builder._table(data, page))
             if all(getattr(line, "text", None) == "" for line in cell.content.lines)]
    assert empty, "p01 has empty cells"
    context = LayoutContext(fonts, builder.SOURCE_PROFILE, builder.SOURCE_STYLE)
    for cell in empty:
        measured = measure_block(cell.content, context, 40)
        assert measured.width > 0
        assert not any(isinstance(command, Text) and command.text.strip() for command in measured.commands)


def test_rotated_table_cells_use_the_swapped_page_grid(fonts):
    builder = module("builder")
    page, data = _table_page(fonts, 30, "p30-combinations-md")
    turned = builder._table(data, page)
    grid = builder.ROTATED_PROFILE.grid
    assert turned.local_grid.pitch_x == grid.pitch_y and turned.local_grid.pitch_y == grid.pitch_x
    assert (turned.local_grid.columns, turned.local_grid.rows) == (grid.rows, grid.columns)
    assert all(cell.content.line_advance == grid.pitch_x for cell in _cells(turned.block))


def test_header_line_breaks_follow_the_original_when_the_manuscript_joins_them():
    builder = module("builder")
    geometry = {"lines": [{"text": "せん断"}, {"text": "力"}, {"text": "Vd(kN)"}]}
    assert builder._cell_source_lines(("せん断力", "Vd(kN)"), geometry, "c") == ("せん断", "力", "Vd(kN)")
    assert builder._cell_source_lines(("A", "B"), {"lines": [{"text": "A"}, {"text": "B"}]}, "c") == ("A", "B")
    with pytest.raises(ValueError, match="differs"):
        builder._cell_source_lines(("せん断カ", "Vd(kN)"), geometry, "c")


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


def test_all_five_complete_proofs_fit_one_original_page_each(fonts):
    builder = module("builder")
    selection = builder.PROOF_PAGES
    assert selection == (16, 17, 26, 30, 36)
    pages = builder.layout_report(fonts, source_pages=selection)
    assert len(pages) == len(selection)
    assert [page.metadata["placements"][0]["block_id"] for page in pages] == [f"p{n:02}" for n in selection]
    assert all(page.profile.width == 595 and page.profile.height == 842 for page in pages)
    assert all(page.metadata["placements"][0]["rows"] <= page.profile.grid.rows for page in pages)
    assert [page.profile for page in pages] == [builder.SOURCE_PROFILE] * 3 + [builder.ROTATED_PROFILE] * 2


def test_actual_proof_overflow_is_an_error_without_pagination(fonts, tmp_path):
    source = json.loads((FIXTURE / "pages/p16.json").read_text(encoding="utf-8"))
    source["blocks"].append({"id": "p16-intentional-overflow", "type": "spacer", "rows": 3})
    (tmp_path / "p16.json").write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(LayoutOverflowError, match="原本再現できず.*p16"):
        module("builder").layout_report(fonts, source_pages=(16,), pages_root=tmp_path)


def test_snow_subscript_and_next_cell_line_have_separate_ink(fonts):
    """The rotated tables' 1.0S30 / 703.13 cell: a library Script line and the next line at 10.8 pt."""
    from gridlayoutpdf import CellLines, GridSpec, LayoutContext, PageProfile, Rect, Text, TextStyle, measure_block
    builder = module("builder")
    grid = builder.ROTATED_PROFILE.grid
    local = GridSpec(0, 0, grid.pitch_y, grid.pitch_x, grid.rows, grid.columns)
    context = LayoutContext(fonts, PageProfile("local", local.columns * local.pitch_x, local.rows * local.pitch_y, local),
                            builder.SOURCE_STYLE)
    cell = CellLines((builder.math_node({"type": "row", "items": ["1.0", {"type": "script", "base": "S", "sub": "30"}]}),
                      builder.math_node("703.13")), style=TextStyle("MS Mincho", 10), line_advance=local.pitch_y)
    result = measure_block(cell, context, 50)
    assert result.rows == 2
    texts = [command for command in result.commands if isinstance(command, Text)]
    def ink(command):
        bounds = fonts.measure(command.text, command.style).ink_bounds
        return Rect(bounds.x + command.x, bounds.y + command.y, bounds.width, bounds.height)
    upper = [ink(command) for command in texts[:-1]]
    lower = ink(texts[-1])
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


def test_row_placement_centres_lines_by_whole_rows_and_clears_the_rules():
    """builder._row_placement: rows nearest the middle (ties upward), one row off where a rule
    leaves no room, the offset in the middle of the room, an error where nothing fits."""
    from types import SimpleNamespace
    from gridlayoutpdf import LayoutOverflowError
    builder = module("builder")
    box = SimpleNamespace(ascent=8.594, descent=1.406)  # a 10 pt MS Mincho line
    # One line in two rows: the upper row (a tie), its glyphs in the middle of the room.
    start, offset = builder._row_placement(1, 2, 10.8, [box], top=.25, bottom=.25, where="t")
    assert start == 0 and offset == pytest.approx((8.594 + .26 + 10.8 - 1.406) / 2)
    # One line in three rows: the middle row, clear of no rule.
    assert builder._row_placement(1, 3, 10.8, [box], top=1.0, bottom=1.0, where="t") == (1, pytest.approx((8.594 + 10.8 - 1.406) / 2))
    # A medium frame rule above leaves no room in the first row: the line moves down one row.
    assert builder._row_placement(1, 2, 10.8, [box], top=1.0, bottom=.25, where="t")[0] == 1
    # Two lines in three rows (the case builder._table uses it for): the upper pair (a tie).
    assert builder._row_placement(2, 3, 10.8, [box, box], top=.25, bottom=.25, where="t")[0] == 0
    # Two lines in three rows under a medium frame rule: one row down.
    assert builder._row_placement(2, 3, 10.8, [box, box], top=1.0, bottom=.25, where="t")[0] == 1
    with pytest.raises(LayoutOverflowError, match="do not fit"):
        builder._row_placement(1, 1, 10.8, [box], top=1.0, bottom=1.0, where="t")
    with pytest.raises(LayoutOverflowError, match="do not fit"):
        builder._row_placement(3, 2, 10.8, [box] * 3, top=0.0, bottom=0.0, where="t")
