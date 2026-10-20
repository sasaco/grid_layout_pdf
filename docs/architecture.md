# アーキテクチャ

GridLayoutPdfは、計算値を表示部品へ渡すところからPDF出力までを扱う。構造計算・入力値の評価・数値の丸めは利用アプリの責務とする。

## 処理の境界

```mermaid
flowchart LR
    A[Pythonの部品ツリー] --> B[書体を解決して計測]
    B --> C[グリッドと等号列へ配置]
    C --> D[行境界で改ページ]
    D --> E[不変のScenePage列]
    E --> F[ReportLabでPDF描画]
    E --> G[配置トレース]
```

部品の位置は左上原点のptで表す。グリッドは外側の位置・幅・占有行数を決め、文字の送りや数式内部の寸法は書体から計測する。PDFの左下原点へ変換する処理は描画器に集約する。

## モジュール

| モジュール | 責務 |
|---|---|
| geometry / profiles | 有限な幾何、グリッド境界、実測／生成した用紙、本文行範囲 |
| styles / fonts / fontfinder | 文字設定、書体名から同梱・Windowsの書体ファイルを引く解決、NFC、欠字検査、送り幅と実字形境界 |
| scene / bounds | 不変の描画命令とページ、線幅・実字形を含む共通境界 |
| semantics | 描画命令の意味のタグ（役割・構造の列・データ）。描画と等価比較には関わらない |
| math | 分数・根号・添字・括弧等の局所計測。MathBoxは基線と数式軸を保持 |
| text / blocks | 行組、基本禁則、上限付き字間、段落・見出し・空白 |
| equations | 意味上の折り返し、等号・結果・単位の共有アンカー、MathBlock |
| layout | 共通計測結果、分割、prefix再掲、部品内境界検証 |
| containers | 縦積み・横並び・分割禁止・明示位置の指示 |
| rotation | 局所グリッドで子を計測し、90度回転した既存primitiveと変換metadataへ確定 |
| tables | セル配置と結合検証、整数行高、分割禁止行群、ヘッダー |
| cell_content | 明示した文字／数式行のpt配置・余白・最低高を一度だけ整数行へ丸める |
| figures | 図枠・矢印・ラベル、画像の読込みと内容固定 |
| document | ページフロー、見出し連鎖、用紙切替、ページ装飾 |
| diagnostics | 確定したページの配置・文字・実境界をJSONへ変換 |
| renderers/reportlab | 全ページの事前検査、描画状態の分離、PDF座標変換、一時ファイル出力 |

## 計測と分割

通常部品は`measure(LayoutContext, available_width)`でMeasuredBlockを返す。LayoutContextは書体・用紙・ReportStyleを渡し、基線を整数行だけ下げる共通処理を持つ。

LayoutPartは分割しない縦方向の単位で、正の占有行数・相対描画命令・不変metadataを持つ。段落では表示1行、数式では折り返し後の1行、表ではrowspanで接続した行群、図では全体が1partになる。

MeasuredBlockはprefixと本文partsを持つ。splitは本文の合法な境界だけで分け、prefixを両側へ再掲する。段落のmin_first/min_lastは表示part数を数え、物理グリッド行数やprefixを数えない。分割結果はどちらも本文を1part以上含み、再分割でも制約を保持する。

Stackは通常フローで子へ展開する。ColumnsやKeepTogetherの中で計測すると全体が原子的になる。原子的な容器でも子の位置とローカルmetadataを残し、等号アンカーをトレースできる。

CellLinesは複数のMathBoxを明示したpt基線へ配置し、内側余白・最低高を含めて最後に一度だけ行数へ丸める。通常Blockの予約契約は変えず、Tableは子の予約高と解決済みInsetsを受け取って必要行数を決める。外側paddingを追加すると再度の行丸めが起こり得るため、その内訳とrowspanの配分を確定metadataに残す。明示row_heightsは自動配分せず、収容を検証する。

Tableの既定モードは従来の行群ごとのpartsと反復headerを保持する。split=Falseの場合だけ全行を一つのpartへ組む。罫線は辺ごとのBorderStyle（FR-022・FR-026）で、行群の境目は上のpartの`joining`（境目を中心に1本、縦線は境目で止める）・`closing`（頁の下端で自分の中に1本）と下のpartの`opening`（頁の先頭で自分の中に1本）・`continuing`（縦線の始まりの半ストロークを境目まで補う）に分けて持つ。MeasuredBlockはpartを置いた断片の中の位置でこの4つから選んで描き、Documentは改ページで切れた断片を必ず頁の先頭に置くので、2つ目以降のpartの`opening`は頁の先頭でだけ描かれる。描画器が線を除去する仕組みは加えず、セルID・元行列・明示行高・辺ごとの罫線の種類を計測時に確定する。

QuarterTurnは原点0の局所PageProfileで子を計測し、Text/Line/Polyline/Rectangleを剛体回転して一つのLayoutPartへ確定する。再帰的な変換sceneノードは増やさない。Textは0〜3のquarter_turnsと既定0のshear_xを持ち、共通boundsは基線周りの実字形四隅を傾斜してから回転し、描画器も同じ順のPDF文字行列で扱う。QuarterTurnは文字の傾斜を保持する。子metadataは局所座標のまま保存し、local_to_part行列と累積part位置を明示する。外側の高さだけ整数行へ丸め、内容や文字サイズは変えない。

## 数式の配置

MathBoxは送りと実字形を含む幅、ascent/descent、数式軸、相対命令を返す。分数・添字等はサイズから局所配置を決め、必要な数式全体の寸法を外側へ返す。外側の部品が基線と占有行数をグリッドへ合わせる。

EquationGroupはラベル・左辺・関係記号・結果・単位を先に計測してアンカーを確定し、残り幅で右辺を折り返す。ページ内の位置に応じてアンカーを変更する循環は作らない。同じprofile・幅での分割ではアンカーを保持し、profile・利用幅に応じて再計測する。

## 意味のタグ

方眼Excelへの対応付け（FR-021）のため、全描画命令はキーワード専用の任意の`tag`（`semantics.Tag`）を持つ。`compare=False`の欄なので、等価比較・hash・PDF描画には一切関わらない。タグは役割`role`、外側から順の構造の列`path`（`Scope`の並び）、命令自身の`data`からなる。部品は下から計測するので、親は子の命令へ自分の`Scope`を外側に足す（`within`）。ライブラリの構造の中に置かれたタグのない命令（利用者の命令）は`Role.OTHER`になる。

| 役割`Role` | 付ける部品 | `data` |
|---|---|---|
| text | Paragraph・Heading の行（表のセルの文字列とヘッダー・フッターもParagraphで組む） | — |
| math | Literal・Symbol・Operator・式の関係記号 | `atom` |
| fraction_bar / radical / delimiter | 分数線、根号、括弧・縦棒 | delimiter は`symbol` |
| table_border | Table の辺 | `orientation`・`boundary`・`first`・`stop`・`drawn`（opening/continuing/joining/closing）・`style`・`stroke` |
| rule / side_rule | Rule・SideRule | `style`・`stroke`（二重線は0が上・左） |
| figure / image | Figure の全命令（文字を含む）、Image | figure は部品ごとの`part`・`line`、image は`block_id` |

セルの罫線にしてよいのは`BORDER_ROLES`（table_border・rule・side_rule）だけで、図の中の利用者の`Line`や分数線は境目に載っていても図形として扱う。

| 構造`Kind` | `part`・`index`・`data` |
|---|---|
| stack / columns / row | `index`: 子・項目の番号（同じ配置の中の兄弟を区別する） |
| paragraph / cell_lines | `index`: 表示行、`data`: `align`（paragraphは`heading`も） |
| decoration | `part`: header・footer、`data`: `template`・`align` |
| table / table_cell | table は`block_id`、cell は`cell_id`・`row`・`col`・`rowspan`・`colspan`・`align`・`valign` |
| equation / equation_line / equation_part | 式の番号、表示行（`continuation`・`result_line`）、label・lhs・relation・rhs・term・result_relation・result・unit（term は`index`と`align`） |
| math_block | — |
| fraction / script / root / delimited | numerator・denominator・bar / base・superscript・subscript / sign・radicand / left・right・body |
| figure / figure_item | figure は`block_id`、item は`index`と`kind`（`raw`・`align`・`rounded`） |
| quarter_turn | `turns`・`local_grid`・`block_id` |

1つの構造は`Tag.key(kind)`（その`Scope`までの列から`part`を除いたもの）で識別し、同じ分数の分子・分母・分数線は同じkeyになる。Documentはページのmetadataの各配置へ`block_type`と、その配置・prefix・各partが描いたページの命令の範囲（`commands`・`prefix_commands`・`part_commands`、半開区間）を記録し、ヘッダー・フッターにも雛形・`align`・命令の範囲を残す。`layout_trace`はタグのある命令にだけ`tag`を出す。

## 書体・描画・失敗時の挙動

書体は`TextStyle.font`の書体名で指定する。`fontfinder`が書体ファイルのnameテーブル（英語・日本語のファミリー名とフルネーム）を標準ライブラリで読み、同梱のIPAex明朝・IPAexゴシック、`%WINDIR%\Fonts`、`%LOCALAPPDATA%\Microsoft\Windows\Fonts`の順に探す（Windows以外は同梱だけ）。import時やstyleの生成時には探さず、`FontRegistry.resolve`が初めて呼ばれたときに探して、名前ごとに結果を保つ。同梱の書体は`font_data/manifest.json`のSHA-256と照合する。

送り幅と実字形境界は別に保持する。特に斜体的な張り出しや下降文字を、文字列の送り幅だけで枠内と判定しない。グリフの存在を幅計測と独立に検査し、欠字を代替字形で黙って出力しない。

画像は計測時に静止PNG/JPEGを検証し、方向・色・透明度を正規化したbytesを描画命令へ保持する。描画時は元のファイルを読み直さない。

物理寸法Imageは描画幅高と予約幅高を分離する。指定pt値とEXIF補正後pixel寸法の比率を検査し、描画値を補正せず保持する。既存のグリッド枠fitとsnapshot処理を共用し、原本の出典・許可図台帳の責務は製品へ持ち込まない。

描画器は全ページと画像を検査してから同じ出力先ディレクトリの一時ファイルへ描き、保存完了後に置き換える。ページごとの用紙サイズ、フォント、文字送り、線属性を明示設定する。描画状態が前の部品・ページから漏れないようにする。

計測・改ページの幅不足は対象のpathと必要量を付けて診断する。空ページでも配置が進まない場合にエラーで停止し、無限に改ページしない。ページ装飾は予約枠へ後描画し、総ページ数の変化が本文の再配置を呼ばない設計とする。
