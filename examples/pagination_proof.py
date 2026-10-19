"""Page flow, heading retention and scoped A4/A3/A4 layout proof.

The numbers below are display specimens, not engineering calculations.
Run with uv run --locked --extra dev python examples/pagination_proof.py.
"""

import argparse
import json
from pathlib import Path

from gridlayoutpdf.blocks import Heading, Paragraph, Spacer
from gridlayoutpdf.containers import Columns
from gridlayoutpdf.diagnostics import layout_trace
from gridlayoutpdf.document import Document, PageDecoration, PageSection
from gridlayoutpdf.equations import Equation, EquationGroup
from gridlayoutpdf.figures import Arrow, Figure, Image, Label
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.math import Fraction, Root, Script
from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE
from gridlayoutpdf.renderers.reportlab import render_pdf
from gridlayoutpdf.scene import Rectangle
from gridlayoutpdf.tables import Cell, Table


ROOT = Path(__file__).resolve().parents[1]


def build_document(fonts: FontRegistry) -> Document:
    lines = [f"本文行 {number:02d}：基線と文字サイズを保持して、表示順に配置します。" for number in range(1, 97)]
    figure = Figure(14, 6, Rectangle(10, 15, 160, 50), Arrow(30, 40, 150, 40),
                    Label(30, 85, "荷重方向の表示例"), block_id="vector-figure")
    table = Table((20, 18, 18), (
        ("Wide table", "表示値", "注記"),
        (Cell("分類 A", rowspan=2), "12.150", "結合セルの上段"),
        ("7.38113", "結合セルの下段"),
        ("分類 B", "0.125", "A3 の同じグリッドピッチ"),
    ), header_rows=1, numeric_columns=(1,), block_id="wide-table")
    return Document(
        Paragraph("\n".join(lines[:46]), block_id="first-paragraph"),
        Heading("末尾に置かない見出し", block_id="kept-heading"),
        Paragraph("\n".join(lines[46:]), block_id="fragmented-paragraph"),
        Spacer(1),
        EquationGroup(Equation("I", Fraction("12.150", "3"), result="4.050", unit=Script("m", superscript="4")),
                      Equation("R", Root("2"), result="1.414", unit="m"), block_id="equation-group"),
        PageSection(A3_LANDSCAPE_REFERENCE, Heading("A3 横・表の表示"), table),
        Heading("最終ページ：A4 に復帰"),
        Paragraph("図と画像も整数行の領域を予約し、次の本文へ重なりません。"),
        Spacer(1),
        Columns(figure, Image(ROOT / "tests/fixtures/layout_cases/sample_pixels.png", col_span=15, rows=6),
                col_spans=(14, 15), block_id="figure-and-image"),
        Paragraph("ページ番号と総ページ数は、全ページ確定後に描画します。"),
        fonts=fonts, header=PageDecoration("GridLayoutPdf / {page}/{pages}"),
        footer=PageDecoration("{page}/{pages}", align="right"),
    )


def write_proof(output_dir: str | Path) -> tuple[Path, Path, Path]:
    fonts = FontRegistry()
    document = build_document(fonts)
    pages = document.layout()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    normal, debug, trace = (output / name for name in (
        "pagination-proof.pdf", "pagination-proof-grid.pdf", "pagination-proof.json"))
    render_pdf(pages, normal, fonts)
    render_pdf(pages, debug, fonts, debug_grid=True)
    trace.write_text(json.dumps(layout_trace(pages, fonts), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    import pymupdf

    previews = output / "previews"
    previews.mkdir(parents=True, exist_ok=True)
    for path in (normal, debug):
        with pymupdf.open(path) as pdf:
            for number, page in enumerate(pdf, start=1):
                page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(
                    previews / f"{path.stem}-page-{number}.png")
    return normal, debug, trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/reports/pagination")
    options = parser.parse_args()
    for path in write_proof(options.output_dir):
        print(path)


if __name__ == "__main__":
    main()
