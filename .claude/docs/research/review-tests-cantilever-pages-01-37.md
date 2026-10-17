# Test Review: 片持ち梁 p01–37

2026-10-17 / reviewer: review_tests / **現在の判定: PASS。未解決のCritical・High・Medium・Lowは0件。**

## 外観修正の再レビュー

ユーザーによる字体・字下げ・等号位置・行高の不一致指摘後、旧成果物の受入を再開した。以下の旧レビューは履歴であり、旧1508件合格・旧98.80% coverage・旧goldenを、現在の原本外観一致の根拠として流用しない。

対象は `Table.row_heights` / `Text.shear_x`、原本字体と意味単位の配置、独立 `verify_appearance.py`、原本順序37 controls、外観の正負例である。原本PDFのpin済みhashを確認して直接抽出する検査器は、作者側の `source-layout.json` / `font-profile.json` を参照しない。最終bundle `20261017T023053Z-a954761644604bd1a289b5fcdd9f20d1` の原本検査と、rootの74画像目視・新golden登録との結び付けを独立確認した。

最新の全件結果は **1738 passed / 107.30s**。製品coverageは **98.92313405124396%（2664 / 2693行、未通過29行）**。`.claude/logs/cantilever-appearance-final-full.log` と同 `cantilever-appearance-final-coverage.json` を直接読み、coverage対象21ファイルが全製品Pythonファイルと一致し、測定記録が対象の最終更新より新しいことを確認した。この数字はfixture検査器自体のcoverageではない。全件試験の重複実行はしていない。

### APP-T01 — Medium、解消

`tests/fixtures/cantilever_p01_37/verify_appearance.py` の旧検査は文字の進行方向の位置だけを比較し、その直交方向の基線差を検出しなかった。候補 `20261017T021112Z-ab279022e1dd42fc89f885990c6faa02` で `p09-sum-x2` の上付き2が原本より2.52/3.24pt下がっていた。さらに `p03-equation-001` のoperand `0.471` をy+2pt動かしても、内容検査と外観検査を通過した。原本・候補のp09 cropでも確認した。

原本の文字方向 `(dx,dy)` に対する直交射影 `-dy*x + dx*y` を、本文・数式・表の全対応文字で **.20pt** の固定許容差で比較する修正を実装した。通常字体に広い補正許容は設けていない。除外は `p21/p22-origin/end-table.r1.c0` の縦方向Identity-Vの括弧8字だけにID・文字・方向を明示限定し、全8字について8倍描画の原本ink比較とy+8pt変位の負例、計16ケースを追加した。原本PDF自身を使った全37頁のpositive controlsは、この新カテゴリの存在・非零検査件数・誤検出なしを確認する。

旧候補の独立全頁実測では256項目・1086字が.20ptを超えた。全字のID/index/文字/family/サイズ/原本と出力origin/符号付きdeltaは `.claude/logs/cantilever-perpendicular-deltas.json` に保存した。正方向は上記直交射影の増加である。

| 原本family / 対象 | 旧候補のdelta（pt）と字数 | 原因・修正対象 |
|---|---|---|
| MS-Mincho、p03–15の算式・単位等 | −.48: 298字 | 意味runに原本固有baselineがなく、行baselineを共用 |
| MS-Mincho、p09–14の作用位置・モーメント等 | −1.68: 92字、+1.08: 2字、+1.082: 2字、+1.20: 40字、+1.32: 20字、+.84: 8字 | 本文runとScript基底・添字の原本baseline差を未保持 |
| MS-Mincho、p09/p15/p16–18のsum/rail/Rm等 | +.72: 45字 | 意味run基線の共用 |
| MS-Mincho、p13–15の応答値 | +.48: 20字 | 意味run基線の共用 |
| MS-Mincho、p16–20のHbd/Hsd | +.36: 60字 | 基底20字・添字40字の基線ずれ |
| MS-Mincho、p09-sum-x2の上付き2 | +3.24: 1字、+2.52: 3字 | 固定sup offsetが原本の−5.64/−4.92ptと異なる |
| MS-Gothic、p24-dead1/dead2-title | +.72: 14字 | 見出しの基底12字・添字2字の基線ずれ |
| MS-Mincho、p30–37回転表 | +.315: 12字、+.469: 18字、+.709: 451字 | global font ascentの保守的な矩形による表セル下方補正 |

Typography担当は意味run基線とScript `sup_y/sub_y` を原本から保持し、Table測定だけ実glyph inkを使うことで従来の最大.85pt補正を撤去した。原本inkが上罫線に触れる明示8セルだけ、実測.043421875/.01271875ptの補正を最大.05ptに制限した。通常の外観許容差は変更せず、元FontRegistryと描画commandも保持する。上/下の実ink超過は引き続き拒否する試験がある。

更新後の単頁候補37枚をreviewerも独立再測定し、直交基線21,204字、error0、最大差0.043418884ptを確認した。p30–35の記録済み接触セル以外は、各頁最大0.000061035pt以下で、p09の上付き差は0だった。結果は `.claude/logs/cantilever-review-perpendicular-final-measurements.json`。これは最終bundleへのhash結び付け前の単頁候補に対する実測である。

### 再レビューの実行証拠

| 実行 | 結果 | ログ |
|---|---|---|
| 旧候補への独立発見probe | 2 failed（意図したassert Red） | `cantilever-appearance-review-red.log` |
| 正式原本37 controlsとy+2負例2件、検査器修正前 | 39 failed（カテゴリ不在/変位未検出） | `cantilever-perpendicular-red.log` |
| 追加した原本基線・上付き・変位・Identity-V ink | 56 passed / 7.32s | `cantilever-perpendicular-targeted.log` |
| 修正途中の外観一式 | 101 passed / 6 setup errors（p30表の実ink罫線余裕、Typographyへ返却して修正） | `cantilever-perpendicular-green.log` |
| 修正後の外観一式 | **107 passed / 10.30s** | `cantilever-perpendicular-final.log` |
| 最終bundle・全hash・golden・原本外観の独立監査 | **5 passed / 3.86s** | `cantilever-final-appearance-registration.log` |
| root単独実行の修正後全件試験、ログをreviewerが確認 | **1738 passed / 107.30s** | `cantilever-appearance-final-full.log` |

すべて共通 `run_tests.py`、固有labelとCOVERAGE_FILEで実施した。Redはpytest非零をwrapper `--expect fail` で確認したもので、合格と混同しない。`.claude/check.ps1` はexit0、ok=true、detect_stack/design-doc/state-docの3check合格（`cantilever-tests-appearance-review-check.json`）。検査器の変更はrootから明示所有権移管を受けた2ファイルに限定した。

p15-dead-eqの第2等号を別途原本から再抽出し、2行ともorigin x431.04/center436.04で候補と一致した。旧候補のy−.48ptはAPP-T01の対象である。全頁縮小画像で疑われたxずれは実PDFで再現せず、rootのfresh原本crop再確認とも一致した。

最終監査では、`appearance-correction-visual-review.json` とgolden manifestのapprovalが完全一致し、目視対象がnormal/grid各37枚の正しい集合であることを確認した。全128入力と全78成果物を実ファイルから再hashし、golden入力集合とも一致した。通常37PNGのファイルhash・デコード画素hash・RGB/1190×1684を確認し、承認対象previewと一致した。目視時に使ったfresh原本37枚とそのmanifest hashも一致した。

さらに最終normal/grid PDF両方へ原本外観検査を再実行し、全カテゴリの件数・最大差・error0がbundle記録と完全一致した。各版3,345内容項目、baseline21,204字、baseline最大差0.043418884pt、等号335字の最大差0.000061035ptを確認した。全74画像の個別目視自体はrootが実施し、reviewerはその記録と実ファイルの同一性を監査した。新bundleの受入に必要な証拠はそろっており、current切替はrootが行う。reviewerは最終golden・成果物・currentを変更していない。

検査器の独立性に関するAPP-T01は原本PDFから直接比較する回帰試験で解消した。Quality担当のAPP-Q01/Q02/Q03については、unsupported AST・relation転記不一致・cell line/style数不一致をfail-closedにする変更と負例を確認し、同担当の解消報告とも一致する。罫線のPDF primitiveやantialiasingによる画素差まで完全同一を要求するものではなく、記録した原本寸法・字形・基線・意味内容を確認する再現試験である。工学的な数値の再計算やソルバーの正当性は対象外である。

---

## 旧受入レビューの履歴（外観修正再開前）

以下は旧bundle `20261017T005753Z-7952a1f3f915474c8a478f77d40cf9da` に対する当時の結果であり、現在の修正版の判定ではない。

## Review Scope

承認計画 `plans/cantilever-pages-01-37.md`、実行記録、改善一覧、`.claude/logs/cantilever-review-scope.json` の非空スコープ168ファイルと差分を基準とした。重点確認対象は次のとおり。

- `tests/fixtures/cantilever_p01_37/verify.py`、全37 expected、転記用 source_evidence、manifest/図metadata、builder/render。
- `tests/integration/test_cantilever_p01_37.py`、`tests/unit/test_cantilever_fixture.py`、通常37頁goldenの試験・manifest。
- 新しい Text 回転、QuarterTurn、Table の境界線幅について、手計算期待値・入力境界・実PDFを確認する unit/integration と製品変更。
- rootの全件試験ログとcoverage JSON。coverageは製品 `gridlayoutpdf` の行カバレッジであり、fixture検査器自体のカバレッジではない。

Coverage: **98.80149812734082%（2638 / 2670行）**。根拠は `.claude/logs/cantilever-final-coverage.json`。JSON更新時刻は全製品Pythonファイルの更新時刻より新しい。gather_diffのcoverage=nullはカスタム保存先を探索しないためであり、未測定値を推定したものではない。

## Findings

未解決の指摘なし。

### 解消した指摘・確認

1. **[Low / 解消] 原本との文字割当検証を正式試験に残す。** 当初の `test_independent_oracle_accounts_for_every_source_character` はexpected内のitem文字とinventoryの整合性のみを比較していた。期待値そのものの編集誤りに対し、原本から直接確かめる回帰試験がない点を指摘した。reviewerが独立probeで原本37頁を再抽出し、21,232非空白文字のinventoryと全3,345 itemへの一意割当を確認した後、rootが `tests/integration/test_cantilever_p01_37.py:74` の37ケースとして正式追加した。頁番号は文字列 `13-n` として確認した上で除外し、図はレビュー済み16cropの領域だけを除外する。※印は別に個数を照合する。各itemの文字集合一致に加え、原本glyphが二重利用も取り残しもなく一度だけ割り当たることを検査する。追加後の対象37件をreviewerも再実行し合格した。

2. **[Medium / Security Reviewer起票・解消確認] 最適化実行でassert検証が無効になる。** `verify.py:8` で `__debug__` を明示確認し、`-O` / `-OO` / `PYTHONOPTIMIZE=1` の起動をimport時に拒否する変更を確認した。3方式のsubprocessと通常起動の欠落頁拒否を再実行して合格。通常版の受入条件を緩和する変更はない。この指摘はSecurity reportと重複計上しない。

## 検出能力の確認

- 全37頁の通常/grid両版を実際に描画・再抽出し、各3,345項目、114算式、124ケース、63箇所の `#######`、40表、16図の契約を検査する。文字はページ全文の存在確認だけでなく、部品・セルごとの順序、回数、方向、サイズ、添字の基線位置を照合する。
- 値/符号の変更、欠落/重複、セル交換、見出し順序、等号/結果/単位アンカー、結合を分断する罫線、疎な表への余分な罫線、グループ線の不足に、実PDFへ到達する負例がある。
- 37頁の数だけでなく、同数での頁交換、38頁化、異なる原本頁IDの子部品、宣言済み部品の欠落を拒否する。あふれ試験は実原稿へ行を足し、`原本再現できず` を確認する。subsetは完成版として有効化できない。
- 許可画像についてSceneの正規化bytesとデコード画素、PDFのデコード画素・出現数・配置・原寸ptを別々に確認する。欠落/複製/拡大/移動/別頁画像/未知画素/全頁化/再エンコードの負例がある。文字を重ねた禁止表画像も拒否する。
- 保存失敗の試験はgrid描画、JSON、preview、独立検査、pointer切替に注入し、既存currentと既存版全ファイルhashの不変を確認する。保存手順の単体試験では内容検査とpreviewをstub化する一方、別の実描画統合試験とgolden試験が両者を実行するため、stubを再現成功の根拠とはしていない。
- 回転の手計算期待値は±90度、既存文字方向との合成、prefix/partの累積位置、全対応primitive、外枠/局所枠の超過、画像拒否を含む。実PDF試験は文字方向、10pt、tracking、後続水平文字への状態漏れを検査する。選択罫線は結合・再掲ヘッダー/分割・0幅・実線幅余裕・短い孤立線分を含む。
- golden試験は通常37枚を全画素比較し、失敗時の自動更新を持たない。reviewer probeで登録時の37PNG、74目視対象、78artifact hash、96source-input hashと独立目視記録の一致を確認した。grid版は内容・配置の実PDF検査と全74画像のroot目視記録に含まれる。

## Test Execution Results

reviewer自身の実行はすべて共通 `run_tests.py` 経由、exit 0。下表は重複を含む別実行であり、合算した件数を全体件数として報告しない。

| 対象 | 結果 | ログ |
|---|---|---|
| 原本全37頁の独立probe + golden登録の照合 | 38 passed / 1.07s | `.claude/logs/cantilever-review-source-probes.log` |
| QuarterTurn・選択罫線・PDF描画 | 124 passed / 3.02s | `.claude/logs/cantilever-review-product.log` |
| 最適化guard追加後の全文/負例と固定頁/保存処理 | 91 passed / 20.18s | `.claude/logs/cantilever-review-content-final.log` |
| 正式追加された原本37頁試験 + 最適化/通常subprocess | 41 passed / 1.57s | `.claude/logs/cantilever-review-followup.log` |
| 新bundle・目視記録・goldenの最終hash結び付け | 1 passed / 0.24s | `.claude/logs/cantilever-review-final-record.log` |
| root実行の修正後最終全体・実測coverage | 1508 passed / 75.96s、98.80149812734082% | `.claude/logs/cantilever-lead-accepted-all.log` と同coverage JSON |

`.claude/check.ps1` はreviewerも実行し、exit 0、`ok: true`、`detect_stack` / `design-doc` / `state-doc` の3checkが合格した。これは文書/構成チェックであり、上記製品試験の代替ではない。既存DESIGNのArchitecture body警告は保持されている。

最終追確認: 新bundle `20261017T005753Z-7952a1f3f915474c8a478f77d40cf9da` に対し、`full37-visual-review.json` とgolden manifestのapprovalが一致し、74目視対象・78artifact hash・96golden source-input hashが同じbundleに結び付くことを独立probeで確認した。78成果物とbundleの全入力を実ファイルから再hashし合格。`regeneration-equivalence.json` は通常/gridのpage content streams不変、変更objectがInfoの65のみ、変更metadataが作成/更新日時であることを記録している。rootからはtrailerIDの差分も確認済みと報告された。PNGは変更せず、確認済み画素を保ったまま新PDF/verify入力hashへ記録を更新した。全件試験は重ねて実行せず、rootの最終1508件合格ログを読んで確認した。

## 限界と引継ぎ

- reviewerは全74画像を再度目視していない。rootの個別目視記録とhashを確認した。工程上の全頁目視はrootの責任として区別する。
- 元PDFとの全座標一致や工学的な値の正否は受入条件ではない。原本の値・不整合を保存する再現試験であり、ソルバーの正当性を保証するものではない。
- 修正後の最終全体ゲートと更新入力hashへのbundle再紐付けは完了し、本reviewでも証拠を確認した。current有効化はleadが実行する。reviewerはcurrent/goldenや製品コードを変更していない。
- 改善一覧の汎用padding・高さ診断・図の物理寸法API・添字style等は将来候補であり、今回の検証欠落や未解決のMedium指摘とは区別した。
