"""Fixed-scene typography proof; this precedes the public document-flow API.

Run: uv run --locked --extra dev python examples/typography_proof.py
The pinned test font is an example input. Product callers supply their own font.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
import json
from pathlib import Path

from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.math import Delimited, Fraction, Operator, Root, Row, Script
from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE
from gridlayoutpdf.renderers.reportlab import render_pdf
from gridlayoutpdf.scene import Line, Rectangle, ScenePage, Text
from gridlayoutpdf.styles import TextStyle


ROOT = Path(__file__).resolve().parents[1]


def build_pages(fonts: FontRegistry) -> tuple[ScenePage, ...]:
    """Build three measured reference pages with identical typography."""
    pages = []
    style = TextStyle(size=10)
    for page_number, profile in enumerate(
        (A4_PORTRAIT_REFERENCE, A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE),
        start=1,
    ):
        grid = profile.grid
        equal_centers = (grid.x(10), grid.x(22))
        equal_width = fonts.measure("=", style).width
        commands = [
            Text(grid.x(0), grid.y(0) + 11, f"文字組の最小実証  {page_number} / 3", style),
            Text(grid.x(0), grid.y(2) + 11, "日本語 ABC 123  α β γ  σ τ φ Σ  × ÷ ≦ ≧ ±", style),
        ]
        baselines = []
        for row, label, variable, expression, result, exponent in (
            (5, "断面積", "A", Row("4.50", Operator("×"), "2.70"), "12.150", "2"),
            (8, "断面二次モーメント", "I",
             Fraction(Row("4.50", Operator("×"), Script("2.70", superscript="3")), "12"),
             "7.38113", "4"),
        ):
            baseline = grid.y(row) + 11
            baselines.append(baseline)
            commands.extend((
                Text(grid.x(0), baseline, label, style),
                Text(grid.x(8), baseline, variable, style),
                Text(equal_centers[0] - equal_width / 2, baseline, "=", style),
                *expression.measure(fonts, style).translated(grid.x(11), baseline),
                Text(equal_centers[1] - equal_width / 2, baseline, "=", style),
                Text(grid.x(26) - fonts.measure(result, style).width, baseline, result, style),
                *Script("m", superscript=exponent).measure(fonts, style).translated(grid.x(27), baseline),
            ))
        commands.extend((
            Text(grid.x(0), grid.y(12) + 11, "自然な文字送り：日本語 ABC", style),
            Text(grid.x(0), grid.y(14) + 11, "字間追加 0.25 pt：日本語 ABC", TextStyle(tracking=0.25)),
            Text(grid.x(0), grid.y(17) + 11, "表示用原稿。工学計算は実行しない。", style),
        ))
        commands.append(Text(grid.x(0), grid.y(20) + 11, "段分数・指数・根号", style))
        complex_expression = Script(
            Delimited(Fraction(
                "1",
                Row("1", Operator("+"), Fraction(
                    Script("β", subscript="2"), Root(Row("1", Operator("+"), "γ")),
                )),
            )),
            superscript=Fraction("1", "2"),
        )
        math_box = complex_expression.measure(fonts, style)
        math_x, math_top = grid.x(4), grid.y(22)
        math_baseline = math_top + math_box.ascent
        commands.extend(math_box.translated(math_x, math_baseline))
        if profile is A3_LANDSCAPE_REFERENCE:
            commands.append(Text(grid.x(42), grid.y(2) + 11, "A3横：同じピッチ・文字サイズ", style))
        pages.append(ScenePage(profile, tuple(commands), {
            "font_size_pt": 10,
            "baseline_offset_pt": 11,
            "equal_centers_pt": equal_centers,
            "result_right_pt": grid.x(26),
            "unit_start_pt": grid.x(27),
            "equation_baselines_pt": baselines,
            "display_data_only": True,
            "complex_math": {
                "bounds_pt": [math_x, math_top, math_x + math_box.width,
                              math_top + math_box.height],
                "baseline_pt": math_baseline,
                "axis_pt": math_baseline - math_box.axis,
                "occupied_rows": grid.rows_for(math_box.height),
                "command_count": len(math_box.commands),
                "features": ["nested_fraction", "fraction_exponent", "subscript", "root", "tall_delimiters"],
            },
        }))
    return tuple(pages)


def _json_value(value):
    """Convert immutable metadata and dataclasses without deepcopy/asdict."""
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _text_bounds(command: Text, fonts: FontRegistry) -> list[float]:
    bounds = fonts.measure(command.text, command.style).bounds
    return [command.x + bounds.x, command.y + bounds.y,
            command.x + bounds.right, command.y + bounds.bottom]


def _debug_pages(pages, fonts):
    result = []
    for page in pages:
        commands = list(page.commands)
        for command in page.commands:
            if isinstance(command, Text):
                left, top, right, bottom = _text_bounds(command, fonts)
                commands.append(Rectangle(left, top, right - left, bottom - top,
                                          stroke_width=0.2, color=(0.2, 0.65, 0.35)))
                commands.append(Line(left, command.y, right, command.y,
                                     width=0.2, color=(0.25, 0.5, 0.85)))
        for center in page.metadata["equal_centers_pt"]:
            commands.append(Line(center, page.profile.grid.y(4), center,
                                 page.profile.grid.y(10), width=0.35, color=(0.85, 0.25, 0.6)))
        result.append(ScenePage(page.profile, tuple(commands), page.metadata))
    return tuple(result)


def write_proof(output_dir: str | Path, font_path: str | Path) -> tuple[Path, Path, Path]:
    """Write normal/debug PDFs, a coordinate trace, and 144 dpi preview PNGs."""
    fonts = FontRegistry()
    face = fonts.register("body", font_path)
    pages = build_pages(fonts)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plain = output_dir / "typography-proof.pdf"
    debug = output_dir / "typography-proof-grid.pdf"
    trace_path = output_dir / "typography-proof.json"
    render_pdf(pages, plain, fonts)
    render_pdf(_debug_pages(pages, fonts), debug, fonts, debug_grid=True)
    trace = {"schema_version": 1, "font": _json_value(face), "pages": []}
    for page in pages:
        commands = []
        for command in page.commands:
            data = {"kind": type(command).__name__, **_json_value(command)}
            if isinstance(command, Text):
                data["bounds"] = _text_bounds(command, fonts)
            commands.append(data)
        trace["pages"].append({
            "profile": _json_value(page.profile),
            "metadata": _json_value(page.metadata), "commands": commands,
        })
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # PyMuPDF is a development dependency used for independent visual QA only.
    import pymupdf

    previews = output_dir / "previews"
    previews.mkdir(parents=True, exist_ok=True)
    for path in (plain, debug):
        with pymupdf.open(path) as document:
            for number, page in enumerate(document, start=1):
                page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(
                    previews / f"{path.stem}-page-{number}.png"
                )
    return plain, debug, trace_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=ROOT / "tests/fixtures/fonts/ipaexm.ttf")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/reports")
    options = parser.parse_args()
    for path in write_proof(options.output_dir, options.font):
        print(path)


if __name__ == "__main__":
    main()
