# Quality review: cantilever-p01-37-improvements

2026-10-17、独立品質担当 `/root/quality_review`。最終判定: **PASS、未解決指摘0件**。初回のMedium 1件・Low 1件は担当が修正し、品質担当の限定再レビューでクローズした。製品・fixture・テストは品質担当から編集していない。

## Review Scope

基準HEADは `3da8b7cb71803c463029c68e155798f377c62e07`。`.claude/logs/cantilever-improvements-review-scope.json` の全32 changed filesと対応patchを読み、承認計画とFR-014/015へ照合した。レビュー開始後の `docs/validation.md` と実行記録の文書更新も確認した。

中心対象はInsets・CellLines・行高診断・Image物理寸法・Script明示offset・Table不可分モード、公開exports、fixture adapter、原本順序ゲートとprepare/activateである。対応する全変更unit/integrationテスト、API/設計文書、golden manifestの変更範囲も確認した。SourceCell/SourceScriptの保持、現行source表のsplit=True維持、別3頁の公開API実証は承認範囲と整合する。

## Findings

### Q01 [Medium / Closed] 原本領域のitem IDへの対応が検査対象expectedへ依存する

- 場所: `tests/fixtures/cantilever_p01_37/verify.py:432`。`selected = _inside(content, item["source_bbox"])` が検査対象のbboxを選択根拠にする。
- 再現: メモリ上のp1 expectedで `p01-dead-loads.r1.c3`（1530.0）と `p01-dead-loads.r2.c3`（160.0）の `source_bbox`、`text`、`direction`、`source_scripts` を一緒に交換。item IDは維持する。`verify_source_order((1,), records=[record])` は79項目を正常受理した。元ファイルを編集せず、CLI相談と品質担当でそれぞれ再現した。
- 影響: 読み順と一回被覆は領域内で成立しても、どの行・セルIDがどの原本値を表すかが入れ替わる。prepare/activateで同じ関数を再実行しても、この対応の独立性は補われない。
- 修正案: レビュー済みのitem ID→原本bbox対応を独立に固定し、expectedのbboxがその対応と一致してから原本glyphを選ぶ。ページ単位のID/bbox正規形の固定hash、または独立した固定mapを利用できる。本文を正解としてhashへ含めず、原本からの順序検査は維持する。payloadとbboxの連動交換を負例へ追加する。
- 修正と再レビュー: `_SOURCE_REGION_SHA256`へ基準HEADのレビュー済みID/bboxだけのページ別SHAを固定し、原本glyph選択前に `_check_source_regions` で照合する。品質担当が基準HEADの全37 JSONを別途git showして37頁3345項目のSHAを再計算し、不一致0を確認した。本文・方向・添字はhash対象外で原本直接検査を維持する。元の連動交換reproducerは `original region assignment` で拒否され、ID交換・bboxのみ変更・prepare/activateの負例とserialization順の正常例も合格。品質担当の共有runner再実行は **21 passed / 4.08秒**（`.claude/logs/cantilever-improvements-quality-q01-rereview.log`）。Q01はクローズした。

### Q02 [Low / Closed] 横方向の枠逸脱でも縦方向の不足量を返す

- 場所: `src/gridlayoutpdf/cell_content.py:135`〜139。両軸の枠逸脱を一つのifで検出した後、常に `needed=bounds.height` と内側の高さを返す。
- 再現: 公開MathNodeが `MathBox(10, 10, 3, (Text(30, 0, "A", style),), 2.5)` を返すと、横だけの逸脱に対して `needed=10.0, available=15.48` を返した。IPAex明朝10pt・標準A4で品質担当も再現した。
- 影響: レイアウト安全性は保たれるが、構造化された診断の軸が違い、呼出側が幅の不足を高さの問題と誤認する。
- 修正案: 横・縦の判定を分け、それぞれのcontent extentと容量に対応するneeded/availableを返す。横だけの逸脱のテストを追加する。
- 修正と再レビュー: 水平・垂直を分け、変位も含む必要extentと該当軸の内側容量を返す。左右・上下それぞれで不足量が正しくなる8回帰を確認。拒否条件・許容値・正常配置は不変。品質担当の共有runner再実行は **37 passed / 0.60秒**（`.claude/logs/cantilever-improvements-quality-q02-rereview.log`）。Q02はクローズした。

## 確認した契約

- Insetsは不変・有限非負値で、scalarと全辺同値Insetsが同じ計測になる。明示row_heightsは不足時に拡張せず拒否し、rowspanの増分と行高決定セルをmetadataへ保持する。
- CellLinesはpt配置・内側余白・最低高をまとめて一度だけ行へ丸め、空行を保持する。予約枠と行間の実ink接触を検査する。Q02は診断の問題で、はみ出しを受理する問題ではない。
- split=Falseはheader込み1partとし、prefixを重複させず、既存の線分統合を利用する。既定Trueの行群・反復headerを維持する。
- ImageはEXIF補正後の±0.5pixel密度区間を検査して指定ptを保持する。SourceFigureは実際に返されたsnapshotの寸法・pixels・bytesを再照合する。
- Scriptの既定経路は維持され、opt-in時だけrole・基底接触・上下clearanceを検査する。明示offsetは動かさず、許可されたauto側だけを調整し、新しいMathBox extentsを外側へ伝える。
- 原本順序は原本PDFの方向・幾何・基線から導き、expectedの文字列を並べ替えの根拠にはしていない。Q01修正後はitem IDと原本領域の結び付けも独立した固定SHAで検査する。

## Verification

- 品質担当の限定再実行: **119 passed / 1.54秒**。共有runnerのtargetは `test_cell_content.py`、`test_insets.py`、`test_table_rules.py`。ログは `.claude/logs/cantilever-improvements-quality-focused.log`。coverageは再測定・上書きしていない。
- 初回レビュー時のlead全体ログを実読: **1925 passed / 135.39秒**。coverage JSONの実数 **2940 / 2975 = 98.82352941176471%** をPythonで確認した。これはQ01/Q02修正前の全体証拠であり、修正後の最終全体ゲートはrootが別途再実行する。
- 初回候補031210のgolden manifestは37ページ定義が基準HEADと一致し、129入力hashの不一致は0だった。74枚の個別目視はrootの記録に基づく。品質担当が再度74枚を目視したとは扱わない。Q01/Q02修正により入力hashが変わるため、この旧候補を最終成果物の証拠へ転用しない。
- 品質担当の `.claude/check.ps1`: exit 0、`ok=true`、detect_stack/design-doc/state-docのexit_codeは全て0。文書・設定検査であり、機能試験ではない。ruffは収集時 `skipped` で、実行済みとはしない。

## Codex Consultations

read-onlyで複雑な契約と組合せを照会した。wrapperは `ok=true`、exit_code 0、write_access=false、timed_out=false、duration_sec=511.881。応答は `.claude/logs/codex/20261017T031949Z-cantilever-improvements-quality-final.md`。Q01/Q02を返し、他のMedium以上はなしとした。品質担当は両方を別の読み取り専用reproducerで再現し、実装位置と影響を確認した。相談の自己申告だけで指摘を採用していない。

Q01/Q02の修正は品質担当が独立に検証した。追加のCLI相談は行っていない。修正後の全体検証・配布物・新bundleと目視記録の結び付け・有効化はrootの最終工程であり、この品質PASSだけで完了したとは扱わない。
