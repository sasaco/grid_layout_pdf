"""Merged table proof using measured fragments and the stable scene renderer.

The scene placement here is proof glue until Document integration is complete.
Run: uv run --locked --extra dev python examples/table_proof.py
"""

from collections.abc import Mapping
import json
from pathlib import Path

from gridlayoutpdf.equations import MathBlock
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.math import Fraction, Root, Script
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.renderers.reportlab import render_pdf
from gridlayoutpdf.scene import ScenePage, Text
from gridlayoutpdf.styles import ReportStyle, TextStyle
from gridlayoutpdf.tables import Cell, Table


ROOT = Path(__file__).resolve().parents[1]


def make_table():
    """Display-only data: no engineering calculations are performed."""
    return Table((4, 5, 6, 5, 5, 5), [
        [Cell("部材", rowspan=2), Cell("断面・条件", colspan=2, align="center"),
         Cell("照査結果", colspan=3, align="center")],
        ["寸法", "式", "作用値", "許容値", "判定"],
        [Cell("部材A", rowspan=2), "幅 b", Cell(MathBlock(Fraction("b", "2")), align="center"), "12.50", "18.00", "OK"],
        ["高さ h", Cell(MathBlock(Script("h", superscript="2")), align="center"), "8.40", "12.00", "OK"],
        [Cell("部材B", rowspan=2), "係数 α", Cell(MathBlock(Fraction("1", Fraction("a", "b"))), align="center"), "0.85", "1.00", "OK"],
        ["条件 β", Cell(MathBlock(Root("β")), align="center"), "9.60", "15.00", "OK"],
        ["CASE-C", "曲げ", Cell(MathBlock("M"), align="center"), "25.00", "30.00", "OK"],
        ["CASE-D", "せん断", Cell(MathBlock(Script("V", subscript="d")), align="center"), "6.25", "10.00", "OK"],
        ["CASE-E", "比率", Cell(MathBlock(Fraction("σ", "σa")), align="center"), "0.75", "1.00", "OK"],
        ["CASE-F", "表示値", Cell(MathBlock("N"), align="center"), "125.00", "150.00", "OK"],
    ], header_rows=2, numeric_columns=(3, 4), block_id="merged-proof")


def _part_trace(part):
    return {"rows": part.rows, "metadata": part.metadata}


def _json_value(value):
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def build_pages(fonts):
    profile = A4_PORTRAIT_REFERENCE
    context = LayoutContext(fonts, profile, ReportStyle())
    measured = measure_block(make_table(), context, profile.grid.columns * profile.grid.pitch_x)
    fragments = []
    while measured.rows > 20:
        split = measured.split(20)
        if split is None:
            raise ValueError("Proof row group exceeds its declared fragment capacity")
        head, measured = split
        fragments.append(head)
    fragments.append(measured)
    pages, trace = [], []
    x, y = profile.grid.x(0), profile.grid.y(3)
    for index, fragment in enumerate(fragments, 1):
        commands = (
            Text(profile.grid.x(0), profile.grid.y(0) + 11, f"結合表の実証  {index} / {len(fragments)}", TextStyle()),
            *fragment.translated(x, y),
            Text(profile.grid.x(0), profile.grid.y(26) + 11, "表示用原稿。工学計算は実行しない。", TextStyle()),
        )
        metadata = {"table_origin_pt": (x, y), "rows": fragment.rows,
                    "prefix": tuple(_part_trace(part) for part in fragment.prefix),
                    "parts": tuple(_part_trace(part) for part in fragment.parts)}
        pages.append(ScenePage(profile, commands, metadata))
        trace.append(metadata)
    return tuple(pages), trace


def write_proof(output_dir, font_path):
    import pymupdf

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fonts = FontRegistry()
    fonts.register("body", font_path)
    pages, trace = build_pages(fonts)
    previews = output_dir / "previews"
    previews.mkdir(exist_ok=True)
    for name, debug in (("table-proof", False), ("table-proof-grid", True)):
        path = output_dir / f"{name}.pdf"
        render_pdf(pages, path, fonts, debug_grid=debug)
        with pymupdf.open(path) as pdf:
            for index, page in enumerate(pdf, 1):
                page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).save(previews / f"{name}-page-{index}.png")
    (output_dir / "table-proof.json").write_text(
        json.dumps(_json_value({"schema_version": 1, "pages": trace}), ensure_ascii=False, indent=2), encoding="utf-8",
    )


if __name__ == "__main__":
    write_proof(ROOT / "build/reports", ROOT / "tests/fixtures/fonts/ipaexm.ttf")
