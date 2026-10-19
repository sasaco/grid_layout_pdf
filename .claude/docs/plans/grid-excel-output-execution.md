## Execution: Grid Excel Output（方眼Excel出力）

計画: [grid-excel-output.md](grid-excel-output.md)。ブランチ `feature/grid-excel-output`（起点 `a8c5228`、計画の記録 `58c296b`）。2026-10-20 ユーザー承認「ok 新しいブランチでGO」。

### 担当とファイルの所有

| グループ | 担当 | 工程 | 主なファイル | 状態 |
|---|---|---|---|---|
| 0 | lead | Step 1 基準 | — | ✅ 完了 |
| 1 | fonts | Step 2（FR-024） | `fonts.py`・`fontfinder.py`・`styles.py`（書体の既定のみ）・同梱書体・全テスト/例/文書の `register` の書き換え・片持ち梁の書体の指定 | ✅ 完了（commit 待ち） |
| 1 | xlsx-core | Step 7（ADR-0001） | `renderers/xlsx/{__init__,_model,_package,_sheet,_styles,_drawing,_units,_xml}.py`・`tests/unit/test_xlsx_{package,model,units,cells,sheet,drawing}.py`・`tests/integration/test_xlsx_excel_core.py`（計画の `test_xlsx_excel.py` は Step 10 で ScenePage からの検査を担う） | レビュー中 |
| 2 | size | Step 3（FR-023） | `styles.py`・`math.py`・文字サイズのテスト・片持ち梁の文字サイズ | ✅ 完了（p30〜35 と p36 の9セルは Step 9 へ保留） |
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
- ✅ Excel 実機（`tests/integration/test_xlsx_excel_core.py`、`xlsxcore-excel-r4`）: 35 passed、約114秒（アクティブなプリンター DocuWorks Printer）。
- ✅ coverage（`COVERAGE_FILE=.coverage.xlsxcore`、単体テストだけ）: `renderers/xlsx` 全体 99%。
- ✅ 印刷の倍率の実測の生データ: `scripts/xlsx_probe/measure_print_pitch.py` で測り、`scripts/xlsx_probe/print_pitch.json` に保存（3,240 件。プリンター DocuWorks Printer、2書体×11〜30 px の全整数×20〜100% の全整数）。DocuWorks PDF は 10〜400% の 29 段・4 幅（11・16・21・30 px）のみ測定（生データはラウンド3で上書きして消失、残っているのはレビュアーが確かめた最大値。オーケストレーターの判断でこのまま受け入れ）。

**モデルの API（Step 8 への引継ぎ。`src/gridlayoutpdf/renderers/xlsx/_model.py`）**

- 単位と座標: 行・列は 0 始まり。色は 0〜1 の RGB 3要素。長さは pt で2種類ある。セルと図形の位置・大きさはモデルの列幅・行高で測る pt（Excel の整数 px のセルへは、セルの中の割合のまま写す）。線の太さ・文字の大きさ・余白・内側の余白・角の半径・破線の長さは絶対の pt。図形の座標はシートの左上（A1 の左上）原点で、y は下向き。
- 全クラスは `frozen=True, slots=True` の dataclass で、生成時に検査して誤りは `ValueError`（自動で直さない。巨大な整数も `OverflowError` でなく `ValueError`）。並びは list か tuple で渡し tuple で保持する。set・dict は出力の順が決まらないので `ValueError`。
- `Workbook(sheets, default_font=Font("游ゴシック", 11))`: シート名の重複は Excel と同じく大文字小文字・全角半角を区別しない比較（NFKC＋casefold）でエラー。`default_font` は Excel の「標準」スタイルで列幅の単位（最大の数字の幅 MDW）を決めるため、実測した書体の標準・黒だけを受ける（`_units._MAX_DIGIT_WIDTH_PX`）。独自の表示形式はブック全体で 206 種まで。
- `Sheet(name, column_widths_pt, row_heights_pt, cells=(), merges=(), borders=(), row_breaks=(), page=PageSetup(), header=None, footer=None, drawings=(), show_gridlines=True)`。列 1〜16,384、行 1〜1,048,576。行高は 409 pt まで、列幅は 255 文字まで。半ピクセル（0.375 pt）未満はエラー。印刷範囲は常にシートの全セル（`_xlnm.Print_Area`）。図形は外接箱がシートの中（端は 1e-6 pt の誤差まで可）でなければエラー。`width_pt`・`height_pt` はモデルの列幅・行高の合計（Excel の実寸ではない）。検査は結合の面積・セル・罫線の数に比例する（結合 3 万で1秒程度）。
- `CellValue(row, col, value, number_format=None, font=None, h_align="left", v_align="center", rotation=0, fill=None)`: `value` は `str`・数（float にする）・`RichText`・`None`（書式だけの空セル）。`font=None` はブックの既定の書体。`rotation` は反時計回りの度で 0・90（下から上へ読む）・270（上から下へ読む）。Excel の textRotation の 90・180 へはライブラリが写す。`h_align`・`v_align` は回しても紙面の向きのまま。`fill` はセルの背景色（指示の `color` をこの名前にした）。結合範囲の左上以外に値があればエラー。文字列の `_xHHHH_` と `\r` は書き出し時に逃がす（`_x005F_`・`_x000D_`）ので元の文字のまま読める。
- `RichText(runs)`、`Run(text, font=None, vert_align=None|"superscript"|"subscript")`。`font=None` はセルの書体。上付き・下付きの run には記号と同じ大きさを渡す（Excel が自動で約2/3に縮める）。
- `Font(name, size, color=(0,0,0), bold=False, italic=False)`。`size` は 1〜409 pt の 0.5 pt 刻み。`name` は 31 文字まで、制御文字・空白だけは不可。
- シート名・書体名・表示形式に `_xHHHH_` の形があるとエラー（SpreadsheetML ではこれらも文字の符号として読まれうる。Excel の扱いは測っていないので、逃がさず拒否した）。
- `number_format`: 255 文字まで。引用符・角括弧の閉じ、`\`・`_`・`*` の後の文字、4区画まで、角括弧の中身（色・`Color1`〜・条件・`$`で始まる通貨と言語・経過時間 `h`/`m`/`s`・`DBNum`/`NatNum`）を検査する。その他の文法の誤りは Excel でしか分からない。
- `CellRange(first_row, first_col, last_row, last_col)`（2セル以上）。結合の重なりはエラー。
- `EdgeBorder(row, col, side, style, color=(0,0,0))`: 1つのセルの1辺。`style` は `BORDER_STYLES` の13種の名前。同じ物理的な辺（上のセルの bottom と下のセルの top など）を2度与えるとエラー。結合範囲の内側の辺はエラー。結合範囲の辺は `range_edges(cell_range, side, style, color)` で辺に沿う各セルの `EdgeBorder` を作る。
- `row_breaks`: 増加する行番号の並びで、その行の上で改ページ（1〜最終行、1,026 か所まで。1,026 は Excel の文書の上限で実測していない）。
- `PageSetup(paper="A4"|"A3", orientation="portrait"|"landscape", margins=Margins(...), scale=100, first_page_number=None, print_gridlines=False)`、`Margins(left, top, right, bottom, header, footer)`（pt。既定は Excel の「標準」）。`scale` は 10〜400、`first_page_number` は 1〜32,767（None は自動）。`paper_size_pt`・`printable_size_pt` を持つ。`paper_for_size(width_pt, height_pt, tolerance_pt=1.0)` がページの大きさから `(paper, orientation)` を返す（A4・A3 以外はエラー。許容差は 0〜10 pt）。
- `HeaderFooter(left=None, center=None, right=None)`、`HeaderSection(parts, font=None)`、`parts` は文字列・`PageNumber()`（`&P`）・`SheetPageCount()`（`&N`。そのシートのページ数で、帳票全体の総数ではない。FR-021 の `{pages}` は数字の文字列で渡す）。文字列の `&` はここで `&&` にする。`font` の大きさは整数 pt、名前に `"`・`,`・`&` は不可、名前 `-`（Excel の既定の書体の意味）も不可。書式文字列は 255 文字まで。`code()` で Excel の書式文字列を返す。
- 図形の線・塗り・文字の欄はキーワードだけで渡す（scene の `Rectangle` の5番目は線の太さだが、ここで位置で渡すと角の半径になるのを防ぐ）。長さ0の線、幅か高さが0の箱、全点が同じ位置の自由形状、2点の閉じた自由形状はエラー。scene の `Point` は `(p.x, p.y)` に直して渡す。
- 図形: `Line(x1, y1, x2, y2, *, stroke_width_pt=0.5, color, dash=(), start_arrow=None, end_arrow=None)`（`Arrowhead(kind, width, length)`、kind は triangle・stealth・diamond・oval・arrow、大きさは sm・med・lg。start は (x1, y1)）、`Polyline(points, *, closed=False, stroke_width_pt, color, fill=None, dash=(), stroke=True)`（塗りは閉じた形だけ）、`Rect(x, y, width, height, *, corner_radius_pt=0, stroke=True, stroke_width_pt, color, fill=None, text=None, dash=())`、`Ellipse(...)`・`Diamond(...)`（corner_radius なし）、`TextBox(x, y, width, height, text)`（枠・塗りなし）、`Picture(x, y, width, height, data, format)`（`format` は "png" か "jpeg" で必須。Pillow で読めない・形式が違う・途中で切れた data はエラー。MPO 拡張の JPEG は JPEG。scene の `RasterImage` は他の形式もあるので Step 8 で PNG にする）、`Group(children)`（入れ子可）。`dash` は scene と同じく pt の on/off の並びで `()` が実線（奇数個は PDF と同じく2回繰り返す）。線の太さは 1 EMU 以上 1,584 pt 以下、破線の長さは線の太さの 0.00001〜21,474 倍。線も塗りも文字もない四角・楕円・菱形はエラー。
- `TextFrame(paragraphs, *, font, h_align="left", v_align="top", rotation=0, insets_pt=(0,0,0,0), wrap=False)`: `paragraphs` は `Run` の並びの並び（空の並びは空行、run に改行・タブなどの制御文字は不可）。`rotation` は反時計回りの 0・90・180・270。寄せ方は文字の読む向きで決まる（90度では「上」が紙面の左）。`Font` の 0.5 pt 刻みは図形の文字にも掛かるので、図形の中の添字も記号と同じ大きさ＋`vert_align` で渡す（添字の添字は1段になる）。
- 書き出し（`_package.py`）: `write_workbook(workbook) -> bytes`、`save_workbook(workbook, path)`（全体を作ってから同じフォルダの一時ファイル経由で `os.replace`。POSIX では umask どおりの権限にする）。
- 単位（`_units.py`）: `excel_column_width_pt(pt)`・`excel_row_height_pt(pt)`（Excel が実際に使う pt）、`column_width_chars(pt, font)`、`pt_to_emu`、`page_heights_pt(row_heights_pt, row_breaks)`、`print_fit(sheet, default_font, *, maximum=100) -> PrintFit(scale, limited_by, column_factor, row_factor)`（全ページが1枚に収まる最大の整数%と、それを決めたのが `"width"`・`"height"`・`"maximum"` のどれか）、`fit_scale_percent(sheet, default_font, *, maximum=100)`（その `scale` だけ。`dataclasses.replace(sheet, page=replace(sheet.page, scale=...))` で使う）。`default_font` は必須で、そのシートを書くブックの `Workbook.default_font` を渡す。印刷を測った 游ゴシック 11 と ＭＳ 明朝 10.5（標準・黒）だけを受ける。20% でも収まらなければ `ValueError`。`maximum` は 20〜100（`MIN_FIT_SCALE`・`MAX_FIT_SCALE`。測った範囲）。測ったセルの大きさは `MEASURED_CELL_PIXELS`（11〜30 px）。図形の配置は `_drawing.SheetGeometry`（セルの境目から 1e-6 pt 以内の座標は次のセルの 0 として書く）。
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
  - 統合テスト（DocuWorks Printer で実行。測っていないプリンターでは xfail）で 18 通りについて、各ページが1枚に収まり（右下近くの印がそのページにある）、5%（20〜54% の段は 10%）大きくするとページが増えることを確認: 各段の下限ぎりぎり（90・55・20%、21 px）、DocuWorks Printer の4幅の測定で列の倍率が最大だった条件ぎりぎり（11 px で 95・55・25%）、DocuWorks PDF で最大だった条件ぎりぎり（11 px で 60・30%）、行の倍率が最大だった条件ぎりぎり（95・57・20%）、幅で決まる場合、高さで決まる場合、最大の 100% に達する場合、ＭＳ 明朝 10.5、A4 の基準グリッドを 100% にする余白。11 px 未満・30 px 超のセル、他のプリンターのドライバーは未確認。
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
