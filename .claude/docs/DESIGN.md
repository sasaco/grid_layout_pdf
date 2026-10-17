# GridLayoutPdf — Design

## 背景・目的 (Background & Purpose)

Python の自作 PDF 計算書ライブラリを設計する。A4.pdf の GridLayout に従って文字配置を調整し、計算書の書式と計算式の等号位置を統一する。

## スコープ (Scope)

今回の成果物は資料調査と実装計画。対象資料は `.claude/docs/research/A4.pdf` と `tests/output/*.pdf`。ライブラリ実装と既存 P7 アプリへの移行は後続作業。

数式の初期入力形式は構造化したPython部品とする。TeX文字列パーサーは初期版の必須機能に含めない。

初期版の用紙設定はA4縦を標準とし、A3・横向き・同一PDF内の混在を含める（FR-011）。外部PDFページの読み込み・合成の要否はこの回答だけからは追加せず、実装計画で境界を明示する。

2026-10-16 更新：ユーザーが plans/grid-aligned-calculation-reports.md の実装開始を承認した。以後の作業は同計画の全8工程と検証・修正を含む。既存P7アプリの移行は含めない。進捗と担当は plans/grid-aligned-calculation-reports-execution.md に記録する。

2026-10-16 最終更新：ユーザー承認済みのPythonライブラリ初期版と全8工程の受入を完了した。製品はsrc/gridlayoutpdf、公開例はexamples/representative_report.py、利用・設計・検証ガイドはdocs/。P7移行、構造計算ソルバー、GUI、TeXパーサー、外部PDF取込み、PyPI公開は範囲外のまま。初期調査・計画のみとした冒頭は履歴であり、現状は実装済み。

2026-10-17 追加依頼：tests/output/13_片持ち梁照査.pdfの物理ページ1〜37を対象とする再現テストを作成する。全対象ページの見出し・本文・数式・表・図と原稿・検証の対応を保持する。表示値は原本の文字列を保持し、判読不能な箇所や原本の不明値は推測で補わない。ソルバー・P7移行・GUI・TeXパーサー・PyPI公開・原本PDFの変更は対象外。最新のgrill-with-docs/plan指定により調査・具体的な計画を先行する。初期ライブラリの完了と今回の37ページ再現テストの完了は区別する。

2026-10-17 grill第2問による上書き：今回の片持ち梁再現は固定ページ再現とする。原本p1〜37の内容をそれぞれ1ページに収め、合計37ページを必須とし、あふれた場合は『原本再現できず』のエラーで停止する。右上ページ番号は全ページ不要。A4縦とp30〜37の反時計回り90度回転表を保持し、表の18/13ケースの区切りも維持する。原本との対応は検証用台帳に保存する。これは今回の再現条件の追加であり、既存ライブラリの自動改ページや他の帳票の受入条件を変更しない。FR-008の座標完全一致不要・文字サイズ保持は引き続き適用しつつ、今回のページ割りにはFR-014を優先する。

2026-10-17 更新：ユーザーがcantilever-pages-01-37計画の実装開始を承認。固定37頁・頁番号不要・回転表原本ままというFR-014を優先して実装・検証する。不足機能・改善候補はresearch/cantilever-p01-37-improvements.mdに根拠、今回の対応、検証状況を継続記録する。

2026-10-17 P7移行の新規依頼: K:/ニュージャパンコンサルタンツ/26_LRT鉄道照査/P7橋脚/pier_designのPDF生成を6帳票すべてGridLayoutPdfへ移行する計画を策定する。計算ロジック・入力画面・入出力仕様の維持、Example橋脚/outputの体裁だけを参照、全6帳票の可変ページ数をgrillで確認済み。これまでのP7移行範囲外という記録は初期ライブラリ/片持ち梁作業の境界として残し、今回の独立した依頼にはFR-016/017を適用する。計画slugはpier-report-grid-migration。具体的計画の作成・レビュー・提示は継続中。

2026-10-17 P7移行実装承認: 計画pier-report-grid-migrationの形式・存在・内容レビューPASS提示後、ユーザーがOK GOで全10工程の実装を承認した。計算/UI/I/O維持、全6PDFのGridLayoutPdf移行、全6帳票可変頁、見本書式と白黒化を実装・検証する。進捗はplans/pier-report-grid-migration-execution.md。先行する計画作成中・承認待ち記録は履歴となる。

## 機能要件 (Functional Requirements)

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| FR-001 | A4.pdf の GridLayout に基づく文字位置調整 | Must | ユーザー指定 |
| FR-002 | 複数行の計算式の等号位置を揃える | Must | ユーザー指定 |
| FR-003 | 余白・フォント・改ページを共通コンポーネントで扱う | Must | 会話で確認した目的 |
| FR-004 | 初期版は Python コードから文章・表・計算式を組み立てるライブラリ | Must | 2026-10-16 ユーザー回答。GUI 帳票デザイナは初期版に含めない。 |
| FR-005 | 文字サイズを保ち、開始位置・字送り・行位置をグリッドに合わせる | Must | 2026-10-16 ユーザー回答。自動縮小・字形の横方向伸縮を基本動作にしない。 |
| FR-006 | グリッドの1マスは文章・式・表を配置する単位とし、文字数と独立させる | Must | 2026-10-16 grill-with-docs 第1問で選択肢1をユーザーが選択。文章は複数マスにまたがり、等号は指定列に揃えられる。 |
| FR-007 | 上から自動配置し、必要な箇所のみ位置指定する方式を基本候補とする | Must | 2026-10-16 ユーザーは選択肢1を支持し、tests/output/*.pdf の体裁を実現できるか確認した。参考体裁の表現能力を検証して採用を確定する。 |
| FR-008 | A4グリッド上で見本と同等の表現・読みやすさへ体裁を統一する | Must | 2026-10-16 ユーザーが再現基準の選択肢1を選択。等号揃え・数式・表の構成を再現し、余白・ページ割りは新規則に合わせる。元PDFの文字座標・改ページの完全一致は合格条件にしない。 |
| FR-009 | 計算式をPythonの数式部品の組み合わせで記述できる | Must | 2026-10-16 ユーザーが選択肢1を選択。Equation(lhs=..., rhs=Fraction(...)) は概念例であり、最終API名・引数は実装計画で定義する。 |
| FR-010 | 幅を超える数式は適切な区切りで自動折り返しし、明示改行も指定できる | Must | 2026-10-16 ユーザーが選択肢1を選択。分数・根号の内部を分断せず、継続行・等号の配置を揃える。分割できず収まらない場合は自動縮小せずエラーとする。 |
| FR-011 | A4縦を標準に、A3・横向きのページと同一PDF内の用紙混在に対応する | Must | 2026-10-16 ユーザーが選択肢1を選択。ページごとに用紙とグリッドを設定する。大きな表・図の横向きページへの配置を扱う。 |
| FR-012 | 片持ち梁照査の原本PDFの物理ページ1〜37を、公開APIで構成した原稿と独立した内容・体裁検証で網羅する | Must | 2026-10-17の引継ぎ実装依頼。FR-008の体裁統一を維持し、出力37ページ固定を意味しない。原本画像の全面貼付・PDFページコピー・ソルバー追加は行わない。計画はplans/cantilever-pages-01-37.mdへ作成中。 |
| FR-013 | 片持ち梁照査p30〜37の大表は、原本どおりA4縦の紙面内で90度回転した配置を保つ | Must | 2026-10-17 grill-with-docsでA3横正規化またはA4分割を提示したところ、ユーザーは『原本まま』と回答。文字・数式・表の画像化で対応せず、元の読み順・表構造と独立したページ番号を保持する。この回答は大表の扱いへの指定であり、全37ページの原本座標・改ページ完全一致という新要件には拡張しない。 |
| FR-014 | 片持ち梁p1〜37は原本ページと出力ページを1対1に固定し、あふれをエラーとして停止する。右上ページ番号は全ページで省く | Must | 2026-10-17 grill第2問でユーザーが『出力ページが増えたらエラー（原本再現できず）として止まってください。右上のページ番号は全ページ不要』と指定。今回の再現テストに限り、FR-012の注記『出力37ページ固定を意味しない』とFR-013の頁番号保持を上書きする。全37ページ・各原本ページの内容境界を保持し、欠落による頁数減少も成功にしない。既存ライブラリ一般の自動改ページ機能は維持する。 |
| FR-015 | 片持ち梁p1〜37の再現では、原本の書体、階層別インデント、等号の紙面内位置、表の行高を保持する | Must | 2026-10-17 ユーザーが生成版のfont・indent・equals位置・table row heightの相違を指摘。今回の再現fixtureについて、従来のIPAex/標準グリッドへの体裁統一をこれらの項目へ適用しない。全37頁固定・頁番号省略・あふれ時停止・native本文/数式/表を継続する。原本と生成物の直接比較で検証し、生成物同士のgolden一致だけでは受入しない。 |
| FR-016 | P7橋脚アプリのPDF生成部分を6帳票すべてGridLayoutPdfへ移行し、既存計算・入力画面・入出力仕様を維持する | Must | 2026-10-17 grill第1問にユーザーがyesと回答。対象は0500/0600/0610/0620/0710/0720と、それらが用いる本文・数式・表・図の生成。Example橋脚/outputの4PDFは体裁見本であり計算仕様・期待数値へ置き換えない。 |
| FR-017 | P7の全6帳票は見本の書体・字下げ・等号揃え・表行高を踏襲し、内容に応じたページ数の増減を許す | Must | 2026-10-17 grill第2問でユーザーが全6帳票の増減を選択。既存0710=3頁/0720=4頁固定も今回の移行では解除し、計算式や表のまとまりを保持して改ページする。原本69頁への固定や、片持ち梁fixtureの37頁固定・全頁番号省略をP7へ転用しない。 |
| FR-018 | P7移行後の本文・数値・表を白黒に統一する | Must | 2026-10-17 grill第3問でユーザーが白黒統一を選択。見本の赤/青数値は黒、黄色表見出しは白地に変更し、書体・字下げ・等号揃え・表構造を保持する。今回のためのカラー文字/背景API拡張は不要。 |

## 非機能要件 (Non-Functional Requirements)

| Category | Requirement | Metric / Target |
|---|---|---|
| 保守性 | 余白・フォント・改ページ処理を共通部品として再利用し、帳票ごとの重複定義を減らす。 | 定量的な評価基準は未設定。 |
| 責務の分離 | 構造計算と帳票のレイアウト・描画を分離する。 | `.claude/rules/project-scope.md` の方針。具体的な構成は設計時に定める。 |

## アーキテクチャ (Architecture)

### Agent Roles

| Agent | Role | Responsibilities |
|---|---|---|
| Codex | Main Agent | ユーザーとの作業調整、共有コンテキストの維持、依頼された作業の実行と検証。 |

検討案（未実装）：文章・数式・表・図を部品単位で上から配置し、部品の開始位置と占有行数を配置グリッドへ合わせる。部品内には等号列・結果列・単位列、数式の基線、分数・添字の局所配置を持たせる。自動配置の採用は、参照にある代表的な構成を表現できることを検証条件とする。

2026-10-16 実装計画案を [plans/grid-aligned-calculation-reports.md](plans/grid-aligned-calculation-reports.md) に作成。部品ツリー → 計測 → グリッド・アンカー配置と改ページ → 確定した描画命令 → PDF の責務分離を提案する。数式内部の分数・根号・添字は局所pt座標で組み、数式全体の位置・占有行数と等号列をグリッドへ合わせる。本文は自動フロー、横並びは宣言した容器、明示位置はフローカーソル以降の予約枠で扱う。これらは計画提案であり、製品実装済み・ユーザー承認済みを意味しない。

2026-10-16 実装確定：文書部品→measureによる不変のMeasuredBlock/LayoutPart→Documentの整数行フロー・分割→ScenePage→ReportLabの一時PDF/原子的置換。数式内部はpt、外側の占有高と等号等のアンカーはグリッド。containers.pyは容器、document.pyは改ページ・用紙混在・装飾、diagnostics.pyは確定ページの配置JSON。Tableの列は整数tupleとしColumnSpecを増やさない。公開API/拡張契約はリポジトリ直下docs/api.mdとdocs/architecture.md。

## 技術選定 (Tech Stack & Rationale)

| Area | Technology | Rationale | Alternatives Considered |
|---|---|---|---|
| 帳票部品 | Pythonによる自作ライブラリ（設計段階） | 既存のKey DecisionsとFR-001〜003に基づき、A4グリッド、等号位置、共通レイアウトを扱う。 | 既存のKey Decisionsに記載。 |
| 描画バックエンド | 未選定 | 帳票部品を自作する決定と、描画など下位機能のライブラリ選定を区別する。 | 資料調査・実装計画で比較する。 |
| 共有スクリプトの実行 | uv run --no-project python | 初期化時点で製品のmanifestがなく、同コマンドで共有スクリプトを実行できた。 | FrameWeb指定のコマンドは、このリポジトリの構成に一致しない。 |
| 現在の作業環境 | Windows / PowerShell | ユーザーから提示された作業環境。製品の対応OSを決めるものではない。 | 製品の対応OSは未決定。 |
| 描画バックエンド（計画案） | ReportLab Canvasを第一候補、PyMuPDFは開発検証用 | 独自のグリッド計測・配置・改ページを中核に保ち、低水準PDF描画を委ねる。日本語書体・数式記号・混在ページをStep 2で実証してから採用を確定する。 | Platypusのフローを主構造にする方式、PDF生成まで全自作する方式。 |
| 初期版の確定構成（2026-10-16） | Python>=3.12、ReportLab/Pillow、Hatchling/uv。WindowsでPython3.12.12と3.13.11を確認 | 低水準PDFはReportLab、画像はPillow、独自部分は計測・グリッド配置・改ページ。PyMuPDF/pytest/pytest-covは開発のみ。uv.lockに固定。wheelは20モジュールとパッケージ情報のみ、書体や資料は含めない。 | 未選定だった計画段階の記述を本行で更新する。他OSは未検証。 |

## 制約 (Constraints)

参照 PDF は読み取り専用で保持する。グリッド寸法は PDF から検証し、確認済み事実と提案値を区別する。

2026-10-16 の初期化時点で、製品コード、依存関係のmanifest、ロックファイル、製品の実行・テストコマンドは未作成。共有スキルに残る FrameWeb 等の別プロジェクト用の設定は、GridLayoutPdf の採用技術の証拠としない。

`.claude/check.ps1` はスタック検出とDESIGN・STATEの文書契約を検証する。製品の機能や参照PDFの再現性は、別途検証する。

## Key Decisions

| Decision | Rationale | Alternatives Considered | Date |
|---|---|---|---|
| Custom Python component library | ユーザーが自作を選択し、A4 グリッドへの文字配置調整を独自性として指定した。 | ReportLab Platypus, ReportBro, borb, fpdf2, WeasyPrint を調査済み。描画など下位機能のライブラリ利用は未決定。 | 2026-10-16 |
| Python library first | ユーザーが初期版の利用形態として選択。 | GUI 帳票デザイナを初期版から含める。 | 2026-10-16 |
| Preserve font size during grid adjustment | ユーザーが文字サイズ保持と開始位置・字送り・行位置の調整を選択。 | 枠に収まるよう文字サイズや字形の横幅を自動変更する。 | 2026-10-16 |
| Grid cells represent placement units | ユーザーは文章・式・表の配置単位を選択。文字送りを全角1マス・半角半マスに固定しない。 | 原稿用紙のように1マスを文字送りの単位とする。 | 2026-10-16 |
| Use grid-normalized appearance as acceptance criterion | ユーザーはA4グリッド上で見本と同等の表現・読みやすさへ統一する基準を選択。内容量に応じた自動配置・改ページと両立させる。 | 元PDFの文字位置・余白・改ページまで一致させる。 | 2026-10-16 |
| Author equations with structured Python components | ユーザーがPython部品を組み合わせる方式を選択。等号・分数・添字を個別に計測・配置できる構造を採る。 | TeX風の文字列を初期版の主要入力形式にする。 | 2026-10-16 |
| Wrap equations at valid structural boundaries | ユーザーが自動折り返し＋明示改行を選択。可変長の式を文字サイズを保って表示する。 | 呼び出し側が全改行位置を指定し、未指定の幅超過を即時エラーとする。 | 2026-10-16 |
| Support mixed page and grid profiles in the first release | ユーザーがA4縦標準＋A3・横向き・混在対応を選択。参考PDFにはA3横のページがある。 | 初期版をA4縦に限定する。 | 2026-10-16 |
| Implement the approved plan with TDD and parallel ownership | 2026-10-16 ユーザーが『ok $tdd $parallel-agent-dev』と回答し、計画全体の実装開始を承認した。依存関係のないモジュールを分担し、Red-Green-Refactorとleadによる検証を行う。 | 計画段階に留める。 | 2026-10-16 |
| Prepare local package installation before PyPI publication | 2026-10-16 ユーザーが将来のPyPI公開を前提に、まずローカルでuv pip installできる状態を依頼した。既存のHatchlingとsrcレイアウトを維持し、通常・編集可能インストール、README、wheel/sdistを検証する。 | 今回からPyPI公開や公開用ワークフローを整備する。 | 2026-10-16 |
| Adopt ReportLab after measured typography proof | Step 2の全体テスト413件とA4/A3/A4の通常・検査PDF全6PNG目視により、日本語・2等号列・段分数・分数指数・根号・括弧を確認。本文10pt、基線offset11pt、添字比率0.65を初期値として採用する。文字は縮小せず、送り幅と実字形境界を別に計測する。 | 書体または描画バックエンドを再選定する。 | 2026-10-16 |
| Complete the approved component library and retain measured visual baselines | 全8工程をTDDとファイル所有による並行実装で完了。1269 passed、製品行coverage98.82%、独立レビューMedium以上0。標準5頁・長文6頁の通常/grid全22画像を目視し、標準通常5頁を固定書体・ツール・入力hash付きの画像回帰基準にした。等号列、構造化数式、文章、結合表、図画像、用紙混在を公開APIで構成できる。 | 元PDF全251頁の完全複製を受入基準にする、個別Canvas座標を利用側へ公開する、幅不足を自動縮小で隠す。 | 2026-10-16 |
| Require a visible legal body fragment after headings | Documentと容器で可視内容の判定を共通化し、空白Textや空行だけのfragmentでは見出しの孤立防止を満たした扱いにしない。段落の最小先頭・末尾行数と既存の分割条件を満たす、可視本文を含むfragmentを予約する。独立レビューで見つけた境界を回帰TDDで修正・再確認済み。 | 非空の描画命令一覧だけで可視本文と判定する。 | 2026-10-16 |
| Preserve portrait A4 sheets with rotated combination tables for cantilever pages 30–37 | ユーザーの『原本まま』指定により、大表の紙面方向と回転配置を維持する。既存APIに回転表がないため、公開APIから構造を持つ表を回転配置する最小拡張の実証を計画に含める。 | 大表をA3横の通常横書きへ正規化する、A4の複数パネルへ分割する。 | 2026-10-17 |
| Require fixed one-to-one source pages and omit page-number decorations for this reproduction | 最新のユーザー指定により全37原本ページを各1出力ページで再現し、内容の他ページへの送りを失敗として扱う。右上の頁番号は生成しない。 | 自動改ページを許して連番を振る、原本番号と枝番を振る。 | 2026-10-17 |
| Add explicit per-boundary table stroke widths for sparse source tables | 原本p26の6表で、全セル罫線では表現できない上下太線・選択された細線を確認した。Tableに水平/垂直境界ごとの非負線幅tupleを追加し、0は非描画、Noneは従来出力を維持する。既存の結合・行群・分割契約に従い、線幅は各ストロークの幅とする。fixture側で描画命令を削除して回避しない。 | 表の画像化、全罫線への置換、汎用描画変換や全Tableの分割方式の再設計。 | 2026-10-17 |
| Accept the fixed 37-page native reproduction with independent content and visual regression gates | ユーザー指定の原本1頁=出力1頁・全頁番号省略・A4縦内CCW90表を全37頁で実証。公開Text.quarter_turns/QuarterTurn/Table境界線幅を追加し、本文/式/表はnative、16図のみ出典付き原寸画像とした。全3345項目と原本21232文字の照合、74画像目視、37golden、1508 passed/行coverage98.80%、独立レビュー未解決0、Python3.12/3.13 wheel受入で確認。検証器は最適化Pythonを明示拒否し、全検査済みの不変bundleだけをcurrentへ切り替える。 | 表や式の画像化、A3横への変更、追加頁や自動縮小による収容、原本の不整合値の推測修正、生成直後のgolden自動承認。 | 2026-10-17 |
| Reopen cantilever appearance acceptance after user comparison | 前回の1508件合格と74画像確認は内容・自己回帰の証拠であり、原本との書体・インデント・等号座標・行高一致を保証できていなかった。原本のMS明朝/MSゴシックと意味部品ごとの実測配置を採用し、独立した原本比較を追加する。旧currentは修正版の検証完了まで保持し、承認済みの修正作業として継続する。 | IPAexのまま許容する、既存goldenだけを更新する、本文や表を原本画像へ置換する。 | 2026-10-17 |
| Keep exact row heights and synthetic italic explicit and opt-in | 原本p1/p21の行高と人工斜体Dを復元するため、Table.row_heightsを正の局所整数行数、Text.shear_xを有限の横傾斜係数として追加する。既定None/0は既存表示を保持する。指定行高不足はLayoutOverflowError、傾斜の字送りは維持しbounds・回転・PDF文字行列・traceを整合させる。実PDFの原本比較、負例、配布環境の検証を伴う。 | 文字の縮小、描画後の画像化、fixture限定の私的renderer操作。 | 2026-10-17 |
| Preserve source whitespace and compare actual ink for vertical punctuation | 原本の非空白文字一致と抽出bbox一致だけでは数式内の有意空白欠落とIdentity-V括弧の描画位置差を見逃した。意味行の空白と式のASTを両立させ、縦括弧は実描画のinkを原本と比較する。文字ごとの座標再生や式画像は使わない。 | 非空白inventoryだけで合格、自己goldenだけで合格、元PDFページを再利用。 | 2026-10-17 |
| Compare native glyph positions in both axes and keep table ink measurement local | 外観再レビューで横位置だけの比較では上付きや意味runの縦ずれを見逃した。原本の基線差を意味ASTに保持し、進行方向と直交方向を独立に検査する。狭い原本表はfixture専用の実glyph ink計測で配置し、元FontRegistryと製品の保守的boundsは変更しない。原本罫線に接触する明示8セルのみ最大0.05ptの補正を許し、実inkと下辺余裕を検証する。全37頁で直交基線21204字、最大差0.043419pt、縦ずれ負例も合格。 | 全基線の許容を広げる、font boxを理由に本文全体を一律移動する、基準画像の自己一致だけで合格する。 | 2026-10-17 |
| Implement explicit cell, image and script layout options while preserving the accepted source appearance | 2026-10-17ユーザーがcantilever-p01-37-improvementsの全8工程を承認。Insetsによる四辺余白と診断、CellLinesのpt内側配置後の一度の行丸め、Imageの物理寸法、Scriptの明示scale/基線offset、Tableの不可分モードをopt-inとして追加する。既定の計測・分割・描画を維持し、FR-015のSourceCell/SourceScript固有アンカーと局所ink測定は等価な範囲のみ共通化する。 | 全Blockの予約行規則を変更する、原本アンカーを汎用APIへ強制置換する、任意の分割表の罫線方式まで再設計する。 | 2026-10-17 |
| Gate cantilever bundles on independent source glyph order as well as inventory and appearance | 同じセル内の数字順序交換はCounter一致だけでは検出できない。原本37頁の方向・基線・添字役割から独立した順序を確認し、prepare/activate双方で有効化を阻止する。既存の一回被覆・文字集合・generated-to-expected・原本外観比較は維持する。 | expectedをbuilderから再生成する、画素goldenまたは文字集合の一致だけを内容の根拠にする。 | 2026-10-17 |
| Migrate all six P7 PDF report generators while preserving calculations and application interfaces | ユーザーがPDF生成部分すべての移行を確定。既存計算結果・表示値の意味・入力UI・CLI/GUIの操作・成果物一式の公開仕様を保ち、Example橋脚/outputの体裁を現在の計算内容へ適用する。 | 入力画面や計算処理も再設計する、4見本に対応する帳票だけを移行する、見本の数値・ケースへ現計算を戻す。 | 2026-10-17 |
| Allow all P7 report page counts to vary while preserving reference typography and semantic groups | ユーザーが全6帳票のページ増減を選択。固定頁へ収めるための文字縮小を避け、見本の書体・字下げ・等号・表の行高と現在の全計算内容を両立する。0710/0720の旧固定頁条件を今回の移行について上書きする。 | 0710=3頁/0720=4頁だけを維持する、全6帳票の旧ページ割りを維持する、見本のページ数へ固定する。 | 2026-10-17 |
| Use monochrome text, values and tables in migrated P7 reports | ユーザーは見本の色分け維持という提案に対して、本文・数値・表の白黒統一を選択した。色差を意図した変更として書式検査へ反映し、値や意味的な項目区分は保持する。 | 見本の赤/青数値と黄色表見出しを維持する。 | 2026-10-17 |
| Use a measured 0.12 pt grid and explicit reference font roles for P7 report flow | 原本の14.28/14.88/23.04/12.84pt行高、14.52pt字下げ、章位置を同一Gridで表現できた。公開APIによる長表2頁・rowspan・反復header・構造化式・通常/overlayの先行実証をrootが68testsと全8画像で確認。本文MS明朝9.9、見出しMSゴシック9.9、添字6.5を基本とし、0500の一軸圧縮強度見出しのみ原本実測8.9を役割として保持する。固定頁へ収める縮小は行わない。 | 既定の粗い行へ表各行を丸める、文字縮小、P7固有機能を汎用ライブラリへ追加する。 | 2026-10-17 |
| Treat P7 equation anchors as relation text origins and translate them to public center anchors | 見本の等号座標はglyph左端、EquationAnchorsは中心であり単純転用では約2.5ptずれた。共通層は各式の実font/relation幅の半分を加え、0.12pt Gridの最寄り中心へ変換する。原本5役割と実PDFの差は0.045pt以下で、中心を誤って左端として扱う負例を検出。添字は原本実測の上付き4.92pt/下付き1.92ptを明示する。 | 中心/左端の意味を混同する、許容差を拡大する、式ごとに手作業の座標補正を散在させる。 | 2026-10-17 |
| Report the short axis in table clearance diagnostics | 2026-10-17のレビュー指摘を承認して修正。罫線に接触した内容のneeded/availableを不足している軸の値にし、メッセージへ(horizontal)/(vertical)を付けた。CellLinesの既存表記に合わせ、利用者が変更すべき寸法と数値を一致させる。 | 常に横方向の幅と余地を報告する従来形式を維持する。 | 2026-10-17 |
| Keep one validation and metadata module for every boundary | 2026-10-17のレビュー指摘を承認して修正。許容誤差1e-7、整数・識別子検証、グリッド丸め、metadataの凍結とJSON化を validation.py と metadata.py に集約し、計測引数・子部品計測・部品traceの重複を layout.py の共通関数へ寄せた。丸めは whole_units_ceil / whole_units_in の2関数に統一し、同値を数値で確認した。 | 各モジュールが独自の検証と丸めを持つ従来構成を維持する。 | 2026-10-17 |

## TODO / Open Questions

- GridLayout の正確な寸法、文字基線、余白を資料で確認する。
- 描画バックエンド、初期 API、検証条件は計画内で提案する。

- 実装開始時に、対応OS・Pythonバージョン、依存定義と製品の検証コマンドを整える。

- grill-with-docs の対話で、グリッド1マスと文字の関係を最初に確定する。A4.pdf は文字を含まないため、この意味は実測から推定しない。

2026-10-16 解決済み：上記の『グリッド1マスと文字の関係』は、FR-006 と用語集 CONTEXT.md の『配置グリッド』で確定。1マスは部品の配置単位であり、文字数とは独立する。A4 の実測寸法・余白は research/grid-reference-findings.md に記録済み。文字基線は未決定。

2026-10-16 追加調査：research/sample-report-findings.md に10 PDF・251ページの構造調査と14ページの目視結果を記録。08_線路 p2 の列揃え、13_片持ち梁照査 p54 の段分数・添字・複数段導出、12_フーチング p1 の結合セル表を初期の再現検証候補とする。元PDFは文字送り・行間がA4グリッドと異なるため、受入基準を『元の座標・改ページまで一致』とするか『A4グリッドで同等の体裁へ統一』とするかは次の対話で確認する。

2026-10-16 解決済み：上記の参照PDF再現基準はFR-008で確定。元PDFの座標・ページ割りの完全一致を求めず、A4グリッドに基づく体裁統一を合格基準とする。上から自動配置＋必要箇所のみ位置指定を計画の基本方針とし、代表構成の出力検証は実装の受入工程として残す。

2026-10-16 解決済み：数式の入力形式はFR-009のPython部品方式。次に、幅を超える式の折り返し方針を確認する。

2026-10-16 解決済み：数式の幅超過はFR-010の自動折り返し＋明示改行で扱う。分割できない式の幅超過はエラーとし、自動縮小しない。具体的な分割候補・優先順位・継続行配置は実装計画で定義する。

2026-10-16 現時点の整理：FR-001〜011の主要方針は対話で確認済み。A4/A3のグリッド寸法は research/grid-reference-findings.md に実測済み。A3横はA4縦と同じ原点・ピッチ・47行で、30列から67列へ広がる。未確定事項は計画書のOpen Questionsへ集約した。標準書体・基線・字間の値、描画バックエンドの実用性はStep 1〜2の実証ゲートで確定し、不成立なら後続工程へ進まない。工程は環境整備、最小PDF実証、文字組、数式、改ページと用紙混在、表、図と代表帳票、受入検証の8段階。元PDFの完全複製・全251ページの移植を合格条件にはしない。製品コードは未実装で、計画提示後に実装開始の承認を得る。

2026-10-16 実装進捗：承認済み8工程のStep 1〜2を完了。上記の書体・基線・描画バックエンドは実証により確定した。製品は実装中であり、文章・数式の折り返し、自動改ページ、結合表、図、代表帳票、最終受入は継続する。正本の進捗は plans/grid-aligned-calculation-reports-execution.md、共通型の契約は plans/gridlayoutpdf-flow-draft.md。新しい実字形境界と破損フォント診断は独立再レビュー済み、数式の独立レビューもMedium以上0。

2026-10-16 最終受入：上記の実装中・承認待ち・未実装という記録は解消済み。グリッド寸法、書体、本文10pt/基線11pt/添字比0.65/追加字間上限0.05em、描画器、API、改ページと用紙混在、表、図、代表例、画像回帰を確定した。全11要件と検証はリポジトリ直下docs/validation.md、経緯はplans/grid-aligned-calculation-reports-execution.md。lead最終全件1269 passed/coverage98.82%、原本12PDF不変、独立レビューMedium以上0、Python3.12/3.13のwheel実行成功。300頁14,100行は31.251秒、別メモリ計測でPython割当peak37.877MiB、全行・頁番号を独立抽出で確認。計画内の未解決事項はない。新たな表現や既存アプリ移行は別依頼の範囲で扱う。
