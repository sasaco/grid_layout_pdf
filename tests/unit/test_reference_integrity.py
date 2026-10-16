"""Preserve measured source evidence and useful display-only layout specimens.

The expected values below are transcribed from the research records.  They must
never be refreshed automatically from the PDFs or from the manifest under test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"
CASES = FIXTURES / "layout_cases"
EXPECTED_ORIGINALS = {
    ".agents/docs/research/A4.pdf": "eb6176ec32e60e494605da9e1e0481149eed89183d5ac306245db13ced603f60",
    ".agents/docs/research/A3.pdf": "3ef244c1085416746b0392fc2ef8898004bb1be49fc35a0f56335482425d9e16",
    "tests/output/04_地盤のモデル化.pdf": "f89ea249e4f9a9998821de7a7309af9bd41019841fa2feef6d0496af43183e3c",
    "tests/output/06_照査の前提.pdf": "ca7436bb4364db6437acb4aa79b6c1e3aed87c23601d54cb00a58b1e4767ec55",
    "tests/output/07_荷重計算.pdf": "23a6358c5a5b8966789668dc80a140095a0d2fe22e6d29943691f900213c3f1b",
    "tests/output/08_線路.pdf": "91e288880677f6e121afa887314d183000371478852b96663a6c753f76806706",
    "tests/output/09_直角.pdf": "b6a7f5658b9f98ee8a7d6b29691edcb0209bc7455fa8309d4e3a2e16605474de",
    "tests/output/10_線路(耐震).pdf": "933dec57e79330f44d07ed38adb89f8d2aa1ffd1c3e87b987ba3e20515f4063c",
    "tests/output/11_直角(耐震).pdf": "809a09f126daee89128ea991de35d50a4633151fccb7c50378af60d14965b838",
    "tests/output/12_フーチング.pdf": "f14c3fd062d13a0109ac809eda6a3468fc6ebfdc1e527b43c89ef7b55175ddf6",
    "tests/output/13_片持ち梁照査.pdf": "e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e",
    "tests/output/14_桁座補強●.pdf": "448811731bc0afd5d8dbfc3297e44b014e22a947d545391f4b549d937d8f7c56",
}
EXPECTED_REPORT_PAGES = {
    "report_04": (3, [1]),
    "report_06": (13, [1]),
    "report_07": (18, [1, 2]),
    "report_08": (32, [2, 3]),
    "report_09": (29, [6]),
    "report_10": (26, [25]),
    "report_11": (27, [8]),
    "report_12": (24, [1]),
    "report_13": (67, [1, 54]),
    "report_14": (12, [1, 11]),
}
CASE_IDS = (
    "japanese_two_anchors",
    "nested_fractions_scripts",
    "long_substitution",
    "merged_table",
    "mixed_diagram",
    "mixed_paper",
)


def read_json(path: Path) -> dict:
    assert path.is_file(), f"Missing fixture: {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def nodes(value):
    """Walk display data, including expressions nested in cells and sections."""
    if isinstance(value, dict):
        if "kind" in value:
            yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def case(case_id: str) -> dict:
    return read_json(CASES / f"{case_id}.json")


@pytest.mark.parametrize("path,expected", EXPECTED_ORIGINALS.items())
def test_original_pdfs_match_recorded_research_hashes(path, expected):
    source = ROOT / path
    assert source.is_file(), f"Original reference is missing: {path}"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected, path


def test_manifest_enumerates_all_originals_and_separates_generated_output():
    manifest = read_json(FIXTURES / "reference_manifest.json")
    assert manifest["schema_version"] == 1
    assert manifest["source_policy"] == "read_only_originals"
    references = manifest["references"]
    assert len(references) == 12
    assert len({item["id"] for item in references}) == 12
    assert {item["path"]: item["sha256"] for item in references} == EXPECTED_ORIGINALS
    assert manifest["generated_output_directory"] == "build/reports"
    generated = (ROOT / manifest["generated_output_directory"]).resolve()
    assert generated.is_relative_to(ROOT)
    for source_dir in (ROOT / "tests/output", ROOT / ".agents/docs/research"):
        assert not generated.is_relative_to(source_dir.resolve())
        assert not source_dir.resolve().is_relative_to(generated)
    assert manifest["layout_cases_directory"] == "tests/fixtures/layout_cases"
    assert manifest["acceptance"] == "grid_normalized_appearance_not_source_pixel_equality"


def test_manifest_preserves_measured_paper_grid_and_reviewed_page_roles():
    manifest = read_json(FIXTURES / "reference_manifest.json")
    assert manifest["coordinates"] == {"origin": "top_left", "x": "right", "y": "down", "unit": "pt"}
    references = {item["id"]: item for item in manifest["references"]}
    for reference_id, width, columns, right in (
        ("grid_a4", 595, 30, 533.28),
        ("grid_a3", 1191, 67, 1128.24),
    ):
        ref = references[reference_id]
        assert ref["page_count"] == 1
        assert ref["paper_runs"] == [{"first_page": 1, "last_page": 1, "size_pt": [width, 842], "rotation": 0}]
        assert ref["grid"] == {
            "origin_pt": [50.88, 54.598], "pitch_pt": [16.08, 15.48],
            "columns": columns, "rows": 47, "line_width_pt": 0.96,
            "bottom_right_pt": [right, 782.158], "measurement_status": "measured",
        }
        assert ref["reviewed_pages"] == [{"page": 1, "roles": ["grid_geometry"]}]
    for reference_id, (page_count, reviewed) in EXPECTED_REPORT_PAGES.items():
        ref = references[reference_id]
        assert ref["page_count"] == page_count
        assert [item["page"] for item in ref["reviewed_pages"]] == reviewed
        assert all(item["roles"] for item in ref["reviewed_pages"])
        a3_start = {"report_10": 25, "report_11": 26}.get(reference_id)
        expected_runs = [{"first_page": 1, "last_page": a3_start - 1 if a3_start else page_count, "size_pt": [595, 842], "rotation": 0}]
        if a3_start:
            expected_runs.append({"first_page": a3_start, "last_page": page_count, "size_pt": [1191, 842], "rotation": 0})
        assert ref["paper_runs"] == expected_runs
    required_roles = {
        ("report_08", 2): "two_equal_anchors",
        ("report_13", 54): "nested_fractions_scripts",
        ("report_07", 1): "wrapped_substitution",
        ("report_12", 1): "merged_table",
        ("report_06", 1): "raster_images",
        ("report_10", 25): "a3_landscape",
    }
    for (reference_id, page), role in required_roles.items():
        reviewed = {item["page"]: item["roles"] for item in references[reference_id]["reviewed_pages"]}
        assert role in reviewed[page]


def test_six_cases_contain_display_data_and_resolvable_source_pages():
    assert {path.stem for path in CASES.glob("*.json")} == set(CASE_IDS)
    manifest = read_json(FIXTURES / "reference_manifest.json")
    sources = {item["id"]: item for item in manifest["references"]}
    for case_id in CASE_IDS:
        data = case(case_id)
        assert data["schema_version"] == 1
        assert data["id"] == case_id
        assert data["display_data_only"] is True
        assert data["purpose"] and data["body"] and list(nodes(data["body"]))
        assert data["source_pages"]
        for source in data["source_pages"]:
            assert 1 <= source["page"] <= sources[source["reference_id"]]["page_count"]
        for node in nodes(data["body"]):
            if node["kind"] in {"literal", "symbol"}:
                assert isinstance(node["text"], str) and node["text"]
            if node["kind"] == "equation":
                assert isinstance(node["result"], str) and node["result"]


def test_japanese_case_has_two_shared_equal_anchors_and_formatted_results():
    groups = [n for n in nodes(case("japanese_two_anchors")) if n["kind"] == "equation_group"]
    assert len(groups) == 1
    group = groups[0]
    anchors = group["anchor_columns"]
    assert 0 < anchors["first_equal"] < anchors["second_equal"] < anchors["result_right"] < anchors["unit_start"] < 30
    assert len(group["equations"]) >= 2
    assert {row["result"] for row in group["equations"]} == {"12.150", "7.38113"}
    for row in group["equations"]:
        assert any("\u3040" <= ch <= "\u9fff" for ch in row["label"])
        assert row["relation"] == "=" and row["result_relation"] == "="
        assert row["unit"]


def test_nested_case_exercises_atomic_fractions_scripts_root_and_delimiters():
    parts = list(nodes(case("nested_fractions_scripts")))
    fractions = [node for node in parts if node["kind"] == "fraction"]
    assert len(fractions) >= 3
    assert any(any(child["kind"] == "fraction" for child in nodes(node["denominator"])) for node in fractions)
    scripts = [node for node in parts if node["kind"] == "script"]
    assert any("subscript" in node for node in scripts)
    assert any(any(child["kind"] == "fraction" for child in nodes(node.get("superscript"))) for node in scripts)
    assert {"root", "delimited"} <= {node["kind"] for node in parts}


def test_long_substitution_preserves_ordered_terms_and_explicit_break():
    equations = [node for node in nodes(case("long_substitution")) if node["kind"] == "equation"]
    assert len(equations) == 1
    items = equations[0]["rhs"]["items"]
    assert [node["text"] for node in items if node["kind"] == "literal"] == ["12.50", "3.20", "8.75", "4.00", "6.25", "2.10", "9.50", "1.80"]
    assert [node["text"] for node in items if node["kind"] == "operator"] == ["×", "+", "×", "+", "×", "+", "×"]
    assert sum(node["kind"] == "break" for node in items) == 1
    assert equations[0]["result"] == "105.225"


def test_merged_table_spans_cover_cells_once_and_keep_header_boundary():
    tables = [node for node in nodes(case("merged_table")) if node["kind"] == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert table["header_rows"] == 2 and table["repeat_header"] is True
    assert sum(table["column_spans"]) <= 30
    assert any(cell.get("rowspan", 1) > 1 for cell in table["cells"])
    assert any(cell.get("colspan", 1) > 1 for cell in table["cells"])
    occupied = set()
    for cell in table["cells"]:
        assert cell["content"]
        row_end = cell["row"] + cell.get("rowspan", 1)
        col_end = cell["column"] + cell.get("colspan", 1)
        assert 0 <= cell["row"] < row_end <= table["row_count"]
        assert 0 <= cell["column"] < col_end <= len(table["column_spans"])
        assert not cell["row"] < table["header_rows"] < row_end
        for row in range(cell["row"], row_end):
            for column in range(cell["column"], col_end):
                assert (row, column) not in occupied
                occupied.add((row, column))
    assert occupied == {(row, column) for row in range(table["row_count"]) for column in range(len(table["column_spans"]))}


def test_mixed_diagram_contains_vector_shapes_labels_and_a_raster_asset():
    parts = list(nodes(case("mixed_diagram")))
    assert {"heading", "paragraph", "figure", "image", "equation"} <= {node["kind"] for node in parts}
    figure = next(node for node in parts if node["kind"] == "figure")
    assert {"line", "arrow", "rectangle", "label"} <= {item["kind"] for item in figure["elements"]}
    image = next(node for node in parts if node["kind"] == "image")
    asset = (CASES / image["asset"]).resolve()
    assert asset.is_relative_to(CASES.resolve())
    assert asset.is_file() and asset.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert image["preserve_aspect_ratio"] is True


def test_mixed_paper_explicitly_returns_to_a4_without_changing_text_size():
    sections = case("mixed_paper")["body"]
    assert [section["kind"] for section in sections] == ["page_section"] * 3
    assert [section["profile"] for section in sections] == ["A4_PORTRAIT_REFERENCE", "A3_LANDSCAPE_REFERENCE", "A4_PORTRAIT_REFERENCE"]
    assert all(section["body"] for section in sections)
    assert {section["font_size_pt"] for section in sections} == {10}
