# 実装契約（段階的に固定）

対象計画: grid-aligned-calculation-reports。2026-10-16。これは実装担当間の型・責務共有であり、公開APIの全固定ではない。

## 座標と幾何（Step 2a）

- 全数値は有限のpt。上原点、右x、下y。負の局所yは数式の基線基準では許すが、ページの外側への配置は許さない。
- `geometry.py`: 不変 `Point(x,y)`、`Rect(x,y,width,height)`（right/bottom/contains）、`GridSpec(origin_x,origin_y,pitch_x,pitch_y,columns,rows)`。`x(col)`/`y(row)`は境界0..columns/rowsを受ける。`rows_for(height)`は必要高さを行へ切り上げる。入力不正はValueError系。
- `profiles.py`: 不変 `PageProfile(name,width,height,grid,body_start_row=0,body_end_row=None)`。`body_rect`プロパティ。ページにgrid/bodyが含まれること。A4/A3実測定数と `derived_profile(name,width,height)`。
- `errors.py`: `LayoutError`、`LayoutOverflowError(message, *, block_id='', needed=None, available=None)`、`FontError`。未対応や不正入力を黙って無視しない。

## 書体・描画命令（Step 2a）

- `styles.py`: 不変 `TextStyle(font='body',size=10.0,tracking=0.0)`。有限正のsize、tracking非負。`ReportStyle`等の上位設定は必要時に追加する。
- `fonts.py`: `FontRegistry.register(name,path,face_index=0)`、`resolve(name)`、`measure(text,style)`。戻り値は `TextMetrics(width,ascent,descent)`、ascent/descentはともに非負。必要文字のcmapを検証し、欠字はFontError。計測で返す幅にtrackingを含める。追加書体は計測前に明示して解決する。
- `resolve(name)`の戻り値は `FontFace(name,path,face_index,sha256,pdf_name)`。pdf_nameはReportLabの登録キー。同一論理名が別registryで異なるファイルを指す場合の衝突を避ける。
- `FontRegistry.normalize_text(text)` はNFCへ正規化する。計測と描画の両方で同じ処理を使用し、合成可能な日本語濁点などを一貫して扱う。非収録文字を黙って除去しない。
- `scene.py`: 不変 `Text(x,y,text,style)`（yは基線）、`Line(x1,y1,x2,y2,width=0.5,color=(0,0,0))`、`Polyline(points,width=0.5,color=(0,0,0),closed=False)`、`Rectangle(x,y,width,height,stroke_width=0.5,color=(0,0,0))`。Image命令は後続工程で追加。全命令に `translated(dx,dy)` を持たせる。
- `ScenePage(profile,commands=tuple(),metadata=...)` は確定ページ。metadataはデバッグ用でなくても空辞書でよい。可変辞書の外部変更でレイアウト結果が変化しないよう防御する。本文内容と描画座標の分離を保つ。

## Step 2bに渡す最小契約

- 数式は `measure(fonts,style)` → `MathBox(width,ascent,descent,commands,axis)`。commandsは自分の基線 `(0,0)` に対する座標。axisは基線から上へ向かう数式軸までの距離（初期案size×0.25）。上下付き・分数は局所自由座標で組む。
- `MathBox.height=ascent+descent`。ページへ置くときは `baseline_y=top+ascent` を使い、全commandsを平行移動する。グリッド行高への切上げは外側のブロック処理が担当。
- `MathBox.translated(dx,dy)` は移動した描画命令のtupleを返す。初期ノードは `Literal(text)`, `Symbol(text)`, `Operator(text)`, `Row(*items,gap=None)`, `Fraction(numerator,denominator)`, `Root(body)`, `Script(base,superscript=None,subscript=None)`, `Delimited(body,left='(',right=')')`。`as_math` は文字列をLiteralへ持ち上げるだけで、式を解析しない。
- 描画器は `render_pdf(pages,path,fonts,debug_grid=False)`。左下座標への変換をここに限定し、文字のyに用紙高-yを使う。ページごとの書体・線設定を適用し直す。出力は同じ出力先ディレクトリの一時ファイルを経由し、成功後だけ置換する。
- 後続の文章・数式・表のフロー契約は、最小PDF実証後にこの文書へ追記する。

## 実字形境界の補足（Step 2レビューによる修正）

- `TextMetrics.width` は字送り幅を維持する。`ink_bounds: Rect | None = None` を追加し、実字形の基線相対矩形を別に表す。registryが返す計測では実矩形を入れ、空文字・空白だけの実字形は空矩形とする。既存の3引数構築では従来の計測矩形を保守的な代用値にする。
- `ascent/descent` は書体の基本値と実字形の上下端の大きい方。`TextMetrics.bounds` は送り矩形と実字形の合成矩形。紙外検査には `bounds` を用いる。幅を字形の実幅へ置き換えて字送りを変えない。
- `Literal` の数式枠は、負の左はみ出しを必要な余白として確保し、実字形の右はみ出しも含める。文字そのものは縮めない。等号アンカーの定義は引き続き関係記号の送り枠中心。
- 根拠: 固定IPAex明朝でも `g/j` の実下降端、`Å` の上端・右端、`j` の負の左端が基本メトリクス・送り幅を超える。実字形境界と送り幅を同一視すると、数式内の接触や紙外配置を見逃す。

## Step 3以降の共通部品契約

Step 2の413件の全体テストと全6枚のPNG目視により、ReportLab採用、本文10pt、基線offset11pt、添字比率0.65を確定。共通の不変計測結果・分割規則・設定は [配置契約](gridlayoutpdf-flow-draft.md) に記載し、reference_fixturesがStep 3aを実装する。
