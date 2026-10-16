# GridLayoutPdf — Design

## 背景・目的 (Background & Purpose)

Python の自作 PDF 計算書ライブラリを設計する。A4.pdf の GridLayout に従って文字配置を調整し、計算書の書式と計算式の等号位置を統一する。

## スコープ (Scope)

今回の成果物は資料調査と実装計画。対象資料は `.agents/docs/research/A4.pdf` と `tests/output/*.pdf`。ライブラリ実装と既存 P7 アプリへの移行は後続作業。

数式の初期入力形式は構造化したPython部品とする。TeX文字列パーサーは初期版の必須機能に含めない。

初期版の用紙設定はA4縦を標準とし、A3・横向き・同一PDF内の混在を含める（FR-011）。外部PDFページの読み込み・合成の要否はこの回答だけからは追加せず、実装計画で境界を明示する。

2026-10-16 更新：ユーザーが plans/grid-aligned-calculation-reports.md の実装開始を承認した。以後の作業は同計画の全8工程と検証・修正を含む。既存P7アプリの移行は含めない。進捗と担当は plans/grid-aligned-calculation-reports-execution.md に記録する。

2026-10-16 最終更新：ユーザー承認済みのPythonライブラリ初期版と全8工程の受入を完了した。製品はsrc/gridlayoutpdf、公開例はexamples/representative_report.py、利用・設計・検証ガイドはdocs/。P7移行、構造計算ソルバー、GUI、TeXパーサー、外部PDF取込み、PyPI公開は範囲外のまま。初期調査・計画のみとした冒頭は履歴であり、現状は実装済み。

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

## 非機能要件 (Non-Functional Requirements)

| Category | Requirement | Metric / Target |
|---|---|---|
| 保守性 | 余白・フォント・改ページ処理を共通部品として再利用し、帳票ごとの重複定義を減らす。 | 定量的な評価基準は未設定。 |
| 責務の分離 | 構造計算と帳票のレイアウト・描画を分離する。 | `.agents/rules/project-scope.md` の方針。具体的な構成は設計時に定める。 |

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

`.agents/check.ps1` はスタック検出とDESIGN・STATEの文書契約を検証する。製品の機能や参照PDFの再現性は、別途検証する。

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
