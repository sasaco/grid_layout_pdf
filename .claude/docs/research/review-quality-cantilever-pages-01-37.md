# 品質レビュー: 片持ち梁 p01〜37

2026-10-17 / reviewer: `review_quality` / 比較基準: `HEAD`（`72de7fa`）。外観修正版の品質再レビューはPASS。Medium 2件 / Low 2件の修正を独立確認し、未解決指摘は0件。初回PASSと修正版の検証証拠は分けて記録する。

## Appearance Correction Review — PASS

追加対象は `Table.row_heights`、`Text.shear_x`、`appearance.py`、`builder.py`、`font-profile.json`、`source-layout.json`、`verify_appearance.py`。typography担当のfreeze後の実装を確認した。新候補の全74画像・golden・全体試験はleadの別ゲートであり、本レビュー完了時は進行中。製品・fixture・テストに本担当からの変更はない。

- [Medium / APP-T01 / 解決] 固定sup/sub基線と意味run基線による直交方向の差（p09上付き+3.24/+2.52pt、p9〜14ラベル等）は、`appearance.py:165` のSourceScript相対yと `anchored_commands` のrun別baselineで修正。`verify_appearance.py:180` は原本native文字方向の直交射影を0.20ptで比較する。原本p09上付き4字の位置一致と、operand/supをy方向へ2pt動かした負例の拒否を本担当の対象試験で確認した。旧Red証拠は `.claude/logs/cantilever-perpendicular-deltas.json` と `cantilever-appearance-review-red.log`。
- [Low / APP-Q01 / 解決] 未対応MathNodeを空文字として捨てていた `_flatten_text` は `appearance.py:374` で型名を含むValueErrorを送出する。FractionのRHSと分割後に残るFractionの両負例が明示失敗することを確認した。現行37頁にFractionがないという影響範囲も変わらない。
- [Medium / APP-Q02 / 解決] relation anchorのtextが原稿A=BをAXBへ置換する問題は `appearance.py:419` で解消。切り出したAST pieceの非空白文字とtranscriptの一致を先に確認し、描画内容はAST pieceから取得する。metadataのXによる書換えはValueErrorとなり、意味Scriptは分割せず保持される。
- [Low / APP-Q03 / 解決] SourceCellのlines/styles列長を `appearance.py:204` でzip前に検証する。FIRST/SECONDの2行・style1件の負例がValueErrorとなり、黙示的な行欠落を防ぐことを確認した。

Table専用の `SourceTableInkFonts` は元registryのadvanceと実glyph inkを保持し、全font共通ascent/descentだけを実inkに限定する。`PageFrame` はtableの局所計測にだけadapterを渡し、ページ全体の `measure_block`、renderer、呼出し元registryには元の保守的boundsを残す。Tableの各辺とQuarterTurnの容量検査は実inkを含むboundsで引き続き行う。以前の一律0.85pt移動は撤去され、原本と接触する明示8セルだけ最大0.05ptの下方移動を許す。移動後も下辺の罫線余裕をTableが検査する。原本基線を保つ正常例、上下の実ink超過、0.05ptを超える補正の拒否、元registryのmetrics不変をunitで確認した。製品boundsの緩和はない。

本担当の共通wrapper実行は **28 passed / 2.01秒**（fixture unit25件、p09原本上付き基線1件、直交方向の変異2件）。証拠は `.claude/logs/quality-appearance-closure.log`。全suiteは重複実行していない。typographyの `full-candidate-checks.json` も直接読み、全37頁・内容3345項目、appearance error0、baseline21204字・最大差0.0434188843ptを確認した。これは個別candidateの証拠であり、leadの最終normal/grid bundle受入とは区別する。

独立oracleはsource-layoutのanchorを正解として読まず、原本PDFのnative文字位置と比較する。Identity-V括弧8字のみorigin定義の相違を対象ID/文字/方向で限定し、別の実ink正例8件・変位負例8件で確認する構成を読んだ。汎用の直交方向許容を拡大していない。

今回のread-only Codex補助は `.claude/logs/codex/20261017T021412Z-quality-review-cantilever-appearance.md`（exit 0、563.252秒）。全文を読み、APP-T01の確認とAPP-Q02/Q03の独立再現を行った。Table.row_heights / Text.shear_xに追加指摘なし。

lead依頼のp30〜32細罫も実PDFで確認。色は原本・出力とも黒RGB(0,0,0)、opacity=1。原本は0.12ptの塗り矩形、独立行群の出力境界は0.06ptの隣接2strokeで、合成した帯幅・中心は原本と一致する。p30の例は原本x=[120.120003,120.240005]、出力中心120.150002/120.209999各幅0.06pt。2倍描画で出力がやや濃いことは測定できるが、塗り矩形と隣接strokeのアンチエイリアス差と整合する。外枠内部で端点が重なるが外側への超過はなく、線幅・色の不一致としては扱わない。

完了時の `.claude/check.ps1` はexit 0 / `ok: true` / checks 3件、work-log契約検査はexit 0 / reviewer variant / 警告0件。共有checkの既存Architecture空本文警告のみ残る。以下は初回レビューの履歴。

## Review Scope

`.claude/logs/cantilever-review-scope.json` の変更168ファイル、`scope_empty: false` を確認した。品質担当は次の製品差分とそれを使用するfixtureを中心に、実装・既存契約・対象テストを直接読んだ。

- `src/gridlayoutpdf/scene.py`、`bounds.py`、`diagnostics.py`、`renderers/reportlab.py`、`__init__.py`: Textの方向検証、基線周りの境界、PDF座標への変換、描画状態の分離、既定API・診断JSONとの互換。
- `src/gridlayoutpdf/rotation.py`: ±90度の剛体変換、既存方向との合成、子の局所容量、prefixとpartの累積位置、外側グリッドへの予約高の切上げ、metadataの変換契約。
- `src/gridlayoutpdf/tables.py`: 原本行列境界に対応する線幅、0指定、結合セルの内部線抑止、分割・ヘッダー反復、実際の各辺の線幅による余裕検査、既定出力の維持。
- `tests/fixtures/cantilever_p01_37/builder.py`、`render.py`: 意味を持つ原稿から公開APIへの組立、固定頁ガード、図の原寸配置、原稿と独立期待値の分離、一式を検査してから有効化する処理。
- `tests/unit/test_rotation.py`、`test_table_rules.py`、`test_scene.py`、`test_bounds.py`、`tests/integration/test_pdf_renderer.py`、`test_table_pdf.py` とAPI・設計文書。

## Findings

None。修正を要する具体的な不具合・互換性の後退は見つからなかった。

回転前の子の予約幅・高さを交換し、描画命令は拡大縮小しない。回転metadataは子の局所座標と累積part位置を保持し、ページ平行移動を別に適用できる。Tableの明示規則は既定の行群・分割構造を保持する。独立行群の罫線継ぎ目の太さ・微小な隙間は既存契約であり、改善一覧IMP-007の将来候補として扱う。

## Codex Consultations

`codex-system` / `team-execute` に従い、完全な依頼を `.claude/logs/codex/prompt-quality-review-cantilever.md` に保存してread-only相談を行った。

初回はWindowsのmultiline引数欠落により先頭行しか渡らず、回答が目的の再入力要求だったためレビュー証拠として採用しなかった。完全な依頼ファイルを読む単一行launcherで再実行し、`.claude/logs/codex/20261017T005513Z-quality-review-cantilever-r2.md` の全文と実行ログを確認した。wrapperはexit 0、`write_access: false`、338.95秒。

再相談の指摘は0件。補助解析は回転bounds、4方向の実PDF文字方向、明示規則を従来線幅と同じ値にした場合の命令一致をin-memoryで確認した。変換式、prefix/parts位置、幅・高さの検証、span・反復ヘッダーの扱いは本担当の独立したコード読解とも一致する。CLIの成功終了だけを根拠に判定していない。

## Verification and Limits

leadの実行ログ `.claude/logs/cantilever-lead-full-final.log` を直接読み、1467 passed / 69.83秒を確認。`.claude/logs/cantilever-final-coverage.json` の実数は2638 / 2670行、98.80149812734082%。品質担当による全suiteの重複実行はしていない。

本担当の `.claude/check.ps1` はexit 0、`ok: true`、checks 3件。これはスタック・共有文書の検査であり、製品機能試験とは区別する。既存のArchitecture節の空本文警告は残る。

全37頁の逐字転記と独立oracle全体をこの品質レビューで再監査したわけではない。内容検証は専用検査・テスト担当、全74画像の最終目視はleadの記録を根拠とする。製品・fixture・goldenは変更していない。
