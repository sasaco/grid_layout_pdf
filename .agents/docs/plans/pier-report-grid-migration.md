## Implementation Plan: Pier Report Grid Migration

状態: 3問の要件対話を反映した計画案。工程分解のCodex相談、形式・存在検査は完了。内容レビューと計画全体の実装承認は未完了。製品実装・PDF再生成・移行後試験は未実施。

### Purpose

P7橋脚アプリの6帳票すべてのPDF生成を、このrepoの `gridlayoutpdf` へ移行する。現在の計算内容とアプリの利用方法を保ち、`Example橋脚/output/*.pdf` の書体・字下げ・等号揃え・表行高を踏襲した、内容に応じて改ページする計算書を出力する。

### Scope

対象はAPPの全PDF生成と、その実現に必要な最小限の汎用描画機能・回帰検証である。

#### 対象と確定条件

- `GL` = `C:/Users/sasai/Documents/GridLayoutPdf`（本計画の正本を置くrepo）。
- `APP` = `K:/ニュージャパンコンサルタンツ/26_LRT鉄道照査/P7橋脚`。以下のアプリ側パスはAPP相対。
- `REF` = `K:/ニュージャパンコンサルタンツ/26_LRT鉄道照査/Example橋脚/output`。
- 計画slugはworkspaceが解決した `pier-report-grid-migration`。引継ぎ先も同slugを使う。
- **確認済み**: 0500/0600/0610/0620/0710/0720のPDF生成を全面移行。計算ロジック、入力画面、入力JSON、CLI/GUI操作、成果物名・結果schema・公開契約は維持する。旧描画器を選択可能なfallbackとして残さない。
- **確認済み**: REFは体裁だけの見本。現アプリの数値・条件・式・ケースを見本へ戻さない。見本にない0710/0720も現在の全内容へ共通書式を適用する。
- **確認済み**: 全6帳票のページ増減を許す。0710=3頁/0720=4頁の旧制約も解除する。見本69頁や片持ち梁fixtureの37頁・頁番号省略は移植条件ではない。
- **計画提案**: A4縦を維持する。章番号・頁番号の意味は現在のP7仕様に従い、増減後の実ページに連番を付ける。図は現在の入力に追従するnative図形を使い、既存の静的画像が必要な箇所に限り画像を使う。本文・式・表やページ全体の画像貼付では代替しない。
- **確認済み**: 本文・数値・表は白黒に統一する。赤/青数値は黒、黄色の表見出しは白地とし、見出し書体・結合・罫線・配置で区別する。この移行のためのカラー文字/背景API追加は不要。

| Stage | 既存の公開入口 / 主な実装 | 体裁の参照と内容の正本 |
|---|---|---|
| 0500 | `pier_design/report.py` | REF/0500、現在の0500結果 |
| 0600 | `reaction_report.py` と値・layout・pagination・図の各module | REF/0600、現在の0600結果と既存表示評価 |
| 0610 | `longitudinal_report.py` → `longitudinal_example2_report.py` | REF/0610の書式、現行schema2の内容 |
| 0620 | `transverse_report.py` → `transverse_report_example2.py` | REF/0620の書式、現行schema2の内容 |
| 0710 | `seismic_longitudinal_report.py` | 4見本の共通書式、現在の地震時線路方向の内容 |
| 0720 | `seismic_transverse_report.py` | 4見本の共通書式、現在の地震時線路直角方向の内容 |

#### New files

- APP `pier_design/reporting/__init__.py`, `fonts.py`, `styles.py`, `formatting.py`, `equations.py`, `tables.py`, `figures.py`, `document.py`, `runtime.py`。原稿組立・書式・必要な表示変換・描画依存識別を担当する。計算ソルバーを置かない。
- APP `pier_design/reporting/stages/{foundation,reaction,longitudinal,transverse,seismic_longitudinal,seismic_transverse}.py`。帳票固有の節・式・表・図を現在の結果から組み立てる。
- APP `tests/reporting/test_renderer_inventory.py`, `test_report_source_parity.py`, `test_gridlayoutpdf_proofs.py`, `test_report_content.py`, `test_report_appearance.py`, `test_report_publication.py`, `test_render_dependency_identity.py`。既存試験で十分なケースは重複作成しない。
- APP `tests/fixtures/reporting/{baseline,appearance}/`。凍結入力・数値/表示値の独立期待値・原本書式の測定値・出典hash・内容対応台帳を保存する。期待値を新builderから自動生成しない。
- APP `docs/reporting-style.md` に確定書式、`docs/reporting-migration.md` に入口台帳・内容対応・変更理由・検証結果をまとめる。
- GL `.agents/docs/plans/pier-report-grid-migration-execution.md`（実装開始時）。担当、ゲート、実行した試験、未解決指摘を記録する。

#### Modified files

- APP `pier_design/report.py`, `reaction_report.py`, `longitudinal_report.py`, `transverse_report.py`, `seismic_longitudinal_report.py`, `seismic_transverse_report.py`。既存の公開関数signatureを維持して新原稿へ委譲する。
- APP 0600の `reaction_report_{values,layout,pagination,horizontal,snow,diagrams}.py`、0610の `longitudinal_example2_report.py`、0620の `transverse_report_example2{,_loads,_cases}.py` と `transverse_report_style.py`。値評価を保持し、旧PDF描画は移行・撤去する。
- APP `frame_outline.py`, `frame_model_report.py` の描画依存部分。外形・節点・寸法・微小部材等の意味的な幾何を保つ。
- APP `longitudinal_report_reference.py` 等の旧帳票経路。入口台帳で互換用途を判定し、必要な入口は新描画への委譲、用途のない描画コードは撤去する。旧計算器・auditデータは別責務として保持する。
- APP `cli.py` は新描画例外の変換と新描画への接続に限定する。並行追加された `GenerationCandidate` / `prepare_generation` の一回生成・同じbytesの検証/公開を維持する。
- APP `jrsnap_artifacts.py`, `scripts/accept_jrsnap_ndu.py` は、入れ子原稿・外部描画ライブラリ・書体等の依存識別へ追従する最小修正候補。NDUモデル、serializer、読戻し計算の機能追加は行わない。
- APP `tests/test_*report*.py`, `test_*cli*.py`, `test_editor_calculation.py`, `test_editor_gui.py`, `test_frameweb_publication.py` 等の影響箇所。固定ページ数/旧座標だけの検査を新しい内容・体裁検査へ置き換え、数値oracleは維持する。
- APP `README.md`, `pyproject.toml`, `uv.lock`。新導入版と書体要件・可変ページ数を反映するための最小変更。無関係な依存更新は行わない。
- GL `src/gridlayoutpdf/{styles,blocks,scene,diagnostics,tables,cell_content,document}.py`, `renderers/reportlab.py`, `docs/api.md` と該当unit/integration testsは、Step 3で公開APIの不足を実証した場合の最小汎用拡張候補。P7固有の式・ケースを汎用ライブラリに入れない。

#### Dependencies and protected boundaries

- P7には既にローカルpath依存のgridlayoutpdf 0.1.0が登録済み。同じversionの異なる実体を区別するため、実装開始時に受入済みコードと配布物hash・インストール場所・必要APIを固定する。
- 計算器、inputs/actions/combinations、入力JSON、入力GUI、FrameWeb/NDUの意味変換は変更対象外。rendererは渡された結果を変更しない。
- PDFは既存stagingへ生成し、JSON/FrameWeb/NDU/sidecarとの整合確認後に既存公開処理を使う。PDFだけを正式フォルダへ上書きしない。PDF hash・publication ID等の公開メタデータは新成果物に追従して更新する。
- 最新観測では通常all=16成果物、JRSNAP付きall=18、0710単独+JRSNAP=4。これはAPI台帳から確認する数であり、テストやGUIへ新たな固定値として埋め込まない。
- REF、元Excel、入力、旧正式出力、既存の数値oracle・goldenを保持する。QA用grid/trace/PNGは正式staging集合へ追加しない。
- GLとAPP双方に並行変更がある。HEADだけでなく変更済み/未追跡ファイルも記録し、担当外変更を上書きしない。

#### 調査根拠

- [アプリ調査](../research/pier-report-grid-app-findings.md): 最新境界は `cli.py:_render_reports`（調査時218行）、`prepare_generation`（249行）、`GenerationCandidate`（86行）。0600表示評価、全6入口、既存試験、JRSNAPの並行変更を含む。
- [公開API調査](../research/pier-report-grid-api-findings.md): 文書・数式・表・図API、密なセル、細かいPageProfileの選択肢と制約。
- [見本調査](../research/pier-report-grid-reference-findings.md): 原本4冊69頁の構造調査、7頁個別目視、hash、確定した対話。
- 工程分解: `GL/.agents/logs/codex/20261017T033305Z-plan-pier-report-grid-migration-steps.md`。相談後に判明した最新JRSNAP境界と微細グリッドの制約は、本計画で補正する。

### Implementation Steps

表示内容と見本書式の独立した基準、先行実証、各帳票の移行、統合、全体受入の順で進める。

#### Step 1: 最新のアプリと依存物を固定し、移行前基準を確立する

- [ ] GL/APPの状態・依存物・書体・参照原本・正式出力hashを記録し、既存未コミット/未追跡変更の所有を確認する。計画中の古い行番号ではなく、最新call siteを読む。
- [ ] APPの全PDF入口・呼出し元・使用schema・必要な互換入口を `docs/reporting-migration.md` へ列挙する。preview等のPDF読取りとPDF生成を区別する。
- [ ] 既存venvの計算/帳票/CLI/GUI/公開試験を実行し、移行前の成功・失敗を記録する。既存依存のlock不整合は別作業と混同せず、必要最小限の同期と実体検証で再現可能な実行環境を確保する。
- [ ] 並行JRSNAP実装の合流を再確認する。調査時はexport/ndu moduleと関連試験が未完だったため、既存経路の完成を本移行が勝手に代行しない。計算/公開の安定した基準を確保できない経路は、統合・正式公開を進める前に並行担当の完成版と再照合する。
- [ ] 試作は `APP/tmp/reporting-grid-migration/<run-id>/` へ隔離し、基準入力と出力は不変保存する。

**Verification**: 使用コード・wheelまたはソースmanifest・書体face/hashとインストール先が一致。必要なpublic APIのsignature確認、`uv lock --check`、既存試験の実結果、原本/正式出力の不変hashを記録する。既存失敗を黙って成功に数えない。通常6帳票の基準が成立しない間は移行後の同値性を合格にしない。

#### Step 2: 計算内容と見本書式を独立した台帳へ固定する

- [ ] 全6結果の数値・単位・符号・表示桁・欠値・式因子・全支承/ケース/節/注記を、既存独立oracleと現行入力から内容台帳へ記録する。行/セル/式をstage内の安定IDで追跡する。
- [ ] `reaction_report_values.py` の既存式評価を保持し、現在使われる全論理セルと表示文字列、式依存、ROUND/IF/SUM、Single/Doubleの引継ぎを基準化する。純JSON評価資源と座標/罫線資源を区別する。
- [ ] REF全69頁を構成別に棚卸しし、書体face/サイズ、本文基線間隔、階層別左端、等号列、表行高・列幅・罫線・結合、図題を独立測定する。対応する見本のない現在の節には共通書式の適用元を明記する。
- [ ] 役割別の書式と比較許容を実装前に固定する。書体faceは一致、通常の文字サイズ差は0.1pt以内、共通アンカー相対位置・同構成の表行高は0.5pt以内を計画上の初期受入値とする。抽出器の差を理由に後から一括で緩めない。原本自体のばらつきがあれば、該当する意味構成ごとに基準値を分けて記録する。
- [ ] 現在の入力と見本では数値が違うため、全ページ画素一致・原本絶対Y・原本頁数を内容検証に使わない。書式の比較ではユーザー指定の白黒化を期待変換として明示し、原本の赤/青/黄との色差を不具合に数えない。

**Verification**: 全6帳票の旧内容と台帳を一回被覆で照合。0600表示セルを旧評価器と完全比較。順序交換、符号変更、式因子欠落、単位違いを検出する負例を作る。書式期待値は原本を直接測定した出典付きデータで、新rendererの自己抽出ではない。

#### Step 3: 微細グリッド・長表・数式・図を先行実証する

- [ ] 0500地盤表、0600分数/添字/複数等号式と寸法図、0610/0620多段結合ヘッダ・縦ラベル・長表を、現在のP7値と公開APIだけで小さなproofへ組む。
- [ ] 第一候補は帳票全体の見本用 `PageProfile/GridSpec`。見本の行高やアンカーを表せる共通刻みを測定して決める。0.12pt等は検討例であり、未測定のP7既定値にしない。標準15.48ptの行へ局所表の各行を丸め直す方法は、行間を増やすため採用しない。
- [ ] 明示 `Table.row_heights`、`CellLines`/`Insets`、適切なセル基線を使い、保守的な字形境界を維持して密なセルを収める。表全体を不可分blockへ包むだけで長表分割を回避しない。
- [ ] 微細Gridに合わせSpacer/Columns/EquationAnchors/PageDecorationの単位を変換し、本文の基線間隔も確認する。Paragraphはbaseline+descentで行送りを決めるため、必要なら明示行送りを既定互換のopt-inとして最小追加する。
- [ ] 本文・数値・表は黒文字/黒罫線/白地で実証し、原本の入力値/参照値という意味は内容台帳側に残す。白黒化のため数値や注記を削らない。既存の黒文字APIを使い、カラー文字/セル背景機能は追加しない。
- [ ] 微細Gridの全線を描く既存 `debug_grid=True` は使用せず、公開scene部品による粗い検査overlayを別QA出力にする。必要なら診断線の間引きだけを公開opt-inとして追加し、本文配置は変えない。
- [ ] 必要な最小汎用拡張の依存順を確定し、library変更→GL回帰/proof→wheel作成→P7へ強制再導入→導入実体/hash/API確認→APP proof→source identity/receipt確認→帳票展開の順で進む。非editable path依存なので、library変更のたびに `uv sync --project "$p7Root" --locked --reinstall-package gridlayoutpdf` を実行する。fixture専用SourceCell/SourceScript/PageFrameやprivate rendererをimportしない。
- [ ] APPのPythonで `gridlayoutpdf.__file__` と必要API signatureを検査し、インストールされた製品ファイル集合/個々のSHA-256を今回の固定ソースmanifestと照合する。配布wheelのhashと内容manifestも別に記録する。version文字列だけ、GL環境だけ、`uv build`だけの確認でAPP proofへ進まない。候補のsource identity/receiptも、この導入実体と同じhash集合へ結び付ける。

**Verification**: 実PDFのnative抽出と原本測定値で書体・基線・等号・行高・罫線を検査。2頁以上の長表でheader反復、rowspan、行順、行群境界を照合。PageDecorationの予約高、Paragraph leading、Spacer/Columns/anchorsのpt換算も実PDF/traceから数値検査する。通常版と粗いoverlay版は同じ確定layoutを使い、本文文字列・値・ページ数・glyph座標・基線・等号座標が一致すること、確定sceneの差分が診断線だけであることを機械照合する。意図的に本文位置や基線をずらす負例で検査の感度も確認する。長式の合法折返し、短すぎる行高、巨大不可分行群、書体不足、極端寸法と近接節点ラベルの負例も検証。通常/検査proof全頁を目視する。不成立ならStep 4以降へ展開せず、最小拡張を修正して同gateを再実行する。libraryを変更した場合は既存全件・90%以上行coverage・既存golden・外部wheel利用の回帰、P7強制再導入と実体照合を毎回通す。

#### Step 4: 共通帳票層と描画依存識別を実装する

- [ ] `reporting/` のフォント・書式・数値整形・数式・表・図・Document共通処理をproofから整理する。stage固有の式やschemaは各stageに残す。
- [ ] 値は現在のresultと既存表示評価から取り、丸め・符号・欠値を変えない。書体未発見・欠字は明示エラーとし、受入書体と異なるCID書体へ黙って置換しない。
- [ ] 原稿・入れ子module・既存の値評価資源・実際に使うgridlayoutpdf/描画依存版・書体・画像の識別を `reporting/runtime.py` に集約する。入力や生成物を依存ソースとして循環登録しない。
- [ ] `jrsnap_artifacts.py` の直下 `*.py` hashと `accept_jrsnap_ndu.py` の集合照合が、新しい入れ子原稿・外部依存を見落とさないよう整合させる。既存のsidecar/receiptの必須構造と失敗時保護を維持し、再生成したメタデータだけを更新する。
- [ ] QA出力と通常出力を分け、保持候補のstagingに未宣言のgrid/trace/PNGを増やさない。

**Verification**: result deep-copy不変、同じ入力から同じ意味原稿、private/fixture importなし。受入前に入れ子原稿・表示資源・外部ライブラリ・書体を変更した場合の候補無効化、同じbytesの一回公開、依存追加/削除の集合違いを負例で検証する。公開経路が並行作業中の場合は接続仕様を完成版で再照合するまで、その経路の統合合格を宣言しない。

#### Step 5: 0500を最初の一貫した移行単位にする

- [ ] `report.py` の公開入口を `reporting/stages/foundation.py` へ委譲する。地盤表、支持力係数、根号・分数指数、変数説明、基準注記を現在の値で組み立てる。
- [ ] 3頁固定を可変ページへ変更し、見出しの孤立防止と式群のまとまりを適用する。共通 `_Page` の他帳票依存は台帳に残し、この段階で破壊しない。
- [ ] `test_report_cli.py` 等の計算JSONの検査を維持し、旧ページ数/絶対Y依存を内容・書式検査へ置換する。

**Verification**: 0500の全内容台帳と結果JSON一致、原本書式との直接比較、通常/検査全頁目視、入力増減時の改ページ、失敗時既存target保持。未移行5帳票の入口がこの変更で壊れないことを対象回帰で確認する。

#### Step 6: 0600の全表示値・原稿・動的図を移行する

- [ ] `reaction_report.py` を `reporting/stages/reaction.py` へ委譲し、既存表示評価の全セルを新原稿へ結ぶ。既存計算的表示処理は移行対象の値契約として維持する。
- [ ] 死荷重、列車/衝撃、水平荷重、雪等の現在の全節を意味builderへ移す。記号式・代入・結果・単位の対応を保持する。見本にしかない式や新たな計算条件を追加しない。
- [ ] `reaction_report_diagrams.py`、`frame_outline.py` 等の現在寸法・水位・重心・ラベルをFigure部品へ移す。式と表のページ境界で継続見出しを出す。
- [ ] 旧layout JSONの座標・描画経路を切り離す。必要なconstants/formulas/number format等の純データは別扱いで保持し、値依存の整理で計算を変更しない。

**Verification**: 全表示セル・全内容ID・式因子・図寸法の一致。既存Single/Doubleと表示値分離の試験を保持。座標だけを変えても新帳票の配置が変わらず、値/formatを変えた負例では適切に検出できることを確認。全節の通常/検査全頁、長文/最大桁/多支承条件を確認する。

#### Step 7: 0610・0620を現在のschemaとケースのまま移行する

- [ ] `reporting/stages/longitudinal.py` と `transverse.py` に骨組・材料・鉛直/水平荷重・作用組合せを組む。現行schema2を守る。
- [ ] 現行の全係数・ケース・支承を移行し、見本の件数へ置き換えない。現テストの320/240係数は基準入力での期待値として保持し、可変入力の件数を固定しない。
- [ ] 多段header、結合セル、縦ラベル、続きページを共通表で表現する。旧reference rendererは入口台帳に従って委譲または撤去する。
- [ ] FrameWebへ渡すresult/意味変換を変えない。

**Verification**: 既存独立数値oracle、全係数の行列位置/順序/一回被覆、全支承を確認。長表で行群不分断とheader反復を実PDFから検査。FrameWeb native payloadは移行前と意味同値で、PDF hashを含む新sidecarは整合する。両帳票の通常/検査全頁を確認する。

#### Step 8: 0710・0720を可変ページの共通書式へ移行する

- [ ] `seismic_longitudinal_report.py` と `seismic_transverse_report.py` を対応stage builderへ委譲する。現在の骨組、等価作用、微小部材、作用高さ、ケース、工学注記を保持する。
- [ ] 旧3/4頁制限を取り除き、同じ意味内容を分割規則に従って流す。増頁を理由に式・支承・非ゼロ作用を省略しない。
- [ ] 表示した式因子から結果を再現できる既存精度契約を維持し、通常全6帳票と同じ書式を適用する。

**Verification**: 既存地震系oracle、全因子・ケース・式の検査、20支承等の既存境界条件、元の3/4頁を超える内容の正常分割を確認。内容欠落や縮小で旧頁数へ収めていないことを独立抽出で判定。不可分部品自体の容量超過・render/replace失敗は既存targetを保持する。全頁目視を行う。

#### Step 9: 最新CLI/GUI/公開経路を統合し、旧PDF生成を閉じる

- [ ] 最新 `_render_reports` の6入口を切替え、新しいfont/layout例外を既存InputErrorへ変換する。計算順・選択stage・result JSON保存・候補保持・公開順は維持する。
- [ ] stage単独/all、GUIの保存→計算→プレビュー、通常FrameWeb公開を検証する。合流済みのJRSNAP on/offも同じ変更コードで検証する。実装前に存在しなかった外部連携機能をこの移行で新設しない。
- [ ] 旧 `_Page` と手書きCanvasの全呼出しを撤去/委譲する。静的検索だけでなく全importable rendererの動的経路を検査し、旧描画器が選択されないことを確認する。
- [ ] publication関連の故障注入、候補内のPDF改変、依存ソース改変、公開先競合、backup/journal保持を回帰確認する。完成候補の検証後に別PDFを再生成して公開しない。

**Verification**: APPに到達可能な旧Canvas PDF生成経路0。通常/all/単独/GUIで選択成果物集合、計算JSON/FrameWeb/NDUの意味不変、新PDFを含むmanifest/sidecarの世代一致を確認。JRSNAPは調査時未完のため、完成版でこの統合検証を通すことを最終公開の前提とする。並行機能の既知未完を「本移行で合格」と扱わず、未完ならその正式経路の公開を保留して状況を明記する。

#### Step 10: 全6帳票の受入・文書更新・正式出力を完了する

- [ ] 最終library版をP7へ強制再導入し、`__file__`、必要API、インストール済みファイル集合/hashを最終manifestへ再照合した後、現在の入力と選定した既存境界fixtureで全6帳票を隔離生成する。以後の候補/receiptにも同じ依存identityを使う。負値、0、欠値、長い名称、桁数、支承/ケース増減、ページ境界、近接図ラベルを含める。
- [ ] 全表示項目・順序・桁数/単位を独立照合し、見本由来の書式測定値と比較する。通常/overlay版の本文・ページ数・glyph座標/基線/等号位置の一致と診断線だけの差分を全帳票で自動検査し、最終候補の通常/粗い検査overlay全頁を個別目視する。
- [ ] 原本との比較と内容合格の後に、書体/入力/依存hash付きの新goldenを登録する。ページ数は固定せず、各検証入力に対するgoldenとして扱う。
- [ ] APP READMEと書式/移行文書を更新し、全試験、必要なlibrary回帰、独立レビューで未解決Medium以上0を確認する。
- [ ] 検証対象と同じ入力・依存世代の候補を、既存の公開経路で正式出力へ反映する。入力/依存が途中で変わった場合は候補を無効にして再検証する。正式ファイルを再読込しhash/manifestと全PDFの読取・ページ構成を確認する。

**Verification**: 全6帳票の内容台帳・書式比較・全頁目視・計算回帰・CLI/GUI/公開試験が合格。元入力/見本/計算oracle不変。公開したbytesと検証候補が一致し、結果JSON/関連payloadの計算内容が基準と同値。残っている並行機能の検証未完を隠して全体完成を宣言しない。

#### 実行コマンドと依存順

実装開始後、PowerShellで実際のパスを指定する。APPの既存venvを選び、GL用のuv環境でP7の試験を走らせない。

```powershell
$env:PYTHONUTF8 = '1'
$p7Root = 'K:/ニュージャパンコンサルタンツ/26_LRT鉄道照査/P7橋脚'
$gridRoot = 'C:/Users/sasai/Documents/GridLayoutPdf'
& "$p7Root/.venv/Scripts/python.exe" -X utf8 "$gridRoot/.agents/skills/_shared/run_tests.py" --project-root $p7Root --runner python --target tests --expect pass --label p7-grid-baseline
# 必要な対象試験は --target を対象ファイルへ絞り、labelを毎回区別する。
```

GLを変更した場合はGLルートで既存標準ゲートを使う。

```powershell
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests --expect pass --cov gridlayoutpdf --min-coverage 90 --label pier-grid-library-final
uv build
```

GLの受入済みソースからP7へ同期する。非editableな同一versionの再導入を省略しない。

```powershell
uv sync --project "$p7Root" --locked --reinstall-package gridlayoutpdf
& "$p7Root/.venv/Scripts/python.exe" -X utf8 -c "import gridlayoutpdf; print(gridlayoutpdf.__file__)"
# 続けて受入manifestとの製品ファイル集合/hash・必要API照合を行う。
# その合格後にだけAPPのproofと対象試験を実行する。
```

`uv sync --locked` が既存lock不整合で失敗した場合は同期成功とみなさず、Step 1の依存整合へ戻る。意図せず他依存を更新して先へ進まない。

Step 1→2→3→4が前提。0500→0600で共通層と表示境界を実証した後、0610/0620と0710/0720は所有ファイルを分けて進められる。共有styles/図/公開経路の変更は担当を一人に定め、全stageが揃ってからStep 9→10へ進む。試作合格を全6帳票の移行完了とは扱わない。

### Risks & Considerations

- **表示処理に既存計算が混在**: 0600の式評価と各帳票の表示因子を無条件に消さない。計算結果・表示値・配置の三つを分けて同値性を確認する。
- **表行高とグリッド契約の衝突**: 小さい局所表を全体不可分にすると長表分割できず、外側グリッドへ行単位で丸めると余白が増える。見本用の全体グリッドを先行実証し、字形boundsやoverflow検査を迂回しない。
- **微細Gridの副作用**: 単位換算、本文leading、等号列、ページ装飾、検査線本数を別々に検証する。処理時間/メモリも代表長表で測り、単純な高密度化による極端な遅延を受け入れない。
- **白黒化と情報保持**: 色差は今回の明示した変更点であり、原本色を再現しない。値の役割・単位・表見出しは引き続き表記し、色でしか区別できない箇所は既存の項目名/列見出しとの対応を検証する。
- **変動内容と見本の混同**: 本文位置は前の内容量に応じて動く。意味アンカー・書体・同構成の行高と全内容を検証し、同じ頁数や同じ数値を要求しない。
- **全ての表示内容を維持**: 更新するのはPDF体裁であり、計算項目の削除・章省略・入力調整による見本合わせは行わない。実装/移植監査の説明はPDF本文に混入させず文書/QA側に置く。
- **配布版と同名version**: 0.1.0だけでは版を特定できない。受入済みの実コード、依存解決、書体を固定してAPP実環境で検証する。
- **並行JRSNAP実装**: source集合が直下globのままだと入れ子原稿と外部rendererの変更を見落とす。候補世代と依存識別を同じ実体へ結び、既存の検証済みbytes公開を保つ。未完成の別機能を本移行のscopeへ取り込まない。
- **公開の相互hash**: PDF変更でsidecarのhashも変わる。旧メタデータbytes不変を要求せず、新世代の整合性と計算payload不変を要求する。QAファイルで正式候補の集合を汚さない。
- **旧テストの弱体化**: 固定頁assertionを消すだけにせず、内容の一回被覆・順序・行群・header反復・正常増頁と失敗時保護で置き換える。
- **書体**: 実行環境のMS書体face/hashを明示し、不足時に失敗を見える形で返す。書体ファイルをライブラリwheelへ無条件に同梱しない。

### Open Questions

- 未回答のユーザー要件はない。全6PDF移行、計算/UI/I/O維持、可変頁、見本の書式踏襲、本文/数値/表の白黒化を確認済み。
- 未確定の技術値（グリッド刻み、基線、書体登録名、保持する既存表示資源）はStep 2/3の測定・同値実証で確定する。利用者の新しい計算仕様を仮定する問いではない。
- JRSNAPの並行未完は外部の統合条件である。通常帳票の原稿作成を妨げないが、完成していない任意経路の最終受入・正式公開は宣言できない。Step 1/9で最新状態と担当境界を再確認する。
- 計画全体の実装開始承認は、形式・存在・Codex内容レビューを通過した具体的な文書を提示してから得る。今回の3回答を完成計画への承認として扱わない。

#### Completion gates

- Gate 1（plan-doc形式）: 初回合格。内容更新後に再検証する。
- Gate 2（workspace存在）: 合格。
- Gate 3（Codex内容レビュー）: 初回NEEDS_REVISIONの2件（P7強制再導入、overlay/微細Gridの機械検査）を修正済み。再レビュー待ち。初回記録は `GL/.agents/logs/codex/20261017T034255Z-plan-pier-report-grid-migration-validate.md`。
- Gate 4（計画全体の実装承認）: 未取得。
