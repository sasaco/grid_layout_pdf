# GridLayoutPdf — Agent Bootstrap

このリポジトリでの作業は、次の共有コンテキストを読み込んで開始する。

- `.agents/rules/`：プロジェクトの作業ルール。
- `.agents/STATE.md`：担当エージェント、Repository Identity、進行中の作業。
- `PROGRESS.md`：`/checkpointing` が管理する進捗履歴。
- `.agents/docs/DESIGN.md`：目的、要件、設計、未決定事項。

読み込み順の取得：

```powershell
uv run --no-project python .agents/skills/context-loader/load_context.py
```

共有設定の検証：

```powershell
& .agents/check.ps1
```

このファイルには起動時の案内だけを置き、詳細な設計や進捗は上記の文書で管理する。
