# APIガイド

文字・数式・表・図を部品として組み立て、`Document`で計測・改ページ・PDF出力する。計算結果の算出や数値の丸めは呼び出し側で行い、表示する文字列を渡す。

## 最初の計算書

```python
from gridlayoutpdf import (
    Document, Equation, EquationGroup, Heading,
    Operator, PageDecoration, Paragraph, Row, Script,
)

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
    footer=PageDecoration("{page} / {pages}", align="center"),
)
report.render("report.pdf")
```

書体は既定で同梱のIPAex明朝を使う。ファイルの登録は要らない。

同じ書体・設定・入力で再計測できるよう、標準部品と計測結果は不変にしている。部品を組み替えるときは新しいインスタンスを作る。

## 帳票全体の設定

`Document(*blocks, fonts=None, profile=A4_PORTRAIT_REFERENCE, style=ReportStyle(), header=None, footer=None)`が帳票全体の既定を決める。部品側でstyleを省略したときは、この設定を使う。

| 引数 | 既定 | 内容 |
|---|---|---|
| `*blocks` | なし | 本文へ流す部品。Stackは展開し、PageBreak・PageSection・Atは配置指示として扱う |
| `fonts` | `None` | 書体名を書体ファイルへ引くFontRegistry。省略すると共有の既定のFontRegistryを使う。書体はTextStyle.fontの書体名で選ぶ |
| `profile` | `A4_PORTRAIT_REFERENCE` | 用紙寸法・グリッド・本文行範囲 |
| `style` | `ReportStyle()` | 本文と見出しのTextStyle、基線offset、追加字間上限、段落の最小分割行数 |
| `header` | `None` | 本文上の予約枠に置くPageDecoration |
| `footer` | `None` | 本文下の予約枠に置くPageDecoration |

書体と用紙をまとめて変更する例：

```python
from gridlayoutpdf import (
    A3_LANDSCAPE_REFERENCE, Document, PageDecoration, ReportStyle, TextStyle,
)

report = Document(
    *blocks,
    profile=A3_LANDSCAPE_REFERENCE,
    style=ReportStyle(
        body=TextStyle("ＭＳ 明朝", 10.5),
        heading=TextStyle("IPAexゴシック", 12),
        baseline_offset=11.0,
        min_first_lines=2,
        min_last_lines=2,
    ),
    header=PageDecoration("橋脚設計計算書", align="right"),
    footer=PageDecoration("{page} / {pages}", align="center", style=TextStyle("IPAexゴシック", 9)),
)
```

`ＭＳ 明朝`はWindowsの書体フォルダから名前で引く（英語名`MS Mincho`でもよい）。Windows以外では同梱の書体だけを探すため、この例は`FontError`になる。

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
| `TextStyle(font='IPAex明朝', size=10, tracking=0)` | 書体名・文字サイズ・明示的な追加字間 |
| `ReportStyle(...)` | 本文／見出しstyle、基線offset、追加字間上限、段落の最小分割行数 |

書体は`TextStyle(font=...)`に書体名で書く。ライブラリが書体名から書体ファイルを探す。書体名は書体ファイルのnameテーブルにあるファミリー名（nameID 1と16）またはフルネーム（nameID 4）の英語名・日本語名のどれか（例: `MS Mincho`・`ＭＳ 明朝`・`IPAexMincho`・`IPAex明朝`）で、表記は完全に一致させる。TrueType collectionの書体番号も名前から決まる（`MS PMincho`は`msmincho.ttc`の1番）。

探す順は、(1) パッケージに同梱したIPAex明朝・IPAexゴシック（004.01、IPAフォントライセンスv1.0、無改変）、(2) `%WINDIR%\Fonts`、(3) `%LOCALAPPDATA%\Microsoft\Windows\Fonts`。macOS・Linuxでは同梱の書体だけを探し、それ以外の書体名は`FontError`になる。同じ名前は先に探すフォルダのものを使う。同じフォルダの中では、フルネーム（nameID 4）、ファミリー名（nameID 1）、typographic family（nameID 16）の順に一致を調べ、同じ段階で別の書体が2つ以上一致すれば曖昧として`FontError`にする。エラーには候補のフルネームを示す（例: 同じファミリー名の標準と太字があるときは、`Yu Gothic Regular`のようにフルネームで1つに決める）。見つからないときは探したフォルダと同梱の書体名を示す`FontError`になる。書体フォルダの読めない・壊れたファイルは飛ばしてその数を示すが、フォルダそのものを一覧できないときは`FontError`で止める。同梱の書体が欠けている・壊れている・名前が違うときは、Windowsの同名の書体へ切り替えず`FontError`にする。`%WINDIR%`がなければ`%SystemRoot%`を使い、絶対パスでない値は使わない。

書体ファイルは、import時や`TextStyle`の生成時には探さず、初めて計測・描画するときに探す。`fonts`を省略した`Document`・`render_pdf`・`layout_trace`・`command_bounds`は共有の既定の`FontRegistry`を使う。`FontRegistry`は名前ごとに解決した`FontFace`（`name`は指定した書体名、`path`・`face_index`・`sha256`・`pdf_name`、`family`はWindows・Excelが使う英語のファミリー名nameID 1）を保ち、`resolve(name)`・`measure(text, style)`・`normalize_text(text)`を持つ。計測を差し替えるときは継承して`resolve`・`measure`を上書きする（`resolve`は`FontRegistry.resolve`が返した`FontFace`を返す）。`fonts`を明示して組んだページは、同じ`FontRegistry`を`render_pdf`・`layout_trace`にも渡す。TrueTypeとTrueType collectionを扱い、CFF OpenTypeは対象外。ファイルのハッシュとfaceを使って計測・描画を揃え、同梱の書体はmanifestのSHA-256と一致することも確かめる。`FontRegistry.register`による書体ファイルの登録は廃止した。

文字列はNFCで正規化する。書体にない文字と、正規化後に残る結合マークは`FontError`になる。数式の上付き・下付きは、専用Unicode文字の代わりに`Script`で組める。

## 文章と容器

| 部品 | 用途 |
|---|---|
| `Paragraph(text, style=None, align='left', ...)` | 日本語の基本禁則と英数字の連続語を保って折り返す |
| `Heading(text, ...)` | 分割せず、次の可視部品の最小fragmentと同じページに置く |
| `Spacer(rows, *, discard_at_page_top=False)` | 整数グリッド行の空白。0行も可 |
| `Rule(style=BorderStyle.THIN, *, columns=None, color=(0, 0, 0))` | 本文を横切る区切り線。1グリッド行（細かいグリッドでは線の太さが入る行数）を占め、その上の境目に罫線の種類で引く。幅は利用可能幅、または`columns`グリッド列。partのmetadataに`rule`（`style`・`width_pt`）を記録する |
| `PageBreak()` | 明示改ページ。先頭・末尾・連続指定で空ページを増やさない |
| `Stack(*blocks)` | 縦に並べる。通常フローでは子の分割規則を維持する |
| `Columns(*blocks, col_spans=(...), gap_cols=1)` | 整数グリッド列幅で横に並べる。全体は分割せず、高さは子の最大値 |
| `KeepTogether(block)` | 子の途中で改ページしない |
| `KeepWithNext(block)` | Headingと同様に、次の可視部品の最小fragmentと同じページに置く。子の分割規則は変えない |
| `PreferKeepTogether(block)` | 空ページに収まれば次ページへ送って分割を避け、1ページを超えるときだけ合法な位置で分割する |
| `Indent(block, left)` | 子をleft pt狭く計測し、右へleft pt移す。各partに`indent_pt`を記録する（入れ子では合計） |
| `Leading(block, rows, *, minimum=False, overhang=0.0)` | 本文の各part（表示行）をrows行にそろえる。不足する行は`LayoutOverflowError`、`minimum=True`では短い行だけ伸ばす。`overhang` ptまでの超過は行送りを保ってはみ出させる。繰返しprefixと、断片の端で描く命令を持つpart（分割する表の行群）の行数の変更は`ValueError` |
| `SideRule(block, x, *, style=BorderStyle.THIN, top=0.0, bottom=0.0, color=(0, 0, 0))` | 子の左端からx ptの位置（線の中心）に、各partの高さ全体の縦線を罫線の種類で引く。`top`は最初の本文part、`bottom`は最後の本文partの線を縮める。各partに`side_rule_pt`と`side_rule_style`（種類のExcel名）を記録する |

`Paragraph.align`はleft/right/center/justify。justifyは最終行と明示改行の直前を自然な字間にし、それ以外の行だけ追加字間を試す。既定上限は1間隔0.05em。上限内で幅を埋められなければ合法な折り返し位置と自然な字間を使う。字形を横へ伸縮しない。

`fit_tracking(text, fonts, style, target_width)`は、分割しないラベル等のための厳密な幅合わせ。上限内で追加字間だけでは届かない場合に`LayoutOverflowError`を返す。行頭・行末のASCII空白は文章の折り返しで除き、内部空白と明示改行による空行は保持する。tabは拒否する。

`Leading(block, rows, overhang=0.12)`は、行送りを固定したまま、字形が行の下へわずかにはみ出す表示行を許す。各partの測定行数がrowsを超えても、超過分（行数差×行ピッチ）が`overhang` pt以内ならそのpartをrows行に固定し、描画コマンドはそのまま次の行へはみ出させる。はみ出した量は各partのmetadataに`overhang_pt`として記録され（入れ子では合算）、`measure_block`はその量だけpartの下端より下のインクを許す。超過が`overhang`を超えるpartは従来どおり、`minimum=False`では`LayoutOverflowError`、`minimum=True`では伸ばしたままにする。`overhang`は有限の非負数（pt、boolは不可）で、既定の0では従来と同じ結果になる。はみ出しは次の行の字形との接触を検査しないため、下付き添字のような小さな超過に限って使う。`Stack`・`Columns`の中では全体を1つのpartとして計測するため、最終行のはみ出しは外側のpartを超えて`LayoutOverflowError`になる。

`Spacer(rows, discard_at_page_top=True)`は、LaTeXの`\vspace`（`\vspace*`ではない）のように頁頭で消える空白になる。文書の流し込みで、その頁にまだ何も置かれていない状態（文書の先頭、改ページの直後、頁末に収まらず次頁へ送られた場合を含む）で置こうとすると、行を進めずplacementも記録せずに捨てる。頁の途中では通常どおり行を確保する。印は`MeasuredBlock.discard_at_page_top`に載り、`KeepWithNext`・`KeepTogether`・`PreferKeepTogether`・`Indent`・`Leading`を通しても保たれる。`Stack`・`Columns`の中では全体を1つの部品として計測するため印は外側へ伝わらず、`At`の明示配置では捨てない。既定の`False`では従来どおり頁頭にも空白を残す。

`SideRule(block, x, top=…, bottom=…)`は、式のまとまりを左の縦線で括るときに使う。線の太さは`style`の罫線の種類（既定は細、pt の太さは指定できない）。実線の種類は子の各part（繰返しprefixを含む）に塗りの縦棒（`Rectangle(stroke=False)`、二重は中心間1.0 ptの2本）として足すので、インクはpartの中に収まり、同じ頁で続くpartの線はつながる。破線系の種類は破線の`Line`で、各partの中に線幅の半分だけ内側へ収める。改ページではその頁の最後のpartで切れ、次の頁の先頭のpartから続く。`top`・`bottom`（pt、有限の非負数）は線の始まりと終わりを行の中で縮め、partの高さを使い切る値は`ValueError`。幅・flag（`keep_with_next`・`discard_at_page_top`など）・分割規則は子のまま保ち、xが子の幅より右なら利用可能幅までの範囲で予約幅を広げ、超えれば`LayoutOverflowError`。いくつかの部品をまとめて括るときは、部品ごとに同じxで包み、最初の部品に`top`、最後の部品に`bottom`を渡す。頁頭で捨てられる`Spacer`を包めば、線も一緒に捨てられる。

```python
from gridlayoutpdf import BorderStyle, Rule, SideRule

separator = Rule(BorderStyle.MEDIUM, columns=20)
```

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

`Equation(lhs, rhs, label='', result=None, unit=None, ...)`をまとめた`EquationGroup`内で、第一等号の送り中心、第二等号の送り中心、結果の右端、単位開始を共有する。アンカーはブロックの左端から数えた整数グリッド列。省略すると左辺・ラベル・結果・単位を計測して自動決定する。半角と全角の等号も送り中心を揃える。`label_columns`を省略したラベルは計測した幅を確保し、上限は紙面上の96.48pt（グリッドのピッチによらない）で、超えるラベルは折り返す。

結果がある明示アンカーにはsecond_equal/result_right、単位がある場合はunit_startも必要。unitだけを指定することはできない。右辺に単位を含める場合はRowで組む。式のstyleは式→グループ→本文の順で解決する。

折り返しは最上位のRowだけを対象にし、強制改行、preferred hint、関係演算子、加減算、allowed hintの順で候補を選ぶ。関係演算子や加減算記号は継続行の先頭へ残す。分数・根号・添字・括弧・入れ子Rowの内部は分断しない。

通常は結果列を先に予約する。その幅へ原子的な右辺が入らず、結果列を含む全幅なら入る場合、結果を専用の最終行へ送る。結果・単位のアンカーは保持する。それでも入らなければエラーとなり、文字サイズや用紙を自動変更しない。

```python
from gridlayoutpdf import Equation, EquationGroup, Operator, Row, TermStop

def kv(alpha):
    return Row("5.1", TermStop("center"), Operator("×"), TermStop("right"), alpha,
               TermStop("center"), Operator("×"), TermStop("right"), "68600")

group = EquationGroup(Equation("kv", kv("0.5"), result="174930", unit="kN/m"),
                      Equation("kv", kv("1.0"), result="349860", unit="kN/m"),
                      term_gap=4)
```

右辺の最上位`Row`に幅のない`TermStop(align='left', width=None)`を置くと、その式は項の列揃えの式になる。TermStopで区切った区間が列となり、最初のTermStopより前の区間が左揃えの列0（先頭のTermStopは列0の揃えと最小幅を定める）。グループ内の列揃えの式で同じ番号の列は、最も広い区間（`width`の最小幅があればそれ以上）を列幅として共有し、`align`（left・center・right）に従って列内に置く。列の間隔は`EquationGroup(term_gap=...)`で、省略すると`gap`。同じ列番号でalignが食い違う場合と末尾のTermStopはValueError。列揃えで1行に置く式は`BreakHint`を無視し（幅0）、全列が通常の右辺幅に入らなければ結果を専用の最終行へ送る。1行に収まるかの判定はその式自身の最後の列までの幅で行い、同じグループの列の多い式に引きずられない。自身の列だけで並べても1行が全幅（結果のない式は通常の右辺幅）に入らない式は「退避」とし、退避した式を除いて列を決め直し、共有の列で入らなくなった式も退避する（退避が増えなくなるまで繰り返す）。退避した式は列幅の共有に加わらず、先頭以外の各TermStopの位置に`BreakHint('allowed')`を置いた`Row`（元の`gap`と`BreakHint`はそのまま）として通常の折り返しをし、それでも入らなければLayoutOverflowErrorとなる。各行のmetadataの`term_columns_pt`にその式が使う列の左端・幅・揃え（ブロック左端からのpt）を記録し、退避した式の行は`term_columns_pt`の代わりに`term_fallback: True`を持つ。TermStopを含まない式の配置は変わらない。

`EquationGroup(term_columns='packed')`（既定）は上のとおり列をptで詰めて並べる。`term_columns='grid'`は項の列をグリッドの列単位で割り当てる（FR-025）。各列は右辺の開始列（ブロック左端からの整数列）から隙間なく続き、列の境目から始まる。列の幅は、その列を使う各式について「項（`width`の最小幅があればそれ以上）＋その式の文字サイズでの`excel_cell_padding_pt(size)`×2」を求め、その最大が入る最小の列数とする。項のない列（幅0）は0列。項は列の左右からこの余白を除いた範囲に`align`で置く。8〜12 ptの文字ではExcelの実測の余白は左右とも2.4 pt以下で、左・右・中央のどの寄せ方でもExcelの表示と1 pt未満ずれる（左寄せは最大約0.6 pt、右寄せは最大約1 pt）。列の間隔は余白が担うので、`term_gap`との併用はValueError。1行に入るか・結果を専用の行へ送るかの判定は整数の列で行い、ちょうど範囲の端で終わる列は入る。それ以外の結果の専用行・退避と通常の折り返し・エラーの規則は`'packed'`と同じで、退避した式の配置は`'packed'`の退避と同一。単独の`Equation`は常に`'packed'`なので、`'grid'`にするには`EquationGroup`で包む。型注釈には`gridlayoutpdf.equations.TermColumns`（`Literal['packed', 'grid']`）を使える。

各行のmetadataは`term_columns_pt`（列の左端・幅・揃え、ブロック左端からのpt）に加えて、`term_columns_grid`（同じ列の（開始列, 列数, 揃え）、ブロック左端からの整数列。列数0の項もそのまま並ぶ）と`term_cell_padding_pt`（その式で使った片側の余白）を持つ（結果の専用行にも同じ鍵が付く）。ページの列は、ブロックの置かれた列を足して求める（合計と最も近い整数との差に`pitch_x`を掛けた長さが1e-6 ptを超えれば、揃っていない置き方として扱う。方眼Excelへの対応付けと同じ判定。そうでなければ`round()`で整数にする。ページのmetadataの配置の`col`に、式までの経路の各段のpartの`indent_pt / pitch_x`と、`Columns`・`Stack`の子（`children`）の`x_pt / pitch_x`を足す。入れ子の`Indent`の`indent_pt`はずれの合計）。描画命令のタグ（`equation_part`の`term`）は`index`と`align`に加えて、`'grid'`の時だけ`first_column`（その項の開始列、ブロック左端から）・`columns`（列数）・`cell_padding_pt`（その項で使った片側の余白。0列の項は0）を持つ。

`gridlayoutpdf.equations.EXCEL_CELL_PADDING_PT`（2.4 pt）は、Excel 16.0がセルの端と文字の間に取る片側の余白の実測値の上限（8〜12 ptの文字、ＭＳ 明朝・ＭＳ ゴシック・游明朝、ExcelのPDF書出し、100%、プリンターはPX-M6711FT Series。8〜12 ptの最大2.37 ptを0.05 pt単位で切り上げた値）。余白は文字サイズとともに約0.12 pt/ptで増えるため、`excel_cell_padding_pt(size_pt)`は12 ptを超える文字ではこれを`size_pt / 12`倍した値を返す（14 ptで2.8 pt、16 ptで3.2 pt。実測は14 ptで最大2.61 pt、16 ptで最大2.73 pt）。制限（実測。Excel 16.0、A4のグリッドの列21 pxを1〜8列結合したセル、右寄せの数値、ＭＳ 明朝 10 pt、Normalの書体は游ゴシック 11とＭＳ 明朝 10.5、プリンターはDocuWorks PDF）：この規則でちょうど収まる桁数の数値は、ExcelのPDF書出し（印刷、拡大率100%）では1〜8列のすべてで表示される。画面（ズーム100%、`Range.Text`）では1〜4列は表示されるが、5〜8列では「###」になる（画面の列は21 px＝15.75 ptで印刷より狭く、字の幅も画素に丸められるためと見られる）。これら以外のプリンターのドライバー（余白はDocuWorksで、「###」はPX-M6711FTで測っていない）と、`QuarterTurn`で回したセルの余白は測っていない。

### 方眼Excelで重ならない書き方

方眼Excel（FR-021）は文字片ごとにセルを作り、同じセルに文字片が重なると右へずらして記録する。次の書き方は、式の各部分が別々のセルになるようにするためのもので、方眼Excelへの対応付け（Step 8）の規則とあわせて使う。

- 等号・結果の等号・結果の右端・単位の開始は`EquationAnchors`の整数の列。等号はその列の境目に送りの中心を置くので紙面では境目をまたぐが、方眼Excelでは等号を、左辺と重ならない範囲で中心が紙面の位置に最も近い列のセル（1字の等号なら境目の右の列）にし、左辺を境目の左の列までのセルにする。ラベルは`label_columns`（省略時は計測した幅）の中に収める。折り返したラベルは、方眼Excelでは各行をそれぞれの行のセルに置く（式の行の縦結合には入れない）。
- 右辺で数値・演算子を並べる式は、最上位の`Row`の各項の間に`TermStop`を置き、`EquationGroup(term_columns='grid')`にする。各項が自分の列の範囲を持つ。数値は`TermStop('right')`、演算子は`TermStop('center')`で区切ると、行をまたいで桁と記号が揃う。
- `TermStop`は最上位の右辺の`Row`にだけ置ける。分数の分子・分母、根号・括弧の中の`Row`は1つの項の中身で、方眼Excelでは分子・中身ごとに1つのセルになる。
- 上付き・下付き（`Script`）の中に分数を入れない。セルのリッチテキストでは表せないため、方眼Excelは記録し、`strict=True`ではエラーになる。指数の分数は根号（`Root`）などの同じ意味の書き方にする。
- `'grid'`の列はブロックの左端から数える。ページの直下・`Columns`・`Stack`・`At`、`Indent`の`left`がピッチの整数倍の時（入れ子を含む）はページの列の境目に揃う。ptの`Indent`や表のセル（既定の内側の余白3 pt）の中では揃わない。
- `TermStop`のない`Row`と、退避した式（metadataの`term_fallback: True`。`'grid'`でも警告は出ない）は項をptで詰めて並べるので、方眼Excelでは同じセルに重なることがある。退避したら、アンカーを左へ寄せて右辺の列を増やすか、式を分ける。空でない項は`'grid'`で少なくとも1列を使うので、`'packed'`より横に長くなり、書体によって列数が変わる。
- 列揃えで1行に置く式は`BreakHint`を無視する。
- 例: `examples/representative_report.py --term-columns grid`（`build_report(..., term_columns='grid')`）。アンカーは既定の書体（IPAex明朝、10 pt）に合わせてあり、他の書体で項の列が退避すると`write_report`はValueErrorで止まる。

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

### 罫線の種類

罫線の太さはExcelの罫線の種類`BorderStyle`から選ぶ（pt の太さを直接指定する書き方はない）。値はExcelの名前で、文字列（`"thin"`など）でも渡せる。数値を渡すと`ValueError`。PDFでは次の線で描く。

| 種類 | 線幅 pt | 破線（描く長さ, 空ける長さ, … pt） |
|---|---|---|
| `hair`（極細） | 0.25 | 実線 |
| `thin`（細） | 0.5 | 実線 |
| `medium`（中） | 1.0 | 実線 |
| `thick`（太） | 1.5 | 実線 |
| `double`（二重） | 0.5 を2本 | 実線。線の中心の間隔1.0 pt（隙間0.5 pt、全体1.5 pt） |
| `dotted` | 0.5 | 0.5, 1.0 |
| `dashed` | 0.5 | 3.0, 1.5 |
| `dashDot` | 0.5 | 6.0, 1.5, 1.5, 1.5 |
| `dashDotDot` | 0.5 | 6.0, 1.5, 1.5, 1.5, 1.5, 1.5 |
| `mediumDashed` | 1.0 | 6.0, 2.0 |
| `mediumDashDot` | 1.0 | 6.0, 2.0, 2.0, 2.0 |
| `mediumDashDotDot` | 1.0 | 6.0, 2.0, 2.0, 2.0, 2.0, 2.0 |
| `slantDashDot` | 1.0 | 6.0, 1.0, 2.0, 1.0（斜めの切り口は描かない） |

`BorderStyle.thickness`は線の外側から外側までの太さ（二重は1.5 pt）、`stroke_width`・`dash`・`offsets`は1本ごとの線幅・破線・辺の中心線からのずれ、`lines(x1, y1, x2, y2, color)`は水平か垂直の辺の中心線に沿う線（二重は2本の`Line`）を返す。表と区切り線の線は`Table`・`Rule`・`SideRule`だけが描き、利用者が`Line`で描く必要はない。

`Table(..., borders=...)`は辺ごとに罫線の種類か線なし（`None`）を持つ。`borders`は`TableBorders`、全辺に使う1つの`BorderStyle`、または線なしの`None`。既定は全辺が細。

```python
from gridlayoutpdf import BorderStyle, Table, TableBorders

borders = TableBorders(
    BorderStyle.THIN,                     # 表全体の既定
    outer=BorderStyle.MEDIUM,             # 外枠（省略すると既定と同じ）
    horizontal={1: BorderStyle.DOUBLE},   # 行の境目1本ぶん（0が上端、行数が下端）
    vertical={2: None},                   # 列の境目1本ぶん（0が左端、列数が右端）
    horizontal_edges={(3, 1): None},      # 辺1つ：(行の境目, 列)
    vertical_edges={(0, 1): BorderStyle.HAIR},  # 辺1つ：(行, 列の境目)
)
table = Table((8, 8, 8), [["荷重", "G1", "G2"], ["終点", "12.50", "-3.00"], ["起点", "0.00", "4.50"]],
              header_rows=1, borders=borders)
```

1つの辺には、書いた順序によらず、より具体的な指定が優先する：辺1つ（`horizontal_edges`・`vertical_edges`）→ 境目1本ぶん（`horizontal`・`vertical`）→ 外枠（`outer`）→ 既定。`frame`は外枠が解決する種類（`outer`を指定しなければ既定）、`resolve(行数, 列数)`は辺ごとの種類（結合セルの内側を消す前）を返す。`horizontal_edges`で一部の列だけの横線を引ける（例：`{(2, c): BorderStyle.THIN for c in range(1, 3)}`）。結合セルの内側の辺は指定があっても引かず、`horizontal_edges`・`vertical_edges`で結合セルの内側の辺を名指すと`ValueError`。表の外の番号も`ValueError`。4つの対応表は不変の`(番号, 種類)`の組として写し取り、その組の形でも受け付ける（同じ番号の重複は`ValueError`）。色は共通の`border_color`を使う。

外枠の線は表の内側に収め、それ以外の線は境目を中心に引く。同じ種類で続く辺は、行群の中では1本の線にまとめる。分割できる表（既定の`split=True`）の行群の境目も1本の線で、同じ頁の中では実線の種類のインクが分割しない表と同じになる（縦線は上の行群が境目で止め、下の行群が境目から始める）。破線の種類では、破線の模様が行群ごとに初めから始まる。改ページで行群の間が切れたときは、上の行群がその頁の下端の線を自分の中に引いて頁を閉じ、次の頁の先頭に来た行群だけが自分の上の線を自分の中に引く。繰り返すヘッダーは自分の下の線（ヘッダーの下の境目の種類）を引き、その下に続く本文の行群は上の線を重ねて引かない。

セルの中身は、出会う可能性のある線から離れていなければならない。行群の上下と表の外枠では線の太さ全体、それ以外の境目では太さの半分だけ離す（二重線・破線も`thickness`で数える）。ヘッダーを繰り返す表では、後の頁でヘッダーの真下に来る本文の各行群の上端も、ヘッダーの下の線の太さの半分だけ離す。足りなければ`LayoutOverflowError`。線のない辺でもセル枠の外へのはみ出しは拒否する。外枠の角やT字の交わりでは、線の端を線幅の半分だけ内側で止めるため小さな欠けが残る。各セルのmetadataには`align`・`valign`と、四辺の辺ごとの種類（`borders`：`top`・`bottom`は列ごと、`left`・`right`は行ごと、線なしは`None`）を記録する。

`row_heights=(...)`は各元行の高さを局所グリッドの正の整数行数で固定する。元の表の行数と同じ個数を指定し、`None`では従来どおり自動計測する。例えば局所`pitch_y=.01`なら`row_heights=(1428, 1428)`は各14.28ptとなる。セルの計測高と上下paddingが指定高を超える場合、`LayoutOverflowError`に必要量・使用可能量・セルIDを含めて停止する。行の拡大や文字の縮小は行わない。rowspanは結合した行の合計高を使い、改ページ時の繰返しヘッダーも指定高を保持する。

分割・ヘッダー再掲後も元の行列番号を保ち、線なしの境目の断片端へ外枠を補わない。

`Table(..., split=False)`はヘッダーを含む全行を一つの不可分な表として計測する。明示行高・結合セル・選択罫線を維持し、ページに入らない表はエラーになる。既定の`split=True`は分割・ヘッダー再掲を行い、同じ頁の中では`split=False`と同じ罫線になる。

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

列幅を合計グリッド数の比で配分するには`proportional_spans(weights, total)`を使う。境界を累積比の丸めで決めるため、合計は常にtotalと一致し、丸め誤差は列をまたいで蓄積しない。1単位未満の列が生じる場合は`ValueError`。

```python
from gridlayoutpdf import Table, proportional_spans

Table(proportional_spans((2, 1, 1), 30), [["名称", "値", "単位"]])
```

`CellLines(lines, *, style=None, line_styles=None, line_advance=12.8, min_height=0, inner_padding=0, align='left', wrap=False, block_id='')`は文字列またはMathNodeの明示行を組むBlock。既定では自動改行せず、`wrap=True`の場合だけ文字列行を左右の内側余白を除いた幅で`wrap_text`により折り返す（追加字間なし、空文字列は行を作らない、MathNodeと行別styleはそのまま）。各行をpt単位で配置した後、内側余白・最低高を含む高さを一度だけ整数グリッド行へ切り上げる。空行を消さず、全空行でも正の領域を予約する。行別styleを指定する場合は行数を一致させる。alignは各行を部品内で揃える指定で、Cell.alignによる部品全体の配置とは別。

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

`Figure(col_span, rows, *items)`の外枠はグリッド単位、内部だけは左上原点のpt座標で記述する。Line/Polyline/Rectangle/Circle/Textと、矢印Arrow・文字Labelを置ける。図は分割せず、実字形と線幅を含めた枠内検査を行う。

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

LineとPolylineは`dash=(on, off, ...)`でpt単位の破線になる（始点から位相0、Polylineは頂点をまたいで継続）。Rectangleと`Circle(x, y, radius, *, stroke_width=.5, color=(0,0,0), fill=None, stroke=True)`は`fill`で塗り、`stroke=False`なら塗りだけを描く。線も塗りもない図形は拒否する。線なしの図形の範囲は線幅を含まない正確な外形になる。

```python
from gridlayoutpdf import Circle, Figure, Line, Rectangle

marks = Figure(
    10, 4,
    Line(10, 10, 130, 10, .35, dash=(2, 2)),
    Rectangle(20, 20, 30, 12, fill=(1, 1, 1), stroke=False),
    Circle(80, 30, 1.7, fill=(0, 0, 0), stroke=False),
)
```

Labelのyは基線、xはleft/center/rightのアンカー。Arrowは終点に開いた矢印を付ける。ゼロ長の矢印や枠外の文字・線は拒否する。

フローチャートの部品も`Figure`に置ける。`TextBox(x, y, width, height, lines, *, style=None, leading=None, padding=3.0, rounded=False, stroke_width=.6, color=(0,0,0))`は箱の中央に複数行の文字を置く処理の箱で、`rounded=True`なら短辺の半分を半径とする角丸の端子になる。`TextDiamond(x, y, width, height, lines, ...)`は外接する箱(x, y, width, height)の菱形に文字を置く判定、`Connector(points, *, head_length=6.0, head_width=4.0, width=.6, color=(0,0,0))`は折れ線の終点にArrowと同じ矢じりを付ける線である。行送り`leading`は基線から基線までで、既定は文字サイズの1.4倍。文字は自動縮小せず、箱では`padding`を除いた内側、菱形では各行の字形の高さでの菱形の内側（輪郭から横方向に`padding`）に収まらなければ`LayoutOverflowError`になる。Yes/Noなどの注記には`Label`を使う。角丸は`Rectangle(..., corner_radius=r)`（0以上、短辺の半分以下）で、範囲は角丸のない箱と同じ。

```python
from gridlayoutpdf import Connector, Figure, Label, TextBox, TextDiamond

flow = Figure(
    20, 12,
    TextBox(100, 2, 80, 24, ("START",), rounded=True),
    Connector(((140, 26), (140, 44))),
    TextDiamond(80, 44, 120, 40, ("σb ≦ σbl",)),
    Connector(((200, 64), (250, 64), (250, 100))),
    Label(205, 60, "No"),
)
```

Imageは静止PNG/JPEGを対象に、指定枠へ縦横比を保って内接させる。alignはleft/center/right、valignはtop/middle/bottom。透明度とEXIF方向を処理し、計測時に画像bytesを固定する。配置結果を描画するまでに元ファイルが変わっても、出力画像は変わらない。

`Image("detail.png", width_pt=123.25, height_pt=80.5, align="left", valign="top")`のように物理寸法のペアを渡すと、指定ptで描き、幅はそのまま、高さだけ整数行へ切り上げて予約する。画像の比率と寸法を一致させる必要があり、許容する差はEXIF補正後の各軸±0.5pixelに相当する丸めだけ。受理したpt値を変更しない。

`col_span`／`rows`のペアも指定すれば、そのグリッド枠内でalign／valignに従って配置する。既定はcenter／middleなので、物理寸法だけでも予約行の余りへ縦中央配置する。上端に固定する場合は`valign="top"`を指定する。寸法の片方だけの指定、比率不一致、枠不足を拒否し、縮小や切り抜きで収容しない。物理寸法を省略した既存のfit動作は変わらない。

`PdfFigure(col_span, rows, data, *, page=0, preview=None, align="center", valign="middle", block_id="")`は、ベクターのPDF（CADの図など）の1頁をグリッド枠に置く。`data`はPDFのbytes、`page`は0から数える頁。頁の表示範囲（CropBox、無ければMediaBox）を、縦横比を保って枠に内接するよう拡大・縮小し、align／valignで寄せる（既定は中央）。PDFでは頁の内容を1つのform XObjectとして描くので、線も文字もベクターのまま残り、CropBoxの外は切り取られる。同じbytesの同じ頁を何度置いてもPDFには1つだけ書く。注釈・フォームは描かない。

```python
from gridlayoutpdf import PdfFigure

drawing = PdfFigure(30, 20, pdf_bytes, preview=png_bytes, block_id="配筋図")
```

`data`は作った時に読み、PDFとして読めない・暗号化されている・その頁がない・頁が回転（`/Rotate`）している・表示範囲の面積が0のときは`ValueError`（`block_id`を前に付ける）。枠が利用幅を超えれば計測時に`LayoutOverflowError`。分割せず、`QuarterTurn`には入れられない。方眼Excelはベクターの頁を持てないので、`preview`（同じ図のPNG/JPEGのbytes。画素数の縦横比が頁の縦横比と各軸±0.5pixelで合うこと）を同じ位置に画像として置く。`preview`がなければ枠線だけを置き、`fallbacks`に`pdf_figure_frame`として記録する（`strict=True`では`XlsxStrictError`）。低水準の描画命令は`VectorPage(x, y, width, height, data, page=0, *, preview=None, tag=None)`で、頁の表示範囲をその箱へ引き伸ばす。

## 改ページ・位置指定・用紙混在

`PageSection(profile, *blocks)`の範囲だけ用紙を切り替え、退出時は親の用紙へ新ページで戻る。ネストも同じ規則。profile・利用幅に応じて部品を再計測し、文字サイズを維持する。参照A4/A3とderived_profileは共通のグリッドピッチを使い、独自のPageProfileでは指定したgridを使う。空セクションは進行中のページを分断しない。

`At(row, col, col_span, block)`は現在ページのグリッド原点から位置を指定する。現在のフローカーソルより前へ戻れず、本文外にも置けない。成功すると部品の終端行まで縦帯全体を予約する。同じ行へ複数のAtを置く代わりにColumnsを使う。Atは自動改ページしない。

見出しが連続した場合は連鎖全体と次の本文を同居させる。途中のSpacerは高さに含めるが、本文の代わりにしない。次の可視部品より先に明示改ページ・用紙境界・At・文書末尾に達するkeep_with_nextはエラーになる。

`PageDecoration(text, rows=1, gap_rows=1, align='left', style=None)`でヘッダー・フッターを指定する。本文の上下の予約枠に、全ページ確定後に描く。既定は本文書体の9pt。`{page}`と`{pages}`、`{page:03d}`などの整数書式を使える（方眼Excelでは書式付きの指定はエラー）。枠が紙外に出る場合や文字が入り切らない場合は、本文を再配置せずエラーにする。

## 方眼Excel

`render_xlsx(reports, path, fonts=None, *, strict=False, cell_padding_pt=None) -> XlsxResult`は、組み終えたScenePage列をPDFの代わりに方眼Excel（`.xlsx`）として書く（FR-021）。`reports`は`(シート名, ScenePage列)`の並び。`Document.render_xlsx(path, sheet_name, *, strict=False)`は`layout()`の結果を1帳票として書く。目的はセル上で値と文言を直せることで、Excelの数式による再計算はしない。製品の依存は増えない（標準ライブラリで書く）。

```python
from gridlayoutpdf import Document, Paragraph, XlsxStrictError, render_xlsx

pages = Document(Paragraph("計算書")).layout()
result = render_xlsx([("計算書", pages)], "report.xlsx", strict=True)
print([sheet.name for sheet in result.sheets], result.numbers_as_text)
```

- ページのグリッドの1マスを1セルにする。用紙・向き・グリッド、またはヘッダー・フッターの位置・雛形が変わる所で次のシート（`名前`、`名前_2`…）にし、ページの境目に改ページを入れる。シート名がExcelの規則（31文字、`[]:*?/\`不可、重複不可）に反する時、用紙がA4・A3以外の時、Excelの上限（16,384列・1,048,576行）を超える時は`XlsxError`。
- 行高・列幅は、Excelの印刷で累積の位置がPDFのグリッドに合うよう、セルごとに整数pxで選ぶ。100%で印刷できない時は`print_scale`として記録する。
- 文字片ごとに1セル（またがる範囲は結合）。文字片の列は字形のインクが触れる列。重なれば右（回転表では読む方向）へずらして`shifts`に記録し、グリッドの右端を越える時は常に`XlsxError`。添字・指数は記号と同じセルのリッチテキスト。
- 数値の書き方に丸ごと一致する文字片（`−2.000`、`1,234.5`など）は、Excelの画面で`###`にならずに範囲へ入る時だけ数値型＋PDFと同じ表示の表示形式にする。先頭0の番号・`−0.000`・図の中の文字は文字列。入らない数値は文字列のまま`numbers_as_text`に記録する。文字列のセルも、Excelで要る幅まで空いたセルへ広げ、足りなければ`texts_clipped`に記録する（Excelの印刷で末尾の字が切れうる）。字が1つだけの表のセルはセルの範囲全体を結合して寄せ方を写す。
- 分数は分子・分母を上下のセル、分数線は行の境目の図形。同じ式の左辺・等号・結果・単位は別々のセルで、式の行の範囲を縦結合して上下中央にする。
- セルの罫線になるのは`Table`・`Rule`・`SideRule`が描いた線だけ。利用者の`Line`（図の中を含む）・分数線・根号・図は、セルの境目に載っていても図形。図はグループ化した図形・テキストボックス・画像になる。
- `QuarterTurn`は`local_grid`がページのグリッドの縦横入替の時にセル（文字の向き90度）で、それ以外は図形にして`fallbacks`に記録する。
- `PageDecoration`はExcelのヘッダー・フッター（`align`の欄）。`{page}`は`&P`と各シートの先頭ページ番号、`{pages}`は渡した帳票の総数。
- `XlsxResult`は`path`、`sheets`（`XlsxSheet`：名前・帳票・ページ範囲・行列数・印刷の拡大率）、`shifts`（`XlsxShift`：理由は`overlap`・`fraction`・`fraction_in_script`）、`fallbacks`（`XlsxFallback`：種類は`pdf_figure_frame`・`quarter_turn`・`border_off_grid`・`border_in_merge`・`border_conflict`・`rotated_text`・`fraction_in_script`・`term_off_grid`・`cell_padding_mismatch`・`print_scale`）、`numbers_as_text`、`texts_clipped`、`untagged`（意味のタグのない描画命令の型と数）、`dropped`（大きさのない図形）を持つ。
- `strict=True`では`shifts`か`fallbacks`が1件でもあれば`XlsxStrictError`（`XlsxError`の一種）にし、何も書かない。`numbers_as_text`・`texts_clipped`・`untagged`は対象外。
- `cell_padding_pt`はExcelのセルの片側の内側の余白（文字の大きさ→pt）。省略時は`term_columns='grid'`と同じ`excel_cell_padding_pt`。
- 書体はPDFと同じ書体名を書く。開くパソコンにその書体がないとExcelは別の書体で表示する（同梱のIPAex書体はPDF用で、Excelでは使えるようにならない）。両端揃えの字間（`tracking`）と`Text.shear_x`はセルでは表せないため捨てる。
- ちょうど列に収まる数値は、印刷では表示されるが、画面（100%）では5列以上の範囲で`###`になることがある（Excel 16.0、ＭＳ 明朝 10 pt で実測）。
- 例: `examples/representative_report.py --term-columns grid --xlsx --strict`。

## 診断・部品拡張

`Document.layout()`は確定したScenePage列を返す。`Document.render()`は全ページの配置成功後に一時ファイルへPDFを作り、最後に出力先を置き換える。空文書をrenderした場合や計測・描画が失敗した場合、既存の出力を成功扱いで上書きしない。

`LayoutOverflowError`にはblock_id、needed、availableがある。幅はpt、文書の高さ予約は行数としてメッセージに単位を示す。識別しやすい`block_id`を部品へ付けると、長い帳票の問題箇所を追いやすい。

`render(..., debug_grid=True)`でグリッドを表示できる。`render(..., invariant=True)`（`render_pdf`も同じ）は作成日時と文書IDを書き込まず、同じページから同じbytesのPDFを作る。既定値`False`ではReportLabの日時付きメタデータを保つ。`layout_trace(pages, fonts=None)`は用紙・配置・ローカルアンカー・描画境界をJSON保存可能なdictへ変換する。画像bytesは含めない。ローカルの基線やアンカーは、配置元のx/yと合わせて解釈する。

独自部品は`measure(context, available_width) -> MeasuredBlock`を実装する。計測中にPDF Canvasを触らず、左上原点の相対描画命令をLayoutPartへ入れる。`LayoutPart(rows, commands, metadata, *, opening=(), continuing=(), joining=(), closing=())`の4つの命令列は、置かれた断片の中の位置で描くかが決まる：`opening`はそのpartが断片の先頭のとき（改ページで切れた断片は頁の先頭に置かれるので、2つ目以降のpartでは頁の先頭のときだけ）、`continuing`はそれ以外（前のpartがすぐ上にあるとき）、`closing`は断片の最後のとき、`joining`は同じ部品の次のpartがすぐ下に続くとき。`joining`は次のpartの中まで、`continuing`は前のpartの中まで描いてよい（越えれば`LayoutOverflowError`。繰り返すprefixの前後は、分割後に並び得るpartのうち最も低いもので測る）。表は境目を1本の線にするためにこれを使う。部品を包んでpartを作り直す容器は、4つの命令列も一緒に移す（`Indent`と同じ）。Textのyだけは基線。外側の高さは整数行にし、分割可能な境界ごとにpartを分ける。`measure_block`で型・幅・ピッチ・描画境界を共通検証できる。詳しい責務は[アーキテクチャ](architecture.md)を参照。

`Text(x, y, text, style, quarter_turns=0, shear_x=0.0)`は基線原点の周りで文字を90度ずつ反時計回りに回転する。`quarter_turns`は0〜3の整数で、1は紙面上で下から上へ進む文字、2は180度、3は時計回り90度。boolは受け付けない。平行移動しても向きは変わらない。`command_bounds`は変換した実字形の境界を返す。診断JSONは回転文字に`quarter_turns`と`direction`を追加し、既定の水平文字の形式は維持する。

`shear_x`は有限の実数で、正値は文字の上端を右へ傾ける。基線原点を基準に、上原点の局所座標で`x'=x-shear_x*y`を適用してから回転する。例えば`.342`は原本の人工斜体を再現する指定で、字送りとtrackingは変えない。描画は埋込みフォントのPDF文字行列を使い、文字を画像や輪郭へ変換しない。`command_bounds`は傾斜後の四隅を含むため、セル端などで広がった字形が収まらなければ通常どおりエラーになる。0以外の値は診断JSONにも記録する。既定0では従来の文字表示と診断形式を維持する。

初期版は横書きの日本語・欧文と構造化数式を対象とする。完全なUnicode行分割、複雑文字のshaping、TeX解析、任意の大型演算子や行列、GUIデザイナー、外部PDFの取り込みは含まない。
