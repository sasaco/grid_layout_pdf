# 結合表の実装契約

2026-10-16。承認計画Step 6。共通計測・Paragraph・MathBlockを使う独立計測を先行できる。文書への分割統合と完成判定はStep 5bのゲート後。

## API

- `Cell(content='', *, colspan=1, rowspan=1, align=None, valign='middle', padding=3.0, style=None)`。contentは表示文字列又はBlock。数値の丸め・文字列化は利用側で行う。spanは正整数。paddingは全周共通の非負pt。alignはNone/left/center/right、valignはtop/middle/bottom。styleは文字列セルのTextStyle。Blockとstyleの同時指定は、無視された設定を作らないため明示エラーとする。
- `Table(columns, rows, *, header_rows=0, numeric_columns=(), border_width=0.5, border_color=(0,0,0), block_id='')`。columnsは各列が占める正整数のグリッド列数。空のcolumnsは入力エラー。rowsはCell又は文字列からなる行の列で、文字列はCellへ持ち上げる。入力コレクションを深さ2までtupleへコピーする。
- numeric_columnsは0始まりの表列番号。align未指定の単独セルがその列にあれば右揃え、その他は左揃え。明示alignが優先。文字列セルはParagraph(align=...)で組み、Blockセルはその計測枠をalignに従って置く。Paragraph等が既に全幅を確保する場合、内部の行揃えはそのBlockの設定に従う。数式は`Cell(MathBlock(...))`と明示する。
- header_rowsは先頭からの行数、0..全行数。行が空なら0だけ許し、空MeasuredBlockを返す。ヘッダーだけの表はatomicな通常partsとして表示できる。本文がある表では全ヘッダーをprefixにまとめ、ヘッダーだけがページ末尾に残らない。

## 結合と高さ

- 行ごとに既存rowspanで占有されていない最初の列へ次のセルを置く。colspanの全域が連続して空いていることを要求し、飛び越して別の列へ置き直さない。未占有の穴・行列範囲外・重複を明示エラーにする。rowspanで全列が覆われた行は空リストで表現できる。
- ヘッダーと本文をまたぐrowspanは入力エラー。本文内のrowspanで接続された行区間の推移的な和を1 LayoutPartにする。セルや数式の途中は分断しない。
- 各セルを列幅合計−2paddingで計測する。内容が空でも各物理表行の最小高さは1グリッド行。単独行セルの必要高さは`rows_for(measured.height+2padding)`で確保する。
- rowspanセルの必要高さが対象行の合計を超える場合、不足行数を対象の最終行へ足す。spanの短いものから、同じ長さなら開始行・開始列順に処理し、入力順で結果が揺れないようにする。
- セル内容は計測済みの全体をatomicに置き、縦位置はpadding内のtop/middle/bottom。枠線の内側に必要な余裕を確保し、文字の実境界が線へ接触しないことを検証する。paddingが小さ過ぎる設定では線幅を含む実際の余裕を検証する。
- 表幅はsum(columns)*pitch_x。available_width超過、padding後の幅不足は対象セルpathとneeded/availableを付けて失敗。既存FontErrorのcauseも保持する。

## 罫線・分割結果

- 線幅を含む境界が各LayoutPart内へ収まるように線中心を置く。結合セル内に余分な罫線を引かず、同じpartの共有線分は重ねて描かない。各独立した行群とヘッダーは改ページしても枠が閉じた状態になる。
- MeasuredBlockのprefixがヘッダー全体、partsが本文の行群。通常splitを使用でき、prefixは分割先にも1回だけ再掲する。1ページより大きい行群・ヘッダーはDocument側の停止条件で明示エラー。
- metadataに表列幅、元の表行番号、セルのrow/col/span、セル枠と内容位置、子partのローカルmetadataを保存する。描画命令やMutableオブジェクトをmetadataへ埋め込まない。

## leadケース

- 列幅の独立値、左右中央/上下中央の配置、数値列の右揃え、実字形境界、paddingと罫線の非接触。
- 文字列・Paragraph・段分数の混在、複数行見出し、colspan/rowspanと推移的に接続した行群。
- 内容増加で必要整数行が増えること、rowspan不足を最終行へ加える決定性、入力不変、同じ入力の再計測一致。
- 無効なspan、穴/重複/範囲外、ヘッダー本文跨ぎ、空表/ヘッダーだけの表、不正な幅・行数・色・NaN/inf/bool。
- 共通splitによるヘッダー再掲、本文内容の順序と回数の維持、rowspan群を切らないこと。Step 5b完了後には実Documentでヘッダーだけ残る境界・巨大行群・連続ページを検証する。
- 多段ヘッダーの表をPDF化し、独立抽出で文字と罫線を確認。通常/grid PNGで密なセルの接触・欠落・罫線の不足を目視する。
