# 検証方法

合格基準は、参照計算書にある文章・等号揃え・数式・結合表・図を、共通グリッド上で読みやすく表現できることです。原本の座標やページ割り、PDFのバイト列一致は要求しません。原本PDFは入力資料として保持し、生成先は `build/reports/` とします。

## 再実行

リポジトリのルートで、Python 3.13のロック環境を用います。

```powershell
uv sync --locked --extra dev
$env:PYTHONUTF8 = '1'
$env:COVERAGE_FILE = '.agents/logs/coverage-validation'
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests --expect pass --cov gridlayoutpdf --min-coverage 90 --label validation
```

`run_tests.py` は期待する成功／失敗と実測結果を比較して終了コードを返します。TDDのRedとして認めるのは実際のテスト失敗（pytest exit 1）で、importや収集のエラーではありません。並行実行時はラベルと `COVERAGE_FILE` を担当別にします。

## 検証の組み合わせ

- 幾何・文字・組版の単体テストでは、手計算した境界値、実フォントの送りと字形境界、入力順序を確認します。幅が不足しても字形を縮小せず、必要量を含む例外になることを確認します。
- 統合テストではPyMuPDFからPDFを独立に読み、文字・基線・サイズ・用紙寸法・繰返しヘッダー・ページ番号を確認します。配置器の返す座標だけを期待値にはしません。
- 通常PDFとグリッド付きPDFを画像化し、接触・切断・欠字・数式の見た目・改ページ前後を目視します。グリッドは描画の検査用で、通常出力の配置を変えません。
- 固定書体の代表帳票は、目視した生成画像を回帰基準にします。更新時は画像を機械的に置き換えず、差分の原因と通常／グリッド両方の外観を確認します。

PDF検証用のPyMuPDFは開発依存です。利用アプリにPDF抽出器やテスト用フォントの配置は要求しません。

## 固定条件

| 項目 | 条件 |
|---|---|
| 検証書体 | IPAex明朝004.01、face 0。実ファイルと利用条件は `tests/fixtures/fonts/manifest.json` |
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

## 範囲と制約

日本語横書きと基本的な禁則、英数字の単語保持を対象にします。完全なUnicode行分割、複雑文字shaping、縦書き、TeX解析、計算値の工学的妥当性判定は含みません。NFC後にも結合文字が残る場合や書体に字形がない場合は明示エラーです。

表はrowspanで接続する行群を分割せず、ヘッダーと最小行群が空ページに入らなければエラーにします。既定0.5ptの罫線を持つ隣接行群の境界は、閉じた枠が接して見かけ1ptになります。画像は静止PNG/JPEGを対象とします。

原本10計算書251ページの全文移植、P7アプリの改修、PyPI公開は今回の検証には含みません。OSの正式な確認範囲はWindows、Pythonは3.12と3.13です。

## 受入記録

2026-10-16の最終全件ゲート `lead-final-all` は **1269 passed（59.22秒）**、製品全体の行カバレッジは **98.82%（2540行中2510行、pytest表示99%）**。基準90%以上を満たし、原本12PDFのハッシュ不変、独立PDF抽出、代表5ページの画像回帰を含めて成功しました。Python 3.13.11での一回の全件実測であり、担当別のテスト件数・カバレッジを合算した値ではありません。ログは `.agents/logs/lead-final-all.log` です。

独立レビューで検出した指摘は回帰TDDで修正し、再レビューでMedium以上0を確認しました。最終段階のDocument、入れ子Columns、公開代表例、画像回帰も確認済みです。個別の根拠は [実装記録](../.agents/docs/plans/grid-aligned-calculation-reports-execution.md) にあります。

### 代表帳票

`examples/representative_report.py` は標準5ページ、長文版6ページです。A4→A3横→A4の構成に、2等号列、分数・根号・添字・分数の指数、変数説明、rowspan／colspanと繰返しヘッダー、寸法図、PNGを含みます。数値文字列は利用側から `display_values` で差し替えられ、収まらない値を縮小せず診断します。

標準と長文の通常／グリッド全22画像をleadが目視し、文字欠落・接触・切断・自動縮小を認めませんでした。例の最終ゲート `lead-representative-final` は17 passed。標準版の通常5ページを画像回帰の基準とし、書体・入力画像・描画ツール・PNGと画素のhashを固定します。更新手順は [画像回帰の説明](../tests/visual/README.md) を参照してください。

### 配布物と互換性

`uv build` によりsdistを作り、そのsdistからwheelを生成しました。wheelは20個の製品Pythonファイルとパッケージ情報の計23エントリー、sdistは24エントリーです。書体・参照PDF・画像・テスト・`.agents`は配布物へ含まれません。

Python 3.12.12／3.13.11の新規仮想環境へwheelを通常インストールし、リポジトリ外へコピーした例・画像・利用者側フォントで出力しました。`python -I`で実行し、site-packagesからの読込みとPyMuPDF未導入を確認しています。各環境の標準5ページは、本文・用紙寸法・全画素が承認した出力と一致しました。これは3.12で全開発テストを実行したという意味ではなく、両バージョンの配布物・実行時機能の検証です。

結果は `build/reports/wheel-acceptance.json` に保存しています。最終READMEを含むwheelのSHA-256は `d71f18b1d414d44784853e9a9a0205da75cafac994f6eb7d486f57d3eebf198b`。両環境へこのwheelを再インストールして確認しました。利用者にはReportLab・Pillowが導入され、検証用のPyMuPDFは必要ありません。

### 300ページの出力計測

2026-10-16、Windows / Python 3.13.11。14,100行の一つの段落を47行ずつ自動改ページしました。境界の負荷を測るため、この段落だけmin_first/min_lastを1にしています。生成後にPDFを独立抽出し、全14,100個の行IDが入力順で1回ずつ存在し、全300ページの番号が正しいことを確認しました。

| 計測 | 書体登録 | 配置 | PDF描画 | 合計 | Python割当メモリのピーク |
|---|---:|---:|---:|---:|---:|
| 時間計測（tracemallocなし） | 0.112秒 | 27.472秒 | 3.667秒 | 31.251秒 | 未計測 |
| メモリ計測（tracemallocあり） | 4.271秒 | 176.146秒 | 22.868秒 | 203.285秒 | 37.877 MiB |

tracemalloc自体の負荷があるため、時間とメモリを別実行で記録しています。ピークはPythonの割当メモリで、プロセスのRSSではありません。入力行リストの作成とPDF抽出は計測範囲外です。表示内容や書体・環境に依存する実測であり、性能保証値や合否の上限ではありません。

実行スクリプトは `.agents/logs/benchmark_300.py`、結果は `build/reports/performance-300{,-time}.json`、PDFは同じstemで保存しています。これらはローカル受入の生成物で、配布パッケージには入りません。
