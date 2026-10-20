# 検証方法

合格基準は、参照計算書にある文章・等号揃え・数式・結合表・図を、共通グリッド上で読みやすく表現できることです。原本の座標やページ割り、PDFのバイト列一致は要求しません。原本PDFは入力資料として保持し、生成先は `build/reports/` とします。

## 再実行

リポジトリのルートで、Python 3.13のロック環境を用います。

```powershell
uv sync --locked --extra dev
$env:PYTHONUTF8 = '1'
$env:COVERAGE_FILE = '.claude/logs/coverage-validation'
uv run --locked --extra dev python -X utf8 .claude/skills/_shared/run_tests.py --target tests --expect pass --cov gridlayoutpdf --min-coverage 90 --label validation
```

`run_tests.py` は期待する成功／失敗と実測結果を比較して終了コードを返します。TDDのRedとして認めるのは実際のテスト失敗（pytest exit 1）で、importや収集のエラーではありません。並行実行時はラベルと `COVERAGE_FILE` を担当別にします。

## 検証の組み合わせ

- 幾何・文字・組版の単体テストでは、手計算した境界値、実フォントの送りと字形境界、入力順序を確認します。幅が不足しても字形を縮小せず、必要量を含む例外になることを確認します。
- 統合テストではPyMuPDFからPDFを独立に読み、文字・基線・サイズ・用紙寸法・繰返しヘッダー・ページ番号を確認します。配置器の返す座標だけを期待値にはしません。
- 通常PDFとグリッド付きPDFを画像化し、接触・切断・欠字・数式の見た目・改ページ前後を目視します。グリッドは描画の検査用で、通常出力の配置を変えません。
- 固定書体の代表帳票は、目視した生成画像を回帰基準にします。更新時は画像を機械的に置き換えず、差分の原因と通常／グリッド両方の外観を確認します。

PDF検証用のPyMuPDFは開発依存です。利用アプリにPDF抽出器やテスト用フォントの配置は要求しません。既定の書体IPAex明朝はパッケージに同梱しています（FR-024）。

## 固定条件

| 項目 | 条件 |
|---|---|
| 検証書体 | IPAex明朝004.01、face 0。既定の書体名`IPAex明朝`で同梱の `src/gridlayoutpdf/font_data/ipaexm.ttf` に解決する。同じファイルを `tests/fixtures/fonts/` にも置き、利用条件は各 `manifest.json` |
| フォントSHA-256 | `7a306386f930fee80922f71eebf4ffe0f1ff2817da8e619230953487673d71c7` |
| 本文 | 10pt、基線offset 11pt、追加字間上限0.05em |
| 添字 | 基本サイズの0.65倍。幅超過への自動縮小とは別の明示組版 |
| A4参照 | 595×842pt、原点(50.88,54.598)、ピッチ(16.08,15.48)、30列×47行 |
| A3横参照 | 1191×842pt、同じ原点・ピッチ、67列×47行 |
| PDF描画 | ReportLab 5.0.1（`uv.lock`） |
| 抽出・画像化 | PyMuPDF 1.28.2（`uv.lock`） |

Windowsの検証ではPopplerが配置されていないため、PyMuPDFを画像化にも使用します。書体・描画器・画像化ツールを変更した場合、座標テストが成功しても画像差分を確認します。PDFメタデータや圧縮差があるため、PDFファイルのSHA-256一致は生成結果の判定に使いません。

## 要件と確認箇所

以下は検証の対応表です。最終実行結果は末尾の受入記録に記載します。

| 要件 | 実装と主な検証 |
|---|---|
| FR-001 グリッド位置 | geometry / profiles。`test_geometry.py`、`test_profiles.py`、PDFの基線とグリッド出力 |
| FR-002 等号揃え | EquationGroup / EquationAnchors。`test_equations.py`、`test_equation_layout.py`、2等号列の画像確認 |
| FR-003 共通書式・改ページ | ReportStyle / Document / PageDecoration。`test_report_style.py`、`test_document.py`、混在PDF |
| FR-004 Python部品 | 公開APIと `examples/representative_report.py`。wheelを利用するクリーン環境でも生成 |
| FR-005 サイズ保持 | fonts / text / math。幅変更前後の文字サイズ、字形境界、上限付き字間、幅不足の診断 |
| FR-006 配置マスと文字送りの分離 | LayoutContext / MathBox。整数占有行数と内部pt座標、全角文字の自然な送り |
| FR-007 自動配置と位置指定 | Document / At / Columns / KeepTogether。境界・過去行・予約帯・巨大部品・孤立見出し |
| FR-008 共通の体裁 | 段分数、結合表、図画像、代表帳票の数値・PDF抽出・目視・生成画像回帰 |
| FR-009 構造化数式 | math / MathBlock。`test_math.py`、分数・根号・添字・括弧と表セル内の数式 |
| FR-010 式の折返し | wrap_math / EquationGroup。`test_equation_wrap.py`、項・演算子の保存、強制改行、結果行 |
| FR-011 用紙混在 | PageSection / derived_profile。A4→A3→A4、ネスト・空セクション、MediaBoxと文字サイズ |
| FR-014 片持ち梁の固定37頁再現 | cantilever_p01_37 fixture。原本1頁=出力1頁、A4縦、頁番号省略、CCW90表、全文・セル・図の独立照合、追加頁拒否 |
| FR-021 方眼Excel | renderers/xlsx / `render_xlsx`。`test_xlsx_*` の openpyxl 読み戻し・図形のXML・バイト列の決定性、`scripts/compare_xlsx_pdf.py` による Excel から書き出した PDF との比較 |
| FR-022・026 罫線 | BorderStyle / 表・Rule・SideRule。セルの罫線への写し方と、利用者に Line を描かせない検査 |
| FR-023 文字サイズの刻み | 0.5 pt 刻みの丸めと、片持ち梁の 10.0 pt での固定37頁 |
| FR-024 書体名 | fontfinder。同梱書体と Windows の書体フォルダからの解決、wheel の新しい環境での解決 |
| FR-025 項の列 | `EquationGroup(term_columns="grid")`。代表例の grid 版を `strict=True` で方眼Excel に出せること |
| FR-027 片持ち梁の作り直し | 新しい決まりで全37頁、`test_cantilever_grid_rules.py`、方眼Excel を `strict=True` で出せること |

## 範囲と制約

日本語横書きと基本的な禁則、英数字の単語保持を対象にします。完全なUnicode行分割、複雑文字shaping、縦書き、TeX解析、計算値の工学的妥当性判定は含みません。NFC後にも結合文字が残る場合や書体に字形がない場合は明示エラーです。

表はrowspanで接続する行群を分割せず、ヘッダーと最小行群が空ページに入らなければエラーにします。既定0.5ptの罫線を持つ隣接行群の境界は、閉じた枠が接して見かけ1ptになります。画像は静止PNG/JPEGを対象とします。

原本10計算書251ページの全文移植、P7アプリの改修、PyPI公開は今回の検証には含みません。OSの正式な確認範囲はWindows、Pythonは3.12と3.13です。

## 受入記録

2026-10-16の最終全件ゲート `lead-final-all` は **1269 passed（59.22秒）**、製品全体の行カバレッジは **98.82%（2540行中2510行、pytest表示99%）**。基準90%以上を満たし、原本12PDFのハッシュ不変、独立PDF抽出、代表5ページの画像回帰を含めて成功しました。Python 3.13.11での一回の全件実測であり、担当別のテスト件数・カバレッジを合算した値ではありません。ログは `.claude/logs/lead-final-all.log` です。

独立レビューで検出した指摘は回帰TDDで修正し、再レビューでMedium以上0を確認しました。最終段階のDocument、入れ子Columns、公開代表例、画像回帰も確認済みです。個別の根拠は [実装記録](../.claude/docs/plans/grid-aligned-calculation-reports-execution.md) にあります。

### 代表帳票

`examples/representative_report.py` は標準5ページ、長文版6ページです。A4→A3横→A4の構成に、2等号列、分数・根号・添字・分数の指数、変数説明、rowspan／colspanと繰返しヘッダー、寸法図、PNGを含みます。数値文字列は利用側から `display_values` で差し替えられ、収まらない値を縮小せず診断します。

標準と長文の通常／グリッド全22画像をleadが目視し、文字欠落・接触・切断・自動縮小を認めませんでした。例の最終ゲート `lead-representative-final` は17 passed。標準版の通常5ページを画像回帰の基準とし、書体・入力画像・描画ツール・PNGと画素のhashを固定します。更新手順は [画像回帰の説明](../tests/visual/README.md) を参照してください。

### 配布物と互換性

2026-10-20（FR-024）からは、sdistとwheelの両方に同梱書体を含めます。`gridlayoutpdf/font_data/` にIPAex明朝・IPAexゴシック（004.01、無改変）、IPAフォントライセンスv1.0の原文、配布元のReadme、SHA-256を固定した `manifest.json` が入ることを、`uv build` の出力と新しい仮想環境へのwheelの導入（site-packagesの同梱書体へ名前で解決すること）で確かめました。参照PDF・画像・テスト・`.claude`は引き続き配布物へ含めません。

それ以前の記録：`uv build` によりsdistを作り、そのsdistからwheelを生成しました。wheelは20個の製品Pythonファイルとパッケージ情報の計23エントリー、sdistは24エントリーで、当時は書体を配布物へ含めていませんでした。

Python 3.12.12／3.13.11の新規仮想環境へwheelを通常インストールし、リポジトリ外へコピーした例・画像・利用者側フォントで出力しました。`python -I`で実行し、site-packagesからの読込みとPyMuPDF未導入を確認しています。各環境の標準5ページは、本文・用紙寸法・全画素が承認した出力と一致しました。これは3.12で全開発テストを実行したという意味ではなく、両バージョンの配布物・実行時機能の検証です。

結果は `build/reports/wheel-acceptance.json` に保存しています。最終READMEを含むwheelのSHA-256は `d71f18b1d414d44784853e9a9a0205da75cafac994f6eb7d486f57d3eebf198b`。両環境へこのwheelを再インストールして確認しました。利用者にはReportLab・Pillowが導入され、検証用のPyMuPDFは必要ありません。

### 300ページの出力計測

2026-10-16、Windows / Python 3.13.11。14,100行の一つの段落を47行ずつ自動改ページしました。境界の負荷を測るため、この段落だけmin_first/min_lastを1にしています。生成後にPDFを独立抽出し、全14,100個の行IDが入力順で1回ずつ存在し、全300ページの番号が正しいことを確認しました。

| 計測 | 書体登録 | 配置 | PDF描画 | 合計 | Python割当メモリのピーク |
|---|---:|---:|---:|---:|---:|
| 時間計測（tracemallocなし） | 0.112秒 | 27.472秒 | 3.667秒 | 31.251秒 | 未計測 |
| メモリ計測（tracemallocあり） | 4.271秒 | 176.146秒 | 22.868秒 | 203.285秒 | 37.877 MiB |

tracemalloc自体の負荷があるため、時間とメモリを別実行で記録しています。ピークはPythonの割当メモリで、プロセスのRSSではありません。入力行リストの作成とPDF抽出は計測範囲外です。表示内容や書体・環境に依存する実測であり、性能保証値や合否の上限ではありません。

実行スクリプトは `.claude/logs/benchmark_300.py`、結果は `build/reports/performance-300{,-time}.json`、PDFは同じstemで保存しています。これらはローカル受入の生成物で、配布パッケージには入りません。

### 片持ち梁の原本p01〜37

ユーザーが指摘した書体・インデント・等号位置・表行高を修正し、原本PDFから直接取得した情報で外観を検査しています。旧goldenの一致だけを原本との外観一致の証拠にはしません。今回の最終検証は **1738 passed（107.30秒）**、製品の行カバレッジ **98.92%（2693行中2664行）** です（`cantilever-appearance-final-full`）。

`tests/fixtures/cantilever_p01_37/` は `tests/output/13_片持ち梁照査.pdf` の物理p1〜37を再現する表示用原稿です。本文・数式・表を公開部品で組み、16点の図だけは出典とhashを持つ画像素材として原寸配置します。構造計算の再計算や原本の表示値の訂正は行いません。

原本1頁を出力1頁へ固定し、全頁595×842pt・PDF Rotate0とします。p30〜37の表は`QuarterTurn`で反時計回り90度に配置し、全頁の右上番号を省略します。`KeepTogether`と頁ID検査により、容量不足、内容の別頁移動、追加頁は「原本再現できず」のエラーです。文字の自動縮小や余剰頁の切捨ては行いません。

```powershell
uv run --locked --extra dev python -X utf8 tests/fixtures/cantilever_p01_37/render.py --output build/reports/cantilever-p01-37
```

このコマンドは一意の`.staging/<bundle-id>/`へ通常/grid PDF、配置trace、原本対応表、各37枚のpreviewを生成し、両PDFの内容と外観を検証します。検証後も自動でcurrentにはしません。全74画像の目視記録が成果物hashと一致した場合だけ、`--activate <staging-dir> --visual-review <review.json>`で不変の`versions/<bundle-id>/`へ移し、最後に`current.json`を原子的に切り替えます。途中失敗時に旧currentが残ることを失敗注入で検査します。先行5頁などのsubsetはcurrent化できません。

照合用`expected/`は組立用`pages/`と別担当が原本から作成しています。全項目・空セル・結合・罫線・文字方向・添字・字形サイズ・画像の配置と画素を実PDFから検査します。114算式、124ケース、63箇所の`#######`の総量確認は、項目ごとの照合を補う検査です。生成後画像の回帰手順は[画像回帰の説明](../tests/visual/README.md)、不足機能と改善候補は[改善項目一覧](../.claude/docs/research/cantilever-p01-37-improvements.md)を参照してください。

2026-10-17の外観修正後全件実測は原本12PDFのhash、既存golden、新しい通常37頁goldenの再生成画素一致を含みます。通常/grid各3345項目と全37頁の外観検査が合格。外観107件、旧内容127件、builder25件、固定頁/保存24件の計283件もrootが個別に再実行しました。基線21,204字の最大差は0.043419pt、等号335件は0.0000611pt、表罫線21,312検査は0.002ptです。全体coverageの実数は`.claude/logs/cantilever-appearance-final-coverage.json`に保存しています。

rootは再生成した最終候補の通常37枚/grid37枚を個別表示し、原本の書体・インデント・等号・行高、添字・括弧の接触、切断、セル結合、罫線、回転方向、頁番号不在を確認しました。記録は`build/reports/cantilever-p01-37/appearance-correction-visual-review.json`、登録画像とhashは`tests/visual/cantilever_p01_37/manifest.json`です。128入力・78成果物・全74目視画像を結び付けています。原本との全画素一致は主張しません。細罫の塗り矩形とstrokeには描画時のアンチエイリアス差が残り、書体の微小な変形も独立した許容範囲で検査します。

独立レビューで見つかった最適化Python起動時の検査消失、添字や意味runの基線ずれ、未対応ASTの黙示省略、relationの別文字への置換、行/style数不一致による行欠落を修正し、負例を追加しました。原本に対する非空白文字の一回被覆・方向・読み順も検査します。検証器は`-O`/`-OO`/`PYTHONOPTIMIZE`を明示拒否します。

追加APIを含むsdist→wheelも、リポジトリ外の新規Python3.12.12/3.13.11で受入済みです。21製品moduleを含み、原本・書体・検証コードを配布物へ含めていませんでした（書体はFR-024以降、同梱の2書体だけを含めます）。PyMuPDF未導入でQuarterTurn±1、選択罫線、Table.row_heightsと過小高の拒否、Text.shear_x、後続の水平文字を検証し、両環境の画素一致を確認しました。証拠は`build/reports/cantilever-p01-37/wheel-acceptance.json`です。

初回1508件の検証と`20261017T005753Z-7952a1f3f915474c8a478f77d40cf9da`は外観修正前の履歴です。今回の完成版は`versions/20261017T023053Z-a954761644604bd1a289b5fcdd9f20d1/`で、独立レビュー未解決0・全ゲート通過後に有効化しました。`build/reports/cantilever-p01-37/current.json`の解決先、128入力・78成果物のhash、両PDF37頁・A4縦・Rotate0をrootが再確認済みです。記録は同rootの`appearance-correction-current-audit.json`です。

### 片持ち梁の改善計画と共通API

2026-10-17の承認済み改善計画で、`Insets`、`CellLines`、表の行高診断、`Image`の物理寸法、`Script`の明示サイズ・基線offset、`Table(split=False)`を追加しました。既定の分割・丸め・画像fit・添字配置は保持します。`split=False`はheaderを含む全行を1partへまとめ、共有罫線を統合します。任意分割表のページ境界をまたぐ線は、2026-10-20の辺ごとの罫線（FR-026）で継ぎ目を1本として描くようになりました。

レビュー指摘修正後の最終全件検証は **1939 passed（192.16秒）**、行カバレッジは **98.825109%（2979行中2944行）**。ログは`.claude/logs/cantilever-improvements-revised-final.log`、実数は`cantilever-improvements-revised-final-coverage.json`です。原本対expectedの文字順序と添字の役割を直接検査するゲートを、生成前・有効化前へ追加しました。同じ文字集合の桁交換、符号移動、回転セル、添字role/index/textの改変を負例で検査します。さらに基準commitの全37頁・3345項目のIDと原本bboxだけを独立pinし、本文とbboxの連動交換・ID交換・微小bbox変更も拒否します。本文・方向・添字は固定hashへ含めず、原本から直接検査します。

全16図を物理寸法Imageへ、旧CompactCellをCellLinesへ委譲し、829セルと16図を検査しました。非等間隔アンカーを持つ現行SourceCell/SourceScriptと表の原本配置は維持しています。新APIを組み合わせた別3頁の実証では、298セルを独立expectedと実PDFで照合し、通常/grid計6画像をrootも確認しました。密な表に必要な内側余白と局所容量は実証側で明示し、原本の37頁へ転用していません。

初回候補031210の通常/grid計74枚を個別目視しました。修正後の最終候補033209は、その全74枚および外観受入版023053とPNG bytes・画素配列の両方が完全一致することを確認し、同一画像の目視結果を再利用しました。最終候補の代表5頁×通常/gridの10画像も再表示して確認しています。原本PDFとの内容・外観検査は最終候補の全37頁で合格。golden PNGは保持し、manifestの入力hashと目視記録だけを更新しました。原本そのものとの全画素一致を意味しません。

修正後にsdistから再生成したwheelは22製品moduleを含み、Python3.12.12/3.13.11の新規環境へインストールして新APIを描画しました。両版の画素・物理画像寸法・文字内容が一致し、PyMuPDFを導入していないことを確認しました。結果は`build/reports/cantilever-p01-37/improvements-wheel-acceptance.json`、wheel SHA-256は`14ac344e68447ef802580824e14b02cf6a719c6d7b04ea0a92dc28125ac02510`です。

独立レビューのQ01（原本領域対応・Medium）とQ02（枠逸脱診断の軸・Low）を修正して再レビューし、未解決0件となりました。全ゲート通過後に`versions/20261017T033209Z-f93e3db55c094beaa28d3b3029fc2b7d/`を有効化し、129入力・78成果物・currentの解決先・両PDF37頁を再監査済みです。旧versionは保持しています。詳細と成果物へのリンクは[改善計画の実行記録](../.claude/docs/plans/cantilever-p01-37-improvements-execution.md)を参照してください。

### 方眼Excel（FR-021〜027）

2026-10-20、feature/grid-excel-output の最終全件ゲート `grid-excel-final` は **3838 passed・2 skipped（587.01秒）**、製品全体の行カバレッジは **98.2%（7230行中7101行、pytest表示98%）** です。lead が単独で一回実行した値です。PNG 正解2件（片持ち梁37頁・代表5頁）はユーザーが Gate 4 で承認した新しい画像に対して合格しています。skip の2件は DocuWorks PDF の印刷を前提にした Excel の検査で、この環境のプリンター（DocuWorks Printer on Ne04:）では対象外です。ログは `.claude/logs/grid-excel-final.log` です。

Excel 16.0（build 20326）で、代表例（`term_columns="grid"` の標準・長い版）と片持ち梁 p1〜37 を `strict=True` で方眼Excel に出し、`scripts/compare_xlsx_pdf.py` で Excel から書き出した PDF とライブラリの PDF を比べました。修復なしで開くこと・ページ数・用紙・`###` の表示なし・見つからない字0は全件合格です。文字片が横1マス・縦半マスを越えたのは代表例 標準364片中5、長い版414片中12、片持ち梁5418片中1です。内訳は、本文の幅いっぱいの行で Excel のセルの余白（片側 2.4 pt）のために最後の1字が切れるものと、分子の中の上付き・入れ子の分数の分母の縦のずれ（8.3〜8.5 pt）です。Gate 3 でユーザーが並べた画像を目視し、これらを方眼Excel の制限として受け入れました（DESIGN の Key Decisions）。

片持ち梁は FR-027 の新しい決まりで全37頁を組み直し、固定37頁に収まることと、原本との内容の照合を確かめています。p30〜37 は横 10.8・縦 14.52 pt のグリッドの縦横入替で組みます（ユーザーの選択）。有効な版は `build/reports/cantilever-p01-37/versions/20261020T084235Z-5654d55613454fceb14d796e01cdf09b/` です。

配布物は 0.2.0 です。`uv build` の wheel（SHA-256 `4f84b2abe368fa50beca841cad64209a70609906469a26a181fa87709145e5fb`）に `renderers/xlsx` と同梱書体が入り、依存が ReportLab・Pillow だけ（openpyxl・PyMuPDF は開発用）であることを確かめました。この wheel を新しい仮想環境（Python 3.13）に入れ、`python -I` で `render_xlsx(..., strict=True)` が書けることを確かめています。Python 3.12 の環境での導入はこの作業では行っていません。
