# GridLayoutPdf 実装記録

計画: [grid-aligned-calculation-reports.md](grid-aligned-calculation-reports.md)。2026-10-16、ユーザーが `ok $tdd $parallel-agent-dev` で実装を承認。

## 実行方針

同じ作業ツリーでファイル所有を分ける。全体フォーマット、git reset/stash、他担当のファイル変更は禁止。依存するAPIを凍結してから後続担当へ渡す。エージェントは担当のTDDログと変更ファイル全量を報告し、計画への統合記録・独立した再検証はleadが行う。

TDDは `.claude/skills/tdd/SKILL.md`、レビューは `.claude/skills/parallel-agent-dev/ImplementationLoop.md` を使用する。コピー元の `.claude/skills/tdd-workflow`、Rust、FrameWebのコマンドは本リポジトリには適用しない。テストは必ず `run_tests.py` 経由で実行し、Redはpytest exit 1を確認する。Windowsの出力はプロセス内 `PYTHONUTF8=1` を使用する。

## タスクグラフと担当

| 段階 | 独立して進める担当 | 依存・合流条件 | 状態 |
|---|---|---|---|
| 1 | bootstrap:環境 / reference_fixtures:参照と表示原稿 / font_supply:書体供給 | テスト実行は環境完成後、leadが全件検証 | ✅ 24 passed |
| 2a | bootstrap:幾何・プロファイル / font_supply:書体・描画命令 | Step 1検証後、共有契約を固定 | ✅ レビュー指摘2件解消 |
| 2b | bootstrap:数式の最小組版 / reference_fixtures:PDF描画器・試作原稿 | 2aの契約後、同一原稿でPDF実証 | ✅ 全体413 passed、6PNG目視 |
| 3a | reference_fixtures:共通style・計測・分割結果 | Step 2ゲート後、配置契約を固定 | ✅ lead対象134 passed、レビュー修正・再検証済み |
| 3b–4a | font_supply:文章 / bootstrap:数式の構造的折り返し | 文字行組・数式行組は既存基盤だけで独立実装 | ✅ lead統合401 passed、独立再レビュー済み |
| 4b | bootstrap:Equation/Group・共有アンカー | 文章・wrap_mathのleadゲート後。equation-contractを凍結 | ✅ 数値・PDF・4PNGを検証。gap境界修正・独立再レビュー済み |
| 5a | reference_fixtures:Stack/Columns/KeepTogether/At | 共通計測型だけに依存する容器を先行 | ✅ lead対象206 passed |
| 5b | bootstrap:フロー・ページ分割・位置指定・用紙混在 | 数式アダプター統合ゲート後。pagination-contractを凍結 | ✅ PDF全10PNG・境界修正・独立round3完了 |
| 6a/7a | reference_fixtures:表の独立計測 / font_supply:図・画像の独立計測と描画 | 安定した共通型とParagraph/MathBlockだけへ依存する部分は先行可能。文書統合と完成ゲートはStep 5b後 | ✅ 独立部分とPDF目視。表の丸め誤差修正・独立再レビュー済み |
| 6b/7b | 表・図のページ統合、代表帳票 | Step 5bと独立部品の完了後 | ✅ 公開例17 passed・全22PNG・独立レビュー完了 |
| 8 | 独立レビュー / 利用文書・配布検証 | 実装完了後、Medium以上を修正して再検証 | ✅ 全件1269 passed・coverage98.82%・wheel2環境・300ページ |

## leadが定義した検証ケース

各項目の完了は対応する `run_tests.py --expect pass` の成功とログを条件とする。実測値・独立PDF抽出・画像確認を使い、実装の返す値をそのまま正解にしない。

- [x] ✅ E01: 12原本のハッシュと用途、6種類の非空表示用原稿を固定する。
- [x] ✅ E02: 書体ファイル・face・ハッシュ・利用条件、必要な日本語/記号の存在を検証する。
- [x] ✅ G01: A4の原点・30×47・最終境界、A3の67×47を独立した数値で確認する。
- [x] ✅ G02: 不正なピッチ・行列数・NaN/inf・用紙外・小さすぎる生成プロファイルを拒否する。
- [x] ✅ F01: 同じfaceで文字幅/ascent/descentを計測し、欠字・未配置・不正フォントを明確に失敗させる。
- [x] ✅ R01: A4/A3/A4のMediaBox、文字サイズ、上原点からPDF座標への変換を独立抽出で確認する。
- [x] ✅ R02: 描画状態のページ間漏れ、描画失敗時の既存出力保持を確認する。
- [x] ✅ M01: 段分数・根号・上下付き・分数の指数・括弧の必要寸法と非接触を確認する。
- [x] ✅ M02: 数式内部の自由配置と、外側の整数占有行数を区別する。
- [x] ✅ T01: 全角文字を半セル幅へ圧縮しない。日本語・ASCII・結合文字を保つ。NFC後に残る結合マークは明示拒否。
- [x] ✅ T02: 禁則・英単語・明示改行・空行・狭すぎる幅・最終行・単一文字を確認する。
- [x] ✅ T03: 字間追加のみで指定幅へ合わせ、上限・負の調整禁止を確認する。
- [x] ✅ Q01: 2等号列・結果右揃え・単位開始を複数行/局所グループで確認する。
- [x] ✅ Q02: 長いラベル・左辺・結果・単位の幅衝突を検出する。
- [x] ✅ Q03: 自動/明示改行で項・演算子の順番を保持し、分数・根号・添字を分断しない。
- [x] ✅ Q04: 幅を狭めると行数が増え、字形サイズは変わらない。分割不能なら必要幅を示す。
- [x] ✅ P01: 下端ぴったり/1行不足、段落の先頭末尾各2行、見出しの孤立防止を確認する。
- [x] ✅ P02: KeepTogetherの巨大ブロックや分割不能式が無限改ページせず失敗する。
- [x] ✅ P03: 明示位置が過去の行・枠外・重複なら失敗し、正常なら縦帯を予約する。
- [x] ✅ P04: 横並びの高さ、用紙切替、空文書・連続改ページの規則を確認する。
- [x] ✅ P05: ページ番号/総数を予約枠へ後描画し、桁増加・装飾の枠超過を検出する。
- [x] ✅ B01: 表の列幅・セル内容・行高・colspan/rowspanを検証する。
- [x] ✅ B02: 複数ヘッダー再掲、rowspan行群の同一ページ、内容の重複欠落なしを確認する。
- [x] ✅ B03: 不正結合、ヘッダー本文をまたぐspan、巨大行群、空表、幅超過を検証する。
- [x] ✅ I01: 図の線/矢印/ラベルと画像が指定枠に収まり、縦横比を保持する。
- [x] ✅ A01: 公開APIだけで代表帳票を組み、本文長・表示値の変化へ追従する。
- [x] ✅ A02: 固定書体で代表PDFを画像化し、欠字・接触・切断・アンカーを目視確認する。
- [x] ✅ A03: クリーン環境のwheelからサンプル生成、Python 3.12/3.13を検証する。
- [x] ✅ A04: 数百ページの停止・欠落、参照原本不変、全テストとカバレッジ90%以上を検証する。

## 検証記録

最終カバレッジ目標は製品 `gridlayoutpdf` 全体90%以上。低リスクの依存設定・文書そのもののためだけのテストは追加しない。

- Step 1: `reference-fixtures-red` 9 failed/12 passed → `reference-fixtures-green-1` 21 passed。`font-supply-red` 3 failed → `font-supply-green-1` 3 passed。lead独立検証 `lead-step1-all` は24 passed、wrapper exit 0。
- 環境はPython3.13.11、別の `build/compat312` で3.12.12の同期・wheelインストールを確認。ReportLab5.0.1、PyMuPDF1.28.2、pytest9.1.1、pytest-cov7.1.0をlock。
- フォントはIPAex明朝004.01、face0。無改変配布原本・ライセンス・Readmeを保持。欠字も幅を返すため、cmap検査を幅計測と分ける。
- 作業中に `.claude/skills/` 群に別作業の変更が出現。担当エージェントの所有外なので保持し、この実装の変更として報告・上書きしない。現行run_tests.pyのインターフェースと24件の実行成功を確認した。
- Step 2a: leadの `lead-step2-geometry` 169 passed、`lead-step2-fonts-styles` 41 passed、統合した `lead-step2a-all` 274 passed。各担当のcoverageは幾何99%、書体/scene97%。A4横45×31、A3縦45×69。
- ReportLabは登録名と内部face名の両方で共有するため、登録時のface名もハッシュで分離する。元フォントファイルは変更しない。NFCで合成した文字を計測・描画し、残った結合マークは初期版で明示エラーとする。
- 外部コミット `cb4e08a` により一部の初期TDDログが整理された。担当のprogressに元ツール結果と現存しない範囲を記し、ログ再作成・過去Redの再演はしない。製品ファイルと現行のlead検証は正常。

## レビュー記録

Step 2aの独立レビューを実施（`core-review-step2a-baseline`: 250 passed）。High以上0、Medium2件: 実字形境界の不足、破損フォントのZeroDivisionError漏れ。font_supplyがTDDで修正し、数式・描画器も追従。leadの `lead-font-bounds-and-renderer` 56 passed、再レビュー `core-review-round2-fonts` 33 passedで両件解消、新規Medium以上0。

Step 2最終ゲート `lead-step2-all` は413 passed。`build/reports/typography-proof.pdf` と `typography-proof-grid.pdf` 各3ページ、合計6PNGをleadが目視し、欠字・接触・括弧不足を認めなかった。本文10pt・基線offset11pt・添字比率0.65を採用。上付き4は書体未収録のU+2074を使わず、通常数字をScriptで組む。

数式の独立レビュー `core-review-math-round1` は103 passed、Medium以上0。描画器の独立レビュー `review-pdf-backend-font-supply` は26 passed、Medium1件（欠字診断にpage/commandの位置が欠ける）。Step 3aの共有境界検証への移行と合わせて担当が回帰TDDで修正する。

Step 3aの共通型・共有描画境界・設定・PDF統合は `lead-step3a-common` 134 passed。leadが全実装を読み、part数による最小行数、再掲prefixを含む分割高、再分割の条件保持を確認。描画時の欠字位置の修正も通過、独立再レビューは次の枠で行う。文章・数式の担当がRedサイクル中のため、この時点の検証は対象範囲を明示し、全体成功とは扱わない。

共通型の独立レビューでMedium1件（基線offsetを引いた際の丸めで境界ぴったりでも1行余分に進む）を検出。`layout-baseline-red-1` 1 failed → Green91 passed、leadの `lead-baseline-boundary-fix` と独立 `core-review-baseline-round2` が各91 passed。実際のoffset＋整数行の境界と比較して補正し、境界直後の値は次行へ送る。新規Medium以上0。描画器の欠字位置の指摘も独立再レビューで解消確認済み。

最終段階ではPython/計画適合と、エラー処理/不変条件の独立レビューを並行し、Medium以上が0になるまで修正する。

Step 3b/4aのlead統合 `lead-text-wrap-common` は401 passed。文章・基本部品は15サイクル（text-red-10は予想外に成功しRedとはせず10bで実際の境界誤差を再現）、担当scope113 passed/99%。数式折り返しは7サイクル、既存mathと合わせ197 passed、equations 100%。独立レビューへ引き渡した。

文章は行境界のASCII空白だけを除き、内部空白と明示改行による空行を保持する。通常配置は自然幅。justifyは明示指定時だけ上限0.05emの正の字間で合わせる。独立レビューにより、どの合法境界でも指定幅へ届かない段落は最後に入る合法境界で自然幅へ戻す方針へ修正済み。単独fit_trackingの指定幅不足は明示エラーのまま。フォントサイズは変えない。英単語の保持と基本的な日本語禁則を対象とし、完全なUnicode行分割・複雑文字shapingは対象外。

Step 5a容器は3サイクル、担当191 passed/containers 100%。lead `lead-containers-common` は206 passed。Stackは通常フローで展開し、容器内部ではatomic。Columnsは高さの最大、KeepTogetherはprefixと既存条件を保持、Atは未配置の指示だけを表す。文書フローでの検証はStep 5bへ続く。

### レビュー反映 (2026-10-16, 文章・折り返し ラウンド1)

独立 `core-review-text-wrap-round1` は207 passed、Medium2件。全角＝が関係演算子の候補から漏れる点を `equation-wrap-fullwidth-red` 1 failed/94 passed → Green95 passedで修正。段落justifyの過度な幅一致要求は `text-justify-fallback-red` 5 failed/110 passed → Green115 passed/99%で修正した。厳密なfit_trackingの既存テストは保持した。lead `lead-text-wrap-review-fixes` 210 passed。独立round2は160＋50 passed、両件クローズ、新規Medium以上0。

MathBlockは他のEquationクラスから独立して完成し、lead `lead-mathblock-contract` 14 passed。表の独立計測はこれとParagraphだけに依存できる。初期の工程表から実装順だけを調整し、表・図の独立部分を先行して並行性を確保する。自動改ページとの統合・目視の合格条件は省略しない。

### レビュー反映 (2026-10-16, 容器 ラウンド1)

独立 `core-review-containers-round1` は75 passed、Medium1件（原子的Stack/Columnsで子partのアンカー等metadataが消失）。`containers-trace-red-1` 3 failed/75 passed → Green78 passed/100%で修正。子の位置・行数・prefix/bodyのローカルmetadataを不変のchildren traceへ保持した。lead `lead-containers-trace-fix` 169 passed。独立 `core-review-containers-round2` 78 passedで解消確認、新規Medium以上0。

Step 4bの数式アダプターは10サイクル、担当288 passed/99%。Step 7aの図・画像は10サイクル、関連scope162 passed/99%。並行実装中の表を除いたlead統合 `lead-step4-and-figures` は1000 passed。数式4PNG、図2PNGをleadが確認し、等号と単位の列、継続・結果行、複雑式、寸法図、画像の縦横比と透明度に問題を認めなかった。図・画像の独立レビュー `core-review-figures` 162 passed、Medium以上0。

Step 6aの表はlead `lead-table-common` 245 passed、担当table coverage99%。通常/grid各2ページ、全4PNGをleadが確認。独立した行群の閉じた枠同士が接する境界は各0.5pt、見かけ1ptの線となる規則を採用し、APIへ記載した。本文内のrowspan・分数・数値の右揃え・ヘッダー再掲を確認。Document連携はStep 5bの後続ゲートに残す。

並行coverage実行で共通の`.coverage`が競合したため、以後は担当ごとのCOVERAGE_FILEをログ配下へ指定する。最終全体coverageはleadが単独で測り、個別scopeの合算では判定しない。

### レビュー反映 (2026-10-16, 数式アダプター・表 ラウンド1)

数式の独立レビューは90 passed、Medium1件（gap=0で結果右端と単位開始が同列になる）。`equation-gap-review-red` 4 failed/91 passed → Green96 passedで、自動結果右端を単位開始より1列以上前へ置く修正。lead `lead-equation-gap-review` と独立 `core-review-equations-gap-round2` は各96 passed。実書体の168境界プローブも正常配置又は必要幅診断となり、予期しない例外0、新規Medium以上0。

表の独立 `review-table-font-supply` は76 passed、Medium1件（入れ子表の幅に列位置依存の丸めが入り、32.16ptが32.15999999999998ptとして不足扱いになる）。物理的に同じセル幅の計測と極小許容差を揃える回帰TDDを担当へ割り当てた。

表の回帰 `tables-width-review-red-1-valid` は10 failed/95 passed、Green107 passed/99%。同じspan×pitchを計測・配置・traceで使い、共通境界と同じ1e-7ptの丸め許容に揃えた。lead `lead-table-width-review` と独立 `font-table-review-round2` は各107 passed。第3列の元再現は成功、1.1e-7pt及び0.0001ptの不足は拒否、Medium以上0でクローズ。

Documentの計測・改ページと並行して、確定ScenePageだけに依存する配置トレースをdiagnostics.pyへ分離した。reference_fixturesがtraceと公開exportsを担当する。bootstrapはページ装飾・PDF統合・改ページ実証に集中する。APIとarchitectureの文書は独立レビュー後に実サンプルで確認する。

配置トレースと公開exportsは `lead-public-and-trace` 15 passed。担当 `diagnostics-final` は関連61 passed、diagnostics coverage96%。低水準ScenePageを直接扱い、ローカルmetadataを保ってJSONへ変換する。画像bytesはhashと長さに置き換える。

文書基本機能は `lead-document-basic` 64 passed、担当統合69 passed/coverage100%。通常/grid各5ページ（A4×3→A3→A4）の全10PNGをleadが確認し、本文行01〜96・見出し・数式・表・図・画像・番号に欠落や切断を認めなかった。API/architectureの独立文書レビューはMedium以上0、Low2件（numeric_columnsの単列条件、任意profileのピッチ）を反映済み。

### レビュー反映 (2026-10-16, Document ラウンド1)

独立レビューでMedium2件を検出し、bootstrapが別サイクルで修正中。フッターが紙の下端へ正確に収まる場合の減算丸めによる誤拒否、及び空文字・空白だけのTextを見出しに続く可視本文と扱ってしまう点。後者の可視内容規則はpagination-contractに明記し、Documentと容器で共通化する。修正後にlead対象ゲートと独立再レビューを行う。

画像の読込み・検証でPillowを直接利用するため、ReportLab経由で導入されていたPillow>=9.0.0を実行依存に明示した。ロック済み版12.3.0は変わらず、uv lock --checkは成功。

Documentの2件は `lead-document-review-fixes` と独立 `core-document-review-round2` 各268 passedで解消。追加の空行開始段落プローブで、同居するfragment自体が空白のみになるMediumを検出した。`document-visible-fragment-red` 7 failed → Green96 passedで、可視内容を含む最小の合法fragmentを予約する修正。lead `lead-document-visible-fragment` 104 passed、独立round3を実施中。

公開APIのREADME/APIガイド全8コード例をleadが実行し、3PDFを独立抽出・全3PNG目視した。数式・変数説明・結合表・図・画像を組み合わせても境界検証を通過した。

最終統合レビュー `final-integration-review-stable-1` は582 passed。既存の個別レビューと異なる入れ子構成でMedium1件（Columnsの幅ガードだけが1e-7pt許容を持たず、9列セル−左右1列paddingと7列Columnsの一致を誤拒否）を検出。reference_fixturesがcontainers.py限定で回帰TDD修正中。他の新規Medium以上0。

代表帳票の初期lead `lead-representative` は10 passed。標準5ページとlong6ページの通常/grid全22PNGをleadが確認し、`.claude/logs/lead-visual-approval.json` に画像hashと目視の承認を記録。標準版5ページを回帰画像の基準とする。例の外部表示値mapping入力を追加後、最終独立レビューへ進む。

長文性能は1段落14,100行を300ページへ自動配置し、独立PDF抽出で全行IDの順序・個数とページ番号を検証。Python3.13.11でtracemalloc無し31.251秒（書体0.112/配置27.472/描画3.667）、計測あり203.285秒・Python割当peak37.877MiB。RSSではなく、入力行リスト作成とPDF抽出を計測外とした。結果と条件はdocs/validation.mdに記録した。

### 最終受入 (2026-10-16)

Documentの空行開始fragment修正は独立 `core-document-review-round3` 104 passed、Medium以上0でクローズ。見出しの直後に空白があっても、可視本文を含み最小先頭・末尾行数を満たす合法fragmentを同居させる。

最終統合のColumns幅境界は `final-columns-width-red-1-valid` 6 failed / 89 passed → `final-columns-width-green-1` 300 passedで修正。幅ガードを共通の1e-7pt許容に揃え、lead `lead-final-columns-width` と独立 `core-columns-final-round2` が各208 passed。通常の幅不足は引き続き拒否し、Medium以上0でクローズした。

代表例に6種類の外部表示値mappingを追加し、文字列をコピーして丸めず保持する。`lead-representative-final` と独立 `final-example-review-scope-1` は各17 passed。最終例を再出力した全22PNGのhashはlead承認時から不変だった。レビュー記録は `.claude/logs/final-example-review-report.md`。

画像回帰は `visual-golden-red` 1 failed / 2 passed → Green3 passed。承認済みの標準通常5PNGをhash照合して固定し、実際の再出力とdecoded RGB画素を比較する。1画素破壊の検出と圧縮差の許容も検証した。独立レビュー `.claude/logs/final-golden-review.md` は全指摘0。基準を自動更新する機能は持たない。

lead単独の最終全件ゲート `lead-final-all` は **1269 passed in 59.22s**、製品全体の行カバレッジ **98.82%（2540行中2510行、pytest表示99%）**。共有wrapperは期待成功・実測成功・exit0・90%以上を確認した。原本12PDFの不変検証と画像回帰もこの全件に含む。検証後に製品・テストは変更していない。

最終READMEを含む `uv build` のsdist→wheel作成と、Python3.12.12／3.13.11の独立環境への再インストールを確認。リポジトリ外から `python -I` で公開例を実行し、PyMuPDFなしで通常/grid/JSONを生成した。両環境とも標準全5ページのMediaBox・本文・画素が承認出力と一致。配布物は製品20モジュールと情報のみで、フォント・画像・参照PDF・テスト・agentsを含まない。結果は `build/reports/wheel-acceptance.json`。

全11要件の検証対応表・再実行手順・制約は `docs/validation.md`、利用法は `docs/api.md`、責務と拡張契約は `docs/architecture.md` に整理した。参照PDFの全251ページ移植、P7改修、PyPI公開は承認計画の範囲外として実施していない。

DESIGNとSTATEは型付きJSON→preview確認→applyで更新済み。最終 `.claude/check.ps1` はstack/design/stateともexit0・ok=true、plan-doc契約、`uv lock --check`、今回の対象ファイルの`git diff --check`も成功。DESIGN検証器はArchitecture直下が子見出しで始まるためempty-body警告を出すが、実際の本文と確定構成は同セクションに存在する。これは製品ゲートとは別の文書構造チェックで、合否は成功。計画の全チェック項目を完了にした。
