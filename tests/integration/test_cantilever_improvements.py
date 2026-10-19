"""Public API proofs and preserved original appearance after fixture migration."""

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from PIL import Image as PILImage

from gridlayoutpdf import (
    Cell, CellLines, Document, GridSpec, Insets, LayoutContext, Line, PageBreak,
    PageProfile, QuarterTurn, RasterImage, ReportStyle, Script, Table, Text,
    TextStyle, layout_trace, measure_block, render_pdf,
)
from gridlayoutpdf.bounds import command_bounds


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/cantilever_p01_37"


def _module(name):
    key = f"cantilever_fixture_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, FIXTURE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def _authored_tables(number):
    record = json.loads((FIXTURE / f"pages/p{number:02}.json").read_text(encoding="utf-8"))
    return [block for block in record["blocks"] if block["type"] == "table"]


def _local_context(fonts):
    return LayoutContext(fonts, PageProfile("public-cells", 800, 800,
                         GridSpec(0, 0, .12, .12, 6600, 6600)), _module("builder").SOURCE_STYLE)


def _public_table(data, *, local):
    """Keep source values/styles; explicitly reserve stroke clearance inside."""
    builder = _module("builder")
    original = builder.build_block(data)
    rotated = isinstance(original, QuarterTurn)
    table = original.block if rotated else original
    rows = []
    for row in table.rows:
        converted = []
        for cell in row:
            content = cell.content
            styles = (tuple(replace(content.style, size=size) for size in content.line_sizes)
                      if content.line_sizes else None)
            lines = CellLines(tuple(builder.math_node(line) for line in content.lines),
                              style=content.style, line_styles=styles,
                              line_advance=content.line_advance, min_height=content.min_height,
                              inner_padding=Insets(top=1.01, bottom=1.01, left=content.inline_padding,
                                                   right=content.inline_padding),
                              align="center", block_id=content.block_id)
            converted.append(replace(cell, content=lines, padding=0))
        rows.append(tuple(converted))
    columns = table.columns if rotated or not local else tuple(value * 134 for value in table.columns)
    return replace(table, columns=columns, rows=tuple(rows), split=False)


@pytest.mark.parametrize("number,count", [(1, 70), (26, 186), (30, 267), (36, 306)])
def test_all_authored_table_cells_use_single_rounding_and_explicit_clearance(number, count):
    builder = _module("builder")
    fonts = builder.fixture_fonts()
    context = _local_context(fonts)
    seen = []
    for data in _authored_tables(number):
        # Existing manuscript parameters remain usable through the thin adapter.
        original = measure_block(builder.build_block(data),
                                 LayoutContext(fonts, builder.SOURCE_PROFILE, builder.SOURCE_STYLE), 498.48)
        assert original.commands
        measured = measure_block(_public_table(data, local=True), context, 780)
        assert len(measured.parts) == 1 and not measured.break_after
        for cell in measured.parts[0].metadata["cells"]:
            seen.append(cell["cell_id"])
            assert all(value == 0 for value in cell["padding_pt"].values())
            content = cell["content"]
            assert content["row_pitch"] == .12
            metadata = content["parts"][0]["metadata"]
            assert metadata["height_rounding"] == "single"
            assert metadata["inner_padding_pt"]["top"] == 1.01
            assert metadata["inner_padding_pt"]["bottom"] == 1.01
            baselines = metadata["baselines_pt"]
            assert all(b - a == pytest.approx(metadata["line_advance"])
                       for a, b in zip(baselines, baselines[1:]))
    assert len(seen) == len(set(seen)) == count


def test_all_16_source_figures_preserve_physical_snapshot_and_provenance():
    builder = _module("builder")
    context = LayoutContext(builder.fixture_fonts(), builder.SOURCE_PROFILE, builder.SOURCE_STYLE)
    assets = builder.load_manifest()["figures"]
    assert len(assets) == 16
    for asset in assets:
        measured = measure_block(builder.SourceFigure(asset, block_id=asset["id"]), context, 500)
        command, = measured.commands
        assert isinstance(command, RasterImage)
        x0, y0, x1, y1 = asset["source_bbox"]
        assert (command.x, command.y, command.width, command.height) == (0, 0, x1-x0, y1-y0)
        assert measured.width == command.width
        assert sha256(command.data).hexdigest() == asset["normalized_byte_sha256"]
        with PILImage.open(BytesIO(command.data)) as image:
            assert image.size == (asset["pixel_width"], asset["pixel_height"])
            assert sha256(image.convert("RGB").tobytes()).hexdigest() == asset["decoded_pixel_sha256"]
        assert measured.parts[0].metadata["figure_id"] == asset["id"]
        assert measured.parts[0].metadata["source_page"] == asset["source_page"]


# p30 is deferred to FR-027 Step 9 (2026-10-20 user decision c); p1, p26, p36 still run.
@pytest.mark.parametrize("selected", _module("deferred").selections((1, 26, 30, 36)))
@pytest.mark.parametrize("grid", [False, True])
def test_migrated_fixed_pages_preserve_original_content_and_appearance(tmp_path, grid, selected):
    builder = _module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=selected)
    assert len(pages) == len(selected)
    # The accepted PageFrame reserves all 48 available rows; actual content
    # remains inside the 47-row envelope. Do not conflate those two quantities.
    assert all(max(command_bounds(command, fonts).bottom for command in page.commands)
               <= page.profile.grid.origin_y + 47 * page.profile.grid.pitch_y for page in pages)
    trace = layout_trace(pages, fonts)
    output = tmp_path / "fixed-pages.pdf"
    render_pdf(pages, output, fonts, debug_grid=grid)
    content = _module("verify").verify_pdf(output, source_pages=selected, trace=trace,
                                          manifest=builder.load_manifest(), grid=grid)
    assert content["source_order"]["source_pages"] == list(selected)
    # Only the listed p36 operator positions are deferred to Step 9 (FR-027).
    appearance = _module("verify_appearance").verify_appearance(
        output, source_pages=selected, trace=trace, deferred=_module("deferred").DEFERRED_DIFFERENCES)
    assert appearance["error_count"] == 0
    assert appearance["deferred_count"] == 9


def _nested_script_table():
    content = CellLines((Script("S", subscript="30", scale=.6, subscript_drop=4),
                         Script("x", superscript=Script("2", superscript="n"),
                                scale=.6, superscript_rise=8)),
                        style=TextStyle("MS Mincho", size=10), line_advance=24,
                        inner_padding=Insets(1, 2, 1, 2), block_id="public-script-lines")
    table = Table((20,), ((Cell(content, padding=Insets(1, 2, 1, 2)),),),
                  row_heights=(12,), split=False, block_id="public-script-table")
    return QuarterTurn(table, turns=1, local_grid=GridSpec(0, 0, 5, 5, 25, 20),
                       block_id="public-script-turn")


def write_api_proof(output):
    """Write a three-page opt-in proof; this is not the accepted source report."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    builder = _module("builder")
    fonts = builder.fixture_fonts()
    p26 = _public_table(_authored_tables(26)[0], local=False)
    p30_data = _authored_tables(30)[0]
    # This opt-in proof explicitly allocates the added inner stroke clearance.
    # Its 504 pt local capacity is independent of the unchanged source frame.
    p30_grid = {**p30_data["local_grid"], "rows": 4200}
    p30 = QuarterTurn(_public_table(p30_data, local=True), turns=1,
                      local_grid=GridSpec(0, 0, **p30_grid), block_id="public-p30-turn")
    pages = Document(p26, PageBreak(), p30, PageBreak(), _nested_script_table(),
                     fonts=fonts, profile=builder.SOURCE_PROFILE).layout()
    assert len(pages) == 3
    trace = layout_trace(pages, fonts)
    (output / "trace.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    for variant in ("normal", "grid"):
        path = output / f"{variant}.pdf"
        render_pdf(pages, path, fonts, debug_grid=variant == "grid")
        with pymupdf.open(path) as pdf:
            for number, page in enumerate(pdf, 1):
                page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(output / f"{variant}-p{number:02}.png")
    return pages, trace


def test_selective_p26_rotated_p30_and_nested_script_native_pdf(tmp_path):
    pages, trace = write_api_proof(tmp_path)
    metadata = json.dumps(trace)
    assert '"height_mode": "explicit"' in metadata
    assert '"height_rounding": "single"' in metadata
    assert '"block_id": "public-script-lines"' in metadata
    p26_horizontal = [command for command in pages[0].commands
                      if isinstance(command, Line) and command.y1 == command.y2]
    assert len(p26_horizontal) == 3
    # The source's 0.12 pt hairline and 1 pt rules as border styles: hair 0.25 pt, medium 1.0 pt.
    assert sorted(command.width for command in p26_horizontal) == [.25, 1, 1]
    assert len({(command.x1, command.y1, command.x2, command.y2) for command in p26_horizontal}) == 3
    with pymupdf.open(tmp_path / "normal.pdf") as plain, pymupdf.open(tmp_path / "grid.pdf") as grid:
        assert len(plain) == len(grid) == 3
        for number in range(3):
            assert plain[number].get_images() == grid[number].get_images() == []
            assert plain[number].get_text() == grid[number].get_text()
        assert "Case" in plain[1].get_text()
        verifier = _module("verify")
        checked_cells = 0
        for page_index, source_page in ((0, 26), (1, 30)):
            record = json.loads((FIXTURE / f"expected/p{source_page:02}.json").read_text(encoding="utf-8"))
            expected_table = next(block for block in record["blocks"] if block["kind"] == "table")
            regions, _ = verifier._trace_regions(trace["pages"][page_index])
            chars = verifier._chars(plain[page_index])
            for cell in expected_table["cells"]:
                selected = verifier._inside(chars, regions[cell["id"]])
                assert verifier._compact(verifier._reading(selected, cell["direction"])) == verifier._compact(cell["text"])
                verifier._script_positions(selected, cell)
                checked_cells += 1
        assert checked_cells == 298
        script_glyphs = [char for block in plain[2].get_text("rawdict")["blocks"]
                        for line in block.get("lines", []) for span in line["spans"]
                        for char in span["chars"] if char["c"] in ("S", "3", "0", "x", "2", "n")]
        assert len(script_glyphs) == 6
        assert {char["c"] for char in script_glyphs} == {"S", "3", "0", "x", "2", "n"}
    assert len(list(tmp_path.glob("*-p*.png"))) == 6
