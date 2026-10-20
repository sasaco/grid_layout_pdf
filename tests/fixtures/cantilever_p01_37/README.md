# 片持ち梁照査・原本 p01〜37 の再現 fixture

`tests/output/13_片持ち梁照査.pdf` の物理ページ 1〜37 を、表示文字列と意味のある部品から組み立てる。計算・再計算は行わない。原本と同じ 37 枚の A4 縦に固定し、各原本ページを一つの `KeepTogether(Stack(...))` にする。右上のページ番号は全ページで省略する。内容が入らない場合は `LayoutOverflowError: 原本再現できず` で停止し、ページ削除・追加・自動縮小で補わない。

全 37 ページの入力と、16 点の原本図の切り出しを収録する。ページ・部品・図・原本の不整合の台帳は `manifest.json` に置く。入力の転記、内容検証、目視承認の状態は区別し、有効な完成版は `current.json` が指す承認済み bundle のみとする。先行実証の p16、p17、p26、p30、p36 を含め、subset は current として有効化できない。

`pages/pNN.json` は意味内容と縦の流れ（Stack・Spacer）、`source-layout.json` は原本で各部品・等号・表の列と行が置かれた位置、`font-profile.json` は書体・サイズ・混合書体の指定である。`expected/pNN.json` は原本 PDF と画像から別担当が確認した期待値である。builder は原本 PDF と expected を一切読まない。`verify.py` は生成 PDF から文字・添字・向き・セル・罫線・用紙を独立抽出する。`verify_appearance.py` は原本と出力の内容・読み順・書体を直接比較し、位置・罫線・等号・回転表は新しい決まり（FR-027）どおりかを検査する。trace は部品の位置だけを伝える。入力を expected に自動コピーしない。

## 組み方（FR-027）

全 37 ページを新しい決まり（FR-021〜026）でライブラリの部品だけで組む。原本の座標は再生せず、`source-layout.json` の位置をグリッドのマスの整数倍へ寄せる手掛かりにだけ使う。

- ページのグリッド: p1〜29 は fixture 専用の `CANTILEVER_SOURCE_A4`（595×842 pt、原点 50.88/54.598、A4.pdf のピッチ 16.08/15.48、31列48行。原本の p24 表下端と図の幅を含めるためで、製品の `A4_PORTRAIT_REFERENCE`（30列47行）は変更しない）。p30〜37 は `CANTILEVER_ROTATED_A4`（同じ原点、横 10.8・縦 14.52 pt、46列51行。2026-10-20 ユーザー判断：原本の回転表の列の幅 14.52 pt・行の高さ 10.8 pt を縦横入替の局所グリッドのマスにするため）。用紙の切替えは `PageSection`。方眼Excel ではグリッドが変わる所で別のシートになる（FR-021）。
- ページは `schema_version: 1`、`source_page`、`blocks` を持つ。全 block ID は原本ページの `pNN-` で始まり、一意である。Paragraph / MathBlock / EquationGroup / Table / Cell / CellLines / Columns / Stack / Spacer / Indent / SideRule / QuarterTurn / Image を使う。数式は明示した Row / Script を保持し、表示文字列を数式として再解釈しない。未対応の数式の型は明示エラーにする。
- 字下げ: 原本の見出しの段は 53.52＋14.52k pt に並ぶ。文字の部品（段落・数式・式・表）は段 k を本文の左端から k 列の `Indent` にする（違う段は違う列のまま、段の順も保つ。原本で同じ左端の式は同じ列）。図は段を持たないので最も近い列。p30〜37 は自分のグリッドの最も近い列。
- 等号・結果・単位: `EquationAnchors` は、原本の第一等号・第二等号・結果の右端・単位の始まりに最も近いページの列（グループの式すべての最頻値、同数なら右の列）を、式の列からの距離にしたもの。左辺・ラベル・結果・単位が入らない時だけ右へずらし（原本の最も近い列より左にはしない）、原本で1行の右辺は1行に入るよう第二等号を右へ広げる（結果・単位が本文の幅に入る範囲で）。結果には方眼Excel で数値として見える分のセルをまず与え、それで原本の行が崩れる時だけ少なくする（p2 の7値は文字列のセルになる）。原本の列がすべて同じ式はまとめて決め、原本で 6 pt 以内にあった列（p16〜19 の T1・T2・ストッパー、p13・p14 の断面力と反力、p3〜8 の右寄せの結果。原本で最大 5.04 pt ずれている）はグループをまたいで右側にそろえる。結果のない右辺は第二等号の列をまたいでよい（ライブラリが全幅を与える）ので、第二等号を右へ広げるのは結果のある式の右辺だけ（p16〜20 の「＝ 8 576.98 kN」のような結果だけの行が等号から離れない）。空白の第二の関係記号にはセルを取らない。そろえると原本の行が崩れる所だけそろえない（p13 の断面力と反力の第二等号：反力は右辺のため 25 列目が要り、断面力をそこへ動かすと単位が本文に入らない）。ライブラリは折り返した式の結果を最終行に置くため、原本で結果が1行目にある式（p1・p2 の R_B）は1行目と続きの行を別の式（左辺なし・関係記号は空白）にし、原本で結果だけが下の行にある式（p9〜11 の水平力）は結果を別の式にする。読み順は原本のまま。
- 項の列（FR-025）: 式はすべて `EquationGroup(term_columns="grid")`。右辺の最上位の各項目を1項（添字は直前の項目と同じ項＝方眼Excel の同じセルのリッチテキスト）として `TermStop` で区切り、演算子は中央・数値は右・それ以外は左に寄せる（同じ列で式どうしが食い違えば左）。項の数が同じ連続した式ごとに1つの `EquationGroup`（列を共有）にし、原本で右辺の始まり（と第一等号）が 6 pt 以内のグループどうしは、同じ形の式の各項の最小の幅（`TermStop.width`）をそろえて同じ項を同じ列に置く（p3〜7 の「×」）。形の違う式は同じアンカーの別のグループにする（`Stack` に入れ、元の ID を保つ）。項に分けると原本の行に入らない（退避する・結果が下の行へ行く・右辺が折り返す）グループだけ、右辺全体を1項（入れ子の Row）にする（p1・p2・p12・p13・p19 の9グループ16行。`test_cantilever_grid_rules.py` の `WHOLE_TERM_RUNS` に固定）。
- 表: 列の幅と行の高さは原本の累積の境目をマスへ丸め、内容が入らない所だけ広げる（`_grid_spans`）。原本で同じ x・同じ列の幅の表（p26・p27）は、どの表の内容も入る同じ列にする（`_same_columns`）。セルは `CellLines`（行送り＝行のピッチ、各行が1グリッド行）で、左右の余白は 2.0 pt＋罫線の太さ。行の高さは上下に罫線の太さを足して決める。1行だけのセルはセル全体の中央（上下の余白は罫線の太さ。方眼Excel ではセルの範囲の結合セルの縦の中央になる）。複数行のセルは各行を自分のグリッドの行（p30〜37 はローカルの行＝ページの列）の中に置く: 上寄せで `first_baseline` を使い、行のまとまりをセルの中で行単位で中央に（余りが奇数なら上へ。端の行が罫線に当たる時は1行ずらす）、各行の字の箱（`command_bounds`）が行の中に収まり端の行は罫線から離れる位置の中央に基線を置く（`_row_placement`。方眼Excel は1行を1つのセルの行にしか置けないため。FR-027、2026-10-20 lead の条件）。p30〜37 の下付き添字は 10.8 pt の行に収まるよう基線から 1.0 pt 下（ほかのページは原本の 1.92 pt）。原本の境目ごとの線幅と省略線は `TableBorders` の境目ごとの罫線の種類にする（FR-022・FR-027：原本 0.12 pt → 極細 0.25 pt、0.96 pt → 中 1.0 pt、`pages/*.json` の 0.24 → 極細、0.4・0.5 → 細、0.7・1 → 中）。原稿が原本の見出しの改行をつないでいるセル（p32・p33「せん断」「力」）は原本の行で組む。p21・p22 の縦見出しのセルも1字1行で同じ置き方。
- p30〜37 の大表は `QuarterTurn(turns=1, local_grid=ページのグリッドの縦横入替)` で A4 紙面内で反時計回り90度にする。ページの /Rotate は0。0.01 pt の局所グリッドは廃止した。
- 区切り線: p16〜20 の式のまとまりを括る縦線（以前の Figure＋Line）は `SideRule`（細、原本の縦線の段の列の境目、括る式より左）。`Rule` は本文を横切る横線の部品なので使わない（`SideRule` を使う判断は lead の確認待ち）。
- 添字はライブラリの `Script`（scale 0.65 で 10 pt の添字は 6.5 pt、下付きは原本の 1.92 pt 下〈p30〜37 の表は 1.0 pt 下〉、上付きは 2.4 pt 上）。
- image は SourceFigure が許可済み素材のpath・hash・画素・寸法を検査し、公開 `Image(width_pt=..., height_pt=..., align='left', valign='top')` へ寸法配置を委ねる。返された実snapshotのbytes・画素も台帳と照合し、事前検査後の入力差替えを見逃さない。原本 crop の物理幅・高さを保ち、左上はグリッドの交点（`manifest.json` の `target_bbox` は原本での位置の記録）。収まらない場合はエラーにする。図だけを画像とし、本文・数式・表は含めない。素材の作成方法と個別目視記録は `assets/README.md` と `assets/crop-review.json` に置く。

`pages/*.json` には内容と縦の流れだけを書く。以前の組版の値（表の `columns`・`horizontal_rules`・`vertical_rules`・`border_width`・`padding`・`local_grid` 等、式の `anchors`、区切り線の `rows`、セルの `padding`・`size`・`line_advance`）は位置を `source-layout.json` とグリッドから決めるようになったので削除し、書いてあればエラーにする。

`#######`、原本の見切れた文章、係数・単位・重複値の不整合はそのまま保持する。推測した値に置き換えない。本文・数式・表の画像化は不可。図を追加する際は figure ID、原本 crop、素材 hash、デコード画素 hash・寸法、出力範囲・許可回数を manifest に記録する。

## 書体

本文は書体名 `MS Mincho`（`msmincho.ttc` face0）、見出しは `MS Gothic`（`msgothic.ttc` face0）。`font-profile.json` の書体の指定は書体名で書き、`fixture_fonts()` がライブラリの書体名による解決（FR-024: 同梱 → `%WINDIR%\Fonts` → `%LOCALAPPDATA%\Microsoft\Windows\Fonts`）で引いたファイルの名前・face・SHA-256 を `font-profile.json` の固定値と照合する。フォントファイルはこの fixture に複製・配布しない。face1 の MS PMincho / MS UI Gothic は使わない。書体が見つからない場合や hash 不一致はエラーであり、自動代替は行わない。以前の `render.py --font`（ファイルの差し替え）は書体ファイルの登録の廃止とともに廃止した。

文字サイズは 0.5 pt 刻み（FR-023：原本の 9.9/9.8 pt は 10.0 pt、9.058 は 9.0 pt）。字間は書体の自然な送り（以前の 0.8% の追加字間は廃止）。MS の半角固定幅5 ptと全角10 ptを保ち、文字の縦横倍率を変えない。`font-profile.json` で使うのは `fonts`・`items`（`font`・`size`・`line_sizes`・`font_runs`・`shear_atoms`）・`vertical_glyphs` の鍵。混合書体の見出し（p21・p22・p28）は run ごとの Paragraph / MathBlock を `Columns` で並べ、後の run は列の境目から始める（`x` のある run は原本の位置に最も近い列）。p1 の D 4文字は `appearance.Sheared`（Text の `shear_x=.342`）で原本の人工斜体を保ち、添字は傾けず、原本の 1.68 pt の間隔になるよう基底の送りを 0.68 pt 広げる。p21/22 の縦見出しは漢字の向きを保ち、括弧だけ `appearance.VerticalGlyph`（`quarter_turns=3`、字形を1字ぶんの枠の中央に置く）で回す。抽出のsynthetic空白は通常のspace文字として扱わない。

## 実行

リポジトリルートで開発依存を同期して実行する。

```powershell
uv sync --locked --extra dev
uv run --locked --extra dev python -X utf8 tests/fixtures/cantilever_p01_37/render.py
```

出力は `build/reports/cantilever-p01-37/.staging/<bundle-id>/`。`normal.pdf`、`grid.pdf`、`trace.json`、`mapping.json`、各版の全ページ PNG、`bundle.json` を一式で保存する。入力・製品ソース・依存 lock・書体・原本・ツール版・成果物 hash と独立検証結果を記録する。生成前のあふれや、PDF / JSON / preview / 独立抽出の途中失敗でも既存 current を変更しない。

`verify_source_order`は原本PDFからglyphを直接読み、全37頁のexpectedについて文字集合・一回被覆・読み順・方向・添字役割を検証する。原本の描画命令順を読み順とせず、幾何から並べる。`verify_pdf`に加えprepareの配置開始前とactivateの再検証で実行し、原稿とexpectedの両方を同じ桁順へ誤変更しても有効化を拒否する。既存のgenerated-to-expected照合、原本との外観直接比較、画像回帰は別々に維持する。

`verify_appearance` は原本と内容・読み順・書体（`font`）を比べ、位置は新しい規則で調べる。`placement` は出力 PDF が trace の描画命令をそのまま描いていること（各文字の原点と並び、罫線の端と太さ、括りの縦線の矩形、命令にない文字や線がないこと。debug grid の線は除く）を確かめ、ほかの規則は trace の意味のタグ付きの命令から読む: 項が自分の方眼の列に寄せ方どおり入ること・ラベルが式の左端から始まること・左辺の右端が式の中でそろい関係記号の手前で終わること（`equals`）、表の外の左寄せの段落と数式の各行が列の境目から始まること・括りの縦線がグリッド線上にあること（`position`）、セルの各行が罫線から求めた余白で寄せ方どおりに並び、行送りが行のピッチで、1行だけのセルの字がセルの中で上下の中央にあり、複数行のセルの各行の字が自分のグリッドの行の中にあり、行の位置と基線が builder の置き方（行単位で中央、罫線を避ける、空きの中央）と一致すること（`table`）。規則ごとの検査の件数は `rule_checks` に出る。

`--pages 16,17,26,30,36` の指定は先行実証の再検証に使える。完成版では `--pages` を省略する。通常・grid の全 74 画像を目視し、同じ bundle の全 artifact hash、確認者、日時、`result: "pass"` を持つレビュー JSON を作ってから有効化する。生成直後の自動承認は行わない。

```powershell
uv run --locked --extra dev python -X utf8 tests/fixtures/cantilever_p01_37/render.py --activate <staging-bundle> --visual-review <review.json>
```

有効化は実 PDF を再検証し、変更しない `versions/<bundle-id>/` へ確定した後、`current.json` を一時ファイルから原子的に切り替える。読み手は `resolve_current(output)` で pointer を一度解決し、その版だけを使う。pointer 切替に失敗した未参照版は成功として返さない。旧版は保持する。

テストはプロジェクト共通 wrapper を使用する。

```powershell
$env:PYTHONUTF8 = '1'
$env:COVERAGE_FILE = '.claude/logs/coverage-cantilever-fixture-local'
uv run --locked --extra dev python -X utf8 .claude/skills/_shared/run_tests.py --target tests/unit/test_cantilever_fixture.py --target tests/integration/test_cantilever_p01_37.py --expect pass --label cantilever-fixture-local
```
