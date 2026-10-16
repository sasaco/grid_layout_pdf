# GridLayoutPdf の作業ルール

## 言語と実行環境

ユーザーへの報告と設計文書は日本語を基本とする。現在の作業環境は Windows / PowerShell。製品は Python による計算書の共通化を目的としており、採用ライブラリ、対応 Python バージョン、製品の実行・テストコマンドは未決定。

共有スキルの標準ライブラリだけを使う Python スクリプトは、リポジトリルートから `uv run --no-project python <script> ...` で実行する。スキルに残る `--project FrameWeb --locked --extra dev` は別プロジェクトの指定であり、このリポジトリのコマンドとして使用しない。製品の依存定義を追加した時点で、実際の manifest に合わせて実行方法を更新する。

## 文書の責務

- 目的、要件、設計、未決定事項は `.agents/docs/DESIGN.md` に記録する。内容更新には `.agents/skills/_shared/update_design.py` の型付き入力、プレビュー、適用を使う。
- Repository Identity と作業状態は `.agents/STATE.md` に置き、対応する型付きライターを使う。Main Agent と Progress Tracker を保持する。
- `PROGRESS.md` の履歴は `/checkpointing` で生成する。初期雛形はチェックポイント実施済みを意味しない。
- `AGENTS.md` は薄い起動案内に留める。

## 根拠と検証

実装、要件、検討案を区別する。`.agents/docs/research/` と `tests/output/` の既存 PDF は、内容を検証するまでは要件や成功したテストの証拠としない。既存ファイルとユーザーによる変更を保持する。

`.agents/check.ps1` はスタック検出・文書契約の検証用であり、製品の機能試験ではない。製品の検証方法は実装と依存定義に合わせて決める。
