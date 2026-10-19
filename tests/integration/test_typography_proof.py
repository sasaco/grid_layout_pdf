"""Acceptance checks for the small, inspectable Step 2 typography proof."""

import importlib.util
import json
from pathlib import Path

import pymupdf
import pytest

from gridlayoutpdf.fonts import FontRegistry


ROOT = Path(__file__).resolve().parents[2]


def proof_module():
    path = ROOT / "examples/typography_proof.py"
    assert path.is_file(), "The typography proof example has not been implemented"
    specification = importlib.util.spec_from_file_location("typography_proof", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def pdf_chars(page):
    return [
        (character, span)
        for block in page.get_text("rawdict")["blocks"] if "lines" in block
        for line in block["lines"] for span in line["spans"]
        for character in span["chars"]
    ]


def test_proof_outputs_have_independent_anchors_mixed_pages_and_debug_trace(tmp_path):
    proof_module().write_proof(tmp_path)
    plain = tmp_path / "typography-proof.pdf"
    debug = tmp_path / "typography-proof-grid.pdf"
    trace = json.loads((tmp_path / "typography-proof.json").read_text(encoding="utf-8"))
    assert trace["schema_version"] == 1
    assert len(trace["pages"]) == 3
    assert trace["font"]["sha256"] == "7a306386f930fee80922f71eebf4ffe0f1ff2817da8e619230953487673d71c7"
    assert trace["pages"][0]["metadata"]["equal_centers_pt"] == pytest.approx([211.68, 404.64])
    with pymupdf.open(plain) as pdf, pymupdf.open(debug) as grid_pdf:
        assert [(p.rect.width, p.rect.height) for p in pdf] == [(595, 842), (1191, 842), (595, 842)]
        assert len(grid_pdf) == len(pdf)
        for page, grid_page in zip(pdf, grid_pdf, strict=True):
            assert page.get_text() == grid_page.get_text()
            assert "日本語" in page.get_text()
            assert "α β γ" in page.get_text()
            chars = pdf_chars(page)
            equals = [char for char, _ in chars if char["c"] == "="]
            assert len(equals) == 4
            centers = [(char["bbox"][0] + char["bbox"][2]) / 2 for char in equals]
            assert sorted(centers) == pytest.approx([211.68, 211.68, 404.64, 404.64], abs=0.1)
            for char, span in chars:
                if char["c"] == "=":
                    assert span["size"] == pytest.approx(10, abs=0.01)
            for number in ("12.150", "7.38113"):
                found = page.search_for(number)
                assert len(found) == 1
                assert found[0].x1 == pytest.approx(468.96, abs=0.1)
            # The fixture font lacks U+2074; units use ordinary digits as
            # explicit superscripts instead of silently substituting a glyph.
            units = [(char, span) for char, span in chars if char["c"] == "m"]
            assert len(units) == 2
            for char, _ in units:
                assert char["origin"][0] == pytest.approx(485.04, abs=0.1)
            superscripts = [(char, span) for char, span in chars
                            if span["size"] < 10 and char["c"] in {"2", "4"}
                            and char["origin"][0] > 485 and char["origin"][1] < 200]
            assert {char["c"] for char, _ in superscripts} == {"2", "4"}
            assert all(span["size"] == pytest.approx(6.5, abs=0.01)
                       for _, span in superscripts)
            assert len(grid_page.get_drawings()) > len(page.get_drawings())
    previews = sorted((tmp_path / "previews").glob("*.png"))
    assert len(previews) == 6
    for preview in previews:
        image = pymupdf.Pixmap(preview)
        assert image.height == 1684
        assert image.width in {1190, 2382}


def test_proof_trace_serializes_frozen_metadata_and_text_bounds(tmp_path):
    module = proof_module()
    fonts = FontRegistry()
    pages = module.build_pages(fonts)
    assert len(pages) == 3
    module.write_proof(tmp_path)
    trace = json.loads((tmp_path / "typography-proof.json").read_text(encoding="utf-8"))
    for page in trace["pages"]:
        assert page["commands"]
        text = next(command for command in page["commands"] if command["kind"] == "Text")
        assert text["bounds"][1] < text["y"] < text["bounds"][3]
        assert text["style"]["size"] == 10
        assert page["metadata"]["font_size_pt"] == 10


def test_complex_math_is_vector_text_with_fractions_scripts_root_and_tall_brackets(tmp_path):
    proof_module().write_proof(tmp_path)
    trace = json.loads((tmp_path / "typography-proof.json").read_text(encoding="utf-8"))
    assert all("complex_math" in page["metadata"] for page in trace["pages"])
    with pymupdf.open(tmp_path / "typography-proof.pdf") as pdf:
        for page in pdf:
            assert not page.get_images()
            assert "段分数・指数・根号" in page.get_text()
            chars = pdf_chars(page)
            math_chars = [(char, span) for char, span in chars if char["origin"][1] > 390]
            assert {"β", "γ", "1", "2", "+"} <= {char["c"] for char, _ in math_chars}
            assert any(span["size"] == pytest.approx(6.5, abs=0.01)
                       for _, span in math_chars)
            drawings = page.get_drawings()
            assert len(drawings) >= 7
            horizontal_rules = [
                (start.x, end.x, start.y, drawing["width"])
                for drawing in drawings for kind, *points in drawing["items"]
                if kind == "l"
                for start, end in [points]
                if abs(start.y - end.y) < 0.01 and end.x > start.x + 2
            ]
            assert len(horizontal_rules) >= 4
            for left, right, y, width in horizontal_rules:
                for char, _ in chars:
                    box = pymupdf.Rect(char["bbox"])
                    if char["c"].strip() and min(right, box.x1) - max(left, box.x0) > 0.05:
                        assert not (box.y0 < y + width / 2 and box.y1 > y - width / 2), (
                            f"Fraction/root rule touches {char['c']!r}: {box}, y={y}"
                        )
