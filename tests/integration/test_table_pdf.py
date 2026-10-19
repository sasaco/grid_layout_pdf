"""Independent PDF extraction for the merged-table scene proof."""

import importlib.util
import json
from pathlib import Path

import pymupdf
import pytest


ROOT = Path(__file__).resolve().parents[2]


def proof_module():
    path = ROOT / "examples/table_proof.py"
    assert path.is_file(), "The table proof has not been implemented"
    spec = importlib.util.spec_from_file_location("table_proof", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_table_proof_pdf_text_numeric_alignment_and_stroked_frame(tmp_path):
    proof_module().write_proof(tmp_path)
    with pymupdf.open(tmp_path / "table-proof.pdf") as plain, pymupdf.open(tmp_path / "table-proof-grid.pdf") as debug:
        assert len(plain) == len(debug) == 2
        full_text = "".join(page.get_text() for page in plain)
        for label in ("部材A", "部材B", "CASE-C", "CASE-D", "CASE-E", "CASE-F"):
            assert full_text.count(label) == 1
        for page, grid_page in zip(plain, debug, strict=True):
            assert (page.rect.width, page.rect.height) == (595, 842)
            assert page.get_text() == grid_page.get_text()
            assert page.get_text().count("断面・条件") == 1
            assert page.get_text().count("照査結果") == 1
            assert len(grid_page.get_drawings()) > len(page.get_drawings())
            lines = [item for drawing in page.get_drawings() for item in drawing["items"] if item[0] == "l"]
            assert any(item[1].x == pytest.approx(51.13, abs=0.02) and item[2].x == pytest.approx(51.13, abs=0.02) for item in lines)
            assert any(item[1].x == pytest.approx(533.03, abs=0.02) and item[2].x == pytest.approx(533.03, abs=0.02) for item in lines)
        result = plain[0].search_for("12.50")
        assert len(result) == 1 and result[0].x1 == pytest.approx(369.48, abs=0.05)
        spans = [span for block in plain[0].get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"] if "12.50" in span["text"]]
        assert len(spans) == 1 and spans[0]["size"] == pytest.approx(10)


def test_table_proof_trace_keeps_original_rows_and_cell_content_metadata(tmp_path):
    proof_module().write_proof(tmp_path)
    trace = json.loads((tmp_path / "table-proof.json").read_text(encoding="utf-8"))
    assert trace["schema_version"] == 1 and len(trace["pages"]) == 2
    body_rows = []
    for page in trace["pages"]:
        assert page["table_origin_pt"] == pytest.approx([50.88, 101.038])
        assert page["prefix"][0]["metadata"]["source_rows"] == [0, 1]
        assert page["prefix"][0]["metadata"]["columns_pt"] == pytest.approx([64.32, 80.4, 96.48, 80.4, 80.4, 80.4])
        for part in page["parts"]:
            body_rows.extend(part["metadata"]["source_rows"])
            assert all("content" in cell and "frame" in cell for cell in part["metadata"]["cells"])
    assert body_rows == list(range(2, 10))
    previews = sorted((tmp_path / "previews").glob("table-proof*.png"))
    assert len(previews) == 4
    assert all(pymupdf.Pixmap(path).height == 1684 for path in previews)


def test_selective_table_rules_are_native_paths_with_requested_per_stroke_widths(tmp_path):
    from gridlayoutpdf import Cell, Document, FontRegistry, GridSpec, PageProfile, Table, TextStyle

    assert "horizontal_rules" in Table.__dataclass_fields__
    fonts = FontRegistry()
    profile = PageProfile("rules", 300, 400, GridSpec(20, 20, 10, 20, 20, 18))
    table = Table((5, 5, 5), (("荷重", "G1", "G2"), ("終点", "12.50", "-3.00"), ("起点", "0.00", "4.50")),
                  header_rows=1, horizontal_rules=(2, 0.5, 0, 2), vertical_rules=(0, 0.5, 0, 0))
    document = Document(table, fonts=fonts, profile=profile)
    output = tmp_path / "rules.pdf"
    document.render(output)
    with pymupdf.open(output) as pdf:
        assert len(pdf) == 1
        page = pdf[0]
        assert page.get_images() == []
        assert "12.50" in page.get_text() and "-3.00" in page.get_text()
        drawings = page.get_drawings()
        assert len(drawings) == 7
        horizontal = [p for p in drawings if abs(p["items"][0][1].y - p["items"][0][2].y) < 0.001]
        vertical = [p for p in drawings if abs(p["items"][0][1].x - p["items"][0][2].x) < 0.001]
        assert [p["width"] for p in horizontal] == pytest.approx([2, 0.5, 0.5, 2])
        assert [p["items"][0][1].y for p in horizontal] == pytest.approx([21, 59.75, 60.25, 139], abs=0.001)
        assert [p["width"] for p in vertical] == pytest.approx([0.5] * 3)
        assert all(p["items"][0][1].x == pytest.approx(70) for p in vertical)


def test_indivisible_table_pdf_has_single_shared_rule_and_continuous_vertical_path(tmp_path):
    from gridlayoutpdf import Document, FontRegistry, GridSpec, PageProfile, Table

    assert "split" in Table.__dataclass_fields__
    fonts = FontRegistry()
    profile = PageProfile("atomic", 300, 400, GridSpec(20, 20, 10, 20, 20, 18))
    table = Table((5, 5, 5), (("荷重", "G1", "G2"), ("終点", "12.50", "-3.00"), ("起点", "0.00", "4.50")),
                  header_rows=1, horizontal_rules=(2, .5, 0, 2), vertical_rules=(0, .5, 0, 0), split=False)
    for debug in (False, True):
        path = tmp_path / f"atomic-{debug}.pdf"
        Document(table, fonts=fonts, profile=profile).render(path, debug_grid=debug)
        with pymupdf.open(path) as pdf:
            assert len(pdf) == 1 and pdf[0].get_images() == []
            assert pdf[0].get_text().count("荷重") == 1
            drawings = pdf[0].get_drawings()
            strokes = [d for d in drawings if d["width"] == .5 and d["color"] == (0, 0, 0)]
            assert len(strokes) == 2
            horizontal = next(d for d in strokes if d["items"][0][1].y == d["items"][0][2].y)
            vertical = next(d for d in strokes if d["items"][0][1].x == d["items"][0][2].x)
            assert horizontal["items"][0][1].y == pytest.approx(60)
            assert vertical["items"][0][1].y == pytest.approx(20.25)
            assert vertical["items"][0][2].y == pytest.approx(139.75)


@pytest.mark.parametrize("turns", [-1, 1])
def test_rotated_nested_cell_lines_keep_ink_size_and_json_diagnostics(tmp_path, turns):
    from gridlayoutpdf import (Cell, CellLines, Document, FontRegistry, GridSpec, Insets,
                              PageProfile, QuarterTurn, Table, TextStyle, layout_trace)

    fonts = FontRegistry()
    profile = PageProfile("nested", 300, 400, GridSpec(20, 20, 10, 20, 25, 18))
    content = CellLines(("G1", "12.50"), style=TextStyle(size=10), line_advance=12.8,
                        inner_padding=Insets(top=1, right=2, bottom=1, left=2), block_id="lines")
    inner = Table((8,), ((Cell(content, padding=0),),), split=False, row_heights=(3,), block_id="inner")
    outer = Table((10,), ((Cell(inner, padding=Insets(1, 2, 3, 4)),),), split=False, block_id="outer")
    rotated = QuarterTurn(outer, turns=turns, local_grid=GridSpec(0, 0, 10, 10, 20, 20))
    document = Document(rotated, fonts=fonts, profile=profile)
    trace = layout_trace(document.layout(), fonts)
    assert json.loads(json.dumps(trace)) == trace
    metadata_text = json.dumps(trace["pages"][0]["metadata"])
    assert '"height_mode": "explicit"' in metadata_text
    assert '"height_mode": "automatic"' in metadata_text
    assert '"cell_id": "outer.rows[0].cells[0]"' in metadata_text
    assert '"inner_padding_pt": {"top": 1.0, "right": 2.0, "bottom": 1.0, "left": 2.0}' in metadata_text
    output = tmp_path / "nested.pdf"
    document.render(output)
    with pymupdf.open(output) as pdf:
        assert len(pdf) == 1 and pdf[0].get_images() == []
        lines = [line for block in pdf[0].get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] if any(s["text"] in ("G1", "12.50") for s in line["spans"])]
        assert len(lines) == 2
        assert all(line["dir"] == pytest.approx((0, -turns)) for line in lines)
        assert all(span["size"] == pytest.approx(10) for line in lines for span in line["spans"])
        assert abs(lines[1]["spans"][0]["origin"][0] - lines[0]["spans"][0]["origin"][0]) == pytest.approx(12.8, abs=.001)


def test_indivisible_table_moves_whole_and_rejects_oversize_without_new_fragment(tmp_path):
    from gridlayoutpdf import (Cell, CellLines, Document, FontRegistry, GridSpec,
                              LayoutOverflowError, PageProfile, Spacer, Table)

    fonts = FontRegistry()
    profile = PageProfile("small", 200, 200, GridSpec(20, 20, 10, 20, 16, 8))
    table = Table((8,), ((Cell(CellLines(("A",), inner_padding=1), padding=0),),) * 3,
                  row_heights=(2, 2, 2), split=False, header_rows=1)
    pages = Document(Spacer(4), table, fonts=fonts, profile=profile).layout()
    assert len(pages) == 2
    assert sum(command.text == "A" for command in pages[1].commands if hasattr(command, "text")) == 3
    oversized = Table(table.columns, table.rows, row_heights=(3, 3, 3), split=False, header_rows=1)
    with pytest.raises(LayoutOverflowError):
        Document(oversized, fonts=fonts, profile=profile).layout()
