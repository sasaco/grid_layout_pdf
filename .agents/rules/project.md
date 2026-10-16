# GridLayoutPdf の作業ルール

## 言語と実行環境

ユーザーへの報告と設計文書は日本語を基本とする。作業環境は Windows / PowerShell。製品は Python 3.12以上のライブラリで、PDF描画にReportLab、画像処理にPillowを使う。開発環境は `uv sync --locked --extra dev` で同期する。

共有スキルの標準ライブラリだけを使う Python スクリプトは、リポジトリルートから `uv run --no-project python <script> ...` で実行する。スキルに残る `--project FrameWeb --locked --extra dev` は別プロジェクトの指定であり、このリポジトリのコマンドとして使用しない。製品の依存定義を追加した時点で、実際の manifest に合わせて実行方法を更新する。

製品テストは `uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests --expect pass --label <固有名>` を使う。TDDのRedは `--expect fail` とし、実際のテスト失敗を確認する。PowerShellでは `$env:PYTHONUTF8='1'` を指定する。並行coverageは `COVERAGE_FILE` を担当別パスへ分け、最終全体カバレッジはleadが単独実行して90%以上を確認する。配布物は `uv build` で作る。

## 文書の責務

- 目的、要件、設計、未決定事項は `.agents/docs/DESIGN.md` に記録する。内容更新には `.agents/skills/_shared/update_design.py` の型付き入力、プレビュー、適用を使う。
- Repository Identity と作業状態は `.agents/STATE.md` に置き、対応する型付きライターを使う。Main Agent と Progress Tracker を保持する。
- `PROGRESS.md` の履歴は `/checkpointing` で生成する。初期雛形はチェックポイント実施済みを意味しない。
- `AGENTS.md` は薄い起動案内に留める。

## 根拠と検証

実装、要件、検討案を区別する。`.agents/docs/research/` と `tests/output/` の既存 PDF は、内容を検証するまでは要件や成功したテストの証拠としない。既存ファイルとユーザーによる変更を保持する。

`.agents/check.ps1` はスタック検出・文書契約の検証用であり、製品の機能試験ではない。製品の検証方法は実装と依存定義に合わせて決める。
