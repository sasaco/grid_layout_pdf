"""The expected transcription must agree with the original PDF independently."""

from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from hashlib import sha256
import sys

import pytest


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/cantilever_p01_37"


def _module(name):
    spec = importlib.util.spec_from_file_location(f"source_order_test_{name}", FIXTURE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def verifier():
    return _module("verify")


def _record(number):
    return json.loads((FIXTURE / f"expected/p{number:02}.json").read_text(encoding="utf-8"))


def _item(record, identifier):
    return next(item for block in record["blocks"] for item in block.get("cells", [block])
                if item["id"] == identifier)


def _gate(verifier, pages, **kwargs):
    assert hasattr(verifier, "verify_source_order"), "original-to-expected ordering gate is absent"
    return verifier.verify_source_order(pages, **kwargs)


def test_every_source_page_matches_geometry_order_and_script_roles(verifier):
    result = _gate(verifier, range(1, 38))
    assert result["source_pages"] == list(range(1, 38))
    assert result["verified_items"] == 3345
    assert result["complete_37_pages"] is True


@pytest.mark.parametrize("number,identifier,before,after", [
    (1, "p01-dead-loads.r1.c3", "1530.0", "1350.0"),
    (30, "p30-combinations-md.r2.c3", "625.00", "265.00"),
    (1, "p01-reactions", "4-517.77", "4517.77-"),
    (1, "p01-dead-loads.r2.c4", "100.0", "010.0"),
])
def test_original_order_rejects_same_inventory_changes(verifier, number, identifier, before, after):
    record = _record(number)
    item = _item(record, identifier)
    original = item["text"]
    assert before in original
    item["text"] = original.replace(before, after, 1)
    assert Counter(original) == Counter(item["text"])
    with pytest.raises(AssertionError, match="original text order"):
        _gate(verifier, (number,), records=[record])


@pytest.mark.parametrize("change", ["role", "index", "text", "duplicate"])
def test_original_script_role_and_attachment_cannot_follow_changed_expected(verifier, change):
    record = _record(9)
    item = _item(record, "p09-sum-x2")
    script = item["source_scripts"][0]
    if change == "role":
        script["role"] = "subscript"
    elif change == "index":
        script["character_index"] += 1
    elif change == "text":
        script["text"] = "3"
    else:
        item["source_scripts"].append(deepcopy(script))
    with pytest.raises(AssertionError, match="original script"):
        _gate(verifier, (9,), records=[record])


def test_source_order_does_not_depend_on_pdf_paint_command_order(verifier, monkeypatch):
    extract = verifier._chars
    monkeypatch.setattr(verifier, "_chars", lambda page: list(reversed(extract(page))))
    assert _gate(verifier, range(1, 38))["verified_items"] == 3345


def test_source_direction_does_not_follow_changed_expected(verifier):
    record = _record(30)
    _item(record, "p30-combinations-md.r2.c3")["direction"] = [1, 0]
    with pytest.raises(AssertionError, match="original direction"):
        _gate(verifier, (30,), records=[record])


def test_source_gate_retains_once_only_glyph_coverage(verifier):
    record = _record(1)
    duplicate = deepcopy(_item(record, "p01-dead-loads.r1.c3"))
    duplicate["id"] += "-duplicate"
    next(block for block in record["blocks"] if "cells" in block)["cells"].append(duplicate)
    with pytest.raises(AssertionError, match="original region assignment"):
        _gate(verifier, (1,), records=[record])


def _swap_cell_assignment(record):
    first = _item(record, "p01-dead-loads.r1.c3")
    second = _item(record, "p01-dead-loads.r2.c3")
    for field in ("source_bbox", "text", "direction", "source_scripts"):
        first[field], second[field] = second[field], first[field]


@pytest.mark.parametrize("corruption", ["payload-and-bbox", "ids", "bbox-only"])
def test_source_region_assignment_cannot_follow_changed_expected(verifier, corruption):
    record = _record(1)
    first = _item(record, "p01-dead-loads.r1.c3")
    second = _item(record, "p01-dead-loads.r2.c3")
    if corruption == "payload-and-bbox":
        _swap_cell_assignment(record)
    elif corruption == "ids":
        first["id"], second["id"] = second["id"], first["id"]
    else:
        # This changes no selected glyph: bounds themselves must be pinned.
        first["source_bbox"][0] += .0001
    with pytest.raises(AssertionError, match="original region assignment"):
        _gate(verifier, (1,), records=[record])


def test_source_region_pin_is_independent_of_record_serialization_order(verifier):
    record = _record(1)
    record["blocks"].reverse()
    for block in record["blocks"]:
        if "cells" in block:
            block["cells"].reverse()
        for item in block.get("cells", [block]):
            item["source_bbox"] = [float(coordinate) for coordinate in item["source_bbox"]]
    assert _gate(verifier, (1,), records=[record])["verified_items"] == 79


def _changed_expected(tmp_path, monkeypatch, verifier, corruption="text"):
    expected = tmp_path / "expected"
    expected.mkdir()
    for number in range(1, 38):
        record = _record(number)
        if number == 1:
            if corruption == "assignment":
                _swap_cell_assignment(record)
            else:
                _item(record, "p01-dead-loads.r1.c3")["text"] = "1350.0"
        (expected / f"p{number:02}.json").write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(verifier, "EXPECTED", expected)


@pytest.mark.parametrize("corruption", ["text", "assignment"])
def test_prepare_rejects_wrong_oracle_before_layout_or_staging(tmp_path, monkeypatch, corruption):
    writer = _module("render")
    _changed_expected(tmp_path, monkeypatch, writer._sibling("verify"), corruption)
    monkeypatch.setattr(writer, "_input_hashes", lambda *args: {})
    def must_not_layout(*args, **kwargs):
        raise AssertionError("invalid original oracle reached layout")
    monkeypatch.setattr(writer.builder, "layout_report", must_not_layout)
    output = tmp_path / "output"
    message = "original region assignment" if corruption == "assignment" else "original text order"
    with pytest.raises(AssertionError, match=message):
        writer.prepare_bundle(output, object(), source_pages=(1,))
    assert not output.exists()


@pytest.mark.parametrize("corruption", ["text", "assignment"])
def test_activation_rechecks_original_before_publishing_even_with_matching_input_hashes(tmp_path, monkeypatch, corruption):
    writer = _module("render")
    _changed_expected(tmp_path, monkeypatch, writer._sibling("verify"), corruption)
    output = tmp_path / "output"
    bundle = output / ".staging" / "candidate"
    bundle.mkdir(parents=True)
    old_pointer = b'{"accepted": "previous"}'
    (output / "current.json").write_bytes(old_pointer)
    names = {"normal.pdf", "grid.pdf", "trace.json", "mapping.json"}
    names.update(f"previews/{variant}-p{number:02}.png"
                 for variant in ("normal", "grid") for number in range(1, 38))
    artifacts = {}
    for name in names:
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-only-artifact")
        artifacts[name] = sha256(path.read_bytes()).hexdigest()
    checks = {variant: {"source_pages": list(range(1, 38)), "complete_37_pages": True,
                        "variant": variant} for variant in ("normal", "grid")}
    changed_file = writer._sibling("verify").EXPECTED / "p01.json"
    manifest = {"source_pages": list(range(1, 38)), "checks": checks,
                "status": "content-verified-awaiting-visual-review",
                "tools": writer._tool_versions(), "python": sys.version,
                "inputs": {str(changed_file): sha256(changed_file.read_bytes()).hexdigest()},
                "artifacts": artifacts}
    (bundle / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    review = {"result": "pass", "reviewer": "test-only", "reviewed_at": "test-only",
              "artifacts": artifacts}
    def must_not_verify(*args, **kwargs):
        raise AssertionError("invalid original oracle reached generated PDF verification")
    monkeypatch.setattr(writer, "_verify_pdf", must_not_verify)
    message = "original region assignment" if corruption == "assignment" else "original text order"
    with pytest.raises(AssertionError, match=message):
        writer.activate_bundle(output, bundle, review)
    assert (output / "current.json").read_bytes() == old_pointer
    assert bundle.exists()
    assert not (output / "versions").exists()
