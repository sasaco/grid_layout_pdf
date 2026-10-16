"""Measured equation adapters: A4 fixed anchors and A3 automatic anchors.

Run with uv run --locked --extra dev python examples/equation_proof.py.
The supplied values are display specimens; this example performs no engineering
calculation. Callers provide a font; the default is the pinned test fixture.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
from pathlib import Path

from gridlayoutpdf.equations import Equation, EquationAnchors, EquationGroup
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.math import Delimited, Fraction, Operator, Root, Row, Script
from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE
from gridlayoutpdf.renderers.reportlab import render_pdf
from gridlayoutpdf.scene import Line, Rectangle, ScenePage, Text
from gridlayoutpdf.styles import ReportStyle


ROOT = Path(__file__).resolve().parents[1]


def _equations() -> tuple[Equation, ...]:
    terms = []
    for index in range(1, 9):
        if terms:
            terms.append(Operator("+"))
        terms.append(f"{index}.{index:02d}")
    complex_math = Script(Delimited(Fraction(
        "1", Row("1", Operator("+"), Fraction(
            Script("β", subscript="2"), Root(Row("1", Operator("+"), "γ")),
        )),
    )), superscript=Fraction("1", "2"))
    return (
        Equation("A", Row("4.50", Operator("×"), "2.70"), label="断面積",
                 result="12.150", unit=Script("m", superscript="2")),
        Equation("I", Fraction(Row("4.50", Operator("×"), Script("2.70", superscript="3")), "12"),
                 label="断面二次モーメント", result="7.38113", unit=Script("m", superscript="4"),
                 relation="＝", result_relation="＝"),
        Equation("S", Row(*terms), label="継続行", result="36.36", unit="kN"),
        Equation("Q", complex_math, label="複雑式", result="0.125", unit="kN"),
        Equation("Z", "1234567890" * 4, label="結果最終行", result="0.98765", unit="kN"),
    )


def build_pages(fonts: FontRegistry) -> tuple[ScenePage, ...]:
    equations = _equations()
    pages = []
    for profile, anchors, caption in (
        (A4_PORTRAIT_REFERENCE, EquationAnchors(10, 22, 26, 27), "A4：固定アンカー"),
        (A3_LANDSCAPE_REFERENCE, None, "A3：自動アンカーで再計測"),
    ):
        context = LayoutContext(fonts, profile, ReportStyle())
        measured = measure_block(EquationGroup(*equations, anchors=anchors, block_id="equation-proof"),
                                 context, profile.body_rect.width)
        left, top = profile.grid.x(0), profile.grid.y(3)
        commands = (
            Text(left, profile.grid.y(0) + 11, "数式部品・折り返しの実証  " + caption, context.style.body),
            *measured.translated(left, top),
        )
        parts = []
        rows = 0
        for part in measured.parts:
            parts.append({"rows": part.rows, "top_pt": rows * measured.row_pitch,
                          "metadata": part.metadata})
            rows += part.rows
        pages.append(ScenePage(profile, commands, {
            "block_origin_pt": (left, top), "block_width_pt": measured.width,
            "block_height_pt": measured.height, "parts": parts,
            "display_data_only": True,
        }))
    return tuple(pages)


def _json_value(value):
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def write_proof(output_dir: str | Path, font_path: str | Path) -> tuple[Path, Path, Path]:
    fonts = FontRegistry()
    fonts.register("body", font_path)
    pages = build_pages(fonts)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    normal = output_dir / "equation-proof.pdf"
    debug = output_dir / "equation-proof-grid.pdf"
    trace = output_dir / "equation-proof.json"
    render_pdf(pages, normal, fonts)
    debug_pages = []
    for page in pages:
        left, top = page.metadata["block_origin_pt"]
        height = page.metadata["block_height_pt"]
        annotations = [Rectangle(left, top, page.metadata["block_width_pt"], height,
                                 stroke_width=.25, color=(.2, .65, .35))]
        points = page.metadata["parts"][0]["metadata"]["anchors_pt"]
        for point in points.values():
            if point is not None:
                annotations.append(Line(left + point, top, left + point, top + height,
                                        width=.3, color=(.8, .25, .5)))
        debug_pages.append(ScenePage(page.profile, (*page.commands, *annotations), page.metadata))
    render_pdf(debug_pages, debug, fonts, debug_grid=True)
    trace.write_text(json.dumps({"schema_version": 1, "pages": [
        {"profile": page.profile.name, **_json_value(page.metadata)} for page in pages
    ]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    import pymupdf

    previews = output_dir / "previews"
    previews.mkdir(parents=True, exist_ok=True)
    for path in (normal, debug):
        with pymupdf.open(path) as document:
            for number, page in enumerate(document, start=1):
                page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(
                    previews / f"{path.stem}-page-{number}.png")
    return normal, debug, trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=ROOT / "tests/fixtures/fonts/ipaexm.ttf")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/reports/equations")
    options = parser.parse_args()
    for path in write_proof(options.output_dir, options.font):
        print(path)


if __name__ == "__main__":
    main()
