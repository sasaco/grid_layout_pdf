# 代表帳票の画像回帰

`representative/` の通常版5ページは、root が通常版・グリッド版を目視して
承認した標準帳票です。`tests/output/` の原本PDFを基準には使用しません。
承認の由来、PNGのSHA-256、デコード後の画素SHA-256、画像寸法、入力画像と
IPAex明朝のSHA-256、描画ライブラリのバージョンは `manifest.json` に保存します。

テストは公開APIで構成された `examples/representative_report.py` の
`write_report` を使って一時ディレクトリへ再生成し、RGB画素を完全一致で比較します。
PNG圧縮方式やPDF作成日時の一致は要求しません。描画条件は
PyMuPDF matrix `(1.5, 1.5)`、`alpha=False` です。

```powershell
$env:PYTHONUTF8 = '1'
$env:COVERAGE_FILE = '.agents/logs/coverage-visual-golden'
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests/visual/test_representative_golden.py --expect pass --label visual-golden-check
```

画素・寸法・モードの差分時は、pytest の一時ディレクトリ内の
`differences/<page>/actual.png` と `diff.png` に証拠を保存し、失敗メッセージに
両方のパスを表示します。ページ数の差分時も再生成した画像のディレクトリを表示します。
1画素だけを変えるメモリ上のコピーで検出器を検証し、異なるPNG圧縮でも同じ画素なら
一致することを確認しています。保存済みの基準画像をテスト中に変更しません。

## 意図した変更やバージョン更新時

基準の自動更新スイッチはありません。以下を手動で実施します。

1. 意図する依存バージョンをロックし、`uv sync --locked --extra dev` で環境を揃えます。
   バージョン差分による失敗を無視したり、比較精度を緩めたりしません。
2. 既存基準を保持したまま、新しい候補ディレクトリへ標準・長文の両方を出力します。

   ```powershell
   uv run --locked --extra dev python examples/representative_report.py --font tests/fixtures/fonts/ipaexm.ttf --output build/reports/visual-candidate/standard --variant standard --preview
   uv run --locked --extra dev python examples/representative_report.py --font tests/fixtures/fonts/ipaexm.ttf --output build/reports/visual-candidate/long --variant long --preview
   ```

3. 代表帳票の統合テストを実行し、候補の通常版・グリッド版の全ページを目視します。
   文字欠落、基線、縮小、等号・結果列、表ヘッダー、改ページ、はみ出しを確認します。
   差分が意図した変更か判断し、確認者・日付・対象画像のSHA-256を承認記録に残します。
4. 承認後だけ、標準の通常版 `representative-report-page-1.png` ～ `page-5.png` を
   `tests/visual/representative/` へコピーします。コピー前後のSHA-256が承認記録と
   一致することを確認します。標準のページ数自体を変更する場合は、テストの5ページ
   という受入条件も別途レビューします。グリッド版や長文版はここへコピーしません。
5. `manifest.json` の承認記録、各ファイルSHA-256、RGB画素SHA-256、寸法、
   フォント・入力画像SHA-256、ReportLab/PyMuPDF/Pillowの実バージョンを更新します。
   画素SHA-256は Pillowで開いた画像の `image.tobytes()` に対して計算します。
6. 上記画像回帰テストを固有のログ名で実行し、画像とmanifestの変更を一緒にレビューします。

承認画像と再生成画像が異なる場合、現在の実装に合わせて基準を置換するだけでは
解決としません。違いの原因と採用する体裁を確認してから承認し直します。
