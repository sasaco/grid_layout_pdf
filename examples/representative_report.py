"""A public-API example of a mixed-size Japanese calculation report.

All numbers are supplied display data. No engineering solver is implemented.
"""

import argparse
from collections.abc import Mapping
import json
from pathlib import Path

from gridlayoutpdf import (
    A3_LANDSCAPE_REFERENCE, Arrow, BreakHint, Cell, Columns, Delimited,
    Document, Equation, EquationAnchors, EquationGroup, Figure, Fraction,
    FontRegistry, Heading, Image, Label, Line, MathBlock, Operator, PageBreak,
    PageDecoration, PageSection, Paragraph, Rectangle, Root, Row, Script,
    Spacer, Stack, Table, layout_trace, render_pdf,
)


def _load_figure():
    blue = (0.12, 0.35, 0.56)
    items = [
        Label(135, 16, "鉛直方向の分布荷重 q", align="center"),
        Rectangle(35, 55, 160, 16, stroke_width=1),
        Rectangle(102, 71, 25, 95, stroke_width=1),
        Label(115, 67, "梁", align="center"),
        Label(115, 119, "柱", align="center"),
        Line(87, 166, 143, 166, width=1),
        Line(35, 181, 35, 201), Line(195, 181, 195, 201),
        Arrow(35, 193, 195, 193), Arrow(195, 193, 35, 193),
        Label(115, 216, "梁幅 4.50 m", align="center"),
        Line(205, 71, 221, 71), Line(143, 166, 221, 166),
        Arrow(215, 71, 215, 166), Arrow(215, 166, 215, 71),
        Label(225, 112, "柱高"), Label(225, 128, "3.00 m"),
    ]
    items.extend(Arrow(x, 25, x, 49, color=blue) for x in (45, 80, 115, 150, 185))
    items.extend(Line(x, 166, x - 5, 173) for x in range(92, 144, 10))
    return Figure(17, 15, *items, block_id="load-diagram")


def _combination_table(*, long=False):
    rows = [
        [Cell("組合せ", rowspan=2), Cell("作用荷重一覧", colspan=6, align="center"),
         Cell("備考", rowspan=2)],
        ["荷重方向", "軸力 N (kN)", "せん断力 V (kN)", "曲げ M (kNm)",
         "偏心 e (m)", "係数 α"],
    ]
    for number in range(1, 16):
        rows.append([Cell(f"CASE-{number:02d}", rowspan=2), "橋軸方向", "125.00", "12.50",
                     "37.50", "0.300", "1.00", "常時の作用値と基部の作用位置を整理" if long else "常時の作用値"])
        rows.append(["橋軸直角方向", "125.00", "10.00", "30.00", "0.240", "1.00",
                     "直角方向の作用値と符号規約を記録" if long else "方向別の整理"])
    return Table((6, 10, 8, 7, 7, 7, 7, 10), rows, header_rows=2,
                 numeric_columns=(2, 3, 4, 5, 6), block_id="load-combinations")


def _section_equations(values, *, long=False):
    return EquationGroup(
        Equation("A", Row("4.50", Operator("×"), "2.70"), label="断面積",
                 result=values["area"], unit=Script("m", superscript="2")),
        Equation("I", Fraction(Row("4.50", Operator("×"), Script("2.70", superscript="3")), "12"),
                 label="中立軸に関する断面二次モーメント" if long else "断面二次モーメント",
                 result=values["inertia"], unit=Script("m", superscript="4")),
        Equation("W", Fraction("7.381125", Fraction("2.70", "2")),
                 label="縁端応力度に用いる断面係数" if long else "断面係数",
                 result=values["section_modulus"], unit=Script("m", superscript="3")),
        anchors=EquationAnchors(10, 22, 26, 27), block_id="section-properties",
    )


def _load_equations(values, *, long=False):
    terms = []
    for value in ("12.50", "8.75", "6.25", "4.00", "3.50", "2.00", "1.50", "1.50"):
        if terms:
            terms.append(Operator("+"))
        terms.append(value)
    return EquationGroup(
        Equation("S", Row(*terms), label="鉛直方向の作用値の合計" if long else "鉛直力の合計",
                 result=values["vertical"], unit="kN"),
        Equation("H", Row("1.50", Operator("+"), "2.50", BreakHint("forced"),
                          Operator("+"), "3.00"), label="水平方向の作用値の合計" if long else "水平力の合計",
                 result=values["horizontal"], unit="kN"),
        anchors=EquationAnchors(10, 22, 26, 27), block_id="load-totals",
    )


def build_report(fonts, image_path, *, variant="standard", display_values=None) -> Document:
    """Build a report from caller fonts, image and already-formatted result strings.

    display_values replaces known results only; the sample expressions and input
    conditions are authored separately. Values are never calculated or rounded.
    """
    if variant not in ("standard", "long"):
        raise ValueError("variant must be 'standard' or 'long'")
    long = variant == "long"
    values = {
        "area": "12.1500" if long else "12.150",
        "inertia": "7.3811250" if long else "7.381125",
        "section_modulus": "5.46750" if long else "5.4675",
        "vertical": "40.000" if long else "40.00",
        "horizontal": "7.000" if long else "7.00",
        "adjustment": "1.000",
    }
    if display_values is not None:
        if not isinstance(display_values, Mapping):
            raise ValueError("display_values must be a mapping of known result names to strings")
        for key, value in display_values.items():
            if key not in values or not isinstance(value, str):
                raise ValueError(f"display_values[{key!r}] must name a known result and contain a string")
            values[key] = value
    conditions = ("矩形断面の幅を b、高さを h とする。寸法は m、力は kN を用い、"
                  "断面諸量の単位を各式の右側に記す。図は部材と荷重方向の関係を示す模式図である。")
    if long:
        conditions += ("部材中心線と作用位置の関係は、橋軸方向と橋軸直角方向でそれぞれ確認する。"
                       "断面の寸法は設計図に記載された値を用い、柱高と混同しない。"
                       "荷重の正負は採用する座標系に従い、入力資料と結果表で同じ規約を使う。"
                       "単位を変更する場合は、荷重、寸法および断面諸量を一括して換算した表示値を用意する。")
    notes = ("断面諸量と方向別の荷重を整理した。適用時は、部材形状、荷重の組合せ、作用位置と単位を"
             "原資料と照合する。照査に用いる基準値と計算過程は案件ごとに別途定める。")
    if long:
        notes += ("荷重組合せの管理では、ケース番号だけでなく荷重方向と作用位置を併記する。"
                  "原資料が更新されたときは変更箇所と更新日を記録し、旧条件による値が残っていないか確認する。"
                  "末尾のゼロも表示精度を表すため保持する。数式中の入力値と結果欄は同じ資料に基づいて揃える。"
                  "図に示す寸法は位置関係の説明に用い、図から長さを読み取って計算値を置き換えない。"
                  "添付資料と本書をまとめて管理し、照合できる状態を保つ。")
    return Document(
        Heading("橋脚部材の計算整理", block_id="report-title"),
        Paragraph("断面寸法、作用荷重および荷重組合せを整理する。本書の数値は説明用の表示例であり、"
                  "実案件では採用する設計条件と計算済みの値に置き換える。", block_id="introduction"),
        Spacer(1),
        Heading("1 計算条件"),
        Paragraph(conditions, block_id="conditions-text"),
        Spacer(1),
        Table((7, 8, 15), [["項目", "表示値", "内容"],
                           ["断面幅 b", "4.50 m", "矩形断面の幅"],
                           ["断面高 h", "2.70 m", "矩形断面の高さ"],
                           ["柱高", "3.00 m", "基部から梁下面まで"]], header_rows=1,
              block_id="conditions-table"),
        Spacer(1),
        Columns(_load_figure(), Image(image_path, col_span=12, rows=15, block_id="site-image"),
                col_spans=(17, 12), gap_cols=1, block_id="overview"),
        Columns(Paragraph("図1 部材・荷重方向と主要寸法"), Paragraph("図2 河川橋の概念図"),
                col_spans=(17, 12), gap_cols=1),
        Paragraph("図の寸法と断面寸法は別項目として記録する。各方向の作用値は荷重組合せ一覧にまとめる。"),
        PageBreak(),
        Heading("2 断面諸量"),
        Paragraph("矩形断面の幾何量を以下に示す。表示桁は原資料の指定を保持し、式と単位を対応させる。"),
        _section_equations(values, long=long),
        Spacer(1),
        Stack(
            Columns(MathBlock("A"), Paragraph("断面積。幅と高さの積。"), col_spans=(3, 26)),
            Columns(MathBlock("I"), Paragraph("断面二次モーメント。曲げに関係する幾何量。"), col_spans=(3, 26)),
            Columns(MathBlock("W"), Paragraph("断面係数。中立軸から縁端までの距離で I を除した値。"), col_spans=(3, 26)),
            block_id="section-definitions",
        ),
        Spacer(1),
        Heading("3 作用荷重"),
        Paragraph("鉛直方向と水平方向の作用値を別々に整理する。加算項の順序を保ち、単位を合計値に付す。"),
        _load_equations(values, long=long),
        Spacer(1),
        Paragraph("補正係数 η は下式で表す。ここでは β = 0、γ = 0 を与えた値を示す。"),
        EquationGroup(Equation("η", Script(Delimited(Fraction("1", Row("1", Operator("+"),
                            Fraction(Script("β", superscript="2"), Root(Row("1", Operator("+"), "γ")))))),
                            superscript=Fraction("1", "2")), result=values["adjustment"]),
                      anchors=EquationAnchors(10, 22, 26), block_id="adjustment-factor"),
        PageSection(A3_LANDSCAPE_REFERENCE,
                    Heading("4 荷重組合せ一覧"),
                    Paragraph("組合せごとに橋軸方向と橋軸直角方向を対として示す。軸力、せん断力、曲げモーメント、"
                              "偏心量および係数を横に並べ、各方向の条件を比較する。"),
                    Spacer(1), _combination_table(long=long)),
        Heading("5 整理と確認事項"),
        Paragraph(notes),
        Spacer(1),
        Heading("記号と単位"),
        Columns(MathBlock("N"), Paragraph("軸力。部材軸方向の力で、単位は kN。"), col_spans=(3, 26)),
        Columns(MathBlock("V"), Paragraph("せん断力。部材軸に直交する力で、単位は kN。"), col_spans=(3, 26)),
        Columns(MathBlock("M"), Paragraph("曲げモーメント。単位は kNm。"), col_spans=(3, 26)),
        Columns(MathBlock("e"), Paragraph("偏心量。軸力に対する曲げモーメントの比で、単位は m。"), col_spans=(3, 26)),
        Spacer(1),
        Heading("確認事項"),
        Paragraph("・断面の幅と高さ、および荷重の方向を確認する。\n"
                  "・作用位置と偏心量の符号規約を統一する。\n"
                  "・原資料の表示精度と単位を維持する。\n"
                  "・変更した条件に関連する計算値を一括して更新する。"),
        Spacer(1),
        Paragraph("記録欄：条件確認日、担当者、参照資料番号を案件の管理方法に従って記入する。"),
        fonts=fonts,
        header=PageDecoration("橋脚部材の計算整理"),
        footer=PageDecoration("{page} / {pages}", align="right"),
    )


def write_report(output, font_path, *, image_path=None, variant="standard", preview=False):
    """Write normal/grid PDFs and JSON from one immutable layout result.

    A .pdf output selects the exact normal filename; other paths are directories.
    Only --preview needs the optional development package PyMuPDF.
    """
    fonts = FontRegistry()
    fonts.register("body", font_path)
    image_path = Path(image_path) if image_path is not None else Path(__file__).resolve().parent / "assets/bridge-overview.png"
    pages = build_report(fonts, image_path, variant=variant).layout()
    output = Path(output)
    normal = output if output.suffix.lower() == ".pdf" else output / "representative-report.pdf"
    grid = normal.with_name(normal.stem + "-grid.pdf")
    trace = normal.with_suffix(".json")
    render_pdf(pages, normal, fonts)
    render_pdf(pages, grid, fonts, debug_grid=True)
    trace.write_text(json.dumps(layout_trace(pages, fonts), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if preview:
        try:
            import pymupdf
        except ImportError as exc:
            raise RuntimeError("--preview requires the development dependency PyMuPDF") from exc
        previews = normal.parent / "previews"
        previews.mkdir(parents=True, exist_ok=True)
        for path in (normal, grid):
            with pymupdf.open(path) as pdf:
                for number, page in enumerate(pdf, 1):
                    page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(
                        previews / f"{path.stem}-page-{number}.png")
    return normal, grid, trace


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True, help="Embeddable TrueType font supporting Japanese and math symbols")
    parser.add_argument("--output", type=Path, required=True, help="Output directory or normal PDF filename")
    parser.add_argument("--image", type=Path, help="PNG/JPEG; defaults to assets/bridge-overview.png beside this script")
    parser.add_argument("--variant", choices=("standard", "long"), default="standard")
    parser.add_argument("--preview", action="store_true", help="Render all pages as PNG (development dependency PyMuPDF)")
    options = parser.parse_args(argv)
    for path in write_report(options.output, options.font, image_path=options.image,
                             variant=options.variant, preview=options.preview):
        print(path)


if __name__ == "__main__":
    main()
