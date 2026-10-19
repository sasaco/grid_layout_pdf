"""Original-vs-output appearance checks, independent of authored placement data."""

import importlib.util
import json
from pathlib import Path
import sys
from dataclasses import replace

import pytest

from gridlayoutpdf import Line, ScenePage, Text, layout_trace, render_pdf


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/cantilever_p01_37"


def module(name):
    key = "cantilever_source_appearance_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, FIXTURE / f"{name}.py")
        result = importlib.util.module_from_spec(spec)
        sys.modules[key] = result
        spec.loader.exec_module(result)
    return sys.modules[key]


REPRODUCTION_PAGES = (1, 3, 21, 30)
# p30 is deferred to FR-027 Step 9 (2026-10-20 user decision c). p36, the
# available rotated table, keeps the rotated-table appearance checks running.
AVAILABLE_REPRODUCTION_PAGES = (*module("deferred").available(REPRODUCTION_PAGES), 36)


def _reproduce(path, source_pages):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=source_pages)
    render_pdf(pages, path, fonts)
    return path, layout_trace(pages, fonts)


@pytest.fixture(scope="module")
def reproduction(tmp_path_factory):
    return _reproduce(tmp_path_factory.mktemp("source-appearance") / "normal.pdf", AVAILABLE_REPRODUCTION_PAGES)


DEFERRED_DIFFERENCES = module("deferred").DEFERRED_DIFFERENCES


@pytest.mark.parametrize("category", ["font", "indent", "equals", "table", "spacing", "baseline"])
def test_reproduction_matches_original_appearance(reproduction, category):
    path, trace = reproduction
    report = module("verify_appearance").appearance_report(
        path, source_pages=AVAILABLE_REPRODUCTION_PAGES, trace=trace, categories=(category,),
        deferred=DEFERRED_DIFFERENCES)
    assert not report["errors"], json.dumps(report["errors"][:8], ensure_ascii=False)
    # Only the listed p36 differences are deferred, and each is counted separately.
    assert report["deferred_count"] == (9 if category == "spacing" else 0)
    assert sorted(item["id"] for item in report["deferred"]) == (
        sorted(entry["id"] for entry in DEFERRED_DIFFERENCES) if category == "spacing" else [])


def test_deferred_differences_list_the_nine_p36_operator_positions():
    deferred = module("deferred")
    assert [entry["id"] for entry in DEFERRED_DIFFERENCES] == [
        f"p36-combinations-summary.r{row}.c8" for row in range(10, 19)]
    assert all(entry["page"] == 36 and entry["category"] == "spacing"
               and entry["detail"] == "operator inline origin" and entry["max_delta_pt"] == .61
               and entry["reason"] == deferred.DIFFERENCE_REASON for entry in DEFERRED_DIFFERENCES)
    assert "0.600 pt" in deferred.DIFFERENCE_REASON and "Step 9" in deferred.DIFFERENCE_REASON


def test_deferred_differences_never_hide_other_or_resolved_differences(reproduction):
    path, trace = reproduction
    verifier = module("verify_appearance")

    def report(deferred):
        return verifier.appearance_report(path, source_pages=AVAILABLE_REPRODUCTION_PAGES, trace=trace,
                                          categories=("spacing",), deferred=deferred)

    # Without the list the nine differences are ordinary failures.
    plain = report(())
    assert sorted(error["id"] for error in plain["errors"]) == sorted(entry["id"] for entry in DEFERRED_DIFFERENCES)
    assert plain["deferred_count"] == 0
    # A listed difference that no longer occurs fails, like a strict xfail.
    resolved = {**DEFERRED_DIFFERENCES[0], "id": "p36-combinations-summary.r9.c8"}
    stale = report((*DEFERRED_DIFFERENCES, resolved))
    assert [(error["category"], error["id"]) for error in stale["errors"]] == [
        ("deferred", "p36-combinations-summary.r9.c8")]
    # A difference larger than its listed bound stays a failure, and its entry is unmatched.
    bounded = report(tuple({**entry, "max_delta_pt": .5} for entry in DEFERRED_DIFFERENCES))
    assert bounded["deferred_count"] == 0
    assert sorted(error["category"] for error in bounded["errors"]) == ["deferred"] * 9 + ["spacing"] * 9
    # Entries for pages outside the comparison, or other categories, are ignored.
    elsewhere = report(({**DEFERRED_DIFFERENCES[0], "page": 37, "id": "p37-x"},))
    assert len(elsewhere["errors"]) == 9
    other = verifier.appearance_report(path, source_pages=AVAILABLE_REPRODUCTION_PAGES, trace=trace,
                                       categories=("font",), deferred=DEFERRED_DIFFERENCES)
    assert not other["errors"] and other["deferred_count"] == 0
    with pytest.raises(ValueError, match="deferred"):
        report(({"id": "p36-combinations-summary.r10.c8"},))


@module("deferred").DEFERRED
def test_reproduction_with_deferred_pages_matches_original_appearance(tmp_path):
    path, trace = _reproduce(tmp_path / "with-deferred.pdf", REPRODUCTION_PAGES)
    report = module("verify_appearance").appearance_report(path, source_pages=REPRODUCTION_PAGES, trace=trace)
    assert not report["errors"], json.dumps(report["errors"][:8], ensure_ascii=False)


def test_source_font_indent_equals_control():
    verifier = module("verify_appearance")
    source = next((FIXTURE.parents[1] / "output").glob("13_*.pdf"))
    records = [json.loads((FIXTURE / f"expected/p{n:02}.json").read_text(encoding="utf-8")) for n in (1, 3, 21, 30)]
    trace = {"oracle_regions": [{item["id"]: item["source_bbox"] for block in record["blocks"]
                                for item in (block["cells"] if block["kind"] == "table" else [block])}
                               for record in records]}
    report = verifier.appearance_report(source, source_pages=(1, 3, 21, 30), trace=trace,
                                        categories=("font", "indent", "equals", "spacing"))
    assert report["error_count"] == 0


@pytest.mark.parametrize("number", range(1, 38))
def test_original_perpendicular_baselines_are_positive_controls(number):
    verifier = module("verify_appearance")
    source = next((FIXTURE.parents[1] / "output").glob("13_*.pdf"))
    record = json.loads((FIXTURE / f"expected/p{number:02}.json").read_text(encoding="utf-8"))
    trace = {"oracle_regions": [{item["id"]: item["source_bbox"]
                                for block in record["blocks"]
                                for item in block.get("cells", [block])}]}
    report = verifier.appearance_report(source, source_pages=(number,), trace=trace)
    assert not report["errors"], report
    assert "baseline" in report["checks"], "Perpendicular origins are not compared"
    assert report["checks"]["baseline"] > 0


def test_original_p09_superscript_baselines_are_preserved(tmp_path):
    import pymupdf

    builder, verifier = module("builder"), module("verify_appearance")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(9,))
    path = tmp_path / "p09-superscripts.pdf"
    render_pdf(pages, path, fonts)
    item = next(block for block in json.loads((FIXTURE / "expected/p09.json").read_text(encoding="utf-8"))["blocks"]
                if block["id"] == "p09-sum-x2")
    regions, _ = verifier._content._trace_regions(layout_trace(pages, fonts)["pages"][0])
    source = next((FIXTURE.parents[1] / "output").glob("13_*.pdf"))
    with pymupdf.open(source) as original, pymupdf.open(path) as actual_pdf:
        wanted = [char for char in verifier._content._inside(verifier._characters(original[8], trusted_source=True), item["source_bbox"])
                  if char["size"] < 8]
        actual = [char for char in verifier._content._inside(verifier._characters(actual_pdf[0]), regions[item["id"]])
                  if char["size"] < 8]
    wanted.sort(key=lambda char: char["origin"][0])
    actual.sort(key=lambda char: char["origin"][0])
    assert [char["c"] for char in actual] == [char["c"] for char in wanted] == ["2"] * 4
    assert [char["origin"][1] for char in actual] == pytest.approx(
        [char["origin"][1] for char in wanted], abs=.20)


@pytest.mark.parametrize("number,key,text,script", [
    (3, "p03-equation-001", "0.471", False), (9, "p09-sum-x2", "2", True),
])
def test_perpendicular_operand_and_superscript_mutations_are_rejected(number, key, text, script, tmp_path):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(number,))
    trace = layout_trace(pages, fonts)
    regions, _ = module("verify")._trace_regions(trace["pages"][0])
    left, top, right, bottom = regions[key]
    commands = list(pages[0].commands)
    index = next(index for index, command in enumerate(commands) if isinstance(command, Text)
                 and command.text == text and (command.style.size < 8) is script
                 and left <= command.x <= right and top <= command.y <= bottom)
    commands[index] = replace(commands[index], y=commands[index].y + 2)
    path = tmp_path / "perpendicular-mutation.pdf"
    render_pdf([ScenePage(pages[0].profile, tuple(commands), pages[0].metadata)], path, fonts)
    # Both mutations retain content and readable script roles; only the source
    # perpendicular-position check can reject these two-point displacements.
    assert module("verify").verify_pdf(path, source_pages=(number,), trace=trace,
                                       manifest=builder.load_manifest())["verified_items"] > 0
    report = module("verify_appearance").appearance_report(path, source_pages=(number,), trace=trace)
    relevant = [error for error in report["errors"] if error["id"] == key and error["category"] == "baseline"]
    assert relevant and any(error["delta"] > 1.9 for error in relevant), report


@pytest.mark.parametrize("number", range(1, 38))
def test_expected_reading_order_matches_original_geometry(number):
    import pymupdf

    content = module("verify")
    expected = json.loads((FIXTURE / f"expected/p{number:02}.json").read_text(encoding="utf-8"))
    source = next((FIXTURE.parents[1] / "output").glob("13_*.pdf"))
    with pymupdf.open(source) as pdf:
        chars = [char for char in content._chars(pdf[number - 1]) if char["c"] != "※"]
        for block in expected["blocks"]:
            for item in block["cells"] if block["kind"] == "table" else [block]:
                selected = content._inside(chars, item["source_bbox"])
                actual = content._compact(content._reading(selected, tuple(item["direction"])))
                assert actual == content._compact(item["text"]), item["id"]
                overrides = {entry["character_index"]: entry["direction"]
                             for entry in item.get("source_direction_overrides", [])}
                ordered = [char for line, _ in content._ordered_lines(selected, item["direction"])
                           for char in line if not char["c"].isspace()]
                for index, char in enumerate(ordered):
                    assert tuple(char["direction"]) == tuple(overrides.get(index, item["direction"])), item["id"]


@pytest.mark.parametrize("category", ["font", "indent", "equals", "table", "spacing"])
def test_native_appearance_mutations_are_rejected(category, tmp_path):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(1,))
    commands = list(pages[0].commands)
    if category in ("font", "indent"):
        index = next(i for i, command in enumerate(commands) if isinstance(command, Text))
        old = commands[index]
        commands[index] = (replace(old, style=replace(old.style, font="MS Mincho")) if category == "font"
                           else replace(old, x=old.x + 1))
    elif category == "equals":
        index = next(i for i, command in enumerate(commands) if isinstance(command, Text) and command.text == "=")
        commands[index] = replace(commands[index], x=commands[index].x + 2)
    elif category == "spacing":
        index = next(i for i, command in enumerate(commands) if isinstance(command, Text) and command.text == "×")
        commands[index] = replace(commands[index], x=commands[index].x + 2)
    else:
        # Move an actual drawn row boundary, leaving trace and text untouched.
        boundary = min(command.y1 for command in commands
                       if isinstance(command, Line) and abs(command.y1 - command.y2) < .001)
        commands = [replace(command, y1=command.y1 + 1, y2=command.y2 + 1)
                    if isinstance(command, Line) and abs(command.y1 - boundary) < .001
                    and abs(command.y1 - command.y2) < .001 else command for command in commands]
    path = tmp_path / f"bad-{category}.pdf"
    render_pdf([ScenePage(pages[0].profile, tuple(commands), pages[0].metadata)], path, fonts)
    report = module("verify_appearance").appearance_report(
        path, source_pages=(1,), trace=layout_trace(pages, fonts), categories=(category,))
    assert any(error["category"] == category for error in report["errors"]), report


def test_removing_original_synthetic_italic_is_rejected(tmp_path):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(1,))
    commands = tuple(replace(command, shear_x=0) if isinstance(command, Text) and command.shear_x
                     else command for command in pages[0].commands)
    assert sum(isinstance(command, Text) and bool(command.shear_x) for command in pages[0].commands) == 4
    path = tmp_path / "missing-original-italic.pdf"
    render_pdf([ScenePage(pages[0].profile, commands, pages[0].metadata)], path, fonts)
    report = module("verify_appearance").appearance_report(
        path, source_pages=(1,), trace=layout_trace(pages, fonts), categories=("font",))
    assert sum(error["detail"] == "glyph inline extent" for error in report["errors"]) == 4


@pytest.mark.parametrize("number", [21, 22])
@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("mark,vertical_crop", [("（", (200.5, 207.5)), ("）", (229.5, 234.5))])
@pytest.mark.parametrize("shifted", [False, True])
def test_vertical_parenthesis_visible_ink_matches_original(number, side, mark, vertical_crop, shifted, tmp_path):
    """Identity-V and rotated horizontal glyphs have different bbox origins."""
    import pymupdf
    from PIL import Image

    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(number,))
    commands = list(pages[0].commands)
    matches = sorted((index for index, command in enumerate(commands) if isinstance(command, Text)
                      and command.text == mark and command.quarter_turns == 3), key=lambda index: commands[index].y)
    assert len(matches) == 2
    if shifted:
        index = matches[side]
        commands[index] = replace(commands[index], y=commands[index].y + 8)
    path = tmp_path / "parenthesis.pdf"
    render_pdf([ScenePage(pages[0].profile, tuple(commands), pages[0].metadata)], path, fonts)
    source = builder.REPOSITORY_ROOT / builder.load_manifest()["source"]["path"]

    def ink(path, number):
        with pymupdf.open(path) as pdf:
            pixmap = pdf[number].get_pixmap(matrix=pymupdf.Matrix(8, 8),
                clip=pymupdf.Rect(132, vertical_crop[0] + side * 226.8, 145, vertical_crop[1] + side * 226.8),
                colorspace=pymupdf.csGRAY, alpha=False)
        with Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples) as image:
            with image.point(lambda value: 255 if value < 128 else 0) as mask:
                return mask.getbbox(), mask.histogram()[255]

    expected_box, expected_pixels = ink(source, number - 1)
    actual_box, actual_pixels = ink(path, 0)
    assert expected_box is not None and expected_pixels > 200
    matches = (actual_box is not None and max(abs(a - w) for a, w in zip(actual_box, expected_box)) <= 2
               and abs(actual_pixels - expected_pixels) / expected_pixels < .10)
    assert matches is not shifted


def test_shifted_operand_is_rejected_even_with_correct_operators(tmp_path):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(3,))
    commands = list(pages[0].commands)
    index = next(i for i, command in enumerate(commands) if isinstance(command, Text) and command.text == "0.471")
    commands[index] = replace(commands[index], x=commands[index].x + 3)
    path = tmp_path / "shifted-operand.pdf"
    render_pdf([ScenePage(pages[0].profile, tuple(commands), pages[0].metadata)], path, fonts)
    report = module("verify_appearance").appearance_report(
        path, source_pages=(3,), trace=layout_trace(pages, fonts), categories=("spacing",))
    relevant = [error for error in report["errors"] if error["id"] == "p03-equation-001"]
    assert relevant and all(error["detail"] == "inline character origin" for error in relevant)
    assert min(error["delta"] for error in relevant) > 2.9


@pytest.mark.parametrize("size", [9.5, 10.5])
def test_native_body_size_off_by_one_step_is_rejected(size, tmp_path):
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(1,))
    commands = list(pages[0].commands)
    index = next(i for i, command in enumerate(commands) if isinstance(command, Text) and command.style.size == 10)
    commands[index] = replace(commands[index], style=replace(commands[index].style, size=size))
    path = tmp_path / "bad-size.pdf"
    render_pdf([ScenePage(pages[0].profile, tuple(commands), pages[0].metadata)], path, fonts)
    report = module("verify_appearance").appearance_report(
        path, source_pages=(1,), trace=layout_trace(pages, fonts), categories=("font",))
    assert any(error["detail"] == "body size (0.5 pt step)" for error in report["errors"]), report


def test_deferred_entries_must_name_a_known_category_and_hold_one_difference_each():
    verifier = module("verify_appearance")
    entry = {**DEFERRED_DIFFERENCES[0]}
    with pytest.raises(ValueError, match="deferred"):
        verifier._checked_deferrals(({**entry, "category": "spacng"},))
    error = {"category": entry["category"], "id": entry["id"], "detail": entry["detail"], "delta": .6}
    remaining, held = verifier._apply_deferrals([error, dict(error)], (entry,), (36,), {"spacing"})
    assert len(held) == 1 and remaining == [error]


def test_output_rules_must_have_their_border_styles_thickness(tmp_path):
    """FR-027: the original's 0.12 pt is not a tolerance; output hairlines are hair 0.25 pt."""
    builder = module("builder")
    fonts = builder.fixture_fonts()
    pages = builder.layout_report(fonts, source_pages=(1,))
    commands = tuple(replace(command, width=.12) if isinstance(command, Line) and command.width == .25
                     else command for command in pages[0].commands)
    assert commands != pages[0].commands
    path = tmp_path / "source-width-rules.pdf"
    render_pdf([ScenePage(pages[0].profile, commands, pages[0].metadata)], path, fonts)
    trace = layout_trace(pages, fonts)
    verifier = module("verify_appearance")
    report = verifier.appearance_report(path, source_pages=(1,), trace=trace, categories=("table",))
    wrong = [error for error in report["errors"] if error["detail"].endswith("rule thickness (border style)")]
    assert wrong and all(error["expected"] == .25 and error["actual"] == pytest.approx(.12) for error in wrong)
    native = tmp_path / "native.pdf"
    render_pdf(pages, native, fonts)
    assert not verifier.appearance_report(native, source_pages=(1,), trace=trace, categories=("table",))["errors"]
