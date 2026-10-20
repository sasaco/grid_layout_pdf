## Execution: Grid Excel Output（方眼Excel出力）

計画: [grid-excel-output.md](grid-excel-output.md)。ブランチ `feature/grid-excel-output`（起点 `a8c5228`、計画の記録 `58c296b`）。2026-10-20 ユーザー承認「ok 新しいブランチでGO」。

### 担当とファイルの所有

| グループ | 担当 | 工程 | 主なファイル | 状態 |
|---|---|---|---|---|
| 0 | lead | Step 1 基準 | — | ✅ 完了 |
| 1 | fonts | Step 2（FR-024） | `fonts.py`・`fontfinder.py`・`styles.py`（書体の既定のみ）・同梱書体・全テスト/例/文書の `register` の書き換え・片持ち梁の書体の指定 | ✅ 完了（commit 待ち） |
| 1 | xlsx-core | Step 7（ADR-0001） | `renderers/xlsx/{__init__,_model,_package,_sheet,_styles,_drawing,_units,_xml}.py`・`tests/unit/test_xlsx_{package,model,units,cells,sheet,drawing}.py`・`tests/integration/test_xlsx_excel_core.py`・`scripts/xlsx_probe/{measure_print_pitch.py,print_pitch.json}`（計画の `test_xlsx_excel.py` は Step 10 で ScenePage からの検査を担う） | ✅ 完了 |
| 2 | size | Step 3（FR-023） | `styles.py`・`math.py`・文字サイズのテスト・片持ち梁の文字サイズ | ✅ 完了（p30〜35 と p36 の9セルは Step 9 へ保留） |
| 2 | borders | Step 4（FR-022・026） | `borders.py`・`tables.py`・`containers.py`・`blocks.py`（`Rule`）・`layout.py`（端の命令）・`document.py`・表と線のテスト・片持ち梁の表の線 | ✅ 完了（commit 待ち） |
| 3 | tags | Step 5 | `scene.py`・`math.py`・`equations.py`・`tables.py`・`cell_content.py`・`figures.py`・`blocks.py`・`rotation.py`・`document.py`・`diagnostics.py`・`semantics.py`（新設） | ✅ 完了（commit 待ち） |
| 4 | grid-terms | Step 6（FR-025） | `equations.py`・`docs/api.md` の指針・`examples/representative_report.py`（grid 版）・`tests/unit/test_equation_grid_terms.py` | ✅ 完了（ImplementationLoop 7 ラウンドで MEDIUM 以上 0、commit 待ち。Step 6 の3項目めは Step 8 の完成待ち） |
| 5 | xlsx-map | Step 8（FR-021） | `renderers/xlsx/{__init__,_map,_numbers}.py`・`document.py`（`render_xlsx`） | ✅ 完了（commit 待ち。ImplementationLoop 6 ラウンドで MEDIUM 以上 0。比較の修正 C1〜C4、A3 のフッターの修正 F1〜F2 で MEDIUM 以上 0。A3 のフッターの件に限り `_units.py` も編集） |
| 5 | cantilever | Step 9（FR-027） | `tests/fixtures/cantilever_p01_37/**`・片持ち梁のテスト | 進行中（37ページの作り直し・項の列・strict・回転表の行の条件（lead の判断 (a)）まで済み。レビューのラウンド5中） |
| 6 | lead | Step 10 受入と文書 | 文書・PNG 正解・最終検証 | 未着手 |

### 基準（Step 1）

- 起点の状態: `main` は clean（`a8c5228`）。計画の記録を `58c296b` でコミット。
- 依存: uv 0.10.0。
- ✅ 全テスト（`--label baseline-grid-excel`）: 2151 passed in 141 s、カバレッジ 99.0%（`.claude/logs/baseline-grid-excel.log`）。

### 記録

（各担当が進捗・知見・設計判断を追記する）

#### fonts（Step 2）

担当 fonts（サブエージェント）。2026-10-20。

**進捗**

- ✅ Red: `tests/unit/test_fontfinder.py`（新設）と `tests/unit/test_fonts.py`（書替え）を先に書き、`fontfinder.py` を骨組みだけ置いた状態で `--label fonts-red` が 56 failed / 6 passed（本物の失敗。骨組みなしでは収集エラーで理由違いだったため骨組みを置いた）。
- ✅ Green: `fontfinder.py`・`fonts.py`・同梱書体・既定の書体名で `--label fonts-green` 62 passed。
- ✅ テスト・例・文書の `register` を書体名の指定へ書換え（テスト 28 ファイルは機械的に、残りは手で）。片持ち梁は `MS Mincho`／`MS Gothic` を名前で引く。
- ✅ 全テスト `--label fonts-final`: 2419 passed、1 failed（`tests/visual/test_cantilever_p01_37_golden.py`。失敗は `source_inputs` の hash 不一致 `tests/fixtures/cantilever_p01_37/render.py` で想定どおり）。代表例の PNG 正解（`test_representative_golden.py`）は合格。
- ✅ 片持ち梁の画素: hash の検査だけを外した一時スクリプトで37ページを再生成し、承認済み PNG と全37ページ画素一致（差分0）を確かめた（`renderers/xlsx/` は並行作業中で生成中に hash が変わるため、その確認でだけ除外）。
- ✅ `uv build -o <scratch>`: wheel と sdist の両方に `gridlayoutpdf/font_data/` の `ipaexm.ttf`・`ipaexg.ttf`・`IPA_Font_License_Agreement_v1.0.txt`・`Readme_ipaexm00401.txt`・`Readme_ipaexg00401.txt`・`manifest.json` が入る。新しい仮想環境（Python 3.12）に wheel を入れ、`python -I` で `IPAex明朝`・`IPAexGothic` が site-packages の同梱書体へ、`MS Mincho` が `C:\Windows\Fonts\msmincho.ttc` face 0 へ解決することを確かめた。

**IPAexゴシックの取得（ユーザー承認済み）**

- `https://moji.or.jp/wp-content/ipafont/IPAexfont/ipaexg00401.zip` を空のスクラッチのディレクトリへ取得し、展開せずに Python の `zipfile` で `ipaexg00401/ipaexg.ttf` と `Readme_ipaexg00401.txt` だけを読み出した。
- archive sha256 `4ab6fee94bf6f94b3eeb31be2b73c559f738dc6b336d722d5301b1f3f592f850`（4,166,255 bytes）、`ipaexg.ttf` sha256 `3b9955a5e437ffb24c41548e79296fa724822da21ee75dc1b94f6ccdb8f400dd`（6,099,900 bytes）。同梱の IPA ライセンス文書の sha256 は IPAex明朝の配布物と同じ `4c84dd52…7e54`。配布元の公式 hash は配布ページに載っていないため、取得時の値を `src/gridlayoutpdf/font_data/manifest.json` に固定した（無改変・名称保持。IPA フォントライセンス 2条・3条）。

**設計判断**

- データ用ディレクトリ名は `src/gridlayoutpdf/font_data/`。`src/gridlayoutpdf/fonts/` にするとモジュール `fonts.py` とパッケージ名がぶつかるため。
- 書体名の一致は完全一致（NFC 正規化のみ。大文字小文字・空白・全角半角は区別）。nameID 1・16（ファミリー名）と 4（フルネーム）、Windows platform（3）の Unicode 符号化（0・1・10）、言語 0x409・0x411 だけを読む。
- 同じ名前が複数ある場合: 探す順（同梱 → `%WINDIR%\Fonts` → `%LOCALAPPDATA%\Microsoft\Windows\Fonts`）で最初に一致したフォルダを使う。そのフォルダの中ではフルネームの一致をファミリー名の一致より優先し、同じ段階で別の書体（ファイルと書体番号の組）が2つ以上一致すれば曖昧として `FontError`（候補を列挙）。例: 同じファミリー名の標準・太字はフルネームで決める。
- 書体フォルダの読めない・壊れたファイルは飛ばし、見つからない時の `FontError` に飛ばした数を書く（`.ttf`・`.ttc`・`.otf`・`.otc` だけを見る。CFF の `.otf` は名前で見つかっても読み込み時に `Unsupported font format` の `FontError`）。
- フォルダの索引はファイル名・大きさ・更新時刻の組で持ち、変わったら作り直す（書体を足した後の再検索で見つかる）。
- 同梱の書体は読み込み時に manifest の SHA-256 と照合し、違えば `FontError`。
- `FontRegistry` は `resolve(name)`・`measure`・`normalize_text` を残し、名前ごとに解決した `FontFace` を保つ。字形の外接箱はファイルの SHA-256 を含む PDF 名をキーに共有する（同じ bytes なら同じ箱）。`FontFace` に `family`（英語の typographic family → family → full name の順）を足した（末尾、既定 `""`）。
- `fonts` の省略: `Document(fonts=None)`・`render_pdf(pages, path, fonts=None, ...)`・`layout_trace(pages, fonts=None)`・`command_bounds(command, fonts=None)` は `fonts.default_fonts()`（初回に作る共有の `FontRegistry`）を使う。既存の位置引数の呼出しはそのまま。`LayoutContext.fonts`・`wrap_text`・`fit_tracking`・`MathNode.measure` は内部・低水準の入口として必須のまま（`wrap_text` 等は fonts が位置引数の途中にあり、省略可能にすると位置引数の呼出しが壊れるため）。
- 公開名（`__all__`）は増やさない。`default_fonts` と `fontfinder` はモジュールから使える（公開 API を最小に保つため）。
- 例: `representative_report.py` の `--font` は書体名（既定 `IPAex明朝`、見つからなければ `parser.error` で終了コード 2）。`build_report(image_path, *, font=...)`・`write_report(output, *, font=...)` に変えた。部品の実証例（`*_proof.py`）の `--font` は廃止し、既定の書体に固定。
- 片持ち梁: `font-profile.json` の別名 `body`→`MS Mincho`、`heading`→`MS Gothic`（3,247 か所と 108 か所）、`fonts` の表は書体名をキーに `file`・`face_index`・`sha256` を持つ。`fixture_fonts()` は名前で解決したファイルの名前・face・sha256 を照合。文書の `ReportStyle` は `builder.SOURCE_STYLE`（本文・見出しとも MS Mincho、見出し 12 pt。以前の `ReportStyle()` が `body` 別名で MS Mincho だった挙動を保つ）。`render.py --font`（ファイルの差し替え）は廃止。
- 代表例の PNG 正解の検査（`tests/visual/test_representative_golden.py`）は、例の `DEFAULT_FONT` が manifest の書体と同じ SHA-256 のファイルへ解決することを確かめてから描く形にした（PNG と承認記録は変えていない）。

**Tips**

- この環境の Bash ツールのヒアドキュメントでは `\\` が `\` に潰れる（`b"\\x00"` が NUL バイトになった）。バックスラッシュを含むコードはヒアドキュメントで書かず、Write ツールでスクリプトを書いて実行する。
- 作業ツリーは CRLF（`core.autocrlf=true`）。`Path.read_text`/`write_text` で置換すると改行の不一致で一致しないことがある。bytes で読み、改行を合わせて置換する。
- テストで Windows の書体フォルダを差し替えるには `WINDIR`・`LOCALAPPDATA` を一時ディレクトリへ向け、`fontfinder._is_windows` を差し替える。名前を変えた書体は `tests/unit/_sfnt.py`（name テーブルを作り直して sfnt を組み直す）で作る。

**レビュー反映 (2026-10-20, ラウンド 1)**

レビュアー3体（silent-failure-hunter、python-reviewer＋type-design、計画整合＋PDF）。集約: CRITICAL 0 / HIGH 2 / MEDIUM 10 / LOW 約25（重複は高い方へ統合）。

- ✅ H: 同梱の書体が壊れている・消えている・名前が違うと、Windows の同名の書体へ黙って切り替わっていた → 同梱は manifest だけから索引を作り、ファイルの欠け・読めない・manifest の `family`/`family_ja` を持たない時は `FontError`（再インストールを促す）。
- ✅ H: `font_data/*.txt` が `core.autocrlf` で commit 時に改行を変えられ、manifest の SHA-256 と合わなくなる → ルートに `.gitattributes`（`src/gridlayoutpdf/font_data/*.ttf binary`、`*.txt -text`）。`git hash-object` のフィルタありとなしが一致することを確かめた。
- ✅ M: 索引が古い（大きさ・時刻を保った差し替え）と別の名前の書体を返す → 読み込んだ bytes の name テーブルで要求した名前を確かめ、違えば索引を捨てて `FontError`。索引の鍵に inode も足した。
- ✅ M: manifest の形が崩れると `KeyError`/`TypeError` が漏れる → 形を検査して `FontError`。manifest は不変の tuple で持つ。
- ✅ M: `WINDIR` が無いと Windows の書体を探さず「他の OS」と案内する → `SystemRoot` へ代替、文言を分けた。相対パスの環境変数は使わない。
- ✅ M: `FontFace.family` が nameID 16 を優先し、太さ違いが区別されない → `family` は英語の nameID 1（Windows・Excel が使う名前）を優先。Step 8（xlsx-map）への申し送り: セルに書く書体名は要求した名前 `FontFace.name`（または nameID 1 の `family`）を使い、typographic family は使わない。
- ✅ M: 曖昧の規則で游明朝・游ゴシックがファミリー名で引けない／エラーに区別に使える名前が出ない → 段階を フルネーム(4)→ファミリー名(1)→typographic family(16) に分け、エラーに候補のフルネームを出す（`Yu Gothic` は標準・太字が nameID 1 を共有するので引き続き曖昧。フルネームで指定する）。DESIGN.md の Key Decisions に記録（`update_design.py`）。
- ✅ M: `FontLocation` の `bundled` と `expected_sha256` の対応が型で守られていない → `bundled` を `expected_sha256` から導く property にし、`__post_init__` で path・face_index・hash を検査。
- ✅ M: TTC の 1 番の書体の読込み・計測・PDF 埋め込みをどの OS でも縛るテストがない → 合成 TTC で face 0/1、`_f0`/`_f1`、幅の差 0.3125 pt、PDF の埋め込み名を確かめるテストを追加。
- ✅ M: 統合テストの skip が同梱書体の故障まで隠す → skip は MS の書体で「was not found」の時だけ。
- ✅ L（同ラウンドで対応）: `resolve` で名前を NFC 正規化／`resolve` を上書きした派生が読み込まれていない書体を返すと `KeyError` → `FontError`／TTC の一部の書体が壊れていても他の書体は使う／飛ばしたファイル名を文言に出す／`fontfinder.__all__`／`needs_ms_fonts` を `WINDIR` から作る／`FONT_SUFFIXES` をテストで使う／import の検査に陽性対照（resolve 後は検出する）／対になっていない surrogate の記録を飛ばすテスト／`_sfnt.build_collection` の checksum の注記／未使用の `FONT` 定数と import の削除／片持ち梁のテストは `builder.SOURCE_STYLE` を使う／fixture の `Document` は `fonts=None` を拒む／`tests/fixtures/fonts/manifest.json` の古い purpose／`render_pdf`・`layout_trace` に「組んだ時の registry を渡す」と注記／`docs/api.md` に規則の追記。
- 持ち越し（LOW、ユーザー判断）: CFF の `.otf` が先のフォルダで TrueType 版を隠す（エラーにはなる）／`default_fonts()` の共有状態をテストごとに戻す手段／`_load_face` が同じ書体を別名で引くたびにファイルを読み直す（性能のみ）／未使用の `Path` の import（22 ファイル）／README の最初の例を実行するテスト／片持ち梁 `render.py` の `source_inputs` が `font_data/` を含まない（今は MS の2書体だけなので影響なし。Step 9 で正解を作り直す時に検討）。
- 新しい見逃しパターン: 「同じ規則（読めないファイルは飛ばす）を、信頼の前提が違うフォルダ（同梱）にも当てはめる」と、改ざん検出が後段の分岐で迂回される。
- 検証: レビュー修正の回帰テストは修正と同時に書いたため、修正前の失敗は確かめていない（レビュアーが修正前の挙動を実行して再現済み）。`--label fonts-round1`: 2554 passed、1 failed（片持ち梁の PNG 正解の `source_inputs` の hash 不一致のみ）。

**レビュー反映 (2026-10-20, ラウンド 2)**

レビュアー1体（silent-failure-hunter＋python-reviewer、ラウンド 1 の修正の検証）。CRITICAL 0 / HIGH 0 / MEDIUM 1 / LOW 6。

- ✅ M: TTC の 1 書体が壊れていると、索引では残りの書体を使えるのに読み込み（名前の再確認）で全体が失敗した → `fontfinder.face_names_at(handle, face_index)` で要求した書体の名前だけを読む。失敗はパス・書体名・face を含む `FontError`。Red（`--label fonts-r2-red`、1 failed）を確かめてから修正。
- ✅ L: ジャンクション経由だと `forget(path.parent)` が索引の鍵と一致しない → `forget()` は全消去、`_load_face` は全消去する。
- ✅ L: `WINDIR`・`SystemRoot` が無い時の文言に、システムの書体フォルダを探さなかったことを書く。
- ✅ L: 統合テストの skip は「unreadable」を含む時は raise。
- ✅ L: 同梱の hash は索引の項目に持たせて渡す（`_bundled_hashes` を削除。ファイル名で引き直さない）。
- ✅ L: `forget` を `fontfinder.__all__` に追加。
- 持ち越し: なし（ラウンド 1 の持ち越しは変わらず）。
- 検証: `tests`（`test_xlsx_*` は別担当の作業中で収集エラーのため除外）2212 passed、1 failed（片持ち梁の PNG 正解の `source_inputs` の hash 不一致のみ）。

**レビュー反映 (2026-10-20, ラウンド 3)**

レビュアー1体（silent-failure-hunter＋python-reviewer、ラウンド 2 の修正の検証）。CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 3。

- ✅ L: 読み込み時の名前の再確認が失敗した分岐（パス・書体名・face を含む `FontError` に包む、索引の全消去）のテストを追加。
- ✅ L: `forget(directory)` の引数ありの形を廃止し、`forget()` は全消去だけにした（鍵の書き方が違うと何も消えない形を残さない）。
- 持ち越し（LOW、対応不要と判断）: 統合テストの skip は、MS 書体が無い環境で別の壊れた書体があると skip でなく失敗になる（隠す方向ではなく厳しすぎる方向。日本語版 Windows では起きにくい）。

**完了（ImplementationLoop）**

- 全ラウンド数 3。指摘の推移: ラウンド 1 HIGH 2 / MEDIUM 10 → ラウンド 2 MEDIUM 1 → ラウンド 3 MEDIUM 0。
- 最終確認: `tests`（`test_xlsx_*` を除く）2213 passed、1 failed（片持ち梁の PNG 正解の `source_inputs` の hash 不一致のみ）。片持ち梁の37ページは hash の検査を外した確認で画素一致（差分0）を再確認。`--label fonts-final`（`tests` 全体）は 2613 passed、13 failed で、内訳は上の1件と xlsx-core が作業中の `tests/unit/test_xlsx_drawing.py`・`test_xlsx_units.py` の12件（この担当の変更とは無関係）。
- 片持ち梁の PNG 正解（`tests/visual/cantilever_p01_37/manifest.json`）の作り直しは最終工程で lead が行う。`source_inputs` が変わったのは `render.py`・`builder.py`・`font-profile.json`・`pyproject.toml`・`src/gridlayoutpdf/` の bounds・diagnostics・document・fonts・renderers/reportlab・styles と新設の fontfinder（`uv.lock` は Step 1 の commit による）。
- commit の注意: `.gitattributes`（ルート新設）と `src/gridlayoutpdf/font_data/` は同じ commit に入れる（先に `font_data/*.txt` を入れると改行が正規化され manifest の SHA-256 と合わなくなる）。

#### xlsx-core（Step 7）

担当 xlsx-core（サブエージェント）。2026-10-20。新規ファイルだけを作り、既存ファイルは編集していない（この実行記録と計画書の Step 7 の ✅ を除く）。

**進捗（RED→GREEN の記録。ログは `.claude/logs/` の同名）**

- ✅ 1 最小のブック・同じバイト列・ZIP の固定（`xlsxcore-red-1` 7 failed → `xlsxcore-green-1` 7 passed）。
- ✅ 2 モデルの検査（シート名・上限・重複）と単位（`xlsxcore-red-2` → `xlsxcore-green-2`）。
- ✅ 3 セル: 文字列・数値・リッチテキスト・表示形式・寄せ方・文字の向き・塗り・結合・罫線13種・結合範囲の辺（`xlsxcore-red-3` 44 failed → `xlsxcore-green-3`）。
- ✅ 4 シート: 列幅・行高・改ページ・用紙・余白・拡大率・先頭ページ番号・ヘッダー/フッター・枠線・印刷範囲（`xlsxcore-red-4` 46 failed → `xlsxcore-green-4`）。
- ✅ 5 図形（DrawingML）: 線・破線・矢じり・自由形状・四角・角丸・楕円・菱形・テキストボックス・文字入り図形・グループ・画像（`xlsxcore-red-5` 66 failed → `xlsxcore-green-5`）。
- ✅ 6 印刷の拡大率のヘルパー（`xlsxcore-red-6` 9 failed → `xlsxcore-green-6`）。
- ✅ 7 表示形式の構造の検査・ヘッダーの書体名の `&`（`xlsxcore-red-7` 8 failed → `xlsxcore-green-7`）。
- ✅ レビュー反映 ラウンド1（`xlsxcore-red-r1` 74 failed → `xlsxcore-green-r1b` 399 passed）。
- ✅ レビュー反映 ラウンド2（`xlsxcore-green-r2`・`xlsxcore-green-r2b`、単体 433 passed）。このラウンドの HIGH 2件は修正を先に書いたため、回帰テストが修正前のコードで落ちることを別に確かめた（旧 `_xHHHH_` の逃がしは総当たりで 176 件失敗、同じ `CellRange` の2度渡しは旧コードで通る）。
- ✅ レビュー反映 ラウンド3（`xlsxcore-green-r3f`、単体 463 passed）。このラウンドの修正も多くはテストと同時に書いた（下のラウンド3の記録を参照）。
- ✅ レビュー反映 ラウンド4（`xlsxcore-green-r4b`、単体 477 passed）。
- ✅ レビュー反映 ラウンド5（`xlsxcore-green-r5b`、単体 491 passed）。
- ✅ レビュー反映 ラウンド6（`xlsxcore-green-r6b`、単体 501 passed）。
- ✅ レビュー反映 ラウンド7（`xlsxcore-green-r7c`、単体 506 passed）。
- ✅ レビュー反映 ラウンド8（単体 508 passed）。
- ✅ 最終確認: 単体（`xlsxcore-final-unit`）508 passed・`renderers/xlsx` の coverage 98%（閾値 90%）、Excel 実機（`xlsxcore-final-excel`）33 passed・2 skipped、約116秒（アクティブなプリンター DocuWorks Printer。skip は DocuWorks PDF の最悪条件の2件で、理由を表示する）。
- ✅ 印刷の倍率の実測の生データ: `scripts/xlsx_probe/measure_print_pitch.py` で測り、`scripts/xlsx_probe/print_pitch.json` に保存（3,240 件。プリンター DocuWorks Printer、2書体×11〜30 px の全整数×20〜100% の全整数）。このデータはラウンド4の版のスクリプトで測ったもので、ラウンド5以降のスクリプトの「紙の大きさのページは拡大 1 として扱う」は入っていない（記録の `page_enlargement` は 1.0001、倍率の差は 0.0001 以下で係数の余裕に影響しない）。DocuWorks PDF は 10〜400% の 29 段・4 幅（11・16・21・30 px）のみ測定（生データはラウンド3で上書きして消失、残っているのはレビュアーが確かめた最大値。オーケストレーターの判断でこのまま受け入れ）。

**モデルの API（Step 8 への引継ぎ。`src/gridlayoutpdf/renderers/xlsx/_model.py`）**

- 単位と座標: 行・列は 0 始まり。色は 0〜1 の RGB 3要素。長さは pt で2種類ある。セルと図形の位置・大きさはモデルの列幅・行高で測る pt（Excel の整数 px のセルへは、セルの中の割合のまま写す）。線の太さ・文字の大きさ・余白・内側の余白・角の半径・破線の長さは絶対の pt。図形の座標はシートの左上（A1 の左上）原点で、y は下向き。
- 全クラスは `frozen=True, slots=True` の dataclass で、生成時に検査して誤りは `ValueError`（自動で直さない。巨大な整数も `OverflowError` でなく `ValueError`）。並びは list か tuple で渡し tuple で保持する。set・dict は出力の順が決まらないので `ValueError`。
- `Workbook(sheets, default_font=Font("游ゴシック", 11))`: シート名の重複は Excel と同じく大文字小文字・全角半角を区別しない比較（NFKC＋casefold、`sheet_name_key(name)`）でエラー。シート名の規則は `validate_sheet_name(name)`（UTF-16 で 31 単位まで、`[]:*?/\` と制御文字は不可、先頭・末尾の `'` は不可、自動で直さない）。Step 8 は FR-021 の「名前・名前_2・名前_3…」を作る時に、この2つで重複と長さを確かめる。`default_font` は Excel の「標準」スタイルで列幅の単位（最大の数字の幅 MDW）を決めるため、実測した書体の標準・黒だけを受ける（`_units._MAX_DIGIT_WIDTH_PX`）。独自の表示形式はブック全体で 206 種まで。
- `Sheet(name, column_widths_pt, row_heights_pt, cells=(), merges=(), borders=(), row_breaks=(), page=PageSetup(), header=None, footer=None, drawings=(), show_gridlines=True)`。列 1〜16,384、行 1〜1,048,576。行高は 409 pt まで、列幅の 255 文字は既定の書体の数字の幅に依るので `Workbook` で検査し、`Sheet` は 100 万 px 未満（`PIXEL_LIMIT`）だけを検査する。半ピクセル（0.375 pt）未満と負の長さはエラー。印刷範囲は常にシートの全セル（`_xlnm.Print_Area`）。図形は外接箱がシートの中（端は 1e-6 pt の誤差まで可）でなければエラー。`width_pt`・`height_pt` はモデルの列幅・行高の合計（Excel の実寸ではない）。検査は結合の面積・セル・罫線の数に比例する（結合 3 万で1秒程度）。
- `CellValue(row, col, value, number_format=None, font=None, h_align="left", v_align="center", rotation=0, fill=None)`: `value` は `str`・数（float にする）・`RichText`・`None`（書式だけの空セル）。`font=None` はブックの既定の書体。`rotation` は反時計回りの度で 0・90（下から上へ読む）・270（上から下へ読む）。Excel の textRotation の 90・180 へはライブラリが写す。`h_align`・`v_align` は回しても紙面の向きのまま。`fill` はセルの背景色（指示の `color` をこの名前にした）。結合範囲の左上以外に値があればエラー。文字列の `_xHHHH_` と `\r` は書き出し時に逃がす（`_x005F_`・`_x000D_`）ので元の文字のまま読める。
- `RichText(runs)`、`Run(text, font=None, vert_align=None|"superscript"|"subscript")`。`text` は空でない（空の文字片は run にしない。セルの値の `""` は可）。`font=None` はセルの書体。上付き・下付きの run には記号と同じ大きさを渡す（Excel が自動で約2/3に縮める）。
- `Font(name, size, color=(0,0,0), bold=False, italic=False)`。`size` は 1〜409 pt の 0.5 pt 刻み。`name` は 31 文字まで、制御文字・空白だけは不可。
- シート名・書体名・表示形式に `_xHHHH_` の形があるとエラー（SpreadsheetML ではこれらも文字の符号として読まれうる。Excel の扱いは測っていないので、逃がさず拒否した）。
- `number_format`: 255 文字まで。引用符・角括弧の閉じ、`\`・`_`・`*` の後の文字、4区画まで、角括弧の中身（色・`Color1`〜・条件・`$`で始まる通貨と言語・経過時間 `h`/`m`/`s`・`DBNum`/`NatNum`）を検査する。その他の文法の誤りは Excel でしか分からない。
- `CellRange(first_row, first_col, last_row, last_col)`（2セル以上）。結合の重なりはエラー。
- `EdgeBorder(row, col, side, style, color=(0,0,0))`: 1つのセルの1辺。`style` は `BORDER_STYLES` の13種の名前。同じ物理的な辺（上のセルの bottom と下のセルの top など）を2度与えるとエラー。結合範囲の内側の辺はエラー。結合範囲の辺は `range_edges(cell_range, side, style, color)` で辺に沿う各セルの `EdgeBorder` を作る。
- `row_breaks`: 増加する行番号の並びで、その行の上で改ページ（1〜最終行、1,026 か所まで。1,026 は Excel の文書の上限で実測していない）。
- `PageSetup(paper="A4"|"A3", orientation="portrait"|"landscape", margins=Margins(...), scale=100, first_page_number=None, print_gridlines=False)`、`Margins(left, top, right, bottom, header, footer)`（pt。6つとも必須。`PageSetup.margins` の既定は `DEFAULT_MARGINS`＝Excel の「標準」の 50.4・54・50.4・54・21.6・21.6 pt）。`scale` は 10〜400、`first_page_number` は 1〜32,767（None は自動）。`paper_size_pt`・`printable_size_pt` を持つ。`paper_for_size(width_pt, height_pt, tolerance_pt=1.0)` がページの大きさから `(paper, orientation)` を返す（A4・A3 以外はエラー。許容差は 0〜10 pt）。
- `HeaderFooter(left=None, center=None, right=None)`、`HeaderSection(parts, font=None)`、`parts` は空でない文字列・`PageNumber()`（`&P`）・`SheetPageCount()`（`&N`。そのシートのページ数で、帳票全体の総数ではない。FR-021 の `{pages}` は数字の文字列で渡す）。文字列の `&` はここで `&&` にする。`font` の大きさは整数 pt、名前に `"`・`,`・`&` は不可、名前 `-`（Excel の既定の書体の意味）も不可。書式文字列は 255 文字まで。`code()` で Excel の書式文字列を返す。
- 図形の線・塗り・文字の欄はキーワードだけで渡す（scene の `Rectangle` の5番目は線の太さだが、ここで位置で渡すと角の半径になるのを防ぐ）。長さ0の線、幅か高さが0の箱、全点が同じ位置の自由形状、2点の閉じた自由形状はエラー。scene の `Point` は `(p.x, p.y)` に直して渡す。
- 図形（`*` の後はキーワードだけ。既定値は線の太さ 0.5 pt・色は黒 (0,0,0)・塗りなし・実線）: `Line(x1, y1, x2, y2, *, stroke_width_pt=0.5, color=(0,0,0), dash=(), start_arrow=None, end_arrow=None)`（`Arrowhead(kind, width, length)`、kind は triangle・stealth・diamond・oval・arrow、大きさは sm・med・lg。start は (x1, y1)）、`Polyline(points, *, closed=False, stroke_width_pt, color, fill=None, dash=(), stroke=True)`（塗りは閉じた形だけ）、`Rect(x, y, width, height, *, corner_radius_pt=0, stroke=True, stroke_width_pt, color, fill=None, text=None, dash=())`、`Ellipse(...)`・`Diamond(...)`（corner_radius なし）、`TextBox(x, y, width, height, text)`（枠・塗りなし）、`Picture(x, y, width, height, data, format)`（`format` は "png" か "jpeg" で必須。Pillow で読めない・形式が違う・途中で切れた data はエラー。JPEG はマーカーを先頭からたどり、各フレームが EOI まであることを確かめる（EOI の後のデータ、例えばスマートフォンの写真の後置データは、そのまま受けて保つ）。MPO 拡張の JPEG は JPEG で、全フレームを確かめる。scene の `RasterImage` は他の形式もあるので Step 8 で PNG にする）、`Group(children)`（入れ子可）。`dash` は scene と同じく pt の on/off の並びで `()` が実線（奇数個は PDF と同じく2回繰り返す）。線の太さは 1 EMU 以上 1,584 pt 以下、破線の長さは線の太さの 0.00001〜21,474 倍。線も塗りも文字もない四角・楕円・菱形はエラー。
- `TextFrame(paragraphs, *, font, h_align="left", v_align="top", rotation=0, insets_pt=(0,0,0,0), wrap=False)`: `paragraphs` は `Run` の並びの並び（空の並びは空行、run に改行・タブなどの制御文字は不可）。`rotation` は反時計回りの 0・90・180・270。寄せ方は文字の読む向きで決まる（90度では「上」が紙面の左）。`Font` の 0.5 pt 刻みは図形の文字にも掛かるので、図形の中の添字も記号と同じ大きさ＋`vert_align` で渡す（添字の添字は1段になる）。
- 書き出し（`_package.py`）: `write_workbook(workbook) -> bytes`、`save_workbook(workbook, path)`（全体を作ってから同じフォルダの一時ファイル経由で `os.replace`。POSIX では umask どおりの権限にする）。
- 単位（`_units.py`）: `excel_column_width_pt(pt)`・`excel_row_height_pt(pt)`（Excel が実際に使う pt）、`column_width_chars(pt, font)`、`pt_to_emu`（有限の数だけ。他は ValueError）、`page_heights_pt(row_heights_pt, row_breaks)`、`print_fit(sheet, default_font, *, maximum=100) -> PrintFit(scale, limited_by, column_factor, row_factor)`（全ページが1枚に収まる最大の整数%、それを決めたのが `"width"`・`"height"`・`"maximum"` のどれか、計算に使った段の係数。係数は実測の最大より 0.6% 以上大きい設計値。255 文字を超える列はエラー）、`fit_scale_percent(sheet, default_font, *, maximum=100)`（その `scale` だけ。`dataclasses.replace(sheet, page=replace(sheet.page, scale=...))` で使う）。`default_font` は必須で、そのシートを書くブックの `Workbook.default_font` を渡す。印刷を測った 游ゴシック 11 と ＭＳ 明朝 10.5（標準・黒）だけを受ける。20% でも収まらなければ `ValueError`。`maximum` は 20〜100（`MIN_FIT_SCALE`・`MAX_FIT_SCALE`。測った範囲）。測ったセルの大きさは `MEASURED_CELL_PIXELS`（11〜30 px）。図形の配置は `_drawing.SheetGeometry`（セルの境目から 1e-6 pt 以内の座標は次のセルの 0 として書く）。
- `renderers/xlsx/__init__.py` は説明文だけ（公開・再公開は Step 8）。名前が scene の `Line`・`Polyline`、geometry の `Rect`、figures の `TextBox` とぶつかるので、Step 8 では `from . import _model as xl` のようにモジュール名を付けて使うことを勧める。

**Step 8 以降で決めること（このモジュールでは決めない）**

- ヘッダー・フッターの書体の大きさは整数 pt しか Excel の書式で表せない。`PageDecoration` が 10.5 pt などの時にエラーにするか、大きさを書かずに記録するかは Step 8 で決める（DESIGN の未決定事項に入れることを勧める）。
- 印刷の拡大率と位置の比較（Step 10）: 100% なら Excel は 21 px の列を 16.08 pt、21 px の行を 15.48 pt で印刷し、A4.pdf のグリッドと同じ間隔になる（PDF 書出しで実測）。`print_fit` は安全側に、90% 以上で列を 1.04 倍・行を 1.0 倍して計算するので、100% にするには余白を次の式で決める（左・上はグリッドの原点）: 右の余白 ≤ 用紙の幅 − 左の余白 − Σ（Excel の列幅）× 1.04、下の余白 ≤ 用紙の高さ − 上の余白 − 1ページの Σ（Excel の行高）。値は 0.01 pt に切り捨てて書く。A4 縦 30 列×47 行（左 50.88・上 54.598）では右 ≤ 52.99 pt・下 ≤ 47.04 pt。A3 横 67 列×47 行では右 ≤ 42.21 pt・下 ≤ 47.04 pt（単体テストでこの値なら 100、0.01 pt 超えると 99）。統合テスト `a4-reference-grid-at-100` で右 50.6・下 47.0 の時に 100% で2ページに収まることを確認。A4.pdf の余白（右 61.72・下 59.842）は、右だけでも下だけでも 98% になる。100% 未満になる場合、Step 10 の位置の比較は拡大率で正規化するかを決める。
- 用紙は A4・A3 だけ（`paper_for_size`）。B4・Letter などを扱うかは DESIGN で決める。
- 方眼Excel の既定の書体: 100% で A4.pdf のグリッドの間隔（16.08×15.48 pt）で印刷されるのは、既定の書体が游ゴシック 11 の時だけ。ＭＳ 明朝 10.5 では 21 px のセルが 15.84×14.52 pt で印刷され、47 行で縦に約 45 pt（約2.9マス）ずれ、Step 10 の「縦半マス以内」を満たせない。Step 8 は既定の書体を游ゴシック 11 に固定するか、書体ごとの印刷のマスの大きさを扱う（DESIGN の未決定事項に入れることを勧める）。
- 印刷の原点はプリンターのドライバーで変わる（A4 の基準グリッドの最初の罫線は、余白から DocuWorks PDF で約 0.06 pt、DocuWorks Printer で 0.80 pt 内側。間隔は 47 行で 0.12 pt 以内の誤差で 16.08×15.48 pt）。Step 10 の位置の比較は原点の違いを考える。
- A4.pdf の余白では Excel の実機でも 100% で収まらない: Excel の A4 は 841.89 pt で A4.pdf（842 pt）より短く、47×15.48 = 727.56 pt が印刷できる高さ 727.45 pt を超える。実機で収まる下の余白は 59.73 pt 以下、`print_fit` では 47.04 pt 以下。
- 退化した図形（長さ0の線、幅0の四角、全点同じ位置）は scene では描けるが、モデルではエラー。飛ばして記録するかエラーにするかを Step 8 で決める。
- 隣り合う結合範囲の両方に `range_edges` で同じ辺を作ると「same edge」のエラーになる。表の罫線は、行の境目×列・行×列の境目の対応表から物理的な辺1つずつに `EdgeBorder` を作る。
- 寄せ方の基準と既定値の違い: `CellValue` の `h_align`・`v_align` は紙面の向き（既定の縦は center）、`TextFrame` は文字の読む向き（既定の縦は top）。回転した表と図で取り違えないよう Step 8 でテストを置く。

**Excel 16.0（このPC、96 DPI、既定のプリンター DocuWorks PDF）での実測**

- 修復の検出: `DisplayAlerts=False` で `Workbooks.Open` すると、修復が必要なブック（存在しない書式番号 `s="99"`、閉じていない XML、不正な表示形式 `0.0"`・`[Red`、独自の表示形式 207 種、32 文字の書体名）は例外になり開かない。修復して開くモード（`CorruptLoad=1`）は COM から呼ぶと正常なブックでも失敗したので使わない。シートに未知の要素（`<foo/>`）を入れたブックは黙って開いたため、開けることに加えて、読み戻した中身（セル・書式・結合・罫線と色・ページ設定・図形の種類と位置・グループの子の位置・線の太さと色と破線と矢じり・塗り・文字の書体と大きさと上付き下付き・寄せ方・余白）をモデルと比べる2段で確かめる。`%TEMP%` に修復ログ（`error*.xml`）は作られなかった。
- 上限: 独自の表示形式は 206 種まで開き 207 種で開かない（ja-JP。組込みの数に依るため言語版で変わる可能性がある）。書体名は 31 文字まで開き 32 文字で開かない。書体 1,100 種のブックは開いた（書体・セルの書式の数の上限は検査していない）。シート名のタブ・改行・U+2028 は開いたが、Excel の画面では入力できないのでモデルでエラーにする。
- 最大の数字の幅（MDW、px）: 游ゴシック 11 = 8、Yu Gothic 11 = 8、游ゴシック 10.5 = 8、游ゴシック 10 = 7、游明朝 11 = 8、ＭＳ 明朝 11 = 8、ＭＳ 明朝 10.5 = 7、ＭＳ ゴシック 11 = 8、ＭＳ ゴシック 10.5 = 7、ＭＳ Ｐゴシック 11 = 8、Calibri 11 = 7、Arial 10 = 7（幅 1・2・3・10・20 文字の列の `Range.Width`。統合テストで全書体の列幅 9 通りが計算どおりであることを確認）。列の幅は ECMA の式 `Truncate(((256*w + Truncate(128/MDW))/256)*MDW)` px どおり。既定の書体は Excel の日本語版の既定と同じ游ゴシック 11 にした。96 DPI 以外の画面、太字・斜体の既定の書体は未確認。
- 列幅: 指定の pt を最も近い整数 px に丸めた幅で表示（16.08 pt → 21 px = 15.75 pt、8.04 → 8.25、100 → 99.75）。行高: Excel はファイルの pt を整数 px に切り捨てて表示する（15.48 → 15.0、20.64 → 20.25、0.5 → 0 で行が消える）。このためライブラリは最も近い整数 px（半分は切り上げ）の pt を書き、表示と一致させる（15.48 → 15.75）。0.375 pt 未満はエラー。
- 図形の位置: 列幅・行高のピクセル丸めでずれないよう、座標をそのセルの中の割合のまま Excel の実際のセルへ写す（twoCellAnchor の from/to と EMU のオフセット、`xfrm` も同じ写し方、グループは子の座標系を親と同じにする）。21 px に丸めた列・行の中の図形とグループの子で、Excel の `Shape.Left/Top/Width/Height` が写した値と 0.05 pt 以内で一致することを確認（例: 半列の位置は 240 + 0.5×15.75 pt）。
- 罫線の種類 → Excel の (LineStyle, Weight): hair (1,1)、thin (1,2)、medium (1,-4138)、thick (1,4)、double (-4119,4)、dotted (-4118,2)、dashed (-4115,2)、dashDot (4,2)、dashDotDot (5,2)、mediumDashed (-4115,-4138)、mediumDashDot (4,-4138)、mediumDashDotDot (5,-4138)、slantDashDot (13,-4138)。
- 図形の線: `start_arrow`（headEnd）は `Line.BeginArrowheadStyle`、`end_arrow`（tailEnd）は `EndArrowheadStyle` に出る（oval = 6、triangle = 2）。実線は `DashStyle` = 1、custDash は 1 以外。
- 文字の向き: textRotation 90 は `Range.Orientation` = xlUpward(-4171)、PDF で下から上へ読む（反時計回り）。180 は xlDownward(-4170)、上から下へ読む。図形の `TextFrame` の 90 は `vert="vert270"`（Orientation 2 = Upward）、270 は `vert="vert"`（3 = Downward）、180 は `bodyPr rot="10800000"`（PDF で逆さ）。
- 上付き・下付き: Excel はセルのリッチテキストでも図形の文字でも、上付き・下付きの run を自動で約2/3に縮めて描く（10.5 pt → PDF で 7.08 pt）。7 pt を与えると 4.68 pt になる。
- ヘッダー・フッター: 書体付きの区画は `&大きさ&K色&"名前,太さ"本文` の順に書く（引用符で閉じる書体の指定で終わるので、数字や A〜F で始まる本文も色の符号に読まれない。PDF で「12AB計算書」を確認）。`&P-1`・`&P+1` は Excel がページ番号の足し引きとして印刷する（5 → 4、6）。`&P1` は「51」。`&N+2` では「+」が消えた。このため `PageNumber()`/`SheetPageCount()` の直後の文字が `+`/`-` で始まる時は、書体の指定（`&"-,Regular"` または区画の書体）を挟んで区切る（PDF で「4+1」を確認）。`&10.5` は 10 pt と文字「.5」になる（ヘッダーの大きさは整数だけ）。書体の太さは英語名 `Regular`・`Bold`・`Italic`・`Bold Italic` が日本語版でも効く（`&"Arial,Bold Italic"` が Arial-BoldItalicMT）。`&KRRGGBB` で色。
- シート名: 31 文字は UTF-16 の単位で数える（絵文字 15 個＋1 文字は可、16 個は不可）。重複として拒否: abc/ABC、A/Ａ、ア/ｱ、Ä/ä、ß/SS、①/1、ﬁ/fi、ｶﾞ/ガ、σ/ς、é/e＋結合文字。別名として可: ア/あ、İ/i、㌔/キロ、Ⅰ/I（NFKC は後ろ2つも重複とみなすので、ライブラリは厳しめにエラーにする）。`History` は COM では付けられた。
- 先頭ページ番号: COM で 0・負数・65535 も受けるが 32768 は「自動」(-4105) になった。範囲を 1〜32,767 にした。拡大率は 10〜400（9・401 は COM がエラー）。
- 印刷の寸法: Excel の PDF 書出し（`ExportAsFixedFormat`）では、列は画面の幅より広く、行は狭く（低い拡大率では少し広く）印刷され、その倍率は拡大率・セルの大きさ・プリンターのドライバーで変わる。
  - DocuWorks PDF（セッション開始時の既定のプリンター）: 10〜400% の 29 段・4 幅（11・16・21・30 px）のみ測定。生データはラウンド3で上書きして消失し、残っているのはラウンド2・3のレビュアーが JSON から再計算して確かめた最大値（`_units.DOCUWORKS_PDF_MAXIMA`）: 列は 90% 以上で 1.0284（150%）・55〜89% で 1.0430（11 px・60%）・20〜54% で 1.0673（11 px・30%）、行は 20% 以上で 0.9933 以下。10% の ＭＳ 明朝 10.5 は列 1.10〜1.16 倍・行 1.16〜1.23 倍と乱れた。PDF のページは 100/拡大率 倍に大きくなる。
  - DocuWorks Printer（ラウンド3以降の既定のプリンター）: 2書体×11〜30 px の全整数×20〜100% の全整数（`print_pitch.json`、3,240 件）。列の最大は 90〜100% で 1.0322（12 px・93%）・55〜89% で 1.0370（12 px・63%）・20〜54% で 1.0475（12 px・28%）、行の最大は 0.9931（12 px・98%）・0.9955（12 px・75%）・1.0158（12 px・21%）。PDF のページは紙の大きさのまま、中身が縮む。4 幅だけの測定（ラウンド3）より最大が大きかった（12 px が最悪）。
  - 例: 游ゴシック 11 の 21 px の列・行は 100% で 16.08・15.48 pt（1/600 inch の格子。両プリンターで同じ）。ＭＳ 明朝 10.5 では 15.84・14.52 pt。
  - `print_fit` の係数は両プリンターの最大より 0.6% 以上大きい: 列 1.04（90% 以上）・1.05（55〜89%）・1.08（20〜54%）、行 1.0（90% 以上）・1.01（55〜89%）・1.025（20〜54%）。単体テストが JSON と `DOCUWORKS_PDF_MAXIMA` から、この余裕と、20〜100% の全整数が両書体・11〜30 px の全幅で測られていることを確かめる。
  - 統合テスト（DocuWorks Printer で実行。測っていないプリンターでは xfail、`GRIDLAYOUTPDF_REQUIRE_EXCEL=1` なら失敗）で、各ページが1枚に収まり（右下近くの印がそのページにある）、5%（20〜54% の段は 10%）大きくするとページが増えることを確認: 各段の下限ぎりぎり（90・55・20%、21 px）、各段で列・行の倍率が最大だった条件ぎりぎり（`print_pitch.json` から実行時に求める。今は 12 px の列 93・63・28%、行 98・75・21%）、幅で決まる場合、高さで決まる場合、最大の 100% に達する場合、ＭＳ 明朝 10.5、A4 の基準グリッドを 100% にする余白。DocuWorks PDF の最悪条件（11 px で 60・30%）のケースは、アクティブなプリンターが DocuWorks PDF の時だけ意味があるので、それ以外では理由を付けて skip する（今の環境では skip。DocuWorks PDF での実機の確認はしていない）。11 px 未満・30 px 超のセル、他のプリンターのドライバーは未確認。
- `PageSetup.Pages.Count` と `HPageBreaks` の自動改ページは、同じ Excel で拡大率を変えても更新されず当てにならなかった。ページ数は PDF に書き出して数える。
- グループの高さが0（水平線だけのグループ）、0.01 pt の四角も Excel は開いた。

**設計判断**

- 書き出しは `_xml.py`（エスケープ・数の書式・要素の書き方・名前空間）を加えた7モジュール。要素の順は CT_Worksheet・CT_Stylesheet・DrawingML の並びに従う。styles（numFmts・fonts・fills・borders・cellXfs）と共有文字列・画像は重複をまとめ、出現順（シート順・行列順・図形順）で番号を付ける。組込みの表示形式（`General`・`0`・`0.00`・`#,##0`・`#,##0.00`・`0%`・`0.00%`・`0.00E+00`・`@`）は組込みの番号、他は 164 から。
- ZIP: 日時 1980-01-01 00:00:00、deflate レベル 6、`create_system=0`、`external_attr=0o600<<16`、部品の順は固定（[Content_Types].xml → _rels → workbook → workbook の rels → styles → sharedStrings → シート → シートの rels → drawing と drawing の rels → media）。同じ環境（同じ zlib）で同じバイト列（`PYTHONHASHSEED` を変えた別プロセスでも一致することをテスト）。別の zlib の版でのバイト一致は未確認。
- docProps と theme は書かない（Excel は開いた）。
- 共有文字列とヘッダー・フッターの文字（SpreadsheetML の ST_Xstring）は `_xHHHH_` を `_x005F_xHHHH_` に、`\r` を `_x000D_` にして書く。Excel で `_x0041_` と `a\r\nb` が元のまま読めることを確認。
- 図形の線は端を平ら（`cap="flat"`）・角を丸く（`a:round`）して、PDF の描き方（butt・round join）に合わせた。テキストの余白の既定は0、折り返しなし（`wrap="none"`）。
- 色の 0〜255 への変換は半分を切り上げる（`floor(x*255+0.5)`）。
- 一辺だけ・結合範囲の辺の一部だけに罫線を書いた場合の Excel の見え方は未確認（結合範囲の辺全体に書いた場合は確認済み）。

**レビュー反映 (2026-10-20, ラウンド 1)**

レビュアー5観点（python・silent-failure・type-design・layout・計画とテスト）。集約後 CRITICAL 0 / HIGH 5 / MEDIUM 約20 / LOW 約30。HIGH と MEDIUM はすべて直し、テストを足した。

- 解消（HIGH）: `_xHHHH_` の逃がし（セル・リッチテキスト・ヘッダー）。統合テストで図形の線・塗り・文字・グループの子・罫線の色・リッチテキストの書体を読み戻す。`fit_scale_percent` の係数を 90% 以上 1.03 に分け、A4 の基準グリッドを 100% にできる余白を引継ぎに記録。図形の範囲検査に 1e-6 pt の許容差。セルの文字の向きを図形と同じ反時計回りの度（0・90・270）に統一（欄名 `text_rotation` → `rotation`）。
- 解消（MEDIUM）: 巨大な整数の `OverflowError`。set・dict を拒否（出力の順の固定）。`\r` の保持。`fit_scale_percent(sheet)` に変えて検査済みの Sheet を受ける。結合・セル・罫線の検査を2乗から線形へ（結合 3 万で数分 → 1 秒未満）。型注釈（`tuple[Drawing, ...]` など）。Excel のプロセスを PID で追い、時間切れ・残った時は止めて失敗にする。全 MDW 書体の列幅と `&P` の後の「+1」を統合テストに追加。拡大率に5%以上の余裕がないことを確かめる。制御文字のシート名・書体名、32 文字の書体名、独自の表示形式 207 種、未知の角括弧の表示形式をエラーに。DrawingML の整数の範囲（線の太さ 0 EMU、破線の比、内側の余白）。画像を Pillow で読めるか確かめる。既定の書体は標準・黒だけ。文字のない透明な図形をエラーに。図形の run の改行・タブをエラーに。`PageCount` → `SheetPageCount`。`width_pt` → `stroke_width_pt`、`dash=None` → `()`（scene に合わせる）。セルの境目の座標を `(k, 0)` で書く。`paper_for_size` を追加。
- 解消（LOW の一部）: docstring の食い違い、POSIX の権限、置換の失敗時のテスト、部品の順の全体のテスト、名前空間の定数の重複。
- 持ち越し（LOW、対応不要と判断。降格はユーザー判断に委ねる）: 2^53 を超える整数の丸め、`-0.0` の符号、セルの改行に折り返しの指定がないこと、`SheetGeometry` の置き場所、`HeaderSection.code()` のモデル内の置き場所、`CellValue` などの名前、英語の書体名での MDW、極端に小さい図形が 0 EMU になること、`fsync` なし。
- 新たな見逃しパターン候補: 「Excel が黙って受けるが中身を変える」入力（`_xHHHH_`、`\r`）は openpyxl の読み戻しでは見つからない（openpyxl は共有文字列の `_xHHHH_` を解かない）。Excel 実機の読み戻しでしか確かめられない。

**レビュー反映 (2026-10-20, ラウンド 2)**

silent-failure のレビューは完了。python・type-design のレビューは API の利用制限で途中で止まった（ラウンド3で改めて行う）。layout と統合テストのレビュー結果はオーケストレーター経由で受け取った（MEDIUM 6件）。

- 解消（HIGH）: `_xHHHH_` の逃がしの穴（続いた形、CR の直前）。先読みの正規表現で `_` を1文字ずつ逃がし、総当たりの往復テストを追加。同じ `CellRange` のインスタンスを2度渡すと重なりの検査を抜けた（線形化の退行）。結合の番号で比べる。
- 解消（MEDIUM、silent-failure）: 統合テストに `&P` の後の「+1」と書体付きの区画の `&N` の後の「-2」を入れ、PDF で「3+1」「3-2」を確認。図形の文字の `_x0041_` が Excel でそのまま読めることを確認（DrawingML は逃がさない判断の裏付け）。シート名・書体名・表示形式の `_xHHHH_` はエラーに。
- 解消（MEDIUM、layout と統合テスト）: M1 係数を実測の最大より 0.6% 以上大きく（1.035・1.05・1.08）、実測の生データを JSON で保存し、記録の誤り（1.0391 → 1.0430）を直した。M2 `print_fit`／`fit_scale_percent` に既定の書体の引数を加え、測っていない書体はエラーに。ＭＳ 明朝 10.5 を実測と統合テストに追加。M3 各段の下限ぎりぎり・幅で決まる 55〜89%・高さで決まる場合を統合テストに加え、`PrintFit.limited_by` で何が拡大率を決めたかを確かめる。大きくする側は相対（`ceil(scale×1.05)`、20〜54% は 1.10）。M4 図形の位置の期待値を手で書いた式（240 + 割合×15.75 pt）にし、`TopLeftCell` で境目の図形が次のセルから始まることを確認。M5 `GRIDLAYOUTPDF_REQUIRE_EXCEL=1` なら Excel がない時に失敗にする（Excel のない環境での動作は実行していない）。M6 余白の一般式と A3 横の値、A4.pdf の余白で 98% を引継ぎに記載し、A3 横 67×47 の単体テストと A4 30×47 の統合テストを追加。
- 解消（LOW の一部）: `_run_excel` の PID の確認に EXCEL.EXE の名前を加え、`tasklist` の失敗と `taskkill` の失敗を区別、前の結果ファイルを消す。修復が要るブックが開けない理由を COM の文から確かめる。bytearray・memoryview を数の並びとして受けない。`page_heights_pt` の検査を Sheet にそろえる。図形の境目を補償付きの和（Neumaier）で作り、10 万行でも境目が `(k, 0)` になる。表示形式の角括弧の Color1〜56、条件の小数・指数、小文字の dbnum。MPO 形式の JPEG を受ける。Pillow の例外を絞った。
- 持ち越し（LOW）: layout と統合テストのラウンド2の LOW（L1〜L6）はオーケストレーター側の報告にあり、この担当は本文を受け取っていない（指示どおり記録だけ）。silent-failure L-3 の生成器の元の順は検査できない（docstring に記載）。IDAT の CRC が壊れた PNG を Pillow は受ける（Excel での見え方は未確認）。
- 新たな見逃しパターン候補: 1つずつのエスケープのテストは通っても、続いた形や後から挿入する符号との組合せで壊れる。逃がしは総当たりの往復テストで確かめる。性能のために同一性（`is`）で比べると、同じインスタンスの重複を見逃す。

**レビュー反映 (2026-10-20, ラウンド 3)**

レビュアー3観点（python と type-design、silent-failure、layout と統合テスト）。集約後 CRITICAL 0 / HIGH 1 / MEDIUM 約11 / LOW 約25。HIGH と MEDIUM はすべて直した。

- 解消（HIGH）: 印刷の倍率を測っていない拡大率があった。`print_fit` の最大を 100% にし、20〜100% の全整数を2書体×4幅で測り直した（`print_pitch.json`、656 件）。測り直しの途中で、既定のプリンターがセッション開始時の DocuWorks PDF から DocuWorks Printer に変わっていることに気づいた（ドライバーで PDF の書出し方と倍率が変わる）。この担当はラウンド1の調査で一度 Excel の `ActivePrinter` を Microsoft Print to PDF にした（Windows の既定のプリンターを変えることがある）が、今の既定はそれとも違い、変わった原因は分からない。システムの設定は戻さず、オーケストレーターに報告する。係数は両プリンターの最大を覆うようにし、行の係数を 20〜54% で 1.01 に上げた。
- 解消（MEDIUM）: `default_font` を必須に（省略で游ゴシックとみなして検査を抜けていた）。係数と JSON の突合せを単体テストに。書体付きのヘッダー区画の本文が `&K` の色に読まれうる順を直した。巨大な有限の float（1e308）の `OverflowError`。図形の線・塗り・文字の欄をキーワードだけに（scene と位置の意味が違う）。退化した図形・寄せ方の基準・画像の形式・隣り合う結合範囲の辺を Step 8 への引継ぎに追加。`maximum` が段の境にかかる場合のテスト。リッチテキストの run の逃がしを run ごとに確かめるテスト。游ゴシック 11 でだけ A4.pdf のグリッドの間隔で印刷されることを引継ぎと単体テストに。統合テストの下限ぎりぎりの場合を、各段の下限（90・55・21%）と、列の倍率が最大だった条件（11 px で 95・55・25%）に置き換えた。A4 の基準グリッドの罫線の位置を Excel の PDF で確かめる統合テストを追加。
- 解消（LOW）: `page_heights_pt` の検査を Sheet にそろえた。Pillow の `LOAD_TRUNCATED_IMAGES` でも切れた PNG を拒否（`verify()`）。`_run_excel` で PID 0 と `tasklist` の失敗を扱う。`GRIDLAYOUTPDF_REQUIRE_EXCEL` は 0・1 以外をエラーに。測定スクリプトで Excel の版・プリンターを記録し、時間切れでも Excel を止め、ページの拡大を割り戻す。ヘッダーの書体名 `-` を拒否。閉じた自由形状は3点以上、文字のない文字枠は文字なしと扱う。`paper_for_size` の許容差を 0〜10 pt に。`rotation` のエラー文。`_drawing` の名前空間と許容差の定数の重複。`_CONTROL` の正規表現を逃がした書き方に。テスト名と上の余白 54.598 をそろえた。
- 持ち越し（LOW）: 11 px 未満・30 px 超の列の印刷（docstring に「測っていない」と書いた）、他のプリンターのドライバー、`Literal` 型の導入、テストの `pytest.raises` の `match` の不足、3秒の時間判定のゆれ、`write_workbook` の型検査が一時ファイルの経路より先に落ちるテスト。
- このラウンドで RED を先に確かめていない修正: キーワード化・巨大な float・閉じた自由形状・許容差・ヘッダーの順などは修正と同時にテストを書いた。
- 新たな見逃しパターン候補: 実測に基づく係数は、測った条件（拡大率・プリンター）の外で根拠を失う。測った範囲を API の上限・下限にし、係数とデータの突合せをテストにする。Excel の COM で `ActivePrinter` を変える調査は、Windows の既定のプリンターを変えうるので避ける。

**レビュー反映 (2026-10-20, ラウンド 4)**

レビュアー2観点（silent-failure、python・type-design・layout）。集約後 CRITICAL 0 / HIGH 0 / MEDIUM 8 / LOW 約14。

- 解消（MEDIUM）: 破線の比がちょうど 0.5 で `d="0"` と書かれた（書き出す整数を作る `dash_value` を1つにし、その値を 1〜2^31−1 で検査。比は書いた EMU の線幅に対して計算）。1e305〜1e308 の列幅の `OverflowError`（ピクセル数を 100 万未満に制限）。`LOAD_TRUNCATED_IMAGES` のもとで切れた JPEG が通った（終わりの EOI を確かめる）。行の係数を段の境で確かめる統合テスト（95・57・20% の高さぎりぎり）と DocuWorks PDF の列の最悪条件（11 px で 60・30%）を追加し、統合テストの結果にアクティブなプリンターを残して、測っていないプリンターでは xfail に。測定スクリプトの後始末を EXCEL.EXE の確認つきにし、失敗を報告、既存のデータは `--force` なしで上書きしない。引継ぎの余白の上限を切り捨てで書き、上の余白を 54.598 にそろえ、その値で 100%・0.01 pt 超えで 99% になる単体テストを追加。docstring と記録の測った範囲を事実に合わせ、DocuWorks Printer で 11〜30 px の全幅を測り足した（その結果、12 px で列・行とも最大が更新され、係数を列 1.04、行 1.01・1.025 に上げた）。
- オーケストレーターの判断で受け入れ（M4）: DocuWorks PDF は 29 段・4 幅のみの測定のまま（全整数の再測定には Windows の既定のプリンターの変更が要るため行わない）。係数はその最大値と DocuWorks Printer の全整数の測定の最大値の両方を 0.6% 以上上回る。測定スクリプトと統合テストはプリンターを切り替えない（`ActivePrinter` を読むだけ）。
- 解消（LOW）: `print_fit` が色付きの既定の書体を拒否。`PrintFit` に `row_factor`。キーワードだけの欄のテストに `Ellipse`・`Diamond`、`TextFrame(rotation=90.0)`、`maximum=20` のテスト。統合テストの docstring のプリンター名。`_EDGE_TOLERANCE_PT` の別名を削除。空行の体裁。
- 持ち越し（LOW）: `Workbook` を受ける `print_fit` の版（Step 8 で必要なら）、単体テストで JSON の倍率を `printed_*_pt` から計算し直すこと、11 px 未満・30 px 超のセル、他のプリンターのドライバー。
- 新たな見逃しパターン候補: 実測の範囲を一部の幅（4 幅）で代表させると、測っていない幅（12 px）で最大を見逃す。測れる範囲は全部測る。

**レビュー反映 (2026-10-20, ラウンド 5)**

レビュアー2観点（silent-failure、python・type-design・layout）。集約後 CRITICAL 0 / HIGH 0 / MEDIUM 3（重複を除く）/ LOW 約10。

- 解消（MEDIUM）: 負の巨大な列幅・行高（-1.5e308 など）の `OverflowError`（半ピクセル未満の判定を先にし、上限は `PIXEL_LIMIT` 未満）。JPEG の終わりの確認が後置データのある正当な JPEG を拒否した（マーカーを先頭からたどる走査に変え、後置データは受ける。EXIF のサムネイルの EOI や MPO の1枚目の EOI で切れたものは拒否）。統合テストの「最悪条件」がラウンド4の全幅の測定（12 px が最悪）とずれていた（JSON から実行時に求める形にし、データを測り直してもずれない）。DocuWorks PDF の最悪条件のケースは、そのプリンターでなければ理由を付けて skip。
- 解消（LOW）: `GRIDLAYOUTPDF_REQUIRE_EXCEL=1` で測っていないプリンターなら失敗にし、プリンター名を `record_property` で残す。罫線の位置のテストも測っていないプリンターでは xfail。破線の境界のテストを明示的に（比 0.5 は `d="1"`、上限超えはエラー）。測定スクリプト: `Add-Type` を Excel の起動の前へ、出力先のフォルダを先に確かめる、一時ファイルから置き換える、別のプリンターで測ったデータは上書きしない、紙の大きさのページは拡大 1 として扱う。`MAX_PIXELS` → `PIXEL_LIMIT` とエラー文。`_units` の型注釈（`TYPE_CHECKING`）。統合テストに JPEG の図形の読み戻し。JSON のプリンター名の単体テスト。体裁。
- 持ち越し（LOW）: `PrintFit` が NamedTuple（位置での展開ができるので、欄を足すと呼び出し側が壊れうる。Step 8 で dataclass にするか判断）。
- このラウンドも修正とテストを同時に書いた（JPEG の後置データのテストは旧コードで失敗することをレビュアーが再現済み）。

**レビュー反映 (2026-10-20, ラウンド 6)**

レビュアー2観点（silent-failure、python・type-design・layout）。集約後 CRITICAL 0 / HIGH 0 / MEDIUM 2 / LOW 約18。

- 解消（MEDIUM）: JSON から作る最悪条件が、`print_fit` の返せない拡大率（100%、下の段の上端など）になりうる（各段で倍率の大きい順に試し、`print_fit` がその拡大率と幅・高さを返すケースだけを使う。返せる記録がない段・空の段はエラー。合成した記録で確かめる単体テストを追加）。区切りの間に余分なバイトがある正当な JPEG を拒否した（libjpeg と同じく次の 0xFF まで読み飛ばす。エラー文も「切れている、またはマーカーの並びが読めない」に）。
- 解消（LOW）: MPO のフレームの間に他のバイトがある場合（次の SOI を探す）。`_units` の変換関数を直接呼んだ時の bool・巨大な整数・`PIXEL_LIMIT` ちょうど。`print_fit` が 255 文字を超える列を拒否。`page_heights_pt` の型注釈。docstring の係数の説明。API の記述の既定値・`DEFAULT_MARGINS`・`sheet_name_key`/`validate_sheet_name`。罫線の位置のテストでもプリンター名を残す。統合テストの docstring。JSON から作るケースの ID を ASCII（`yu-gothic`・`ms-mincho`）に。測定スクリプト: 別のプリンターのデータは上書きせず、日時付きの別名に保存して終わる（データを失わない）、プリンター名はポートを除いて比べる、壊れた既存の JSON も扱う、一時ファイルを一意に、ページの拡大は近い候補（1 か 100/拡大率）との差 0.2% 以内を求める。
- 記録の補足: ラウンド4で足した行の段の境のケース（95・57・20%、21 px と 16 px）は、ラウンド5で JSON から作る行の最悪条件（12 px の 98・75・21%）に置き換えた。`print_pitch.json` はラウンド4の版のスクリプトの出力（上の進捗に記載）。
- 持ち越し（LOW）: A4 の寸法と JSON のパスと段の分け方の処理が、テストとスクリプトで重複している（読みやすさの問題で、値は同じ）。拡大率 103% など実測の範囲の外を「大きくする側」の確認に使うケースがある（はみ出す向きなので実害は小さい）。

**レビュー反映 (2026-10-20, ラウンド 7)**

レビュアー2観点（silent-failure、python・type-design・layout）。集約後 CRITICAL 0 / HIGH 0 / MEDIUM 1 / LOW 約14。python・type-design・layout の観点は MEDIUM 以上 0。

- 解消（MEDIUM）: 測定スクリプトで、最後の置き換えに失敗する（Windows で既存の JSON が開かれている等）と約1時間の測定データが消えた。測り終えたらまずマイクロ秒までの日時付きの新しい名前で保存し、同じプリンターの時だけ既存のファイルを置き換える。置き換えに失敗した時や別のプリンターのデータの時は終了コード 2 で、日時付きのファイルを残す。読めない・形の違う既存の JSON は別のプリンターのデータと扱う。保存の部分を `_store` に切り出し、置き換えの失敗・形の違う JSON の単体テストを追加（初めの版は秒までの日時で、同じ秒の2回目が1回目を上書きしたのをこのテストで見つけた）。
- 解消（LOW）: JPEG の走査で、フレームの中の2つ目の SOI・長さ 2 未満の区画は完全なフレームとみなさない（走査の途中で切れた JPEG に完全な JPEG をつないだものを拒否。区画の見出し（DQT・SOF・DHT 等）の途中で切れて別の JPEG が続くものは受けうる。ラウンド8で判明、既定の設定の Pillow もこれを読む）。区画の間の `FF 00` は libjpeg と同じく読み捨てる。JSON から作る最悪条件で 100% の記録は "maximum" を期待するケースにする。プリンター名はポートだけを除く（`rsplit`）。`print_fit` の docstring に出すエラーを全部書いた。`pt_to_emu` と `sheet_name_key` が型の誤りを ValueError にする。`validate_sheet_name` の型注釈。`--force` の help。測っていない書体のケース ID はエラー。MPO のテストで `Picture` の受け付けも確かめる。API の記述に「run の text とヘッダーの文字の部品は空でない」。
- 持ち越し（LOW）: MPO の各フレームを MP 索引の位置から確かめること（間に完全な JPEG を挟み2枚目を切った、手で作るファイルを受ける）。単体テストが統合テストのファイルを読み込んで生成器を使う形（Excel に依らない補助モジュールへの切り出し）。`print_pitch.json` を含む `scripts/xlsx_probe/` は必ずコミットに入れること（統合テストが読み込み時に使う）。

**レビュー反映 (2026-10-20, ラウンド 8) とループの終了**

レビュアー1観点（silent-failure、python の品質を軽く）。CRITICAL 0 / HIGH 0 / MEDIUM 1 / LOW 6。製品のコード（`renderers/xlsx`）には MEDIUM 以上なし。MEDIUM は測定スクリプトのもの。

- 解消（MEDIUM）: 測定スクリプトで、測り終えた後に一時フォルダの削除が失敗する（PDF が他のプロセスに開かれている）と全データを失った。`TemporaryDirectory(ignore_cleanup_errors=True)` にし、保存（`_store`）を一時フォルダのブロックの中で行う。Excel の後始末の失敗は保存の後に報告する。PowerShell の時間切れを 3 時間に。構造を AST で確かめる単体テストを追加。
- 解消（LOW）: `pt_to_emu(10**400)` の OverflowError。日時付きの名前を OS が一意にする（同じ秒・同じマイクロ秒でも上書きしない。Python 3.12 の Windows では `now()` の刻みが粗い）。読めない既存の JSON は常に置き換えない、プリンター名が空なら失敗。日時付きのファイルに残した時の終了コードを 3（`KEPT_DATED`、引数の誤りの 2 と区別）にし、メッセージは標準エラーへ。`_store` の単体テストに、別のプリンター・ポートだけ違う同じプリンター・読めない JSON・同じ秒の2回の保存を追加。
- 記録の訂正（L-1）: 上のラウンド7の「切れた JPEG に完全な JPEG をつないだものを拒否」に条件を足した。
- ループの終了: ImplementationLoop の上限の 8 ラウンドに達した。ラウンド8の MEDIUM（測定スクリプト）は直して単体テストで確かめたが、その修正の再レビューはしていない（9 ラウンド目は上限を超えるため）。製品のコードの MEDIUM 以上はラウンド7の python・type-design・layout と、ラウンド8の silent-failure で 0。指摘の件数（CRITICAL/HIGH/MEDIUM）は、ラウンド1 0/5/約20、2 0/2/9、3 0/1/約11、4 0/0/8、5 0/0/3、6 0/0/2、7 0/0/1、8 0/0/1 と減った。

**Tips**

- Excel の COM は PowerShell の `New-Object -ComObject Excel.Application` で動かし、入出力は UTF-8 の JSON ファイルで渡す（標準出力の文字コードに頼らない）。PowerShell のエラー文は `oem` で decode する。`$xl.Hwnd` と `GetWindowThreadProcessId` で自分が起こした Excel の PID をファイルに書き、終わった後に残っていれば `taskkill` する（利用者の Excel とぶつからない）。`finally` で全ブックを閉じて `Quit`・`ReleaseComObject`。
- `PYTHONUTF8=1` のもとで `subprocess.run(..., capture_output=True, text=True)` で `tasklist` を読むと `stdout` が `None` になった（cp932 の出力を UTF-8 として読めないためと推定。原因は未確認）。bytes で受けて decode する。
- pytest の parametrize に 32,768 文字の値を渡すと、テスト ID が環境変数 `PYTEST_CURRENT_TEST` の上限を越えて落ちる。`ids=` を付ける。
- Excel の PDF 書出しで罫線（hair・thin）は2本の細い四角として出ることがある。線の位置を測る時は 1.5 pt 以内の辺をまとめる。
- この環境の Bash のヒアドキュメントでは `\r`・`\n`・`\\1` などのバックスラッシュが壊れる（fonts の Tips と同じ）。正規表現や改行を含むコードは Write/Edit ツールで書く。

#### size（Step 3）

担当 size（サブエージェント）。2026-10-20。状態: **完了**。途中で片持ち梁 p30〜35 の `原本再現できず`（下記の診断）と p36 の位置の差で2度停止して報告し、ユーザー判断 (c)（p30〜35 を Step 9 へ保留）とオーケストレーター判断 (2)（p36 の9セルの差分だけを保留）で再開した。経緯は下の各節。

**進捗**

- ✅ Red: `tests/unit/test_styles.py`（0.5 pt 刻みでない 9.9・9.8・9.058・8.056・0.1・0.25・1.1・7.8・10.25・10.4 がエラー、0.5〜409 の刻みは通る、浮動小数の誤差だけ刻みへ寄せる、`replace()` でも同じ規則、`Script` の大きさの内部の生成経路、その引数の検査）と `tests/unit/test_math.py`（12 pt の添字 7.8 pt・入れ子 5.07 pt が通る、`scale=.66` も通る）。`_script_style` を「今の挙動を返すだけ」の骨組みで置いて `--label size-red` が 25 failed / 171 passed（収集エラーでない本物の失敗）。
- ✅ Green: `--label size-green`（196 passed）。追加の Red: `TextStyle(size=1e308)` が `OverflowError`（`round(inf)`）になる不具合を `--label size-red2` で確かめてから `math.fmod` に変えて解消（`tests/unit/test_fonts.py` の巨大な大きさの検査が通る）。
- ✅ テストの直接指定: `test_text.py` の 0.1／1.1 pt（幅の境目の丸め誤差の検査）を、同じく丸め誤差が出る 4.5 pt（幅 13.500000000000002）・9 pt（27.000000000000004）へ。片持ち梁のテストの 9.9→10、8.056→8、独自の添字 6.7→6.5、`+` の位置 33.6168→33.516（6.5 pt の添字 R の送りが 0.1008 pt 短い）。
- ✅ 片持ち梁の fixture を写像どおりに変更（下記）。
- ⛔→保留 全37ページの生成: p30〜35 が `原本再現できず` で失敗（下記の診断）。2026-10-20 ユーザー判断 (c) で Step 9 へ保留（下の「保留（ユーザー判断 c、2026-10-20）の反映」）。以下はその判断の前の状態。この6ページの影響で片持ち梁の統合テスト（`test_cantilever_p01_37.py`・`test_cantilever_source_appearance.py`・`test_cantilever_improvements.py`）と `test_cantilever_fixture.py::test_all_five_complete_proofs_fit_one_original_page_each`、`test_cantilever_appearance_builder.py::test_only_documented_header_ink_contact_allows_less_than_point_zero_five_shift[9.0-True]` が失敗する。失敗の原因はすべて p30 の見出しのセルの例外（一行の理由で分類して確認）。
- ImplementationLoop と `--label size-final` は末尾の節。

**設計判断**

- `TextStyle.size` は 0.5 pt の正の倍数。誤差 1e-9 pt 以内だけ刻みへ寄せ（`0.1*3*15` → 4.5）、それを超える 9.9 などはエラー（黙って丸めない）。下限は 0.5 pt。上限は設けない（FR-023 は刻みだけを定める。Excel の 1〜409 pt の範囲は xlsx 側の `Font` が検査する）。余りは `math.fmod` で求め、巨大な値でも溢れない。刻みの定数は非公開（`_SIZE_STEP`）。
- `Script` の大きさの生成経路（ラウンド 1 で変更。下の「レビュー反映 (2026-10-20, ラウンド 1)」）: `styles._script_style(style, scale)`（非公開）だけが添字の大きさの style を作る。`scale` は (0, 1] の有限数、`style` は `TextStyle` に限る。刻みどおりなら普通の `TextStyle`、刻み外れなら非公開の `_ScriptTextStyle` （`size == _script_size` の間だけ刻みの検査を外す）。`TextStyle(...)` で一から作る・別の大きさへ `replace` すると規則が働く。書体・字間だけの `replace` は通る。`math.Script.measure` だけがこれを使う。
- src の既定値: `TextStyle()` 10、`ReportStyle.heading` 12、`PageDecoration` の既定（`replace(body, size=9)`）9 はすべて刻みどおり（構築時に検査が働く）。src に他の大きさの生成はない（`replace(style, size=...)` は `math.py` の1か所だけだった）。
- 片持ち梁の写像（`font-profile.json` は JSON を読み書きし、整形は元と同じ indent 2・CRLF）: `items.size` 9.9→10.0 ×1,411、9.8→10.0 ×9、`line_sizes` の 9.8・9.9→10.0 ×各27、`rotated_body_size` 9.9→10.0、`vertical_glyphs.size` 9.9→10.0 ×2。`pages/*.json` の 9.058→9.0 ×8・8.056→8.0 ×4（字句の置換）。`builder.py` の既定 9.9→10、8.056/9.058 の写像（`replace_style_size`）は不要になったので削除。`appearance.py` の独自の添字は `floor(size*.67*2+.5)/2`（10 pt → 6.5 pt）。
- 縦書きの括弧: `vertical_glyphs` に `source_size: 9.9` を足し、原本の字形の外接箱を原本の座標へ直す計算（`appearance.py` の `scale=`）だけに使う。描く大きさは `size: 10.0`。原本の字形の中心へ 10 pt の字形を合わせるため（観測値と描画の値を分ける）。
- 原本比較の文字サイズ（`verify_appearance.py`）: 原本の大きさを 0.5 pt 刻みで読み替え（`_half_point_size`）、出力の大きさは丸めずに比べる。許容差は 0.16 → 0.02 pt（読み替えた値とは一致するはず）。原本どうしの比較（陽性対照）は両方を読み替える。`verify.py` の大きさの検査（8 pt 未満を添字とする区分・本文の最小 −0.02・添字 6.45 以上）は丸めた値でも成り立つので変えていない。位置の許容差は変えていない。

**片持ち梁 p1〜37 の診断（Gate 2 前半）**

診断は一時スクリプトで行い、作業ツリーのファイルは変えていない。HEAD（9.9 pt）は `git archive HEAD src tests/fixtures/cantilever_p01_37` をスクラッチへ展開して同じスクリプトで測った。

| ページ | 結果（10.0 pt） | 原因 | HEAD（9.9 pt） |
|---|---|---|---|
| p1〜29、p36、p37 | 1ページずつ生成できる | — | 同じ |
| p30・p31 | `原本再現できず`: `p3x-combinations-md-r0-cell1: source glyph ink clearance exceeds 0.05 pt` | 回転表の見出し「組合せ」のインクの上端が上の 0.96 pt の線の内側に食い込み、許された押下げ 0.05 pt を超える **0.1251 pt** が要る | 0.0434 pt（許容内） |
| p32・p33 | 同上（`-vd-r0-cell1`） | 「組合せ」0.1251 pt、`r0-cell2` も **0.0916 pt** | 0.0434・0.0127 pt |
| p34・p35 | 同上（`-mt-r0-cell1`）。押下げの上限を外しても `p3x-combinations-mt.rows[0].cells[10]: content lacks clearance from border strokes (vertical)` | 「組合せ」0.1251 pt に加え、見出し「ねじり」のインクが上の線の内側の縁を **0.0516 pt** 越える（ライブラリの `Table` の余白検査） | 「ねじり」の余白 +0.027 pt |

- 全37ページの一括生成も p30 で止まる（上限を外すと p34 で止まる）。ページ数のあふれ（38ページ目）ではなく、セル単位の `原本再現できず` の検査が止めている。
- 10.0 pt への変更との関係: すべて p30〜35 の回転表の見出し行（row 0）で、行の高さは原本の 9.9 pt の字に合わせた固定値。字が 1.01 倍になり、インクの上端が上がって上の線に近づいた（「組合せ」で +0.082 pt、「ねじり」で +0.079 pt）。HEAD ではどれも許容内だった。
- 最も詰まった所（上限を外した診断で、上記以外）: p30〜35 の「ﾓｰﾒﾝﾄ」等の見出しの上の余白 0.0266 pt（HEAD 0.1043 pt）、p30・p32・p34・p36 の「1.0LR+1.23B」の右の余白 0.28 pt（p36 の HEAD は 9.8 pt で 1.388 pt）。p31・p33・p35・p37 は 0.3112 pt（変化なし）。
- 直し方の候補（ユーザー判断。私は実施していない）: (a) `SOURCE_INK_CLEARANCE_CELLS` の押下げ上限 0.05 pt を 0.13 pt 程度へ上げ、「ねじり」のセルも対象に足す（原本の位置から最大 0.13 pt ずれる）、(b) 見出し行の高さを広げる（原本の表の行高と異なる。FR-027 では Step 9 でグリッドの整数倍に作り直す予定）、(c) Step 9 の作り直しまで、この6ページの検査を保留する。

**保留（ユーザー判断 c、2026-10-20）の反映と、新たに見つかった p36 の位置の検査の失敗（指示待ち）**

- 保留の定義: `tests/fixtures/cantilever_p01_37/deferred.py`（新設。テストだけが読む）に `DEFERRED_PAGES = p30〜35`、`AVAILABLE_PAGES`（31ページ）、`DEFERRED = pytest.mark.xfail(strict=True, raises=LayoutOverflowError, reason=…)`、`selections(pages)`（除外ページを除いた組と、全体を strict xfail にした組の parametrize）。fixture 本体の挙動は変えていない。
- 31ページで走らせるように直したテスト: `test_cantilever_p01_37.py` の37ページ一括の fixture（`complete_report` → `available_report`。p30 未満のページ番号の添字は不変）を使う検査すべて、`test_all_37_pages_from_public_api`・`test_scene_images_have_independent_allowlist_validation`・`test_native_fixed_37_page_contract`（31ページ版を追加し、37ページ版は xfail）、`test_complete_rotated_proof_pages_from_public_api`（p36 だけ版を追加、(30, 36) は xfail）、`test_native_page_number_is_prohibited`（p36 版を追加、p30 版は xfail）、`test_native_pdf_visual_corruptions_are_detected`（small-body・lost-rule・split-merged-cell を p36 で。p36・p37 の表には添字が無いので flat-script・raised-script は p30 版だけ＝xfail）、`test_cantilever_fixture.py::test_all_five_complete_proofs_fit_one_original_page_each`（p30 を除いた4ページ版と、5ページ版の xfail）、`test_cantilever_improvements.py::test_migrated_fixed_pages_preserve_original_content_and_appearance`（(1, 26, 36) 版と (1, 26, 30, 36) の xfail）、`test_cantilever_source_appearance.py` の原本外観の比較（(1, 3, 21) に、回転表の代わりとして p36 を足した版と、(1, 3, 21, 30) の xfail を1件）。
- ⛔→保留（下の「p36 の9セルの保留」） 新たに見つかった失敗（p30 で止まっていたため今まで見えていなかった）: p36 を含む原本外観の比較で、`spacing` の「operator inline origin」が **9件**（`p36-combinations-summary.r10.c8`〜`r18.c8`、どれも「1.0LR+1.23B」の `+`）、差 **0.600 pt**（許容差 0.25 pt）。HEAD（9.8 pt）では差 0.098 pt で合格。原因: 9.8→10.0 pt で半角1字の送りが 4.94→5.04 pt になり、セルの先頭に固定した行で `+` より前の5字の分だけ `+` がずれる（0.1 pt × 5 ＋ もとの差）。31ページ（p1〜29・p36・p37）全体の原本外観の比較で、許容差を超えるのはこの9件だけ（各分類の最大差: spacing 1.2001 pt（許容差内の検査も含む）、font 0.117、table 0.002、baseline・equals 0.0001、indent 0）。指示どおり位置の許容差は緩めず、ここで止めて指示を待つ。この影響で `test_migrated_fixed_pages_preserve_original_content_and_appearance[*-without-deferred]` の2件と `test_reproduction_matches_original_appearance[spacing]` が失敗中。
- 見出しの余白の単体テスト（`test_cantilever_appearance_builder.py::test_only_documented_header_ink_contact_allows_less_than_point_zero_five_shift`）は、ページの生成ではなく仕組み（0.05 pt までの押下げだけを許す）の検査で、基線を自由に決めている。xfail にせず、10 pt の「組合せ」のインクの高さ（209/256 em = 8.1640625 pt、9.9 pt より 0.08 pt 高い）に合わせて基線を 9.0/8.9 → 9.1/9.0 に下げ、期待値を `.961+8.1640625` にした（押下げ 0.025 pt で通る／0.125 pt で拒否）。
- 計画書: Step 3 の3項目めに ✅（31ページは生成できる、p30〜35 は Step 9 へ保留）。Step 9 に保留を外す項目、Completion gates の Gate 2 を同じ趣旨に更新。

**p36 の9セルの保留（2026-10-20 オーケストレーター判断 (2)、根拠 FR-027）**

- 保留はこの9件の差分だけ。p36 のページ全体と他の検査は保留しない（外観比較の対象 (1, 3, 21, 36)・(1, 26, 36) はそのまま）。
- `deferred.py` に `DEFERRED_DIFFERENCES`（ページ 36、要素 id `p36-combinations-summary.r10.c8`〜`r18.c8`、検査の種類 `spacing`・`operator inline origin`、上限 `max_delta_pt` 0.61、理由 `DIFFERENCE_REASON`）を列挙。
- `verify_appearance.appearance_report(..., deferred=…)`・`verify_appearance(..., deferred=…)`: 列挙と id・種類・詳細が一致し、差が上限以内の差分だけを `deferred`（`deferred_count`）に別に数え、`errors` から外す。それ以外の差分は今までどおり失敗。比較したページ・種類に列挙があるのに差分が出なければ `deferred` 種類の失敗（「no longer occurs; remove it from deferred.py」）になる（strict の xfail と同じ考え方）。列挙の形（鍵の組・型・id のページ接頭辞・重複）を検査し、崩れていれば `ValueError`。既定の `deferred=()` では挙動は従来どおり（`render.py` の正解の作成は変わらない）。
- Red: `--label size-deferred-red`（7 failed。`deferred` 引数が無い `TypeError`）→ Green: `--label size-deferred-green`。
- 計画書の Step 9 の保留を外す項目にこの9セルを追加。

**レビュー反映 (2026-10-20, ラウンド 1)**

レビュアー3体（silent-failure-hunter＋python-reviewer、type-design＋計画整合＋テスト妥当性、layout＋PDF）。集約（重複は高い方へ統合）: CRITICAL 0 / HIGH 1 / MEDIUM 2 / LOW 12。

- ✅ H: 添字の書式（刻み外れ、例 12 pt の上付き 7.8 pt）を、利用者の作った MathNode が `replace(style, font=…/tracking=…)` で作り直すと ValueError になっていた（公開の `fit_tracking` も同じ。3体が指摘）。FR-023 は Script 由来の大きさを対象外とするので、大きさを変えない作り直しは許すべき → 非公開の `styles._ScriptTextStyle(TextStyle)` を作り、`size` が `_script_size`（`_script_style` が `Script.scale` から求めた値）と一致する間だけ刻みの検査を外す。`dataclasses.replace` は型と `_script_size` を保つので書体・字間の変更は通り、別の大きさにすると `TextStyle` の規則が働く（`replace(script, size=9.9)` はエラー、9.5 は可）。刻みどおりの添字（10 pt × 0.65 = 6.5 pt）は普通の `TextStyle` を返す（等しさ・型の変化を避ける）。`object.__new__` での作り方はやめた。Red（`--label size-r1-red`、4 failed）→ Green（`size-r1-green`）。
- ✅ M: 保留の strict xfail は例外の型だけを見ており、p30〜35 の失敗の理由が変わっても気づけない → `test_cantilever_fixture.py::test_deferred_pages_still_stop_for_the_recorded_header_clearance`（p30〜35 を1ページずつ、`p3x-combinations-{md,vd,mt}-r0-cell1: source glyph ink clearance exceeds 0.05 pt` で止まることを固定。直れば失敗して保留を外す合図になる）。
- ✅ M: 実行記録の担当表と状態が「指示待ち」のまま → 更新（上）。
- ✅ L（同ラウンドで対応）: 大きさの下限は「at least 0.5 pt」と別のエラー文に／`math.py` の未使用の `replace` の import を削除／保留の列挙の `category` を既知の6種類に限る／保留1件は差分1件だけを吸収する／`deferred.selections` は先に tuple 化／`SourceScript` は丸めた添字が 6.45〜8 pt（`verify.py` の区分）を外れるベース（9・12 pt など）を ValueError に／本文の大きさを1段（9.5・10.5 pt）変えると `body size (0.5 pt step)` で検出される陰性対照を追加／見出しの余白の単体テストの合格側の基線を 9.08（押下げ 0.045 pt、上限のすぐ内側）に。
- 持ち越し（LOW、lead・ユーザー判断）: `docs/api.md` の `TextStyle` に 0.5 pt 刻みを書く（計画では Step 10）／DESIGN.md に判断 (c) と p36 の保留の注記を足す（`update_design.py`、lead の担当）／回転した添字の改ざん検出が p30 の xfail だけになった（`verify._script_positions` の回転方向の単体テストで補える）／`render.py` は保留を受け取らないので、p36 を含む proof bundle は Step 9 まで9件の差分で止まる（隠さず止まる側）／片持ち梁の PNG 正解の作り直しは Step 9 の後（10 pt にした後の画素は誰も比べていない）。
- 新しい見逃しパターン: 「作り直しでも規則を効かせる」を「大きさを変えない作り直しも禁じる」と広く実装すると、拡張点（MathNode）で利用者の正当な書体・字間の変更が、大きさのエラーとして現れる。

**レビュー反映 (2026-10-20, ラウンド 2)**

レビュアー1体（silent-failure-hunter＋python-reviewer＋type-design、ラウンド 1 の修正の検証）。CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 5。

- ✅ L: 実行記録の設計判断の一文がラウンド 1 の前のまま → 書き直し（上）。
- ✅ L: `SourceScript` の注記を受け付ける範囲（`verify.py` の区分 6.45〜8 pt に入る添字）に合わせた。
- 持ち越し（LOW、コードの変更を伴うので次の担当・lead の判断）: 刻みの大きさへ `replace` した添字の style は `_ScriptTextStyle` のまま残り、同じ値の `TextStyle` と `==` にならない（ライブラリ内に style の等しさを使う所は無い。Step 8 で書体をまとめる時は値で比べること）／`_script_style` は誤差の寄せを使わず厳密一致で刻みを判定する（実在の基準・scale の組合せで差は0件）／上限を超えた保留の差分に「no longer occurs」と案内してしまう（失敗は隠れない）。

**完了（ImplementationLoop）**

- 全ラウンド数 2。指摘の推移: ラウンド 1 HIGH 1 / MEDIUM 2 / LOW 12 → ラウンド 2 MEDIUM 0 / LOW 5。
- 最終確認 `--label size-final`（片持ち梁の PNG 正解テストと `test_xlsx_*`・`test_xlsx_excel_core.py` を除く全テスト 51 ファイル）: **2266 passed、18 xfailed**（xfail はすべて `deferred.DEFERRED` の strict xfail、XPASS 0）。カバレッジ（`COVERAGE_FILE=.coverage.size`）は `styles.py` 99%（未到達は防御の1行）、`math.py` 98%。全体の 72% は作業中の `renderers/xlsx/`（テストを除外したため 0%）を含む値で、最終の全体カバレッジは lead が単独で測る。
- 片持ち梁の PNG 正解（`test_cantilever_p01_37_golden.py`）は、src の hash の不一致に加えて p30 の `原本再現できず` でも止まる。作り直しは Step 9 で保留を外した後。

#### borders（Step 4）

担当 borders（サブエージェント）。2026-10-20。

**進捗**

- ✅ 基準: `--label borders-baseline`（片持ち梁の PNG 正解と `test_xlsx_*`・`test_xlsx_excel_core.py` を除く全テスト。除外は `PYTEST_ADDOPTS` で渡した）2266 passed、18 xfailed。代表例の PNG 正解はこの時点で合格。
- ✅ Red: `tests/unit/test_borders.py`・`test_table_borders.py`・`test_rule.py`（新設）、`test_side_rule.py`（書替え）。公開名を `gridlayoutpdf` の属性で引く書き方にして `--label borders-red-1` が 102 failed / 11 passed（本物の失敗。最初は `from gridlayoutpdf import BorderStyle` で収集エラーになったので書き方を直した）。
- ✅ Green: `--label borders-green-1`。既存テストの書き換え（下記）の後、自己レビューの3件（外枠の既定を表す印がコピー・pickle で別物になる／ヘッダーの縦線の延長／`KeepWithNext` の予約で線を端の命令だけに持つ part を見えないと数える）を `--label borders-red-2`（3 failed）→ `borders-green-2`。
- ✅ 片持ち梁の原本比較の太さの検査の陰性対照（`test_output_rules_must_have_their_border_styles_thickness`）は、HEAD の `verify_appearance.py` に一時的に戻して `--label borders-red-thickness` で失敗を確かめ、元に戻した。
- ✅ ImplementationLoop ラウンド 1 の修正: `--label borders-r1-red`（16 failed）→ `borders-r1-green`。全体 `borders-full-4`: 代表例の PNG 正解の1件だけ失敗（下記、想定どおり）。

**公開 API（最終）**

- `BorderStyle`（`StrEnum`、値は Excel の名前 hair・thin・medium・thick・double・dotted・dashed・dashDot・dashDotDot・mediumDashed・mediumDashDot・mediumDashDotDot・slantDashDot。文字列でも渡せる）。`stroke_width`・`offsets`・`dash`・`thickness`・`lines(x1, y1, x2, y2, color)`。
- `TableBorders(default=THIN, *, outer=<既定と同じ>, horizontal={}, vertical={}, horizontal_edges={}, vertical_edges={})`。優先は辺1つ → 境目1本 → 外枠 → 既定（書いた順によらない）。`None` は線なし。`frame`（外枠が解決する種類）、`resolve(rows, columns)`。対応表は `(番号, 種類)` の組で保持（組の形も受け付け、重複は ValueError）。結合セルの内側を名指すと ValueError、表の外の番号も ValueError。
- `Table(..., borders=TableBorders() | BorderStyle | str | None, border_color=...)`。`border_width`・`horizontal_rules`・`vertical_rules` は廃止（渡すと TypeError、数値の種類は ValueError「pt widths are no longer accepted」）。既定は全辺が細。セルの metadata に `align`・`valign`・`borders`（`top`・`bottom` は列ごと、`left`・`right` は行ごと）。
- `Rule(style=THIN, *, columns=None, color=(0, 0, 0), block_id="")`: 1グリッド行（細かいグリッドでは太さが入る行数）を占め、上の境目に沿って行の中に引く。幅は利用可能幅か `columns` 列。metadata `rule`（`style`・`width_pt`）。
- `SideRule(block, x, *, style=THIN, top=0, bottom=0, color, block_id)`（`width=` は廃止）。x は線の中心。実線は塗りの `Rectangle`（二重は2本）、破線系は `Line`。metadata `side_rule_pt`・`side_rule_style`。
- `LayoutPart(rows, commands, metadata, *, opening=(), continuing=(), joining=(), closing=())`。

**設計判断**

- PDF での描き方（DESIGN.md Key Decisions に記録）: 極細 0.25・細 0.5・中 1.0・太 1.5 pt。二重は 0.5 pt の2本で、間隔 1.0 pt は**線の中心の間**（隙間 0.5 pt、全体 1.5 pt＝太と同じ。Excel の線・隙間・線が同じ幅の比）。破線は細の dotted (0.5, 1.0)・dashed (3.0, 1.5)・dashDot (6.0, 1.5, 1.5, 1.5)・dashDotDot (6.0, 1.5×5)、中の mediumDashed (6.0, 2.0)・mediumDashDot (6.0, 2.0×3)・mediumDashDotDot (6.0, 2.0×5)・slantDashDot (6.0, 1.0, 2.0, 1.0、斜めの切り口は描かない)。`SideRule` の既定は細（旧 0.72 pt に最も近い）。`Rule` は行の上の境目（直前の内容のすぐ下）に引く。
- 優先順位はより具体的な指定が勝つ（計画の Red の「後から決めたものが優先」ではなく、オーケストレーターの指示どおり）。境目1本ぶんの指定が結合セルを横切るときは内側だけ黙って抜く。辺1つで結合セルの内側を名指すのは誤りとしてエラー。
- 継ぎ目と「ページ先頭のときだけ描く命令」（DESIGN.md Key Decisions に記録）: `prefix`・`discard_at_page_top` と同じく計測結果（`LayoutPart`）に印を載せる。4つの命令列は、置かれた断片の中の位置で選ぶ（先頭なら opening、それ以外は continuing、最後なら closing、それ以外は joining）。`MeasuredBlock.commands`（＝`translated`）が選ぶので、`Document._Paginator.place` は変更不要。Document は改ページで切れた断片を必ず flush の後（頁の先頭）に置くので、2つ目以降の part の opening は頁の先頭でだけ描かれる。表の行群の境目は、上の行群が joining（境目を中心に1本）/closing（頁の下端で自分の中に1本）、下の行群が opening（頁の先頭で自分の中に1本）。縦線は上の行群が境目で止め（closing では半ストローク手前）、下の行群は半ストローク下から始めて continuing で境目まで補う。これで同じ頁では実線の種類のインクが `split=False` と同じになる。joining は次の part の中まで、continuing は前の part の中まで描けて、`measure_block` が「分割後に隣に来得る part のうち最も低いもの」で検査する（繰り返す prefix の前後を含む）。
- 繰り返すヘッダー: 自分の下の境目の線を引き、後の頁でその下に来る本文の行群は上の線を引かない（境目の種類はヘッダーの下の境目のもの）。本文の各行群の先頭のセルは、ヘッダーの下の線の太さの半分の余白も取る（ラウンド 1 の HIGH）。
- 余白の検査: 行群の上下と外枠は太さ全体（opening/closing で part の中に引くことがあるため保守的に）、内側の境目は半分。二重・破線も `thickness` で数える。
- 計算と描画の分離: 罫線の種類は計測の段階ですべて `Line`（と SideRule の `Rectangle`）に確定する。`scene.py`・`renderers/reportlab.py` は変更不要（`Line.dash` と butt cap の描画が既にある）。計画の Step 4 のファイル一覧にある2ファイルを変えなかったのはこのため。
- 継ぎ目の線の位置は、上の行群の中（境目から半分上）ではなく境目の中心にした。分割しない表と同じ見た目・同じ余白（内側は半分）になり、fixture の旧「半分の太さ2本」と同じ中心位置になる。
- 不採用: `command_bounds` を butt cap どおり（軸に平行な線の端を延ばさない）にすれば、外枠の角の欠けも継ぎ目の補いの線も不要になるが、公開関数と既存の検査（`test_layout` の線の外形の検査など）の契約が変わるため、Step 4 では行わない（下の持ち越し）。

**片持ち梁 fixture（最小の変更）**

- `builder.py`: 線幅 → 種類の写像 `rule_style`（原本 0.12・0.1201 → 極細、0.96 → 中、`pages/*.json` の 0.24 → 極細、0.4・0.5 → 細、0.7・1 → 中。0.7 は原本の太い線の役なので中）。`_rule_borders` が境目ごとの `TableBorders` を作り、境目の数を検査する。継ぎ目の半分の太さ（旧 265-266 行）は廃止。`_table_outer_edges` は新しい種類の太さの半分で外枠へ寄せる（線の中心は原本の位置のまま）。`SourceCell` の余白も新しい太さで計算。区切り線（Figure＋Line）は触っていない（Step 9）。
- `appearance.py`: `continuous_table_rules` は線幅・色・破線の模様（＝種類）で分け、接するか重なる線だけをつなぐ（ライブラリが継ぎ目を連続して描くので、隙間は本物の隙間として残す）。
- `verify_appearance.py`: 外枠の線の太さの検査（±0.08 pt で原本と比較）を「種類の太さどおりか」（原本 0.12 → 0.25、0.96 → 1.0、許容差 0.01 pt）に置き換えた。原本どうしを比べる陽性対照だけは原本の太さどうし。位置（中心 ±0.20 pt）など他の検査は変えていない。
- `README.md` の表の線の説明を更新。保留（p30〜35 の strict xfail、p36 の9セル）は維持され、XPASS なし、新しい失敗なし。

**既存テストの書き換え（意図を保つ）**

- `test_table_rules.py`: 数値の太さを種類へ。pt で太さを変えていた「太い線がセルを食い潰す」「向かい合う線」などは、細かいグリッド（1 pt）の小さなセルで太（1.5 pt）を使う形に。継ぎ目の二重線（19.75・20.25）を前提にした期待値は、中央の1本へ。
- `test_tables.py`・`test_table_row_heights.py`・`test_table_pdf.py`・`test_cantilever_improvements.py`（p26 の線幅 0.12 → 0.25）・`test_cantilever_appearance_builder.py`: 同様。`test_table_pdf.py` は継ぎ目が1本・縦線が連続することを検査。

**代表例の PNG 正解（想定どおりの失敗、更新はしていない）**

- `tests/visual/test_representative_golden.py` が失敗する。差は分割する表の行群の境目だけ（1頁 3か所、3頁 10か所、4頁 5か所、各帯は表の全幅・高さ 1〜2 pt。2頁・5頁は画素一致）。旧: 上の行群の下端と下の行群の上端に 0.5 pt の線が2本（計 1.0 pt）。新: 境目の中心に 0.5 pt の1本（FR-026）。頁の先頭・下端の線と外枠は画素一致。正解の作り直しは lead（Step 10）。

**Step 5（tags）への引継ぎ**

- 表の線はすべて `tables._Edges` の `_horizontal`/`_vertical` から `BorderStyle.lines()` で作る。1回の呼出しが「1つの境目・同じ種類で続く列（行）の範囲」で、1本（二重は2本）の `Line` になる。タグ（辺の向き・境目の番号・列/行の範囲・種類・opening/continuing/joining/closing のどれか）はここで付けられる。continuing の補いの線は、下の行群の同じ縦の辺に属する。
- `Rule` の線は `Rule.measure`、`SideRule` は `SideRule._bars`（実線は塗りの `Rectangle`、破線系は `Line`）で作る。
- セルの記録に `align`・`valign`・`borders`（辺ごとの種類）がある。`Rule` の part に `rule`、`SideRule` の part に `side_rule_pt`・`side_rule_style`。
- part を作り直す容器を足すときは、`layout.EDGE_COMMANDS` の4つの命令列も移すこと（`Indent` と同じ）。`Leading` は端の命令を持つ part の行数を変えるとエラー。

**レビュー反映 (2026-10-20, ラウンド 1)**

レビュアー4体（python-reviewer＋type-design、silent-failure-hunter、layout＋PDF、計画整合＋テスト妥当性）。集約（重複は高い方へ統合）: CRITICAL 0 / HIGH 1 / MEDIUM 5 / LOW 12。

- ✅ H（3体）: 繰り返すヘッダーの下の線（境目を中心に引く）が、後の頁でその下に来る本文の行群（自分の上の境目は別の種類か線なし）の中身と重なっても検査を通っていた → 本文の各行群の先頭行のセルは、ヘッダーの下の線の太さの半分の余白も取る（`Table.measure` が `under` を渡す）。
- ✅ M（3体）: 継ぎ目で縦線の種類が変わる・継ぎ目から始まる所、ヘッダーの下に縦線の揃わない行群が来る所で、`split=True` だけ縦線が半ストローク途切れていた → `LayoutPart.continuing`（先頭でないときに描く。前の part の中まで描ける）を加え、上の行群は縦線を境目で止め、下の行群が境目から半ストロークを補う。旧「続く行群がすべて同じ種類なら延ばす」は廃止。ランダムに作った表で `split=True` と `split=False` の実線のインクの差 0 をレビュアーが確認（ラウンド 2）。
- ✅ M: 文書の「破線の模様も続く」「split=False と同じ罫線」が不正確 → 破線の模様は行群ごとに始まる、実線はインクが同じ、と書き直した（`docs/api.md`、`Table` の docstring）。
- ✅ M: `TableBorders` の型注釈が保持する値と違う → 受け取りと保持の型の和で注釈、`frame` プロパティを公開、補助（`_border_style`・`_table_borders`・`_check`）を非公開に。
- ✅ M: `Rule` が細かいグリッド（pitch 0.01 など）で失敗 → `max(1, rows_for(thickness))` 行を占める。
- ✅ M: 記録の欠け → この節、計画の Step 4 の ✅、DESIGN.md Key Decisions（2件、`update_design.py`）。代表例の PNG 正解の失敗の理由も上に記録。
- ⏭ M（layout＋PDF）: 外枠の角・T 字の交わりの小さな欠け → HEAD でも異なる太さの組合せで同じ（`command_bounds` の保守的な線の外形が原因）。直すには公開関数の契約変更が要るため Step 4 では行わず、`docs/api.md` に制約として書き、持ち越し（上）に記録。lead・ユーザーの判断事項。
- ✅ L（同ラウンドで対応）: 組の形の対応表の重複キーをエラーに／`Decimal`・`Fraction` も「pt widths」の案内（`numbers.Number`）／`borders=` のエラー文に TableBorders／`_runs` の終わりを `stop` と命名・型注釈／`Leading` が端の命令を持つ part の行数を変えないように／`SideRule` が `side_rule_style` を記録／fixture の `_rule_borders` が境目の数を検査／`continuous_table_rules` は接する線だけをつなぐ（隙間を隠さない）／`test_table_row_heights.py` の余白のテストを 1.1 pt の行で `clearance` に戻した／Table の docstring の古い一文。
- 持ち越し（LOW）: 二重線の角が格子状になる（Excel の二重罫線の角とは違う。方針の判断）／`docs/validation.md:132` の古い記述（Step 10）。
- Red→Green: `borders-r1-red`（16 failed）→ `borders-r1-green`。

**レビュー反映 (2026-10-20, ラウンド 2)**

レビュアー2体（silent-failure＋python、layout＋PDF）。CRITICAL 0 / HIGH 0 / MEDIUM 1 / LOW 4。

- ✅ M: `Leading` の検査が、行数の変わらない part（`minimum=True` で背の高い行群）まで拒否し、短すぎる指定の `LayoutOverflowError` より先に止まっていた → 新しい行数を先に決め、実際に変わる時だけ拒否。
- ✅ L: 組の形の対応表のハッシュできないキーを ValueError（引数名付き）に／`True` を「pt widths」と案内しない／`under` の適用範囲（行群の先頭行だけ、ヘッダー自身には効かない）のテスト／`_part_visible` を断片の中の位置で判定（先頭の part は opening、他は continuing も数える）。
- 検証（layout＋PDF）: ランダムな表で `split=True`/`split=False` の実線インクの差 0（pitch 5 で 1,500 表、pitch 0.01 で 300 表、破線を含む 800 表）、改ページした頁ごとの比較 2,399 頁で差 0、QuarterTurn 375 表で差 0、PDF の線幅・破線は設計表どおり。代表例の差はすべて継ぎ目から 2 pt 以内。
- Red→Green: `borders-r2-red`（4 failed）・`borders-r2b-red` → `borders-r2-green`・`borders-r2b-green`。

**レビュー反映 (2026-10-20, ラウンド 3)**

レビュアー1体（silent-failure＋python、ラウンド 2 の修正の検証）。CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 2（どちらもラウンド 2 の修正由来ではない）。

- ✅ L: prefix の part は必ず本文が続くので joining だけで見えると数える（`_part_visible(..., prefix=True)`）。以前は joining と closing の両方を求め、自作の部品で見出しの予約が過大になり得た。
- ✅ L: `Leading(overhang=…)` が端の命令の part を拒否する経路・短い overhang で先に溢れる順序、prefix の後の part の continuing を見える扱いにする経路のテストを追加。

**完了（ImplementationLoop）**

- 全ラウンド数 3。指摘の推移: ラウンド 1 HIGH 1 / MEDIUM 5（うち1件は持ち越し）/ LOW 12 → ラウンド 2 MEDIUM 1 / LOW 4 → ラウンド 3 MEDIUM 0 / LOW 2（対応済み）。
- 最終確認 `--label borders-final`（片持ち梁の PNG 正解と `test_xlsx_*`・`test_xlsx_excel_core.py` を除く全テスト）: **2392 passed、1 failed、18 xfailed**。失敗は代表例の PNG 正解1件だけで、理由は上の「代表例の PNG 正解」（FR-026 の継ぎ目）。xfail はすべて `deferred.DEFERRED` の strict xfail で XPASS 0。カバレッジ（`COVERAGE_FILE=.coverage.borders`、`borders-full-4`）: `borders.py`・`blocks.py`・`containers.py`・`document.py` 100%、`tables.py` 99%、`layout.py` 98%（未到達は以前からの防御の行）。

**持ち越し（lead・ユーザーの判断）**

- 外枠の角や T 字の交わり（細い外枠に太い内側の線など）で、線の端を半ストローク手前で止めるため小さな欠けが残る（細 0.25×0.25 pt、太 0.75×0.75 pt）。HEAD でも異なる太さの組合せでは同じ（`command_bounds` が線の端も半ストローク延ばす保守的な外形のため）。直すには `command_bounds` を butt cap どおりにする契約変更が要る。`docs/api.md` に制約として記載。
- 破線の模様は行群ごとに初めから始まる（`Line` に模様の開始位置がないため）。`docs/api.md` に制約として記載。
- `DESIGN.md` FR-020 の備考に `SideRule(block, x, *, width, ...)` が残っている（型付きライターは既存の行を書き換えられないため、lead が直す）。`docs/validation.md:132` の「任意分割表のページ境界をまたぐ線の統合は対象外」も古い（Step 10 の文書更新で）。

#### tags（Step 5）と数値の見分け（Step 8 の先行分）

2026-10-20。前のセッションの担当が中断した状態から lead が引き継いだ。

- ✅ `semantics.py`（`Role`・`Kind`・`Scope`・`Tag`・`FrozenData`・`within`・`tagged`）と全描画命令の `tag`（`compare=False`、キーワード専用）。分数・添字・根号・括弧・式の各部分・表のセルと辺・`CellLines`・段落・図・`Rule`・`SideRule`・ヘッダー/フッター・`QuarterTurn` に付与。`Document` はページの metadata の配置ごとに `block_type` と命令の範囲（`commands`・`prefix_commands`・`part_commands`）、装飾に雛形・`align`・範囲を記録。`layout_trace` はタグのある命令にだけ `tag`。
- ✅ `tests/unit/test_scene_tags.py`・`test_component_tags.py`（PDF が変わらないことの検査を含む）合格。
- ✅ `renderers/xlsx/_numbers.py`（`classify_number`・`excel_display`・`NumericCell`）。中断時に Red だった `test_exact_context_does_not_take_the_default_context`（`decimal.DefaultContext` を import 前に変えると `_EXACT` に漏れる）を、`Context` の全設定を名前で渡して Green（`resume-numbers-green` 244 passed、Excel の統合テストを含む）。
- ✅ `docs/architecture.md` に「意味のタグ」の節（役割・構造の種類・データの一覧）を追加。

#### cantilever（Step 9）

担当 cantilever（サブエージェント）。2026-10-20。状態: **作り直し済み・レビュー中（ラウンド4の反映と lead の判断 (a) の反映済み。ラウンド5の silent-failure レビュー中）**（2026-10-20 ユーザーが案 (a) を選んで再開。式の `term_columns="grid"`・方眼Excel の strict 検査も済み）。下の「あふれの確認」「案 (a) の実測」は再開前の記録。

**あふれの確認（Gate 2 後半の事前確認）**

作り直しの前に、回転表 p30〜37 を縦横入替のページのグリッドで組めるかを、ライブラリの部品だけで確かめた（一時スクリプト、作業ツリー外）。

- 条件: `local_grid = GridSpec(0, 0, 15.48, 16.08, 48, 31)`（`CANTILEVER_SOURCE_A4` のグリッド 16.08×15.48・31列48行の縦横入替）。`Table` の行の高さは自動（整数の局所行）、セルは `CellLines`（MS Mincho 10.0 pt、上下の余白 0.3 pt・左右 0.5 pt、`padding=0`）、罫線は極細、添字は `Script(subscript_drop=1.92)`。列の幅は内容の最大幅＋1.25 pt が入る最小の局所列数。
- 結果（行送り 10.0 pt）: p31・p33・p35・p36・p37 は1ページに収まる。**p30・p32・p34 は表の高さ（紙面では幅）が 38 局所行 = 611.04 pt 要り、使える 31 局所行 = 498.48 pt を 7 局所行（112.56 pt）超えて `LayoutOverflowError`**。611.04 pt は用紙の幅 595 pt も超えるので、余白やグリッドの列数を変えても A4 縦の紙面には入らない。行送り 10.8 pt（原本の値）では p30・p34 が 39 局所行（627.12 pt）。
- 原因: p30・p32・p34 の表は見出し2行と18ケースで、各ケースの行に「係数／値」の2行のセル（例 `1.0S10`／`625.00`）がある。2行のセルは 1 局所行（16.08 pt）に入らない（行送り 8.0 pt で `1.0S10` の添字と次の行の字形が接触してエラー、9.0 pt でも2局所行になる）。よって 2＋18×2 = 38 局所行が下限。原本はこの行を 21.6 pt（局所行の 1.34 倍）で組んでいる。
- 参考: p36・p37 は原本の列の幅を切り上げると 49 局所列で、本文の 48 行を超える。内容に合わせた列の幅（43・41 局所列）なら収まる。非回転のページ（p1〜29）は、1行の文字を1グリッド行・表の行を内容の行数・図を切り上げた行数として数えた下限が最大 40 行（p14・p24）で、48 行に収まる見込み（実際の組みでは未確認）。
- 指示どおり、文字を縮める・内容を変える・グリッドを変えるなどの対処はせずに停止した。lead の判断を待つ。

**判断が要る点（候補。どれも未実施）**

- (a) p30〜37 だけ別の用紙の設定（グリッド）にする。原本の回転表の列の幅（29.04〜29.1・43.56・58.08・87.06 pt）は 14.52 pt のほぼ整数倍（2・3・4・6倍）、行の高さ（10.86・21.6・21.54 pt）は 10.8 pt のほぼ整数倍（p36・p37 の見出し行 44.64 pt は 4.13 倍、14.94 pt は 1.38 倍）なので、ページのグリッドを横 10.8・縦 14.52 pt にすると、縦横入替の局所グリッドで原本に近い行の高さ・列の幅をマスの整数倍で組める見込み（組んで確かめてはいない）。方眼Excel ではグリッドが変わる所で別のシートになる（FR-021）。A4.pdf のグリッドとは異なる。
- (b) 2行のセルを1局所行に入れる: 字形が接触するので不可（上記）。
- (c) 表を2ページに分ける・文字を縮める: FR-014・FR-023 と不可侵条件に反する。

**確認に使ったもの（scratchpad、リポジトリ外）**: `rotated_probe.py`（原本の列の幅の切り上げ）・`rotated_probe_min.py`（内容に合わせた列の幅）・`rows_needed2.py`（非回転ページの行数の下限）。

**案 (a) の実測（lead の依頼、2026-10-20。fixture・テストは変更せず scratchpad のスクリプトだけ）**

- 決めたページのグリッド（p30〜37 用）: `GridSpec(50.88, 54.598, 10.8, 14.52, 46, 51)`（用紙 595×842 の A4 縦。原点は `CANTILEVER_SOURCE_A4` と同じ。列数・行数は `CANTILEVER_SOURCE_A4` の本文の枠 右 549.36・下 797.638 pt に収まる最大の整数で、右端 547.68・下端 795.118 pt）。縦横入替の局所グリッドは `GridSpec(0, 0, 14.52, 10.8, 51, 46)`（列の幅 14.52 pt・行の高さ 10.8 pt）。
- 組み方: `Table`＋`CellLines`（MS Mincho 10.0 pt、行送り 10.8 pt＝原本どおり、左右の内側余白 0.5 pt、`padding=0`）、罫線は全辺極細、`split=False`、`QuarterTurn(turns=1)`、添字は `Script(subscript_drop=1.92)`。p30 は見出し「13.2 設計作用の組合せ」（MS Gothic 10 pt の `Paragraph`）を表の上に置く。列の幅は「原本の幅を 14.52 pt で丸めた列数、10.0 pt の内容が入らない列だけ広げる」。行の高さは「原本の高さを 10.8 pt で丸めた行数」で固定（自動の行の高さでも結果は同じ。ただし p36・p37 は1行のケースの行が1局所行になる）。
- 結果: **全8表が1ページに収まり、エラーなし（字形の接触・罫線との余白・枠の超過のエラーも出ない）**。2行のセル（p30・p32・p34 で101個、p31・p33・p35 で60個、p36 で3個、p37 で5個）は2局所行（21.6 pt＝原本と同じ）に入る。1局所行には入らない（2行で2局所行）。

| ページ | 局所行（紙面の横） 必要/使える | 局所列（紙面の縦） 必要/使える |
|---|---|---|
| p30 | 39/46（421.20/496.80 pt） | 48/50（見出しで1行使う） |
| p31・p33・p35 | 29/46（313.20 pt） | 48/51 |
| p32・p34 | 39/46（421.20 pt） | 48/51 |
| p36 | 41/46（442.80 pt） | 50/51 |
| p37 | 31/46（334.80 pt） | 50/51 |

- 列の幅（局所列）: p30〜35 は (2, 3, 3, 3, 3, 3, 3, 3, 4, 3, 3, 5, 4, 6)、p36・p37 は (2, 2, 2, 3, 2, 2, 2, 2, 4, 2, 4, 4, 4, 5, 4, 6)。原本より広げたのは「性能項目」の列だけ（原本 58.08 pt＝4列 → 5列。「安全性(破壊)」が 10.0 pt で 60 pt になり 4列（58.08 pt）に入らない）。p30〜35 の表の幅 421.20 pt は原本の表の幅（421.2 pt）と同じ。内容に合わせて最小の列数にすると p30 は 44 局所列まで減る。
- 方眼Excel で2行のセルの各行が別の局所行に載るか（xlsx-map の振り分けの規則）は確かめていない（`_map.py` が未完成のため）。

**A4.pdf のグリッドのまま（16.08×15.48）で入れる別の手段（参考）**

- 試した案: 「係数」と「値」を半角空白をはさんで1行に並べる（行送りは関係しなくなり、表の行は1局所行）。表の高さ（紙面の横）は入るが、表の幅（紙面の縦）が p30・p32 で 52 局所列（804.96 pt）、p31・p33 で 54、p34 で 50、p35 で 51 になり、使える 48 局所列（743.04 pt）を超える。文字の並び（セル内の行）も変わる。
- そのほかに、行送りを詰めず・表を分けず・文字を縮めずに入れる手段は見つからなかった。用紙を A3 にする・ページの /Rotate・`local_grid` をページのグリッドの縦横入替以外にする、はそれぞれ FR-013・FR-014・FR-027 に反する。

**非回転の p1〜29（A4.pdf のグリッドのまま）**

- `pages/*.json` のグリッド単位の書き方（`builder.build_block` の原本座標を使わない経路: `Paragraph`・`MathBlock`・`EquationGroup`（グリッド列のアンカー）・`Table`（グリッド列・整数行の自動の行の高さ）・`Spacer`・`Columns`/`Stack`・物理寸法の図）を、ページごとに `KeepTogether` にして `CANTILEVER_SOURCE_A4`（31列48行）で組んだ。**29ページすべてが1ページに収まる**。使う行数: p01 38、p02 32、p03 44、p04 20、p05 44、p06 20、p07 42、p08 29、p09 33、p10 28、p11 27、p12 31、p13 39、p14 41、p15 29、p16 44、p17 41、p18 41、p19 37、p20 26、p21 44、p22 44、p23 22、p24 43、p25 42、p26 45、p27 36、p28 35、p29 19（いずれも /48）。
- まだ見ていないこと: この経路は fixture 独自の部品（`SourceLiteral`・`SourceScript`・`CompactCell`）を使い、式は `term_columns="grid"` ではなく、区切り線は `Figure`＋`Line` のまま。作り直しでこれらを変えたときの行数は確かめていない（最も詰まっているのは p26 の残り 3 行）。
- スクリプト: `rotated_probe_a.py`（自動の行の高さ）・`rotated_probe_a_rows.py`（原本の行の高さを丸めて固定）・`rotated_probe_side.py`（係数と値を1行に並べる案）・`flat_pages_probe.py`（p1〜29）。

**作り直し（2026-10-20、案 (a)。ユーザー判断）**

進捗:

- ✅ Red（`--label cantilever-red-1`、8 failed）: `tests/integration/test_cantilever_grid_rules.py`（新設）。37ページが1ページずつ組める・ページのグリッド（p1〜29 は A4.pdf のグリッド、p30〜37 は 10.8×14.52）・回転表の `local_grid` が縦横入替のページのグリッド・配置と表のセルの辺がページのグリッドの線上・線は `Table`/`Rule`/`SideRule` の罫線の種類（分数線を除く）・書体は MS Mincho/Gothic、本文は 0.5 pt 刻み、添字はライブラリの `Script`・式の関係記号がグリッドの列の線の上に中心。どれも作り直す前の fixture で実際に失敗（p30〜35 の `原本再現できず`、0.01 pt の `local_grid`、53.52 pt の配置、図の `Line`、独自の添字、式の部分のタグなし）。
- ✅ Green（`cantilever-green-2`、8 passed）。片持ち梁の関連テスト全体 `cantilever-green-all-1`: **302 passed**。全テスト `cantilever-full-1`: 3435 passed、2 skipped、**2 failed（既知の PNG 正解2件だけ**: `test_cantilever_p01_37_golden.py::test_all_37_pages_match_approved_pixels`・`test_representative_golden.py::test_standard_report_matches_all_approved_golden_pixels`）。
- ✅ 全37ページが固定ページに収まる（Gate 2 後半）。使う行数: p01 35、p02 33、p03 44、p04 20、p05 44、p06 20、p07 42、p08 29、p09 33、p10 29、p11 29、p12 31、p13 39、p14 41、p15 29、p16 38、p17 35、p18 35、p19 31、p20 22、p21 32、p22 32、p23 22、p24 43、p25 42、p26 45、p27 36、p28 35、p29 19（/48）、p30 48、p31〜35 47、p36・p37 49（/51）。最も詰まっているのは p26 の残り3行と p36・p37 の残り2行。
- ✅ 保留の解除: `deferred.py` を削除し、`xfail(strict=True)`・`DEFERRED_DIFFERENCES` とその仕組み（`verify_appearance` の `deferred` 引数）を外した。p30〜35 と p36 の9セルを含む全37ページで `verify_pdf`（通常・grid とも 3345 項目）と `verify_appearance` が合格。
- ⏳ 式の `term_columns="grid"` と方眼Excel の `strict=True` の検査は lead の連絡待ち（指示どおり）。

設計判断（fixture。ライブラリは変更していない）:

- 組み方: 原本の座標の再生（`PageFrame`・0.01 pt の局所グリッド・`SourceCell`・`SourceLiteral`・`SourceScript`・`SourceTableInkFonts`・`continuous_table_rules` など）を廃止し、`pages/*.json` の縦の流れ（Stack・Spacer・Columns）をライブラリの部品で組む。`source-layout.json` は原本の位置をマスの整数倍へ寄せる手掛かりにだけ使う。各ページは `KeepTogether(Stack)`、p30〜37 は `PageSection(CANTILEVER_ROTATED_A4)`。
- 字下げ: 原本の見出しの段は 53.52＋14.52k pt に並ぶ（k=0〜9 を確認）。最も近い列へ丸めると 140.64 と 155.16 pt が同じ列になり段が消えるため、段 k を k 列の `Indent` にした（違う段は違う列のまま）。p30〜37 は自分のグリッドの最も近い列。
- 等号・結果・単位: 原本の位置に最も近い列。左辺・ラベル・結果・単位が入らない時だけ右へ（原本より左にはしない）。原本で1行の右辺が1行に入るよう第二等号を右へ広げる（空の右辺も1列取る。0列だとライブラリが結果を次の行へ送る）。同じアンカー・ラベル・字下げで書いた兄弟の式は列を共有する（p3 の桁ごとの行など。原本も揃っている）。
- 読み順: ライブラリは折り返した式の結果を最終行に置く（`equations.py` の `trailing`）。原本で結果が1行目にある式（p1・p2 の R_B）は1行目と続きの行を別の式（左辺なし・関係記号は空白）に、原本で結果だけが下の行にある式（p9〜11 の水平力4件）は結果を別の式にした。文字と読み順は原本どおり。lead 判断の材料: ライブラリに「結果を1行目に置く」選択肢があれば、この書き換えは要らない。
- 表: 列の幅・行の高さは原本の累積の境目をマスへ丸め、内容が入らない所だけ広げる（`_grid_spans`。各列を別々に丸めると表が右へ伸びた）。セルは `CellLines`（行送り＝行のピッチ、各行が1グリッド行）、上下の余白は接する罫線の太さ全体、左右は 2.0 pt＋罫線の太さ（0.6 pt では右寄せの数字が罫線に接して見えた）。原稿が原本の見出しの改行をつないでいる2セル（p32・p33「せん断」「力」）は原本の行で組む（文字が違えばエラー）。
- 区切り線: 計画の「`Rule` へ」は、実物が p16〜20 の式のまとまりを括る**縦線**（10本）なので、縦線の部品 `SideRule`（細、列の境目、括る式より左）にした。`Rule` は本文を横切る横線の部品。lead 確認事項。
- 添字: ライブラリの `Script`（scale 0.65 で 6.5 pt、下付き 1.92 pt・上付き 2.4 pt は原本の値）。p1 の人工斜体の D は `appearance.Sheared`（`shear_x` だけ変え、原本の 1.68 pt の添字の間隔になるよう送りを 0.68 pt 広げる）。p21・p22 の縦見出しの括弧は `appearance.VerticalGlyph`（`quarter_turns=3`、1字の枠の中央）。どちらも元の Literal のタグを保つ。
- 混合書体の見出し（p21・p22・p28）: run ごとの Paragraph / MathBlock を `Columns` で並べ、後の run は列の境目から（方眼Excel で別のセルになる）。
- 丸めは半分を切り上げ（`_nearest`。Python の `round` は偶数への丸め）。

検査の置き換え（`verify.py`・`verify_appearance.py`）:

- 残した原本との比較: 内容・読み順（`verify_source_order`・項目ごとの文字列・添字の役割・向き・ページ・文字の在庫）、書体（書体名・字形の向き・字形の幅＝人工斜体・0.5 pt 刻みの大きさ）。新たに各項目の行の構成（行ごとの字数）も原本と比べる（p21・p22 の Identity-V の括弧のある項目だけ、原本の原点が行から外れるため除く）。
- 置き換えた検査（新しい決まりどおりか）: 図の位置（原本 ±0.1 pt → 左上がグリッドの交点、物理寸法は原本どおり）、p16〜19 の括り線（原本 ±0.1 pt → `SideRule` の塗りの縦棒2本・罫線の種類の幅・列の線上・括る項目の字形より左・項目の範囲を覆う）、p3〜8 の結果・単位・等号（原本 ±0.1 pt → 列の線上・同じ列から始まる式で共有）、`verify_appearance` の `indent`・`baseline`・`spacing`・`equals`・`table` の原本の位置との比較 → `position`（項目の左上・セルの四辺がグリッドの線上、行の字形の基線が1本、原本の段の順を保つ）・`equals`（trace のアンカーが列の整数倍、描いた関係記号の中心がアンカー上）・`table`（原本に罫線がある辺に罫線、その辺がセルの辺上、太さは原本の 0.12→0.25・0.96→1.0）・`rotation`（回転表の `local_grid` がページのグリッドの縦横入替）。原本どうしの比較（陽性対照）は書体だけ（新しい決まりの検査は出力の trace が要る）。
- `verify._trace_regions` が `Indent` の `indent_pt` を足すようにした（以前は `PageFrame` が子の位置を trace に書いていた）。lead から連絡のあった `Indent` の入れ子の `indent_pt`（和になる変更）: fixture は各部品を高々1つの `Indent` で包むだけなので影響しない（`builder.py` の `Indent(` は1か所）。

テストの書き換え:

- `test_cantilever_appearance_builder.py`: 旧部品（`PageFrame`・`SourceCell` 等）の単体テストを、新しい部品（字下げの段・アンカー・読み順の分け方・改行の位置・混合書体・括り線・`Sheared`・`VerticalGlyph`・添字）の単体テストへ全面的に置き換えた。
- `test_cantilever_fixture.py`: `CompactCell` のテストを表のセルの組み方（行送り・余白・境目の丸め・空のセル・回転表の局所グリッド・見出しの改行）のテストへ。あふれのテストは 48 行のページに合わせて 49 行の Spacer に。保留のテストを削除。
- `test_cantilever_p01_37.py`: 保留の parametrize を外す。原本の位置を陽性対照にしていた等号・括り線の検査のテストを、出力の陽性対照と「原本の位置はグリッドに乗らないので拒否される」陰性対照・ずらし／短縮／幅の変更の陰性対照に置き換えた。
- `test_cantilever_source_appearance.py`: 新しい区分ごとの合格・陰性対照（書体・基線から外れた演算子・等号のずれ・罫線のずれ・段の順・回転表の局所グリッド・人工斜体・0.5 pt 刻み・罫線の太さ）、原本の書体の陽性対照（37ページ）、括弧の字形の形と位置。原本の位置との比較だけを確かめていたテスト（演算子の横位置）は削除。
- `test_cantilever_improvements.py`: 旧 adapter を経由した「公開部品での組み直し」の実証を、fixture 自身の表（全セルが1回の丸め・行送り＝行のピッチ）と3ページの公開部品の PDF に置き換えた。

目視（scratchpad の画像。既存の bundle・current.json は変更していない）: p1・p9・p16・p21・p26・p30・p36 の通常と p1・p30 の grid を 1.5 倍で確認。見出しの段・表・式の等号の列・図・括り線・回転表が読める配置で、文字の重なり・はみ出しはない。原本との見た目の差（位置・行の高さ・極細の罫線の太さ）は FR-027 で許した範囲。気づいた点: p1 の表は原本より右へ広い（列の境目を丸めた結果、右端 533 pt。原本 502 pt）。p21・p22 の縦見出しのある表で最後の行だけ高かったのは、結合セルの不足分を丸めた行の高さでなく内容の行数と比べていた不具合で、直した（原本で等しい4行は各2グリッド行。`test_rows_the_original_made_equal_stay_equal_under_a_merged_heading`）。行は1行ずつ丸め（原本で等しい行は等しいまま）、列は累積の境目で丸める。

**レビュー反映 (2026-10-20, ラウンド 1)**

レビュアー3体（silent-failure＋python、layout＋type-design＋pdf、計画整合＋テスト妥当性）。集約（重複は高い方へ）: CRITICAL 0 / HIGH 2 / MEDIUM 11（うち1件は lead 判断）/ LOW 約25。Red（`cantilever-r1-red`、39 failed）→ Green。

- ✅ H: 等号を 4 pt 以上ずらすと `equals` も `verify_pdf` も通っていた → 探す幅をやめ、trace の行ごとに「右辺の開始より左の等号は第一等号の線上」「結果のある行の最も右の等号は第二等号の線上」「それ以外の等号は右辺の字形にはさまれる」を必須にした。ずらし 2・6・16.08・−16.08 pt の陰性対照。
- ✅ H: 結果・単位の描いた位置は p3〜8・p16〜19 以外で検査されていなかった → 全ページの式の行で「結果の最後の字形の右端が result_right」「単位の最初の字形の原点が unit_start」（右辺の終わりは trace の項の列から求める）。p12 の結果・単位を −6 pt ずらす陰性対照。
- ✅ M: 図の位置が自分の配置に結び付いていなかった → trace の `figure_id` の配置の左上と PDF の画像の左上の一致を必須に（1マス・1行ずらしの陰性対照）。
- ✅ M: p20 の括り線が未検査、高さ 100 pt の閾値で短い括り線が落ちていた → 括り線の検査を `_group_bars` に分けて p16〜20 に、閾値は 20 pt（p20 の最短 77 pt）。p20 の陰性対照（ずらし・短縮・幅・欠け・1列右）。
- ✅ M: 原本 PDF の hash の陰性テストが消えていた → `test_source_pdf_hash_is_checked_before_reading_the_original`。
- ✅ M: 新しい部分検査の陰性対照の不足 → 項目のグリッド外れ（trace を 0.5 pt）、アンカーの列外れ（+0.3 pt）、回転の記録の欠け、原本にある罫線の欠け、段の順、ブロックの中での文字のずれ。
- ✅ M: 37ページ全体の `verify_appearance` のテストがない → `test_appearance_and_grid_rules_hold_on_all_37_pages`。
- ✅ M: 兄弟の式のアンカーの多数決で p14 の第二等号が原本の最も近い列より左になった → 兄弟（family）の判定を原稿の `anchors` の値から「原本の最も近い列が同じ」に変え、アンカーは式の原本の左端からの距離で丸める（式の左端の段によらない）。全ページの全アンカーが自分の原本の最も近い列以上であるテスト。
- ✅ M: 段の写し方を図にも使っていた（p23・p24 の正面図が2列右）→ 図は最も近い列。文字の部品は段のまま（最も近い列にすると p12・p15 で段の順が崩れることを確かめた）。
- ✅ M: `font_profile()` の読み直しで組立てが組版の約7倍遅い → 入力は1回だけ読む（`_fixture_json`、公開の読込みは複製を返す）。
- ✅ M: 使われない古い組版の値が `pages/*.json`・`font-profile.json` に残り、原稿の `anchors` が兄弟の判定に効いていた → `pages/*.json` から削除（表の `columns`・`horizontal_rules`・`vertical_rules`・`border_width`・`padding` 等 217 件、式の `anchors` 190 件、区切り線の `rows` 10 件、セルの `padding`・`size`・`line_advance` 20 件。セルの `size` は font-profile の値と一致することを確かめてから）。書いてあればエラー。`font-profile.json` の `body_size`・`rotated_body_size`・`spacing_ratio`・`script_size_ratio`・`subscript_offset`・`superscript_offset` を削除。
- ⏳ M（lead 判断）: 区切り線を `Rule` でなく `SideRule` にした件。DESIGN の FR-026 と計画の文言は「Rule へ」。
- ✅ L（同ラウンドで対応）: 死んだ分岐、`_grid_spans` の説明、結合セルの幅（`_widen_for_spans`）、位置の決まった混合書体の run の幅の検査、文字列の数式見出しの run、`Sheared` の大きさの依存と入力検査、縦向きの括弧を原本で回したセルの行に限る、括り線の中身が stack でない時のエラー、式の記録の数の不一致・行の文字のない右辺の行・単位だけの別行の結果をエラーに、行の構成の検査の除外を固定の4項目に、`rotation` の件数を記録ごとに数え `turns` も確かめる、関係記号の幅を EquationGroup と同じ測り方に、式の幅は container の列数で、陰性対照の `match` を固有の文に、37ページ一括と1ページずつの組みの一致。
- 持ち越し（LOW）: 同じ段の項目が同じ列に揃っているかは見ていない／ReportLab の既定の Helvetica が使われない資源として PDF に載る（ライブラリの範囲）。

**式の項の列（FR-025、2026-10-20 lead の連絡で着手）**

- 全ての式を `EquationGroup(term_columns="grid")` にした。右辺の最上位の各項目を1項（添字は直前の項目の項）とし `TermStop` で区切る。寄せ方は演算子が中央・数値が右・その他が左、同じ列で式どうしが食い違えば左（ライブラリが食い違いを ValueError にするため）。
- 最初は項を全部分けると 13 行で結果が下の行へ行き（読み順が変わる）、14 行が退避（`term_fallback`）した。対処: (1) 項の数が同じ連続した式ごとに1つの `EquationGroup`（列の共有は同じ形の式どうし。形の違う長い式が他の式の列0を広げていた。グループは同じアンカーで `Stack` に入れ、元の ID を保つ）、(2) ライブラリで組んで原本の行を保てない run だけ右辺全体を1項（入れ子の Row）にする。結果: 項の列の式 238 行、項なし 44 行、退避 0、結果の下の行への移動 0。全37ページの行数は項の列にする前と同じ。（訂正、ラウンド2: 238 行には右辺全体を1項にした行を含む。ラウンド2の後で 16 行・9グループ。下の「レビュー反映 ラウンド 2」）

**方眼Excel の strict 検査（2026-10-20 lead の連絡で着手）**

- Red: 作り直す前の fixture（HEAD を `git archive` で scratchpad に展開。p30〜35 を除く31ページ）では、`render_xlsx` が strict でなくても `XlsxError: sheet '片持ち梁' page 1: '13.850' moved to free cells passes the right edge of the grid (31 x 48 cells)` で書き出せない。
- 作り直した fixture の最初の結果（strict なし）: シート2枚（`片持ち梁` p1〜29、`片持ち梁_2` p30〜37、回転表はセル）、図形への切替え 0、タグのない命令 0、ずらし 24（結果の数値・`#######` が第二等号のセルにかかる 20 件、p21・p22 の縦見出しの「）」4件）、数値のまま書けない数値 89。
- 対処: (1) 結果に方眼Excel のセル（第二等号のセル〈関係記号の送りが2列なら2セル〉の右から result_right まで、Excel の画面の字の幅〈字ごとに画素へ切上げ〉＋余白×2 が入る数）を与えるよう result_right・第二等号を決める。ただし原本の行を保つこと（読み順）を優先し、保てない時はライブラリで組んで確かめながらセルを減らす。(2) p13・p14 の地震時の反力は段の列（7）では結果と単位が本文の幅に入らないため、原本の最も近い列（6）にする（段の浅い文字の部品より右である時だけ）。(3) 縦見出しのセルは各行を自分のグリッドの行の中央に置く（`CellLines.first_baseline`、セルは上寄せ）。7行を8行に中央寄せすると全行が行の境目をまたぎ、方眼Excel で回した括弧とそのほかの字が別の行に割り当てられていた。
- 結果: `render_xlsx(..., strict=True)` が合格。ずらし 0・図形への切替え 0・タグのない命令 0。数値のまま書けない数値は p2 の7件（`537.29` など。セル2つ 31.5 pt に対し、builder の見積り〈`_excel_cells`：Excel の画面の字の幅を字ごとに画素へ切り上げる計算〉で 36.3 pt。Excel での実測ではない。builder がライブラリで組んで、3つ目のセルを与えると原本の行を保てないことを確かめて減らした）。`dropped` は表の継ぎ目の補いの線 2065 件だけ（0.125 pt の補い 1799 件と 0.5 pt の補い 266 件。補う線の端は補われる線が描くので、方眼Excel の罫線には影響しない）。テスト `test_grid_excel_of_all_37_pages_is_strict`。
- 目視（scratchpad、`v2-*.png`）: p1・p9・p13・p16・p21・p26・p30・p36 の通常と p9・p16・p21 の grid。項の列で右辺の項の間が広がった（p1・p16）が、行は原本どおりで重なりなし。p21 の縦見出しは1字1行。


**レビュー反映 (2026-10-20, ラウンド 2)**

レビュアー2体（silent-failure、layout＋計画整合）。集約: CRITICAL 0 / HIGH 1 / MEDIUM 11 / LOW 約17。残った指摘の大半は「部品の中の字の位置が PDF の検査で何にも結び付いていない」（項・左辺・ラベル・セルの字・行の基線・入れ子の段落・括り線の位置）だった。個別に検査を足す前に trace を確かめると、描画命令はすべて意味のタグ（式の部分・項の列 `first_column`/`columns`/寄せ方/余白、セル、セルの行、段落、括り線）を持っていた。そこで (1) PDF が trace の命令をそのまま描いていること（`placement`）と、(2) タグ付きの命令が規則を満たすこと、の2段に分けた。Red `cantilever-r2-red-1`（21 failed：区分 `placement` がない、各規則の検査がない）→ Green。

- ✅ H: 項の位置が PDF で検査されていなかった（p15 の `13580.00` を 64.1 pt ずらしても通る）→ `placement`: 全 Text 命令（37ページで 6889）の字形が命令の原点から方向に沿って送りの中に並ぶこと（±0.02 pt）、全 Line（4569）と括り線の Rectangle（10）が端・太さ・矩形どおりであること、命令にない字形・線がないこと（debug grid の線は色と太さで除く）。`equals`: 各項の字が自分の列（式の左端＋`first_column`×ピッチから `columns` 列）の余白の内にあり、寄せ方（右・左・中央）どおり。陰性対照: 字形を +64.1・±1・下へ 0.5 pt（`placement`）、命令にない字形、括り線のずらし・欠け、表の罫線のずらし、trace ごと項を ±1・+64.1 pt・`×` を +1 pt（`equals`）。
- ✅ M: 第二等号の列をまたぐ字形があると、その行の結果・単位の検査を黙って飛ばしていた → trace でその行に結果があれば `a glyph runs across the second relation` で拒否（結果の無い行だけ飛ばす）。結果を第二等号の上へ動かす陰性対照（読み順は保つ）。
- ✅ M: 左辺・ラベルの位置が未検査 → ラベルは式の左端から始まる、左辺の右端は同じグループの行でそろい関係記号の手前で終わる（ライブラリの組み方 `first − first_left − gap`）。陰性対照（左辺の最後の命令を −2 pt、ラベルを +2 pt）。
- ✅ M: 入れ子の段落（p16〜19 の「可動支承に働く鉛直荷重」など、領域の左端を持たない Stack の中）の位置が未検査 → 表と式の外の左寄せの段落・数式の各行（全角の本文の字、添字・分数を除く）の最初の命令が列の線上（`position`）。
- ✅ M: セルの字の位置が未検査（M-4）・縦の行の位置（M-5）→ `table`: セルの各行がセルの中で寄せ方どおり（中央は左右の罫線の差の半分＝0.76 pt 以内、左右寄せは余白 2〜3.5 pt）、同じ行の字は1本の基線、行の間はちょうど行のピッチ×行番号の差（回転表は局所グリッドの 10.8 pt）、行のまとまり（命令の枠）が中央寄せのセルの中央（0.76 pt 以内）・上寄せのセルの上の余白の内。全セルで測った中央からのずれは最大 0.5 pt。陰性対照（下へ 2 pt、1行上へ、右へ 3 pt）。
- ✅ M: 括り線の x が trace に結び付いていなかった（M-6）→ `placement` で矩形が命令どおり、`position` で中心が列の線・上下が行の線。陰性対照（+1 pt）。
- ✅ M: 括り線の陰性対照の名前が「1列右」なのに2列ずらしていた → 1列右は括る字の左のままで、`_group_bars`（字より左か）では拒否できないことを確かめた。陰性対照は「字の上（2列右）」に改名し、各括り線の列（原本の縦線の段の列：p16〜19 は 6、p20 は 5、各ページ2本）を `test_bracket_bars_are_side_rules_of_a_border_style_on_column_lines` で固定した（1列のずれもここで落ちる）。本数は `== 10`（L-8）。
- ✅ M（M1）: p14 の起点側・終点側の反力が原本で同じ左端なのに列が1つ違った → 地震時の反力に最も近い列を使う例外（`_result_needs_nearest_column`）をやめ、式も段の列に戻した。代わりにアンカーをページの列で決める（下）ことで結果と単位が本文に入る。原本で同じ左端の式は同じ列（`test_groups_with_the_same_original_left_take_the_same_column`、43組）。
- ✅ M（M2）: 原本でそろっていた等号・結果・単位が、段の違うグループの間でずれていた（p16〜19 の T1・T2 とストッパー、p13・p14 の断面力と反力）→ アンカーを「式の原本の左端からの距離」でなく「原本の位置に最も近いページの列」で決める（`_source_anchors`）。原本の列がすべて同じ式はまとめて決め（`_family_anchors`）、一部の列だけ同じ式どうしはその列を右側にそろえる（原本の行を保てる時だけ、`_equation_anchors`）。原本で同じ列の組 2976 のうち、そろわないのは p13 の断面力と反力の第二等号の2組だけ（反力は右辺のために 25 列目が要り、断面力をそこへ動かすと単位が本文に入らない＝ライブラリで組んで確かめた）。`test_anchors_the_original_aligned_stay_aligned_across_groups` が例外をこの2組に固定し、例外が避けられないことも確かめる。Red はそろえる段を外した builder で確かめた（p3 などの組がずれて失敗）。`verify.py` の p3〜8 の列の共有は「出力で左端が同じ式」から「原本で同じ位置（0.5 pt 以内）だった式」に変えた（陰性対照: 結果・単位を1列ずらす）。
- ✅ M（M4）: 右辺全体を1項にした run は「退避なし」のテストに掛からない → `WHOLE_TERM_RUNS` に固定（p1・p2・p12・p13・p19 の9グループ・16行）。記録の「238 行（うち 14 行は1項）」の数を訂正（上）。
- ⏳ M（M3、lead へ）: `builder._excel_cells` が方眼Excel の写像の非公開の `gridlayoutpdf.renderers.xlsx._units`（`PIXELS_PER_PT`・`excel_column_width_pt`）を読む。セル数の見積りを公開の関数にしてほしい（または公開しない方針の判断）。src は触っていない。
- ⏳ M（M5、lead へ）: commit の履歴: `deferred.py` の削除が lead の commit 89bba39 に入り、89bba39〜c1e9475 のテストは `deferred` を import する（その commit 単独ではテストが通らない）。
- ✅ L: 原稿でなく font-profile の古い鍵も書いてあればエラー（`_reject_obsolete_profile_keys`、Red `cantilever-r2-red-2` 6 failed）。`_keeps_original_lines` は右辺の折り返し（`continuation`）も拒否。p09 の run のアンカーを全項目で比べる。※ は `placement` で検査される（`_characters` の除外は書体の比較だけ）。README の組み方（アンカー・そろえ方・1項の run・縦見出し・SideRule の判断待ち・検査の区分）を更新。記録の「36.3 pt」「長さ0」の書き方を訂正（上）。
- 持ち越し（LOW）: `_SCRIPT_X_EM`（.1）が `Sheared` の既定と同じ値の重複（ライブラリの Script の横の間隔の公開値がないため）。

テスト: 片持ち梁の関連 `cantilever-r2-green-5` **359 passed**。全テスト `cantilever-full-3`: 3700 passed、2 skipped、**2 failed（既知の PNG 正解2件だけ**）。全37ページ: `verify_pdf`（通常・grid）3345 項目合格、外観 0 件（`placement` 10449・`equals` 3471・`table` 29736・`position` 35361 件の検査）、`render_xlsx(strict=True)` 合格（ずらし 0・図形への切替え 0・タグなし 0・数値のまま書けない数値 p2 の7件）、行数はラウンド1と同じ（p13 も 39 行）。目視（scratchpad `img/r2-p13-grid.png`・`r2-p16-grid.png`）: p16 の T1・T2 の結果とストッパーの行が同じ列、p13 の重なり・はみ出しなし。

**レビュー反映 (2026-10-20, ラウンド 3)**

レビュアー2体（silent-failure、layout＋計画整合）。集約: CRITICAL 0 / HIGH 1 / MEDIUM 6 / LOW 17。Red `cantilever-r3-red-1`（13 failed：先頭が空白の命令・破線の罫線・タグのない命令・タグを失ったセル／式の行・1行のグループの左辺・セルの 0.7〜1.4 pt のずれ・debug grid・規則ごとの件数）→ Green。layout の3件の Red はそれぞれの修正を外した builder（monkeypatch、`scratchpad/red_r3.py`）で確かめた（p3 の × が2列、結果の間隔 16.2 列）。

- ✅ H（layout H1）: 右辺が空で結果だけの行（p16〜20 の「＝ 8 576.98 kN」、p20 の Hsd）の結果が等号から 15〜16 列離れていた。原因は、結果のない長い右辺（同じグループの別の run）を1行に入れるために第二等号を広げていたこと。結果のない右辺はライブラリが全幅を与えるので、第二等号を広げる判定（`_grid_width(with_result=True)`）を結果のある式の右辺だけにした。結果の手前の字からの間隔は最大 4.4 列（`test_results_stay_near_what_precedes_them` で 4.5 列以下に固定）。
- ✅ M（layout M1-new）: 原本で数 pt 違う結果の右端（p3 の 345.32・347.84・350.36 pt）が列の中点をまたいで別の列に分かれ、p3〜7 の「×」も2列に分かれていた → そろえの判定を「最も近い列が同じ」から「原本で 6 pt 以内」に（`_source_positions`・`ALIGNED_SOURCE_PT`）。原本で右辺の始まり（と第一等号）が 6 pt 以内のグループどうしは同じ形の式の各項の最小の幅を `TermStop.width` でそろえる（`_shared_term_widths`。入らなければグループ自身の幅、それでも入らなければ1項）。6 pt 以内の組 3344 のうちそろわないのは p13 の2組だけ（前と同じ）。p3〜7 の「×」は各ページ1列（`test_operators_the_original_set_in_one_column_share_a_column`）。
- 一部対応（layout M2-new）: 「Hsd ＝ 0.00 kN」の等号と結果の間が 4.4〜5.4 列 → 空白の第二の関係記号にはセルを取らないようにして 4.4 列以下に。残りは、空の右辺に1列要ること（ライブラリの制約）と、同じグループの `#######` が方眼Excel で求めるセル（数値だけにセルを与えると方眼Excel でずらし5件が出ることを確かめた）による。読み順と方眼Excel のセルを優先した結果として残す（lead 確認事項に追加）。
- ✅ M（silent M-1）: 先頭が空白の命令（9件）は字形を 8 pt ずらしても `placement` を通った → 横書きで傾けていない命令は、最後の字形の右端が原点＋送り（±0.02 pt）であることも必須に。p28「　[」を −8・−2 pt ずらす陰性対照。
- ✅ M（silent M-2）: 規則が 0 件でも区分の合計に隠れて通った → report に規則ごとの件数 `rule_checks`（`placement.text`・`placement.rule`・`placement.tag`・`equals.term`・`equals.label`・`equals.lhs`・`position.paragraph`・`position.side_rule`・`table.cell` など）を出し、37ページのテストで固定（括り線 10、項の数＝trace の項の数 906 など）。加えて、意味のタグのない命令・PDF に字があるのにタグ付きのセルの行がないセル・タグ付きの命令がない式の行をエラーにした（陰性対照: p16 のタグを消す、p30・p36 の `cell_lines` を消す、p9 の `equation_line` を消す）。
- ✅ M（silent M-3）: 1行のグループ（252 のうち 230）では左辺の検査が空振り → ライブラリの組み方どおり「左辺の右端＝第一等号の線 − グループの関係記号の左側の最大 − 原稿の gap」を ±0.01 pt で必須に（gap は `pages/*.json` から）。p3 の1行の式の左辺を −2 pt の陰性対照。
- ✅ M（silent M-4）: セルの許容値（中央 0.76 pt、余白 2〜3.5 pt）が広く、0.7〜1.4 pt のずれが通った → trace の表の罫線（境目ごとの最も太い線）から余白を正確に求める（上下＝罫線の太さ、左右＝2 pt＋罫線の太さ）。寄せ方・行のまとまりの上下中央は ±0.01 pt。上寄せのセル（p21・p22 の縦見出し）は各行が自分のグリッドの行の中央。陰性対照（p1「G2」右・下 0.7 pt、p1「520.0」・p26「0.00」左 1.4 pt）。
- ✅ L: `placement` で罫線の色・破線、矩形の塗りも照合（破線にした罫線の陰性対照）。`_train_anchors` は全ての組を比べる。未知の寄せ方・縦の寄せ方・段落の寄せ方は ValueError。セルの検査の文言を分けた（行送り／上下中央／行の中央）。debug grid の PDF の `placement` のテスト（除いたグリッド線が 32＋49 本）。README の最頻値の説明。
- 持ち越し（LOW）: 添字（82件）と段落の行の2つ目以降の命令（47件）の位置はライブラリの組み方の範囲として規則を置かない（`placement` で trace どおりであることは確かめる）。`_family_anchors` の `chosen or (values, True, 0)`・`_equations` が keeps を捨てる経路は今は通らない（37ページで `WHOLE_TERM_RUNS`・行の構成・`numbers_as_text` の固定が崩れを検出する）。`texts_clipped` 2件（p15 の見出し、p36 の `EQ`）は固定していない。1項の run の項の間が詰まって見える（p12・p13）。

テスト: 片持ち梁の関連 `cantilever-r3-green-3` **373 passed**。全37ページ: `verify_pdf`（通常・grid）3345 項目、外観 0 件、`render_xlsx(strict=True)` 合格（ずらし 0・図形への切替え 0・タグなし 0・数値のまま書けない数値 p2 の7件）、行数は前と同じ。目視（scratchpad `img/r3-p03-grid.png`・`r3-p16-grid.png`・`r3-p20-grid.png`）: p3 の × と結果がそれぞれ1列、p16 の結果だけの行が等号の近く。全テスト `cantilever-full-4`: 3759 passed、2 skipped、20 failed（既知の PNG 正解2件、この担当の重複して貼った検査1件〈直して `cantilever-r3-green-3` で合格〉、Step 10 の比較スクリプトの作業途中の17件〈`'ClipLoss' object has no attribute 'close'`。`scripts/compare_xlsx_pdf.py` は未追跡で、この担当は触っていない〉）。

**回転表の字をローカルの行に収める（2026-10-20 lead の追加の条件）**

- 条件: 方眼Excel と PDF の比較で、p30〜37 の回転表の各行の字（10 pt）がローカルの行（10.8 pt、ページの列）の境目をまたいでいた。各表示行の字形（`command_bounds`）をそのローカルの行の中に収め、それを確かめる検査を足す。
- 実測（作業前）: 表の Text のうち行の境目をまたぐもの: 回転表 2601 件中 1509 件（p30〜37）。回転していない表でも 1363 件中 128 件（p1・p21〜29。2行分の高さのセルに1行を中央寄せすると、行の境目に字がかかる）。原因は、`CellLines` の行のまとまりをセルの中で中央寄せしていたこと（行の位置がグリッドの行に合わない）。
- 対処（fixture だけ、ライブラリは変えていない）:
  - 全ての表のセルを上寄せにし、`CellLines.first_baseline` で各行を自分のグリッドの行に置く（`builder._row_placement`）。行のまとまりはセルの中で行単位で中央（余りが奇数なら上）。各行の字の箱が行の中に入り、端の行は罫線から離れる基線の範囲の中央に基線を置く。端の行が罫線に当たって入らない時は1行ずらす。上下の余白は0にした（行の高さは今までどおり罫線の太さを足して決めるので、行数は変わらない）。
  - Table は行ごとの部分の端の罫線から、字を罫線の太さ全部ぶん離す（`tables._inner_edges`）。そのため、離す量は罫線の太さ全部にした（半分では `content lacks clearance from border strokes` で止まることを確かめた）。
  - p30〜37 の下付き添字は、10 pt の基底（上 8.59 pt）と 6.5 pt の添字（下 0.92 pt）が 10.8 pt の行に入るよう、基線から 1.0 pt 下にした。原本の 1.92 pt のままでは1行に 11.43 pt 要る。ほかのページは 1.92 pt のまま。
  - 回転表の基線は ReportStyle の `baseline_offset` ではなく、セルの `first_baseline` で決めた（表の中の行は `CellLines` が置くため）。
- 結果: 行の境目をまたぐ Text は回転表・回転していない表とも 0 件。行数は前と同じ（p30 48、p31〜35 47、p36・37 49 / 51）。`render_xlsx(strict=True)` 合格（ずらし 0・図形への切替え 0・タグなし 0・数値のまま書けない数値 p2 の7件）。全37ページの `verify_pdf` 3345 項目と外観 0 件。
- 検査:
  - `test_cantilever_grid_rules.py::test_each_table_line_keeps_its_glyphs_inside_one_local_row`（各表の全 Text の字形が1つのローカルの行の中。回転表 2601 件）。Red は、行のまとまりを中央寄せにする前の置き方に builder を差し替えて確かめた（p1「雪荷重」が行をまたいで失敗。`scratchpad/red_rows.py`）。
  - 外観の `table` も、上寄せのセルで「各行の字が自分のグリッドの行の中」「行は連続」「行単位で中央（1行以内）」「端の行が罫線に当たらない」「基線は空きの中央（±0.01 pt）」を確かめるようにした。p30 のセルの行を1 pt ずらす陰性対照も足した。
  - 見た目（scratchpad `img/r4-p30-crop.png`・`r4-p21-grid.png`）: p30 の字はページの列の中に収まっている。p21 の2行分の高さのセルの1行は上の行に置かれる（以前はセルの中央）。
- テスト: 片持ち梁の関連 `cantilever-rows-green-2` **376 passed**。

**レビュー反映 (2026-10-20, ラウンド 4)**

レビュアー2体（silent-failure、layout＋計画整合）。集約: CRITICAL 0 / HIGH 1 / MEDIUM 4（うち lead 判断1件）/ LOW 12。

- ✅ H（silent H-1）: セルの行をグリッド1行ぶん丸ごとずらしても通った（レビュアーの実測: builder を「入るなら1行下」に差し替えて 37ページで 0 件。中央の判定が ±1 行を許し、先頭の行の位置を基準にしていた）→ 上寄せのセルの検査を `_top_aligned_rules` に分け、builder の選び方（行単位で中央、同点は上、罫線に当たれば次の候補、空きの中央の基線）を trace の字の箱と罫線の太さから組み直して、行と基線が一致することを必須に。陰性対照 `test_cell_lines_moved_a_whole_row_are_rejected`（p1・p26、builder を1行下に差し替え）。
- ✅ M（silent M-1）: 基線のない行（p21・p22 の回した括弧 8 行）は行の中で 2 pt 動いても通った → 同じセルの全角の字の em の中心に合うことを必須に（`cell line without a baseline is off its row's em box`）。陰性対照（±2・0.3 pt）。
- ✅ M（silent M-2）: `rule_checks` の固定が粗かった → 規則名を分けた（`equals.lhs_gap`／`equals.lhs_group`、`table.cell_align`・`cell_baseline`・`cell_spacing`・`cell_rows`・`cell_room`・`cell_turned`・`cell_centre`・`cell_coverage`）。37ページのテストで trace から数えた件数と等式で固定（左辺と関係記号のある行の数＝`lhs_gap`、タグ付きのセルの数＝`cell_centre`＝`cell_room`、`cell_turned`＝8、`placement.rule`＝Line・Rectangle の命令の数）。
- ✅ M（layout M2）: p26 の6表・p27 の5表は原本で x と列の幅が同じなのに、出力で列の境目が1列ずれていた → 原本で同じ x・同じ列の幅の表は、どの表の内容も入る同じ列にする（`_same_columns`、`_table(needs_only=True)`）。`test_tables_the_original_drew_alike_keep_the_same_columns`（Red は `_same_columns` を外して確かめた: p26 で (5,3,2,3,…) と (5,3,3,2,…)）。行数は同じ。
- ⏳ M（layout M1、lead 判断）: 1行だけのセルが2行以上の高さを持つ時、余りが奇数だと上（回転表では左）の行に入る。回転表で 1381 セル、ほかで 86 セル。p21・p22 では表が「1行おきに空行」に見える。lead の条件「各表示行の字形がローカルの行の中」を満たすための結果。レビュアーの代案: 方眼Excel の写像は字が1つのセルを結合セルにして縦の寄せ方で置くので（`_map.py` の `table_cells`）、1行だけのセルはセル全体の中央（字は行の境目にかかる）に戻せる見込み。ただし lead の条件を「複数行のセルの各行」と読み直すことになる。件数は `test_one_line_cells_in_two_rows_sit_in_their_upper_row` に固定（罫線を避けて1行下に入る見出しのセル 16 も）。
- ✅ L: `_ALIGNED_PT`（`verify.py` の列の共有）を builder と同じ 6 pt に。`_row_placement` の単体テスト（同点は上、罫線で1行ずらす、入らない時のエラー）。回転表の下付き 1.0 pt・ほかのページ 1.92 pt のテスト、`_with_subscript_drop` は分数の中もたどる。検査とbuilder の罫線の余裕の値が等しいことのテスト。陰性対照を期待する文言で一致させた。`test_results_stay_near_what_precedes_them` は確かめた行の数（200 超）も確かめる。`_authored_gaps` の説明（既定 2 は builder の値）。README（下付き 1.0 pt、`table` の規則の説明、同じ列の表）と検査の docstring を更新。
- 持ち越し（LOW、記録のみ）: p12 の7項の2グループと p10 の forces/reactions は、項の幅をそろえると原本の行に入らない・第一等号の有無が違うため、項の列がそろわない（原本で6 pt 以内の項の始まり 3224 組のうち 35 組）。p3〜8 の空白の第一の関係記号も1列取るので、ラベルと右辺の間が原本より広い。回転表の下付き 1.0 pt と lead の条件は DESIGN・計画にはまだ書いていない（lead の判断で DESIGN へ）。
- Red の根拠: H-1・M-1 はレビュアーの陰性実験（修正前の検査で 0 件）、M2 は monkeypatch（`scratchpad/red_cols.py`）。

テスト: 片持ち梁の関連 `cantilever-r4-green-3`（1件はテストの数え方の誤りで、直して `cantilever-r4-green-4` grid_rules 19 passed）。全37ページ: `verify_pdf` 3345 項目、外観 0 件、`render_xlsx(strict=True)` 合格（ずらし 0・図形への切替え 0・タグなし 0・数値のまま書けない数値 p2 の7件）、行数は同じ。

**1行だけのセルはセル全体の中央に（2026-10-20 lead の判断 (a)）**

- lead の判断: 条件の意図は「Excel で1つのセル（行）に置かれる字が行の境目をまたがないこと」。写像は字が1つだけのセルをセルの範囲全体に結合し縦の寄せ方を写すので、1行だけのセルはセル全体の中央（元の valign）でよい。条件は「複数行のセルの各表示行の字形はローカルの1行の中」と読み直し、1行だけのセルはセルの範囲の中に収まることを検査する。
- 対処: `builder._table` は1行だけのセルを行の置き方（`_row_placement`）から外し、元の `valign="middle"`・上下の余白＝罫線の太さに戻した。複数行のセル（682 セル）は前のとおり行ごと。行数は同じ。
- 検査: `test_each_line_of_a_multi_line_cell_keeps_its_glyphs_inside_one_local_row`（複数行のセル 682 の各行の字が1つのローカルの行の中・連続した行、1行だけのセル 2322 の字がセルの中）、`test_one_line_cells_stay_centred_and_multi_line_cells_are_set_row_by_row`（行の置き方を使うのは複数行のセル 682 だけ。前の「上の行に入る」件数の固定は外した）。外観の `table` は、1行だけのセルはセルの上下の余白の間の中央（±0.01 pt）とセルの中、複数行のセルは `_top_aligned_rules`。1行だけのセルを上寄せにすると・複数行のセルを中央寄せにするとエラー。
- 結果: 37ページの `verify_pdf` 3345 項目と外観 0 件、`render_xlsx(strict=True)` 合格（ずらし 0・図形への切替え 0・タグなし 0・数値のまま書けない数値 p2 の7件）。片持ち梁の関連テストは `cantilever-a-green-1`（2件は検査の件数の数え方と陰性対照のページの選び方の誤りで、直して `cantilever-a-green-2` で合格）。
- `scripts/compare_xlsx_pdf.py --example cantilever --out <scratchpad>/compare-cantilever`（compare 担当の作成中のスクリプト。編集していない）: 終了コード 1。checks は `positions` だけ False（`opens_without_repair`・`readback`・`strict`・`no_hashes`・`page_count`・`page_size`・`no_extra_text` は True）。文字片 5418 のうち一致 5418・見つからない 0・**範囲外 1**（p15 の見出し「a)使用時の照査における…」、セル F677。失敗は `clipped`：Excel の印刷で最後の字が切れる。方眼Excel の `texts_clipped` の2件の1つで、Excel の字幅が PDF より広いため。位置のずれは dx 2.57 pt・dy 0.56 pt で許容内）。最大のずれは dx 12.72 pt・dy 8.122 pt、紙の軸で測った場合の範囲外は 6。Excel 16.0 build 20326、プリンターは DocuWorks Printer。

**lead 確認事項（cantilever、未決）**
- 区切り線を `Rule` でなく `SideRule` にした（DESIGN FR-026・計画の文言は「Rule へ」。ラウンド1）。
- `builder._excel_cells` が非公開の `gridlayoutpdf.renderers.xlsx._units` を読む（公開の見積り関数がほしい。ラウンド2 M3）。
- commit の履歴: `deferred.py` の削除が 89bba39 に入り、89bba39〜c1e9475 のテストは `deferred` を import する（ラウンド2 M5）。
- 結果だけの行（p16〜20 の Hsd・Hbd ＝ 0.00 など）の等号と結果の間が 3.4〜4.4 列残る（ラウンド3 M2-new。空の右辺の1列はライブラリの制約、残りは方眼Excel のセル）。
- p13 の断面力と反力の第二等号の2組はそろわない（ラウンド2）。
- （済み、lead の判断 (a)）1行だけのセルはセル全体の中央に戻した。
- p15 の見出し（F677）は Excel の印刷で最後の字が切れる（compare の範囲外 1、`texts_clipped`）。
- 回転表の下付き添字を原本の 1.92 pt から 1.0 pt にした件と、lead の条件「各表示行の字形がローカルの行の中」を DESIGN（FR-027）・計画に書くかどうか。
- 項の列がそろわない所（p12 の7項の2グループ、p10。ラウンド4 L1）と、空白の第一の関係記号の1列（p3〜8）。

#### grid-terms（Step 6）

担当 grid-terms（サブエージェント）。2026-10-20。編集したのは `src/gridlayoutpdf/equations.py`・`docs/api.md`・`examples/representative_report.py`・`tests/unit/test_equation_grid_terms.py`（新設）と、この節・担当表の行・計画の Step 6 の行だけ。

**決めた API（実装済み）**

- `EquationGroup(..., term_columns="packed")`。値は `"packed"`（既定。今までの pt で詰める並べ方）か `"grid"`。名前の流儀は `TermStop(align=...)`・`BreakHint(mode)` と同じ文字列の選択肢にした。それ以外の値（`"Grid"`・`None`・`True` など）は ValueError。`"grid"` と `term_gap` を一緒に渡すと ValueError（黙って無視しない）。
- `"grid"`: 各項の列は右辺の開始列（`rhs_start_pt` と同じ整数の列。ブロック左端から数える）から隙間なく続く。列数は「その列の最も広い項（`TermStop.width` があればそれ以上）＋その式の文字サイズでの片側の余白×2」が入る最小の整数。項のない列（幅0）は0列。項は列の左右から余白を除いた範囲に `align` で置く（Excel のセルの文字の置き方に合わせる）。1行に入るかの判定・結果の専用行・退避（fallback）・エラーは `"packed"` と同じ関数で行い、退避した式の配置は `"packed"` の退避とまったく同じ（テストで部品の等価を確認）。
- metadata（`"grid"` の時だけ、退避していない列揃えの式の各行に追加）: `term_columns_grid` = 各列の `(開始列, 列数, align)`（ブロック左端からの整数の列）、`term_cell_padding_pt` = その式で使った片側の余白。`term_columns_pt`（左端・幅・揃え、pt）はそのまま残す（`"grid"` では列の幅も整数の列）。ページの metadata の配置には `col`（ブロックの左端のページの列）があるので、ページの列は `col + 開始列`。
- タグ: packed は今までどおり（`equation_part` の `term` に `index` と `data.align`）。grid の時だけ `data` に `columns`（列数）と `cell_padding_pt`（ラウンド1、0列の項は0）、`first_column`（ブロック左端からの開始列、ラウンド2）を足した。`term_columns_grid[index]` でも項の列を引ける。

**Excel のセルの内側の余白（定数）**

- 名前と場所（lead が指定）: `gridlayoutpdf.equations.EXCEL_CELL_PADDING_PT = 2.4`（片側、pt）。lead の依頼で関数 `gridlayoutpdf.equations.excel_cell_padding_pt(size_pt) -> float` も公開した（`EXCEL_CELL_PADDING_PT × max(1, size_pt / 12)`。size_pt は正の有限の数、それ以外は ValueError）。項の列の計算はこの関数を使う。`renderers/xlsx` は import しない。
- 実測（2026-10-20、Excel 16.0 build 20326、COM で `ExportAsFixedFormat`、拡大率 100%、PyMuPDF で読取り）: 3列を結合したセルに左寄せ・右寄せ・中央寄せで `12.50`・`0.000`・`kN`・`断面` を置き、結合の左右に細の罫線を引いた。左の余白＝最初の字の x0 − 左の罫線の中心、右の余白＝右の罫線の中心 − 最後の字の x1（原点＋送り）。細の罫線は PDF で2本の長方形になるので、1 pt 以内の縁を平均して中心にした。条件は Normal の書体2種（游ゴシック 11・ＭＳ 明朝 10.5）、列の幅（21・30 px）、文字の書体と大きさの組合せ。
- 結果（pt。Normal の書体と列の幅では変わらない）:

| 文字 | 左の余白 | 右の余白 | 中央寄せのずれ |
|---|---|---|---|
| ＭＳ 明朝 8 | 1.77 | 1.41〜1.47 | +0.63〜0.66 |
| ＭＳ 明朝 9 | 1.89 | 1.53〜1.59 | +0.63〜0.66 |
| ＭＳ 明朝・ＭＳ ゴシック 10 | 2.01 | 1.65〜1.73 | +0.56〜0.66 |
| ＭＳ 明朝 10.5 | 2.01 | 1.59 | +0.69 |
| ＭＳ 明朝 11 | 2.13 | 1.71 | +0.69 |
| ＭＳ 明朝 12 | 2.25 | 1.83〜1.85 | +0.62〜0.69 |
| ＭＳ 明朝 14 | 2.49 | 2.13〜2.19 | +0.60〜0.66 |
| ＭＳ 明朝 16 | 2.73 | 2.37〜2.43 | +0.60〜0.66 |
| 游明朝 10 | 2.13 | 1.71〜1.77 | +0.61〜0.69 |
| 游明朝 12 | 2.37 | 1.91〜1.95 | +0.64〜0.69 |
| 游明朝 14 | 2.61 | 2.15〜2.20 | +0.63〜0.71 |

- 決め方: 余白は文字の大きさとともに約 0.12 pt/pt で増える（ＭＳ 明朝の左は、整数の大きさでは 0.81＋0.12×size に乗る。10.5 pt は 2.01 で外れる）。そのため1つの値では全部の大きさを覆えない。8〜12 pt の最大（游明朝 12 pt の左 2.37）を 0.05 pt 単位で切り上げた 2.4 を定数にし、12 pt を超える文字は大きさに比例させた（14 pt で 2.8 ≥ 2.61、16 pt で 3.2 ≥ 2.73）。左右で同じ値を使う（右の余白は左より小さい）。
- 根拠に使わなかったもの: 画面の AutoFit の幅は「n 桁 × MDW ＋ 約12 px」（游ゴシック 11: 1〜9桁で 8n+12 px）で、描く時の余白とは別のもの。
- 測っていないこと: 画面に表示した時の余白。Excel の 100% の画面では 21 px の列が 15.75 pt（印刷では 16.08 pt）なので、文字がセルに比べて約2%大きく見える。DocuWorks など他のプリンターのドライバー。17 pt 以上の文字。
- 環境の注意: 測った時の Excel のアクティブなプリンターは「家のプリンター (PX-M6711FT Series)」だった。xlsx-core が記録した DocuWorks PDF・DocuWorks Printer とは別のもので、私は設定を変えていない。印刷される 1 px の pt は、このプリンターでは Normal の書体と列の px で変わった（21 px で游ゴシック 11: 0.7657、ＭＳ 明朝 10.5: 0.7543。30 px で 0.7642・0.7562。ＭＳ 明朝 10.5 なら 21 px の列は印刷で 15.84 pt）が、余白の pt は同じだった。**IPAex明朝は Windows に入っていないため、Excel の PDF では MS-Gothic に置き換わった**（Step 8・10 で外観を比べる時に注意）。
- 測定のスクリプトと JSON はスクラッチパッドで作り、lead が `scripts/xlsx_probe/` に移した（`measure_cell_padding.py`・`measure_cell_padding_sizes.py`・`cell_padding.json`・`cell_padding_sizes.json`）。プリンターは PX-M6711FT Series。

**進捗（RED→GREEN。ログは `.claude/logs/` の同名）**

- ✅ Red `gridterms-red-1`: 38 failed、1 passed（`term_columns` の引数がない TypeError と、`excel_cell_padding_pt` がない AttributeError。正しい理由の失敗）。通ったのは「packed の metadata に grid の鍵がない」の1件で、実装前から成り立つ。
- ✅ 既定の出力が HEAD と同じ: 実装の前に、HEAD 3e42e18 の `equations.py` で、既定の8つの場面（項の列・最小幅・`term_gap`・空の列・退避・結果の専用行・列のない式・ラベル・分数・強制改行）を組んだ。その命令（`repr` とタグ）と metadata の sha256（`ebd81f7e…`）をテストに固定した（`test_default_output_is_the_same_as_before_grid_term_columns`）。代表例の standard・long の全ページの命令・タグ・ページの metadata の sha256（`513398f7…`、スクラッチパッドのスクリプト）も、実装の後に一致することを確かめた。
- ✅ Green `gridterms-green-2`（式の単体 4 ファイルで 268 passed）。初回の `gridterms-green-1` では2件が失敗した。原因は実装ではなく、テストに書いた算数の誤り（`X×22` が 9 列に入ることを見落とした）。場面を作り直した。
- ✅ 代表例の grid 版: `build_report(..., term_columns="grid")`・`write_report(..., term_columns=)`・CLI の `--term-columns {packed,grid}`。既定（`"packed"`）は今と同じオブジェクトを作る。grid 版では、A・S・H の右辺を `TermStop`（数値は right、演算子は center）で区切った。荷重の式は anchors を `(6, 24, 28, 29)` にした（15 列の和を1行に収め、退避を起こさないため。first_equal 6 はラベル「鉛直力の合計」が1行に入る最小。5 にするとラベルが折り返す。ラウンド1の時点の `render_xlsx` ではずらしが 26 件に増えたが、ラウンド2の時点では0件）。断面の式は `(10, 21, 26, 27)` にした（long の結果 7.3811250 を等号のセルから離すため）。H の強制改行は、列揃えの式では無視されるので書いていない。η は lead の指示で grid 版だけ `Root(...)`（√）で書いた（上付きの中の分数はセルのリッチテキストで表せないため）。これらの grid 版の受入テスト（`test_grid_example_*`）の最初の3件は代表例を変えた後に書いたので、Red を経ていない（受入の確認として追加）。`gridterms-green-3` で 43 passed。
- 簡易の見積り（Step 8 の対応付けではない。スクラッチパッドの `estimate_cells.py`）: 式の部品（lhs・relation・term k・result_relation・result・unit、普通の右辺は最上位の Row の項目ごと）の送りの幅をページのグリッドの列に写し、基線の行と列が重なる部品を数えた。packed の standard は 27 件、grid の standard・long はそれぞれ 8 件で、項の列による重なりは 0 件。残る 8 件は (1) 左辺と等号の 6 件（等号の送りの中心を列の境目に置くので、等号が2列にまたがる）、(2) 分数の分子の中の Row「4.50 × 2.70³」1 件、(3) η の入れ子の「1 + γ」1 件。どれも項の列（FR-025）の外で、Step 8 の対応付けの規則で決まる（lead に SendMessage 済み）。

**Tips**

- 列の数は `validation.whole_units_ceil(max(0, need − TOLERANCE), pitch)` で数える。項の幅と余白の和が k 列ちょうどの時に、浮動小数の誤差で k+1 列にならないようにするため（`TOLERANCE` は共有の 1e-7 pt）。
- `"grid"` の列の左端は `(右辺の開始列 + 累積の列数) × pitch` で作る。`rhs_start_pt` と同じ式なので、列0の左端は `rhs_start_pt` とビットまで同じ。
- `_term_rhs` は `"packed"` では余白 0.0 を渡すので、`left + 0.0`・`width − 0.0` は元の値と同じビットになり、既定の出力は変わらない（sha256 で確認）。

**レビュー反映 (2026-10-20, ラウンド1)**

レビュアー5体（python・silent-failure・layout・type-design・general）。重複を統合して HIGH 4・MEDIUM 6・LOW 多数。

- ✅ H（python・layout・general）: 列が範囲の端でちょうど終わる時に、浮動小数の誤差（`a*p + b*p > (a+b)*p`）で退避したり、結果が専用の行へ送られたりした（幅 13・25・26・31・48 列などで再現。30 列では起きていなかった）。→ grid の時だけ整数の列で判定する（`_GridTerms.end` と `limit_column`、結果の行は `rhs_end_column` と比べる）。packed の比較は変えていない（sha256 が一致）。回帰テスト: ピッチ 16.08・15.48・14.52・10.8 × 幅 13〜48 列で右端ちょうど、second 14・18・24・26 で通常域ちょうど、1列はみ出すと退避すること。Red は `gridterms-red-r1b`（境目の誤判定 12 件ほか）、Green は `gridterms-green-r1`。
- ✅ H（silent-failure・type-design）: Step 8 が項の列の範囲を項の命令からたどれず、送りが k−1 列にしか触れない項の数値が文字列のセルになる。→ grid の時だけ `term` のタグの data に `columns`（列数）と `cell_padding_pt` を足した（packed は `align` だけのまま）。lead に連絡。`docs/architecture.md` の表の更新は lead に依頼した。
- ✅ H（silent-failure）・M（python・layout・type-design・general）: ブロックの左端がページの列の境目にない置き方（pt の `Indent`、表のセルの padding）では、黙ってページの列から外れる。→ レイアウトの側では、絶対の位置が分からないので検出できない。docs と docstring に、揃う置き方（ページの直下・`Columns`・`At`・`Indent` の pitch の整数倍）と揃わない置き方を書いた。揃う置き方のテストと、pt の Indent ではずれること（文書の制限）のテストを足した。Step 8 で確かめることを lead に勧めた。
- ✅ H（silent-failure）・M（layout・general）: 代表例の grid 版は書体によっては気づかれずに退避する（IPAexゴシックの "12.50" は 27.8 pt で3列）。→ `write_report`・CLI は grid の時に退避が起きたら ValueError（CLI は `parser.error`）で止まる。`grid_fallbacks(pages)` を追加。テスト: IPAexゴシックで止まること。
- ⏭→解消 H の一部（silent-failure）: long の grid 版は、作業中の `render_xlsx` で「右端を越える」エラーになった（2026-10-20 のラウンド1の時点）。原因は折り返したラベル（その時点では packed の long でも14件のずらし）で、Step 8 の側の扱いとして lead に連絡した。ラウンド2の時点（2026-10-20 10:28 ごろ、xlsx-map の作業中の版）では、grid の standard・long ともずらし0・図形への切替え0、packed の long はずらし2件。xlsx-map の担当が実装を進めたためと見られる。
- ✅ M（python・layout・general）: docs の指針が言い過ぎだった（「指定しなくても列に揃う」、ずらしが起きないと読める）。→ lead の指示 (a)〜(c) を含めて書き直した。(a) 等号は境目の右の列、左辺は左の列まで。(b) 上付き・下付きに分数を入れない。(c) TermStop は最上位の右辺だけで、入れ子の Row は1つのセル。あわせて、ラベルの折り返し、退避の見つけ方（`term_fallback`、警告なし）、空でない項は1列以上、単独の `Equation` は packed であること、余白の左右差（Excel の実測より PDF のほうが右寄せ・中央寄せで1 pt 未満ずれる）を書いた。
- ✅ M（python・general）: 既定の出力の sha256 の固定は壊れやすく、作り直しの手順がない。→ 意図して変えた時の作り直し方と、Step 6 の commit の後に外してよいことをテストの注記に書いた。代表例の HEAD との一致はスクラッチパッドのスクリプトで確かめた。general のレビュアーも、`git archive HEAD` で別に確かめて一致した。
- ✅ M（type-design）: 余白の出どころが、レイアウトと `render_xlsx(cell_padding_pt=...)` の2か所にある。→ grid の項はタグ・metadata の `cell_padding_pt` を正とすることを lead に勧めた（Step 8 の契約）。レイアウトの側は `_GridTerms.padding` の1か所にまとめた。
- ✅ M（layout、推測とされた点）: 列幅ちょうどの数値が Excel で「###」になるおそれ。→ COM で実測した。条件は Excel 16.0、A4 のグリッドの列 21 px を 1〜8 列結合したセル、右寄せの数値、ＭＳ 明朝 10 pt、Normal の書体は游ゴシック 11 と ＭＳ 明朝 10.5。結果: 印刷（PDF 書出し、100%）ではちょうど収まる桁数が 1〜8 列のすべてで表示され、1桁増やすと「###」になった（游ゴシックの4列だけは1桁多くても表示）。画面（ズーム 100%、`Range.Text`）では 1〜4 列は表示されたが、5〜8 列では「###」になった。lead の判断で規則は変えず、docs に制限として書いた。Step 10 の COM 検査で、合格対象の全数値セルの画面の表示を lead が確かめる。スクリプトと JSON（`measure_hash_fit.py`・`hash_fit.json`）は lead が `scripts/xlsx_probe/` に移した。この測定のプリンターは DocuWorks PDF（余白の測定の PX-M6711FT とは別）。
- ✅ M（general）: 計画の Step 6 の行が更新されていなかった。→ 1・2 項目めを ✅ にした。3 項目めは、版を用意したことと、作業中の `render_xlsx` で standard のずらし0件を確かめたことを書き、Step 8 の完成待ちとして未完了のままにした。
- ✅ L（同ラウンドで対応）: `term_columns` を `Literal["packed", "grid"]`（`TermColumns`）にし、選択肢を `_TERM_COLUMNS` として非公開にした。エラー文を既存の書き方（"term_columns must be packed or grid"）にそろえた。`term_columns` の欄を最後に移した（`__match_args__` の順を保つ）。余白の計算を1か所にまとめた。0 列の項は余白を取らずに列の左端に置く（空の Text が隣の列に出ない）。等価比較・hash のテスト。文字サイズの違う式で「項＋余白」の最大が列数を決めるテスト（10 pt で 2 列、14 pt で 3 列になる組合せ）。metadata の pt と整数の列が完全に一致することのテスト。代表例のテストで A・S・H の列数と揃えを名指しで確かめる。grid 版に上付きの中の分数がないことのテスト。
- 持ち越し（LOW、lead の判断）: `examples/README.md` に `--term-columns grid` を書く（計画 Step 10 の README の更新）。DESIGN.md の FR-025 の「最も広い項が入る最小の列数」に「＋Excel のセルの余白」を足す（`update_design.py`、lead の担当）。`dataclasses.replace(EquationGroup)` は HEAD のころから使えない（独自の `__init__`）。`_map` の許容差を式の側（`TOLERANCE`）にそろえる（xlsx-map）。`QuarterTurn` の中の grid の余白（上下の余白）は測っていない。
- 新たな見逃しパターン候補: 整数の列に「ちょうど収まる」ことが普通に起きる設計では、pt の和の比較の誤差が必ず表に出る。grid の判定は整数で行い、pt は表示と metadata のためだけに作る。

**レビュー反映 (2026-10-20, ラウンド2)**

レビュアー4体（silent-failure・python・layout・general）。ラウンド1の修正は全員が正しいと確かめた（silent-failure は負の通常域・幅が整数倍でないブロック・ラベル付き・自動のアンカー・別のピッチで、layout は 11,102 件の総当たりで誤判定0）。新たに HIGH 1・MEDIUM 7（重複を統合）。

- ✅ H（layout）: `Columns` の中の `Indent`、A3 の `Indent` では、子の幅 `n·p − k·p` が `(n−k)·p` より1 ulp 短く、`limit_column` が1列少なくなって、右端ちょうどの行が退避した。→ `limit_column = _floor_column(available_width + TOLERANCE, pitch)`（`Columns` の measure の許容差と同じ考え方）。回帰テスト: `Columns(MathBlock, Indent(group, k·p), col_spans=(3, span))` の (9,2)・(9,5)・(12,7)、A3 の `Indent(44·p)`、1e-6 pt 狭いと退避すること。Red `gridterms-red-r2` → Green `gridterms-green-r2`。
- ✅ M（silent-failure・python・general）: 代表例の CLI が grid の時、関係のない ValueError（壊れた画像など）まで「--term-columns grid」の誤りとして報告した。→ `GridTermFallbackError(ValueError)`（`block_ids` を持つ）を作り、CLI はそれだけを `parser.error` にする。テスト: 壊れた画像では ValueError がそのまま出ること、退避では終了コード2で stderr に `--term-columns grid` と `load-totals` が出ること。
- ✅ M（silent-failure）: 項のタグに開始列がなく、Step 8 が命令の範囲から左端を推定した。そのため、項の中に命令のない幅（空の Row など）があると、正しく揃った項が「列の境目から外れた」と記録された。→ grid の時はタグの data に `first_column`（ブロック左端からの開始列）を足した。0列の項の `cell_padding_pt` は 0。lead に連絡する。
- ✅ M（general）: ラウンド1の反映の塊が xlsx-map の節の下にあった（私が追記した後に xlsx-map が節を足したため）。→ grid-terms の節へ移した。
- ✅ M（general・python・silent-failure）: 例の docstring の「同梱の書体（複数）に余裕がある」は誤りだった。→ 「既定の IPAex明朝 10 pt に合わせてあり、他の書体（IPAexゴシックなど）では退避して write_report が止まる」に直した。
- ✅ M（general・python・layout）: docs の余白の記述が、12 pt を超える文字と左寄せのずれを無視していた。→ 「8〜12 pt では左右とも 2.4 pt 以下、どの寄せ方でも1 pt 未満のずれ（左寄せは最大約0.6 pt、右寄せは最大約1 pt）」に直した。
- ✅ M（general）: 余白と「###」の測定でプリンターが違うのに書いていなかった。→ docs と記録に、余白は PX-M6711FT Series、「###」は DocuWorks PDF と書いた。
- ✅ M（general）: long の grid 版と first_equal 5 の記述が、今の `render_xlsx` と合わなくなっていた。→ 時点を付けて、最新の結果を書いた（上のラウンド1の ⏭ の項目と、下の追記）。first_equal を 5 にした時のずらし 26 件はラウンド1の時点の値で、ラウンド2の時点では0件（general の確認）。6 にした理由は「ラベルを1行に収める最小の値」に絞る。
- ✅ L（同ラウンドで対応）: 退避の判定の許容差（`TOLERANCE`）を固定するテスト（+5e-8 pt で2列、+2e-7 pt で3列）。小さい文字の広い項が列数を決めるテスト（「最も広い項＋最大の余白」の誤った実装では3列になる組合せ）。`_term_rhs` の余白を関数の中で作るようにした（引数の取り合わせを減らした）。`grid_fallbacks` の docstring を「最上位の配置だけ」に限った。`TermColumns` を docs に書いた。docs のページの列の求め方を `x_pt / pitch_x`・`indent_pt / pitch_x` にした。右端ちょうどのテストは用紙を広げて skip をなくした。テストの名前を中身に合わせた（`..._take_contiguous_whole_columns`、`..._default_is_packed_...`）。記録の「0.81＋0.12×size にちょうど乗る」は整数の大きさだけ（10.5 pt は 2.01 で外れる）。計画の「実測」を「実測の上限を切り上げた値」に直した。
- 持ち越し（LOW）: `grid_fallbacks` は `Columns`・`Stack` の中を見ない（今の代表例では起きない。docstring に記載）。`Table(padding=0)` のセルと `QuarterTurn` の中の grid の項が揃うかは確かめていない。

**レビュー反映 (2026-10-20, ラウンド3)**

レビュアー3体（silent-failure・python・layout）。ラウンド2の修正は全員が正しいと確かめた。layout は 3,349 通りの置き方で 63,223 行、python は修正を外した版で回帰テストが落ちること、silent-failure はタグと metadata の照合 4000 件で、それぞれ誤り0。新たに MEDIUM 1・LOW 11（重複を統合すると 9）。

- ✅ M（layout）: `Indent` を入れ子にすると、`indent_pt` が外側の値で上書きされ（`containers.py:206`、担当外）、docs に書いたページの列の求め方が内側の字下げの分だけずれた。文字の位置は正しい。→ docs に「入れ子の `Indent` ではこの求め方を使えず、描画命令の x から求める」と書き、合計を `round()` することも足した。制限を固定するテスト（`test_nested_indents_keep_only_the_outer_indent_pt`）と、ページの直下・`Columns`・`Indent`・`At` で docs の求め方が文字の位置と一致するテストを足した。`Indent` が足し込むように変えるかは lead の判断。→ その後 lead が `containers.py` の `Indent` を「入れ子では合計」に変えた（xlsx-map の節）。それに合わせて docs の制限の記述を消し、テストを `test_nested_indents_give_the_page_column_by_the_documented_rule`（入れ子でも docs の求め方で正しい列になる）に書き換えた。
- ✅ L（silent-failure）: 結果のある行の通常域の終わりの列も、引き算（`second − second_left − gap`）で1 ulp 短くなりうる（gap 13.08 で再現）。→ grid の時だけ `_floor_column(... + TOLERANCE)` にした。packed は変えていない（sha256 が一致）。テスト `test_rows_ending_exactly_at_a_normal_region_made_by_subtraction_keep_their_result`。修正前の式では列7になる（テストが落ちる）ことを確かめた。
- ✅ L（同ラウンドで対応）: `_term_rhs` の `normal_end_column` を `int | None` にし、grid で None なら ValueError にした（黙った誤判定を防ぐ）。`GridTermFallbackError` の `block_ids` に既定値 `()` と型注釈を付けた（copy・pickle で作り直せる）。荷重の値の並びを `LOAD_VALUES` の1か所にした（既定の出力の sha256 は一致）。CLI の help で、この例は PDF と JSON だけを書くことを明記した。`_GridTerms.limit_column` の docstring を「右端の境目（終わりを含まない端）」に直した。`Columns` の中の `Indent` が 1e-6 pt 広すぎると退避するテストを足した。
- 確かめたこと（python）: 作業中の `render_xlsx` で、grid の standard・long はずらし0・図形への切替え0・タグのない命令0で、`strict=True` でも通った。packed は standard 1件・long 2件。

**レビュー反映 (2026-10-20, ラウンド4)**

レビュアー2体（silent-failure・layout）。ラウンド3の修正はどちらも正しいと確かめた。silent-failure は通常域の終わりの列を 8,304 通りで、layout は 706,962 行の総当たりで確かめ、どちらも誤り0。新たに MEDIUM 1・LOW 7。

- ✅ M（layout）: 結果の行のはみ出し側を守るテストがなかった。通常域の終わりの列を +1・許容差 2e-6・ceil に変えても、テストが落ちなかった。→ テストを3つ足した。gap 13.08 で列9で終わる行は結果が専用の行へ移ること。gap を 1e-6 pt 増やすと列8で終わる行も移ること。ピッチ×second の組合せで、1列はみ出すと移ること。通常域の終わりの列を +1 にしたミュータントで確かめた。最初は 10 件中 9 件しか落ちなかった。通ったのは「1e-6 pt 足りない」側のテストで、gap を増やすと右辺の開始列も 3→4 に変わり、別の範囲を試していたため。プローブを同じ gap で測るように直した後は、10 件すべてが落ちる。ファイルは元に戻した（`+ 1` が残っていないことを確かめた）。2e-6・ceil のミュータントは実行していない。
- ✅ L（同ラウンドで対応）: docs のページの列の求め方に「整数から 1e-6 列以上外れたら揃っていない置き方として扱う」を足した。「経路の各段の part の `indent_pt` と `Columns` の子の `x_pt` を足す」と書き、API の表の `Indent` に「入れ子では合計」を足した。テストの補助関数を docs と同じ求め方（各段の metadata から合計）にし、`Indent(Columns(...))` と `Columns(Indent(...))` の場合を足した。pt の `Indent` が docs の求め方で「揃っていない」と分かることのテストを足した。例外のテストで `copy`・`deepcopy` の後も `block_ids` が残ることを確かめるようにした（pickle はテストの読み込み方では import できない名前になるので使っていない）。CLI の help を「.xlsx は書かない」に直した。
- 持ち越し（LOW）: grid の式の集まりの中でも、項の列のない行・退避した行の通常域は packed と同じ pt の式（許容差なし）なので、gap 13.08 のような偶然の値では、grid の項の行と結果の置き方が揃わない（silent-failure が再現した。packed から変わっていない挙動で、データは失われない）。packed の判定にも許容差を入れるかは lead の判断（既定の出力が変わりうる）。

**レビュー反映 (2026-10-20, ラウンド5)**

レビュアー1体（silent-failure）。ラウンド4のテストと記録の事実を確かめた。ミュータント +1・2e-6・ceil・`limit_column − 5` は、どれも今のテストで検出される。

- ✅ M: docs に書いた「整数から 1e-6 **列**」の判定が、方眼Excelの対応付け（`_map` の `_TERM_EDGE_TOLERANCE_PT`、1e-6 **pt**）と食い違っていた。`Indent(2·p + 5e-6)` は、docs の判定では揃い、`render_xlsx` では `term_off_grid` になった。→ docs を「差に `pitch_x` を掛けた長さが 1e-6 pt 以上なら揃っていない」に直した（対応付けと同じ判定）。テストの補助関数も同じ判定（`documented_on_page_columns`）にし、境目の両側（5e-7 pt は揃う、2e-6・5e-6 pt は揃わない）のテストを足した。
- ✅ L（同ラウンドで対応）: ループが空でないことの確認を足した。右辺の開始列が9であることを確かめてから行を作るようにした。docs の求め方と揃う置き方に `Stack` を足した。

**レビュー反映 (2026-10-20, ラウンド6)**

レビュアー1体（silent-failure）。ラウンド5の docs は `_map` の判定・`containers.py` と一致すると確かめた（`Stack`・入れ子の置き方を `map_reports` で試し、`term_off_grid` 0件）。

- ✅ M: docs の判定が方眼Excelの対応付けと同じであることを、実際の対応付けで照らすテストがなかった（ラウンド5と同じ食い違いが再び起きても気付けない）。→ `test_the_documented_alignment_rule_is_in_pt` で、同じ置き方を `map_reports` にも通すようにした。`term_off_grid` が出るのは、docs の判定で揃っていない時だけであることを確かめる。このテストは xlsx-map の作業中の `_map.py` に依存する。
- ✅ L（同ラウンドで対応）: 境目ちょうど（1e-6 pt）の扱いを `_map`（`> 1e-6` で外れ）にそろえた。docs は「超えれば」、補助関数は `<=` で揃いとした。docs に足した `Stack` の置き方（`Columns(…, Stack(…))`・`Indent(Stack(…))`）をテストに足した。1列はみ出すテストで、退避していないことも確かめるようにした。テストは `gridterms-green-r6` で 123 passed。

**レビュー反映 (2026-10-20, ラウンド7) とループの終了**

レビュアー1体（silent-failure）。CRITICAL・HIGH・MEDIUM は0件。`map_reports` との照合は、`_TERM_EDGE_TOLERANCE_PT` の変更（1e-5・1e-7）、列の単位での比較、開始列の判定を外すこと、葉の `indent_pt` を無視することのどれも捕まえる（ミュータントで確認）。

- ✅ L（同ラウンドで対応）: docs に書いた各置き方（`Columns`・`Stack`・`Indent`・`At` とその入れ子）も `map_reports` に通し、`term_off_grid` が0件であることを確かめるようにした（容器の `indent_pt` を落とすミュータントを捕まえるため）。揃っていない側では `detail` に「not on a page column boundary」が含まれることも確かめる。ラウンド6の記録にテストのラベルと件数を書いた。
- ループの終了: 7 ラウンド。件数の推移（重複を統合した後）は次のとおり。
  - ラウンド1: HIGH 4・MEDIUM 6
  - ラウンド2: HIGH 1・MEDIUM 7
  - ラウンド3: MEDIUM 1
  - ラウンド4: MEDIUM 1
  - ラウンド5: MEDIUM 1
  - ラウンド6: MEDIUM 1
  - ラウンド7: 0
- 残る LOW（lead の判断）: `examples/README.md` の `--term-columns grid`、DESIGN.md の FR-025 の文言、packed の通常域の許容差、`grid_fallbacks` は最上位だけ、`Table(padding=0)`・`QuarterTurn` の中は未確認、5列以上の数値の画面の「###」（Step 10 で lead が確かめる）。

#### xlsx-map（Step 8）

担当 xlsx-map（サブエージェント）。2026-10-20。編集したのは `src/gridlayoutpdf/renderers/xlsx/{__init__,_map}.py`（`_map.py` 新設）、`src/gridlayoutpdf/renderers/xlsx/_model.py`（最小の追加1か所、下記）、`src/gridlayoutpdf/document.py`（`Document.render_xlsx` の追加だけ）、`src/gridlayoutpdf/__init__.py`（公開名）、新設テスト3本、この記録と計画書の Step 8 の行。`_numbers.py` は変更していない。

**進捗（RED→GREEN。ログは `.claude/logs/` の同名）**

- ✅ Red 1: `tests/unit/test_xlsx_map.py`（47件）を先に書き、`_map.py` を `NotImplementedError` の骨組みにして `xlsxmap-red-1` 47 failed（収集エラーでない本物の失敗）→ Green。
- ✅ Red 2〜5（`xlsxmap-red-2`〜`red-5`）: 分数の分母の押下げ、回転したセルの読む方向へのずらし、上付きの中の分数（`red-3`）、grid の項・ラベルの折り返し・数値の余白の許容差（`red-4` 6 failed）、字形のインクで列を決める（`red-5`）。等号の列の規則と上付きの中の分数は実装と同時にテストを書いたので、分岐を一時的に無効にしてテストが落ちる陰性対照を確かめた。
- ✅ ImplementationLoop ラウンド1の修正（`xlsxmap-r1-red` 19 failed → `xlsxmap-r1-green` 380 passed、Step 7 の単体テストを含む）。
- ✅ `tests/integration/test_xlsx_readback.py`（openpyxl、7件）、`tests/integration/test_xlsx_map_excel.py`（Excel COM、9件。Excel がなければ skip と理由、`GRIDLAYOUTPDF_REQUIRE_EXCEL=1` なら失敗。Excel の動かし方は `test_xlsx_excel_core.py` の `_run_excel`・`_EXPORT_PDF` をファイルから読み込んで使う）。Excel 16.0 で `strict=True` の報告書（段落・分数と添字の式・数値・表・Rule・回転・A3 の頁・図・画像・ヘッダー/フッター、3シート）が修復なしで開き、数値・書体・結合・上付き・文字の向き・罫線の太さ・図形の種類・用紙・拡大率 100%・先頭ページ番号・ヘッダー/フッターを読み戻せた。

**印刷の位置の確認（lead 判断 A、2026-10-20）**

- 行高・列幅は行・列ごとに整数 px に振り分ける。各セルは、均等割りの px とその前後のうち、Step 7 の実測の印刷の大きさ（`scripts/xlsx_probe/print_pitch.json` の游ゴシック 11・100%・11〜30 px、`PRINTED_COLUMN_PT`・`PRINTED_ROW_PT`。その外は 21 px の比 列 16.08/21・行 15.48/21）で印刷の境目が PDF に最も近くなるものを選ぶ（誤差が頁の中で積み上がらない。予測の誤差が半マスを超えるグリッドは `XlsxError`）。予測の最大誤差は A4 0 pt、p30〜37 で列 0.36・行 0.24 pt。図形・画像の座標はセルの中の割合のまま、その行・列の累積から計算する。
- A4 の基準グリッドは計算どおり全列・全行 21 px のまま（単体テストで確認）。代表例の .xlsx の列幅・行高・図形の XML は振り分けの前と同じバイト列（数値セルの判定の変更で styles・sharedStrings だけ変わった）。
- COM の実測（`test_every_grid_boundary_prints_within_half_a_cell_of_the_pdf`、全境目に極細の罫線を引いた頁を Excel から PDF に書き出し pymupdf で線を読む。値は PDF のグリッドの位置からの絶対のずれで、プリンターの原点のずれ 0.1〜0.8 pt を含む）。Excel の `ActivePrinter` は実行ごとに違う名前を報告した（lead の連絡の「家のプリンター PX-M6711FT」は一度も報告されていない。プリンターの設定は変えていない）。
  - ラウンド2の振り分け（実測の印刷の大きさで選ぶ）、プリンター「DocuWorks Printer on Ne04:」: A4（16.08 × 15.48 pt、30 × 47）最後の列 +0.90 pt・最後の行 +0.78 pt（全境目の最大 0.90 / 0.78 pt）、p30〜37（10.8 × 14.52 pt、46 × 51）最後の列 +1.26 pt・最後の行 +0.78 pt（最大 1.26 / 1.02 pt）。半マスは A4 8.04 / 7.74 pt、p30〜37 5.4 / 7.26 pt。
  - ラウンド1の振り分け（21 px の比で丸める）、プリンター「DocuWorks PDF on Ne05:」: A4 最後の列 +0.64・最後の行 +0.52 pt、p30〜37 最後の列 −0.68・最後の行 +1.98 pt（最大 1.16 / 1.98 pt）。
  - 振り分けの前（等しい 14.25 pt の行）は p30〜37 の最後の行 −24.2 pt（レビュアーの実測）。
- 改ページで分かれた表: 2頁目の先頭の上罫線が印刷されることを COM で確認（`test_a_table_split_at_a_page_break_prints_its_top_border_on_the_next_page`）。

**代表例（`examples/representative_report.py` を編集せずスクラッチで読み込み、grid-terms の作業途中の版、cell_padding は 2.4×max(1, size/12)）**

| 書体 / variant / term_columns | ずらし | 図形への切替え | 数値を文字列のまま（number_as_text） | タグなし |
|---|---|---|---|---|
| IPAex明朝 / standard / grid | 0 | 0 | 2 | 0 |
| IPAex明朝 / long / grid | 0 | 0 | 2 | 0 |
| MS Mincho / standard / grid | 0 | 0 | 0 | 0 |
| MS Mincho / long / grid | 0 | 0 | 0 | 0 |
| IPAex明朝 / standard / packed | 1（上付きの中の分数） | 1（同） | 2 | 0 |
| IPAex明朝 / long / packed | 2（同上と `7.3811250` の重なり） | 1 | 3 | 0 |
| MS Mincho / standard / packed | 2（同上と `β2` の重なり） | 1 | 0 | 0 |
| MS Mincho / long / packed | 2（同上） | 1 | 1 | 0 |

（ラウンド6の後の値。IPAex明朝の grid 版の文字列のままの2件は、grid の項の `'12.50'` と分数の分子の `'7.381125'`。）

- 片持ち梁の件数は Step 9 の作り直しの後に測る（今の fixture は cantilever 担当が作業中で、単体テストの一部が失敗している。この担当の変更とは無関係）。

**公開 API**

- `render_xlsx(reports, path, fonts=None, *, strict=False, cell_padding_pt=None) -> XlsxResult`（`gridlayoutpdf` と `gridlayoutpdf.renderers.xlsx` から）。`reports` は `(シート名, ScenePage の並び)` の並び。全体を作ってから一時ファイル経由で置き換える。エラーの時はファイルを書かない。
- `Document.render_xlsx(path, sheet_name, *, strict=False, cell_padding_pt=None) -> XlsxResult`（`layout()` の頁を1つの帳票として書く。ページ送りは変えていない）。
- `cell_padding_pt` は「文字の大きさ（pt）→ セルの片側の内側の余白（pt）」の関数。`None` は `gridlayoutpdf.equations.excel_cell_padding_pt`（呼ぶたびに読む）。
- `XlsxResult(path, sheets, shifts, fallbacks, untagged, dropped, numbers_as_text)`（frozen、全部 tuple、ハッシュ可）:
  - `sheets`: `XlsxSheet(name, report, first_page, last_page, rows, columns, scale)`（頁は帳票の 1 始まりの通し番号、両端を含む。`scale` は印刷の拡大率）。
  - `shifts`: `XlsxShift(sheet, page, text, from_cell, to_cell, reason)`。セルは 0 始まりの (行, 列)、`from_ref`/`to_ref` で A1 形式。`reason` は `overlap`・`fraction`・`fraction_in_script`（`SHIFT_REASONS`）。
  - `fallbacks`: `XlsxFallback(sheet, page, kind, detail)`。`kind` は `quarter_turn`・`border_off_grid`・`border_in_merge`・`border_conflict`・`rotated_text`・`fraction_in_script`・`term_off_grid`・`cell_padding_mismatch`（`FALLBACK_KINDS`）。
  - `numbers_as_text`: kind が `number_as_text` の `XlsxFallback`（strict の対象外、lead 判断 B）。
  - `untagged`: タグのない命令の (型名, 数) の並び（`dict(result.untagged)`、`untagged_count`）。`dropped`: 大きさのない図形（長さ0の線など）を書かなかった記録。
  - 記録の型は生成時に値を検査する（未知の reason・kind、負のセル、頁の範囲の逆転は ValueError）。
- `strict=True` で `shifts` か `fallbacks` が1件でもあれば `XlsxStrictError`（`XlsxError` の派生、`ValueError` の派生。`.shifts`・`.fallbacks`、pickle・copy 可）。常に `XlsxError` になるもの: 右端（回転では上端・下端）を越えるずらし、グリッドの外の文字・図形（2頁目以降の余白の図形を含む）、Excel の上限（16,384 列・1,048,576 行・1シート 1,026 か所の改ページ）、A4・A3 以外の用紙、書式付きの頁の欄、整数でないヘッダー/フッターの大きさ、シート名の規則と重複、モデルが受けない書体名など（頁番号付き）、読めない画像。
- 内部の入口 `_map.map_reports(reports, fonts, *, strict=False, cell_padding_pt)` は `(Workbook, XlsxResult)`（`path=None`）を返す。

**`_model.py` への最小の追加（理由つき）**

- `Sheet._check_borders`: 改ページ（`row_breaks`）の境目でだけ、上の行の bottom と下の行の top を同じ物理的な辺として2つ持てるようにした（各頁が自分の側を印刷するため。1つだけだと2頁目の先頭の罫線が印刷されなかった、レビュアーの実測）。そのため `_check_row_breaks` を `_check_borders` の前に移した。テスト `test_the_model_accepts_a_bottom_and_a_top_border_only_at_a_page_break`。

**設計判断（実装判断。ユーザー未確認。lead が DESIGN に載せる）**

- 文字片の単位: 構造の単位（段落・表のセルの行・`CellLines` の行・式の部分と項・分数の分子/分母・`MathBlock`）の文字を左から順に1つのセルにまとめ、その単位の分数が間にある所と、原子が半マス以上離れている所で分ける。原子の間が 0.08 em 以上なら空白1つでつなぐ（`Row` の既定の間隔は 0.15 em）。添字・指数は同じセルの上付き・下付きの run で、大きさは記号と同じ（Excel が約2/3に縮める）。添字の添字は1段。空白だけの文字は捨てる（何も描かない）。
- セルの範囲: 基線のある行（基線がちょうど境目なら上の行）の1行と、字形のインクが触れる全部の列（インクのない文字は送り。境目から 1e-6 マス以内は触れないとみなす）。字の左右の余白（サイドベアリング）で隣の列を取らない（MS Mincho の `β²` の1件の原因）。
- 式の等号（`relation`・`result_relation`）: PDF では anchor の境目に送りの中心があるので、セルは中心のある列（境目の右の列）から始め、中央寄せ（lead 了承、`docs/api.md` に lead が書く）。
- grid の項（lead 指示、grid-terms ラウンド2のタグ）: 項の列は「配置の col＋Stack/Columns の子の `x_pt`＋`indent_pt`」で求めたブロックの左端＋タグの `first_column`、列数はタグの `columns`。ブロックの左端が列の境目に乗らない・ページの metadata から分からない（表のセル・図など）・字形が列の外にはみ出す時は `term_off_grid`、タグの `cell_padding_pt` と `cell_padding_pt(size)` が 1e-9 pt を超えて違えば `cell_padding_mismatch`（どちらも strict でエラー、配置と数値の判定はタグの余白で行う）。
- 寄せ方: 内側から最初に見つかった構造で決める。分子・分母は中央、式の左辺は右、等号は中央、結果は右、単位・ラベル・右辺は左、項は項の `align`、`CellLines`・段落・表のセルはその `align`（`justify` は左）。縦は中央。回転したセルは読む向きの寄せ方を紙面の向きへ直す（+1: 左→下・右→上、−1: 左→上・右→下、横は中央）。
- 数値セル（lead 判断 B）: Excel の画面はグリフを整数 px で描くので、文字の幅は1字ずつ px に切り上げた和（`screen_width`）で測り、セルの範囲（振り分けた px の幅）が「その幅＋余白×2 − 1e-7 pt」以上なら数値。足りなければ、寄せ方の反対側へ（中央寄せは両側へ1セルずつ同時に。片側が空かなければ広げない）、空いたセルだけに、罫線を越えず・結合の内側に罫線を入れずに広げる。それでも足りなければ文字列のまま `numbers_as_text` に記録（strict の対象外）。書体や上付きが混じって rich text になった数値も記録する。COM で、最も狭い表のセルの数値（MS Mincho 8・10・10.5 pt、IPAex明朝 10 pt、7 種）が `###` にならないことを確かめた（`test_number_cells_never_show_hashes`）。
- 分数: 分子・分母が同じ行に入る時は分母（とその中の全部）を下げ `reason="fraction"`（内側の分数から）。分数線は分母の一番上の行の上の境目に図形（横は PDF の位置を、分子・分母がずれた列の数の最小だけ右へ）。同じ式の行（`EQUATION_LINE`・`MATH_BLOCK`）の分数の外の文字片はその行の最上行〜最下行に縦結合し上下中央。2行以上に折り返したラベルは各行を縦結合から外し、それぞれの基線の行に置く。
- 上付き・下付きの中の分数（lead 判断）: 普通の大きさの分子・分母のセルにして `fallbacks` に `fraction_in_script` を1件、分母を下げたら `reason="fraction_in_script"` のずらし。strict ではエラー。基の大きさがないので文字の大きさは 0.5 pt 刻みの最も近い値（12 pt の 0.65 倍 7.8 → 8.0）。
- 罫線: `BORDER_ROLES` の線（`Rectangle` の括り線は幅と高さの小さい方を太さとして向きを決め、色は塗りの色）で、線の中心が境目から線の太さ以内、両端も境目から線の太さ以内にあるものだけ。継ぎ目の半ストロークの補い（タグの `drawn` が `continuing` で長さが太さ以下）は捨てる。それ以外の、境目から外れた・1マスより短い罫線は図形にして `border_off_grid`。頁の下端の境目は上の行の bottom、それ以外は下の行の top（頁の上端は top、改ページの両側を別に持つ）、右端は左の列の right、それ以外は右の列の left。同じ辺に2本ある時は太い方、同じ太さなら実線、それも同じなら先の方。残した方が他方を覆わない（色が違う、破線が消える）時は `border_conflict`。二重線の2本は1辺。結合した文字片の内側に入る罫線は図形にして `border_in_merge`。
- 回転: `QuarterTurn` の `local_grid` の `pitch_x` がページの `pitch_y` と、`pitch_y` が `pitch_x` と（相対 1e-9 で）等しい時だけセル（+1 は 90 度、−1 は 270 度）。それ以外はブロックごとに図形のグループにして `quarter_turn`。ずらしは読む向き（+1 は上、−1 は下）。180 度の文字は図形にして `rotated_text`。
- 図: `Figure` ごとに1つのグループ。`TextBox` は文字入りの四角（角丸を保つ）、`TextDiamond` は文字入りの菱形（行ごとの段落、上下左右中央）、`Label` は枠なしのテキストボックス（`align` を保つ）、矢印・連結線は PDF と同じ線と自由形状（矢じりは開いた折れ線）、利用者の命令はそのまま図形。2点の閉じた自由形状は線。`Image`（`RasterImage`）は画像。PNG・JPEG はそのまま、他の形式は PNG に変換。
- シートの分け方（lead 判断 C）: 用紙・グリッド・ヘッダー/フッター（雛形・寄せ方・書体・枠の位置と高さ）のどれかが変わる所で次のシート（元に戻っても新しいシート）。
- ヘッダー・フッター: `{page}`→`&P`、`{pages}`→帳票全体の頁数の数字、先頭ページ番号は各シートの帳票内の通し番号。大きさは整数 pt だけ（Excel の書式の制約）。余白: ヘッダーは装飾の枠の上端の紙の上からの距離、フッターは枠の下端の紙の下からの距離。装飾の文字はセルにしない。
- ページ設定: 用紙は `paper_for_size`（A4・A3 だけ）、左・上の余白はグリッドの原点。右・下の余白は PDF の値から始め、100% で収まらない時だけ `print_fit` の係数で 100% に収まる値まで小さくする（空白の紙だけなので）。拡大率は `print_fit` の値で、100% 未満なら `fallbacks` に `print_scale`（グリッドが PDF より小さく印刷されるので strict でエラー）。ブックの標準の書体は游ゴシック 11（A4.pdf のグリッドの間隔で印刷される唯一の測った書体）。画面の枠線は表示、印刷はしない。
- タグのない命令: 利用者の命令と同じに扱い（文字はその命令だけの文字片、線などは図形）、型ごとに数える。頁の配置（`placements` の命令の範囲）に属さない命令（手で作った頁）は1つの配置に属するとみなし、タグの構造で区別する。

**Tips**

- `ScenePage` を手で作るテストでは、別の文字片にしたい命令に別の `Scope` の `index` を付ける（同じタグの列は同じ構造とみなす）。
- 代表例の確認は `examples/` を `sys.path` に足して `build_report` を呼ぶスクラッチのスクリプトで行った（例のファイルは編集しない）。
- Excel の `Range.Borders.Item(8)`（上の辺）は値のないセルにも付き、共有の辺も上の辺として報告する（改ページの境目の消失はこれでは見えない）。罫線の印刷は PDF に書き出して pymupdf で確かめる。
- openpyxl の `paperSize` は文字列で読める（`'9'`）。画面の枠線の既定（表示）は `showGridLines=None`。
- この環境の Bash のヒアドキュメントでは、中身によって「unexpected EOF」で失敗することがあった（バッククォートを含む文字列）。長いコードは Write ツールでスクラッチに書いてから実行する。

**docs/api.md に書く候補（lead が Step 10 でまとめる）**

- `render_xlsx`・`Document.render_xlsx`・`XlsxResult` と記録の型、strict の意味、常にエラーになる条件（上の「公開 API」）。
- 方眼Excel の文字片の単位・等号の列・grid の項・分数・上付きの中の分数を避けること・罫線になる線・数値セルになる条件・シートの分け方（上の「設計判断」）。

**未解決・持ち越し**

- 代表例への .xlsx 出力の追加（Step 8 の3項目め）は lead の指示待ち。
- Excel の `ActivePrinter` の報告（DocuWorks PDF）と lead の連絡（家のプリンター）が食い違っている。確認が取れていない。

**レビュー反映 (2026-10-20, ラウンド 1)**

レビュアー3体（silent-failure、python＋type-design、layout＋計画整合）。集約（重複は高い方へ統合）: CRITICAL 0 / HIGH 6 / MEDIUM 15 / LOW 約20。lead の指示（grid の項・ラベル・MS Mincho、判断 A〜C）もこのラウンドで反映した。

- ✅ H: 改ページで分かれた表の、2頁目の先頭の上罫線が印刷されない（3体）→ 頁の上端・下端の辺を別に持ち、モデルは改ページの境目だけ bottom と top の両方を許す。COM で2頁目の線を確認。
- ✅ H: グリッドの刻みが 21 px でないと印刷が累積してずれる（片持ち梁 p30〜37 で最後の行 −24 pt）→ 整数 px の振り分け（上の「印刷の位置の確認」）。
- ✅ H: 余裕ありと判定した数値が Excel の画面で `###`（MS 明朝 8 pt など）→ 1字ずつ px に切り上げた幅で判定、足りなければ空いたセルへ広げ、だめなら `numbers_as_text`。
- ✅ H: 回転した SideRule の帯（横長の `Rectangle`）が縦線とみなされ消えた → 幅と高さで向きを決める。
- ✅ H: 半マス未満の罫線（`SideRule(top=8)` など）が記録なしに捨てられた → 捨てるのは継ぎ目の補いだけ、他は `border_off_grid`。
- ✅ M: SideRule の罫線の色が黒になる → 塗りの色。M: 同じ辺の色・種類の違う罫線が黙って消える → `border_conflict`。M: 罫線の端の位置を黙って丸める → 端も境目から太さ以内。M: 離れた原子を1セルに詰める → 半マス以上離れたら別の文字片。M: 2頁目以降の余白の図形が隣の頁に入る → 頁ごとの範囲で検査。M: 記録の型が値を検査しない・ハッシュできない・`untagged` が外から変わる → 検査と tuple 化。M: `cell_padding_pt` の仮の分岐 → `equations.excel_cell_padding_pt` を直接使う（引数は lead の指示で残す）。M: モデルの素の ValueError（改ページ 1,026 か所超・32 文字の書体名・壊れた画像・シート名）→ `XlsxError`（シートと頁付き）。M: `XlsxStrictError` が pickle・copy できない → `__reduce__`。M: 入れ子の分数で外側の分母が右にずれる → 内側の分数から処理。M: 数値なのに文字列のセルが記録されない → `numbers_as_text`（lead 判断 B）。M: 同じ用紙・グリッドで装飾が変わるとエラー → 次のシート（lead 判断 C）。M: テストの不足（match のない raises、既定の余白の検査が何も確かめていない等）→ 直した。
- ✅ L（同ラウンドで対応）: 2点の閉じた自由形状を線に、空白だけの文字を捨てる、`QuarterTurn` のタグの `local_grid` 欠けで KeyError にしない、`XlsxSheet.scale`、`cell_ref` の負の値、使っていない import。
- lead 指示: grid の項は配置の metadata からブロックの左端を求めて `first_column`・`columns` で結合（`term_off_grid`・`cell_padding_mismatch`）、折り返したラベルの各行は縦結合しない、字形のインクで列を決める（MS Mincho の `β²` の1件を解消）。
- 持ち越し（LOW）: 根号・括弧の図形は中身のセルがずれても動かない（ずらしは記録される）／`Text.shear_x` を捨てる／上付きだけが残ったセルはさらに縮む／`TextBox` の `leading` を写さない／`strict` にタグのない命令を含めない（数えて記録だけ）／`_paper` の比較は GridSpec の完全一致／ヘッダーとフッターの決め事は DESIGN で確認（lead）。
- 新しい見逃しパターン: 罫線の「同じ物理的な辺は1つ」という正しいモデルの規則が、改ページの境目では印刷の結果（頁ごとに描く）と合わない。画面の読み戻し（COM の `Borders`）では見えず、PDF への書き出しでしか見つからない。

**レビュー反映 (2026-10-20, ラウンド 2)**

レビュアー2体（silent-failure、python＋type-design＋layout）。集約: CRITICAL 0 / HIGH 2 / MEDIUM 6 / LOW 約18。

- ✅ H: 中央寄せの数値が片側だけに広がり、分子が分数線の中心から外れる（記録なし）→ 両側へ1セルずつ同時に、片側が空かなければ広げない。
- ✅ H: 印刷が 100% に収まらないと黙って縮小される（30 × 50 の A4 で最後の行 −17 pt、レビュアーの COM 実測）→ `print_scale` を記録し strict でエラー。
- ✅ M: 21 px の比で丸める振り分けは px ごとの印刷の大きさの違いで誤差が積み上がる（p30〜37 で最大 1.7 pt）→ 実測の印刷の大きさで1セルずつ選ぶ（予測の最大誤差 0.36 pt）。
- ✅ M: 入れ子の Indent で `indent_pt` が外側の値で上書きされ、grid の項の列を1列誤る → lead が containers.py を直した（和になる）。map は変更なし、左寄せ2列以上の項の単体テストを追加。
- ✅ M: 後半の処理（ヘッダー・分数線・罫線の図形）のモデルの ValueError が素のまま → `XlsxError` に包む（255 文字を超えるヘッダーのテスト）。
- ✅ M: 数値を広げると、結合の内側に入る罫線が `border_in_merge` に変わり strict のエラーになる → 結合の内側になる辺も調べて広げない。
- ✅ M: 回転した表の中の上付きの分数が `fraction_in_script` にならない → 記録は回転によらず、分母を下げるのは立っている分数だけ。
- ✅ M: `###` を出さないことを守る COM のテストがない → `test_number_cells_never_show_hashes`（レビュアーの手元の確認は 4,608 件で 0 件）。
- ✅ L（同ラウンドで対応）: 分数を含む・離れた原子で分かれた grid の項と回転した grid の項を `term_off_grid` で記録／手で作った頁の metadata の欠けを `XlsxError` に／`dropped`・`untagged` に文字列を渡すとエラー／`dropped` に頁を書く、継ぎ目の補いも `dropped` に載せる／`XlsxStrictError` が記録の型を検査、動いていないずらしはエラー／書体の混じった数値の記録／`FALLBACK_KINDS`・`SHIFT_REASONS` を `renderers.xlsx` から公開／`Document.render_xlsx` の docstring と型注釈／A4 の 21 px の検査を単体テストへ移した／振り分けの単体テスト（px の組・予測の誤差・割合の保存・半マスを超えるグリッドのエラー）。
- 持ち越し（LOW）: 11〜30 px 以外のセルの印刷の大きさは 21 px の比で予測（測っていない）／余白の負の値を 0 にする（PDF の用紙がグリッドより小さい時）／`map_reports` の引数の誤りは素の ValueError（`XlsxError` は書き出せない内容の時）／`{pages}` は渡した頁の数（帳票の一部だけ渡すと PDF の番号と違う）。
- lead 判断が要る（情報）: grid の項に分数を入れると、その項は必ず `term_off_grid` になり strict で出せない。代表例の grid 版には今は無い。
- 陰性対照: `print_scale` の記録と回転した分数の記録は、分岐を一時的に戻すとテストが落ちることを確かめた。他の修正はテストと同時に書いた。
- 新しい見逃しパターン: 「中央は両側へ」と書いた docstring の処理が、ループの `break` で片側だけになっていた。寄せ方を保つ処理は対称性をテストで縛る。

**レビュー反映 (2026-10-20, ラウンド 3)**

レビュアー2体（silent-failure、python＋type-design＋layout）。集約: CRITICAL 0 / HIGH 0 / MEDIUM 5 / LOW 約13。ラウンド2の修正に誤りは見つからなかった（予測の最大誤差は 0.5〜30 pt の刻みで 0.42 pt、回転したセルの広げ方6通り、図形の印刷位置 −0.10〜+0.63 pt をレビュアーが確認）。

- ✅ M: 二重線と細・中・太の罫線が同じ辺に来ると、どちらかが記録なしに消える（太さだけで比べ、二重線の中の隙間を「覆う」とみなしていた）→ 1本の実線が細い1本の実線を覆う時だけ覆うとみなし、他は `border_conflict`（二重線の2本は1件にまとめる）。
- ✅ M: grid の項の数値が、Excel の画面の幅で足りないと項の列を越えて広がる（記録なし）→ grid の項は広げない（足りなければ `numbers_as_text`）。
- ✅ M: 分数だけの grid の項が `term_off_grid` にならない → 文字片の単位の外側に grid の項があれば記録（項ごとに1件）。
- ✅ M: 回転したセルを広げる処理がテストで縛られていない → +1・−1 × 左・中央・右の6通りの結合の行と `v_align`、罫線で止まることのテスト。
- ✅ M: 分数の処理が文字片の数×分数の数に比例して遅い（80頁で 12 秒）→ 分数ごとの文字片の索引を1度だけ作る（600 の分数で 0.4 秒）。
- ✅ L（同ラウンドで対応）: 手で作った頁の metadata の型の誤り（IndexError・TypeError・AttributeError）も `XlsxError`／記録の順が PYTHONHASHSEED で変わる → 文字片を読んだ順で並べる（別プロセスで3つのシードのテスト）／添字の付いた数字を `number_as_text` にしない／`XlsxStrictError` の文面を「fallback(s)」に、`number_as_text` を受けない／`XlsxResult` の `untagged`・`dropped` の型の検査／未知の項の `align` は左／COM の境目のテストに「最初の境目から 1 pt 以内」（累積の誤差の戻りを捕まえる）／`###` の COM テストに中央寄せ（両側へ広げる）を追加／振り分けたグリッドで分数線と結合の内側の罫線の図形が境目に乗るテスト、分母が下端を越えるエラー・菱形・円・種類のない罫線・斜めの罫線のテスト。
- 持ち越し（LOW）: `FALLBACK_KINDS`・`SHIFT_REASONS` は `gridlayoutpdf.renderers.xlsx` だけから公開（最上位にするかは Step 10 の docs/api.md で lead が決める）／`build()` が捕まえる KeyError などは metadata の誤りとして報告される（実装の誤りも同じ文面になりうる。元の例外は `__cause__` に残る）／`block_left` は `children` を持つ最初の part を使う（1配置に複数ある例は作れなかった、未確認）／複数行の `PageDecoration` は Excel では1行のヘッダー（未確認）。
- lead への情報（判断が要る）: grid の項の列数は PDF の送り幅＋余白で決まり、Excel の画面の字ごとの px の切り上げを含まないので、grid の項の数値が文字列のまま残ることがある（代表例 IPAex明朝の grid 版の `'12.50'`。もう1件は分数の分子の `'7.381125'`）。grid-terms の列数の計算に字ごとの px の切り上げを含めるかを DESIGN の未決定事項に入れることを勧める。
- 新しい見逃しパターン: 罫線の優劣を「太さ」1つの数で比べると、形の違う線（二重線の隙間、破線）が覆われたとみなされて消える。覆うかどうかは線の形で決める。

**レビュー反映 (2026-10-20, ラウンド 4)**

レビュアー1体（silent-failure＋python＋layout、ラウンド3の修正の検証。陰性対照のプラグインでテストが修正を縛るかも確かめた）。CRITICAL 0 / HIGH 1 / MEDIUM 1 / LOW 5。ラウンド3の修正は狙いどおり（覆う判定・grid の項を広げない・分数の索引の順序・未知の align）。

- ✅ H: 分数の鍵に頁が入っておらず、1シートの2頁に同じ構造（同じ配置番号・同じタグの列）の分数があると頁をまたいで混ざり、分母が7行下がる・分数線が他の頁の行に引かれる・正しい文書が XlsxError になる（`fraction_in_script` も1件にまとまる）→ 分数と分数線の鍵に頁を入れた（Red: `xlsxmap-r4-red` 5 failed → `xlsxmap-r4-green` 161 passed）。ラウンド3の前からあったかは確認が取れていない。
- ✅ M: 添字の付いた数字のテストが何も縛っていない（空白入りの文字で数値にならなかった）→ `Script("10", superscript="3")`・`Script("2.5", subscript="1")` に変えた。
- ✅ L: `border_conflict` のまとめ方が広すぎ、別の線の負けが記録されない → 線ごと（二重線の2本はタグの `stroke` で1本）に記録／色を書き出す 8 bit の値で比べる（浮動小数の誤差で衝突にしない）／grid の項の `number_as_text` の文面を「grid の項の列（広げない）」に／grid の項を広げないテストで「文字列のまま・記録1件」を要求／太い実線が細い実線を覆う時に記録が出ないことを単体テストで縛る。
- 確認: 代表例の8通りの件数は変わらない（grid 版はずらし0・fallback 0）、COM 9 件合格。
- 新しい見逃しパターン: 「配置の中で一意」なタグの鍵を、頁をまたぐ索引（シート全体）に使うと、頁ごとに 0 から数える配置番号が衝突する。シート全体の索引の鍵には必ず頁を入れる。

**レビュー反映 (2026-10-20, ラウンド 5)**

レビュアー1体（silent-failure＋python、ラウンド4の修正の検証。`src` を複製して1か所ずつ壊す陰性対照で、テストが修正を縛るかを確かめた）。CRITICAL 0 / HIGH 0 / MEDIUM 1 / LOW 2。ラウンド4の修正に誤りはなく、シート全体の索引8つはすべて頁を鍵に含んでいた。

- ✅ M: 入れ子の分数を内側から処理する並び順がテストで縛られていない（鍵の位置での取り出し `key[2]` を取り違えても全テストが通った）→ 分数の鍵を `_FractionKey(page, place, path)`（NamedTuple）にして名前で参照し、入れ子の3つが同じ行に入る手作りの頁と 4 pt の入れ子の分数のテストを追加。
- ✅ L: 頁を鍵に含む `equation_rows`・`split_terms` の索引がテストで縛られていない → 2頁に同じ構造の式の行・分数を含む grid の項を置くテストを追加。
- ✅ L: タグの `stroke` を罫線の種類と照合していない（一重の線の `stroke=1` で別の線と同じ扱い）→ `0 ≤ stroke < 線の本数` かつ `index − stroke ≥ 0` の時だけ同じ線とみなす。
- 陰性対照（この担当が実施）: 並び順・`equation_rows` の頁・`split_terms` の頁・`stroke` の照合をそれぞれ壊すと、追加したテストが 2・1・1・1 件落ち、戻すと全件合格（`xlsxmap-r5-green`）。

**レビュー反映 (2026-10-20, ラウンド 6) とループの終了**

レビュアー1体（silent-failure＋python、ラウンド5の修正の検証。14 通りの陰性対照のうち 11 通りで追加したテストが落ち、生き残った3通りは下の L）。CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 3。

- ✅ L: `stroke` の下限・bool の除外をテストが縛っていない → `stroke` が -1・True の場合をテストに追加。
- ✅ L: 分数の範囲を持たない分数線のタグ（手で作った頁）が記録なしに PDF の位置の図形になる → 頁番号付きの `XlsxError`。
- ✅ L: 型注釈（`dict[_FractionKey, int]` など）と、`stroke` の照合を辺のループの外へ。
- 確認（`xlsxmap-r6-green`）: 単体＋読み戻し 169 passed。

**完了（ImplementationLoop）**

- 全ラウンド数 6。指摘の推移（CRITICAL / HIGH / MEDIUM）: ラウンド1 0/6/15 → 2 0/2/6 → 3 0/0/5 → 4 0/1/1 → 5 0/0/1 → 6 0/0/0。
- 最終確認: 単体＋openpyxl の読み戻し 169 passed（`xlsxmap-r6-green`）、Excel COM 9 passed（`test_xlsx_map_excel.py`）、`_map.py` の coverage 96%（`COVERAGE_FILE=.claude/logs/.coverage-xlsxmap`、ラウンド3の時点）。全テスト `xlsxmap-full`（ラウンド3の後）: 3488 passed・2 skipped・2 failed。失敗は既知の2件（`tests/visual/test_cantilever_p01_37_golden.py::test_all_37_pages_match_approved_pixels`、`tests/visual/test_representative_golden.py::test_standard_report_matches_all_approved_golden_pixels`、Step 10 で作り直す PNG 正解）、skip は `test_xlsx_excel_core.py` の DocuWorks PDF の最悪条件の2件（アクティブなプリンターが DocuWorks Printer）。xfailed は 0 件（片持ち梁の保留を cantilever 担当が作業中のため。この担当の変更とは無関係）。
- ラウンドの途中で、片持ち梁の単体テスト（`test_cantilever_appearance_builder.py`・`test_cantilever_fixture.py`）が cantilever 担当の fixture の作業途中で失敗していた時があった（`tests/fixtures/cantilever_p01_37/**` の変更による。この担当は触っていない）。
- 最後の全テスト `xlsxmap-full-final`（ラウンド6の後）: 3536 passed・2 skipped・10 failed。既知の PNG 正解の2件のほか、片持ち梁の統合テスト8件（`test_cantilever_p01_37.py::test_appearance_and_grid_rules_hold_on_all_37_pages`、`test_cantilever_source_appearance.py` の7件。内容は `p09-forces` の source line structure など）は cantilever 担当が作業中の `tests/fixtures/cantilever_p01_37/**` と片持ち梁のテストの変更によるもので、これらのテストと fixture は方眼Excel の写像を import しない（grep で確認）。

#### compare（Step 10 の検査スクリプト）

担当 compare（サブエージェント）。2026-10-20。編集するのは `scripts/compare_xlsx_pdf.py`（新設）・`tests/unit/test_compare_xlsx_pdf.py`（新設）・`tests/integration/test_compare_xlsx_pdf_excel.py`（新設、Excel がある時だけ）・この節だけ。`src/**`・`tests/fixtures/**`・既存のテスト・`examples/**` は編集しない。

**進捗**

- 着手。必読の文書と COM の流儀（`test_xlsx_excel_core.py` の `_run_excel`、`measure_print_pitch.py`）を読み、代表例（grid 版・standard）を `render_xlsx(strict=True)` で出して Excel 16.0（build 20326、プリンター「DocuWorks Printer on Ne04:」）から PDF に書き出す予備の実験をした（スクラッチ、リポジトリには書いていない）。

**予備の実験で分かったこと（実測）**

- Excel の PDF では IPAex明朝 が ＭＳ ゴシック に置き換わり、10 pt の文字は 9.96 pt、上付きは 6.60 pt で出る（ライブラリの PDF は 10・6.5 pt）。字の幅が変わるので、文字片の左端・右端・中心のどれで比べるかでずれが大きく変わる。
- PyMuPDF の span の切れ方は2つの PDF で違う（ライブラリは `A`・` `・`=` が別の span、Excel は隣のセルの文字も1つの行・span にまとまることがある。例 `1 +`）。このため Excel 側は span ではなく、同じ向き・同じ基線の文字を読む向きに並べた列の中で、空白を除いた文字列を探す。
- openpyxl で読むと、写像はすべての値のセルに寄せ方（left・center・right と縦の center）を書いている。改ページは `rowBreaks` の `brk id`（その行の下で改ページ、0 始まりの行番号ではその次の行から次の頁）。
- 式の左辺・等号・結果・単位は、分数のある式では行の範囲を縦結合して上下中央（FR-021 の確定事項）なので、Excel では PDF の基線の行より下に出る（`W = 7.381125/(2.70/2)` の3行の式のラベル「断面係数」は、文字の箱の上端がライブラリ 180.6 pt・Excel 196.9 pt で約 16 pt。縦の許容の半マス 7.74 pt を超える）。検査はこの差をそのまま報告する（合格に寄せる調整はしない）。

**進捗（RED→GREEN。ログは `.claude/logs/` の同名）**

- ✅ Red 1: `tests/unit/test_compare_xlsx_pdf.py`（37件）を、名前だけの骨組みのスクリプト（`NotImplementedError`）に対して `compare-red-1` 37 failed → 実装して `compare-green-2` 37 passed（途中の `green-1` の1件は期待値の誤り。数値のセルはインクの始まる列から始まる）。
- ✅ Red 2: 代表例で実際に回すと、表の文字片がセルに見つからず「最も近い基準」に落ちていた（ライブラリの文字の箱の中心は帯の上の行、写像は基線の行にセルを置く）。セルを Excel が印刷した字の中心で引く形に直した（`compare-red-2` 2 failed → `compare-green-4`）。あわせて `SpecialCells` が結合範囲の全セルを返して数値セルの数が合わなかった（22 に対し 65）ので、結合範囲の左上だけを数える。
- ✅ Red 3（試して戻した）: 片持ち梁の見つからない文字片を、上付きが別の列になるためと推定し、小さい字の列を基の列に足す処理を書いた（`compare-red-3` → `compare-green-5`）。結果が1件も変わらず、実際は Excel の印刷で末尾の字が切れていた（下記）ので、処理を戻し、上付きが別の列になることのテストに置き換えた（`compare-green-7` 39 passed）。
- ✅ 統合テスト `tests/integration/test_compare_xlsx_pdf_excel.py`（3件、Excel がなければ skip と理由、`GRIDLAYOUTPDF_REQUIRE_EXCEL=1` なら失敗）。数値の列が 11 px だと Excel の `Range.Text` は「###」でなく空になることを実測したので（`compare-excel-red-2` 1 failed）、空の表示も数値が見えないセルとして数える（`compare-excel-green-2` 3 passed）。

**設計判断（実装判断。ユーザー未確認）**

- 文字片: ライブラリの PDF は PyMuPDF の span ごと（空白を除く）。Excel の PDF は span の切れ方が違うので、同じ向きで基線が 1 pt 以内の字を読む向きに並べた列を作り、その中で文字列を探す（隣のセルの字と続いていてもよい）。上付き・下付きは両方とも別の列・別の span になる。
- 対応付け: 文字列の長いものから（上付きの「3」が「12.375」の「3」を取らないため）、同じ文字列の中では距離（許容で割ったずれの長さ）の近い組から、1つの字は1つの文字片にだけ割り当てる。見つからない文字片は `missing`。
- ずれ: Excel − ライブラリ（pt）。許容は読む向きに1マス・直交に半マス（横の文字は横 pitch_x・縦 pitch_y/2、回転した縦の文字は縦 pitch_y・横 pitch_x/2。計画の「横1マス・縦半マス」を読む向きで読んだ。回転表の局所グリッドはページのグリッドの縦横入替なので、局所の1列＝ページの pitch_y）。境目ちょうどは許容内（1e-6 pt）。
- 比べる点: Excel が印刷した字の中心を含むセル（openpyxl で読んだ結合範囲を、そのページのグリッドに置いたもの）の寄せ方で決める。横は左寄せ＝左端・右寄せ＝右端・中央＝中心、縦は上・中・下（回転したセルの寄せ方も紙面の向きで書かれているので、そのまま紙面の軸で使う）。根拠: Excel では IPAex明朝 が別の書体になり字の幅が変わる（実測 ＭＳ ゴシック）。セルが保つのは寄せた側の端なので、その端で比べれば書体の幅の違いがずれに入らない。セルの外の字（ヘッダー・フッター・図の字）は寄せ方が分からないので、軸ごとに左端・中心・右端（上・中・下）のうち最も小さいずれをとる（甘い側の判断なので JSON に `anchor: nearest` と残す）。
- 数値セル: Excel の `SpecialCells(xlCellTypeConstants, xlNumbers)` の各セル（結合範囲は左上だけ）の `Range.Text` に「#」がある、または空なら記録。数が openpyxl で数えたファイルの数値セルと違えば不合格（`SpecialCells` の失敗で 0 件になって合格するのを防ぐ）。
- 修復: `DisplayAlerts=False` の `Workbooks.Open` の例外（xlsx-core の実測で修復が要るブックは開かない）と、`%TEMP%` の `error*.xml` の増加。
- 終了コード: 0 合格、1 検査の不合格、2 引数の誤り、3 Excel がない（理由を標準エラーと JSON に）、4 ライブラリが書けない（strict のエラーなど。例外の型・文面・ずらしと切替えの記録を JSON に）、5 Excel が最後まで動かない（時間切れ・スクリプトの失敗・Excel が残った）。`--no-strict` でも、ずらし・図形への切替えがあれば不合格（`checks.strict`）。プリンターは読むだけで変えない。

**実行結果（2026-10-20、Excel 16.0 build 20326、プリンター「DocuWorks Printer on Ne04:」）**

| 対象 | 修復なし | ページ数（ライブラリ/Excel） | 文字片 | 見つからない | はみ出し | 最大のずれ dx / dy (pt) | ### |
|---|---|---|---|---|---|---|---|
| 代表例 grid standard | ✅ | 5 / 5 | 382 | 1 | 279 | 17.248 / 18.961 | 0 |
| 代表例 grid long | ✅ | 6 / 6 | 434 | 1 | 137 | 17.248 / 18.961 | 0 |
| 片持ち梁 p1〜37（strict で出せた、ずらし・切替え 0） | ✅ | 37 / 37 | 5430 | 15 | 1067 | 18.5 / 8.851 | 0 |

出力は `build/reports/xlsx-compare/{representative-standard,representative-long,cantilever}/`（`result.json`・`library.pdf`・`workbook.xlsx`・`excel/sheet-NN.pdf`・`side-by-side/page-NN.png`）。3つとも位置の検査で不合格。並べた画像で確かめた原因（写像の挙動。検査の誤りではない）:

1. 表のセル: ライブラリは2マスの行の帯の中央に字を置き、写像は基線の行だけのセルにするので、Excel では約 8.5 pt 下（許容 7.74 pt）。回転表 p30〜37 では横に約 5.5〜6.5 pt（許容 5.4 pt）。
2. 分数のある式の左辺・等号・結果・単位・ラベルは縦結合の上下中央（FR-021）で、2行の式で約 8.4 pt、3行の式で約 16 pt 下。
3. Excel の字の幅が広く、結合したセルの末尾の字が印刷で切れる（代表例の「…統一する。」の「。」、片持ち梁 15 片。例 p12「…x 1/2」→「…x 1/」、p16 の「]」、p01 の末尾の「＋」）。
4. 幅のある関係記号「＝±」が1列右（dx 17.3 pt、片持ち梁 p9〜11）、長いリッチテキストの後ろの添字が右へずれる（最大 18.5 pt、p16・p17）、A3 の頁の右フッター（dx 17.2 pt）。

- lead に中間報告済み。`test_xlsx_map_excel.py::test_number_cells_never_show_hashes` は「#」だけを見ていて空の表示を見逃す（この担当は既存のテストを編集しない）。

**lead 判断の反映（2026-10-20）: FR-021 の縦結合の分類 `fr021_vertical_merge`**

- lead 判断: 分数のある式の左辺・等号・結果・単位・ラベルの縦結合と上下中央は FR-021 の確定事項なので、その文字片は別の分類にし、縦は「Excel の位置がその結合範囲の中にあり、範囲の上下中央から半マス以内」、横は通常どおり1マス以内。他の文字片は今の基準。分類はタグで行い、位置から推定しない。比べるスクリプトの判定は緩めない（空の `Range.Text` の検出も残す）。表のセル・末尾の字の切れ・幅のある関係記号・添字のずれ・A3 のフッター・11 px の空の表示は xlsx-map 担当が写像を直す。
- ✅ Red 4（`compare-red-4b` 8 failed。最初の `compare-red-4` は定数がなく収集エラーだったので、定数だけ足して本物の失敗を確かめた）→ `compare-green-8` 46 passed。
- 実装: `text_categories(ScenePage)` が、回していない `Text` 命令ごとに、そのタグの最も内側の `EQUATION_LINE`（写像と同じく `MATH_BLOCK` も）の行の鍵（配置番号・path・part を外した scope。写像の `line_key` と同じ作り方）を作り、その行に分数（`FRACTION` の scope）の中の命令が1つでもあり、自分は分数の外で、行の中の最初の `EQUATION_PART` の part が label・lhs・relation・result_relation・result・unit なら `fr021_vertical_merge`。PDF の各字は、その基線（0.05 pt 以内）上で字の原点より左で始まる最後の命令に属するとし、文字片の全部の字が `fr021_vertical_merge` の命令のものならその分類（混じれば standard、厳しい側）。
- 判定（`Match.rule`）: `fr021_vertical_merge` の文字片は、Excel の字の中心を含むセルが2行以上の結合なら `merged_range`（横は |dx| ≤ 1マス、縦は Excel の字の中心と結合範囲の上下中央の差 `range_dy` が半マス以内。字の中心はセルを引いた時点で範囲の中）。セルが1行なら縦結合がないので通常の基準（`ordinary`、甘くしない）。どのセルにもなければ `no_cell` で常に不合格。
- ✅ Red 5（`compare-red-5`）: 代表例で `fr021_vertical_merge` の最大の dy が 285.7 pt になった。候補の順を `range_dy` で並べたため、どの結合範囲でも中央に近い他の式の「=」を取っていた。候補の順は常にライブラリと Excel の位置の差（dx・dy）で決め、判定だけを範囲の規則で行う（`compare-green-10` 47 passed）。
- JSON: ページごとの `pieces`・`matched`・`max_dx_pt`・`max_dy_pt` は standard の文字片だけ。`fr021_vertical_merge` の件数（pieces・matched・outside）と最大のずれ（max_dx_pt・max_dy_pt＝ライブラリとの差・max_range_dy_pt＝範囲の中央との差）は別の欄。`missing`・`outside` の各項目に `category`・`rule`・`range_dy_pt`。全体の `summary` も同じ分け方。標準出力にも2行に分けて出す。
- 同じ時刻に xlsx-map 担当が `_map.py` を編集中（表のセルが行の帯に結合されるようになっていた）。単体テストの1件が旧い写像の「数値のセルは1行」を縛っていたので、「グリッドの整数行」に直した。
- 途中の実行（写像の修正の途中、2026-10-20）: 代表例 standard は standard 364 片中 はみ出し 6（分数の分母・分子の上付きが Excel で 8.2〜10.7 pt 下、A3 の右フッター dx 17.2 pt）・見つからない 0、`fr021_vertical_merge` 18 片はすべて範囲の中央から 2.527 pt 以内（ライブラリとの差は最大 18.961 pt）。写像の修正の後に lead の指示で再実行する。

**Step 10 の比較の不合格への追加の修正（lead 指示 2026-10-20、HEAD c1e9475 の後）**

`scripts/compare_xlsx_pdf.py`（compare 担当、編集していない）の「全文字片が横1マス・縦半マス以内」の不合格を、写像の側で直した。TDD: `xlsxmap-cmp-red`（10 failed）→ 実装 → 単体＋読み戻し合格。

- ✅ 1) 表のセルの文字: 表のセル（`Kind.TABLE_CELL`）の文字片が1つだけの時は、そのセルの枠（頁の metadata の表の part の `cells` の `frame`。Stack・Columns の子の `x_pt`/`y_pt`、`indent_pt`、QuarterTurn の `local_to_part` を辿ってページの pt に直す）が頁のセルの境目に乗っていれば、枠の全セルを結合し、タグの align と valign を写す（回転した表は valign の top を +1 で左・−1 で右へ）。枠が境目から外れる・metadata から分からない時は今までどおり。複数の文字片のセルは各行をその行のセルに置く。
- ✅ 2) 分数のある式の縦結合は要件どおりで変えていない（比較スクリプトでは `fr021_vertical_merge` に分類され、範囲の中央からのずれは最大 2.5 pt）。
- ✅ 3) 末尾の字が切れる: 文字列のセル（数値でないもの）も、Excel で要る幅（字ごとに px へ切り上げた幅＋余白×2、上付きは自分の大きさで測る）が入るまで、数値と同じ規則（寄せの反対側へ、中央は両側同時、空いたセルだけ、罫線を越えず）で広げる。広げても足りない時は `XlsxResult.texts_clipped`（kind `text_clipped`、strict の対象外、件数を見て lead が決める）に記録。grid の項は広げない。
- ✅ 4) 幅のある等号: 等号は、送りの中心が PDF の中心に最も近く、空いている（左辺の取った列を除く）列の範囲に置く（2列以上の等号は anchor の境目をまたぐ）。
- ✅ 4) 長い行の後ろの添字のずれ（片持ち梁 p16・p17、最大 18.5 pt）の原因: 原子の間の空白。`Row` の既定の間隔 1.5 pt（0.15 em）に、半角の空白（MS Mincho で 5 pt）を入れていたので、空白1つごとに 3.5 pt ずつ右へずれていた。→ 空白は「PDF の間隔がその書体の空白の幅の半分以上」の時だけ入れる（間隔が空白なしより空白ありに近い時。書体に空白の幅がなければ 0.08 em）。IPAex明朝の空白は 2.9 pt なので 1.5 pt の間隔には空白が入り、MS Mincho には入らない。
- 縦の位置（追加、実装判断・ユーザー未確認）: 1行だけのセルの縦の寄せ方を、PDF の行の箱（ascent〜descent）に最も近い Excel の置き方から選ぶ（上端・下端・中央のうち差が最も小さいもの、同じなら中央）。Excel の置き方は、立った文字は実測（Excel 16.0、MS Mincho 10.5 pt、15.48 pt の行、「DocuWorks Printer」、プリンターの原点のずれを含む。レビュアーの測定）で上寄せの箱の上端がセルの上から 1.38 pt、下寄せの箱の下端がセルの下から 3.5 pt（`EXCEL_TOP_INSET_PT`・`EXCEL_BOTTOM_INSET_PT`）、回転した文字は測っていないので 0.75 pt（`EXCEL_TURNED_INSET_PT`、片持ち梁の比較で合格する推定）。式の分数の外の文字片（左辺・等号・結果・単位・ラベル・右辺）は FR-021 どおり中央のまま。分数の分子・分母（行の上寄り）、見出し、回転表の 10.8 pt の列からはみ出す行（片持ち梁 p30〜37）がこれで合う。普通の段落の行は中央のまま。縦の寄せ方は、分数で下げた後のセルで選ぶ。
- ⏭ 4) A3 の頁の右フッター「3/5」の dx 17.2 pt の原因: Excel はヘッダー・フッターの右の欄を右の余白の内側に揃える。`fit` が 100% で印刷するために右の余白を `print_fit` の係数（列 1.04、実測の最大より 0.6% 以上大きい安全側の値、Step 7）で縮める（A3 横 67 列: PDF の 62.8 pt → 42.21 pt）ので、右の欄が約 20 pt 右へ出る（A4 では 61.72 → 52.99 pt で約 9 pt、許容内）。写像の側だけでは直せない: 右の余白を PDF の値にすると 98% の印刷になり `print_scale`（strict でエラー）になる。直すには (a) `print_fit` の係数を 21 px の実測（1.0209）に近づける（Step 7 の安全側の判断を変える。他のプリンター・セルの大きさで自動の改ページが入る危険）、(b) `headerFooter` の `alignWithMargins="0"` を書く（`_sheet.py`、Excel での位置は測っていない）のどちらかで、lead・xlsx-core の判断が要る。
- ⏭ 代表例に残る2件: 分数の中の分数の分母 `'2'`（基線が行の 0.10 の所にあり、字は上の行にはみ出している。上の行は内側の分子が取っているので、行を変えられない）、分子の上付き `'3'`（Excel の上付きの位置と大きさが PDF と違う。セルの上付きは位置を指定できない）。どちらもセルの置き方では直せない。
- ✅ 5) `###` の COM テスト: 11 px の列で Excel の `Range.Text` が空になる場合も検出する。

**比較スクリプトの結果（プリンター「DocuWorks Printer on Ne04:」、Excel 16.0 build 20326）**

| 対象 | 文字片 | 範囲外（standard） | 最大 dx / dy | 判定 |
|---|---|---|---|---|
| 片持ち梁 p1〜37（strict） | 5418 | 0 | 12.72 / 8.12 pt | passed（exit 0） |
| 代表例 standard（IPAex明朝、grid） | 364 | 4（上の2件と A3 のフッター2件） | 17.25 / 8.52 pt | failed |
| 代表例 long | 414 | 5（同じ2件とフッター3件） | 17.25 / 8.52 pt | failed |

修正の前は、代表例 standard で範囲外 279 件（最大 dy 19.0 pt）、片持ち梁で 69 件だった（この担当の途中の測定）。

記録の件数（レビュー反映の後、cell_padding は `excel_cell_padding_pt`、文字列のまま残した数値は `texts_clipped` に重ねて記録しない）:

| 対象 | `numbers_as_text` | `texts_clipped` |
|---|---|---|
| 片持ち梁 p1〜37（MS Mincho） | 7（表の `537.29` など、罫線に挟まれた2列） | 2（p15 の全幅の行、p36 の `EQ`） |
| 代表例 standard / long（IPAex明朝、grid） | 2 / 2 | 6 / 43 |
| 代表例 standard / long（MS Mincho、grid） | 0 / 0 | 4 / 43 |

`texts_clipped` は画面の px で見積もった「切れうる」で、代表例の多くは本文の全幅の行と表の行。比較スクリプトでは印刷でそれらの字がすべて見つかっている（見つからない 0）ので、印刷で切れるかは確認が取れていない。IPAex明朝は Excel の PC に無く ＭＳ ゴシックで印刷されるので、IPAex の字幅による見積もりは当たらない。

**レビュー反映 (2026-10-20, ラウンド 1)**

レビュアー3体（silent-failure、python＋type-design、layout＋計画整合）。集約（重複は高い方）: CRITICAL 1 / HIGH 3 / MEDIUM 12 / LOW 約15。全テストの事前確認 `compare-full`: 3610 passed・2 skipped・9 failed（既知の PNG 正解2件と、cantilever 担当の作業途中の `test_cantilever_p01_37.py` の7件。どちらもこのスクリプトを読み込まない）。Red `compare-r1-red` 42 failed → `compare-r1-green-b` 単体 92 passed、`compare-r1-excel` 統合 5 passed。

- ✅ C1（2体）: `merged_range` の縦の判定が Excel 側の値だけ（字の中心と、その字で引いた結合範囲の中央）で、ライブラリの位置を見ていなかった（レビュアーの実験で 285 pt 離れた範囲でも合格）→ ライブラリの文字片の基線の点が結合範囲の行の上下半マス以内にあることも必須（`library_off_range`）。
- ✅ H1（2体）: Excel の字がずれてどのセルの外に出ると「最も近い基準」に落ちて幅の差でずれが打ち消された → Excel の字の中心のセルがなければ、ライブラリの文字片の基線の点（写像のセルの決め方。グリフの側へ 0.01 pt）のセルを使う。ヘッダー・フッターは装飾のタグの `align`。最も近い基準は図の字だけになり、ページごとの件数と文字列（`nearest`・`nearest_texts`）を出す。
- ✅ H2（2体）: 想定外の例外が終了コード 1（不合格と同じ）で JSON も残らなかった → ライブラリの段（build・render_xlsx・render_pdf）だけを 4 にし、それ以降の比較の失敗は新設の終了コード 6（`internal_error` を JSON に）。PowerShell が起動できない・結果が JSON でない・Excel の結果の欄が欠けている・型が違うものは `ExcelError`（5、`validate_excel_report`）。
- ✅ H3: 合否の検査（positions・strict・数値セルの数の照合）を run の単位で縛るテストがなかった → Excel の代わりの関数に、ずらし・用紙の大きさ・壊れた PDF・数値セルの数のずれ・図形の数のずれ・欄の欠けを入れ、それぞれ不合格・終了コードを確かめる。複数シートの頁の対応付け、改ページの数の合わないブックの拒否、`--no-strict` でずらしがあれば不合格、前回の出力の削除も。
- ✅ M（読み戻し）: 修復の検査は `Open` の例外だけが実体で修復ログは一度も出ていない → 新しい検査 `readback`: シートごとに Excel の `Shapes.Count` とファイルの drawing の anchor の数（グループは1）が一致すること。docstring を実態に合わせた。
- ✅ M（上付きの書式）: 上付きが基の大きさで印刷されても合格した → 字の大きさの比（Excel / ライブラリ）が 0.75〜1.33 の外なら不合格（`size`。実測は 9.96/10、6.60/6.5）。
- ✅ M（向き）: 回転した文字片が横書きの字に当たっても合格しえた → 同じ向きの字だけを候補にする。
- ✅ M（余った字）: Excel の字のうちどの文字片にも使われなかったものを `extra`（件数と最大 50 件）として出す（合否に含めるかは未決定、検討案）。
- ✅ M（許容の読み替え）: 回転した文字の許容を読む向きで取る判断はユーザー未確認 → 紙の向きの許容なら不合格になる件数を `outside_if_paper_axes` として出す（Gate 3 で確認してもらう）。
- ✅ M（引数）: `--pages` の範囲（1〜37）・増加順、`--font ""`、`--variant`/`--font` の有無を `is not None` で、`--timeout` は有限の正 → すべて終了コード 2（テスト11件）。
- ✅ M（型・不変条件）: `Box`（有限・順序）・`Piece`（空白なし・大きさ・寄せ方）・`Glyph`（1字）・`CellArea`（寄せ方）・`Match`（規則と欄の対応・正の許容）・`Target`（フォルダ名に使える名前。`--font` 由来の `/` などは `_` に）を作る時に検査。`ScenePage`・`FontRegistry`・`XlsxResult` の型、Excel の関数は `Protocol`。`_records` は `dataclasses.fields`。
- ✅ M（統合テスト）: 結合した数値セルを1回だけ数える・図形の読み戻し・回転した文字片が Excel の同じ向きの字に当たる、を Excel 実機で追加。
- ✅ M（時間）: PowerShell の区間ごとの秒数を `excel.seconds`・シートごとの `export_seconds`・`numbers_seconds` に出す（片持ち梁で Excel の合計 28 秒）。
- ✅ L（同ラウンドで対応）: 文字片0個の帳票は positions 不合格、頁の大きさの検査 `page_size`（±1 pt）、`get_text` のフラグを明示（`TEXTFLAGS_RAWDICT`。Excel のセルの切り抜きの外の字は取り出されない。レビュアーが flags=0 なら取れることを確認）、`general` などの寄せ方はエラー（写像は必ず書く）、Excel がない時も前回の出力を消す、PowerShell の後始末は自分のブックだけを閉じ、`Close` の失敗で `Quit` を飛ばさない、PID のファイルがない失敗の報告。
- 持ち越し（LOW）: 字の列が離れたセルの字を続けてつなぐため、診断の帰属がずれうる（不合格を合格にはしない）／1字の文字片が別のセルの途中の字に当たりうる（推測、実例なし）／統合テストが非公開の `_model`・`_package` を使う／`main` をサブプロセスで動かすテストはない。
- 統合テストの追加分は Red を先に回していない（`shapes` の欄が前の版になかったので、前の版では KeyError で落ちる）。
- 現在の写像（xlsx-map 担当の修正の途中）での実行: 代表例 standard は standard 364 片中 はみ出し 4（分子の上付き「3」と内側の分母「2」が dy 8.3・8.5 pt、A3 の右フッター 2頁が右寄せの基準で dx 19.1 pt）・見つからない 0・最も近い基準 6（図のラベル）、`fr021_vertical_merge` 18 片すべて合格（範囲の中央から最大 2.527 pt）。long は standard はみ出し 5。片持ち梁は全検査合格（5418 片、`fr021_vertical_merge` 0 片、紙の向きの許容なら不合格 6 片）。

**レビュー反映（比較の修正, ラウンド C1）**

レビュアー2体（silent-failure＋python、layout＋type-design＋計画整合。陰性対照・COM の実測・比較スクリプトで確かめた）。集約: CRITICAL 1 / HIGH 2 / MEDIUM 6 / LOW 約12。

- ✅ C: 上付き・下付きだけの文字片（`Script(Fraction(...), "2")` の親の単位）で `check_clipped` が `StopIteration`（HEAD では動いた）→ 基の原子が無ければ最初の原子。テスト追加。
- ✅ H: 幅のある等号の中央寄せが、後から置く左辺の分数の分母の列を取り、分母が8列ずれる → まだ置いていない文字片の予定のセル（全文字片の初めの範囲）も避ける。
- ✅ H: 1行の式の左辺・等号・結果・単位が 11〜12 pt で上寄せになる（FR-021 の「上下中央」と食い違う）→ 式の分数の外の文字片は中央に固定。
- ✅ M: 表のセルの余白が Excel の余白と大きく違うと、枠いっぱいにした文字が PDF から 1マス以上ずれる → Excel の寄せ方で枠に置いた位置が PDF から半マス以内の時だけ枠いっぱいにする（`frame_keeps_place`、立った文字）。metadata の辿り方を誤った時に黙って文字が動くことも、これで防ぐ。
- ✅ M: 数値が `numbers_as_text` と `texts_clipped` に二重に記録される → 文字列のまま残した数値は `texts_clipped` に重ねない（件数の表を直した）。
- ✅ M: 下寄せの位置の推定（1 px）が実測で約 3 pt 外れる → 立った文字は実測の値（上 1.38・下 3.5 pt）に、回転した文字は推定のまま（上の「縦の位置」）。
- ✅ M: `cell_frame` の各分岐がテストで縛られていない → Indent した Stack・KeepTogether の中の表、−1 回転の表、分割した表の2頁目と繰り返すヘッダー、端数の Indent の表のテストを追加。
- ✅ M（計画・文書との食い違い）: DESIGN の「等号は境目の右の列から」（4）、文字列を広げる処理と `texts_clipped`、表のセルを枠いっぱいにすること、縦の寄せ方の選び方、空白の閾値、Excel の置き方の値は、lead が DESIGN（実装判断・ユーザー未確認）と `docs/api.md`（`XlsxResult` の項目と strict の対象外に `texts_clipped`）に載せる必要がある（この担当は DESIGN・api.md を編集しない）。`scripts/compare_xlsx_pdf.py` の result.json は `numbers_as_text` だけを出す（`texts_clipped` も出すかは compare 担当・lead へ）。
- ✅ L（同ラウンドで対応）: rich text の幅を原子ごとの書体で測る（同じ文字の run が混ざらない）／縦の寄せ方を分数で下げた後のセルで選ぶ／`texts_clipped` の文面を「切れうる」（見積もり）に／記録の型（`_NOTE_KINDS`）と等号の同点（右を取る）のテスト／`_Piece.valign` の型を Literal に／残っていた何もしない代入を削除。
- 確認: 単体＋読み戻し 198 passed。比較スクリプト: 片持ち梁 p1〜37 は passed（範囲外 0、最大 12.72 / 8.12 pt）、代表例 standard 範囲外 4・long 5（入れ子の分数の分母 `'2'`、分子の上付き `'3'`、A3 のフッター。A3 のフッターの今回の実測は dx 19.14 pt）。
- 持ち越し（LOW）: `EXCEL_TURNED_INSET_PT` は測っていない／空白の閾値は IPAex明朝で 1.45 pt と Row の間隔 1.5 pt の差が 0.05 pt しかない（Excel では代わりの書体で印刷され、空白の幅が違う）／`texts_clipped` の画面の見積もりと印刷の関係は確認が取れていない。

**レビュー反映 (2026-10-20, ラウンド 2)**

レビュアー2体（silent-failure、python＋type-design＋layout。陰性対照 40 通りで、壊しても通るテストを探した）。集約: CRITICAL 0 / HIGH 2 / MEDIUM 8 / LOW 約19。Red `compare-r2-red` 29 failed・`compare-r2-red-b` 1 failed → `compare-r2-green-e` 単体 125 passed、`compare-r2-excel` 統合 5 passed。

- ✅ H（Excel 実機でレビュアーが確認）: Excel がセルの境目で字を一部切っても、PyMuPDF はその字を取り出し、位置の検査に合格した（`TEXTFLAGS_RAWDICT` で外れるのは切り抜きから完全に外れた字だけ）→ 新しい不合格 `clipped`。各セルに `printable`（Excel が文字を印刷する範囲。読む向きに沿って、1つのセルの立った文字はその寄せ方の空く側へ、次の値のあるセルかグリッドの端まで。結合範囲・数値・回転した文字は自分のセルだけ）を持たせ、照合した Excel の字の箱がその範囲を `CLIP_TOLERANCE_PT` = 1.5 pt 超えて出たら不合格。字はそれぞれ自分の中心のセルで判定する（ライブラリの1つの span「－1.350」が Excel では符号の T と数値の W:X の2つのセルだった。初めは片のセルだけで判定して片持ち梁 p28・p29 などで 46 件の誤検出、画像で切れていないことを確かめて直した、`compare-r2-red-b`）。1.5 pt は Step 8 で実測した印刷の境目のずれ（最大 1.26 pt）を覆う値で、それより小さい切れは検出しない（記録した限界）。実測の根拠: 代表例 long p1 の「す」は箱が 537.14 pt まで、Excel の切り抜きと字のインクの右端がともに 534.12 pt（約 2 pt 切れている）。片持ち梁 p15 の「査」も同じ（536.49 pt に対しインクは 534.125 pt で止まる）。
- ✅ H: 本番の経路でライブラリの基線の点（`lookup`）を作る処理がテストで縛られていなかった → 横書き・rotate 90・270 の PDF で `lookup`（基線からグリフの側へ 0.01 pt）と大きさを確かめるテスト。
- ✅ M: 大きさが分からないと黙って合格した → 片か字の大きさが不明なら `size_unknown` で不合格。手で作るテストは補助関数 `P` で 10 pt を渡す。
- ✅ M: 出力先に書けない時（`--out` が既存のファイル等）に終了コード 1・JSON なしだった → `main` が OSError を受けて終了コード 6 と標準エラー。
- ✅ M（lead 判断どおりに戻した）: ラウンド1の H の代わりのセル（ライブラリの基線の点）が `fr021_vertical_merge` にも効き、「どのセルにもなければ常に不合格」を緩めていた → `fr021_vertical_merge` の片は Excel の字の中心のセルだけで引く。
- ✅ M: 合否が `fr021_vertical_merge` の不合格を縛る run 単位のテストがなかった → 分数の行だけの文書を Excel の代わりの関数で写すと、standard は合格のまま `fr021_vertical_merge` だけが `range_dy` で不合格になり positions が不合格になるテスト。ページごとの `outside_count`（standard）・`fr021_vertical_merge.missing` を追加。
- ✅ M: 分類の2つの条件（part が FR021_PARTS、文字片の全部の字が FR021 の命令）がテストで縛られていなかった → 分数の外の右辺の項（「7×」）が standard、`piece_category` の表のテスト。
- ✅ M: 「最も近い基準」に落とす対象を位置で決めていた → タグで決める。図（`Kind.FIGURE`）の字だけが最も近い基準、ヘッダー・フッターは装飾の寄せ方（セルより優先）、それ以外でどのセルにもない片は `no_cell` で不合格。
- ✅ M: どの文字片にも使われなかった Excel の字を合否に入れていなかった → 新しい検査 `no_extra_text`（今の3つの対象では 0 件なので合否は変わらない）。
- ✅ M: 写像の `texts_clipped` と `dropped` を JSON に書いていなかった → `xlsx.texts_clipped`（頁と内容）・`xlsx.dropped`（件数）。
- ✅ L（同ラウンドで対応）: 比べたページがない時に `page_size` が合格になった、ページごとに Text の命令があるのに文字片が 0 なら positions 不合格（`text_commands`）、字の命令への割り当てを自己検査（命令ごとに割り当てた字の数がその文字の数と違う、またはどの命令も描いていない字があれば ValueError → 終了コード 6。回転した命令も読む向きで割り当てる）、`CommandInfo` を NamedTuple に、`Match` の不変条件（許容は正の2つ組、範囲の規則は fr021 の片だけ、基準の値、大きさの比）、Excel の結果の各欄の型と負でない数・`hashes` の要素の検査（終了コード 5）、内部エラー時は `checks_complete: false`、ブックの関係（rels）を Type で選び絶対パスの target と外部の関係を扱う、`excel.temp`（PowerShell の `%TEMP%`）を記録、`_rule` の docstring を実態に。
- 持ち越し（LOW）: 写像の `equation_rows` は分数の外の右辺の項も行に縦結合するので、そういう式では通常の基準で約 8 pt の不合格が出る（厳しい側。今の代表例・片持ち梁にはない。lead の判断が要る）／境目ちょうどに中心がある字のセルは並びの先のものになる（実際の Excel の印刷では起きにくい）／`_paper_outside` が許容から升目を逆算している／字の列が離れたセルの字をつなぐ（診断の帰属）／`main` をサブプロセスで動かすテストはない／統合テストが非公開の `_model` を使う。
- 現在の写像での実行（xlsx-map 担当の修正の途中の版、Excel 16.0 build 20326、DocuWorks Printer on Ne04:）: 代表例 standard は standard 364 片中 はみ出し 7（段落の行の末尾の字が切れる 3、分子の上付き「3」・内側の分母「2」の dy 8.3・8.5 pt、A3 の右フッター 2 頁の dx 19.1 pt）・`fr021_vertical_merge` 18 片すべて合格。long は standard 414 片中 15。片持ち梁は 5418 片中 1（p15 の結合した段落の末尾「査」が切れる）、ほかの検査はすべて合格。

**レビュー反映 (2026-10-20, ラウンド 3)**

レビュアー2体（silent-failure：Excel の PDF の切り抜きを外して描き直し画素で比べる実験、python＋type-design＋layout：陰性対照 61 通り）。集約（重複は高い方）: CRITICAL 0 / HIGH 1 / MEDIUM 3 / LOW 約16。Red `compare-r3-red` 11 failed → `compare-r3-green` 単体 140 passed、`compare-r3-excel` 統合 5 passed。

- ✅ H: `clipped` は読む向きの切れしか見ていなかった。片持ち梁 p30〜37 の回転表で 183 字のインクが直交する向き（字の頭）に最大 1.53 pt 切れ、代表例の 12 pt の見出しの上端も最大 0.48 pt 切れていたが合格していた（レビュアーが描き直しの画素の差で確認）→ セルの印刷範囲のモデル（`printable`・`CLIP_TOLERANCE_PT`）をやめ、Excel が実際に切ったインクを測る `ClipLoss` にした。Excel の PDF を、そのままと、全ページの内容ストリームと全フォーム XObject から切り抜きの演算子（`W`・`W*`）を除いたものの2通りに CLIP_ZOOM（4 px/pt）・グレーで描き、差が CLIP_LEVEL（64）を超える画素が字の箱の中にあれば、その字（`Glyph.clipped`）と片（`Match.clipped_glyphs`、JSON の `outside[].clipped_glyphs`）を不合格にする。両方の軸と回転した字に効く。切り抜きの除去は字句に分けて行う `without_clipping`（文字列の中の「W n」は触らない。インライン画像 `BI` は安全に飛ばせないので ValueError → 終了コード 6）。
- ✅ M（2体）: 切れた字の中心が隣の値のあるセルに入ると見逃す、`printable` の分岐がテストで縛られていない → 上のモデルの廃止で解消（関係するテスト3件を、実際の切り抜きを持つ PDF で、行の向き・直交する向き・回転した字の頭の切れを確かめるテストに置き換えた）。
- ✅ M: タグから片の属性を作る本番の経路（回転 ±1 の割り当て、図・装飾の印）がテストで縛られていない → turns=+1 と −1 の `QuarterTurn` の片が縦で standard、`Figure` の `Label` の片が `figure`、右寄せのフッターの片が `align="right"` のテスト。
- ✅ L（同ラウンドで対応）: 図の字はセルを引かない（図は図形なので最も近い基準）、`nearest` は図の字だけを数える、`no_cell` の片は JSON の dx・dy を null に、`workbook_shapes` のパッケージに workbook がない時の名前の付いた ValueError と、Type で選ぶ・外部の関係・絶対パスの関係を手で作った zip で確かめるテスト、bool の数・シートなしで開いたの検査のテスト、終了コード 4・5 でも `checks_complete: false`、ライブラリの段の OSError（ファイルが開かれている等）は終了コード 6（出力の失敗）、`TEXT_FLAGS` の注記を実態に（MuPDF が捨てるのは切り抜きから完全に外れた字だけ）、`CommandInfo` の `turns`・`glyphs` を必須に、`Piece.lookup` の要素数の検査、どのセルにもないフッターが位置どおりなら合格するテスト。
- 持ち越し（LOW）: `xlsx.dropped`（大きさのない図形）は記録だけで合否に入らない（2段目は文字片の検査。線・図形は並べた画像の目視で見る前提を Gate 3 の依頼に書く）／JSON の欄の名前（`missing` は一覧、`missing_count`・`summary.missing` は数）。
- 時間: 片持ち梁 117 秒（描き直しの比較を含む）、代表例 16〜24 秒。
- 現在の写像（xlsx-map 担当の修正の途中）での実行: 代表例 standard は standard 364 片中 はみ出し 11（見出し・段落の行の字が切れる 7、分子の上付き「3」・内側の分母「2」の dy 8.3・8.5 pt、A3 の右フッター 2 頁の dx 19.1 pt）、`fr021_vertical_merge` 18 片すべて合格。long は standard 414 片中 19。片持ち梁は 5418 片中 30（回転表 p30〜37 の字の頭が切れる 29、p15 の段落の末尾 1）。見出し「橋脚部材の計算整理」の頭と p30 の「ﾓｰﾒﾝﾄ」の頭が切れていることを、描き直しとの差の画像で確かめた。

**レビュー反映（比較の修正, ラウンド C2〜C4）とループの終了**

- C2（silent-failure＋python＋layout、24 通りの陰性対照、Excel の置き方の独立した実測）: CRITICAL 0 / HIGH 0 / MEDIUM 3 / LOW 7。MEDIUM はどれも「修正をテストが縛っていない」（`planned`、分子・分母を中央に固定しない側、`frame_keeps_place` の縦の判定）→ テストを直した。LOW: 書体の混ざった数値の二重記録、同点のテストを 2 進で正確な格子に、原子ごとの書体で幅を測るテスト、`zip(strict=True)`、定数のコメント（測定条件に標準の書体）。Excel の置き方の実測は 上 1.10〜1.19 pt・下 3.47〜3.76 pt（印刷した罫線から）で、定数と合う。
- C3（silent-failure＋python、15 通りの陰性対照）: HIGH 1 / MEDIUM 1 / LOW 3。HIGH は C2 の修正の回帰（書体の混ざった数値を広げなくなった）→ rich text の数値も広げ（`check_clipped(record=False)` が足りない理由を返す）、記録は `numbers_as_text` の1件にまとめる。MEDIUM: 下寄せ・中央の縦、中央の横の判定のテストを追加。
- C4（silent-failure＋python、17 通りの陰性対照）: CRITICAL 0 / HIGH 0 / MEDIUM 1 / LOW 3。MEDIUM は「中央寄せで枠いっぱいになる側」のテストが無い → `test_a_centred_cell_with_even_padding_fills_its_cell` を追加し、横の中央の式を左寄せの式に変えると落ちることをこの担当が確かめた（再レビューはしていない）。LOW: grid の項の rich text の数値の文面、`XlsxResult` の docstring（文字列のまま残した数値は `numbers_as_text` だけ）、`EXCEL_TURNED_INSET_PT` のコメント → 直した。
- 縦の寄せ方の規則の変更（C3〜C4 の間、lead 了承）: 上寄せ・下寄せは中央より `CROSS_ALIGN_MARGIN_PT`（1 pt）以上近い時だけ。比較スクリプトに新しく入った clipped の検査で、下寄せの 12 pt の見出しと右寄せの回転した行の字が「切れる」と出たため、近い時は字の切れない中央にする。片持ち梁 p30〜37 の回転表は PDF の字が 10.8 pt の列の境目をまたぐ（ローカルの行に基線を 11 pt 前後で置くため約 4.4 pt はみ出す）ので、中央では位置の検査で 63 件が dx 5.5〜6.5 pt（許容 5.4 pt）。lead の判断で写像は中央（切れない方）のまま、回転表は fixture 側（cantilever 担当）で各行の字をローカルの1行に収める。
- 最終確認（`xlsxmap-cmp-final`）: 単体・openpyxl の読み戻し・Excel COM で 3316 passed。比較スクリプト（「DocuWorks Printer on Ne04:」）: 片持ち梁 p1〜37 は p30〜37 の 63 件（上の回転表）と p15 の clipped 1 件のほかは合格、代表例 long は範囲外 15（clipped 10・入れ子の分母と上付き 2・A3 のフッター 3）。

**全幅の行の clipped の原因（lead の問い、修正はしていない）**

(b)（Excel の字の幅が PDF より広い、正確には PDF の行が Excel のセルの余白の分を残していない）であって、(a)（本文の枠がグリッドより右へ出る）ではない。`profile.body_rect` の右端はどの頁もグリッドの右端と同じ（A4 の基準で 533.28 pt、片持ち梁で 549.36 pt）。

| 行 | PDF の行の右端（送り / インク） | グリッドの右端 | 行の幅（PDF） | Excel で要る幅（字ごとに px へ切り上げた画面の見積もり＋余白 2.4 pt×2） | Excel のセルの幅（画面 / 印刷） |
|---|---|---|---|---|---|
| 代表例 long p1・p6 の本文の全幅の行（9件） | 530.88 / 529.1〜530.4 pt | 533.28 pt | 480.00 pt | 508.8 pt | 30 列: 472.5 / 482.4 pt |
| 代表例 long p1「矩形断面の幅を b、…」 | 533.22 / 532.40 pt | 533.28 pt | 482.34 pt | 511.05 pt | 同上 |
| 片持ち梁 p15「a) 使用性の照査…」（F 列から） | 531.28 / 530.73 pt | 549.36 pt | 400.00 pt | 424.8 pt | 空いている 25 列: 393.75 / 402.0 pt |

- 代表例の行は PDF の字幅（IPAex明朝）で本文の幅 482.4 pt に 480〜482.3 pt を詰めて組まれ、Excel のセルの内側の余白（片側 2.4 pt）の入る余地がない。印刷のセルの幅は PDF と同じ 482.4 pt でも、余白を引いた 477.6 pt に 480 pt の字は入らない（しかも Excel は IPAex明朝を持たず ＭＳ ゴシックで印刷し、字幅が変わる）。比較スクリプトで切れたのは各行の最後の字1つ。
- 片持ち梁 p15 の行は、PDF ではグリッドの右端まで 18 pt 余るが、写像が広げられたのは 25 列まで（26 列目以降は他の文字片か罫線が取っている）で、400 pt＋余白 4.8 pt が印刷の 402 pt に入らない。
- 意見: シートに列を足すのは筋でない（1マス＝1セルと改ページ・印刷の拡大率の前提が崩れ、グリッドの外の列はページの右の余白に印刷される）。PDF 側で、方眼Excel に出す文書は段落の折り返し幅から Excel のセルの余白（`excel_cell_padding_pt` の両側）を引いて組む方が筋（grid の項が余白を列の幅に含めるのと同じ考え方。例: 段落・見出しに、grid の項と同じく Excel の余白を残す指定を足す）。ただし Excel が別の書体で印刷する IPAex明朝では字幅の差が残るので、余白を残しても切れないとは言い切れない（MS Mincho の片持ち梁では字幅は同じ）。

**A3 の右フッターの修正（lead の指示 (1)、2026-10-20）**

lead の許可で、この件に限り `_units.py` を編集した（`_sheet.py` は変更していない）。COM の実測はすべて Excel 16.0 build 20326、アクティブなプリンター「DocuWorks Printer on Ne04:」（設定は変えていない）。

- 原因: Excel はヘッダー・フッターの左・右の欄を余白に揃える（`alignWithMargins` の既定）。写像は 100% にするため右の余白を `print_fit` の段の係数 1.04（12 px・93% の最大 1.0322＋0.6%）で縮めていて、A3 は PDF の 62.8 pt から 42.21 pt、A4 は 61.72 pt から 52.99 pt になっていた。
- 実測（案の比較、代表例 long の grid 版のシートで右の余白だけを変えた）:
  - PDF の余白のままでは 100% で収まらない。A4（30 列）は右 61.0 pt で列が次の紙に出て（4 頁）、60.0 pt で収まる。A3（67 列）は 61.5 pt で出て、61.0 pt で収まる。
  - 案 (b) `alignWithMargins="0"`: 左・右の欄は余白に関係なく紙の端から約 54 pt（0.75 in）に置かれた（右の余白 62.8・42.21 pt のどちらでも、右の欄の右端は紙の右端から 54.9 pt、左の欄は 54.98 pt から）。今の PDF の余白では1マス以内になるが、PDF の余白が 54 pt から離れるほどずれるので、筋でないと判断した。
  - 案 (a) の基礎データ: 印刷した大きさ（print_pitch.json の 100%）の合計に対して Excel が要った余裕は、12・21 px の 2〜10 列・行で 3.0 pt を超え 4.0 pt 以下、20・30 で 3.0 pt 以下、A4 の基準グリッド 30 列で 2.0 pt 以下、A3 の 67 列で 1.3 pt 以下（游ゴシック 11）。
  - 段の係数を下げるだけ（1.04 → 規則の下限 1.0384）では A3 の右の余白が約 43.9 pt にしかならず、1マス以内に入らない。
- 採った案 (a): 100% の判定にだけ、測ったセルの大きさ（11〜30 px）の印刷の大きさを使う。`_units.FULL_SCALE_PRINTED_PT`（2書体×20 幅の列と行、print_pitch.json の 100% の値）、`full_scale_size_pt(sheet, font)` = 印刷の大きさの合計 × `FULL_SCALE_MARGIN`（1.006）＋ `FULL_SCALE_ROOM_PT`（4.5 pt、実測の最大 4.0 pt に 0.5 pt の余裕）。測っていない大きさのセルがあれば None（段の係数だけ）。`print_fit` は maximum が 100 で段の判定が 100 未満の時、幅と高さのそれぞれが段の係数か `full_scale_size_pt` のどちらかで収まれば 100%（報告する係数はその大きさ／シートの大きさ）。写像の `fit()` は軸ごとに2つの規則の小さい方まで余白を縮める。`_map.PRINTED_COLUMN_PT`・`PRINTED_ROW_PT` は `FULL_SCALE_PRINTED_PT` の游ゴシックの値を使う（同じ数の二重定義をやめた）。
- 結果: A4 の右の余白 54.6 pt、A3 は 51.34 pt、下の余白はどちらも 50.86 pt（前は 47.04 pt）。全ページ 100%、頁の数は改ページどおり（比較スクリプトの page_count 合格、追加の統合テストで各シート1頁）。ヘッダー・フッターの PDF からの横のずれ（A4 / A3）: 左 1.22 / 0.98 pt、中央 3.28 / 5.08 pt、右 6.30 / 10.02 pt（1マス 16.08 pt）。比較スクリプトの範囲外は、代表例（IPAex明朝、grid）standard 7 → 5、long 15 → 12（A3 のフッターがなくなった。残りは全幅の行の clipped と、入れ子の分母・上付きの dy）。
- テスト（TDD）: Red は `xlsxmap-a3-red-unit2`（8 failed。初回は関数が無く collection error だったので、空の関数を置いて実際の失敗を確かめた）、`xlsxmap-a3-red-map`（2 failed）、`xlsxmap-a3-red-com`（A3 の右寄せで dx 19.1 pt の failed）。Green は単体 `xlsxmap-a3-green2` 3323 passed、統合（`GRIDLAYOUTPDF_REQUIRE_EXCEL=1`）`xlsxmap-a3-green-com` 488 passed・2 skipped（skip は従来どおり DocuWorks PDF の最悪条件の2件）。Step 7 の統合テスト `test_xlsx_excel_core.py` は全件合格。
  - 新設: `tests/unit/test_xlsx_full_scale.py`（表が print_pitch.json の 100% と一致、余裕の計算、測っていない大きさは None、100% の境目、段の係数で収まる頁は従来どおり、maximum 99 では使わない、軸ごとにどちらの規則でもよい）。`test_xlsx_map.py` に余白の縮め方のテスト。`test_xlsx_map_excel.py` に、`full_scale_size_pt` ちょうどの印刷範囲で 2書体×12・21・30 px×2・20 列（行）が1枚に収まるテストと、左・中央・右のヘッダー・フッターが A4・A3 で PDF から1マス以内のテスト。
  - 陰性対照: `FULL_SCALE_ROOM_PT` を 2.0 にすると、上の統合テストで 24 件中 13 件が2枚に分かれて落ちた（`xlsxmap-a3-negctl`）。
  - Step 7 の単体テストの変更（理由: 旧い限界 52.99・42.21 pt を値として固定していたため）: `test_xlsx_units.py` の `test_reference_a3_landscape_grid_prints_at_100_percent_with_margins_left_for_the_print_factor`（99% になる余白を 42.3 から 51.35 pt に）と `test_handoff_margins_for_100_percent_are_exact_upper_limits`（限界を 54.6・51.34 pt、下 50.86 pt に）。`test_xlsx_map.py` の `test_pages_that_print_under_100_percent_are_recorded` は、50 行の格子が新しい規則で 100% になるので、54 行の格子に変えた。
- レビュー（ImplementationLoop、ラウンド F1、レビュアー1体: silent-failure＋python＋計画整合、浮動小数の走査 17,694 通り）: CRITICAL 0 / HIGH 0 / MEDIUM 2 / LOW 8。
  - ✅ M1: 0.01 pt に切り捨てた余白が 0.01 の倍数ちょうどの時、印刷範囲を引き算で戻すと 1 ulp 足りず 99% になる（A3 横、18 px×29 列で右 732.57 pt）→ 切り捨ての前に `_HUNDREDTH_GUARD`（1e-6 ×0.01 pt）を引く。その例を写像の単体テストにした（Red `xlsxmap-a3-r1-red`: strict で print_scale 99% → 右 732.56 pt・100%）。
  - ✅ M2（記録で対応、lead の判断に残す）: 段の係数は 100% で 2〜10 セルに要る 3〜4 pt の余裕を含まないのに、軸ごとの「どちらか」でそれを受け入れ、新しいテストがそれを期待値にしていた → 段の係数で 100% を認める挙動は Step 7 のまま（変えると Step 7 の `_worst_measured_cases` の 100% の場合と `test_worst_case_generator_skips_conditions_print_fit_cannot_return` が変わる）。テストを、幅が段の係数で十分に収まる 30 列の組に変え、`print_fit` の docstring に限界を書いた。数セルだけの印刷範囲を段の係数の端で切った時に2枚に分かれるかは Excel で確かめていない（確認が取れていない）。
  - ✅ L: `fit()` の docstring（小さい方）、maximum が 100 の時だけ実測の大きさを使うこと（maximum=99 で 99 未満になりうる）を docstring に、テストのコメント、「20 and 30 cells」、新しい2つの COM テストは Step 7 と同じく測っていないプリンターで xfail、エラー文と px の求め方（`column_pixels`）。
  - 申し送り（L4、lead）: 余裕の実測の生データ（ページ数の JSON）はスクラッチ（`scratchpad/xlsxmap/ecom1/pages.json`・`ecom2/pages.json`・`fcom1`）にだけあり、`scripts/xlsx_probe/` に測定スクリプトと JSON はない。L8: `PrintFit` の係数は実測の規則では「要る大きさ／シートの大きさ」（4.5 pt を含む）。使うのは `_map.fit` だけ。
  - 確認: 単体 `xlsxmap-a3-r1-green` 3334 passed、COM `xlsxmap-a3-r1-com`（test_xlsx_map_excel.py）13 passed、Step 7 の COM `xlsxmap-a3-r1-core` 33 passed・2 skipped。
- ラウンド F2（同じレビュアー、F1 の修正の確認。2つの走査をやり直して失敗 0）: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 1。LOW: 新しい COM テストのプリンターの判定が DocuWorks PDF も「測った」扱い → 判定を「DocuWorks Printer on 」だけにし、docstring に DocuWorks PDF は 21 px の列の間隔だけと書いた（`xlsxmap-a3-r2-com` 13 passed）。
- ループの終了: 2 ラウンド（CRITICAL / HIGH / MEDIUM: F1 0/0/2 → F2 0/0/0）。
- 確認が取れていないこと（A3 のフッター）: DocuWorks PDF では 21 px の列が 100% で同じ 16.08 pt の間隔で印刷されることだけを見ていて、余裕と他の大きさは測っていない。ほかのプリンターのドライバーも測っていない（その場合に列が次の紙に出るおそれは、段の係数だけの時より大きい）。ＭＳ 明朝 10.5 の余裕は境目のテスト（4.5 pt で1枚）だけで、要る余裕の大きさは測っていない。

**MS Mincho の代表例の測定（lead の指示 (2)、修正はしていない）**

比較スクリプト `--example representative --variant standard|long --font "MS Mincho"`（grid 版、上の A3 のフッターの修正の後の写像）。Excel の PDF の書体は MS-Mincho（IPAex明朝の時は ＭＳ ゴシックと Calibri）で、書体は PDF と同じ。

| 対象 | 範囲外（standard の片） | うち全幅・表の行の clipped | ほか | `texts_clipped` | `numbers_as_text` |
|---|---|---|---|---|---|
| standard（MS Mincho） | 4 / 364 | 2（p1 A2、p5 A2） | 上付き「3」L53・入れ子の分母「2」M58 の dy 8.1・8.5 pt | 4（p1 A2・A6、p5 A2、p2 の「β2」N73） | 0 |
| long（MS Mincho） | 13 / 414 | 11（p1 A2・A7・A8・A9、p2 の表の「鉛直方向の作用値」A66・「水平方向の作用値」A69、p6 A2〜A6） | 同じ dy 2件 | 43（p1 の5行、p2 の3件、A3 の p3〜p5 の BA 列 30件、p6 の5行） | 0 |
| 比較: standard（IPAex明朝） | 5 / 364 | 3 | 同じ dy 2件 | 6 | 2 |
| 比較: long（IPAex明朝） | 12 / 414 | 10 | 同じ dy 2件 | 43 | 2 |

- 書体が同じでも、全幅の行の末尾の字の切れは残る（standard 2 行、long 9 行。どれも最後の字1つ）。上の原因の分析（PDF の行が Excel のセルの余白を残していない）と合う。
- long の p2 の表のラベル2件は MS Mincho の時だけ切れた（IPAex明朝では切れていない）。
- `texts_clipped` の見積もりのうち、A3 の BA 列の 30 件、p1 A6、p2 の「β2」は、比較スクリプトでは切れていない（見積もりは画面の px による上側の見積もり）。

**レビュー反映 (2026-10-20, ラウンド 4)**

レビュアー1体（silent-failure＋python。Excel 実機の実験と陰性対照）。CRITICAL 0 / HIGH 1 / MEDIUM 3 / LOW 10。3つの実出力の `clipped` 119 字はすべて本当に切れており（誤った不合格 0）、字の箱の外の差は 0 だった。Red `compare-r4-red` 11 failed（最初の版はテストの補助関数が画素の配列を字ごとに写して止まらず、止めて直した）→ `compare-r4-green-b` 単体 147 passed、`compare-r4-excel` 統合 5 passed。

- ✅ H: run の単位で ClipLoss が使われていることを縛るテストがなかった（本番の呼び出しを外しても全件合格）→ Excel の代わりの関数に `clip=`（頁をフォーム XObject として切り抜きを通して見せる）を加え、最初の段落の最後の字「元」を切ると、その片が `clipped`・`clipped_glyphs == ["元"]` で positions が不合格になるテスト。これで、フォームの /BBox も切り抜きになることが分かり（`show_pdf_page` は W ではなく /BBox で切る）、写しでは全フォームの /BBox も広げるようにした。
- ✅ M（判定を緩めない側で直した）: 4 px/pt のページ全体の描画では 0.08〜0.19 pt の切れを見逃し、画素の位相で結果が変わった → 字の箱ごとに 16 px/pt で描く（`ClipPage.clipped`、表示リストを頁ごとに1度作る）。0.3 pt の切れを位相 0・1/16・1/8 pt で見つけ、0.3 pt 上なら見つけないテスト。CLIP_LEVEL 64 の根拠（縁の画素でインクが全部内側なら差は 255 c (1 − c) ≤ 63.75、実測の最大 46）を注記。代表例と片持ち梁の現在の出力で、レビュアーの頁全体の描き直し（6 px/pt）と切れた字の数が一致した（代表例 3、片持ち梁 1）。
- ✅ M: 切り抜きで取り出されなくなった字のインクが、隣のセルの字の切れとして報告された（Excel 実機でレビュアーが確認）→ 切り抜きを外した写しにだけある字を `ClipPage.dropped` とし、頁の JSON に `clipped_out`（字と箱）・`clipped_out_count`、全体の `summary.clipped_out` に出す。1字でもあれば positions を不合格に。隣の字の判定では、それらの字の箱の中の差を数えない。`TEXT_FLAGS` の注記を実測に合わせた（Excel の PDF では中心が切り抜きの外の字は取り出されない。合成の PDF では取り出されたので、テストは字全体が外にある場合で確かめる）。
- ✅ M: 複数の内容ストリームとフォームの切り抜きの除去がテストで縛られていなかった → 切り抜き・字・切り抜きの終わりが別々の内容ストリームにある頁のテスト、フォームは上の run のテスト。
- ✅ L（同ラウンドで対応）: `workbook_shapes` のテストを、別の関係が先にある `_rels/.rels`・絶対パスの drawing・パッケージの外を指す外部の関係・先に来る vmlDrawing で縛った、出力の OSError と Excel がない時も `checks_complete: false`、`without_clipping` の辞書（`<</ActualText (a>b W n)>>`）のテスト、`no_cell` の片を頁の最大のずれから外す、`_compare` の変数名の取り違えを直した、ClipLoss の作成に失敗した時に開いた PDF を閉じる。
- 持ち越し（LOW）: ライブラリの段の OSError は入力の欠け（画像ファイルがない等）も終了コード 6（出力の失敗）として報告する（型と文面は JSON に残る）。
- 時間: 片持ち梁 68 秒、代表例 21〜28 秒。
- 現在の写像（xlsx-map 担当の修正の途中の版）での実行: 代表例 standard は standard 364 片中 はみ出し 7（段落の行の末尾の字が切れる 3、分子の上付き「3」・内側の分母「2」の dy 8.3・8.5 pt、A3 の右フッター 2 頁の dx 19.1 pt）、`fr021_vertical_merge` 18 片すべて合格。long は standard 414 片中 15。片持ち梁は 5418 片中 80（回転表 p30〜37 の文字が直交する向きに 8.4〜8.6 pt、許容 5.4 pt が 79、p15 の段落の末尾が切れる 1）。見出しの頭の切れと回転表の字の頭の切れは、この版の写像ではなくなっていた（描き直しの比較でも 0）。

**レビュー反映 (2026-10-20, ラウンド 5)**

レビュアー1体（silent-failure＋python。実出力の頁全体の描き直し 8 px/pt との照合、Excel 実機、陰性対照）。CRITICAL 0 / HIGH 0 / MEDIUM 3 / LOW 7。実出力の clipped は描き直しの比較と完全に一致（standard 3・long 10・cantilever 1 字、clipped_out 0、字の箱の外の差 0）、CLIP_ZOOM 4〜16・CLIP_LEVEL 0〜128 で実出力の結果は変わらなかった。Excel 実機で 30 pt のセルの D が clipped、E〜P が clipped_out、隣の x は誤検出なし。Red `compare-r5-red-b` 3 failed → `compare-r5-green` 単体 156 passed、`compare-r5-excel` 統合（下）。

- ✅ M（3件、どれもラウンド4の修正がテストで縛られていなかった）: 16 px/pt と 64 → 0.1 pt の切れを位相 0・1/16・1/8 pt で見つけるテストを追加。`clipped_out` を positions の不合格に入れたこと → Excel の代わりの関数で段落の末尾を切り抜きの完全に外へ出す run のテストと、空の切り抜きの中に見えない字を足すと（missing・extra は 0 のまま）`clipped_out` だけで positions が不合格になるテスト。後の内容ストリームとフォームの中の切り抜き → 空のストリームを先に置いた頁、切り抜きを持つ頁をフォームとして写した頁、それをさらに写した入れ子の頁で、C が clipped・D が clipped_out になるテスト。
- 陰性対照（この担当が実施、`compare_xlsx_pdf.py` の写しを1か所ずつ壊す）: CLIP_ZOOM 4・CLIP_LEVEL 200・positions から clipped_out を外す・最初の内容ストリームだけ処理する・フォームを処理しない・/BBox を広げない・開けない時の未検査を False にする、の7通りすべてで単体テストが落ちた（壊す前は全件合格）。
- ✅ L（同ラウンドで対応）: `TEXT_FLAGS` の注記の原因（TEXT_CLIP の bit。この bit で切り抜きの外の字が取り出されないことを確かめるテスト）、同じ字が続く時の clipped_out の照合のテスト、ClipLoss の作成失敗で PDF を閉じるテスト、Excel が開けなかった時は調べなかった検査を null・`checks_complete: false` に、docstring に clipped と clipped_out を記載、`_summary` の欠けた欄を黙って 0 にしない、照合の鍵を tuple に、空行、面積のない字の箱は ValueError（切れていないとみなさない）。
- 持ち越し（LOW）: clipped_out の字の箱に丸ごと覆われる字は自分の切れを判定できない（その頁は clipped_out で必ず不合格になるので合否は変わらない）／字の箱の外の差は見ていない（実出力では 0）。
