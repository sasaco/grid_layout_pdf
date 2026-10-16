"""Exact decoded-pixel regression for the five approved standard report pages."""

from hashlib import sha256
import importlib.metadata
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageChops
import pytest


ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).parent / "representative"


def _assert_pixels_equal(expected: Image.Image, actual: Image.Image, artifacts: Path) -> None:
    """Keep actual/diff evidence on a pixel, size or mode mismatch."""
    if expected.mode == actual.mode and expected.size == actual.size and expected.tobytes() == actual.tobytes():
        return
    artifacts.mkdir(parents=True, exist_ok=True)
    actual_path, diff_path = artifacts / "actual.png", artifacts / "diff.png"
    actual.save(actual_path)
    size = (max(expected.width, actual.width), max(expected.height, actual.height))
    with Image.new("RGB", size, "magenta") as before, Image.new("RGB", size, "magenta") as after:
        before.paste(expected.convert("RGB"), (0, 0))
        after.paste(actual.convert("RGB"), (0, 0))
        with ImageChops.difference(before, after) as difference:
            difference.save(diff_path)
    pytest.fail(f"Decoded pixels differ: expected {expected.mode} {expected.size}, "
                f"actual {actual.mode} {actual.size}; actual={actual_path}; diff={diff_path}", pytrace=False)


def test_standard_report_matches_all_approved_golden_pixels(tmp_path):
    manifest_path = BASELINE / "manifest.json"
    assert manifest_path.is_file(), "Approved visual baseline is missing; see tests/visual/README.md"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["render"] == {"matrix": [1.5, 1.5], "alpha": False, "mode": "RGB"}
    assert manifest["report"]["variant"] == "standard"
    assert len(manifest["pages"]) == 5
    for distribution, pinned in manifest["tools"].items():
        assert importlib.metadata.version(distribution) == pinned, (
            f"Golden tool version changed: {distribution}; see tests/visual/README.md")
    font = ROOT / manifest["font"]["path"]
    assert sha256(font.read_bytes()).hexdigest() == manifest["font"]["sha256"], "Golden font bytes changed"
    image_path = ROOT / manifest["report"]["image_path"]
    assert sha256(image_path.read_bytes()).hexdigest() == manifest["report"]["image_sha256"], "Golden input image changed"

    source = ROOT / manifest["report"]["example"]
    spec = importlib.util.spec_from_file_location("representative_visual_example", source)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    example.write_report(tmp_path, font, image_path=image_path, variant="standard", preview=True)
    actual_paths = sorted((tmp_path / "previews").glob("representative-report-page-*.png"))
    assert [path.name for path in actual_paths] == [page["file"] for page in manifest["pages"]], (
        f"Golden page count or filenames changed; generated images: {tmp_path / 'previews'}")
    for page, actual_path in zip(manifest["pages"], actual_paths, strict=True):
        expected_path = BASELINE / page["file"]
        assert expected_path.is_file(), f"Approved baseline missing: {expected_path}"
        assert sha256(expected_path.read_bytes()).hexdigest() == page["sha256"], f"Baseline bytes changed: {expected_path}"
        with Image.open(expected_path) as expected, Image.open(actual_path) as actual:
            assert expected.mode == page["mode"] == "RGB"
            assert list(expected.size) == page["size"]
            assert sha256(expected.tobytes()).hexdigest() == page["pixel_sha256"]
            _assert_pixels_equal(expected, actual, tmp_path / "differences" / actual_path.stem)


def test_pixel_comparison_detects_one_changed_pixel_and_writes_evidence(tmp_path):
    with Image.new("RGB", (4, 3), (255, 255, 255)) as expected:
        actual = expected.copy()
        actual.putpixel((2, 1), (254, 255, 255))
        with actual, pytest.raises(pytest.fail.Exception) as caught:
            _assert_pixels_equal(expected, actual, tmp_path)
        assert str(tmp_path / "actual.png") in str(caught.value)
        assert str(tmp_path / "diff.png") in str(caught.value)
        with Image.open(tmp_path / "actual.png") as saved, Image.open(tmp_path / "diff.png") as difference:
            assert saved.getpixel((2, 1)) == (254, 255, 255)
            assert difference.getbbox() == (2, 1, 3, 2)
        assert expected.getpixel((2, 1)) == (255, 255, 255)


def test_pixel_comparison_ignores_png_compression_bytes(tmp_path):
    first, second = tmp_path / "uncompressed.png", tmp_path / "compressed.png"
    with Image.new("RGB", (20, 20), (30, 80, 140)) as pixels:
        pixels.save(first, compress_level=0)
        pixels.save(second, compress_level=9)
    assert first.read_bytes() != second.read_bytes()
    with Image.open(first) as expected, Image.open(second) as actual:
        _assert_pixels_equal(expected, actual, tmp_path / "no-difference")
    assert not (tmp_path / "no-difference").exists()
