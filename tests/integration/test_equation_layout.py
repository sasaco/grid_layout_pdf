"""Independent PDF extraction for measured equation groups."""

import importlib.util
import json
from pathlib import Path

import pymupdf
import pytest


ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / "tests/fixtures/fonts/ipaexm.ttf"


def proof_module():
    path = ROOT / "examples/equation_proof.py"
    assert path.is_file(), "The measured equation proof has not been implemented"
    spec = importlib.util.spec_from_file_location("equation_proof", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def chars(page):
    return [(char, span) for block in page.get_text("rawdict")["blocks"] if "lines" in block
            for line in block["lines"] for span in line["spans"] for char in span["chars"]]


def test_equation_proof_extracts_fixed_centers_results_units_order_and_sizes(tmp_path):
    proof_module().write_proof(tmp_path, FONT)
    with pymupdf.open(tmp_path / "equation-proof.pdf") as pdf, pymupdf.open(tmp_path / "equation-proof-grid.pdf") as debug:
        assert [(page.rect.width, page.rect.height) for page in pdf] == [(595, 842), (1191, 842)]
        page = pdf[0]
        extracted = chars(page)
        relations = [(char, span) for char, span in extracted if char["c"] in {"=", "＝"}]
        assert len(relations) == 10
        assert {char["c"] for char, _ in relations} == {"=", "＝"}
        centers = sorted((char["bbox"][0] + char["bbox"][2]) / 2 for char, _ in relations)
        assert centers == pytest.approx([211.68] * 5 + [404.64] * 5, abs=.1)
        assert all(span["size"] == pytest.approx(10, abs=.01) for _, span in relations)
        for result in ("12.150", "7.38113", "36.36", "0.125", "0.98765"):
            rects = page.search_for(result)
            assert len(rects) == 1
            assert rects[0].x1 == pytest.approx(468.96, abs=.1)
        for char, span in extracted:
            if char["c"] in {"m", "k"}:
                assert char["origin"][0] == pytest.approx(485.04, abs=.1)
        tokens = [f"{i}.{i:02d}" for i in range(1, 9)]
        text = page.get_text()
        assert [text.index(token) for token in tokens] == sorted(text.index(token) for token in tokens)
        assert all(len(page.search_for(token)) == 1 for token in tokens)
        assert any(char["c"] == "+" and abs(char["origin"][0] - 227.76) < .1 for char, _ in extracted)
        ordinary_tokens = {char["c"] for char, span in extracted if span["size"] == pytest.approx(10, abs=.01)}
        assert {"β", "γ"} & ordinary_tokens
        assert any(span["size"] == pytest.approx(6.5, abs=.01) for _, span in extracted)
        assert len(page.get_drawings()) >= 7 and not page.get_images()
        wide = page.search_for("1234567890" * 4)
        result = page.search_for("0.98765")
        assert len(wide) == 1 and result[0].y0 > wide[0].y1
        for plain_page, debug_page in zip(pdf, debug, strict=True):
            assert plain_page.get_text() == debug_page.get_text()
            assert len(debug_page.get_drawings()) > len(plain_page.get_drawings())
    trace = json.loads((tmp_path / "equation-proof.json").read_text(encoding="utf-8"))
    assert len(trace["pages"]) == 2
    assert any(part["metadata"]["continuation"] for part in trace["pages"][0]["parts"])
    assert any(part["metadata"]["result_line"] for part in trace["pages"][0]["parts"])
    assert trace["pages"][0]["parts"][0]["metadata"]["anchors_pt"]["first_equal"] == pytest.approx(160.8)
    assert len(list((tmp_path / "previews").glob("*.png"))) == 4
