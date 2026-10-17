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

## 帳票全体の設定

`Document(*blocks, fonts, profile=A4_PORTRAIT_REFERENCE, style=ReportStyle(), header=None, footer=None)`が帳票全体の既定を決める。部品側でstyleを省略したときは、この設定を使う。

| 引数 | 既定 | 内容 |
|---|---|---|
| `*blocks` | なし | 本文へ流す部品。Stackは展開し、PageBreak・PageSection・Atは配置指示として扱う |
| `fonts` | 必須 | 登録済みのFontRegistry。書体はTextStyle.fontの名前で選ぶ |
| `profile` | `A4_PORTRAIT_REFERENCE` | 用紙寸法・グリッド・本文行範囲 |
| `style` | `ReportStyle()` | 本文と見出しのTextStyle、基線offset、追加字間上限、段落の最小分割行数 |
| `header` | `None` | 本文上の予約枠に置くPageDecoration |
| `footer` | `None` | 本文下の予約枠に置くPageDecoration |

書体と用紙をまとめて変更する例：

```python
from gridlayoutpdf import (
    A3_LANDSCAPE_REFERENCE, Document, FontRegistry, PageDecoration, ReportStyle, TextStyle,
)

fonts = FontRegistry()
fonts.register("mincho", "C:/Windows/Fonts/msmincho.ttc")
fonts.register("gothic", "C:/Windows/Fonts/msgothic.ttc")

report = Document(
    *blocks,
    fonts=fonts,
    profile=A3_LANDSCAPE_REFERENCE,
    style=ReportStyle(
        body=TextStyle("mincho", 10.5),
        heading=TextStyle("gothic", 12),
        baseline_offset=11.0,
        min_first_lines=2,
        min_last_lines=2,
    ),
    header=PageDecoration("橋脚設計計算書", align="right"),
    footer=PageDecoration("{page} / {pages}", align="center", style=TextStyle("gothic", 9)),
)
```

用紙だけを変える場合は`profile=derived_profile("B4", 729, 1032)`のように派生profileを渡す。一部の範囲だけ用紙を変えるときは`PageSection`を使う。`style`を渡したうえで個別の部品に`style=TextStyle(...)`を与えると、その部品だけ上書きできる。`Document`とその設定は不変なので、別の体裁で出すときは新しい`Document`を作る。

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

`Script(base, superscript=None, subscript=None, *, scale=.65, superscript_rise=None, subscript_drop=None)`は、添字のサイズ比と基線位置を明示できる。scaleは有限の`0 < scale <= 1`、rise/dropは基底の基線から上／下への正のpt距離。指定しないoffsetは従来の安全な自動配置を使う。添字がない側へのoffset指定、不正な役割や字形の接触は拒否し、明示値を自動補正しない。既定引数の描画は従来どおり。

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

必要な境界だけに罫線を引く場合は、`horizontal_rules`と`vertical_rules`へ線幅のtupleを渡す。水平は行数+1個、垂直は列数+1個で、先頭は上端／左端、末尾は下端／右端。有限の非負値を指定し、0は非描画、Noneは既存のborder_widthによる全面罫線。たとえば4行8列表なら`horizontal_rules=(1, .12, 0, 0, 1)`で上端・ヘッダー境界・下端だけを描ける。色は共通のborder_colorを使う。

`row_heights=(...)`は各元行の高さを局所グリッドの正の整数行数で固定する。元の表の行数と同じ個数を指定し、`None`では従来どおり自動計測する。例えば局所`pitch_y=.01`なら`row_heights=(1428, 1428)`は各14.28ptとなる。セルの計測高と上下paddingが指定高を超える場合、`LayoutOverflowError`に必要量・使用可能量・セルIDを含めて停止する。行の拡大や文字の縮小は行わない。rowspanは結合した行の合計高を使い、改ページ時の繰返しヘッダーも指定高を保持する。

結合セルを横切る線は指定があっても描かない。分割・ヘッダー再掲後も元の行列番号を保ち、0指定の断片端へ外枠を補わない。線幅は1ストロークの幅なので、隣接する独立行群の境界には従来と同じ二重線の性質が残る。字形と罫線の余裕は各辺の実線幅で検証し、線がない辺でもセル枠外へのはみ出しは拒否する。

`Table(..., split=False)`はヘッダーを含む全行を一つの不可分な表として計測する。同じ境界の罫線を統合し、共有横境界を1本に、連続する縦線を一続きにする。明示行高・結合セル・選択罫線を維持し、ページに入らない表はエラーになる。既定の`split=True`は従来の分割・ヘッダー再掲・行群ごとの罫線を維持する。

## 密なセルと四辺の余白

`Cell.padding`は既存の数値（全辺共通pt）に加え、不変の`Insets(top=0, right=0, bottom=0, left=0)`を受け付ける。値は有限の非負数で、boolは拒否する。左右の余白だけを増やせば、上下の予約高は変わらない。必要高は子の予約高＋上余白＋下余白で、明示`row_heights`へ収まらない場合は行を拡大せず停止する。

```python
from gridlayoutpdf import Cell, CellLines, Insets, Script, Table, TextStyle

dense = Table(
    (8, 8),
    [[Cell(CellLines(("荷重", "12.50"), line_advance=12.8,
                     style=TextStyle(size=10), align="center"),
           padding=Insets(left=.6, right=.6)),
      Cell(CellLines((Script("m", superscript="2"),),
                     inner_padding=Insets(top=1, right=.6, bottom=1, left=.6)), padding=0)]],
    split=False,
)
```

`CellLines(lines, *, style=None, line_styles=None, line_advance=12.8, min_height=0, inner_padding=0, align='left', block_id='')`は文字列またはMathNodeの明示行を組むBlock。自動改行はせず、各行をpt単位で配置した後、内側余白・最低高を含む高さを一度だけ整数グリッド行へ切り上げる。空行を消さず、全空行でも正の領域を予約する。行別styleを指定する場合は行数を一致させる。alignは各行を部品内で揃える指定で、Cell.alignによる部品全体の配置とは別。

密なセルでは`Cell(..., padding=0)`とし、`CellLines.inner_padding`へ必要な余白を含めると、子の丸め後に再び上下余白を足すことを避けられる。外側paddingを指定した場合も無視せず加算する。幅不足、指定行間での字形接触、枠外へのはみ出しは部品IDと行番号を含むエラーになる。文字サイズ・行間を自動で縮める機能はない。

Tableの確定metadataには解決した四辺余白、子の予約高、丸め前の必要pt高、必要行数と割当高、自動／明示モード、行高を支配したセルとrowspan追加分を含む。`layout_trace`から、小さい上下余白でも追加行が必要になった理由を確認できる。

## 表や部品の90度回転

`QuarterTurn(block, *, turns, local_grid, block_id='')`は子部品を局所グリッドで計測し、拡大縮小せず90度回転する。`turns=1`は反時計回り、`-1`は時計回り。`local_grid`は原点(0, 0)の`GridSpec`で、子の利用可能な幅・高さと明示的な行間を指定する。書体とReportStyleは呼出側のものを使う。

```python
from gridlayoutpdf import Cell, GridSpec, QuarterTurn, Table

turned_table = QuarterTurn(
    Table((8, 8, 14), [[Cell("種別"), "値", "注記"],
                       ["A", "12.50", "表示値を保持"]]),
    turns=1,
    local_grid=GridSpec(0, 0, 12, 15.48, 30, 30),
    block_id="turned-table",
)
```

回転後の占有高は外側の整数グリッド行へ切り上げ、全体を分割しない。文字・線・折れ線・長方形に対応し、すでに回転したTextの向きも合成する。画像、未知の描画命令、空または可視内容のない子、無効な引数は`ValueError`。子の局所枠、回転後の幅・高さ、実字形・線幅が容量を超えれば`LayoutOverflowError`になり、自動縮小しない。

診断metadataの`child`は子の局所座標を保持する。`local_to_part=(a,b,c,d,e,f)`を使い、`x'=a*x+c*y+e`、`y'=b*x+d*y+f`で回転partの座標へ写す。その後に親の配置平行移動を1回加える。子の各partには累積`row`・`y_pt`と元の`row_pitch`が残り、セル枠や数式アンカーをページ座標と取り違えずに追跡できる。

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

`Image("detail.png", width_pt=123.25, height_pt=80.5, align="left", valign="top")`のように物理寸法のペアを渡すと、指定ptで描き、幅はそのまま、高さだけ整数行へ切り上げて予約する。画像の比率と寸法を一致させる必要があり、許容する差はEXIF補正後の各軸±0.5pixelに相当する丸めだけ。受理したpt値を変更しない。

`col_span`／`rows`のペアも指定すれば、そのグリッド枠内でalign／valignに従って配置する。既定はcenter／middleなので、物理寸法だけでも予約行の余りへ縦中央配置する。上端に固定する場合は`valign="top"`を指定する。寸法の片方だけの指定、比率不一致、枠不足を拒否し、縮小や切り抜きで収容しない。物理寸法を省略した既存のfit動作は変わらない。

## 改ページ・位置指定・用紙混在

`PageSection(profile, *blocks)`の範囲だけ用紙を切り替え、退出時は親の用紙へ新ページで戻る。ネストも同じ規則。profile・利用幅に応じて部品を再計測し、文字サイズを維持する。参照A4/A3とderived_profileは共通のグリッドピッチを使い、独自のPageProfileでは指定したgridを使う。空セクションは進行中のページを分断しない。

`At(row, col, col_span, block)`は現在ページのグリッド原点から位置を指定する。現在のフローカーソルより前へ戻れず、本文外にも置けない。成功すると部品の終端行まで縦帯全体を予約する。同じ行へ複数のAtを置く代わりにColumnsを使う。Atは自動改ページしない。

見出しが連続した場合は連鎖全体と次の本文を同居させる。途中のSpacerは高さに含めるが、本文の代わりにしない。次の可視部品より先に明示改ページ・用紙境界・At・文書末尾に達するkeep_with_nextはエラーになる。

`PageDecoration(text, rows=1, gap_rows=1, align='left', style=None)`でヘッダー・フッターを指定する。本文の上下の予約枠に、全ページ確定後に描く。既定は本文書体の9pt。`{page}`と`{pages}`、`{page:03d}`などの整数書式を使える。枠が紙外に出る場合や文字が入り切らない場合は、本文を再配置せずエラーにする。

## 診断・部品拡張

`Document.layout()`は確定したScenePage列を返す。`Document.render()`は全ページの配置成功後に一時ファイルへPDFを作り、最後に出力先を置き換える。空文書をrenderした場合や計測・描画が失敗した場合、既存の出力を成功扱いで上書きしない。

`LayoutOverflowError`にはblock_id、needed、availableがある。幅はpt、文書の高さ予約は行数としてメッセージに単位を示す。識別しやすい`block_id`を部品へ付けると、長い帳票の問題箇所を追いやすい。

`render(..., debug_grid=True)`でグリッドを表示できる。`render(..., invariant=True)`（`render_pdf`も同じ）は作成日時と文書IDを書き込まず、同じページから同じbytesのPDFを作る。既定値`False`ではReportLabの日時付きメタデータを保つ。`layout_trace(pages, fonts)`は用紙・配置・ローカルアンカー・描画境界をJSON保存可能なdictへ変換する。画像bytesは含めない。ローカルの基線やアンカーは、配置元のx/yと合わせて解釈する。

独自部品は`measure(context, available_width) -> MeasuredBlock`を実装する。計測中にPDF Canvasを触らず、左上原点の相対描画命令をLayoutPartへ入れる。Textのyだけは基線。外側の高さは整数行にし、分割可能な境界ごとにpartを分ける。`measure_block`で型・幅・ピッチ・描画境界を共通検証できる。詳しい責務は[アーキテクチャ](architecture.md)を参照。

`Text(x, y, text, style, quarter_turns=0, shear_x=0.0)`は基線原点の周りで文字を90度ずつ反時計回りに回転する。`quarter_turns`は0〜3の整数で、1は紙面上で下から上へ進む文字、2は180度、3は時計回り90度。boolは受け付けない。平行移動しても向きは変わらない。`command_bounds`は変換した実字形の境界を返す。診断JSONは回転文字に`quarter_turns`と`direction`を追加し、既定の水平文字の形式は維持する。

`shear_x`は有限の実数で、正値は文字の上端を右へ傾ける。基線原点を基準に、上原点の局所座標で`x'=x-shear_x*y`を適用してから回転する。例えば`.342`は原本の人工斜体を再現する指定で、字送りとtrackingは変えない。描画は埋込みフォントのPDF文字行列を使い、文字を画像や輪郭へ変換しない。`command_bounds`は傾斜後の四隅を含むため、セル端などで広がった字形が収まらなければ通常どおりエラーになる。0以外の値は診断JSONにも記録する。既定0では従来の文字表示と診断形式を維持する。

初期版は横書きの日本語・欧文と構造化数式を対象とする。完全なUnicode行分割、複雑文字のshaping、TeX解析、任意の大型演算子や行列、GUIデザイナー、外部PDFの取り込みは含まない。
