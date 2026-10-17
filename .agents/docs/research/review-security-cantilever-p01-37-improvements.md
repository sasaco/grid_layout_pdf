# Security Review: Cantilever p01–37 improvements

2026-10-17、独立担当 `/root/security_review`。初回レビューはPASSだったが、後続の品質レビューで領域対応の独立性不足（Medium Q01）と診断値の誤り（Low Q02）が見つかった。両修正の限定再レビューは **PASS**、未解決指摘は0件。初回記録と修正後の証拠を以下で区別する。

## Review Scope

基準HEADは `3da8b7cb71803c463029c68e155798f377c62e07`。`.agents/logs/cantilever-improvements-review-scope.json` の `changed_files` 全32ファイルと、同時点の `.agents/logs/review-diff-cantilever-p01-37-improvements.patch` を対象とした。実装担当から独立し、製品・テスト・期待値は変更していない。

- 製品6ファイル: `src/gridlayoutpdf/{__init__,cell_content,figures,math,styles,tables}.py`。公開exports、数値入力、配置境界、画像snapshot、データの不変性を確認。
- fixture4ファイル: `tests/fixtures/cantilever_p01_37/{README.md,builder.py,render.py,verify.py}`。原本順序の独立性、許可図の出典、hash、prepare/activateを確認。
- integration5ファイル: `tests/integration/test_{cantilever_improvements,cantilever_p01_37,equation_layout,figure_pdf,table_pdf}.py`。
- unit7ファイル: `tests/unit/test_{cantilever_fixture,cantilever_source_order,cell_content,images,insets,math,table_rules}.py`。負例が実際に拒否経路へ到達することと、既存検査の維持を確認。
- 文書8ファイル: `.agents/STATE.md`、`.agents/docs/DESIGN.md`、`.agents/docs/plans/cantilever-p01-37-improvements{,-execution}.md`、`.agents/docs/research/cantilever-p01-37-improvements.md`、`README.md`、`docs/{api,architecture}.md`。
- 検証記録2ファイル: `coverage.json`、`tests/visual/cantilever_p01_37/manifest.json`。coverageの集計とgoldenの入力・目視記録の更新範囲を確認。

## Findings

初回の検出指摘はNone。ただし、expectedのpayloadとsource_bboxを同時交換するQ01を初回レビューでは検出できなかった。後続レビューの発見と修正後の確認は末尾に記録する。

## 確認した安全性

1. `verify_source_order` は固定SHA-256で同定した原本PDFを直接読む。本文glyphの方向と幾何学的基線から読み順を導き、expectedの文字列・添字役割を並べ替えの根拠にしていない。文字inventory、marker数、許可図・ページ番号の除外、全glyphの一回被覆、item IDの一意性を維持している。同じ文字集合の桁交換、符号移動、回転方向、添字role/index/text/重複を拒否する。
2. 原本検査は通常の `verify_pdf` に加え、`prepare_bundle` の配置・staging作成より前、`activate_bundle` の有効化より前にも実行する。入力hashが変更後の期待値と一致していても、誤った原本順序を拒否する負例があり、旧currentとstagingを保持する。既存の最適化Pythonのimport拒否、成果物hash照合、入力hash照合、完全37頁制限、原子的なpointer切替を弱めていない。
3. `SourceFigure` は既存のpath・原本出典・素材hash確認を保持したうえで、公開Imageが実際に返したRasterImageの座標、物理寸法、snapshot寸法・pixel hash・正規化bytes hashを再確認する。検査後にファイルが差し替わる場合も、測定で得た誤画像を受理しない。
4. `Image` のpt寸法とグリッド寸法は各ペアを必須とし、非有限値・bool・非正数・枠不足を拒否する。比率はEXIF補正後の各軸±0.5pixelの共通密度区間で検査し、受理した寸法を補正しない。元のPNG/JPEG・単一frame・デコード検査とsnapshot/alpha経路を共用する。
5. Insets、CellLines、Scriptの追加数値は既存の有限値検査へ接続されている。負の余白、非正の行間・offset、不正なscaleや対応する添字のないoffsetを拒否する。CellLinesは子の申告寸法だけでなく実commandsの予約枠も確認し、行同士のink接触を拒否する。Scriptはopt-in時に役割・基底接触・上下間隔を検査し、明示offsetを黙って修正しない。
6. Tableは明示row_heights不足を拒否し、新split=Falseも1partの既存収容契約を使う。診断metadataの追加が表示値や実測高の変更経路になっていない。原本・expected・source-layout・書体・依存定義・lockはこの差分で変更されていない。新たなネットワーク送信、実行文字列評価、コマンド起動、認証情報や製品runtime依存の追加はない。

## Verification

独立した対象試験を共有runnerで実行した。

```powershell
$env:PYTHONUTF8='1'
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests/unit/test_cantilever_source_order.py --target tests/unit/test_cantilever_fixture.py --target tests/unit/test_images.py --target tests/unit/test_insets.py --target tests/unit/test_math.py --expect pass --label cantilever-improvements-security-review
```

- **290 passed / 15.64秒**。ログ: `.agents/logs/cantilever-improvements-security-review.log`。最終全体coverageファイルは上書きしていない。
- leadの `.agents/logs/cantilever-improvements-final.log` と `cantilever-improvements-final-coverage.json` を確認。全体 **1925 passed / 135.39秒**、製品行 **2940 / 2975 = 98.82352941176471%**。この全体実行はleadの証拠であり、上記の独立対象試験と区別する。
- reviewer自身の `.agents/check.ps1` はexit 0、`ok=true`、detect_stack/design-doc/state-docすべてexit 0。これは文書・設定検査であり製品機能検証ではない。
- golden manifestの変更は新入力pinと新bundleの目視記録に限定され、37枚のgolden PNG/pixel hashは維持されている。74画像の個別目視はleadが実施した記録を確認し、reviewer自身が実施したものとは扱わない。

この判定はレビュー時点の差分に対するものであり、新bundleの有効化完了を意味しない。有効化と最終pointer/hash監査はleadの最終工程に残る。

## Q01 / Q02修正後の限定再レビュー

2026-10-17、source-validation担当のコード安定通知後にread-onlyで実施。対象は `verify.py` の領域pin、`test_cantilever_source_order.py` の変異負例、`cell_content.py` の逸脱軸別診断と `test_cell_content.py` の回帰ケース。初回の1925件・coverageは修正前の証拠として保持し、今回の全体受入結果として流用しない。

- **Medium Q01 — 解消**。原本を直接読むだけでは、可変expectedのID→source_bbox対応まで独立にならない。2セルのtext/direction/source_scriptsとbboxを同時交換すれば初回のゲートを通過できた。修正では、受入基準commit `3da8b7cb71803c463029c68e155798f377c62e07` の全37頁について、IDと4座標だけを正規化してページ別SHA-256へ固定した。候補recordのglyph選択より先に照合し、本文・方向・添字の正しさは引き続き原本glyphから検査する。
- reviewer自身が `git show` で基準commitのexpectedを読み、別スクリプトで正規化とSHAを再計算した。**37頁・3345組、pin一致37/37、現在expectedの内容不変37/37**。候補expectedからpinを作り直す処理は検証経路にない。
- payload+bboxの同時交換、ID交換、選択glyphが変わらない0.0001ptのbbox改変を拒否する。record/cellの列挙順と座標のint/float表現だけの変更は受理する。prepareはlayout・stagingより前、activateは候補hashを改変後の値へ整合させても出版処理より前に拒否し、旧currentを保持する。
- **Low Q02 — 解消**。CellLinesは横/縦の逸脱を分け、当該軸の余白除外後の容量をavailable、変位を含む必要域をneededへ設定する。上下左右と四辺余白の有無を回帰ケースで確認した。拒否条件・計測・描画座標は変更していない。
- 独立shared runner: **57 passed / 3.73秒**、exit 0。`tests/unit/test_cantilever_source_order.py` と `tests/unit/test_cell_content.py`、label `cantilever-improvements-security-recheck`。ログ `.agents/logs/cantilever-improvements-security-recheck.log`。全体coverageを上書きしていない。
- source担当のRed記録は実テスト5件失敗、Greenは20件合格。追加4ファイルの担当回帰183件合格も確認報告を受領。自身の再check.ps1はexit 0、ok=true。
- 再レビュー対象のSHA-256: `verify.py` = `f02aa41310d68aa7c4744f7e972a96d7102c7ac1898d3c7ace271465d8c3d61d`、`cell_content.py` = `15e8acdbaac30714030847e0850abf00231b6a1f8165d39a7b13aef831eec32a`。

031210の旧stagingは有効化しない。修正後の全体試験・新wheel・新bundle再生成・目視・有効化はleadが別途実施する。今回の限定PASSは、それらが完了したという意味ではない。
