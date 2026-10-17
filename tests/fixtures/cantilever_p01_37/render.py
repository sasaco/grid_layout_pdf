"""Build a validated immutable output bundle; publish only after visual review."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from gridlayoutpdf import layout_trace, render_pdf


def _sibling(name):
    key = f"cantilever_fixture_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, Path(__file__).with_name(f"{name}.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


builder = _sibling("builder")


def _hash(path):
    return sha256(path.read_bytes()).hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _input_hashes(source_pages, fonts):
    root = builder.REPOSITORY_ROOT
    paths = [builder.FIXTURE_ROOT / "manifest.json", Path(__file__), Path(builder.__file__),
             builder.FIXTURE_ROOT / "verify.py", builder.FIXTURE_ROOT / "verify_appearance.py",
             builder.FIXTURE_ROOT / "appearance.py",builder.FIXTURE_ROOT / "font-profile.json",
             builder.FIXTURE_ROOT / "source-layout.json",
             root / builder.load_manifest()["source"]["path"], root / "uv.lock", root / "pyproject.toml"]
    paths.extend((root / "src/gridlayoutpdf").rglob("*.py"))
    paths.extend(fonts.resolve(name).path for name in builder.font_profile()["fonts"])
    for number in source_pages:
        paths.extend(builder.FIXTURE_ROOT / folder / f"p{number:02}.json" for folder in ("pages", "expected"))
    paths.extend(path for path in (builder.FIXTURE_ROOT / "assets").rglob("*")
                 if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    hashes = {str(path.resolve()): _hash(path) for path in paths}
    source = root / builder.load_manifest()["source"]["path"]
    if hashes[str(source.resolve())] != builder.load_manifest()["source"]["sha256"]:
        raise ValueError("original source PDF hash changed")
    return hashes


def _previews(directory, source_pages):
    import pymupdf
    destination = directory / "previews"
    destination.mkdir()
    for variant in ("normal", "grid"):
        with pymupdf.open(directory / f"{variant}.pdf") as pdf:
            if len(pdf) != len(source_pages):
                raise ValueError("preview source-page count changed")
            for page, source in zip(pdf, source_pages):
                page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(
                    destination / f"{variant}-p{source:02}.png")


def _verify_pdf(path, **kwargs):
    report=_sibling("verify").verify_pdf(path, **kwargs)
    report["appearance"]=_sibling("verify_appearance").verify_appearance(
        path,source_pages=kwargs["source_pages"],trace=kwargs["trace"])
    return report


def _tool_versions():
    return {name: importlib.metadata.version(name) for name in ("reportlab", "pillow", "pymupdf")}


def prepare_bundle(output, fonts, *, source_pages=builder.SOURCE_PAGES):
    """Produce all artifacts in staging, never change current.json here.

    The caller must visually inspect both variants and pass their exact hashes
    to activate_bundle. A proof subset is permanently ineligible for activation.
    """
    selected = builder._selection(source_pages)
    inputs = _input_hashes(selected, fonts)
    pages = builder.layout_report(fonts, source_pages=selected)
    scene_image_count = _sibling("verify").verify_scene_images(
        pages, source_pages=selected, manifest=builder.load_manifest())
    trace = layout_trace(pages, fonts)
    output = Path(output).resolve()
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex
    directory = output / ".staging" / identifier
    directory.mkdir(parents=True)
    render_pdf(pages, directory / "normal.pdf", fonts)
    render_pdf(pages, directory / "grid.pdf", fonts, debug_grid=True)
    _write_json(directory / "trace.json", trace)
    _write_json(directory / "mapping.json", [{"source_page": source, "output_page": index,
                                              "block_id": f"p{source:02}"}
                                             for index, source in enumerate(selected, 1)])
    _previews(directory, selected)
    checks = {"scene_image_count": scene_image_count}
    for variant in ("normal", "grid"):
        checks[variant] = _verify_pdf(directory / f"{variant}.pdf", source_pages=selected,
                                      trace=trace, grid=variant == "grid", manifest=builder.load_manifest())
    if _input_hashes(selected, fonts) != inputs:
        raise ValueError("input hashes changed during bundle generation")
    artifacts = {path.relative_to(directory).as_posix(): _hash(path)
                 for path in sorted(directory.rglob("*")) if path.is_file()}
    _write_json(directory / "bundle.json", {
        "schema_version": 1, "bundle_id": identifier,
        "status": "content-verified-awaiting-visual-review" if selected == builder.SOURCE_PAGES else "proof-subset",
        "source_pages": list(selected), "inputs": inputs, "artifacts": artifacts, "checks": checks,
        "tools": _tool_versions(),
        "python": sys.version,
    })
    return directory


def _check_hashes(directory, artifacts):
    for relative, digest in artifacts.items():
        path = (directory / relative).resolve()
        if directory not in path.parents or not path.is_file() or _hash(path) != digest:
            raise ValueError(f"artifact hash mismatch: {relative}")


def _commit_pointer(output, pointer):
    temporary = output / f".current-{uuid4().hex}.json"
    _write_json(temporary, pointer)
    os.replace(temporary, output / "current.json")


def activate_bundle(output, bundle, visual_review):
    """Atomically point readers at one complete reviewed 37-page version."""
    output, directory = Path(output).resolve(), Path(bundle).resolve()
    if directory.parent != output / ".staging":
        raise ValueError("bundle must be inside this output's staging directory")
    manifest = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
    if tuple(manifest["source_pages"]) != builder.SOURCE_PAGES:
        raise ValueError("only complete 37-page bundles can become current")
    checks = manifest.get("checks", {})
    if (manifest.get("status") != "content-verified-awaiting-visual-review"
            or any(checks.get(variant, {}).get("source_pages") != list(builder.SOURCE_PAGES)
                   or checks.get(variant, {}).get("complete_37_pages") is not True
                   or checks.get(variant, {}).get("variant") != variant for variant in ("normal", "grid"))):
        raise ValueError("complete 37-page content verification is required")
    if manifest.get("tools") != _tool_versions() or manifest.get("python") != sys.version:
        raise ValueError("rendering tools changed since bundle preparation")
    if (visual_review.get("result") != "pass" or not visual_review.get("reviewer")
            or not visual_review.get("reviewed_at") or visual_review.get("artifacts") != manifest["artifacts"]):
        raise ValueError("visual review must approve the exact artifact hashes")
    _check_hashes(directory, manifest["artifacts"])
    for name, digest in manifest["inputs"].items():
        if not Path(name).is_file() or _hash(Path(name)) != digest:
            raise ValueError(f"input hash changed since visual review: {name}")
    expected_previews = {f"previews/{variant}-p{source:02}.png"
                         for variant in ("normal", "grid") for source in builder.SOURCE_PAGES}
    required = expected_previews | {"normal.pdf", "grid.pdf", "trace.json", "mapping.json"}
    if not required.issubset(manifest["artifacts"]):
        raise ValueError("37-page bundle is missing required artifacts")
    for variant in ("normal", "grid"):
        _verify_pdf(directory / f"{variant}.pdf", source_pages=builder.SOURCE_PAGES,
                    trace=directory / "trace.json", grid=variant == "grid", manifest=builder.load_manifest())
    _write_json(directory / "visual-review.json", visual_review)
    manifest["visual_review_sha256"] = _hash(directory / "visual-review.json")
    manifest["status"] = "content-and-visual-verified"
    _write_json(directory / "bundle.json", manifest)
    destination = output / "versions" / directory.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    directory.rename(destination)
    _commit_pointer(output, {"schema_version": 1, "bundle_id": destination.name,
                             "bundle_sha256": _hash(destination / "bundle.json")})
    return destination


def resolve_current(output):
    """Read the pointer once and return that immutable bundle directory."""
    output = Path(output).resolve()
    pointer = json.loads((output / "current.json").read_text(encoding="utf-8"))
    directory = (output / "versions" / pointer["bundle_id"]).resolve()
    if directory.parent != output / "versions":
        raise ValueError("current bundle path escapes versions")
    if _hash(directory / "bundle.json") != pointer["bundle_sha256"]:
        raise ValueError("current bundle manifest hash mismatch")
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=builder.REPOSITORY_ROOT / "build/reports/cantilever-p01-37")
    parser.add_argument("--pages", help="comma-separated original pages; omitted means all 37")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--activate", type=Path, help="previously prepared complete staging bundle")
    parser.add_argument("--visual-review", type=Path)
    options = parser.parse_args(argv)
    if options.activate:
        if not options.visual_review:
            parser.error("--activate requires --visual-review")
        review = json.loads(options.visual_review.read_text(encoding="utf-8"))
        print(activate_bundle(options.output, options.activate, review))
    else:
        selected = tuple(int(item) for item in options.pages.split(",")) if options.pages else builder.SOURCE_PAGES
        print(prepare_bundle(options.output, builder.fixture_fonts(options.font), source_pages=selected))


if __name__ == "__main__":
    main()
