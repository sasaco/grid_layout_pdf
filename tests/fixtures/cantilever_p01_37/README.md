# 片持ち梁照査・原本 p01〜37 の再現 fixture

`tests/output/13_片持ち梁照査.pdf` の物理ページ 1〜37 を、表示文字列と意味のある部品から組み立てる。計算・再計算は行わない。原本と同じ 37 枚の A4 縦に固定し、各原本ページを一つの `KeepTogether(PageFrame(...))` にする。右上のページ番号は全ページで省略する。内容が入らない場合は `LayoutOverflowError: 原本再現できず` で停止し、ページ削除・追加・自動縮小で補わない。

全 37 ページの入力と、16 点の原本図の切り出しを収録する。ページ・部品・図・原本の不整合の台帳は `manifest.json` に置く。入力の転記、内容検証、目視承認の状態は区別し、有効な完成版は `current.json` が指す承認済み bundle のみとする。先行実証の p16、p17、p26、p30、p36 を含め、subset は current として有効化できない。

`pages/pNN.json` は意味内容、`source-layout.json` は部品・意味行・数式の役割・表セルの配置、`font-profile.json` は書体・サイズ・混合書体の指定である。`expected/pNN.json` は原本 PDF と画像から別担当が確認した期待値である。builder は原本 PDF と expected を一切読まない。`verify.py` は生成 PDF から文字・添字・向き・セル・罫線・用紙を独立抽出する。`verify_appearance.py` は原本と出力の native 文字・書体・等号・罫線を直接比較する。trace は部品の位置だけを伝える。入力を expected に自動コピーしない。

## 入力の構造

- ページは `schema_version: 1`、`source_page`、`blocks` を持つ。全 block ID は原本ページの `pNN-` で始まり、一意である。
- Paragraph / MathBlock / EquationGroup / Table / Cell / QuarterTurn / Figure を使う。数式は明示した Row / Script を保持し、表示文字列を数式として再解釈しない。fixture の意味配置で未対応の AST（Fraction 等）は明示エラーにし、文字を黙って捨てない。元の stack / columns の ID と領域も trace に残す。
- PageFrame は 0.01 pt の局所グリッドで各意味部品を計測し、入力の行頭・基線・数式の lhs/rhs/result/unit アンカーに配置する。各文字の座標列や PDF 命令を再生しない。原本の改行数と一致しない場合は停止する。有意空白は別入力の `text_with_spaces` で保ち、添字を文字列へ平坦化しない。文字空白では表せない式の間隔は `semantic_runs` の数値operand・演算子・ラベル・添字atomの `start_x` / `baseline` で保持する。Script は不可分のまま、base の原点に対する `script_offsets` の `sub_x` / `sup_x` / `sub_y` / `sup_y` を持つ。単字ごとの位置指定へ展開しない。関係記号の転記と意味AST、セル行とstyleの個数が一致しない場合も停止する。
- 外側は fixture 専用の `CANTILEVER_SOURCE_A4`（595×842 pt、原点50.88/54.598、pitch16.08/15.48、31列48行）。原本の p24 表下端と図の幅を含めるためで、製品の `A4_PORTRAIT_REFERENCE`（30列47行）は変更しない。
- 表は全セル・結合を Table に渡し、`row_heights` で原本の各行高を固定する。`horizontal_rules` / `vertical_rules` は原本の線幅と省略線を保持する。外周の中心線座標を Table の外枠へ半線幅だけ変換し、part 境界の二重線は半幅ずつにする。隣接 part の縦罫線に生じる半線幅の空隙は同一直線の native Line を連結して閉じる。
- SourceCell は意味行の書体・添字・基線を保持する。Table padding は0。fixture の表内測定だけ `SourceTableInkFonts` を用い、書体全体の typographic ascent/descent の代わりに、その文字列の実 glyph ink と advance を予約する。元の FontRegistry、native Text、文字サイズ、製品全体の bounds 検査は変更しない。Table は引き続き実 ink と全罫線の干渉を検査する。
- 原本基線で実 ink が上罫線に接する8セルだけ、上端の実測不足量＋0.001 ptを下へ移す。対象は p30/31/34/35 の `*-r0-cell1`、p32/33 の `*-r0-cell1` と `*-r0-cell2`（「組合せ」「せん断」）。最大移動はそれぞれ0.043421875 / 0.01271875 ptで、明示ID以外には適用せず、0.05 ptを超えれば停止する。独立した原本基線比較の許容0.20 ptは変更しない。行高拡張や文字縮小は行わない。
- p30〜37 は Table / Cell が列・結合・罫線を管理し、QuarterTurn(turns=1) が A4 紙面内で反時計回り90度にする。文字は原本の9.9 ptを使い、ページの /Rotate は0。
- p21/22 の縦見出しは漢字の向きを保ち、括弧だけ90度回転する。原本の縦用括弧の font glyph bounds に基づいて意味行の ink 中心を合わせ、抽出上の typographic bbox の一致による「破」との重なりを防ぐ。
- image は SourceFigure が許可済み素材のpath・hash・画素・寸法を検査し、公開 `Image(width_pt=..., height_pt=..., align='left', valign='top')` へ寸法配置を委ねる。返された実snapshotのbytes・画素も台帳と照合し、事前検査後の入力差替えを見逃さない。原本 crop の物理幅・高さを保ち、収まらない場合はエラーにする。図だけを画像とし、本文・数式・表は含めない。素材の作成方法と個別目視記録は `assets/README.md` と `assets/crop-review.json` に置く。

公開`CellLines`は等間隔の明示行に使い、旧CompactCellは原稿をMathNodeへ変換する薄いadapterとして残す。原本固有の非等間隔start_x/baselineや字送りを持つSourceCell/SourceScriptは保持する。現行source表は原本の罫線中心と二分したseam幅を保持するため既定`split=True`を使う。公開`Table(split=False)`の共有罫線統合は別の実証で検証し、原本外観を無条件に置き換えない。

`#######`、原本の見切れた文章、係数・単位・重複値の不整合はそのまま保持する。推測した値に置き換えない。本文・数式・表の画像化は不可。図を追加する際は figure ID、原本 crop、素材 hash、デコード画素 hash・寸法、出力範囲・許可回数を manifest に記録する。

## 書体

本文は Windows の `C:/Windows/Fonts/msmincho.ttc` face0（MS Mincho）、見出しは `C:/Windows/Fonts/msgothic.ttc` face0（MS Gothic）。各 TTC の SHA-256 を `font-profile.json` に固定し、フォントファイルはこの fixture に複製・配布しない。face1 の MS PMincho / MS UI Gothic は使わない。ファイル不在や hash 不一致はエラーであり、自動代替は行わない。`--font` は診断用の明示上書きで、原本の書体検証を免除しない。

原本は通常10 pt、回転表9.9 pt、添字6.7/6.6 pt。SourceLiteral は自然 advance の0.8%（10 pt の半角0.04 / 全角0.08 pt）を字間に足す。MS の半角固定幅5 ptと全角10 ptを保ち、文字の縦横倍率を変えない。p21/22 見出し末尾の「4 箇所」等は MS Mincho の意味runに切り替える。p1 の D 4文字は native Text の `shear_x=.342` で原本の人工斜体を保ち、添字は傾けず1.68 ptの明示gapで元の開始位置を保つ。抽出のsynthetic空白は通常のspace文字として扱わない。

## 実行

リポジトリルートで開発依存を同期して実行する。

```powershell
uv sync --locked --extra dev
uv run --locked --extra dev python -X utf8 tests/fixtures/cantilever_p01_37/render.py
```

出力は `build/reports/cantilever-p01-37/.staging/<bundle-id>/`。`normal.pdf`、`grid.pdf`、`trace.json`、`mapping.json`、各版の全ページ PNG、`bundle.json` を一式で保存する。入力・製品ソース・依存 lock・書体・原本・ツール版・成果物 hash と独立検証結果を記録する。生成前のあふれや、PDF / JSON / preview / 独立抽出の途中失敗でも既存 current を変更しない。

`verify_source_order`は原本PDFからglyphを直接読み、全37頁のexpectedについて文字集合・一回被覆・読み順・方向・添字役割を検証する。原本の描画命令順を読み順とせず、幾何から並べる。`verify_pdf`に加えprepareの配置開始前とactivateの再検証で実行し、原稿とexpectedの両方を同じ桁順へ誤変更しても有効化を拒否する。既存のgenerated-to-expected照合、原本との外観直接比較、画像回帰は別々に維持する。

`--pages 16,17,26,30,36` の指定は先行実証の再検証に使える。完成版では `--pages` を省略する。通常・grid の全 74 画像を目視し、同じ bundle の全 artifact hash、確認者、日時、`result: "pass"` を持つレビュー JSON を作ってから有効化する。生成直後の自動承認は行わない。

```powershell
uv run --locked --extra dev python -X utf8 tests/fixtures/cantilever_p01_37/render.py --activate <staging-bundle> --visual-review <review.json>
```

有効化は実 PDF を再検証し、変更しない `versions/<bundle-id>/` へ確定した後、`current.json` を一時ファイルから原子的に切り替える。読み手は `resolve_current(output)` で pointer を一度解決し、その版だけを使う。pointer 切替に失敗した未参照版は成功として返さない。旧版は保持する。

テストはプロジェクト共通 wrapper を使用する。

```powershell
$env:PYTHONUTF8 = '1'
$env:COVERAGE_FILE = '.agents/logs/coverage-cantilever-fixture-local'
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests/unit/test_cantilever_fixture.py --target tests/integration/test_cantilever_p01_37.py --expect pass --label cantilever-fixture-local
```
