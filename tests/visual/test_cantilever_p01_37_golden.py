"""Pixel regression for all 37 independently checked and visually reviewed pages."""

from hashlib import sha256
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image, ImageChops
import pytest


ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).parent / "cantilever_p01_37"
FIXTURE = ROOT / "tests/fixtures/cantilever_p01_37"


def test_all_37_pages_match_approved_pixels(tmp_path):
    record = json.loads((BASELINE / "manifest.json").read_text(encoding="utf-8"))
    assert record["schema_version"] == 1
    assert record["source_pages"] == list(range(1, 38))
    assert record["render"] == {"matrix": [2, 2], "alpha": False, "mode": "RGB"}
    approval = record["approval"]
    assert approval["result"] == "pass" and approval["reviewer"] and approval["reviewed_at"]
    assert set(approval["viewed_images"]) == {
        f"previews/{variant}-p{number:02}.png"
        for variant in ("normal", "grid") for number in range(1, 38)
    }
    for name, version in record["tools"].items():
        assert importlib.metadata.version(name) == version, f"Rendering tool changed: {name}"
    for relative, digest in record["source_inputs"].items():
        assert sha256((ROOT / relative).read_bytes()).hexdigest() == digest, relative
    assert [page["file"] for page in record["pages"]] == [f"normal-p{n:02}.png" for n in range(1, 38)]

    key = "cantilever_golden_render"
    spec = importlib.util.spec_from_file_location(key, FIXTURE / "render.py")
    renderer = importlib.util.module_from_spec(spec)
    sys.modules[key] = renderer
    spec.loader.exec_module(renderer)
    generated = renderer.prepare_bundle(tmp_path, renderer.builder.fixture_fonts())
    assert not (tmp_path / "current.json").exists(), "Regression tests never publish output"
    for page in record["pages"]:
        baseline_path = BASELINE / page["file"]
        actual_path = generated / "previews" / page["file"]
        assert sha256(baseline_path.read_bytes()).hexdigest() == page["sha256"]
        assert approval["artifacts"][f"previews/{page['file']}"] == page["sha256"]
        with Image.open(baseline_path) as expected, Image.open(actual_path) as actual:
            assert expected.mode == page["mode"] == "RGB"
            assert list(expected.size) == page["size"] == [1190, 1684]
            assert sha256(expected.tobytes()).hexdigest() == page["pixel_sha256"]
            if actual.mode == expected.mode and actual.size == expected.size and actual.tobytes() == expected.tobytes():
                continue
            evidence = tmp_path / "differences" / baseline_path.stem
            evidence.mkdir(parents=True)
            actual.save(evidence / "actual.png")
            size = (max(expected.width, actual.width), max(expected.height, actual.height))
            with Image.new("RGB", size, "magenta") as before, Image.new("RGB", size, "magenta") as after:
                before.paste(expected.convert("RGB"), (0, 0))
                after.paste(actual.convert("RGB"), (0, 0))
                with ImageChops.difference(before, after) as diff:
                    diff.save(evidence / "diff.png")
            pytest.fail(f"{page['file']}: pixels differ; actual={evidence / 'actual.png'}; "
                        f"diff={evidence / 'diff.png'}", pytrace=False)
