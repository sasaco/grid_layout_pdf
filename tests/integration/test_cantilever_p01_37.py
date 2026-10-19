"""Independent oracle tests; source controls are not reproduction outputs."""

from collections import Counter
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pymupdf
import pytest
from PIL import Image

from gridlayoutpdf import Line, RasterImage, ScenePage, Text, layout_trace, render_pdf


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/cantilever_p01_37"
PROOF = (16, 17, 26, 30, 36)


def _fixture_module(name):
    spec = importlib.util.spec_from_file_location(f"cantilever_p01_37_test_{name}", FIXTURE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# p30-p35 are deferred to FR-027 Step 9 (2026-10-20 user decision c).
deferred = _fixture_module("deferred")


@pytest.mark.parametrize("flags,optimize", [("-O", None), ("-OO", None), (None, "1")])
def test_oracle_refuses_optimized_python(flags, optimize, tmp_path):
    env = os.environ.copy()
    env.pop("PYTHONOPTIMIZE", None)
    if optimize is not None:
        env["PYTHONOPTIMIZE"] = optimize
    command = [sys.executable, *([flags] if flags else []), "-c",
               "import runpy,sys; runpy.run_path(sys.argv[1]); print('UNVERIFIED')",
               str(FIXTURE / "verify.py")]
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0, "Optimized Python silently removed the content gates"
    assert "requires assertions enabled" in result.stderr
    assert "UNVERIFIED" not in result.stdout


def test_unoptimized_oracle_keeps_missing_page_gate(tmp_path):
    env = os.environ.copy()
    env.pop("PYTHONOPTIMIZE", None)
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy,sys; m=runpy.run_path(sys.argv[1]); "
         "m['verify_scene_images']([], source_pages=(1,), manifest={'figures': []})",
         str(FIXTURE / "verify.py")],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "AssertionError" in result.stderr
    assert "requires assertions enabled" not in result.stderr


@pytest.fixture(scope="module")
def verifier():
    spec = importlib.util.spec_from_file_location("cantilever_verify", FIXTURE / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def oracle(page):
    return json.loads((FIXTURE / f"expected/p{page:02}.json").read_text(encoding="utf-8"))


def _source_contains_glyph(char, box):
    x0, y0, x1, y1 = char["bbox"]
    return box[0] <= (x0 + x1) / 2 < box[2] and box[1] <= (y0 + y1) / 2 < box[3]


@pytest.mark.parametrize("number", range(1, 38))
def test_expected_items_cover_actual_source_glyphs_once(number):
    source = next((ROOT / "tests/output").glob("13_*.pdf"))
    expected = oracle(number)
    assert sha256(source.read_bytes()).hexdigest() == expected["source_sha256"]
    assets = json.loads((FIXTURE / "assets/metadata.json").read_text(encoding="utf-8"))["figures"]
    figures = [asset["source_bbox"] for asset in assets if asset["source_page"] == number]
    with pymupdf.open(source) as pdf:
        chars = [char for block in pdf[number - 1].get_text("rawdict")["blocks"]
                 for line in block.get("lines", []) for span in line["spans"]
                 for char in span["chars"] if not char["c"].isspace()]
    omitted = [char for char in chars if _source_contains_glyph(char, (500, 30, 570, 62))]
    assert "".join(char["c"] for char in omitted) == f"13-{number}"
    chars = [char for char in chars if char not in omitted
             and not any(_source_contains_glyph(char, box) for box in figures)]
    assert Counter(char["c"] for char in chars) == Counter(expected["source_character_inventory"])
    covered = Counter()
    for block in expected["blocks"]:
        for item in block.get("cells", [block]):
            indexes = [index for index, char in enumerate(chars)
                       if _source_contains_glyph(char, item["source_bbox"]) and char["c"] != "※"]
            assert Counter(chars[index]["c"] for index in indexes) == Counter(
                char for char in item["text"] if not char.isspace()), item["id"]
            covered.update(indexes)
    assert covered == Counter({index: 1 for index, char in enumerate(chars) if char["c"] != "※"})
    assert sum(char["c"] == "※" for char in chars) == expected["marker_count"]


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("cantilever_builder_oracle_test", FIXTURE / "builder.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def oracle_items(pages):
    return sum(len(block.get("cells", [block])) for number in pages for block in oracle(number)["blocks"])


@pytest.fixture(scope="module")
def reports(builder):
    """Lay out each page selection once; a layout failure is re-raised each time."""
    fonts = builder.fixture_fonts()
    cache = {}

    def report(pages):
        pages = tuple(pages)
        if pages not in cache:
            try:
                laid = builder.layout_report(fonts, source_pages=pages)
                cache[pages] = (fonts, laid, layout_trace(laid, fonts), builder.load_manifest())
            except Exception as exc:
                cache[pages] = exc
        if isinstance(cache[pages], Exception):
            raise cache[pages]
        return cache[pages]
    return report


@pytest.fixture(scope="module")
def available_report(reports):
    """p1-p37 without the deferred p30-p35; page indexes below p30 are unchanged."""
    return reports(deferred.AVAILABLE_PAGES)


@pytest.mark.parametrize("selection", deferred.selections(deferred.ALL_PAGES))
@pytest.mark.parametrize("grid", [False, True])
def test_all_37_pages_from_public_api(reports, verifier, tmp_path, grid, selection):
    fonts, pages, trace, manifest = reports(selection)
    path = tmp_path / "complete.pdf"
    render_pdf(pages, path, fonts, debug_grid=grid)
    result = verifier.verify_pdf(path, source_pages=selection, trace=trace, grid=grid, manifest=manifest)
    assert result["complete_37_pages"] is (selection == deferred.ALL_PAGES)
    assert oracle_items(deferred.ALL_PAGES) == 3345
    assert result["verified_items"] == oracle_items(selection)


def test_coordinated_expected_and_native_text_change_fails_original_gate(builder, verifier, tmp_path, monkeypatch):
    """An internally consistent false number must fail before PDF self-checks."""
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(1,))
    trace = layout_trace(pages, fonts)
    regions, _ = verifier._trace_regions(trace["pages"][0])
    x0, y0, x1, y1 = regions["p01-dead-loads.r1.c3"]
    commands = []
    changed = 0
    for command in pages[0].commands:
        if (isinstance(command, Text) and command.text == "1530.0"
                and x0 <= command.x < x1 and y0 <= command.y < y1):
            command = replace(command, text="1350.0")
            changed += 1
        commands.append(command)
    assert changed == 1
    record = oracle(1)
    cell = next(item for block in record["blocks"] for item in block.get("cells", [block])
                if item["id"] == "p01-dead-loads.r1.c3")
    cell["text"] = "1350.0"
    expected = tmp_path / "expected"
    expected.mkdir()
    (expected / "p01.json").write_text(json.dumps(record), encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "metadata.json").write_bytes((FIXTURE / "assets/metadata.json").read_bytes())
    monkeypatch.setattr(verifier, "EXPECTED", expected)
    path = tmp_path / "coordinated-wrong-value.pdf"
    render_pdf((ScenePage(pages[0].profile, tuple(commands), pages[0].metadata),), path, fonts)
    with pytest.raises(AssertionError, match="original text order"):
        verifier.verify_pdf(path, source_pages=(1,), trace=trace, manifest=builder.load_manifest())


@pytest.mark.parametrize("selection", deferred.selections(deferred.ALL_PAGES))
def test_scene_images_have_independent_allowlist_validation(reports, verifier, selection):
    _, pages, _, manifest = reports(selection)
    assert hasattr(verifier, "verify_scene_images"), "scene image bytes/provenance validation is absent"
    # All 16 figures are outside the deferred p30-p35.
    assert verifier.verify_scene_images(pages, selection, manifest) == 16


def test_native_reordered_headings_are_rejected(builder,verifier,tmp_path):
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts,source_pages=(3,))
    trace = layout_trace(pages, fonts)
    regions, _ = verifier._trace_regions(trace["pages"][0])
    first, second = "p03-title", "p03-b"
    delta = regions[second][1] - regions[first][1]
    commands = []
    moved = Counter()
    for command in pages[0].commands:
        for key, offset in ((first, delta), (second, -delta)):
            x0, y0, x1, y1 = regions[key]
            if isinstance(command, Text) and x0 <= command.x <= x1 and y0 <= command.y <= y1:
                command = replace(command, y=command.y + offset)
                moved[key] += 1
                break
        commands.append(command)
    assert moved[first] and moved[second]
    # Keep each semantic ID with its moved native text. The inspector must
    # reject changed order even when the supplied trace is self-consistent.
    def move_trace(value):
        if isinstance(value, dict):
            if value.get("block_id") in (first, second):
                value["y_pt"] += delta if value["block_id"] == first else -delta
            for child in value.values():
                move_trace(child)
        elif isinstance(value, list):
            for child in value:
                move_trace(child)
    move_trace(trace)
    path = tmp_path / "native-order.pdf"
    render_pdf((ScenePage(pages[0].profile,tuple(commands),pages[0].metadata),),path,fonts)
    with pytest.raises(AssertionError,match="source block order"):
        verifier.verify_pdf(path,source_pages=(3,),trace=trace)


@pytest.mark.parametrize("corruption", ["result-anchor", "unit-anchor"])
def test_all_train_equation_shared_anchors(available_report,verifier,tmp_path,corruption):
    fonts,pages,trace,manifest = available_report
    page = pages[2]
    commands = list(page.commands)
    regions,_ = verifier._trace_regions(trace["pages"][2])
    x0,y0,x1,y1 = regions["p03-equation-001"]
    index = next(i for i,c in enumerate(commands) if isinstance(c,Text) and y0<=c.y<=y1
                 and (c.text=="kN" if corruption=="unit-anchor" else c.text=="243.87"))
    commands[index] = replace(commands[index],x=commands[index].x+2)
    path = tmp_path / "native-train-anchor.pdf"
    render_pdf([ScenePage(page.profile,tuple(commands),page.metadata)],path,fonts)
    with pytest.raises(AssertionError,match="anchor"):
        verifier.verify_pdf(path,source_pages=(3,),trace={"pages":[trace["pages"][2]]},manifest=manifest)


def _source_anchor_control(verifier, number):
    record = oracle(number)
    source = next((ROOT / "tests/output").glob("13_*.pdf"))
    assert sha256(source.read_bytes()).hexdigest() == record["source_sha256"]
    with pymupdf.open(source) as pdf:
        chars = verifier._chars(pdf[number - 1])
        rules = verifier._black_rules(pdf[number - 1])
    regions = {item["id"]: item["source_bbox"] for block in record["blocks"]
               for item in (block["cells"] if block["kind"] == "table" else [block])}
    return chars, rules, record, regions


@pytest.mark.parametrize("number", range(3, 9))
def test_train_anchor_inspector_accepts_actual_original_positions(verifier, number):
    chars, _, record, regions = _source_anchor_control(verifier, number)
    verifier._train_anchors(chars, record, regions)


@pytest.mark.parametrize("number", range(16, 20))
def test_dense_anchor_inspector_accepts_actual_original_bars(verifier, number):
    chars, rules, _, regions = _source_anchor_control(verifier, number)
    verifier._dense_anchors(chars, rules, regions, f"p{number:02}")


@pytest.mark.parametrize("kind", ["result", "unit", "equal"])
@pytest.mark.parametrize("all_equations", [False, True])
def test_train_anchor_inspector_rejects_shift_even_if_all_equations_still_align(verifier, kind, all_equations):
    chars, _, record, regions = _source_anchor_control(verifier, 4)
    formulas = [block for block in record["blocks"] if block["kind"] == "equation"]
    for formula in formulas if all_equations else formulas[:1]:
        ordered = [char for line, _ in verifier._ordered_lines(verifier._inside(chars, regions[formula["id"]]), (1, 0))
                   for char in line if not char["c"].isspace()]
        text = "".join(char["c"] for char in ordered)
        result = verifier.re.search(r"(\d+\.\d+)kN$", text)
        selected = (ordered[result.end(1)-1] if kind == "result" else ordered[-2] if kind == "unit"
                    else next(char for char in ordered if char["c"] == "＝"))
        x0, y0, x1, y1 = selected["bbox"]
        selected["bbox"] = (x0 + .25, y0, x1 + .25, y1)
        selected["origin"] = (selected["origin"][0] + .25, selected["origin"][1])
    with pytest.raises(AssertionError, match=f"{kind} anchor"):
        verifier._train_anchors(chars, record, regions)


@pytest.mark.parametrize("corruption", ["shortened", "shifted", "missing"])
def test_dense_bar_inspector_rejects_actual_source_geometry_changes(verifier, corruption):
    chars, rules, _, regions = _source_anchor_control(verifier, 16)
    index = next(index for index, rule in enumerate(rules)
                 if abs(rule[0] - rule[2]) < .01 and abs(rule[1] - rule[3]) > 100)
    x0, y0, x1, y1 = rules[index]
    if corruption == "shortened":
        rules[index] = (x0, min(y0, y1), x1, max(y0, y1) - 20)
    elif corruption == "shifted":
        rules[index] = (x0 + .25, y0, x1 + .25, y1)
    else:
        rules.pop(index)
    with pytest.raises(AssertionError, match="bar"):
        verifier._dense_anchors(chars, rules, regions, "p16")


@pytest.mark.parametrize("number", [4, 16])
def test_anchor_geometry_rejects_untrusted_original_bytes(verifier, monkeypatch, number):
    chars, rules, record, regions = _source_anchor_control(verifier, number)
    monkeypatch.setattr(verifier, "_SOURCE_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="source PDF hash"):
        if number == 4:
            verifier._train_anchors(chars, record, regions)
        else:
            verifier._dense_anchors(chars, rules, regions, "p16")


def test_introductory_merged_table_rules(available_report,verifier,tmp_path):
    fonts,pages,trace,manifest = available_report
    page = pages[0]
    commands = list(page.commands)
    regions,_ = verifier._trace_regions(trace["pages"][0])
    x0,y0,x1,y1 = regions["p01-dead-loads.r0.c0"]
    index = next(i for i,c in enumerate(commands) if isinstance(c,Line)
                 and abs(c.y1-y0)<.6 and abs(c.y2-y0)<.6 and abs(c.x1-x0)<.6)
    commands.pop(index)
    path = tmp_path / "native-intro-rule.pdf"
    render_pdf([ScenePage(page.profile,tuple(commands),page.metadata)],path,fonts)
    with pytest.raises(AssertionError,match="rule"):
        verifier.verify_pdf(path,source_pages=(1,),trace={"pages":[trace["pages"][0]]},manifest=manifest)


@pytest.mark.parametrize("selection", deferred.selections((30, 36)))
@pytest.mark.parametrize("grid", [False, True])
def test_complete_rotated_proof_pages_from_public_api(builder, verifier, tmp_path, grid, selection):
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=selection)
    path = tmp_path / "rotated-proof.pdf"
    render_pdf(pages, path, fonts, debug_grid=grid)
    result = verifier.verify_pdf(path, source_pages=selection, trace=layout_trace(pages, fonts), grid=grid)
    assert oracle_items((30, 36)) == 574
    assert result["verified_items"] == oracle_items(selection)
    assert result["complete_37_pages"] is False


@pytest.mark.parametrize("grid", [False, True])
@pytest.mark.parametrize("source_page,item_count", [(16, 14), (17, 12), (26, 195)])
def test_complete_dense_proof_pages_from_public_api(builder, verifier, tmp_path, grid, source_page, item_count):
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(source_page,))
    path = tmp_path / "dense-proof.pdf"
    render_pdf(pages, path, fonts, debug_grid=grid)
    result = verifier.verify_pdf(path, source_pages=(source_page,), trace=layout_trace(pages, fonts), grid=grid)
    assert result["verified_items"] == item_count
    assert result["complete_37_pages"] is False


@pytest.mark.parametrize("source_page", [18, 19])
def test_dense_native_pages_preserve_the_union_of_overlapping_original_bars(builder, verifier, tmp_path, source_page):
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(source_page,))
    path = tmp_path / f"dense-union-p{source_page:02}.pdf"
    render_pdf(pages, path, fonts)
    result = verifier.verify_pdf(path, source_pages=(source_page,), trace=layout_trace(pages, fonts))
    assert result["verified_items"] == len(oracle(source_page)["blocks"])
    assert result["complete_37_pages"] is False


ROTATED_MERGED_HEADER = {30: "p30-combinations-md.r0.c1", 36: "p36-combinations-summary.r0.c1"}


_ROTATED_CORRUPTIONS = ("small-body", "lost-rule", "flat-script", "raised-script", "split-merged-cell")


# p36 keeps the rotated-table checks alive; its table has no script runs, so the
# two script corruptions exist only on the deferred p30.
@pytest.mark.parametrize("corruption,page", [
    *((corruption, 36) for corruption in _ROTATED_CORRUPTIONS if "script" not in corruption),
    *(pytest.param(corruption, 30, marks=deferred.DEFERRED) for corruption in _ROTATED_CORRUPTIONS),
])
def test_native_pdf_visual_corruptions_are_detected(builder, verifier, tmp_path, corruption, page):
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(page,))
    commands = list(pages[0].commands)
    if corruption == "small-body":
        index = next(i for i, c in enumerate(commands) if isinstance(c, Text) and c.text == "5577.15")
        command = commands[index]
        commands[index] = replace(command, style=replace(command.style, size=6.5))
    elif corruption in ("flat-script", "raised-script"):
        index = next(i for i, c in enumerate(commands) if isinstance(c, Text) and c.text == "R" and c.style.size < 8)
        base = next(c for c in reversed(commands[:index]) if isinstance(c, Text) and c.text == "L")
        commands[index] = replace(commands[index], x=base.x - (2 if corruption == "raised-script" else 0))
    elif corruption == "split-merged-cell":
        regions, _ = verifier._trace_regions(layout_trace(pages, fonts)["pages"][0])
        x0, y0, x1, y1 = regions[ROTATED_MERGED_HEADER[page]]
        commands.append(Line(x0, (y0+y1)/2, x1, (y0+y1)/2, .4))
    else:
        # Drop a real table outer edge, keeping all text, metadata and pages.
        index = max((i for i, c in enumerate(commands) if isinstance(c, Line)),
                    key=lambda i: commands[i].x1)
        commands.pop(index)
    broken = (ScenePage(pages[0].profile, tuple(commands), pages[0].metadata),)
    path = tmp_path / "broken-layout.pdf"
    render_pdf(broken, path, fonts)
    with pytest.raises(AssertionError, match=f"p{page}.*(size|script|rule|shrunk)"):
        verifier.verify_pdf(path, source_pages=(page,), trace=layout_trace(pages, fonts))


@pytest.mark.parametrize("corruption", ["missing-header", "extra-row", "extra-column"])
def test_dense_tables_preserve_selective_source_rules(builder, verifier, tmp_path, corruption):
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(26,))
    trace = layout_trace(pages, fonts)
    regions, _ = verifier._trace_regions(trace["pages"][0])
    table = regions["p26-safety-b"]
    x0, y0, x1, y1 = table
    commands = list(pages[0].commands)
    if corruption == "missing-header":
        index = next(i for i, c in enumerate(commands) if isinstance(c, Line)
                     and abs(c.y1-y0) < .6 and abs(c.y2-y0) < .6)
        commands.pop(index)
    elif corruption == "extra-row":
        y = regions["p26-safety-b.r2.c2"][1]
        commands.append(Line(x0, y, x1, y, .4))
    else:
        x = regions["p26-safety-b.r1.c3"][0]
        commands.append(Line(x, y0, x, y1, .4))
    path = tmp_path / "bad-table-rules.pdf"
    render_pdf((ScenePage(pages[0].profile, tuple(commands), pages[0].metadata),), path, fonts)
    with pytest.raises(AssertionError, match="p26.*rule"):
        verifier.verify_pdf(path, source_pages=(26,), trace=trace)


@pytest.mark.parametrize("corruption", ["equal-anchor", "result-anchor", "bar-extent"])
def test_dense_equation_alignment_and_group_bars_are_verified(builder, verifier, tmp_path, corruption):
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(16,))
    trace = layout_trace(pages, fonts)
    regions, _ = verifier._trace_regions(trace["pages"][0])
    commands = list(pages[0].commands)
    if corruption == "equal-anchor":
        x0, y0, x1, y1 = regions["p16-movable-rm"]
        index = next(i for i, c in enumerate(commands) if isinstance(c, Text) and c.text == "＝" and y0<c.y<y1)
        commands[index] = replace(commands[index], x=commands[index].x+2)
    elif corruption == "result-anchor":
        index = next(i for i, c in enumerate(commands) if isinstance(c, Text) and "596.80" in c.text)
        commands[index] = replace(commands[index], x=commands[index].x-2)
    else:
        index = max((i for i, c in enumerate(commands) if isinstance(c, Line)), key=lambda i: commands[i].y2)
        commands[index] = replace(commands[index], y2=commands[index].y2-20)
    path = tmp_path / "bad-equation-layout.pdf"
    render_pdf((ScenePage(pages[0].profile, tuple(commands), pages[0].metadata),), path, fonts)
    with pytest.raises(AssertionError, match="p16.*(anchor|bar)"):
        verifier.verify_pdf(path, source_pages=(16,), trace=trace)


def source_control(tmp_path, pages=PROOF):
    """Test the inspector with the source, never label this a rendered result."""
    path = tmp_path / "source-control.pdf"
    trace = {"oracle_regions": [], "source_pages": list(pages)}
    with pymupdf.open(next((ROOT / "tests/output").glob("13_*.pdf"))) as source:
        with pymupdf.open() as control:
            for number in pages:
                control.insert_pdf(source, from_page=number - 1, to_page=number - 1)
                page = control[-1]
                page.add_redact_annot((500, 35, 565, 60), fill=(1, 1, 1))
                page.apply_redactions()
                regions = {}
                for block in oracle(number)["blocks"]:
                    items = block["cells"] if block["kind"] == "table" else [block]
                    for item in items:
                        regions[item["id"]] = item["source_bbox"]
                trace["oracle_regions"].append(regions)
            control.save(path)
    return path, trace


def test_independent_oracle_accounts_for_every_source_character(verifier):
    for file in sorted((FIXTURE / "expected").glob("p[0-9][0-9].json")):
        number = int(file.stem[1:])
        expected = oracle(number)
        chars = Counter()
        for block in expected["blocks"]:
            items = block["cells"] if block["kind"] == "table" else [block]
            for item in items:
                chars.update(c for c in item["text"] if not c.isspace())
        chars.update("※" * expected["marker_count"])
        assert chars == Counter(expected["source_character_inventory"]), number
        assert expected["provenance"]["review_status"] == "source-reviewed"


def test_source_formula_and_case_totals_are_preserved():
    assert sum(sum(b["kind"] == "equation" for b in oracle(n)["blocks"]) for n in range(3, 9)) == 114
    assert sum(next(b for b in oracle(n)["blocks"] if b["kind"] == "table")["body_rows"] for n in range(30, 38)) == 124
    assert sum(oracle(n)["hash_placeholder_count"] for n in range(1,38)) == 63
    assert len(list((FIXTURE / "expected").glob("p[0-9][0-9].json"))) == 37


@pytest.mark.parametrize("mutation", ["value", "sign", "missing", "duplicate", "swapped-cells"])
def test_native_cell_content_corruptions(available_report, verifier, tmp_path, mutation):
    fonts,pages,trace,manifest = available_report
    page = pages[25]
    commands = list(page.commands)
    index = next(i for i,c in enumerate(commands) if isinstance(c,Text) and c.text == "-19.42")
    command = commands[index]
    if mutation == "value": commands[index] = replace(command,text="-19.43")
    elif mutation == "sign": commands[index] = replace(command,text="19.42")
    elif mutation == "missing": commands.pop(index)
    elif mutation == "duplicate": commands.append(command)
    else:
        other = next(i for i,c in enumerate(commands) if isinstance(c,Text) and c.text == "59.75")
        commands[index] = replace(command,text=commands[other].text)
        commands[other] = replace(commands[other],text=command.text)
    broken = [ScenePage(page.profile,tuple(commands),page.metadata)]
    path = tmp_path / "native-content.pdf"
    render_pdf(broken,path,fonts)
    with pytest.raises(AssertionError,match="p26"):
        verifier.verify_pdf(path,source_pages=(26,),trace={"pages":[trace["pages"][25]]},manifest=manifest)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "enlarged", "relocated", "wrong-page", "unknown-pixels", "full-page"])
def test_native_image_corruptions_are_rejected_in_scene_and_pdf(available_report, verifier, tmp_path, mutation):
    fonts,pages,trace,manifest = available_report
    page = pages[0]
    commands = list(page.commands)
    index = next(i for i,c in enumerate(commands) if isinstance(c,RasterImage))
    image = commands[index]
    if mutation == "missing": commands.pop(index)
    elif mutation == "duplicate": commands.append(image)
    elif mutation == "enlarged": commands[index] = replace(image,width=image.width+10)
    elif mutation == "relocated": commands[index] = replace(image,x=image.x+5)
    elif mutation == "wrong-page":
        foreign = next(c for c in pages[1].commands if isinstance(c,RasterImage))
        commands[index] = replace(image,data=foreign.data)
    elif mutation == "full-page": commands[index] = replace(image,x=0,y=0,width=595,height=842)
    else:
        output = BytesIO()
        Image.new("RGB",(10,10),(0,0,0)).save(output,format="PNG")
        commands[index] = replace(image,data=output.getvalue())
    broken = [ScenePage(page.profile,tuple(commands),page.metadata)]
    with pytest.raises(AssertionError,match="image"):
        verifier.verify_scene_images(broken,(1,),manifest)
    path = tmp_path / "native-image.pdf"
    render_pdf(broken,path,fonts)
    with pytest.raises(AssertionError,match="image"):
        verifier.verify_pdf(path,source_pages=(1,),trace={"pages":[trace["pages"][0]]},manifest=manifest)


def test_scene_rejects_reencoded_image_with_identical_pixels(available_report,verifier):
    _,pages,_,manifest = available_report
    page = pages[0]
    commands = list(page.commands)
    index = next(i for i,c in enumerate(commands) if isinstance(c,RasterImage))
    output = BytesIO()
    with Image.open(BytesIO(commands[index].data)) as image:
        image.save(output,format="PNG",compress_level=0)
    assert output.getvalue() != commands[index].data
    commands[index] = replace(commands[index],data=output.getvalue())
    broken = [ScenePage(page.profile,tuple(commands),page.metadata)]
    with pytest.raises(AssertionError,match="image bytes"):
        verifier.verify_scene_images(broken,(1,),manifest)


@pytest.mark.parametrize("position", ["baseline", "opposite-side", "detached"])
def test_native_superscript_baseline_contract(available_report,verifier,tmp_path,position):
    fonts,pages,trace,manifest = available_report
    page = pages[8]
    commands = list(page.commands)
    regions,_ = verifier._trace_regions(trace["pages"][8])
    x0,y0,x1,y1 = regions["p09-sum-x2"]
    index = next(i for i,c in enumerate(commands) if isinstance(c,Text) and c.text == "2" and c.style.size<8 and y0<=c.y<=y1)
    command = commands[index]
    baseline = next(c.y for c in commands if isinstance(c,Text) and c.style.size>=8 and y0<=c.y<=y1)
    target = {"baseline":baseline,"opposite-side":baseline+3,"detached":baseline-9}[position]
    commands[index] = replace(command,y=target)
    broken = [ScenePage(page.profile,tuple(commands),page.metadata)]
    path = tmp_path / "native-superscript.pdf"
    render_pdf(broken,path,fonts)
    with pytest.raises(AssertionError,match="p09.*(script|text)"):
        verifier.verify_pdf(path,source_pages=(9,),trace={"pages":[trace["pages"][8]]},manifest=manifest)


@pytest.mark.parametrize("number", [36, pytest.param(30, marks=deferred.DEFERRED)])
@pytest.mark.parametrize("grid", [False,True])
def test_native_page_number_is_prohibited(reports,verifier,tmp_path,grid,number):
    fonts,pages,trace,manifest = reports((number,))
    path = tmp_path / "native-number.pdf"
    render_pdf([pages[0]],path,fonts,debug_grid=grid)
    with pymupdf.open(path) as pdf:
        pdf[0].insert_text((512,53),f"13 - {number}",fontsize=11.5)
        pdf.saveIncr()
    with pytest.raises(AssertionError,match="page number"):
        verifier.verify_pdf(path,source_pages=(number,),trace={"pages":[trace["pages"][0]]},manifest=manifest,grid=grid)


@pytest.mark.parametrize("selection", deferred.selections(deferred.ALL_PAGES))
@pytest.mark.parametrize("mutation", ["38th-page", "swapped-pages"])
def test_native_fixed_37_page_contract(reports,verifier,tmp_path,mutation,selection):
    fonts,pages,trace,manifest = reports(selection)
    broken = list(pages)
    if mutation == "38th-page": broken.append(ScenePage(pages[-1].profile))
    else: broken[0],broken[1] = broken[1],broken[0]
    path = tmp_path / "native-order.pdf"
    render_pdf(broken,path,fonts)
    with pytest.raises(AssertionError,match="page count|p01"):
        verifier.verify_pdf(path,source_pages=selection,trace=trace,manifest=manifest)


def test_source_controls_exercise_all_five_complete_oracles(verifier, tmp_path):
    path, trace = source_control(tmp_path)
    result = verifier.verify_pdf(path, source_pages=PROOF, trace=trace)
    assert result["source_pages"] == list(PROOF)
    # 26 prose blocks + 195 p26 items + 268 p30 items + 306 p36 items.
    assert result["verified_items"] == 795
    assert result["complete_37_pages"] is False


@pytest.mark.parametrize("grid", [False, True])
def test_page_number_insertion_is_detected_for_both_variants(verifier, tmp_path, grid):
    path, trace = source_control(tmp_path, (30,))
    with pymupdf.open(path) as pdf:
        pdf[0].insert_text((512, 53), "13 - 30", fontsize=11.5)
        pdf.saveIncr()
    with pytest.raises(AssertionError, match="page.number|page number"):
        verifier.verify_pdf(path, source_pages=(30,), trace=trace, grid=grid)


@pytest.mark.parametrize("mutation", ["value", "sign", "duplicate", "empty-cell", "move-cell"])
def test_actual_pdf_cell_corruptions_are_detected(verifier, tmp_path, mutation):
    path, trace = source_control(tmp_path, (26,))
    with pymupdf.open(path) as pdf:
        page = pdf[0]
        if mutation in ("value", "sign", "move-cell"):
            target = page.search_for("-19.42")[0]
            page.add_redact_annot(target, fill=(1, 1, 1))
            page.apply_redactions()
            text = {"value": "-19.43", "sign": "19.42", "move-cell": "-19.42"}[mutation]
            point = (target.x0 - 40 if mutation == "move-cell" else target.x0, target.y1 - 1)
            page.insert_text(point, text, fontsize=10)
        elif mutation == "duplicate":
            target = page.search_for("59.75")[0]
            page.insert_text((target.x0, target.y1 - 1), "59.75", fontsize=10)
        else:
            page.insert_text((385, 174), "0.00", fontsize=10)
        pdf.saveIncr()
    with pytest.raises(AssertionError, match="p26"):
        verifier.verify_pdf(path, source_pages=(26,), trace=trace)


def test_extra_page_is_not_truncated(verifier, tmp_path):
    path, trace = source_control(tmp_path, (30,))
    with pymupdf.open(path) as pdf:
        pdf.new_page(width=595, height=842)
        pdf.saveIncr()
    with pytest.raises(AssertionError, match="page count"):
        verifier.verify_pdf(path, source_pages=(30,), trace=trace)


def test_same_page_count_with_swapped_pages_is_not_accepted(verifier, tmp_path):
    path, trace = source_control(tmp_path, (16, 17))
    with pymupdf.open(path) as pdf:
        pdf.move_page(1, 0)
        pdf.saveIncr()
    with pytest.raises(AssertionError, match="p16"):
        verifier.verify_pdf(path, source_pages=(16, 17), trace=trace)


@pytest.mark.parametrize("pages", [(30, 30), (38,), (), tuple(range(1, 38))])
def test_invalid_or_incomplete_expected_set_is_never_accepted(verifier, tmp_path, pages):
    path, trace = source_control(tmp_path, (30,))
    with pytest.raises((ValueError, AssertionError), match="source|oracle|page"):
        verifier.verify_pdf(path, source_pages=pages, trace=trace)


def test_prohibited_table_image_detected_even_with_text_overlay(verifier, tmp_path):
    path, trace = source_control(tmp_path, (30,))
    with pymupdf.open(path) as pdf:
        page = pdf[0]
        pixmap = page.get_pixmap(clip=(100, 300, 200, 500))
        page.insert_image((100, 300, 200, 500), pixmap=pixmap, overlay=False)
        pdf.saveIncr()
    with pytest.raises(AssertionError, match="image"):
        verifier.verify_pdf(path, source_pages=(30,), trace=trace)
