# Step 3以降の配置契約案

2026-10-16。Step 2のlead数値ゲート（413 passed）と全6枚のPNG目視を通過し、共通型の実装契約として確定。これはAPI設計であり、後続機能の完了記録ではない。

## 共通の計測結果

- `LayoutContext(fonts, profile, style)` が書体・本文style・用紙gridを渡す。通常の部品は `measure(context, available_width) -> MeasuredBlock`。幅はptで正数、すべての外側高さは整数グリッド行。
- `LayoutPart(rows, commands, metadata)` は分割しない縦方向の単位。命令は左上(0,0)相対で、文字のyだけは基線。rowsは正の整数。空の描画命令を持つpartで空白行を表せる。
- `MeasuredBlock(width, row_pitch, parts, *, prefix=(), break_after=None, min_first=1, min_last=1, keep_together=False, keep_with_next=False, prefer_keep=False, block_id='')` は不変。partsは本文単位、prefixは分割後も再掲する表ヘッダー等。widthは確保幅、row_pitchは計測に使用した物理行高。
- `rows`、`height`、`commands`、`translated(dx,dy)`を提供する。commandsはprefixから各partを行数分下へ移動した平坦なtuple。入力コレクションはコピーし、metadataもsceneと同等の不変化を行う。
- `split(available_rows)` は可能なら `(head, tail)`、無理ならNone。prefixを含む高さで収まる最も後ろの有効境界を選ぶ。head/tailはどちらも本文partを1つ以上持つ。break_afterは本文partの個数で示す境界、Noneは全境界。min_first/min_lastは段落の先頭末尾行数制約。分割後のtailでも同じ最小数を保持し、break_afterを再基準化する。
- 空の部品はparts/prefixとも空、0行。KeepTogetherはsplitしない。prefer_keepは「全体が空ページへ収まるならまとめる」という改ページ器への希望。headingはkeep_with_nextで次の最小fragmentとの同居を要求する。
- `minimum_rows` は最初に切れる最小fragment（prefix込み）の行数、分割不能なら全行数。splitのheadはkeep_with_nextをFalseへ、tailは元の値を保持する。splitで全体が収まる場合や、空head/tailになる場合はNone。break_afterには1..len(parts)-1だけを許す。短い段落の最小行数は全体を置けることを妨げない。
- min_first/min_lastは本文part数で判定し、prefixやpartのグリッド行数を含めない。keep_with_nextは見出しの連鎖全体に適用し、prefer_keepより優先する。
- 実字形・線幅を含む命令の境界を検証する関数を共有し、紙外検査と部品内検査で異なる境界式を持たない。測定中にCanvasを操作しない。
- `bounds.py` の `command_bounds(command, fonts) -> Rect` は現在の描画器の境界式を共有する。`layout.py` の `measure_block(block, context, available_width)` は結果型、確保幅、row_pitch一致、各partの描画境界を検証し、呼出し側へ戻す。初期版の境界比較は浮動小数の丸めだけを許す極小の許容差（1e-7pt）を使い、見えるはみ出しを隠さない。FontError等の診断へblock_idを加える。

## 文章と数式

- `ReportStyle(body=TextStyle(), heading=TextStyle(size=12), baseline_offset=11.0, max_tracking_em=0.05, min_first_lines=2, min_last_lines=2)` を不変設定とする。上記の数値・書体型を検証する。ページ装飾はStep 5で別の予約枠設定として追加する。
- 本文の基線offsetは11ptを採用。より大きい字形はoffsetを変形せず、必要なら基線を整数行だけ下へ移し、下降端までの占有行数を切り上げる。`LayoutContext.baseline_for(ascent)` と `rows_for(height)` を共通の補助にする。
- Paragraphは1行を1partとし、明示改行と空行を保持する。既定min_first/min_lastは2。Headingは分割禁止でkeep_with_next。Spacerは指定行数の空part。
- EquationGroupは折り返し後の表示行をpartとする。分数などの内部をpart境界にしない。同じ幅で分割した後も共有アンカーを維持する。全体が1ページ内ならprefer_keep。
- 等号位置は送り枠の中心で固定する。MathBoxの字形境界用余白と混同しない。式・結果・単位を同じ数式軸で揃える。

## フローと容器

- 通常のStackは文書フローで子を順に展開し、それぞれの分割規則を維持する。Columns/At/KeepTogetherの内部でStackを計測する場合は全体を1つの領域として計測する。
- Columnsはグリッド列数の列幅と間隔を明示し、子の高さの最大値を占有する。初期版で横並び全体の途中分割は行わない。
- Atは現在ページの明示位置に全体を置き、占有縦帯の終端まで進める。未来の行でも本文枠外ならエラー。ページを勝手に繰り越さない。
- PageSectionは新しいプロファイルの新ページを開始する。空セクション・連続PageBreakで不要な空ページを増やさない。
- 空ページで進められない場合は明示的に失敗する。分割は必ず元より短い本文part列へ進める。ページ装飾は全ページ確定後の予約枠へ描く。

## 表・図への拡張

- 表はrowspanで接続した行群を1partとし、複数ヘッダー行をprefixへまとめる。これにより結合セルを切らずに通常のsplitを使える。
- 図は宣言枠内の命令群を1partにする。画像は計測時にファイル内容を読み込んだ不変の描画命令へ変換し、描画時のファイル変更で内容・寸法が変わらないようにする。
