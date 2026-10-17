# 片持ち梁 p01-37 改善項目レビュー

レビュー日: 2026-10-17。対象は [改善一覧](cantilever-p01-37-improvements.md) の13件と、受入済み版 `20261017T005753Z-7952a1f3f915474c8a478f77d40cf9da`。以下のファイル位置はこのレビュー時点のもの。

## 結論

13件を新規不具合13件として扱う必要はない。7件は既に実装され、6件は再現用fixtureでの対応を汎用APIへ移す候補、または任意の組版改善である。ただし実装済みのIMP-013には、期待値を将来編集したときの原本との順序一致を強化する余地がある。

優先順は、原本照合の強化、セル余白・行高診断、密なセル内容の共通化、画像の物理寸法指定、添字指定、不可分な表の罫線統合とする。罫線の設計実証は早期に行い、既存の分割可能な表の仕様を維持する。具体的な変更範囲と合格条件は [実装計画](../plans/cantilever-p01-37-improvements.md) を正本とする。

## 今回確認した証拠

- 指定版の `bundle.json` に登録された入力123件・成果物78件のSHA-256を再計算し、不一致0件。現状の製品コード・原稿・原本・書体はこの受入版と対応する。
- `normal.pdf` と `grid.pdf` を開き、各37ページ、全ページ595×842pt、ページRotate=0を確認。
- 同bundleに含まれる、PDFから生成されたハッシュ一致のプレビューを利用。p1・p9・p26・p30・p36について通常/gridの計10画像を全ページ目視した。今回は全74画像の再目視ではない。
- p1の数値セルと図、p9の上付きと図、p26の6表、p30/36の回転表を確認。今回の範囲では新たな紙面破綻を認めず、残件の主目的は公開APIの使い勝手・保守性の改善と判断した。p9の原本由来の `#######` は修正対象にしない。
- 調査開始時の全製品テストを共有runnerから実行: **1508 passed in 55.75s**。ログ: `.claude/logs/cantilever-improvements-plan-baseline.log`。後述の並行変更追加前の結果。今回はcoverageを新規測定していない。既存の98.80%は前回受入記録として区別する。
- `trace.json` のページ予約行数: p1=42、p9=37、p26=45、p30=46、p36=47。p36には追加行の余裕がない。
- 共有 `.claude/check.ps1` は合格。DESIGNのArchitecture本文に関する既存警告は残るが、製品検証の代用にはしていない。

### 作業中の並行変更

初回の入力123件一致確認後、01:27:39 UTCの更新で `src/gridlayoutpdf/tables.py` に `row_heights` の明示行高指定が追加され、`tests/unit/test_table_row_heights.py` も出現した。本レビュー担当による製品変更ではない。後続のhash確認ではtables.pyのみ受入版と不一致、成果物78件は全て一致した。証拠: `.claude/logs/cantilever-improvements-plan-evidence.json`。

この追加を保持し、計画では `row_heights=None` の自動割当と、明示行高の厳密割当の両方へInsets・CellLines・不可分Tableを統合する。明示行高は余白込みで収まらなければエラーとし、汎用化のために勝手に行を伸ばさない。並行変更の最終受入をこのレビューで代行したとは扱わず、実装開始時に基準を取り直す。

続いてbuilderにも変更を検知した。`appearance.py` のSourceCell/SourceLiteral/SourceScript/PageFrame、`source-layout.json`、`font-profile.json`を利用する原本アンカー配置へ移行中で、PageFrameは47行を予約する。従って本書のCompactCell、既定Script、p26=45行という根拠は、指定bundleと調査開始時点に対するものである。新しい原本固有のアンカー・書体を汎用CellLinesやScriptへ無条件に置き換えず、共通責務だけを移す合流方針を計画に追加した。新しい `tests/integration/test_cantilever_source_appearance.py` と `tests/unit/test_cantilever_appearance_builder.py` の受入は並行作業側の結果と区別する。

## 13件の判定

コードパスの `src/` は `src/gridlayoutpdf/`、fixtureは `tests/fixtures/cantilever_p01_37/` を表す。

| ID | 判定 | 根拠と推奨対応 | 計画工程 |
|---|---|---|---|
| IMP-001 | 実装済み・維持 | `src/scene.py:46`、`bounds.py:16`、`renderers/reportlab.py:42`、`diagnostics.py:40`。Textの四半回転は描画・実字形境界・traceへ反映済み。新機能に作り直さず回帰対象とする。 | 8 |
| IMP-002 | 実装済み・維持 | `src/rotation.py:37` のQuarterTurn、`tests/unit/test_rotation.py:57`以降。局所グリッドと不可分性を保持。RasterImage対応はこの改善へ追加しない。 | 2、8 |
| IMP-003 | fixture対応済み・公開化候補 | `fixture/builder.py:61` のCompactCell。明示行・行別サイズ・基線間隔を組む責務を、検証付きの公開部品へ移す。fixtureのJSON解釈は移さない。 | 4 |
| IMP-004 | fixture実装済み・維持 | `fixture/builder.py:239,293`、`tests/unit/test_cantilever_fixture.py:57`。固定頁・頁ID・部品IDの検査がある。一般Documentに37頁制約を移さない。 | 8 |
| IMP-005 | fixture実装済み・維持 | `fixture/render.py:76,124,130`、`tests/unit/test_cantilever_fixture.py:217`以降。stagingから検査済みversionへ移しcurrentを最後に置換。汎用配布システムへ拡大しない。 | 8 |
| IMP-006 | 公開API実装済み・維持 | `src/tables.py:22,93,277`、`tests/unit/test_table_rules.py`。選択罫線・太さ指定・0線の境界検査は既にある。 | 3、7、8 |
| IMP-007 | 任意改善・範囲を限定 | `src/tables.py:76`は行群ごとの共有辺を別strokeとする契約。`tests/unit/test_table_rules.py:62`も2本を期待する。まず不可分な表全体を1partとして統合。一般の分割表の統合は別設計。 | 2、7 |
| IMP-008 | 原因妥当・診断と部品改善 | `src/layout.py:183`の予約高に `tables.py:196,201`がpaddingを加えて再切上げ。任意Blockの予約を実字形高で上書きしない。明示行部品内の余白を丸め前に加算し、Table側余白0と組み合わせる。 | 3、4 |
| IMP-009 | fixture対応済み・公開化候補 | `src/figures.py:160,208`は整数枠へのfitのみ。`fixture/builder.py:107`は物理幅・高さを保持。EXIF/alpha/snapshotを共用し、描画寸法と予約寸法を明示的に分ける。 | 5 |
| IMP-010 | fixture対応済み・公開化候補 | `src/tables.py:42,56,217,298`は全辺同じpadding。fixtureのinline_paddingは横のみ。四辺の余白を明示し、上下0・左右のみの変更で行高が増えないようにする。 | 3、4 |
| IMP-011 | 任意の組版改善 | `src/math.py:181,205`は添字比0.65と自動offset。p9の座標差は受入条件違反ではない。既定値を変えず、明示指定と安全性検査を追加する。 | 6 |
| IMP-012 | fixture実装済み・維持 | `fixture/verify.py:9`、`tests/integration/test_cantilever_p01_37.py:27,41`。最適化Python拒否と通常Pythonのcontrolがある。 | 1、8 |
| IMP-013 | 実装済み・順序検査を追加 | `tests/integration/test_cantilever_p01_37.py:74`の全37頁再抽出は文字集合と一回被覆の検査。次項R1の独立順序検証を追加する。 | 1 |

## レビュー指摘

### R1 / Medium: 原本対expectedの同一セル内の順序交換を検知できない

`tests/integration/test_cantilever_p01_37.py:92-95` は `Counter` 同士を比較している。例えば `expected/p01.json:524` の `p01-dead-loads.r1.c3` は `1530.0` だが、これを `1350.0` に変更しても文字集合・個数は変わらない。

生成PDF対expectedの比較は `fixture/verify.py:415-417` で順序を検査する。しかし、原稿とexpectedを同じ誤順へ変更した場合に原本との独立性を守る検査としては不十分。原本を使う別のcontrolはp16/17/26/30/36の5頁で、p1を含まない (`test_cantilever_p01_37.py:23,428`)。

推奨: 全37頁のsource bbox・方向・基線・添字役割に基づく原本読み順検査を追加。原稿や生成PDFから正解を作らず、同じ文字集合の数字交換、回転セル内の順序交換、添字の役割交換を負例とする。これは将来の期待値保守に対する不足であり、現行PDFの数字が誤っているという指摘ではない。

### R2 / Low: IMP-008の行数を途中経過と最終値に分ける

一覧の「67行→43行」は途中の実証記録であり、指定された受入版のp26は45行。現行原稿に対し、メモリ上だけで6表のTable外側paddingを0から0.6ptへ変えた計測では **69行必要・47行使用可能** のLayoutOverflowErrorになった。原稿ファイルは変更していない。

推奨: 過去の記録を保持し、現行再現条件を45行/69行へ注記する。最終受入に「必ず43行」を流用しない。p36の47行も含め、全ページの実測値を比較基準にする。

## 設計上避けること

- `MeasuredBlock.height` を描画文字のboundsで置き換えること。空行、Spacer、図、任意Blockの意図した予約を失う。
- rendererで全線分を重複除去すること。異なる部品・ページ境界の描画責務に干渉する。
- `KeepTogether(Table(...))`だけでIMP-007が解消したと判断すること。行群ごとのstrokeは既に生成されている。
- 画像の幅・高さだけを追加してSourceFigureとの予約幅も一致すると仮定すること。現状SourceFigureは非整数グリッド幅を予約する。
- 原本にある上付き位置を全書体の既定値へ固定すること、指定された危険なoffsetを無断補正すること。
- 意図した見た目の変更を、goldenの自動更新や原本照合の許容幅拡大だけで通すこと。

## 今回の変更範囲

レビュー文書・計画・改善一覧への追記・作業状態のみを更新する。製品コード、製品テスト、原稿、expected、原本PDF、既存golden、受入bundle/currentはこの計画作業では変更しない。
