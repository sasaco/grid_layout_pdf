# 片持ち梁 p01–37 セキュリティ・データ保全レビュー

2026-10-17、team-execute Phase 2 の独立レビュー。初回の168ファイルに続き、ユーザー指摘による書体・インデント・等号・表行高の外観修正を再レビューした。製品・fixture・テストは変更していない。

## 外観修正の再レビュー結果

未解決のSecurity指摘は0件（Critical/High/Medium/Lowすべて0）。これは以下の実装・データ保全範囲の結果であり、rootによる新74画像の目視・golden更新・最終全体ゲートの代わりにはならない。候補は `20261017T021112Z-ab279022e1dd42fc89f885990c6faa02`、レビュー時点で旧current/goldenを維持している。

- `Table.row_heights` は元行数と一致する正の整数tupleに固定し、bool/非数/無限/巨大非有限値を拒否。セル内容・padding・rowspanの合計高と境界線clearanceを検査し、不足時に縮小や行高拡張で回避しない。
- `Text.shear_x` は有限数に限り、boundsとReportLabが同じshear→rotation行列を使う。QuarterTurnでもshearを保ち、rendererの全命令境界検査・一時ファイル方式を維持している。
- `appearance.py` の意味run・Script・SourceCell・PageFrameは公開native命令を構成する。意味runの文字数/連続offset、空白復元時の本文一致、元原稿と配置対象のID対応を確認。元PDFを実行時に読み込んで本文・表を画像へ置換する経路はない。native文字の最終完全性は独立content oracleで検査する。
- MS明朝/MSゴシックは利用者PCのTTC face 0をhash照合して登録。font profile、source layout、新コード、双方の実書体ファイルをbundle入力hashへ含める。`--font` は任意の代替を自動承認する機構ではなく、最終の原本直接比較が書体相違を拒否する。
- `verify_appearance.py` は原本hashを検査し、独立expectedの意味領域を使い、実PDFの埋込TrueType name tableからfamilyを確認。原本だけはhash固定の参照としてBaseFont fallbackを許す。出力のTTFでname tableを解釈できなければ処理が停止する。新parserはPythonのbytes/struct処理で、実行コードや外部プロセスを起動しない。
- writerは新外観検査をprepareとactivateの双方で実行。入力/成果物hash確認、全37頁・全74preview、旧versionの保持、currentを最後に原子的に置換する契約を維持する。内容oracleを通らずに新外観チェックだけで有効化する経路はない。

独立実行結果:

- `test_text_shear.py`、`test_table_row_heights.py`、`test_cantilever_appearance_builder.py`、`test_cantilever_source_appearance.py`、`test_cantilever_fixture.py` をwrapper経由で実行し **157 passed in 10.67s**、exit 0、ok=true。`.agents/logs/cantilever-security-appearance.log`。今回のcoverageは**未測定**、旧版のcoverageを新差分の値とは扱わない。
- IPAex明朝を明示代替としてp01のprepare_bundleを独立実行。`原本の外観不一致: 997 differences` のValueErrorで停止し、currentが作られていないことを確認。隔離した一時出力だけを使用し、原本・候補・旧currentは変更していない。
- `python -O` で `verify_appearance.py` を直接ロードするprobeも `verify.py:10` のRuntimeErrorで停止。SEC-001の修正は新検証経路でも有効。
- 自身の `.agents/check.ps1` は exit 0、ok=true、detect_stack/design-doc/state-docの3checksがすべてexit 0。

## 対象と根拠

- 公開入力: `scene.py` の Text.quarter_turns、`rotation.py` の QuarterTurn、`tables.py` の境界線幅、bounds と ReportLab 描画境界。型・有限値・容量・不正primitiveの拒否、描画前検証を確認。
- 素材: fixture `builder.py` の SourceFigure と image_id解決、`verify.py` のscene/PDF画像検査、`assets/extract_figures.py`。解決済みパスの配下制約、元bytes・正規化bytes・復号画素・寸法・出現数・配置の検査を確認。図の生成は固定した16領域に限定され、再現writerから抽出器を呼ばない。
- 保存: `render.py` の生成、全体hash、検査、目視記録、version確定、current置換と解決。旧versionを上書きせずpointerを最後に切り替えること、subset拒否、入力/成果物変更拒否、activation時の再照合、path traversal拒否を確認。
- 負例: `tests/unit/test_cantilever_fixture.py` のgrid/JSON/preview/検査/pointer失敗時の旧current・旧成果物保全、未確認/変更済みbundleの拒否を確認。統合の画像・内容異常系と目視golden契約も確認した。
- 変更した実行Pythonにshell実行、動的コード評価、ネットワーク送信や資格情報の追加は見当たらない。`pyproject.toml` と `uv.lock` に差分はない。別途の依存脆弱性調査は実施していない。

## 指摘

### SEC-001 [Medium・解消済み] 最適化起動で独立検査が無効になる

- 場所: `tests/fixtures/cantilever_p01_37/verify.py:191`、同ファイルの画像・内容検査の `assert` 全般。呼出元は `render.py` の `prepare_bundle` / `activate_bundle`。
- 問題: `verify.py` はpytest専用の検査ではなく、完成bundleの生成・有効化でも実行される。しかし検査条件を `assert` で表しているため、Pythonの `-O` または `PYTHONOPTIMIZE=1` によって除去される。内容不一致を検査合格と扱う可能性があり、検査を失敗時停止する契約に反する。
- 再現: importlibで `verify.py` を読み、`verify_scene_images([], source_pages=(1,), manifest={'figures': []})` を呼んだ。通常起動は `AssertionError: scene image page count`、exit 1。同じ呼出を `uv run --locked --extra dev python -O -X utf8 -c ...` で実行すると戻り値0、exit 0。ファイルは変更していない。
- 修正案: 最小対応として `verify.py` のロード時に明示的な `if not __debug__: raise RuntimeError(...)` を置き、最適化実行を拒否する。または検査を最適化で消えない明示例外へ変更する。`-O` を付けた独立subprocessで拒否を確認する回帰テストを追加する。
- 修正と再レビュー: `verify.py:9` の `if not __debug__` による明示的RuntimeErrorを確認。最適化起動は依存importや検査処理に入る前に拒否する。初回と同じimportlibの `python -O` probeを独立再実行し、今度はmoduleロード時のRuntimeError・exit 1を確認した。
- 回帰テスト: `-O`、`-OO`、`PYTHONOPTIMIZE=1` の独立subprocess拒否と通常起動のmissing-page拒否を確認。integrationファイル全体を自身でwrapper経由再実行し、**104 passed in 17.06s**、exit 0、`ok: true`（`.agents/logs/cantilever-security-rereview.log`）。原本再抽出・項目割当の追加試験も含む。
- 状態: **解消済み。残るMedium以上のSecurity指摘は0件。** 製品API・描画には変更を加えず、検証fixtureに限定した修正として妥当。

## 検証と制限

自身で `.agents/check.ps1` を実行し exit 0、`ok: true`、checksは `detect_stack` / `design-doc` / `state-doc` の3件ともexit 0。これは製品テストではない。既存DESIGNのアーキテクチャ節が空というwarningは本変更によるものではない。

rootの修正前全体結果1467 passed・行coverage 2638/2670（98.801498%）は参照したが、自身で全体テストは繰り返していない。自身の追加実行は最適化比較probeと修正後integration104件。全74画像の再目視、全原稿の再転記確認、侵害済みローカルOSや同時悪意あるファイル差替えへの防御はこのレビューの範囲外。
