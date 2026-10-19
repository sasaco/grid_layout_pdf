## Execution: Grid Excel Output（方眼Excel出力）

計画: [grid-excel-output.md](grid-excel-output.md)。ブランチ `feature/grid-excel-output`（起点 `a8c5228`、計画の記録 `58c296b`）。2026-10-20 ユーザー承認「ok 新しいブランチでGO」。

### 担当とファイルの所有

| グループ | 担当 | 工程 | 主なファイル | 状態 |
|---|---|---|---|---|
| 0 | lead | Step 1 基準 | — | ✅ 完了 |
| 1 | fonts | Step 2（FR-024） | `fonts.py`・`fontfinder.py`・`styles.py`（書体の既定のみ）・同梱書体・全テスト/例/文書の `register` の書き換え・片持ち梁の書体の指定 | ✅ 完了（commit 待ち） |
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

担当 xlsx-core（サブエージェント）。2026-10-20。新規ファイルだけを作り、既存ファイルは編集していない。

**進捗（RED→GREEN の記録。ログは `.claude/logs/` の同名）**

- ✅ 1 最小のブック・同じバイト列・ZIP の固定（`xlsxcore-red-1` 7 failed → `xlsxcore-green-1` 7 passed）。
- ✅ 2 モデルの検査（シート名・上限・重複）と単位（`xlsxcore-red-2` → `xlsxcore-green-2`）。
- ✅ 3 セル: 文字列・数値・リッチテキスト・表示形式・寄せ方・文字の向き・塗り・結合・罫線13種・結合範囲の辺（`xlsxcore-red-3` 44 failed → `xlsxcore-green-3`）。
- ✅ 4 シート: 列幅・行高・改ページ・用紙・余白・拡大率・先頭ページ番号・ヘッダー/フッター・枠線・印刷範囲（`xlsxcore-red-4` 46 failed → `xlsxcore-green-4`）。
- ✅ 5 図形（DrawingML）: 線・破線・矢じり・自由形状・四角・角丸・楕円・菱形・テキストボックス・文字入り図形・グループ・画像（`xlsxcore-red-5` 66 failed → `xlsxcore-green-5`）。
- ✅ 6 印刷の拡大率のヘルパー（`xlsxcore-red-6` 9 failed → `xlsxcore-green-6`）。
- ✅ 7 表示形式の構造の検査・ヘッダーの書体名の `&`（`xlsxcore-red-7` 8 failed → `xlsxcore-green-7`、xlsx の単体 328 passed）。
- ✅ Excel 実機（`tests/integration/test_xlsx_excel_core.py`、`xlsxcore-excel-3`）: 15 passed、約30秒。
- ✅ coverage（`COVERAGE_FILE=.coverage.xlsxcore`、単体テストだけ）: `renderers/xlsx` 全体 99%。

**モデルの API（Step 8 への引継ぎ。`src/gridlayoutpdf/renderers/xlsx/_model.py`）**

- 単位と座標: 長さはすべて pt。行・列は 0 始まり。色は 0〜1 の RGB 3要素。図形の座標はシートの左上（A1 の左上）原点の pt で、y は下向き。モデルの列幅・行高の pt で測る。全クラスは `frozen=True, slots=True` の dataclass で、生成時に検査して誤りは `ValueError`（自動で直さない）。
- `Workbook(sheets, default_font=Font("游ゴシック", 11))`: シート名の重複は Excel と同じく大文字小文字・全角半角を区別しない比較（NFKC＋casefold）でエラー。`default_font` は Excel の「標準」スタイルで、列幅の単位（最大の数字の幅 MDW）を決めるため、実測した書体だけを受ける（`_units._MAX_DIGIT_WIDTH_PX`）。
- `Sheet(name, column_widths_pt, row_heights_pt, cells=(), merges=(), borders=(), row_breaks=(), page=PageSetup(), header=None, footer=None, drawings=(), show_gridlines=True)`。列 1〜16,384、行 1〜1,048,576。行高は 409 pt まで、列幅は 255 文字まで。半ピクセル（0.375 pt）未満はエラー。印刷範囲は常にシートの全セル（`_xlnm.Print_Area`）。
- `CellValue(row, col, value, number_format=None, font=None, h_align="left", v_align="center", text_rotation=0, fill=None)`: `value` は `str`・数（float にする）・`RichText`・`None`（書式だけの空セル）。`font=None` はブックの既定の書体。`text_rotation` は Excel の textRotation（0、90＝反時計回り、180＝時計回り90度）。`fill` はセルの背景色（指示の `color` をこの名前にした）。結合範囲の左上以外に値があればエラー。
- `RichText(runs)`、`Run(text, font=None, vert_align=None|"superscript"|"subscript")`。`font=None` はセルの書体。
- `Font(name, size, color=(0,0,0), bold=False, italic=False)`。`size` は 1〜409 pt の 0.5 pt 刻み。
- `CellRange(first_row, first_col, last_row, last_col)`（2セル以上）。結合の重なりはエラー。
- `EdgeBorder(row, col, side, style, color=(0,0,0))`: 1つのセルの1辺。`style` は `BORDER_STYLES` の13種の名前。同じ物理的な辺（上のセルの bottom と下のセルの top など）を2度与えるとエラー。結合範囲の内側の辺はエラー。結合範囲の辺は `range_edges(cell_range, side, style, color)` で辺に沿う各セルの `EdgeBorder` を作る（Excel は結合範囲の辺を各セルの罫線として持つ。実機で辺全体が読めることを確認）。
- `row_breaks`: 増加する行番号の並びで、その行の上で改ページ（1〜最終行、1,026 か所まで）。
- `PageSetup(paper="A4"|"A3", orientation="portrait"|"landscape", margins=Margins(...), scale=100, first_page_number=None, print_gridlines=False)`、`Margins(left, top, right, bottom, header, footer)`（pt。既定は Excel の「標準」）。`scale` は 10〜400、`first_page_number` は 1〜32,767（None は自動）。`paper_size_pt`・`printable_size_pt` を持つ。
- `HeaderFooter(left=None, center=None, right=None)`、`HeaderSection(parts, font=None)`、`parts` は文字列・`PageNumber()`（`&P`）・`PageCount()`（`&N`）の並び。文字列の `&` はここで `&&` にする。`font` の大きさは整数 pt、名前に `"`・`,`・`&` は不可。書式文字列は 255 文字まで。`code()` で Excel の書式文字列を返す。
- 図形: `Line(x1, y1, x2, y2, width_pt=0.5, color, dash=None, start_arrow=None, end_arrow=None)`（`Arrowhead(kind, width, length)`、kind は triangle・stealth・diamond・oval・arrow、大きさは sm・med・lg）、`Polyline(points, closed=False, width_pt, color, fill=None, dash=None, stroke=True)`（塗りは閉じた形だけ）、`Rect(x, y, width, height, corner_radius_pt=0, stroke=True, width_pt, color, fill=None, text=None, dash=None)`、`Ellipse(...)`・`Diamond(...)`（corner_radius なし）、`TextBox(x, y, width, height, text)`（枠・塗りなし）、`Picture(x, y, width, height, data, format="png"|"jpeg")`、`Group(children)`（入れ子可）。`dash` は pt の on/off の並び（奇数個は PDF と同じく2回繰り返す）。
- `TextFrame(paragraphs, font, h_align="left", v_align="top", rotation=0, insets_pt=(0,0,0,0), wrap=False)`: `paragraphs` は `Run` の並びの並び（空の並びは空行）。`rotation` は反時計回りの 0・90・180・270。寄せ方は文字の読む向きで決まる（90度では「上」が紙面の左）。
- 書き出し（`_package.py`）: `write_workbook(workbook) -> bytes`、`save_workbook(workbook, path)`（全体を作ってから同じフォルダの一時ファイル経由で `os.replace`）。
- 単位（`_units.py`）: `excel_column_width_pt(pt)`・`excel_row_height_pt(pt)`（Excel が実際に使う pt）、`column_width_chars(pt, font)`、`pt_to_emu`、`page_heights_pt(row_heights_pt, row_breaks)`、`fit_scale_percent(column_widths_pt, row_heights_pt, row_breaks, page, *, maximum=100)`（全ページが1枚に収まる最大の整数%。10% でも収まらなければ `ValueError`）。図形の配置は `_drawing.SheetGeometry`。
- `renderers/xlsx/__init__.py` は説明文だけ（公開・再公開は Step 8）。

**Excel 16.0（このPC、96 DPI、既定のプリンター DocuWorks PDF）での実測**

- 修復の検出: `DisplayAlerts=False` で `Workbooks.Open` すると、修復が必要なブック（存在しない書式番号 `s="99"`、閉じていない XML、不正な表示形式 `0.0"`・`[Red`）は例外になり開かない。修復して開くモード（`CorruptLoad=1`）は COM から呼ぶと正常なブックでも失敗したので使わない。シートに未知の要素（`<foo/>`）を入れたブックは黙って開いたため、開けることに加えて、読み戻した中身（セル・書式・結合・罫線・ページ設定・図形の数と種類と位置）をモデルと比べる2段で確かめる。`%TEMP%` に修復ログ（`error*.xml`）は作られなかった。
- 最大の数字の幅（MDW、px）: 游ゴシック 11 = 8、Yu Gothic 11 = 8、游ゴシック 10.5 = 8、游ゴシック 10 = 7、游明朝 11 = 8、ＭＳ 明朝 11 = 8、ＭＳ 明朝 10.5 = 7、ＭＳ ゴシック 11 = 8、ＭＳ ゴシック 10.5 = 7、ＭＳ Ｐゴシック 11 = 8、Calibri 11 = 7、Arial 10 = 7（幅 1・2・3・10・20 文字の列の `Range.Width`）。列の幅は ECMA の式 `Truncate(((256*w + Truncate(128/MDW))/256)*MDW)` px どおり。既定の書体は Excel の日本語版の既定と同じ游ゴシック 11 にした。96 DPI 以外の画面は未確認。
- 列幅: 指定の pt を最も近い整数 px に丸めた幅で表示（16.08 pt → 21 px = 15.75 pt、8.04 → 8.25、100 → 99.75）。行高: Excel はファイルの pt を整数 px に切り捨てて表示する（15.48 → 15.0、20.64 → 20.25、0.5 → 0 で行が消える）。このためライブラリは最も近い整数 px（半分は切り上げ）の pt を書き、表示と一致させる（15.48 → 15.75）。0.375 pt 未満はエラー。
- 図形の位置: 列幅・行高のピクセル丸めでずれないよう、座標をそのセルの中の割合のまま Excel の実際のセルへ写す（twoCellAnchor の from/to と EMU のオフセット、`xfrm` も同じ写し方、グループは子の座標系を親と同じにする）。Excel の `Shape.Left/Top/Width/Height` が写した値と 0.05 pt 以内で一致することを確認。
- 罫線の種類 → Excel の (LineStyle, Weight): hair (1,1)、thin (1,2)、medium (1,-4138)、thick (1,4)、double (-4119,4)、dotted (-4118,2)、dashed (-4115,2)、dashDot (4,2)、dashDotDot (5,2)、mediumDashed (-4115,-4138)、mediumDashDot (4,-4138)、mediumDashDotDot (5,-4138)、slantDashDot (13,-4138)。
- 文字の向き: textRotation 90 は `Range.Orientation` = xlUpward(-4171)、PDF で下から上へ読む（反時計回り）。180 は xlDownward(-4170)、上から下へ読む。図形の `TextFrame` の 90 は `vert="vert270"`（Orientation 2 = Upward）、270 は `vert="vert"`（3 = Downward）、180 は `bodyPr rot="10800000"`（PDF で逆さ）。
- 上付き・下付き: Excel はセルのリッチテキストでも図形の文字でも、上付き・下付きの run を自動で約2/3に縮めて描く（10.5 pt → PDF で 7.08 pt）。7 pt を与えると 4.68 pt になる。**Step 8 は添字の run に記号と同じ大きさ（`Script` が縮める前の大きさ）を渡すこと**。
- ヘッダー・フッター: `&P-1`・`&P+1` は Excel がページ番号の足し引きとして印刷する（5 → 4、6）。`&P1` は「51」。このため `PageNumber()`/`PageCount()` の直後の文字が `+`/`-` で始まる時は、書体の指定（`&"-,Regular"` または区画の書体）を挟んで区切る（PDF で「4+1」を確認）。`&10.5` は 10 pt と文字「.5」になる（ヘッダーの大きさは整数だけ）。書体の太さは英語名 `Regular`・`Bold`・`Italic`・`Bold Italic` が日本語版でも効く（`&"Arial,Bold Italic"` が Arial-BoldItalicMT）。`&KRRGGBB` で色。
- シート名: 31 文字は UTF-16 の単位で数える（絵文字 15 個＋1 文字は可、16 個は不可）。重複として拒否: abc/ABC、A/Ａ、ア/ｱ、Ä/ä、ß/SS、①/1、ﬁ/fi、ｶﾞ/ガ、σ/ς、é/e＋結合文字。別名として可: ア/あ、İ/i、㌔/キロ、Ⅰ/I（NFKC は後ろ2つも重複とみなすので、ライブラリは厳しめにエラーにする）。`History` は COM では付けられた。
- 先頭ページ番号: COM で 0・負数・65535 も受けるが 32768 は「自動」(-4105) になった。範囲を 1〜32,767 にした。拡大率は 10〜400（9・401 は COM がエラー）。
- 印刷の寸法: Excel の PDF 書出し（`ExportAsFixedFormat`。既定のプリンターを Microsoft Print to PDF にしても同じ値）では、列は画面の幅より広く（1.0076〜1.0343 倍、拡大率 55% 未満では最大 1.0673 倍）、行は狭く（0.87〜0.99 倍）印刷される。例: 21 px の列は 100% で 16.08 pt、21 px の行は 15.48 pt（1/600 inch の格子）。`fit_scale_percent` は列に 1.045 倍（55% 未満なら 1.07 倍）、行に 1.0 倍を掛けて計算する。A4 縦・35 列（21 px）・1ページ50行の例では Excel で収まる最大は 93%、ヘルパーは 90%。実際のプリンターのドライバーでの印刷は未確認。
- `PageSetup.Pages.Count` と `HPageBreaks` の自動改ページは、同じ Excel で拡大率を変えても更新されず当てにならなかった。ページ数は PDF に書き出して数える（統合テストはこの方法で、`fit_scale_percent` の値で各ページが1枚に収まることを4通りで確認）。
- グループの高さが0（水平線だけのグループ）、0.01 pt の四角も Excel は開いた。

**設計判断**

- 書き出しは `_xml.py`（エスケープ・数の書式・要素の書き方）を加えた7モジュール。要素の順は CT_Worksheet・CT_Stylesheet・DrawingML の並びに従う。styles（numFmts・fonts・fills・borders・cellXfs）と共有文字列・画像は重複をまとめ、出現順（シート順・行列順・図形順）で番号を付ける。組込みの表示形式（`General`・`0`・`0.00`・`#,##0`・`#,##0.00`・`0%`・`0.00%`・`0.00E+00`・`@`）は組込みの番号、他は 164 から。
- ZIP: 日時 1980-01-01 00:00:00、deflate レベル 6、`create_system=0`、`external_attr=0o600<<16`、部品の順は固定（[Content_Types].xml → _rels → workbook → workbook の rels → styles → sharedStrings → シート → シートの rels → drawing → drawing の rels → media）。同じ環境（同じ zlib）で同じバイト列。別の zlib の版でのバイト一致は未確認。
- docProps と theme は書かない（Excel は開いた）。
- 表示形式の文法は Excel だけが正しく判定できるが、閉じていない引用符・角括弧、末尾の `\`・`_`・`*`、5区画以上は、Excel が開けなくなるのでモデルでエラーにする。
- 図形の線は端を平ら（`cap="flat"`）・角を丸く（`a:round`）して、PDF の描き方（butt・round join）に合わせた。テキストの余白の既定は0、折り返しなし（`wrap="none"`）。
- 一辺だけ・結合範囲の辺の一部だけに罫線を書いた場合の Excel の見え方は未確認（結合範囲の辺全体に書いた場合は確認済み）。

**Tips**

- Excel の COM は PowerShell の `New-Object -ComObject Excel.Application` で動かし、入出力は UTF-8 の JSON ファイルで渡す（標準出力の文字コードに頼らない）。`finally` で全ブックを閉じて `Quit`・`ReleaseComObject`。統合テストは実行前後の EXCEL.EXE の PID を比べて残っていないことを確かめる。
- `PYTHONUTF8=1` のもとで `subprocess.run(..., capture_output=True, text=True)` で `tasklist` を読むと `stdout` が `None` になった（Excel が動いていない時の日本語の案内文が cp932 で、UTF-8 として読めないためと推定。原因は未確認）。bytes で受けて decode する。
- pytest の parametrize に 32,768 文字の値を渡すと、テスト ID が環境変数 `PYTEST_CURRENT_TEST` の上限を越えて落ちる。`ids=` を付ける。
- Excel の PDF 書出しで罫線（hair・thin）は2本の細い四角として出ることがある。線の位置を測る時は 1.5 pt 以内の辺をまとめる。
