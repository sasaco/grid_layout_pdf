"""Independent PDF extraction for the merged-table scene proof."""

import importlib.util
import json
from pathlib import Path

import pymupdf
import pytest


ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / "tests/fixtures/fonts/ipaexm.ttf"


def proof_module():
    path = ROOT / "examples/table_proof.py"
    assert path.is_file(), "The table proof has not been implemented"
    spec = importlib.util.spec_from_file_location("table_proof", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_table_proof_pdf_text_numeric_alignment_and_stroked_frame(tmp_path):
    proof_module().write_proof(tmp_path, FONT)
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
    proof_module().write_proof(tmp_path, FONT)
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
    fonts.register("body", FONT)
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
