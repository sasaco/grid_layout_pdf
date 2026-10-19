"""Document output verified independently through PDF text and geometry."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import pymupdf
import pytest

from gridlayoutpdf.blocks import PageBreak, Paragraph, Spacer
from gridlayoutpdf.document import Document, PageDecoration, PageSection
from gridlayoutpdf.errors import FontError, LayoutError, LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE
from gridlayoutpdf.tables import Cell, Table


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def fonts():
    registry = FontRegistry()
    return registry


def test_document_render_forwards_invariant_output(tmp_path, fonts):
    document = Document(Paragraph("再現 Alpha"), fonts=fonts, footer=PageDecoration("{page}/{pages}"))
    first, second = tmp_path / "first.pdf", tmp_path / "second.pdf"
    assert document.render(first, invariant=True) == first
    assert document.render(second, invariant=True) == second
    assert first.read_bytes() == second.read_bytes()


def test_render_returns_path_and_preserves_mixed_page_geometry_text_and_sizes(tmp_path, fonts):
    document = Document(Paragraph("一枚目 Alpha"),
                        PageSection(A3_LANDSCAPE_REFERENCE, Paragraph("二枚目 Beta")),
                        Paragraph("三枚目 Gamma"), fonts=fonts,
                        header=PageDecoration("Report {page}/{pages}"),
                        footer=PageDecoration("{page}/{pages}", align="right"))
    normal, debug = tmp_path / "normal.pdf", tmp_path / "grid.pdf"
    assert document.render(str(normal)) == normal
    assert document.render(debug, debug_grid=True) == debug
    with pymupdf.open(normal) as pdf, pymupdf.open(debug) as grid:
        assert [(page.rect.width, page.rect.height) for page in pdf] == [(595, 842), (1191, 842), (595, 842)]
        for index, (page, debug_page, content) in enumerate(zip(pdf, grid,
                  ("一枚目 Alpha", "二枚目 Beta", "三枚目 Gamma"), strict=True), start=1):
            assert content in page.get_text()
            assert page.get_text().count(f"{index}/3") == 2
            assert page.get_text() == debug_page.get_text()
            spans = [span for block in page.get_text("dict")["blocks"] for line in block.get("lines", ()) for span in line["spans"]]
            body = next(span for span in spans if content in span["text"])
            assert body["origin"] == pytest.approx((50.88, 65.598), abs=.01)
            assert body["size"] == pytest.approx(10, abs=.01)
            assert all(span["size"] == pytest.approx(9, abs=.01) for span in spans if f"{index}/3" in span["text"])
            assert len(debug_page.get_drawings()) > len(page.get_drawings())


@pytest.mark.parametrize("kind", ["empty", "height", "decoration", "glyph"])
def test_render_failure_preserves_existing_destination_and_no_partial_file(tmp_path, fonts, kind):
    destination = tmp_path / "existing.pdf"
    destination.write_bytes(b"original destination bytes")
    if kind == "empty":
        document = Document(PageBreak(), Paragraph(""), fonts=fonts)
        error = LayoutError
    elif kind == "height":
        document = Document(Spacer(48), fonts=fonts)
        error = LayoutOverflowError
    elif kind == "decoration":
        document = Document(Paragraph("valid"), fonts=fonts, header=PageDecoration("x", rows=4))
        error = LayoutOverflowError
    else:
        document = Document(Paragraph("valid"), Paragraph(chr(0x10ffff)), fonts=fonts)
        error = FontError
    with pytest.raises(error):
        document.render(destination)
    assert destination.read_bytes() == b"original destination bytes"
    assert list(tmp_path.iterdir()) == [destination]


def test_render_empty_document_does_not_create_destination(tmp_path, fonts):
    destination = tmp_path / "empty.pdf"
    with pytest.raises(LayoutError, match="empty"):
        Document(fonts=fonts).render(destination)
    assert not destination.exists()


def test_pagination_proof_has_ordered_content_scoped_table_and_fixed_page_numbers(tmp_path):
    source = ROOT / "examples/pagination_proof.py"
    assert source.is_file(), "The pagination proof has not been implemented"
    spec = importlib.util.spec_from_file_location("pagination_proof", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.write_proof(tmp_path)
    with pymupdf.open(tmp_path / "pagination-proof.pdf") as pdf, pymupdf.open(tmp_path / "pagination-proof-grid.pdf") as debug:
        assert [tuple(page.rect)[2:] for page in pdf] == [(595, 842)] * 3 + [(1191, 842), (595, 842)]
        texts = [page.get_text() for page in pdf]
        assert "末尾に置かない見出し" not in texts[0]
        assert "末尾に置かない見出し" in texts[1] and "本文行 47" in texts[1]
        assert "本文行 93" in texts[2]
        assert "Wide table" in texts[3] and "最終ページ" in texts[4]
        all_text = "".join(texts)
        for number in range(1, 97):
            assert all_text.count(f"本文行 {number:02d}") == 1
        indices = [all_text.index(f"本文行 {number:02d}") for number in range(1, 97)]
        assert indices == sorted(indices)
        for index, (page, grid_page) in enumerate(zip(pdf, debug, strict=True), start=1):
            assert page.get_text().count(f"{index}/5") == 2
            assert page.get_text() == grid_page.get_text()
            assert len(grid_page.get_drawings()) > len(page.get_drawings())
        assert len(pdf[3].search_for("Wide table")) == 1
        assert len(pdf[4].get_images()) == 1
    trace = json.loads((tmp_path / "pagination-proof.json").read_text(encoding="utf-8"))
    assert trace["schema_version"] == 1 and len(trace["pages"]) == 5
    assert len(list((tmp_path / "previews").glob("*.png"))) == 10


def test_pdf_table_fragments_repeat_headers_keep_rowspan_group_and_preserve_order(tmp_path, fonts):
    table = Table((6, 6), ((Cell("HEADER", colspan=2),),
                          (Cell("MERGED", rowspan=2), "ROW-A"), ("ROW-B",),
                          ("LAST", "ROW-C")), header_rows=1, block_id="fragmented-table")
    profile = replace(A4_PORTRAIT_REFERENCE, body_end_row=6)
    path = Document(table, fonts=fonts, profile=profile).render(tmp_path / "table.pdf")
    with pymupdf.open(path) as pdf:
        assert len(pdf) == 2
        assert [page.get_text().splitlines() for page in pdf] == [
            ["HEADER", "MERGED", "ROW-A", "ROW-B"], ["HEADER", "LAST", "ROW-C"],
        ]
        for page in pdf:
            assert len(page.search_for("HEADER")) == 1
            rect = page.search_for("HEADER")[0]
            assert rect.x0 == pytest.approx(53.88, abs=.01)
            spans = [span for block in page.get_text("dict")["blocks"] for line in block.get("lines", ()) for span in line["spans"]]
            assert all(span["size"] == pytest.approx(10, abs=.01) for span in spans)
        assert pdf[0].search_for("ROW-B")[0].y0 > pdf[0].search_for("ROW-A")[0].y1
