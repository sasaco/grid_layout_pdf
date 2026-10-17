# P7 report migration: GridLayoutPdf API investigation

調査日: 2026-10-17。計画slug: `pier-report-grid-migration`。読み取り調査であり、製品の変更・試作・pytest再実行はしていない。ライブラリの調査時HEADは `3da8b7cb71803c463029c68e155798f377c62e07`。以下のline番号は調査時の作業ツリーを指す。

## 結論

既存計算結果を表示文字列へ変換し、公開APIの文章・構造化数式・表・図から `Document` を組み立てる帳票層へ移行するのが最小構成となる。計算と数値丸めは利用側に残すというライブラリの契約と一致する（`docs/api.md:3`、`src/gridlayoutpdf/equations.py:37`）。公開例も計算済み表示値を外部から受け取る（`examples/representative_report.py:87`）。

一方、原本の厳密なページ割り・局所文字座標の復元は通常APIの自動フローと別の要求である。片持ち梁fixtureの固定37頁、原本MS明朝/MSゴシック、特殊な原本アンカーをP7移行へ無条件に持ち込まない。用語集は「固定ページ再現」と「体裁統一」を別に定義している（`CONTEXT.md:7`、`CONTEXT.md:31`）。今回の対象PDF・移植章・ページ割り・見本への忠実度をユーザー対話で確定する必要がある。

## 実装済み公開APIと適用先

公開exportの一覧は `src/gridlayoutpdf/__init__.py:30` にある。

| 帳票上の要素 | 使用候補と根拠 | 境界・注意点 |
|---|---|---|
| 本文・節見出し・注記 | `Paragraph`、`Heading`、`Spacer`。`docs/api.md:52`、`examples/representative_report.py:127` | Headingは次の可視本文と同居する。長文は日本語の基本禁則で自動折返し。 |
| 字体・文字サイズ・基線 | `TextStyle`、`ReportStyle`、`FontRegistry.register`。`src/gridlayoutpdf/styles.py:47`、同`:68`、`src/gridlayoutpdf/fonts.py:92` | 書体は利用アプリが明示供給。TrueType/TTCに対応、パッケージ同梱・OS自動探索なし（`docs/api.md:48`）。 |
| 記号式・分数・添字・根号 | `Row`、`Operator`、`Fraction`、`Script`、`Root`、`Delimited`、`MathBlock`。`docs/api.md:103`、同`:113` | TeXや `*`/`^` の文字列を解析しない。式の構造は帳票側で組み立てる。計算は行わない。 |
| 等号列、結果右端、単位列 | `Equation`＋`EquationGroup`＋`EquationAnchors`。`src/gridlayoutpdf/equations.py:16`、同`:37`、同`:75` | first_equal/second_equal/result_right/unit_startは整数グリッド列。1 Equationはlhs/rhs/result/unitであり「記号式＋代入式＋結果」専用モデルはない。複数Equationを同groupへ組む構成を先行実証する。 |
| 長い代入式 | `Operator`、`BreakHint`と最上位`Row`の構造的折返し。`docs/api.md:109` | 分数・根号・添字内を途中で切らない。結果を最終専用行へ送る場合がある。収容不能は縮小せずエラー。 |
| 条件表・結果表・荷重組合せ表 | `Table`、`Cell`、rowspan/colspan、numeric_columns、header_rows。`src/gridlayoutpdf/tables.py:35`、同`:74`、`docs/api.md:136` | 幅は整数グリッド列。結合で接続した行群は不可分。巨大な一セルの内部をページ分割しない。 |
| 罫線・明示行高 | `horizontal_rules`、`vertical_rules`、`row_heights`。`src/gridlayoutpdf/tables.py:98`、同`:103`、`docs/api.md:144` | 行高は局所グリッドの整数行。指定高さ不足は行の拡張や文字縮小をせずエラー。既定の分割表は独立行群の境界が二重に見える。 |
| 荷重図・断面図・模式図 | `Figure`、`Line`/`Polyline`/`Rectangle`、`Arrow`、`Label`。`docs/api.md:198`、`examples/representative_report.py:20` | 外枠はグリッド、図内部のみpt。図は全体不可分。既存図が動的なら図データからnative部品を構成できる。 |
| 画像 | `Image(path, col_span=..., rows=...)`。`src/gridlayoutpdf/figures.py:160`、`docs/api.md:215` | 静止PNG/JPEG、透明度/EXIF対応、計測時bytes固定。外部PDFページの埋込・合成APIではない。 |
| 横並び・変数説明 | `Columns`、`Stack`、`KeepTogether`。`docs/api.md:60`、同`:70` | Columns全体は不可分。巨大な横並びを自動で各列別ページに流すことはない。 |
| 改ページ・用紙混在 | `Document`、`PageBreak`、`PageSection`、`PageProfile`。`src/gridlayoutpdf/document.py:47`、同`:61`、`docs/api.md:221` | A4縦既定、A3横参照あり。セクション入退場で新ページ。用紙を自動拡大しない。 |
| 必要箇所の位置指定 | `At(row,col,col_span,block)`。`docs/api.md:225` | フローカーソルより前に戻れず、終端まで縦帯全体を予約。既存Canvasの任意絶対配置をそのまま置換するAPIではない。 |
| 回転した大表 | `QuarterTurn`＋局所GridSpec。`docs/api.md:176` | native文字・線・表を90度回転。画像には未対応。子全体は不可分。 |
| 表題・頁番号 | `PageDecoration`。`src/gridlayoutpdf/document.py:19` | textの可変フィールドはpage/pagesのみ（同`:39`）。Document全体のheader/footer設定。節ごとの動的表題はアプリの分冊構成と合わせて設計する。 |
| 診断と保存 | `layout_trace`、`debug_grid=True`、`LayoutOverflowError`、`Document.layout/render`。`docs/api.md:231` | PDF単体は全ページ配置後に一時ファイル→replace（`src/gridlayoutpdf/renderers/reportlab.py:127`）。PDF＋結果JSON一式の原子公開までは提供しない。既存アプリの保存トランザクションを維持する。 |

## 密な表のリスクと並行変更

`Cell.padding` の既定は3pt（`src/gridlayoutpdf/tables.py:42`）。子が既にグリッド行へ丸められた後で上下余白を加え、再び行数へ丸める（同`:223`）。標準15.48ptグリッドで子1行に上下6ptを足すとセル2行になる。この既定を密な原本表へ機械的に適用すると高さが大幅に増える。行数・必要pt高を先行実証で測る必要がある。

調査時の未コミット変更には下記APIが含まれる。文書に現れていることだけを、P7の既存環境へ導入済みという証拠にしない。

| 新しい選択肢 | コード・文書 | 利用価値 |
|---|---|---|
| `Insets` | `src/gridlayoutpdf/styles.py:21`、`docs/api.md:154` | 左右余白と上下余白を分け、必要高を抑える。 |
| `CellLines` | `src/gridlayoutpdf/cell_content.py:36`、`docs/api.md:170` | 明示行をptで配置し内側余白込みで一度だけ行へ丸める。密なセルはCell.padding=0＋inner_paddingが候補。 |
| `Table(split=False)` | `src/gridlayoutpdf/tables.py:89`、同`:99`、`docs/api.md:150` | 表を一partにして共有罫線を一本へ統合。ページをまたぐ長表には使わない。 |
| `Image(width_pt,height_pt)` | `docs/api.md:217`、`src/gridlayoutpdf/figures.py:160` | 必要な物理寸法を明示できる。既存fitと違い、比率不一致や容量不足を拒否。 |
| Scriptのscale/rise/drop | `src/gridlayoutpdf/math.py:208`、`docs/api.md:115` | 通常の添字サイズと基線調整を明示できる。原本固有のxアンカー全般の置換ではない。 |

実行記録は全1925件・coverage98.82%・wheel/全74目視合格を報告しているが、同じ時点のStep8は独立レビュー中である（`.agents/docs/plans/cantilever-p01-37-improvements-execution.md:26`、同`:56`、同`:67`）。これは今回の調査者が実行した検証ではない。計画実装開始時に合流・最終受入・実際にインストールされた成果物を再確認し、必要APIを備えた固定版を選ぶ。

## fixtureをそのまま取り込まない理由

代表公開例 `examples/representative_report.py` は、計算済み表示値・公開部品・Documentという利用例として再利用しやすい（同`:87`、同`:193`）。

一方、片持ち梁の `tests/fixtures/cantilever_p01_37/appearance.py` は原本の意味部品・行アンカーを復元する専用コードである。`SourceTableInkFonts`はfixture限定の実ink計測（`:27`）、`SourceScript`は原本固有のx/y位置（`:165`）、`SourceCell`は原本行アンカー（`:194`）、`PageFrame`は一頁枠（`:607`）を持つ。公開 `CellLines`への移行後もこれらは残る。通常のP7帳票層でfixtureをimportすると、製品wheelに含まれないテストコード・元原稿・原本座標へ依存する。

今回の推奨は公開部品を使い、共通化が本当に不足する要素だけ別途最小拡張として切り出すこと。原本忠実再現がユーザー要求となった場合には専用の局所プロフィール／意味アンカー層の必要性を再評価する。既存37頁fixtureのページ数、原本数値、許容誤差をP7の受入期待値には使わない。

## 最小の統合構成案

以下は提案であり、ユーザー合意済み設計ではない。

1. 計算結果・入力モデルから、既存の桁数・符号・単位・欠値を保持した帳票用表示値を作る。帳票が計算を再実行しない。数式の記号構造と代入値は同じ既存結果フィールドに対応付ける。
2. P7側に書式・フォント登録・文書生成の薄い共通層を置く。使用するGridLayoutPdf APIは公開exportに限定する。章単位のbuilderは数式AST、表行、図データを返す。
3. 現在の帳票関数の呼出し契約・出力名を保ち、内部をbuilder→Documentへ段階的に交換する。CLI／GUIと計算処理の変更を帳票の書換えと混ぜない。
4. 計算JSONとPDFの既存の一括保存処理へ接続する。ライブラリのPDF単体の原子置換だけで複数成果物が整合すると仮定しない。
5. 最初に難しい代表断片を実証する。具体的には長い代入式＋結果、密な結合表、ページ境界の繰返しヘッダー、図のラベル、可変入力の増減。実証した書式契約を残りの章へ展開する。

P7側の具体的な変更ファイルは別担当のアプリ調査で確定する。本調査だけから計算モジュールの再実装を要求しない。

## 依存・配布の注意

パッケージ名は `gridlayoutpdf`、versionは依然0.1.0、Python>=3.12、実行時ReportLab>=5.0.1とPillow>=9.0.0である（`pyproject.toml:6`）。新しいAPIが同versionの作業ツリーへ追加されているため、version番号だけでは導入コードを特定できない。計画では利用するcommitまたはwheel hashとuv.lockを検証条件にする。

P7のmanifestには既にgridlayoutpdfとローカルsource pathが登録され、Python>=3.12、ReportLab>=5.0.1,<6になっている（`K:/ニュージャパンコンサルタンツ/26_LRT鉄道照査/P7橋脚/pyproject.toml:5`、同`:7`、同`:19`）。これは現 `.venv` の新API導入・同期を保証しない。インストール先と `__file__`、必要APIのsignature、実際の書体を実装開始ゲートで確認する。

書体・画像・テスト・fixtureはwheelに同梱しない構成である（`pyproject.toml:23`、`docs/validation.md:81`）。書体はP7から安定して参照または供給し、Windows書体の利用と配布の扱いを混同しない。PDF比較用PyMuPDFは開発依存に留められる（`docs/validation.md:24`）。

## 検証の再利用と不足分

| 既存の根拠 | P7での適用・追加点 |
|---|---|
| `tests/integration/test_representative_report.py:40` は実PDFの章順・値・ケース一回出現・用紙・ヘッダーを確認 | P7の実入力と結果JSONを期待値にし、全対象章・全項目の欠落/重複/順序を確認する。ライブラリ例の架空数値は使わない。 |
| 同`:75` と`:182` は等号座標・結果右端・10pt・外部表示文字列を独立抽出で確認 | 採用した見本書式に対する等号列、単位、分数、添字、表示桁数を検査する。生成sceneの自己比較だけにしない。 |
| 同`:104` と`:224` は長文/長い値による再フロー・幅超過を確認 | P7の符号付き最大桁数、空値、長い項目名、ケース増減など現実の境界ケースを加える。 |
| `tests/integration/test_document_pdf.py:55` は失敗時の既存PDF保持 | P7のPDF＋結果JSON一式に対し失敗時の整合・既存出力保持を確認する。 |
| 同`:113` は表のheader反復、rowspan、順序を確認 | 荷重組合せ・地盤等の可変行数表について、ページ境界で行群が割れずケースが欠けないことを確認する。 |
| `tests/visual/test_representative_golden.py:34` は固定フォント・固定ツール・全頁のdecoded pixel比較 | P7用の新しい見本比較と目視受入の後に新goldenを作る。既存5頁/37頁goldenをP7の期待画像にはしない。 |
| `tests/integration/test_cantilever_improvements.py:179` は密な表、回転表、Scriptの実PDF照合 | 新APIへ依存する場合の構成例として参考にできる。元p26/p30の値や固定37頁条件を移植しない。 |

現在のライブラリの合格記録はP7アプリの書換え成功を意味しない。既存アプリの計算回帰テスト、CLI/GUI経由の出力経路、対象全帳票の通常/grid全頁目視、採用書体と導入版を固定した回帰が別途必要である。

## 対話で残すべき問い

- 「書き直す」は帳票生成層が主対象か、入力GUIや計算構造も含むか。推奨は帳票生成層を交換し既存計算の結果を保持。
- 「体裁」の合格は、書体・インデント・式/表構成・等号揃えを共通化して可変内容を自動改ページする方式か、見本の固定ページ再現か。既存用語で区別し、片持ち梁の過去回答を流用しない。
- 帳票の全対象と未実装章の扱い。見本にあるだけの章・算式を今回新規計算へ拡張しない。
- 書体、ページ装飾、横に広い表の回転またはA3横、図を既存動的描画から移すか画像化するか。探索で確定できる項目は質問せず実物に基づいて提案する。

## 追調査: 見本の行高と可変ページ数の両立

後続対話で全6帳票PDF移行、計算/UI/I/O維持、見本の書体・インデント・等号位置・表行高の踏襲、全6帳票の可変ページ数が確定した。上記の未確定問いはこの指定で該当部分を解消する。以下は製品編集・試作をせずに調べた、計画の技術実証候補である。

### 現APIの制約

- `Table.row_heights`は正の整数で、実高さはその整数×contextの縦pitchである（`src/gridlayoutpdf/tables.py:132`、同`:246`）。標準15.48ptで14.28pt行を指定できない。
- 独自Blockは正式な公開拡張点である（`docs/api.md:239`、`src/gridlayoutpdf/layout.py:90`）。ただし返す`MeasuredBlock.row_pitch`は外側contextのpitchとの一致を要求される（同`:275`）。局所計測結果をそのままDocumentへ返す実装は契約違反になる。
- `MeasuredBlock.parts`はそれぞれ整数行数で積み上がり、prefixが各fragmentで再掲される（`src/gridlayoutpdf/layout.py:120`）。Documentはこのpartを分割し、配置後に整数rowsだけcursorを進める（`src/gridlayoutpdf/document.py:237`、同`:265`）。

### 公開APIだけで採れる方式

| 方式 | 成立すること | 制約と判断 |
|---|---|---|
| 帳票全体に見本用の細かいPageProfile/GridSpecを設定 | 任意の正pitchと本文範囲を指定できる（`src/gridlayoutpdf/profiles.py:10`）。たとえばpy=.12なら14.28pt=119行、26.52pt=221行となり、Tableの既存行群分割・header反復を維持できる | 最初の実証候補。実測値の共通刻みからpitchを選び、表行高・列幅・等号/indentを整数化する。丸め誤差で値を改変しない。既存標準プロフィールは変更しない。 |
| アプリの独自LocalGrid Blockで局所計測→外側1partへ包む | 局所PageProfile＋LayoutContext＋公開measure_blockで計測し、commandsを無変形で包み、外側だけ整数行へ丸めれば小表内部の14.28pt行高は保持可能。QuarterTurnにも同様の先例（`src/gridlayoutpdf/rotation.py:69`、同`:88`、同`:119`） | 小さい不可分表に限定すれば合法。表全体を一partにするので、自動で複数頁へ伸びる表の解にはならない。 |
| LocalGridの各行群を外側標準グリッドへ変換 | 幅・高さ・metadataを維持し、外側pitchに合わせたpartを返すこと自体は可能 | 各14.28pt行群が15.48ptへ切上がると行間に余白が入る。連続する表罫線と原本行高を崩すため本件の一般解として不採用。局所結果のrow_pitch偽装や安全検査を迂回しない。 |

`QuarterTurn(turns=0)`は存在しない（`src/gridlayoutpdf/rotation.py:57`）。正逆二重回転で局所グリッドを得る手法も不可分性を解決せず、通常表の設計には採らない。既存fixtureのSourceCell/SourceScript/PageFrameはimportしない。

### 推奨と最小ライブラリ拡張の位置付け

第一候補は**見本用の細かい文書プロフィール＋既存Tableの可変長フロー**とする。小さな不可分図表にだけアプリの公開Block拡張を許す。プロフィールのpitchを細かくするだけで、本文の行送りまで見本一致すると仮定しない。Paragraphはbaseline+descentから各partの行数を決める（`src/gridlayoutpdf/blocks.py:54`）。必要ならアプリの小さな行送り部品で公開MeasuredBlockのpart予約高を明示するが、字形・行を移動/縮小して問題を隠さない。

標準外側15.48ptを絶対維持したまま、異なる局所行高の長表を隙間なく任意ページ分割する機能は、`row_heights_pt`やatomic LocalGridを単に追加するだけでは成立しない。現在の「分割単位=整数行part」契約との調整が必要になるため、これを小さな自明な拡張として計画に書かない。先行実証が不成立なら、失敗理由を固定して、分割可能な局所フロー契約を扱う独立ライブラリ工程へ戻す。

微細Gridには診断表示上の問題もある。`debug_grid=True`は全列・行に0.96pt線を描く（`src/gridlayoutpdf/renderers/reportlab.py:19`）。.12ptや.01ptの検査図は線で埋まるので、文書配置とは独立した粗い検査overlayを公開Line/ScenePageで作るか、診断グリッドの間引きだけをopt-in追加する。これは本文レイアウトの拡張とは分ける。

### 技術実証の成立条件・停止条件

1. 見本実測のフォント・face・size・本文幅・indent・等号座標・表列幅/行高・罫線を契約化し、微細Gridへ無断丸めなく写せる。全てを一律14.28ptと推測しない。
2. 短表・二頁以上の可変長表・複数行header・rowspanを含む実データで、実PDFの行境界差が採用した原本行高に一致し、改ページ前後に空きや罫線の欠落が生じない。header反復、ケース順序/一回出現も独立抽出で確認する。
3. 現行書体のfont metricsと保守的boundsのまま、密なセルが指定行高へ収まる。CellLines/Insetsと明示余白で成立しない場合は失敗とし、fixture専用ink計測・文字縮小・例外無視へ逃げない。
4. 微細化後のSpacer、Columns、EquationAnchors、PageDecorationのrows/gapを新単位へ換算する。PageDecoration(rows=1)を微細gridでもそのまま使用しない。長い式・最大片側符号付き数値・単位を含め独立座標検査を行う。
5. 本文と同じ配置を保った、読みやすい粗い検査overlayを作成できる。通常/検査PDFの本文文字・数値・位置は同一。通常PDFの密度、全頁外観、生成時間・出力容量も確認する。
6. いずれかが不成立なら残り5帳票への展開を止め、ライブラリ拡張またはプロフィール/部品設計を修正して同じ実証を再通過する。固定原本ページ数の要求は追加しない。

