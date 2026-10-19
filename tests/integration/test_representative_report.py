"""Public-API integration and independent PDF checks for the reusable example."""

import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pymupdf
import pytest
from PIL import Image as PILImage

from gridlayoutpdf import Document, LayoutOverflowError, render_pdf


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def example():
    path = ROOT / "examples/representative_report.py"
    spec = importlib.util.spec_from_file_location("representative_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    picture = tmp_path_factory.mktemp("report-input") / "picture.png"
    with PILImage.new("RGB", (240, 160), (220, 232, 238)) as image:
        image.save(picture)
    return (picture,)


def test_standard_report_uses_mixed_paper_and_preserves_chapter_order(example, inputs, tmp_path):
    (image,) = inputs
    report = example.build_report(image)
    assert isinstance(report, Document)
    pages = report.layout()
    assert 4 <= len(pages) <= 6, "The complete sample must contain all report chapters"
    assert report.layout() == pages
    path = tmp_path / "report.pdf"
    render_pdf(pages, path)
    with pymupdf.open(path) as pdf:
        dimensions = [(page.rect.width, page.rect.height) for page in pdf]
        assert dimensions[0] == dimensions[-1] == (595, 842)
        wide = [index for index, dimensions in enumerate(dimensions) if dimensions == (1191, 842)]
        assert len(wide) >= 2 and wide == list(range(min(wide), max(wide) + 1))
        texts = [page.get_text() for page in pdf]
        text = "\n".join(texts)
        chapters = ["1 計算条件", "2 断面諸量", "3 作用荷重", "4 荷重組合せ一覧", "5 整理と確認事項"]
        assert [text.index(chapter) for chapter in chapters] == sorted(text.index(chapter) for chapter in chapters)
        for value in ("12.150", "7.381125", "5.4675", "40.00", "7.00"):
            assert value in text
        for index in wide:
            assert texts[index].count("作用荷重一覧") == 1
            assert "CASE-" in texts[index]
        for number in range(1, 16):
            assert text.count(f"CASE-{number:02d}") == 1
        assert sum(len(page.get_images()) for page in pdf) == 1
        for page in pdf:
            assert f"{page.number + 1} / {len(pdf)}" in page.get_text()


def _pdf_chars(page):
    return [character for block in page.get_text("rawdict")["blocks"] if "lines" in block
            for line in block["lines"] for span in line["spans"] for character in span["chars"]]


def test_pdf_has_two_equal_columns_right_results_and_ten_point_prose(example, inputs, tmp_path):
    (image,) = inputs
    path = tmp_path / "anchors.pdf"
    example.build_report(image).render(path)
    with pymupdf.open(path) as pdf:
        page = next(page for page in pdf if "2 断面諸量" in page.get_text())
        equals = [character for character in _pdf_chars(page) if character["c"] == "="]
        for center in (211.68, 404.64):
            aligned = [character for character in equals if abs((character["bbox"][0] + character["bbox"][2]) / 2 - center) < 0.03]
            assert len(aligned) >= 5
        for result in ("12.150", "7.381125", "5.4675", "40.00", "7.00", "1.000"):
            hits = page.search_for(result)
            assert any(abs(hit.x1 - 468.96) < 0.03 for hit in hits), result
        prose = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]
                 if "矩形断面の幾何量" in span["text"]]
        assert prose and all(span["size"] == 10 for span in prose)
        # Long and forced Rows must retain all their terms on more than one baseline.
        long_terms = [hit for term in ("12.50", "8.75", "6.25", "4.00", "3.50", "2.00")
                      for hit in page.search_for(term)]
        assert len({round(hit.y0, 2) for hit in long_terms}) >= 2
        assert any(character["c"] == "β" for character in _pdf_chars(page))
        assert any(character["c"] == "γ" for character in _pdf_chars(page))
        drawings = page.get_drawings()
        # Six fraction rules, one root outline and two tall parentheses.
        assert sum(len(drawing["items"]) == 1 for drawing in drawings) == 6
        assert sum(len(drawing["items"]) > 1 for drawing in drawings) == 3


def test_long_variant_reflows_more_text_without_changing_display_values(example, inputs, tmp_path):
    (image,) = inputs
    standard, long = (example.build_report(image, variant=variant) for variant in ("standard", "long"))
    standard_pages, long_pages = standard.layout(), long.layout()
    standard_path, long_path = tmp_path / "standard.pdf", tmp_path / "long.pdf"
    render_pdf(standard_pages, standard_path)
    render_pdf(long_pages, long_path)
    with pymupdf.open(standard_path) as short_pdf, pymupdf.open(long_path) as long_pdf:
        short_text = "".join(page.get_text() for page in short_pdf)
        long_text = "".join(page.get_text() for page in long_pdf)
        assert len(long_text) > len(short_text) + 500
        for value in ("12.1500", "7.3811250", "5.46750", "40.000", "7.000"):
            assert value in long_text
        assert "部材中心線と作用位置の関係" in long_text
        short_lines = sum(len(block.get("lines", [])) for page in short_pdf for block in page.get_text("dict")["blocks"])
        long_lines = sum(len(block.get("lines", [])) for page in long_pdf for block in page.get_text("dict")["blocks"])
        assert len(long_pdf) > len(short_pdf) or long_lines > short_lines
        for number in range(1, 16):
            assert long_text.count(f"CASE-{number:02d}") == 1


@pytest.mark.parametrize("variant", ["unknown", "", None])
def test_variant_rejects_unknown_values(example, inputs, variant):
    with pytest.raises(ValueError, match="variant"):
        example.build_report(*inputs, variant=variant)


@pytest.mark.parametrize("pdf_output", [False, True])
def test_writer_emits_matching_normal_grid_trace_and_optional_previews(example, inputs, tmp_path, pdf_output):
    assert callable(getattr(example, "write_report", None)), "The example needs a reusable output writer"
    output = tmp_path / ("custom.pdf" if pdf_output else "output")
    files = example.write_report(output, image_path=inputs[0], preview=True)
    assert len(files) == 3 and all(path.is_file() for path in files)
    normal, grid, trace_path = files
    assert normal == (output if pdf_output else output / "representative-report.pdf")
    assert grid.name == normal.stem + "-grid.pdf"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    with pymupdf.open(normal) as pdf, pymupdf.open(grid) as debug:
        assert len(pdf) == len(debug) == len(trace["pages"])
        assert [page.get_text() for page in pdf] == [page.get_text() for page in debug]
        assert all(len(debug[index].get_drawings()) > len(page.get_drawings()) for index, page in enumerate(pdf))
        previews = sorted((normal.parent / "previews").glob("*.png"))
        assert len(previews) == 2 * len(pdf)
    assert "bytes" not in trace_path.read_text(encoding="utf-8")


def test_copied_cli_uses_public_api_default_asset_without_pymupdf(tmp_path):
    script = tmp_path / "representative_report.py"
    shutil.copyfile(ROOT / "examples/representative_report.py", script)
    asset = ROOT / "examples/assets/bridge-overview.png"
    assert asset.is_file(), "The example must carry an original default image"
    (tmp_path / "assets").mkdir()
    shutil.copyfile(asset, tmp_path / "assets/bridge-overview.png")
    (tmp_path / "pymupdf.py").write_text("raise ImportError('runtime must not import development preview package')\n", encoding="utf-8")
    output = tmp_path / "reports"
    result = subprocess.run([sys.executable, "-X", "utf8", str(script), "--output", str(output),
                             "--variant", "long"], cwd=tmp_path, text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (output / "representative-report.pdf").is_file()
    assert (output / "representative-report-grid.pdf").is_file()
    assert (output / "representative-report.json").is_file()
    assert not (output / "previews").exists()
    with pymupdf.open(output / "representative-report.pdf") as pdf:
        assert "12.1500" in "".join(page.get_text() for page in pdf)
    tree = ast.parse(script.read_text(encoding="utf-8"))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module.startswith("gridlayoutpdf")]
    assert imports == ["gridlayoutpdf"]
    assert "reportlab" not in script.read_text(encoding="utf-8").lower()


def test_cli_reports_an_unknown_font_name(tmp_path):
    result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "examples/representative_report.py"),
                             "--font", "GLP No Such Font", "--output", str(tmp_path / "report.pdf")],
                            text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 2 and "--font" in result.stderr and "GLP No Such Font" in result.stderr
    assert not (tmp_path / "report.pdf").exists()


def test_external_display_strings_keep_digits_size_anchors_and_input_snapshot(example, inputs, tmp_path):
    values = {"area": "12.150000", "inertia": "7.3811250", "section_modulus": "5.4675000",
              "vertical": "40.000000", "horizontal": "7.000000", "adjustment": "1.000000"}
    supplied = values.copy()
    report = example.build_report(*inputs, display_values=supplied)
    assert supplied == values
    supplied["area"] = "999.999"
    path = tmp_path / "external-values.pdf"
    report.render(path)
    with pymupdf.open(path) as pdf:
        page = next(page for page in pdf if "2 断面諸量" in page.get_text())
        assert "999.999" not in page.get_text()
        spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]]
        for value in values.values():
            assert value in page.get_text()
            assert any(abs(hit.x1 - 468.96) < 0.03 for hit in page.search_for(value))
            assert any(value in span["text"] and span["size"] == 10 for span in spans)
        equals = [character for character in _pdf_chars(page) if character["c"] == "="]
        for center in (211.68, 404.64):
            assert sum(abs((character["bbox"][0] + character["bbox"][2]) / 2 - center) < 0.03
                       for character in equals) >= 6


@pytest.mark.parametrize("values", [{"unknown": "1.00"}, {"area": 12.15}, {"area": None}, [("area", "12.15")]])
def test_external_display_values_reject_unknown_keys_and_nonstring_inputs(example, inputs, values):
    with pytest.raises(ValueError, match="display_values"):
        example.build_report(*inputs, display_values=values)


def test_partial_display_mapping_merges_with_variant_defaults(example, inputs, tmp_path):
    from types import MappingProxyType
    path = tmp_path / "partial-values.pdf"
    report = example.build_report(*inputs, variant="long", display_values=MappingProxyType({"area": "12.15000"}))
    report.render(path)
    with pymupdf.open(path) as pdf:
        text = "".join(page.get_text() for page in pdf)
        assert "12.15000" in text
        for value in ("7.3811250", "5.46750", "40.000", "7.000"):
            assert value in text


def test_external_result_wider_than_fixed_column_reports_overflow_without_shrinking(example, inputs):
    report = example.build_report(*inputs, display_values={"inertia": "7.38112500"})
    with pytest.raises(LayoutOverflowError, match="section-properties.*result") as caught:
        report.layout()
    assert caught.value.needed > caught.value.available
    assert caught.value.available == pytest.approx(64.32)
