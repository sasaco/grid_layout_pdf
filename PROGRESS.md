# PROGRESS

> Auto-maintained by /checkpointing. Shows the most recent 5 checkpoints (newest first).
> Full checkpoints live in `.claude/checkpoints/` (git-ignored).

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
