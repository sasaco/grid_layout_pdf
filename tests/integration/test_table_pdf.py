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
