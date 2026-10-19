## Execution: Grid Excel Output（方眼Excel出力）

計画: [grid-excel-output.md](grid-excel-output.md)。ブランチ `feature/grid-excel-output`（起点 `a8c5228`、計画の記録 `58c296b`）。2026-10-20 ユーザー承認「ok 新しいブランチでGO」。

### 担当とファイルの所有

| グループ | 担当 | 工程 | 主なファイル | 状態 |
|---|---|---|---|---|
| 0 | lead | Step 1 基準 | — | ✅ 完了 |
| 1 | fonts | Step 2（FR-024） | `fonts.py`・`fontfinder.py`・`styles.py`（書体の既定のみ）・同梱書体・全テスト/例/文書の `register` の書き換え・片持ち梁の書体の指定 | 実行中 |
| 1 | xlsx-core | Step 7（ADR-0001） | `renderers/xlsx/{_model,_package,_sheet,_styles,_drawing,_units}.py`・`tests/unit/test_xlsx_{package,drawing}.py` | 実行中 |
| 2 | size | Step 3（FR-023） | `styles.py`・`math.py`・文字サイズのテスト・片持ち梁の文字サイズ | 未着手 |
| 2 | borders | Step 4（FR-022・026） | `borders.py`・`tables.py`・`containers.py`・`blocks.py`（`Rule`）・`scene.py`・`renderers/reportlab.py`・表と線のテスト | 未着手 |
| 3 | tags | Step 5 | `scene.py`・`math.py`・`equations.py`・`tables.py`・`cell_content.py`・`figures.py`・`blocks.py`・`rotation.py`・`document.py`・`diagnostics.py` | 未着手 |
| 4 | grid-terms | Step 6（FR-025） | `equations.py`・`docs/api.md` の指針 | 未着手 |
| 5 | xlsx-map | Step 8（FR-021） | `renderers/xlsx/{__init__,_map,_numbers}.py`・`document.py`（`render_xlsx`） | 未着手 |
| 5 | cantilever | Step 9（FR-027） | `tests/fixtures/cantilever_p01_37/**`・片持ち梁のテスト | 未着手 |
| 6 | lead | Step 10 受入と文書 | 文書・PNG 正解・最終検証 | 未着手 |

### 基準（Step 1）

- 起点の状態: `main` は clean（`a8c5228`）。計画の記録を `58c296b` でコミット。
- 依存: uv 0.10.0。
- ✅ 全テスト（`--label baseline-grid-excel`）: 2151 passed in 141 s、カバレッジ 99.0%（`.claude/logs/baseline-grid-excel.log`）。

### 記録

（各担当が進捗・知見・設計判断を追記する）
