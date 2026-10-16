# GridLayoutPdf — Design

## 背景・目的 (Background & Purpose)

Python の自作 PDF 計算書ライブラリを設計する。A4.pdf の GridLayout に従って文字配置を調整し、計算書の書式と計算式の等号位置を統一する。

## スコープ (Scope)

今回の成果物は資料調査と実装計画。対象資料は `.agents/docs/research/A4.pdf` と `tests/output/*.pdf`。ライブラリ実装と既存 P7 アプリへの移行は後続作業。

## 機能要件 (Functional Requirements)

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| FR-001 | A4.pdf の GridLayout に基づく文字位置調整 | Must | ユーザー指定 |
| FR-002 | 複数行の計算式の等号位置を揃える | Must | ユーザー指定 |
| FR-003 | 余白・フォント・改ページを共通コンポーネントで扱う | Must | 会話で確認した目的 |

## 非機能要件 (Non-Functional Requirements)

| Category | Requirement | Metric / Target |
|---|---|---|
| 保守性 | 余白・フォント・改ページ処理を共通部品として再利用し、帳票ごとの重複定義を減らす。 | 定量的な評価基準は未設定。 |
| 責務の分離 | 構造計算と帳票のレイアウト・描画を分離する。 | `.agents/rules/project-scope.md` の方針。具体的な構成は設計時に定める。 |

## アーキテクチャ (Architecture)

### Agent Roles

| Agent | Role | Responsibilities |
|---|---|---|
| Codex | Main Agent | ユーザーとの作業調整、共有コンテキストの維持、依頼された作業の実行と検証。 |

## 技術選定 (Tech Stack & Rationale)

| Area | Technology | Rationale | Alternatives Considered |
|---|---|---|---|
| 帳票部品 | Pythonによる自作ライブラリ（設計段階） | 既存のKey DecisionsとFR-001〜003に基づき、A4グリッド、等号位置、共通レイアウトを扱う。 | 既存のKey Decisionsに記載。 |
| 描画バックエンド | 未選定 | 帳票部品を自作する決定と、描画など下位機能のライブラリ選定を区別する。 | 資料調査・実装計画で比較する。 |
| 共有スクリプトの実行 | uv run --no-project python | 初期化時点で製品のmanifestがなく、同コマンドで共有スクリプトを実行できた。 | FrameWeb指定のコマンドは、このリポジトリの構成に一致しない。 |
| 現在の作業環境 | Windows / PowerShell | ユーザーから提示された作業環境。製品の対応OSを決めるものではない。 | 製品の対応OSは未決定。 |

## 制約 (Constraints)

参照 PDF は読み取り専用で保持する。グリッド寸法は PDF から検証し、確認済み事実と提案値を区別する。

2026-10-16 の初期化時点で、製品コード、依存関係のmanifest、ロックファイル、製品の実行・テストコマンドは未作成。共有スキルに残る FrameWeb 等の別プロジェクト用の設定は、GridLayoutPdf の採用技術の証拠としない。

`.agents/check.ps1` はスタック検出とDESIGN・STATEの文書契約を検証する。製品の機能や参照PDFの再現性は、別途検証する。

## Key Decisions

| Decision | Rationale | Alternatives Considered | Date |
|---|---|---|---|
| Custom Python component library | ユーザーが自作を選択し、A4 グリッドへの文字配置調整を独自性として指定した。 | ReportLab Platypus, ReportBro, borb, fpdf2, WeasyPrint を調査済み。描画など下位機能のライブラリ利用は未決定。 | 2026-10-16 |

## TODO / Open Questions

- GridLayout の正確な寸法、文字基線、余白を資料で確認する。
- 描画バックエンド、初期 API、検証条件は計画内で提案する。

- 実装開始時に、対応OS・Pythonバージョン、依存定義と製品の検証コマンドを整える。
