## Implementation Plan: Grid Excel Output（方眼Excel出力）

状態: 2026-10-20 ユーザーが「ok 新しいブランチでGO」で計画全体の実装開始を承認（Gate 1）。ブランチ `feature/grid-excel-output` で TDD と parallel-agent-dev により実装する。IPAexゴシックの公式配布物の取得もこの承認に含む。進捗・担当・試験の記録は `grid-excel-output-execution.md`。要件は `.claude/docs/DESIGN.md` の FR-021〜027（2026-10-19 grill-with-docs と 2026-10-20 の追加で確定）、用語は `CONTEXT.md` の「方眼Excel」「項の列」、書き出し方式は `docs/adr/0001-xlsx-written-with-stdlib.md`。

### Purpose

ライブラリが組んだ `ScenePage` 列を、PDF の代わりに方眼Excel（`.xlsx`）として出力できるようにする。ページのグリッドの1マスを1セルとし、値と文言をセル上で直せる計算書にする。あわせて、PDF と方眼Excel で同じ原稿が同じ体裁になるよう、文字サイズ（0.5 pt 刻み）・罫線の種類・書体名による指定をライブラリ全体の決まりに改め、方眼Excel で文字片が重ならない書き方（グリッドに合わせた項の列）を用意する。

### Scope

#### 対象と確定条件

- **確認済み（FR-021）**: 出力は PDF の代わりに選ぶ形式。目的はセル上で直せること（Excel の数式による再計算はしない）。範囲はライブラリのみで、WebPier への組込み・差し込みページ（Capacita・Aggre-SE）の扱いは対象外。WebPier はこの仕様に合わせて別リポジトリで作り直す。
- **確認済み（FR-021）**: 1マス＝1セル（セルの大きさはページの `GridSpec`）。1帳票1シートで、用紙・向き・グリッドが変わる所で次のシート（`名前`、`名前_2`、`名前_3`…、元の用紙に戻っても新しいシート）。シート名が Excel の規則（31文字、`[]:*?/\` 不可、重複不可）に反すればエラー。ページの境目に改ページ。Excel の上限（16,384列・1,048,576行）超過はエラー。
- **確認済み（FR-021）**: 文字片ごとに1セル（またがる範囲は結合）。重なったら右（回転表では読む方向）へずらし、ずらした記録を返す。`strict=True` なら1件でもエラー。ずらした結果がグリッドの右端を越えたら常にエラー。添字・指数は記号と同じセルのリッチテキスト（上付き・下付き）。
- **確認済み（FR-021）**: 文字片が数値の書き方に丸ごと一致する時だけ数値型＋表示形式で PDF と同じ表示（例: `−2.000` → 値 −2、`0.000;"−"0.000`）。先頭0の番号・`−0.000`・図の中の文字は文字列。
- **確認済み（FR-021）**: 分数は分子・分母を上下のセル、分数線は分子と分母の行の境目に図形。同じ式の左辺・等号・結果・単位はそれぞれ別セルで、式の行の範囲を縦結合して上下中央。
- **確認済み（FR-021, FR-022, FR-026）**: セルの罫線になるのは `Table`・`Rule`・`SideRule` が描いた線だけ。利用者が書いた `Line`（図の中を含む）・分数線・図は、セルの境目に載っていても図形。罫線の太さは Excel の罫線の種類から選び、pt の直接指定は廃止。
- **確認済み（FR-026）**: 表と区切り線の線はライブラリの部品だけが描き、利用者に `Line` を描かせない。`Table` は辺ごと（行の境目×列、行×列の境目）に罫線の種類か線なしを持ち、表全体の既定・外枠・境目1本ぶんをまとめて決められる（参考: `structural-mcp/Batch/WinPDFPrint/Printing/Table.cs` の `HolLW`・`VtcLW`・`SetHolLW`・`SetVtcLW`）。結合セルの内側の辺は引かない。既定はすべて細。本文を横切る区切り線は `Rule` 部品（仮名）。今の `horizontal_rules`・`vertical_rules`・`border_width` は廃止。PDF での太さは極細 0.25・細 0.5・中 1.0・太 1.5 pt、二重は 0.5 pt の2本で間隔 1.0 pt、表の既定は細。
- **確認済み（FR-021）**: `QuarterTurn` は `local_grid` がページのグリッドの縦横入替の時にセル（文字の向き90度、`turns=+1` は反時計回り）で、それ以外は図形で描いて記録し、`strict=True` でエラー。
- **確認済み（FR-021）**: 図は文字も含め図形（`TextBox`・`TextDiamond` は文字入り図形、`Label` は枠なしテキストボックス、`Image` は画像、図ごとにグループ化）。
- **確認済み（FR-021）**: `PageDecoration` は Excel のヘッダー・フッター（`align` の左・中央・右の欄）。`{page}` → `&P` と各シートの先頭ページ番号、`{pages}` → 帳票全体の総数を数字で書く。書式付きの指定（`{page:03}` 等）はエラー。
- **確認済み（FR-023）**: 文字サイズはライブラリ全体で 0.5 pt 刻み。`Script` の `scale` から決まる大きさは対象外。
- **確認済み（FR-024）**: 利用者は書体名で指定し、ライブラリが同梱の書体（IPAex明朝・IPAexゴシック）、次に Windows の書体フォルダ（`%WINDIR%\Fonts`・`%LOCALAPPDATA%\Microsoft\Windows\Fonts`）から探す。macOS・Linux では同梱以外の書体名はエラー。`FontRegistry.register` は廃止。方眼Excel には同じ書体名を書く。
- **確認済み（FR-027）**: 片持ち梁 p1〜37 を新しい決まりで37ページ全体作り直し、方眼Excel を `strict=True`（ずらし・図形への切替え 0 件）で出す。FR-014（固定37頁・あふれたらエラー・頁番号なし）と FR-013（p30〜37 の回転表を90度回す。縦横を入れ替えたページのグリッドで組み、セルで出す）は保つ。内容・文字の並び・書体は保ち、大きさは 0.5 pt 刻み。FR-015 の表の行の高さ・等号の紙面上の位置・字下げは、新しい決まりとぶつかる所でグリッドのマスの整数倍を優先し、原本と一致しなくてよい。罫線は最小 0.25 pt（極細）を厳守し、原本の 0.12 pt との差が従来の許容差（±0.08 pt）を超えても新しい決まりを優先する。原本との比較は内容・順番・頁・書体の検査を残し、位置・行の高さ・線の太さ・大きさの検査は「新しい決まりどおりか」の検査に置き換える。
- **確認済み（FR-025）**: `EquationGroup` に、項の列をグリッドの列単位で割り当てる指定（仮名 `term_columns="grid"`）を加える。指定した時だけ PDF の項の間隔も変わる。
- **確認済み（検証）**: 自動テストと、Excel がある環境だけの COM 検査の2段。合格対象は `examples/representative_report.py`（`term_columns="grid"` 版）と片持ち梁 p1〜37 で、どちらも `strict=True`。
- **計画提案（質問せずに既定にする事項）**: セルの横の配置は元の部品の寄せ方（項の列の左・中央・右、表の数値列の右寄せ等）。画面のセルの枠線は表示し、印刷では出さない。印刷の拡大率は全ページが改ページ位置どおりに収まる値にする。文字・線・塗りの色はセルと図形に写す。両端揃えの字間（`tracking`）はセルでは表せないため捨てる（自然な幅は揃えた幅以下なので、はみ出しは増えない）。
- **計画提案**: 公開 API は `render_xlsx(reports, path, fonts=None, *, strict=False) -> XlsxResult`。`reports` は `(シート名, ScenePage 列)` の並び。`XlsxResult` はシートごとの名前・ページ範囲と、ずらし・図形への切替えの記録を持つ。`Document.render_xlsx(path, sheet_name, ...)` も用意する。
- **対象外**: WebPier の変更、Excel の数式、外部 PDF ページの取込み、`.xlsx` の読込み、Excel 以外の表計算ソフトでの見え方の保証。

#### New files

- `src/gridlayoutpdf/fontfinder.py`: 標準ライブラリで TTF/TTC の name テーブルを読み、英語名・日本語名（nameID 1・4・16、言語 0x409/0x411）から書体ファイルと TTC の書体番号を引く。探す順は同梱 → `%WINDIR%\Fonts` → `%LOCALAPPDATA%\Microsoft\Windows\Fonts`。
- `src/gridlayoutpdf/fonts/`（パッケージデータ）: `ipaexm.ttf`・`ipaexg.ttf`（004.01）と IPA フォントライセンス、`manifest.json`（sha256・出典）。
- `src/gridlayoutpdf/borders.py`: `BorderStyle`（hair・thin・medium・thick・double・dotted・dashed・dashDot・dashDotDot・mediumDashed・mediumDashDot・mediumDashDotDot・slantDashDot）と、PDF での線幅・破線・二重線の描き方。表の辺ごとの罫線の指定（`TableBorders` 仮名: 既定・外枠・行の境目・列の境目・辺1つ）。
- `Rule` 部品（`blocks.py` に追加）: 本文を横切る区切り線を、行の境目に罫線の種類で引く。
- `tests/unit/test_table_borders.py`, `test_rule.py`。
- `src/gridlayoutpdf/renderers/xlsx/`: `__init__.py`（`render_xlsx`）、`_model.py`（シートのモデル: セル・結合・罫線・図形・ページ設定）、`_map.py`（タグ付き `ScenePage` → シートのモデル。FR-021 の規則すべて）、`_numbers.py`（数値の見分けと表示形式）、`_package.py`（ZIP・content types・rels、日時と順番の固定）、`_sheet.py`、`_styles.py`、`_drawing.py`（DrawingML: 線・矢じり・自由形状・四角・角丸・菱形・楕円・テキスト・グループ・画像）、`_units.py`（pt ↔ EMU・列幅の文字単位・ピクセル丸め）。
- `tests/unit/test_fontfinder.py`, `test_borders.py`, `test_scene_tags.py`, `test_equation_grid_terms.py`, `test_xlsx_map.py`, `test_xlsx_numbers.py`, `test_xlsx_package.py`, `test_xlsx_drawing.py`。
- `tests/integration/test_xlsx_readback.py`（openpyxl で読み戻し）、`test_xlsx_excel.py`（Excel COM。Excel がなければ skip と理由を表示）。
- `scripts/compare_xlsx_pdf.py`: Excel で開いて PDF に書き出し、ライブラリの PDF とページ数・文字片の位置を比べ、並べた画像を作る（COM 検査と目視用）。
- `.claude/docs/plans/grid-excel-output-execution.md`（実装開始時）: 担当・ゲート・実行した試験・未解決の指摘。

#### Modified files

- `src/gridlayoutpdf/fonts.py`: `register` を廃止し、書体名で引く resolver にする。`resolve`・`measure`・`normalize_text` と、`SourceTableInkFonts` のような継承による差し替えは残す。
- `src/gridlayoutpdf/styles.py`: `TextStyle.font` の既定を `"IPAex明朝"` にする（書体の解決は測るときまで遅らせ、import 時にファイルを探さない）。`size` を 0.5 pt 刻みに検査し、`Script` 由来の大きさだけ内部の生成経路で検査を外す。
- `src/gridlayoutpdf/math.py`: `Script` の大きさの生成を検査外の経路へ移す。`Fraction`・`Script`・`Root`・`Delimited` にタグを付ける。
- `src/gridlayoutpdf/scene.py`: 全描画命令に、比較の対象にならない任意の `tag`（`field(default=None, compare=False)`）を足す。`Line`・`Rectangle` に `BorderStyle` を持たせる。
- `src/gridlayoutpdf/tables.py`, `containers.py`（`SideRule`）: `Table` を辺ごとの罫線の種類で描く形に作り直す（`horizontal_rules`・`vertical_rules`・`border_width` は廃止）。`SideRule` の太さも `BorderStyle` にする。表が分かれる継ぎ目は1本として描き、ページの先頭に来た断片だけが上の罫線を描く。二重線・破線の余白の検査。セルの `align`・`valign` と辺ごとの罫線を記録する。
- `src/gridlayoutpdf/equations.py`: `term_columns="grid"` と、式の各部分（ラベル・左辺・等号・項 k・結果・単位）のタグ。
- `src/gridlayoutpdf/blocks.py`, `text.py`, `cell_content.py`, `figures.py`, `rotation.py`, `document.py`, `diagnostics.py`: 寄せ方・図の部品・回転・ヘッダー/フッターの元の書式（`{page}` の雛形と `align`）のタグとページのメタデータ（配置ごとの描画命令の範囲）。`layout_trace` はタグを付いた時だけ出す。
- `src/gridlayoutpdf/renderers/reportlab.py`: `fonts` を省略可能にし、`BorderStyle` の線（破線・二重線）を描く。
- `src/gridlayoutpdf/__init__.py`, `docs/api.md`, `docs/architecture.md`, `docs/validation.md`, `README.md`, `examples/README.md`, `examples/*.py`（`--font` を書体名の指定に、代表例に `.xlsx` の出力を追加）。
- `pyproject.toml`（version 0.2.0、書体をパッケージデータに含める、開発用依存に openpyxl）、`uv.lock`。
- `tests/**`: `register` の呼出し（約47か所）、線の太さの pt 指定（約80行）、0.5 pt 刻みでない文字サイズの直接指定を新しい書き方へ直す。
- `tests/fixtures/cantilever_p01_37/`: `font-profile.json` の書体を名前の指定（MS 明朝・MS ゴシック）へ、文字サイズを 9.9/9.8→10.0、9.058→9.0、8.056→8.0、独自の添字 6.6/6.7 → 6.5（または 7.0）へ、表の線を辺ごとの `BorderStyle` へ（`builder.py:265-266` の継ぎ目の半分の太さは廃止）、`Figure`＋`Line` の区切り線（`builder.py:178`、10本）を `Rule` へ置き換える。FR-027 により37ページ全体を新しい決まりで作り直す（回転表の 0.01 pt の `local_grid` を縦横入替のページのグリッドへ、行の高さ・列の幅・字下げ・等号の位置をグリッドのマスの整数倍へ、式を `term_columns="grid"` へ）。`verify.py`・`verify_appearance.py` は、内容・順番・頁・書体の原本との検査を残し、位置・行の高さ・線の太さ・大きさの検査を新しい決まりどおりかの検査に置き換える。
- `tests/visual/`: 片持ち梁 37 枚と代表例 5 枚の PNG 正解を作り直し、承認記録を更新する（後述のゲート）。

#### Dependencies and protected boundaries

- `.claude/docs/research/A4.pdf` と `tests/output/*.pdf` は変更しない。片持ち梁の原本との比較は原本を正とし、生成物どうしの一致だけで受け入れない（FR-015）。
- 製品の依存は ReportLab と Pillow のまま。openpyxl は開発用の依存だけに加える（ADR-0001）。
- IPAexゴシック（004.01）はリポジトリにないため、公式の配布物（moji.or.jp の `ipaexg00401.zip`）を取得し、sha256 を manifest に固定する。ネットワークでの取得は実装開始時にユーザーの許可を得る。
- 片持ち梁の再現は MS 明朝・MS ゴシックを OS から名前で引く。Microsoft の書体は同梱しない。
- 片持ち梁の固定37ページ（FR-014）は変えない。0.5 pt 刻み・罫線の種類への置換えであふれる場合は、黙って直さず停止してユーザーに報告する。
- 既存の未コミットの変更（`CONTEXT.md`、`DESIGN.md`、`docs/adr/`）を保つ。

#### 調査根拠

- WebPier の実測（2026-10-19、0600 上部工反力 22 ページ・文字片 4641）: WebPier の `report_profile()` は 0.12 pt の位置決め用グリッドで A4.pdf のグリッドではない。A4.pdf のマスに置くと、前の文字片と同じセル 17%・切れる 10%、2行が1つの行に入る 34 行。
- 代表例の実測（A4.pdf のグリッド 16.08 × 15.48 pt、5 ページ・文字片 389）: 同じセル 4%・切れる 2%。主因は `TermStop` の項の列が pt で詰めて並ぶこと（`equations.py:265`）。等号・結果・単位の位置は整数の列（`EquationAnchors`）。
- 分数の実測: `I = (4.50 × 2.70³)/12` は左辺・分子・結果が行5、分母が行6、分数線は 5.55 行目。入れ子の分数は3行。
- 描画命令の調査: `ScenePage` には描画命令と部品の対応がなく、分数線は表の罫線と同じ `Line`、添字は大きさと位置でしか見分けられない。全描画命令は `replace()` で受け渡されるので、`compare=False` の任意の欄は既存の等価比較（19ファイル59か所）を壊さずに末端から `ScenePage` まで届く。`layout_trace` の保存済み正解はない。
- 影響の調査: `FontRegistry()` はテスト44・例7・文書5か所、`register` はテスト47・例7・文書7か所。片持ち梁の表の線は `source-layout.json` の 0.12 pt（337本）と 0.96 pt（105本）、区切り線は図の `Line` 0.72 pt。0.5 pt 刻みでない文字サイズは片持ち梁に 9.9（1,411、すべて p30〜37 の回転表）・9.8（9）・9.058（8）・8.056（4）。回転表の `local_grid` は 0.01 pt（`appearance.py:15`）。片持ち梁の PNG 正解の manifest は `src` の全ファイルの hash を持つため、`src` を変えれば必ず作り直しになる。
- 書体名の読取り: 標準ライブラリで MS 明朝（`msmincho.ttc` 0 番 `MS Mincho`／`ＭＳ 明朝`）・MS ゴシック・IPAex明朝の英語名と日本語名を読めることを確認した。ReportLab は英語名しか持たない。
- 検証の環境: このPCには Excel 16.0 があり COM で操作できる。LibreOffice はない。

### Implementation Steps

TDD で進める。各工程は、失敗するテストを先に書いて `--expect fail` で失敗を確かめ（Red）、実装して `--expect pass`（Green）にしてから整理する。工程の担当とファイルの所有は parallel-agent-dev の方式で分ける。

#### Step 1: 基準を固定する

- [ ] git の状態・未コミットの変更・依存の版・書体の hash を execution 文書に記録する。
- [ ] 全テストを実行し、成功・失敗とカバレッジを記録する。PNG 正解の現状の一致を確かめる。

#### Step 2: 書体を名前で引く（FR-024）

- [x] ✅ Red: 英語名・日本語名・TTC の書体番号・同梱の優先・見つからない時の `FontError`・import 時にファイルを探さないこと。
- [x] ✅ `fontfinder.py` と同梱の書体（IPAexゴシックの取得と hash の固定を含む）、`FontRegistry` の resolver 化、`fonts` 引数の省略、`TextStyle` の既定の書体名。同梱先は `fonts.py` との名前の衝突を避けて `src/gridlayoutpdf/font_data/`（New files の `fonts/` から変更）。
- [x] ✅ テスト・例・文書の `register` を書体名の指定へ直す。片持ち梁は MS 明朝・MS ゴシックを名前で引く（`render.py --font` の差し替えは廃止）。
- [x] ✅ `uv build` の配布物に書体とライセンスが入ることを確かめる（`docs/validation.md` の配布物の記述も直す）。
- [x] ✅ 代表例の PNG 正解が変わらないことを確かめる（同じ書体ファイルに解決するため）。片持ち梁も hash の検査を外した確認で37ページ画素一致（正解のテスト自体は `source_inputs` の hash 不一致で失敗し、最終工程で作り直す）。

#### Step 3: 文字サイズを 0.5 pt 刻みにする（FR-023）

- [ ] Red: `TextStyle(size=9.9)` がエラー、`Script` 由来の 7.8 pt 等は通る、`replace()` による作り直しでも同じ規則。
- [ ] `styles.py`・`math.py` の検査と、`Script` の大きさの内部の生成経路。
- [ ] 片持ち梁の文字サイズを丸めた値へ直し、全37ページを生成して、固定ページからのあふれ（FR-014）がないかを早めに確かめる（本格的な作り直しは Step 9）。あふれたら停止して報告する。

#### Step 4: 罫線の種類と表の作り直し（FR-022, FR-026）

- [ ] Red: `BorderStyle` ごとの PDF の線幅・破線・二重線。`Table` の辺ごとの罫線（既定・外枠・行の境目・列の境目・辺1つの指定、後から決めたものが優先、結合セルの内側は引かない、一部の列だけの横線）。`Rule` が行の境目に引かれること。表・`SideRule` が pt の太さを受け付けないこと。表の継ぎ目が1本になり、ページの先頭の断片だけが上の罫線を描くこと。二重線・破線の余白の検査。
- [ ] `borders.py`、`Rule`、`tables.py`・`containers.py`・`scene.py`・`renderers/reportlab.py`。
- [ ] テストの太さの指定を直す。片持ち梁の表の線（0.12→極細、0.96→中）と区切り線の `Rule` への置換えは Step 9 で行う。

#### Step 5: 描画命令に意味のタグを付ける

- [ ] Red: 分数（分子・分母・分数線）、添字（記号・上付き・下付き）、根号・括弧、式（ラベル・左辺・等号・項 k・結果の等号・結果・単位、式の番号と行）、表（セルの id・寄せ方・罫線の辺と種類）、`CellLines`、段落の寄せ方、図（図の id・部品の種類）、`SideRule`、ヘッダー・フッター（雛形と `align`）、`QuarterTurn`（回転と `local_grid`）がタグとページのメタデータから引けること。
- [ ] `scene.Tag` と各部品の付与、配置ごとの描画命令の範囲。`layout_trace` は付いた時だけ出す。
- [ ] 既存のテストと PDF の出力（Step 2〜4 の変更を除く）が変わらないことを確かめる。

#### Step 6: グリッドに合わせた項の列（FR-025）

- [ ] Red: `term_columns="grid"` で各項が列の境目から始まり、列の幅が「最も広い項＋Excel のセルの余白」が入る最小の列数になること、既定の挙動が変わらないこと、収まらない時の折り返しの規則が今と同じこと。
- [ ] `equations.py` の実装と `docs/api.md` の「方眼Excel で重ならない書き方」の指針。
- [ ] 代表例の式を `term_columns="grid"` で書いた版を用意し、方眼Excel でずらしが0件になることを確かめる（Step 8 で使う）。

#### Step 7: `.xlsx` の書き出し部分（ADR-0001）

Step 2〜6 と並行して進められる（シートのモデルだけを入力にする）。

- [ ] Red: 最小のブックが openpyxl で読めること、同じモデルから同じバイト列、セル・数値の表示形式・リッチテキスト・文字の向き・上下中央・結合・罫線の種類・列幅・行高・改ページ・用紙・余白・ヘッダー・フッター・先頭ページ番号・印刷の拡大率・画像、図形（線・矢じり・自由形状・四角・角丸・菱形・楕円・テキスト・グループ）の XML。
- [ ] `_model.py`・`_package.py`・`_sheet.py`・`_styles.py`・`_drawing.py`・`_units.py`。
- [ ] Excel COM で、修復なしで開けることを早めに確かめる（図形の XML の誤りを先に見つけるため）。列幅・行高の実際の pt を Excel から読み、ピクセル丸めの補正と印刷の拡大率の計算を合わせる。

#### Step 8: `ScenePage` から方眼Excel への対応付け（FR-021）

- [ ] Red: 文字片のセルと結合、ずらしと記録、`strict`、右端を越えた時のエラー、添字・指数のリッチテキスト、数値の見分けと表示形式、分数（分子・分母のセル、分数線を行の境目に、左辺・等号・結果・単位の縦結合）、罫線と図形の振り分け（`Table`・`Rule`・`SideRule` のタグの線だけが罫線、利用者の `Line` は境目に載っていても図形）、回転表（縦横入替のグリッドならセル、それ以外は図形と記録）、図（図形・グループ・画像）、ヘッダー・フッター（`&P`・先頭ページ番号・総数）、シートの分け方と名前、Excel の上限、セルの横の配置、色。
- [ ] `_map.py`・`_numbers.py`・`render_xlsx`・`Document.render_xlsx`・`XlsxResult`。
- [ ] 代表例に `.xlsx` の出力を加える。

#### Step 9: 片持ち梁 p1〜37 を新しい決まりで作り直す（FR-027）

- [ ] Red: 片持ち梁の方眼Excel を `strict=True` で出すと、ずらし・図形への切替えでエラーになること（作り直す前の状態）。新しい決まりどおりかの検査（位置・行の高さがグリッドのマスの整数倍、罫線が `BorderStyle`、文字サイズが 0.5 pt 刻み、回転表の `local_grid` が縦横入替のページのグリッド）。
- [ ] `builder.py`・`appearance.py`・`pages/*.json`・`font-profile.json` を作り直す。回転表は縦横を入れ替えたページのグリッドで組む（0.01 pt の `local_grid` を廃止）。表の行の高さ・列の幅・字下げ・等号の位置はグリッドのマスの整数倍。式は `term_columns="grid"`。表の線は辺ごとの `BorderStyle`（0.12→極細、0.96→中）、区切り線は `Rule`。独自の添字（`SourceScript`）はライブラリの `Script` に寄せる。
- [ ] `verify.py`・`verify_appearance.py` を直す。内容・順番・頁・書体の原本との検査は残し、位置・行の高さ・線の太さ・大きさの検査は新しい決まりどおりかの検査に置き換える。
- [ ] 全37ページが固定ページに収まること（FR-014）を確かめる。あふれたら停止して報告する。
- [ ] 片持ち梁の方眼Excel が `strict=True` で出せることを確かめる。

#### Step 10: 受入と文書

- [ ] 1段目（自動テスト）: openpyxl の読み戻し・図形の XML・エラーの規則・バイト列の決定性を全件合格にする。
- [ ] 2段目（Excel COM）: 代表例（`term_columns="grid"` 版）と片持ち梁 p1〜37 を、どちらも `strict=True` で出し、修復なしで開く・Excel から書き出した PDF とページ数一致・全文字片が同じページで横1マス・縦半マス以内で確かめる。並べた画像を作り、ユーザーに目視を依頼する。
- [ ] PNG 正解（片持ち梁 37 枚・代表例 5 枚）を作り直し、ユーザーの目視の承認を得てから正解と承認記録を更新する。
- [ ] `docs/api.md`・`architecture.md`・`validation.md`・README を更新し、`test_public_api.py` を合格させる。
- [ ] lead が単独で全テストとカバレッジ（90%以上）を実行し、`uv build` の配布物を確かめる。

#### 実行コマンドと依存順

```powershell
$env:PYTHONUTF8='1'
# 環境の同期（openpyxl 追加後）
uv sync --locked --extra dev
# Red（工程ごとに対象と label を変える）
uv run --locked --extra dev python -X utf8 .claude/skills/_shared/run_tests.py --target tests/unit/test_fontfinder.py --expect fail --label fontfinder-red
# Green
uv run --locked --extra dev python -X utf8 .claude/skills/_shared/run_tests.py --target tests/unit/test_fontfinder.py --expect pass --label fontfinder-green
# 並行の coverage は担当ごとに COVERAGE_FILE を分ける。最終の全体は lead が単独で実行する
uv run --locked --extra dev python -X utf8 .claude/skills/_shared/run_tests.py --target tests --expect pass --label final --cov gridlayoutpdf --min-coverage 90
# Excel での確認（Excel のある環境のみ）
uv run --locked --extra dev python -X utf8 scripts/compare_xlsx_pdf.py --example representative --strict
uv build
```

依存順: Step 1 → Step 2・3・4（`styles.py`・`tables.py`・片持ち梁の fixture が重なるため、fixture の変更は1人の担当にまとめる）→ Step 5 → Step 6 → Step 8 → Step 9 → Step 10。Step 7 は Step 1 の後すぐに並行で始め、Step 8 の前に合流する。Step 9 の fixture の作り直しは、Step 4・6 が終われば Step 8 と並行で始められる（`strict=True` の確認だけ Step 8 の後）。

### Risks & Considerations

- **片持ち梁の固定37ページ**: p30〜37 の回転表は 9.9 pt の文字が 1,411 個ある。10.0 pt にすると字の幅が約1%広がり、さらに行の高さ・位置をグリッドのマスの整数倍にすると行が増えることがあるため、あふれるおそれがある（FR-014 のエラー）。Step 3 で早めに、Step 9 で作り直した後に全ページを確かめ、あふれたら停止して報告する。
- **原本との見た目の差**: FR-027 により、罫線（極細 0.25 pt に対し原本 0.12 pt）・文字サイズ（10.0 pt に対し原本 9.8/9.9 pt）・表の行の高さ・等号の位置・字下げが原本と一致しなくなる。原本との比較は内容・順番・頁・書体に限り、見た目の差は Step 10 の並べた画像でユーザーに確かめてもらう。
- **PNG 正解の作り直し**: 片持ち梁の PNG 正解は `src` の全ファイルの hash を持つため、この作業では必ず作り直しになり、ユーザーの目視の承認（通常と grid の 74 枚）が要る。
- **Excel の列幅・行高の丸め**: 列幅は既定の書体の数字の幅（ピクセル）を単位に丸められ、行高もピクセルに丸められる。ずれが印刷範囲を越えると Excel が自動で改ページを足す。Step 7 で Excel から実際の寸法を読み、拡大率を合わせる。
- **図形の XML の誤り**: DrawingML の誤りは Excel が「修復」して黙って図形を消すことがある。COM 検査を Step 7 の早い段階で回す。
- **書体の環境依存**: 方眼Excel を開くパソコンに書体がないと、Excel が別の書体で表示し、セルからのはみ出し方が変わる。同梱の書体は PDF のためのもので、Excel では使えるようにならない。
- **大量の書き換え**: `register` の廃止と線の太さの API の変更で、テスト・例・文書の多くの箇所を直す。意味の変わらない機械的な書き換えと、期待値の変更を別のコミットに分ける。
- **タグの抜け**: タグのない描画命令は、方眼Excel では「意味のわからない線・文字」として図形・ずらしの側に落ちる。対応付けの層で、タグのない描画命令を数えて記録に出す。

### Open Questions

なし。2026-10-20 に次の3点の回答を得た。

1. 片持ち梁の罫線の太さ: 許容差を超えても新しい決まり（最小 0.25 pt）を厳守する（FR-027）。なお grill の Q10 で私が原本の線を 0.5・0.24 pt と伝えたのは誤りで、37ページを描いている値は 0.12・0.96 pt である。
2. 片持ち梁を方眼Excel に出す時の合格条件: 回転表もセルで作り、37ページ全体を新しい決まりで作り直して `strict=True` で合格とする（FR-027）。
3. Windows 以外の OS: 同梱の書体と Windows の書体フォルダだけを探す（DESIGN の決定事項）。

#### Completion gates

- Gate 1: この計画の承認。
- Gate 2: Step 3（文字サイズの丸め）と Step 9（作り直し）の後に、片持ち梁の全37ページがあふれずに生成できること（あふれたら停止して報告）。
- Gate 3: Step 10 の2段の検証の合格と、並べた画像のユーザーの目視。
- Gate 4: PNG 正解の作り直しのユーザーの承認、全テストの合格とカバレッジ 90% 以上、`uv build` の確認。
