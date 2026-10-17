# 片持ち梁照査 p1–37：既存コードと検証の調査

2026-10-17。`/plan` のコード調査担当による読み取り調査。製品・テストの実装は行っていない。原本全37頁の内容調査は別担当の結果と合わせる。本書のファイル配置は提案であり、成果物の存在を意味しない。

## 現状と既存合意

- `CONTEXT.md:7` の「固定ページ再現」を今回適用する。ユーザーの最新回答により原本1頁→出力1頁の37頁固定となり、内容を別頁へ送ることは再現失敗とする。同`:31` の一般的な「体裁統一」と区別する。同`:35` の「配置グリッド」は文字数と独立、同`:39` は文字サイズ保持を定義する。
- 全頁の右上ページ番号は出力しない。物理頁と原本に印刷された番号はmanifestに保持し、PDFの頁番号装飾は追加しない。37頁より増える場合を含む頁対応違反は、出力PDFの置換前にエラー停止する。
- `docs/architecture.md:3`、`src/gridlayoutpdf/equations.py:37` は数式表示と計算を分離する。式・数値の書式済み文字列を入力し、計算や丸めは行わない。
- `tests/fixtures/reference_manifest.json:143` の `report_13` が原本。SHA-256は `e56bf3ddbe3314ed95517099bedb0e68005df1567b0b3e8f52a2a4066d03393e`。既存目視範囲は同`:148` の p1/p54。既存の p54数式試作を今回の37頁の確認済み根拠に流用できない。
- `tests/unit/test_reference_integrity.py:77` は原本ハッシュ、同`:83` は12原本と生成先の分離、同`:101` は既存調査頁、同`:141` は6代表fixtureを検査する。6代表fixtureには37頁の全文対応表がない。
- rootからの実行報告：今回開始時の全件baselineは1269 passed、coverage表示99%、`.claude/logs/cantilever-p01-37-baseline.log`。これは既存テストの健全性であり、新しい37頁の再現成功ではない。

## 再利用できる公開APIと実例

| 責務 | 既存実装・根拠 | 今回の使い方 |
|---|---|---|
| 公開入口 | `src/gridlayoutpdf/__init__.py:28` | builderは `from gridlayoutpdf import ...` の公開exportsのみを使う。ReportLab Canvasやprivate関数へ依存しない。 |
| 文書・改ページ | `src/gridlayoutpdf/document.py:61`、`docs/api.md:163` | Document、Heading、Paragraph、Spacer、PageBreakを組み合わせる。大表もA4縦を保ち、回転は部品内部で行う。 |
| 数式・等号列 | `src/gridlayoutpdf/equations.py:16`、同`:37`、同`:75` | EquationGroupと整数列EquationAnchors。relation/result_relationも指定でき、不等号・全角等号も表示可能。 |
| 分数・上下付き・根号 | `src/gridlayoutpdf/math.py:147`、同`:181`、同`:228`、同`:264` | Fraction、Script、Root、Delimitedを組む。`MathBlock`で表セルへ入れる。 |
| 変数説明 | `examples/representative_report.py:150`、`docs/api.md:70` | Columns(MathBlock, Paragraph)をStackで縦積み。大きいStackを一括Columns/KeepTogetherに入れない。 |
| 結合表 | `src/gridlayoutpdf/tables.py:23`、同`:63`、`examples/representative_report.py:41` | Table列幅を整数グリッド列、Cellのrowspan/colspan、numeric_columns、header_rowsで表現。 |
| 図 | `src/gridlayoutpdf/figures.py:109`、同`:160`、`examples/representative_report.py:20` | 実際に図がある場合だけFigure/Imageを使う。文字・式・表を画像化しない。 |
| 通常/grid出力 | `examples/representative_report.py:193` | 一度のlayout結果をrender_pdfで通常/gridに描き、layout_traceと全頁previewを出す。 |
| 対応追跡 | `src/gridlayoutpdf/document.py:265` | placementにblock_id/source_path/partsが残るため `p01-...` 等の安定IDで入力→生成頁の対応を導出可能。 |

`pyproject.toml:10` はPython>=3.12、同`:11` はReportLab/Pillow、同`:16` はPyMuPDF/pytest/pytest-cov。今回の原稿・検証のために新依存は不要の見込み。固定書体・10pt本文・添字0.65・グリッド値は `docs/validation.md` と既存font manifestを参照し、再定義しない。

## 公開APIの不足を判断する順序

当初は既存APIのみを第一候補としたが、ユーザーが大表を「原本まま」と回答したため、A4縦紙面内の90度回転を保持する製品拡張が必要と判明した。下記の数式・表内容の限界確認に加え、末尾の回転追加調査を適用する。

1. `src/gridlayoutpdf/equations.py:419` の折り返しは最上位Rowだけ。分数・根号・添字・Delimited・入れ子Rowは原子的。乗除算は `tests/unit/test_equation_wrap.py:201` の通り明示BreakHintが必要。長い式を一つのLiteralに埋めると意味上の折り返し候補を失う。
2. 結果列幅を除いた幅に入らない右辺は結果を最終専用行に送れる（`src/gridlayoutpdf/equations.py:191`、`docs/api.md:111`）。式・単位が長ければアンカーとグループ分割を調整し、文字を縮小しない。
3. Table列幅の合計を超えるとエラー（`src/gridlayoutpdf/tables.py:153`）。Cell内の数式は直接MathNodeではなくMathBlock（同`:194`）。rowspanはheader/bodyをまたげず（同`:139`）、連結した行群は分割不可（同`:220`）。巨大な1セル/行群は空ページでも収まらず停止する。
4. Rootは平方根のみ（`src/gridlayoutpdf/math.py:228`）。Delimitedは丸括弧・角括弧・縦棒・省略のみ（同`:271`）。背の高い波括弧やn乗根が実際の対象頁に見つかった場合に限り最小の不足表現を切り出す。添字付き記号を表示できることと、大型演算子用組版APIがあることを混同しない。
5. PDF調査担当の2026-10-17全37頁目視完了報告では、p30–37はA4縦用紙内の90度回転大表。p30–31 Md内訳、p32–33 Vd内訳、p34–35 Mt内訳、p36–37集計で、Case1–18/19–31、内訳14列・集計16列程度。結合ヘッダー、セルの係数+値の2段、dittoの〃、空欄/0/－の区別を保持する必要がある。ユーザーは用紙/分割方針について **「原本まま」** と回答した。A3横正規化は採用せず、A4縦紙面の中で表だけ90度回転し、ヘッダーは原本の向きを保つ。右上ページ番号は最新回答により全頁で省略する。

同担当の全頁確認ではn乗根、背の高い波括弧、行列、積分、上下限付きΣ、段分数は対象範囲に見つかっていない。p9のΣX_i²、p13/15のρ_m/α_f、p16–20のμ・R_m、slashの1/2と長い展開式、∴H_sdは既存Literal/Script/Row/EquationGroupで扱える見込み。ここから数式新APIを先に追加する根拠はない。PDF観察の詳細は別のPDF調査文書を正本とする。

## 既存検証と今回追加すべき検証

| 既存証拠 | 今回への再利用 | 不足する範囲 |
|---|---|---|
| `tests/integration/test_representative_report.py:75` | PyMuPDF rawdictの等号中心、結果右端、本文size、語の保存、描画線を確認 | 37頁の全文章・全値・全式・表のセル対応は未検査 |
| `tests/integration/test_equation_layout.py:29` | 手指定座標とPDFの文字origin/sizeを独立比較。項順・回数・継続行・添字も確認 | 原本別式の項順・演算子・添字・分母分子対応の手確認oracleが必要 |
| `tests/integration/test_table_pdf.py:24` | PDF文字と罫線位置、数値右端、ヘッダー再掲を検査 | 回転大表でもケース×項目の全値を同じセル関係で照合する必要 |
| `tests/integration/test_table_pdf.py:47` | traceのsource_rows/セルframeを使い、分割した行の網羅を確認 | traceのみを正解にせず、PDF抽出のセル/行単位照合と組み合わせる |
| `tests/integration/test_representative_report.py:131` | 通常/gridの内容一致、同一頁数、preview枚数を検査 | 生成37頁と37原本頁の各内容を1対1で照合。頁数だけ一致していても、内容が隣頁へ流れれば失敗 |
| `tests/visual/test_representative_golden.py:34` | フォント・入力素材・ツール版・全PNG/全画素hashを固定 | 新しい通常37頁の独立したbaselineが必要。既存5頁baselineは保持 |
| `tests/visual/README.md:27` | 通常/gridの全頁目視後だけbaseline登録 | 37原本頁と通常/grid各37頁の目視記録、確認対象hash、未判読の記録が必要 |

推奨する検証の粒度：

- 原頁1–37の集合、固有block ID、原稿の順序、部品種別、表の行列/結合の網羅をfixture単体で確認する。p38以降の混入も防ぐ。
- 表示値は末尾ゼロ・符号・小数点・単位・原本の `#######` などを含む文字列。原本に見える欠損表示を計算で復元しない。原本の意図を推測した修正は別に扱う。
- oracleはPDFから目視して確認した別原稿として保持し、builderが読む同じデータをそのままexpectedへ変換して自己一致させない。原本raw extractionは調査証拠として保存できるが、分数/添字/回転表の意味的oracleには単独で使わない。
- 内容確認は単なる全文substring集合を避ける。同じ数値の反復が多いため、入力block/式/表のケース行・項目列にひもづけた順序と出現回数を原頁に対応する1出力頁内で検査する。固定頁の外へ本文や表が流れた場合は不合格。原本にある反復見出しだけを許可重複として明示する。
- 式はトークン列だけでなく上下付きのsize/基線差、分数の上下関係/罫線、等号/結果/単位の座標をPDFから検査する。traceは生成箇所の特定に使い、抽出文字・位置で独立に裏づける。
- 少なくとも代表的な欠落、重複、符号/値置換がoracle検査で失敗することを確かめる。別機能として汎用ミューテーション基盤を作る必要はない。
- 最終ゲートは新規対象テスト、全件pytest/coverage>=90%、既存原本hash/画像基準維持、全生成頁の通常/grid目視。開発依存や製品APIを変えない場合、既存の全wheel互換性工程まで無条件に再実装する必要はない。

## 推奨する具体的な変更先

新規（計画段階の提案）：

- `tests/fixtures/cantilever_p01_37/README.md`：対象と非対象、原頁/生成頁対応、原稿の作り方、再実行、oracleの独立性。
- `tests/fixtures/cantilever_p01_37/manifest.json`：原本hash、物理頁1–37と印刷頁、部品ID/種別/fixtureへの対応、確認記録。既存reference_manifestのp1/p54調査履歴は変更せず参照する。
- `tests/fixtures/cantilever_p01_37/pages/p01.json` ～ `p37.json`：表示値と構造化部品原稿。共通化する場合も37頁それぞれに具体的な内容対応を保持する。JSONは試験専用で、製品の入力形式を追加しない。
- `tests/fixtures/cantilever_p01_37/expected/p01.json` ～ `p37.json`：原本から別確認した文章/式トークン/表行列と出現回数・構造のoracle。上記pagesを自動コピーしてexpectedにする運用は禁止。
- `tests/fixtures/cantilever_p01_37/builder.py`：試験専用の薄い公開API組立器。式/セルの反復構造を共通化する。原本の座標からText/Lineを全頁生成する抜け道にはしない。
- `tests/fixtures/cantilever_p01_37/render.py`：上記builderを使用する再実行入口。通常/grid/PDF/trace/対応JSON/previewを専用生成先へ出す。
- `tests/unit/test_cantilever_fixture.py`：37頁範囲、ID、文字列、fixture構造、セル網羅、oracle対応。
- `tests/integration/test_cantilever_p01_37.py`：公開API生成、PDFから独立した全内容検査、式/表構造・サイズ・改ページ・生成頁対応。
- `tests/visual/test_cantilever_p01_37_golden.py`、`tests/visual/cantilever_p01_37/manifest.json`、同ディレクトリの通常37頁PNG：目視完了後だけ作る画像回帰。
- 生成物：`build/reports/cantilever-p01-37/`。原本のcropは調査資料として必要なら同生成領域へ保存し、再現PDFの文字/式/表を画像として置かない。

文書の基本変更範囲：`docs/validation.md` と `tests/visual/README.md` に今回の手順と受入根拠を追加する。`pyproject.toml`、`uv.lock`、既存代表fixtureと原本PDFは変更を前提にしない。追加の製品変更候補は下記の回転調査を参照する。回転以外の製品拡張は最小失敗実証がある場合だけ追加する。

## ユーザー確認の扱い

コードから解決できる不明点は上記の最小実証で解決する。「全文37入力頁」「ソルバーなし」「原本保存」、大表の「原本まま」、最新回答の「37頁の1対1固定ページ再現・増頁はエラー停止・右上ページ番号は全頁不要」は確定。回転と表密度の実装方式はコード/原本の測定で解決する技術事項であり、ユーザーへ新たな一般論の質問を増やさない。

## 追加調査：A4紙面内の回転表を保持する最小拡張

### 不足が確認できる根拠

- `src/gridlayoutpdf/scene.py:39` のTextはx/y/text/styleだけで向きを保持しない。同`:155` のCommand unionと同`:199` のScenePage受入型はText/Line/Polyline/Rectangle/RasterImageの5種類。
- `src/gridlayoutpdf/renderers/reportlab.py:39` はTextを固定水平のbeginTextで描く。線の端点だけ回転しても文字の向きは変わらない。
- `src/gridlayoutpdf/bounds.py:16` は無回転のフォント実字形矩形に基線座標を足す。rendererだけ回転すると、layout/preflightが別の境界を検査する不整合になる。
- `src/gridlayoutpdf/diagnostics.py:34` は水平基線のみを記録する。回転後の文字方向・局所表座標とページ座標の対応を追える拡張が必要。
- ページ全体を回転させると通常のヘッダーも回転するため今回の要件と合わない。原本ページや表を画像として貼る方法も要件を満たさない。右上ページ番号は描画対象から除外する。

### 推奨候補と変更パス

最小候補は、既存Textに既定0の90度単位の向きを追加し、表を含む子部品を外側のグリッド枠内で剛体回転する公開部品を追加する方式。名称・引数・正負方向・局所グリッド規則はCodex相談で確定する。任意角度、せん断、拡大縮小を同時に追加しない。

| ファイル | 必要な変更/既存参照 |
|---|---|
| `src/gridlayoutpdf/scene.py` | Textの向きと入力検証、translatedで向き保持。既存Textの位置引数4個と既定挙動を維持（`:39`、`:54`）。 |
| `src/gridlayoutpdf/bounds.py` | フォント実字形矩形4隅を基線まわりに剛体変換し、そのAABBを返す（`:8`）。字幅だけで境界を代用しない。 |
| `src/gridlayoutpdf/renderers/reportlab.py` | Textの基線と方向をPDFのtext matrixへ変換（`:31`）。save/restoreState、100%横倍率、tracking、size、欠字preflight、原子的出力を維持。 |
| `src/gridlayoutpdf/rotation.py`（新規候補） | 子を局所座標で計測し、回転後の枠へText/線/Polyline/Rectangleを変換する部品。容器既存パターンは `containers.py:34` の子診断、`:49` の子trace、`:81` の不変計測を再利用。既存containersへ追加する選択も可能だが所有分離のため新モジュールを候補とする。 |
| `src/gridlayoutpdf/diagnostics.py` | Textの方向、回転部品の局所→ページ変換と子metadataを記録（`:26`）。無回転の既存trace互換性を考慮する。 |
| `src/gridlayoutpdf/__init__.py` | 新部品の公開export（`:28`）。 |
| `docs/api.md` / `docs/architecture.md` | 回転方向、枠予約、分割可否、局所座標/グリッド、対応する子種別を記載する。 |

この方式ならCommand型の追加が不要で、`layout.py:111` の型whitelistや `_has_visible_commands` (`:19`) は原則そのまま使える。MathBoxやFigureの型whitelistも変更不要の見込み。今回の回転表に画像は必要ないため、回転容器内のRasterImageは初期対応外として明示拒否する案が最小。黙って画像だけ無回転にしない。

比較候補は再帰的なTransformGroup scene命令。全コマンドに同じ変換を適用できる利点がある一方、`layout.py:19` の可視判定、`:111` の型検証、sceneの型/不変化、bounds/diagnosticsの再帰、rendererの再帰描画と画像preflight (`renderers/reportlab.py:91`) まで広がる。今回の表だけのために一般変換ツリーを導入する必要があるかは慎重に比較する。

### 密度を回転と同時に実証する

標準A4本文枠は `profiles.py:60` の30列×47行、482.4×727.56pt。90度回転後の子枠は概ね727.56×482.4ptになる。`tables.py:194` は文字列セルをParagraphへ変換するため、係数+値の2行は標準pitchでは最低2行。18ケースだけで36×15.48=557.28ptとなり、見出しや余白を含める前に回転後高さを超える可能性が高い。

したがって、小さい回転表が描けるだけでは工程を通過させない。原本の表文字size、2段セルの行間、行高を測定し、原本に対応する明示styleと局所計測設定で最大18ケース表が収まることを先に確認する。文字の自動縮小・ケース削除・A3化は選択しない。局所グリッドのx/yを回転に合わせて入れ替えるか、表内部だけ補助ピッチを持つかも、既存の外枠グリッドと一貫する契約として確定する必要がある。

PDF担当の測定結果：表はline.dir=(0,-1)。主要文字size9.959pt、添字6.659pt、LR+Bセル一部9.8pt、「安全性」9.058pt、「(地震時以外)」8.056pt。内訳表body行高21.60pt、係数→値の基線差10.80pt。p30–35は回転前幅683.40pt、header33.36pt、18ケース全高422.16pt/13ケース314.16pt。p36–37は幅712.44pt、header60.48pt、18ケース全高449.28pt/13ケース341.28pt。標準ピッチのままでは収まらないが、原本と同等の文字サイズ・10.8pt程度の局所行間ならA4回転枠に収まる可能性がある。確定した測定の正本はPDF調査文書。

### 独立した検証の具体案

- `tests/unit/test_scene.py`：向きの入力検証、不変性、translated、既定0の完全互換。
- `tests/unit/test_bounds.py`：非対称の実字形張り出しを持つ文字を±90/180度回した4隅の手計算矩形。線/矩形のstroke境界、回転後枠外を検出。
- `tests/unit/test_rotation.py`（新規候補）：外枠の整数グリッド行/列、局所計測幅と高さ、子の文字順/サイズ、部分変換/二重変換がないこと、巨大表の明示エラー、子metadata・空白内容・既存入力の不変性。未対応の画像等を明示拒否。
- `tests/integration/test_pdf_renderer.py`：PyMuPDF rawdictのline.dirとchar.origin/bboxから文字方向と基線を独立確認。sizeと文字内容を保持し、後続の無回転文字へ状態が漏れない。既存ファイルがある状態の回転境界失敗は出力を保持。
- `tests/unit/test_diagnostics.py`：回転方向と局所→ページ変換をJSONに保持し、再計測せず実描画境界と一致する。
- `tests/integration/test_cantilever_p01_37.py`：全37頁のMediaBox=(595,842)、PDF page.rotation=0、原頁→出力頁の内容1対1、右上頁番号なしを確認。最大大表と全8表頁のline.dirが原本方向、ヘッダーも原本の方向。数字/係数/〃/空欄/0/－をケース×項目で照合し、表のセルはベクター罫線+抽出可能なText、画像化されていないことを確認。通常/gridの内容と座標は同じ。
- 通常/grid全頁目視と新規全頁goldenに加え、既存5頁goldenが不変であることを最終全件ゲートで確認する。製品変更を伴うため、公開APIを使う小さな回転例をwheel外部実行で確認する範囲も計画へ加える。

### 固定ページ保証の最小候補

単一Documentの中で原頁ごとの `KeepTogether(Stack(*components), block_id="pNN")` を `PageBreak()` で区切る案が既存公開契約で成立する。Stack単独は `document.py:114` で展開されるためKeepTogetherが必要。同`:124` では容器ごと計測し、`containers.py:174` が分割禁止、`layout.py:201`/`:212` が全高を最小fragmentにし、`document.py:263` が空頁にも収まらない場合LayoutOverflowErrorを返す。既存 `tests/unit/test_document.py:247`/`:252` にStack展開とKeepTogether(Stack)の過大高失敗の根拠がある。
各Stackには計測可能部品だけを入れ、PageBreak/At/PageSection等のフロー指示は内包しない。`Document.layout()` 後に全37頁と各pNN→対応出力頁の1対1をguardし、成立後だけrender_pdfへ渡す。単一DocumentなのでScenePageのpage_numberも連番を保つ。一般Documentの自動フローは変更しない。
負例では意図的に1原頁の原稿量を増やし、layoutまたはguardの明示失敗と既存通常/grid PDFのバイト保持を検査する。右上ページ番号装飾は無指定、原本印刷番号はmanifestのみで保持する。
