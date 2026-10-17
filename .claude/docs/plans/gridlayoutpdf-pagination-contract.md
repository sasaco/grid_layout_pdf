# 文書フロー・改ページの実装契約

2026-10-16。承認計画Step 5。共通計測、文章、数式アダプターの統合ゲート後に改ページ器を実装する。容器の独立計測は先行できる。

## APIと用紙切替

- `Document(*blocks, fonts, profile=A4_PORTRAIT_REFERENCE, style=ReportStyle(), header=None, footer=None)`。入力部品をtupleへコピーする不変の文書設定。FontRegistryは明示供給する。`layout() -> tuple[ScenePage, ...]`、`render(path, *, debug_grid=False) -> Path`。renderは全layout成功後、既存のatomic PDF rendererへ渡す。
- `PageSection(profile, *blocks)` は子の範囲だけ用紙設定を変える不変の部品。入場・退出時に新ページ。退出後は親のprofileへ戻る。ネストも同じ規則。空セクションとPageBreakしかないセクションはページを生成せず、進行中の親ページも分断しない。
- 通常のStackは再帰的に子へ展開し、分割規則とPageSection/PageBreakを保つ。Columns/KeepTogether/At内のStackは既存のatomic measureを使用する。
- PageBreakは現在ページを終了する。先頭・末尾・連続のPageBreakによる空ページを作らない。空のDocument.layoutは空tuple、renderは明確なLayoutError。正のSpacerは意図的な領域予約として数えるが、0行部品はページ開始理由にならない。
- 同じ部品の再計測はprofile/利用幅ごとに行う。同じ幅の分割済みtailは再計測せず、既存アンカーを保持する。別の用紙へ勝手に繰り越さない。

## フローの優先順位と停止

- カーソルはprofileのbody_start_rowからbody_end_rowまでの整数行。横はbody_rect全幅。高さは整数行で加算し、ページ上のyはgrid.y(row)から求める。
- 全体が残りへ入れば配置。keep_togetherは分割しない。prefer_keepは全体が空ページへ入る場合、次ページへ送ってまとめる。空ページより大きければ共通splitを使う。
- 見出しなどのkeep_with_nextは連鎖全体に適用する。途中の空部品・Spacerは次の本文の代わりにせず、高さだけを予約する。次の可視部品のminimum_rowsまでを同居させる。これをprefer_keepより優先するため、必要なら次の部品が空ページへ丸ごと入る場合も合法な境界で分割する。
- 可視内容は空文字・空白文字だけではないText、又は線・図形・画像の描画命令とする。`Text.text.strip()`が空になるTextは、占有行数を保持するが見出しに続く本文の代わりにならない。この規則をDocumentと原子的なStack/Columnsのkeep伝播で共有する。画像の透明画素解析までは行わない。
- 次の部品が先頭に空行を持つ場合、見出しと同居させる予約量は可視commandを含む最小の合法fragmentとする。prefix、break_after、min_first/min_last、keep_togetherを保ち、合法な分割がなければ全体を必要量とする。部品全体に可視文字があっても、実際に同居するfragmentが空行だけでは条件を満たさない。
- 見出し連鎖＋次の最小fragmentが空ページに収まらない場合は明示エラー。次の可視部品より先にPageBreak/用紙境界/At/文書末尾に達したkeep_with_nextも、規則を無視して孤立させず診断する。明示位置と見出し連鎖は別の容器にまとめて指定できる。
- 残りへ入らず分割できなければ新ページで再試行。空ページでも進められなければ対象block_id、必要行数と使用可能行数を付けたLayoutOverflowError。分割は必ず本文part数が減ることを検証し、無限改ページを防ぐ。
- 部品内部の描画境界はmeasure_blockで検証する。並列部品同士の横方向重複はColumns側、通常フローと明示配置の重複はカーソルと予約帯で拒否する。

## 明示位置

- `At(row, col, col_span, block, block_id='')` の行列は現在ページのgrid原点から数える整数。rowはbody_start_row以上、col/col_spanは全列内。
- rowが現在カーソルより前、枠が本文外、又は部品全高が枠外ならエラー。部品はatomicに扱い、分割や自動改ページをしない。空の子でも位置指定の範囲は検証する。
- 成功時、指定位置から部品全高の縦帯を予約し、次のフローはその終端から開始する。同じ行へ別のAtを後から置く使い方は対象外で、横並びはColumnsを使う。

## ページ装飾

- `PageDecoration(text, *, rows=1, gap_rows=1, align='left', style=None)`。textは固定文字列と`{page}`/`{pages}`のテンプレート。rowsは正整数、gap_rowsは非負整数、alignはleft/center/right。style未指定は本文書体の9pt。桁数指定など整数のformat_specは許可し、未定義フィールド・不正書式は診断する。
- 本文を詰め直さず、全ページ確定後に各ページの実profileで計測する。header枠はbody_rect上端から(gap_rows+rows)行上、footer枠はbody_rect下端からgap_rows行下、幅はbody_rectと同じ。ページ番号は全体通しの1始まり。
- 予約枠自体の紙外、文字の必要高や幅の超過は対象page/header/footerを含むエラー。枠を広げるために本文のページ数を変えたり縮小したりしない。初期版は文字装飾。任意の図を受け取るcallbackは追加しない。

## 診断と検証

- ScenePage.metadataにpage_number、各配置のblock_id/source path、grid row/col、占有rows/width、各partのローカルmetadataを残す。ローカル基線・アンカーを絶対値と誤記しない。traceのJSON変換はMappingを再帰処理し、mappingproxyをdataclasses.asdictへ渡さない。
- `layout_trace(pages, fonts) -> dict` は確定したScenePage列と同じFontRegistryからJSON保存可能な診断データを作る。schema_version、各pageの用紙寸法・grid設定・metadata、各命令の種類と実境界を含める。文字には内容・位置・書式を残すが、画像bytesは含めない。PDFと同じ配置結果を使い、部品のmeasureや改ページを再実行しない。実字形の境界は共有command_boundsで読み取る。ScenePage.metadataへ計算済み文字境界の存在を要求せず、低水準APIのページにも使える。
- leadケース: 残りぴったり/1行不足、短い/長い段落のmin2/2、連続見出し＋Spacer、prefer_keepとの競合、数式グループの合法分割とアンカー維持、巨大な原子的部品の停止、Atの過去/重複/枠外/正常予約、Columns高さ、A4→A3→A4とネスト/空section、空文書・連続改ページ、総ページ数9→10での予約枠検証、出力失敗時の既存PDF保持。
- 独立PDF抽出でMediaBox、基線、部品の順序と欠落なし、本文サイズ、ページ番号/総数を確認する。生成した通常・grid PDFを画像化し、改ページ前後と用紙切替を目視する。
