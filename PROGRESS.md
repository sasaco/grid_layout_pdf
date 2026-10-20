# PROGRESS

> Auto-maintained by /checkpointing. Shows the most recent 5 checkpoints (newest first).
> Full checkpoints live in `.claude/checkpoints/` (git-ignored).

## [2026-10-20-090259](.claude/checkpoints/2026-10-20-090259.md)

### 何をしたのか

方眼Excel 出力（FR-021〜027、計画 `.claude/docs/plans/grid-excel-output.md`）を feature/grid-excel-output で Step 1〜10 まで実装し、Gate 1〜4 を通過した。書体名での指定と IPAex の同梱（FR-024）、文字サイズの 0.5 pt 刻み（FR-023）、標準ライブラリで .xlsx を書く層（ADR-0001）、Excel の罫線の種類と辺ごとの罫線（FR-022・026）、描画命令の意味のタグ、数値セルの見分け、項の列のグリッド揃え（FR-025）、ScenePage から方眼Excel への写像と strict、Excel から書き出した PDF との比較スクリプト、片持ち梁 p1〜37 の新しい決まりでの作り直し（FR-027）を行った。PNG 正解（片持ち梁 通常37枚・代表例 標準5枚）を作り直して登録し、版を 0.2.0 にした。最終の全件は 3838 passed・2 skipped、カバレッジ 98.2%。最新コミットは 2e1b742（未 push）。この期間には、それより前に main で汎用部品・SideRule（FR-020）・CellLines.first_baseline などのコミットもある。

### どういうやり取りをユーザーと行ったのか

2026-10-20 にユーザーが計画を承認し（新しいブランチで、TDD と parallel-agent-dev）、作業中は「continue」で再開した。p30〜37 の回転表が A4 のグリッドの縦横入替に収まらない件では、ユーザーが「p30〜37だけ別グリッド」を選んだ。Gate 3 の質問ツールは拒否されたため文章で4点（全幅の行の最後の字の切れは制限として記録、上付き・入れ子の分母のずれは受入れ、並べた画像の目視、途中のコミットの履歴は残す）を示し、ユーザーが「承認」と答えた。Gate 4 の PNG 正解の候補（片持ち梁 74枚・代表例）もユーザーが「承認」した。

### どうやったのか

lead が依存の順に担当（grid-terms・xlsx-map・cantilever・compare）へ所有ファイルを分けて並行に実装させ、各担当は TDD と ImplementationLoop で MEDIUM 以上を0にした。lead は工程の境目ごとに全件を自分で実行した。Excel の印刷の寸法（列 16.08/21、行 15.48/21 pt/px、セルの余白 2.4 pt）を Excel COM で実測し、行・列の幅の px の配り方を決めた。比較は `scripts/compare_xlsx_pdf.py`（Excel 16.0、DocuWorks Printer）で行い、決定は update_design.py で DESIGN.md に追記した。片持ち梁の正解は render.py の staging → 目視の記録 → activate の手順で `versions/20261020T084235Z-5654d55613454fceb14d796e01cdf09b/` を有効化してから登録した。

### 途中でどういう課題が起こったのか

回転表が A4 のグリッドの縦横入替では 38/31 局所行であふれ、停止して報告し、ユーザーの選択で別グリッドにした。私が xlsx-map 担当に画面の px に揃えるよう誤って指示し、担当の指摘で印刷の実測の px に改めた。入れ子の Indent の indent_pt が外側だけだった不具合を TDD で直した。担当がステージした deferred.py の削除が私の別のコミット（89bba39）に混ざり、89bba39〜02e7f6e では片持ち梁のテストが動かない（ユーザー承認で履歴は書き換えない。以後は `git commit -- <paths>` を使う）。Excel の印刷で全幅の行の最後の字が切れる件と、上付き・入れ子の分母の 8.3〜8.5 pt のずれは制限として残った。版を上げると pyproject.toml・uv.lock が片持ち梁の正解の入力 hash に入るため、候補を作り直した。

### 将来のアクション

feature/grid-excel-output の push と main への統合（PR）はユーザーの指示を待つ。持ち越しの LOW: packed の項に許容差を設けるか、grid_fallbacks が最上位しか見ない点、Table(padding=0) と QuarterTurn の未検査の組合せ、片持ち梁の builder が非公開の `_units` を読む点（公開関数が要る）、結果だけの行の最大 4.4 列の隙間、p10・p12・p13 の揃えの残り、DESIGN の FR-026 の「Rule」と fixture の SideRule の表記の差。Python 3.12 環境での 0.2.0 の wheel の導入確認は未実施。外枠の Excel の medium 罫線は PDF より太く印刷される。

## [2026-10-17-045132](.claude/checkpoints/2026-10-17-045132.md)

### 何をしたのか

P7橋脚のPDF生成全面移行を承認済み計画 pier-report-grid-migration に従って実装中。全10工程のうち、移行前固定、独立内容/書式台帳、先行実証、共通帳票層/描画依存identity、0500の5工程を受入済み。0600、0610/0620、0710/0720は所有分離した3担当で実装中であり、全面移行や正式公開は未完了。

### どういうやり取りをユーザーと行ったのか

ユーザーは全PDF生成部分をGridLayoutPdfへ移行し、Example橋脚/outputのPDFは計算内容ではなく体裁の見本とするよう指定した。追加回答で全6帳票のページ数増減、本文・数値・表の白黒統一を確定し、最後のOK GOで具体的10工程の実装を承認した。同じ許可を再確認せず、計算/UI/入出力境界と並行JRSNAP作業を保持して進めている。

### どうやったのか

context-loader、plan/grill-with-docsで確定した計画をteam-execute/tddで実行。旧ソース/入力/正式出力/見本/書体230ファイルを不変コピーし、全6計算結果75,260 leaf、旧60ページ本文6,569 span、0600全4,601値と3,798表示cellを固定した。GL開始HEAD4f45501d20b3e93e91040f46ad852d5dc720fd1c、APP開始HEAD744e9389fa69c62906d85d42c823940f924a9251。GL1939試験/coverage99%合格、wheelをAPPへ強制再導入して製品22ファイルのsource/wheel/installed SHAを一致確認。0.12pt Grid、明朝/ゴシック9.9pt、添字6.5pt、等号glyph左端、見本行高、native図表で共通層を作った。root共通/内容/0500は122件合格、0500方向小節の改ページ最終確認27件合格。0500-v5通常2頁・長90層4頁・長名称3頁、通常/overlay全18画像を確認し、旧440span→70意味単位→全manuscript leaf→scene→実PDF1,489glyph/vectorを照合した。runtime/公開保護はroot57件、担当主要180件/JRSNAP45件等合格。正式outputはまだ変更していない。

### 途中でどういう課題が起こったのか

等号APIは中心座標で見本測定はglyph左端だったため初期約2.5pt差を発見し、半advanceの変換と負例で修正した。0500見本の一軸圧縮強度ラベルだけ8.9ptであることを確認し、他の文字の縮小には一般化しなかった。Tableの共有境界はper-stroke0.12ptが接してpaint幅0.24ptになり、原本単独0.12ptとの差として記録した。長名称で方向小節が分断された箇所はKeepNext連鎖で修正。骨組寸法の実glyph間隔は4ptで衝突なしだったがnative最小8ptへ改善し、物理geometry不変を確認中。全アプリ初回試験は600秒timeoutで完了扱いにせず、GUI隔離94pass/1skip、非UI3844pass/1failを再確認。既存PDF読取ガードが公開後hash検証を禁止していた不整合と、入力変更時に公開成功を期待する旧試験を現承認契約へ更新した。並行source編集による候補失効は保護機構の正常動作として安定状態で再確認する。

### 将来のアクション

0600/0610/0620/0710/0720のnative本文・数式・表・図を完成し、各独立台帳から実PDFまで照合する。旧Canvas全入口/helpersを、互換計算・legacy意味を維持して撤去する。全stage完成後に入力/計算/FrameWebnative不変、installed実体、全UI/非UI回帰、全頁通常/overlay画像、3観点独立レビューを実施してMedium以上を解消する。root QA .claude/logs/p7-held-acceptance.pyは実build_reportとrender_pdfの確定sceneを捕捉して同一候補PDFを監査し、ID/SHAに束縛したdecisionで既存transactionから全16正式成果物を公開する準備済み（未実行）。JRSNAPアプリreadbackや新受入receiptの発行は実施していない。詳細は .claude/docs/plans/pier-report-grid-migration-execution.md、担当ログは .claude/logs/agent-teams/team-execute-pier-report-grid-migration/。状態/研究文書の旧履歴を破壊的整理せず保持する。
