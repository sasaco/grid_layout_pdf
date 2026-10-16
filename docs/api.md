# APIガイド

文字・数式・表・図を部品として組み立て、`Document`で計測・改ページ・PDF出力する。計算結果の算出や数値の丸めは呼び出し側で行い、表示する文字列を渡す。

## 最初の計算書

```python
from gridlayoutpdf import (
    Document, Equation, EquationGroup, FontRegistry, Heading,
    Operator, PageDecoration, Paragraph, Row, Script,
)

fonts = FontRegistry()
fonts.register("body", "C:/path/to/ipaexm.ttf")

report = Document(
    Heading("断面諸量"),
    Paragraph("寸法と計算済みの表示値を共通の書式で配置します。"),
    EquationGroup(
        Equation(
            "A", Row("4.50", Operator("×"), "2.70"),
            label="断面積", result="12.150",
            unit=Script("m", superscript="2"),
        ),
    ),
    fonts=fonts,
    footer=PageDecoration("{page} / {pages}", align="center"),
)
report.render("report.pdf")
```

同じ書体・設定・入力で再計測できるよう、標準部品と計測結果は不変にしている。部品を組み替えるときは新しいインスタンスを作る。

## グリッド・用紙・書体

1マスは配置単位で、文字数とは独立している。本文は既定10pt、基線は行の上端から11pt。大きな字形・分数は必要な整数行を占有し、文字を縮小しない。通常の文章では各文字の自然な送りを使う。

| 設定 | 内容 |
|---|---|
| `A4_PORTRAIT_REFERENCE` | 595×842pt、30列×47行 |
| `A3_LANDSCAPE_REFERENCE` | 1191×842pt、67列×47行 |
| 共通のグリッド | 原点50.88／54.598pt、横16.08／縦15.48pt |
| `derived_profile(name, width, height)` | 同じピッチと参照余白で別の用紙を作る。寸法はpt |
| `PageProfile(..., body_start_row=0, body_end_row=None)` | グリッド内の本文行範囲を指定する。終端行は含まない |
| `TextStyle(font='body', size=10, tracking=0)` | 書体名・文字サイズ・明示的な追加字間 |
| `ReportStyle(...)` | 本文／見出しstyle、基線offset、追加字間上限、段落の最小分割行数 |

フォントは`FontRegistry.register(name, path, face_index=0)`で明示登録する。TrueTypeとTrueType collectionを扱い、CFF OpenTypeは対象外。ファイルのハッシュとfaceを使って計測・描画を揃える。パッケージに書体は同梱せず、OSの書体を自動検索しない。太字などは別の書体を登録し、`TextStyle(font=...)`で選べる。

文字列はNFCで正規化する。書体にない文字と、正規化後に残る結合マークは`FontError`になる。数式の上付き・下付きは、専用Unicode文字の代わりに`Script`で組める。

## 文章と容器

| 部品 | 用途 |
|---|---|
| `Paragraph(text, style=None, align='left', ...)` | 日本語の基本禁則と英数字の連続語を保って折り返す |
| `Heading(text, ...)` | 分割せず、次の可視部品の最小fragmentと同じページに置く |
| `Spacer(rows)` | 整数グリッド行の空白。0行も可 |
| `PageBreak()` | 明示改ページ。先頭・末尾・連続指定で空ページを増やさない |
| `Stack(*blocks)` | 縦に並べる。通常フローでは子の分割規則を維持する |
| `Columns(*blocks, col_spans=(...), gap_cols=1)` | 整数グリッド列幅で横に並べる。全体は分割せず、高さは子の最大値 |
| `KeepTogether(block)` | 子の途中で改ページしない |

`Paragraph.align`はleft/right/center/justify。justifyは最終行と明示改行の直前を自然な字間にし、それ以外の行だけ追加字間を試す。既定上限は1間隔0.05em。上限内で幅を埋められなければ合法な折り返し位置と自然な字間を使う。字形を横へ伸縮しない。

`fit_tracking(text, fonts, style, target_width)`は、分割しないラベル等のための厳密な幅合わせ。上限内で追加字間だけでは届かない場合に`LayoutOverflowError`を返す。行頭・行末のASCII空白は文章の折り返しで除き、内部空白と明示改行による空行は保持する。tabは拒否する。

段落は既定で、改ページ前後に表示上の行を2行以上残す。`min_first`／`min_last`で変更できる。グリッドの占有行数と表示上の行数は別に数える。ColumnsやKeepTogether内のStackは全体を分割しないため、大き過ぎる場合は明示エラーになる。

変数説明は既存部品を組み合わせる。

```python
from gridlayoutpdf import Columns, MathBlock, Paragraph, Stack, Symbol

definitions = Stack(
    Columns(MathBlock(Symbol("A")), Paragraph("断面積"),
            col_spans=(3, 26), gap_cols=1),
    Columns(MathBlock(Symbol("I")), Paragraph("断面二次モーメント"),
            col_spans=(3, 26), gap_cols=1),
)
```

## 数式・等号列

```python
from gridlayoutpdf import (
    BreakHint, Delimited, Equation, EquationAnchors, EquationGroup,
    Fraction, Operator, Root, Row, Script,
)

group = EquationGroup(
    Equation("I", Fraction(Row("b", Script("h", superscript="3")), "12"),
             label="断面二次モーメント", result="7.38113",
             unit=Script("m", superscript="4")),
    Equation("R", Row("12.50", Operator("+"), "8.75",
                      BreakHint("forced"), Operator("+"), "6.25"),
             label="反力", result="27.50", unit="kN"),
    anchors=EquationAnchors(first_equal=10, second_equal=22,
                            result_right=26, unit_start=27),
)
```

`Literal`・`Symbol`・`Operator`は文字、`Row`は横並び、`Fraction`は分数、`Root`は根号、`Script`は上下付き、`Delimited`は内容に応じた括弧を表す。文字列はLiteralに持ち上げる。TeXや文字列内の`*`・`^`などを解析しない。`Row`の分割候補となる記号は`Operator`として渡す。

`Equation(lhs, rhs, label='', result=None, unit=None, ...)`をまとめた`EquationGroup`内で、第一等号の送り中心、第二等号の送り中心、結果の右端、単位開始を共有する。アンカーはブロックの左端から数えた整数グリッド列。省略すると左辺・ラベル・結果・単位を計測して自動決定する。半角と全角の等号も送り中心を揃える。

結果がある明示アンカーにはsecond_equal/result_right、単位がある場合はunit_startも必要。unitだけを指定することはできない。右辺に単位を含める場合はRowで組む。式のstyleは式→グループ→本文の順で解決する。

折り返しは最上位のRowだけを対象にし、強制改行、preferred hint、関係演算子、加減算、allowed hintの順で候補を選ぶ。関係演算子や加減算記号は継続行の先頭へ残す。分数・根号・添字・括弧・入れ子Rowの内部は分断しない。

通常は結果列を先に予約する。その幅へ原子的な右辺が入らず、結果列を含む全幅なら入る場合、結果を専用の最終行へ送る。結果・単位のアンカーは保持する。それでも入らなければエラーとなり、文字サイズや用紙を自動変更しない。

単独の数式や表セルには`MathBlock(expression)`を使う。MathNodeと通常部品はmeasureの引数が違うため、数式をそのままCellへ渡さない。

## 結合セル表

```python
from gridlayoutpdf import Cell, Table

table = Table(
    (8, 8, 7, 7),
    [
        [Cell("区分", rowspan=2), Cell("表示値", colspan=2, align="center"),
         Cell("単位", rowspan=2)],
        [Cell("左側", align="center"), Cell("右側", align="center")],
        [Cell("区分A", rowspan=2), "12.150", "9.500", "kN"],
        ["7.38113", "6.25000", "kN"],
    ],
    header_rows=2,
    numeric_columns=(1, 2),
)
```

columnsは表の各列幅をグリッド列数で指定する。numeric_columnsは表の列番号（0始まり）で、align未指定かつcolspan=1のセルを右揃えにする。行のセルは既存rowspanが占めた列を飛ばして順番に置く。穴・重複・範囲外・ヘッダーと本文をまたぐrowspanはエラー。

文字列セルは自動でParagraphにする。`Cell(MathBlock(Fraction(...)))`等の部品も置ける。Cell.styleは文字列専用。部品を渡したときはその部品のstyleを設定する。全幅を確保するParagraphの内部の行揃えはParagraph自身で指定する。

行高は内容とpaddingから整数グリッド行で求める。rowspanの不足高は最終行へ加える。結合セルで接続した行群を途中で切らず、複数ヘッダー行を次ページにも再掲する。巨大な1セルや行群を内部で分割する機能はない。

罫線は各行群が独立して閉じるように描く。border_widthはその線幅で、同一ページに隣接する行群の境界は2本分の太さに見える。セル内の実字形と罫線の間に余裕がない設定はエラーになる。

## 図・画像

`Figure(col_span, rows, *items)`の外枠はグリッド単位、内部だけは左上原点のpt座標で記述する。Line/Polyline/Rectangle/Textと、矢印Arrow・文字Labelを置ける。図は分割せず、実字形と線幅を含めた枠内検査を行う。

```python
from gridlayoutpdf import Arrow, Figure, Image, Label, Rectangle

diagram = Figure(
    20, 8,
    Rectangle(20, 45, 240, 15),
    Arrow(140, 15, 140, 42),
    Label(160, 25, "荷重 P"),
    Label(140, 95, "L = 4.50 m", align="center"),
)
photo = Image("detail.png", col_span=20, rows=10)
```

Labelのyは基線、xはleft/center/rightのアンカー。Arrowは終点に開いた矢印を付ける。ゼロ長の矢印や枠外の文字・線は拒否する。

Imageは静止PNG/JPEGを対象に、指定枠へ縦横比を保って内接させる。alignはleft/center/right、valignはtop/middle/bottom。透明度とEXIF方向を処理し、計測時に画像bytesを固定する。配置結果を描画するまでに元ファイルが変わっても、出力画像は変わらない。

## 改ページ・位置指定・用紙混在

`PageSection(profile, *blocks)`の範囲だけ用紙を切り替え、退出時は親の用紙へ新ページで戻る。ネストも同じ規則。profile・利用幅に応じて部品を再計測し、文字サイズを維持する。参照A4/A3とderived_profileは共通のグリッドピッチを使い、独自のPageProfileでは指定したgridを使う。空セクションは進行中のページを分断しない。

`At(row, col, col_span, block)`は現在ページのグリッド原点から位置を指定する。現在のフローカーソルより前へ戻れず、本文外にも置けない。成功すると部品の終端行まで縦帯全体を予約する。同じ行へ複数のAtを置く代わりにColumnsを使う。Atは自動改ページしない。

見出しが連続した場合は連鎖全体と次の本文を同居させる。途中のSpacerは高さに含めるが、本文の代わりにしない。次の可視部品より先に明示改ページ・用紙境界・At・文書末尾に達するkeep_with_nextはエラーになる。

`PageDecoration(text, rows=1, gap_rows=1, align='left', style=None)`でヘッダー・フッターを指定する。本文の上下の予約枠に、全ページ確定後に描く。既定は本文書体の9pt。`{page}`と`{pages}`、`{page:03d}`などの整数書式を使える。枠が紙外に出る場合や文字が入り切らない場合は、本文を再配置せずエラーにする。

## 診断・部品拡張

`Document.layout()`は確定したScenePage列を返す。`Document.render()`は全ページの配置成功後に一時ファイルへPDFを作り、最後に出力先を置き換える。空文書をrenderした場合や計測・描画が失敗した場合、既存の出力を成功扱いで上書きしない。

`LayoutOverflowError`にはblock_id、needed、availableがある。幅はpt、文書の高さ予約は行数としてメッセージに単位を示す。識別しやすい`block_id`を部品へ付けると、長い帳票の問題箇所を追いやすい。

`render(..., debug_grid=True)`でグリッドを表示できる。`layout_trace(pages, fonts)`は用紙・配置・ローカルアンカー・描画境界をJSON保存可能なdictへ変換する。画像bytesは含めない。ローカルの基線やアンカーは、配置元のx/yと合わせて解釈する。

独自部品は`measure(context, available_width) -> MeasuredBlock`を実装する。計測中にPDF Canvasを触らず、左上原点の相対描画命令をLayoutPartへ入れる。Textのyだけは基線。外側の高さは整数行にし、分割可能な境界ごとにpartを分ける。`measure_block`で型・幅・ピッチ・描画境界を共通検証できる。詳しい責務は[アーキテクチャ](architecture.md)を参照。

初期版は横書きの日本語・欧文と構造化数式を対象とする。完全なUnicode行分割、複雑文字のshaping、TeX解析、任意の大型演算子や行列、GUIデザイナー、外部PDFの取り込みは含まない。
