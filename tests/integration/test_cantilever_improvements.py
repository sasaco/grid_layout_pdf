"""Public API proofs and preserved original appearance after fixture migration."""

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
    PageProfile, PageSection, QuarterTurn, RasterImage, Script, Table,
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


def _tables(number):
    """The builder's page inputs and the authored tables of one original page."""
    builder = _module("builder")
    data = json.loads((FIXTURE / f"pages/p{number:02}.json").read_text(encoding="utf-8"))
    layout = {page["source_page"]: page for page in builder.source_layout()["pages"]}[number]
    leaves = tuple(builder._leaves({"type": "stack", "children": data["blocks"]}))
    page = builder._Page(number, builder.fixture_fonts(), {block["id"]: block for block in layout["blocks"]}, leaves)
    return page, [block for block in leaves if block["type"] == "table"]


def _context(fonts, number, turned):
    """The context a source table is measured in: the page grid, or the swapped page grid inside QuarterTurn."""
    builder = _module("builder")
    profile = builder.page_profile(number)
    if not turned:
        return LayoutContext(fonts, profile, builder.SOURCE_STYLE)
    grid = profile.grid
    local = GridSpec(0, 0, grid.pitch_y, grid.pitch_x, grid.rows, grid.columns)
    return LayoutContext(fonts, PageProfile("local", local.columns * local.pitch_x, local.rows * local.pitch_y, local),
                         builder.SOURCE_STYLE)


@pytest.mark.parametrize("number,count", [(1, 70), (26, 186), (30, 267), (36, 306)])
def test_all_authored_table_cells_use_single_rounding_and_one_grid_row_per_line(number, count):
    builder = _module("builder")
    fonts = builder.fixture_fonts()
    page, tables = _tables(number)
    seen = []
    for data in tables:
        built = builder._table(data, page)
        turned = isinstance(built, QuarterTurn)
        table = built.block if turned else built
        context = _context(fonts, number, turned)
        pitch = context.profile.grid.pitch_y
        measured = measure_block(table, context, sum(table.columns) * context.profile.grid.pitch_x)
        assert measured.rows == sum(table.row_heights)
        # Header rows are the repeated prefix; every other row group is a part.
        for part in (*measured.prefix, *measured.parts):
            for cell in part.metadata["cells"]:
                seen.append(cell["cell_id"])
                assert all(value == 0 for value in cell["padding_pt"].values())
                content = cell["content"]
                assert content["row_pitch"] == pitch
                metadata = content["parts"][0]["metadata"]
                assert metadata["height_rounding"] == "single"
                assert metadata["line_advance"] == pitch
                baselines = metadata["baselines_pt"]
                assert all(b - a == pytest.approx(pitch) for a, b in zip(baselines, baselines[1:]))
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


@pytest.mark.parametrize("grid", [False, True])
def test_migrated_fixed_pages_preserve_original_content_and_follow_the_grid_rules(tmp_path, grid):
    selected = (1, 26, 30, 36)
    builder = _module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=selected)
    assert len(pages) == len(selected)
    # Every page keeps its ink inside its own fixed page grid.
    assert all(max(command_bounds(command, fonts).bottom for command in page.commands)
               <= page.profile.grid.origin_y + page.profile.grid.rows * page.profile.grid.pitch_y for page in pages)
    trace = layout_trace(pages, fonts)
    output = tmp_path / "fixed-pages.pdf"
    render_pdf(pages, output, fonts, debug_grid=grid)
    content = _module("verify").verify_pdf(output, source_pages=selected, trace=trace,
                                          manifest=builder.load_manifest(), grid=grid)
    assert content["source_order"]["source_pages"] == list(selected)
    appearance = _module("verify_appearance").verify_appearance(output, source_pages=selected, trace=trace)
    assert appearance["error_count"] == 0
    assert set(appearance["checks"]) == set(_module("verify_appearance").CATEGORIES)


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
    """Write a three-page proof of the fixture's public parts; this is not the accepted source report."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    builder = _module("builder")
    fonts = builder.fixture_fonts()
    page26, tables26 = _tables(26)
    page30, tables30 = _tables(30)
    p26 = builder._table(tables26[0], page26)
    p30 = builder._table(tables30[0], page30)
    pages = Document(p26, PageBreak(), PageSection(builder.ROTATED_PROFILE, p30), PageBreak(), _nested_script_table(),
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
