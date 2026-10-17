# Cantilever p01–37 improvements — execution

2026-10-17、ユーザーの「OK GO」により計画全8工程を承認。計画slugは `cantilever-p01-37-improvements`。

## 基準と範囲

- 実装開始HEAD: `3da8b7cb71803c463029c68e155798f377c62e07`。作業ツリーはクリーン。計画段階の未コミット状態は解消済み。
- 現行受入bundle: `20261017T023053Z-a954761644604bd1a289b5fcdd9f20d1`。指定された旧bundleも保持する。
- 最新外観修正（MS書体、意味run、基線、明示行高、Text.shear_x、fixture局所ink測定）を維持。IMP-014〜024の一般API化は今回へ追加しない。
- FR-014/015、3345項目・114式・124ケース・63不明値・16図、固定37頁を維持。
- 現行ソース・原本・書体・current・goldenのhashは `.agents/logs/cantilever-improvements-start.json` に保存。

## 実装順・担当

所有表: `.agents/logs/ownership-team-execute-cantilever-p01-37-improvements.json`。基準HEADとの差分で最終照合する。

| 工程 | 担当 | 前提・完了条件 | 状態 |
|---|---|---|---|
| 1 原本順序検査 | source-validation | 全37頁・同inventory負例・prepare/activate両ゲート | 担当166件、lead142件合格 |
| 2 契約と最小実証 | lead + 各担当 | 原本アンカーを保持、p26/p30セル・罫線・p9添字で実証 | 829セル・16図・3頁proof合格 |
| 3 Insets/診断 | table-content | float互換、明示row_heights厳守、span内訳 | 実装・対象試験合格 |
| 4 CellLines | table-content | 一度の内側丸め、空行・非接触・行別style | 実装・対象試験・fixture統合合格 |
| 5 Image物理寸法 | image-script | 元比率fit互換、指定pt・snapshot厳守 | 実装・対象試験・fixture統合合格 |
| 6 Script明示style | image-script | auto互換、指定値非補正・role/衝突検査 | 実装・対象試験合格 |
| 7 不可分Table | table-content | split=Falseだけ1part、header/行高保持 | 実装・対象試験合格 |
| 8 合流・受入 | lead | 独立レビュー、全テスト/coverage、wheel、全74画像・新bundle | 修正後1939件・98.825109%、3観点未解決0、wheel/画像確認・有効化後監査合格 |

API契約は承認済み計画の各Stepを規範とする。`Insets(top,right,bottom,left)`、`Cell.padding: float | Insets`、`CellLines`、`Image(width_pt,height_pt)`、`Script(scale,superscript_rise,subscript_drop)`、`Table(split=False)`。既定動作は変えない。新製品依存は追加しない。

独立モジュールのテストと実装は並行できるが、fixture移行は原本順序ゲート合格後に行う。SourceCell/SourceScriptの非等間隔アンカー・字送り・実ink契約は残し、等価であることを示せた共通責務のみ移す。

## 検証ケースと記録

担当は共有runnerによるRed/Green、変更ファイル、判断と未解決事項をcanonical work logへ記録する。leadが統合後に独立再実行する。

- source: p1桁交換、回転順序、符号移動、添字role、同字重複。全37頁の正常例。
- table/cell: scalar互換、全辺・align/valign、幅不足、結合、明示行高、空行、丸め境界、0.12pt局所grid、行接触、trace JSON、不可分罫線。
- image: 部分指定拒否、非整数pt、±0.5pixel比率許容、EXIF/alpha、枠不足、snapshot、16原本図。
- script: default一致、片側/両側、入れ子、書体、invalid値/role/衝突、狭い枠、PDF基線。
- integration: representative golden不変、最新片持ち梁golden差分・原本直接照合、新APIの組合せ、wheel Python3.12/3.13。

## 結果

計画時1508件および外観修正時1738件は今回の完了結果として転記しない。

- 開始時: 1738 passed /67.63秒。`cantilever-improvements-baseline.log`。
- lead独立対象検証: 画像79件、CellLines/Insets62件、10ファイル合計486件、原本順序/再現142件合格。`improvements-lead-{images,cells,modules,order}.log`。件数を合算した全体結果とは扱わない。
- 配布物: sdist→wheel、22製品moduleのhash一致、Python3.12.12/3.13.11新規環境で新APIを生成・計測・描画。両版のPDF画素一致、PyMuPDF未導入。`build/reports/cantilever-p01-37/improvements-wheel-acceptance.json`。初回proofは0paddingセルを罫線に接触させた正しい拒否となり、明示inner_padding=.6の正常例へ修正して合格。
- DESIGN型付きwriter: 新API opt-in互換と原本順序ゲートの2決定を記録。result=applied、decisions_appended=2、skipped_duplicates=0。
- table/image/script担当とleadは既定APIと新APIを分けて検査。SourceCell/SourceScriptの水平位置・字送り・局所inkは等価でないため残す。現行source表はsplit=Trueと二分seamを維持し、split=Falseは公開APIの独立実証へ適用する。
- rootが3書体Scriptの通常/grid proof2画像を個別確認。添字役割、非接触、図を確認した。最終37頁の目視は別ゲート。
- APIガイドのdenseセル例を文書から直接実行し、1頁・overflowなしを確認した。

### 初回統合・配布物・紙面（Q01/Q02修正前）

- 初回全体検証: **1925 passed /135.39秒、行coverage98.823529%（2975行中2940行）**。`.agents/logs/cantilever-improvements-final.log` と `.agents/logs/cantilever-improvements-final-coverage.json`。担当別結果の合算ではない。Q01/Q02修正後の最終結果とは区別する。
- fixture統合: 対象163件と8件のAPIproofを検査し、p26/p30の298セルは別expectedと実PDFの順序・添字を照合した。全体1925件にも含まれる。p1/p26/p30/p36の70+186+267+306=829セルと16図の委譲・予約・snapshotを検査した。
- 3頁の公開APIproof: `build/reports/cantilever-improvements-proof/{normal,grid}.pdf`。rootも6PNGを個別目視し、選択罫線・回転表・入れ子添字の配置を確認。密な行の罫線余裕には上下inner_padding=1.01ptを明示、p30は別実証の局所容量504ptを明示した。原本再現側へは適用しない。
- 予約行数の訂正: 計画の旧47行予約は実コードと一致せず、現行PageFrameは48行予約だった。これを維持し、代表4頁の実描画下端692.500/764.638/776.398/776.398ptが47行境界782.158pt内であることを検査した。
- 37頁再生成候補: `20261017T031210Z-8d17d7f6d15549a2bab7cdc27c9ec982`。入力129件、成果物78件。通常/grid各3345項目、原本順序3345項目、16図、全37頁の外観error0。最大基線差0.043419pt、等号差0.0000611pt、表罫線差0.002pt。
- rootが候補の通常37枚/grid37枚を個別表示。全74画像の画素配列は最新受入023053版と完全一致。`build/reports/cantilever-p01-37/improvements-visual-comparison.json` と `improvements-visual-review.json` に記録。goldenの37PNGと画素hashを保持し、manifestの入力pins/approvalだけを更新した。旧manifestも `improvements-baseline-manifest.json` に保存。
- 共有文書チェック: `.agents/logs/cantilever-improvements-integration-check.json` の `ok=true`、detect_stack/design-doc/state-docすべてexit_code=0。これは機能試験ではない。既存の空architecture節warningは維持。
- 所有照合: 基準HEADとの差分でoverlaps/unowned_changes/idle_ownersなし。4実装worklogの形式検証も合格。レビューscopeは `.agents/logs/cantilever-improvements-review-scope.json`、patchは `.agents/logs/review-diff-cantilever-p01-37-improvements.patch`。ruffはこの環境にないため `status=skipped`、未実行を合格とは扱わない。

### 独立レビューと有効化

security/testsは初回差分について未解決0で合格。品質担当のCodex CLI相談は511.9秒で正常終了し、独立再現で次の2件を採用した。候補031210は有効化しない。修正後の全体検証・配布物・新候補を最終証拠とする。

| 指摘 | 内容 | 対応 |
|---|---|---|
| Q01 Medium | expectedの本文とsource_bboxを2セル間で一緒に交換すると、原本順序ゲートがIDと原本領域の誤対応を見逃す | 解消。基準commitのID→bbox正規形だけを独立pinし、本文は原本直接照合を維持。5負例Red→Green、対象20件・回帰183件合格。品質・セキュリティが基準commitの37頁3345組とpinを独立再照合 |
| Q02 Low | CellLinesの横方向逸脱で構造化エラーのneeded/availableが縦寸法になる | 解消。横/縦を分離し、各軸の変位を含む必要範囲と内側容量を返す。左右上下×余白有無の8負例Red→Green、配置と拒否条件は維持 |

品質担当の修正後試験はQ01が21件、Q02が37件合格。セキュリティ担当は57件合格。未解決指摘は0。初回全体1925件・wheel hash・031210の目視は変更前の証拠として保持する。品質・セキュリティ・テストの各報告には初回確認と限定再レビューを分けて記録する。

### 修正後の最終受入・完了

- root単独の全体検証は **1939 passed /192.16秒、行coverage98.82510909701242%（2979行中2944行）**。共有runnerの`.agents/logs/cantilever-improvements-revised-final.log`と`cantilever-improvements-revised-final-coverage.json`が最終証拠。集計表示の99%を実数と取り違えない。
- [品質レビュー](../research/review-quality-cantilever-p01-37-improvements.md)、[セキュリティレビュー](../research/review-security-cantilever-p01-37-improvements.md)、[テストレビュー](../research/review-tests-cantilever-p01-37-improvements.md)はいずれも修正後PASS・未解決0。テスト担当も追加16件合格、37頁3345組の領域pinと新候補のhash連結を独立監査した。3観点の初回確認でQ01を見逃した経緯は削除していない。
- 修正後wheelをsdistから再構築し、Python3.12.12/3.13.11の新規環境で受入。22製品moduleの現ソースと配布物のhash一致、両環境の公開API描画画素一致、PyMuPDF未導入を確認。wheel SHA-256は`14ac344e68447ef802580824e14b02cf6a719c6d7b04ea0a92dc28125ac02510`。証拠は`build/reports/cantilever-p01-37/improvements-wheel-acceptance.json`。
- 最終候補`20261017T033209Z-f93e3db55c094beaa28d3b3029fc2b7d`の通常/grid各37頁で3345項目・16図・原本順序・外観error0。全74PNGのbytesと画素配列が、個別目視済み031210および既存受入023053の両方と完全一致した。同一画像の74件の目視結果を再利用し、最終候補のp1/9/26/30/36×通常/gridの10画像を追加表示した。最終候補を新たに74回表示したとは記録しない。`improvements-visual-comparison.json`と`improvements-visual-review.json`に初回目視記録のSHAも保持する。
- 全ゲート通過後に既存activate_bundleで新versionだけを有効化し、currentを最後に切り替えた。031210はstagingのまま有効化していない。元の005753/023053 versionと37枚のgolden PNGは保持した。有効化前161ファイル・有効化後160ファイルの基準hash不変も確認した（差はcurrentの許可された切替）。
- 有効化後の監査`improvements-current-audit.json`はPASS。129入力・78成果物・37golden・22wheel module・目視記録・currentの解決先を照合。normal/gridとも37頁・595×842pt・Rotate0。normal SHA-256=`3c9e8bb26344d13eae3b03658252373e40ac4b448c2ad7ecdbae4045c1f98d9b`、grid=`4a877c90455791b627663b7335ab15c7b00c92561ac8a6f476b11fc5ee1476ee`。
- 所有照合と7worklog契約はPASS。作業途中に追加された別作業の`CONTEXT.md`の体裁見本用語と`pier-report-grid-*-findings.md`は変更せず保持し、本実装の成果として扱わない。最終差分収集にはこれらの共有作業ツリー変更も含まれる。ruff未導入によるskippedは合格として扱わない。
- 修正後の差分は`.agents/logs/review-diff-cantilever-p01-37-improvements-final.patch`、収集結果は`cantilever-improvements-final-review-scope.json`。全体試験後に完了文書とSTATEを更新したため、全ファイルのmtimeを比較する収集器はcoverageの`stale_vs_scope=true`を返す。製品・fixture・テストは試験後に変更しておらず、最終coverageは上記1939件の実行に対応する。新しい試験を装うための再集計・時刻更新はしていない。収集用の一時`coverage.json`はログ保存版とhash一致を確認して除去した。

成果物: [通常PDF](../../../build/reports/cantilever-p01-37/versions/20261017T033209Z-f93e3db55c094beaa28d3b3029fc2b7d/normal.pdf)、[グリッドPDF](../../../build/reports/cantilever-p01-37/versions/20261017T033209Z-f93e3db55c094beaa28d3b3029fc2b7d/grid.pdf)、[切替後監査](../../../build/reports/cantilever-p01-37/improvements-current-audit.json)。承認済み8工程に未完了作業なし。コミット・外部公開は行っていない。
