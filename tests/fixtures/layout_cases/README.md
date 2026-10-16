# 表示用原稿

6つの JSON は原本PDFから観察した表現を小さく切り出した、手書きの表示データです。数値は書式済み文字列であり、構造計算を実行・検証しません。公開APIの利用例へ明示的に対応づけるための素材で、製品のJSON入力形式を約束するものではありません。

- `japanese_two_anchors.json`: 日本語ラベル、英数字、2つの等号、結果右端、単位列。
- `nested_fractions_scripts.json`: 段分数、分数の指数、下付き、根号、背の高い括弧。
- `long_substitution.json`: 項と演算子の順序、演算子前の折り返し候補、明示改行。
- `merged_table.json`: 2段ヘッダー、横結合、縦結合、右揃え数値。
- `mixed_diagram.json`: 本文、線・矩形・矢印・ラベル、画像、数式の混在。
- `mixed_paper.json`: A4縦 → A3横 → A4縦、本文10 ptの維持。

`kind` は構造の説明です。数式内の `literal.text`、`symbol.text`、`operator.text` は表示内容を持ち、`equation.result` も文字列をそのまま保持します。`row.items` の順序を変えず、`break` は直後の演算子を継続行頭に置く明示改行です。ページ番号は参照元の1始まり、表の `row` / `column` とアンカーの列番号は0始まりです。

図内部の座標は左上原点のptで、図の局所枠に限定します。`sample_pixels.png` はこのfixture用に新規作成した16×8 RGB画像で、画像枠の縦横比保持を検査する素材です。原本の図や画像を抽出していません。

参照原本のパス・ハッシュ・実測値・ページの役割は `../reference_manifest.json` にあります。生成PDFはリポジトリの `build/reports/` へ出力し、原本ディレクトリ `tests/output/` と `.agents/docs/research/` を上書きしません。原本のバイト列・画素一致は生成PDFの合格基準ではありません。
