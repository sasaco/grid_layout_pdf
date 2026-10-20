# 計算書の例

`representative_report.py` は公開 API の `from gridlayoutpdf import ...` だけで組む代表帳票です。日本語本文、二等号列と結果の右揃え、複雑な数式、折り返し、変数説明、結合セル表、寸法図と画像を、A4 → A3 横 → A4 の文書にまとめます。図の内部以外はグリッド単位と通常の文書フローで配置します。

数値は説明用の表示入力です。設計計算・照査を行うソルバーではありません。`build_report(image_path, font='IPAex明朝', variant='standard')` が返す `Document` を、書体名と画像を指定して生成できます。`font` は本文と見出しの書体名で、既定は同梱の IPAex明朝 です。`long` は本文・ラベル・表の備考を延ばし、結果に同値の末尾ゼロを追加した例です。文字サイズや座標を変えずに再配置します。

利用側で計算と書式設定を済ませた文字列は `display_values` から渡せます。既知のキーは `area`、`inertia`、`section_modulus`、`vertical`、`horizontal`、`adjustment` です。省略した項目は選択した variant の既定値を使い、渡した文字列を計算・丸め直しません。固定した結果欄に収まらない長さは、縮小せず `LayoutOverflowError` にします。式や入力条件そのものを変更する場合は、サンプル内の式の原稿も対応させてください。

```python
from representative_report import build_report

report = build_report("assets/bridge-overview.png", font="IPAex明朝", display_values={
    "area": "12.150000", "inertia": "7.3811250", "vertical": "40.000000",
})
report.render("report.pdf")
```

## 実行

`--font` には書体名を指定します。省略すると同梱の IPAex明朝 を使います。同梱の `IPAexゴシック` や、Windows の書体フォルダにある書体（例: `MS Mincho`、`ＭＳ 明朝`）も名前で指定できます。書体は日本語・ギリシャ文字・数式記号を含み、PDF 埋め込みが許される TrueType 書体を使ってください。見つからない書体名はエラーになります。

```powershell
uv run --locked --extra dev python examples/representative_report.py --output build/reports/representative/standard --preview
uv run --locked --extra dev python examples/representative_report.py --output build/reports/representative/long/report.pdf --variant long --preview
```

`--output` が `.pdf` ならそのファイル名、その他ならそのディレクトリに `representative-report.pdf` を作ります。同じ配置結果から `*-grid.pdf` と JSON の配置記録も保存します。

`--term-columns grid` は代入した値の項をグリッドの列ごとに置きます（`build_report(..., term_columns='grid')`）。`--xlsx` は同じページを方眼Excel（`representative-report.xlsx`、シート名「代表例」）でも書き、`--strict` はその時に文字片のずらしや図形への切替えが1件でもあればエラーにして何も書きません。`--term-columns grid --xlsx --strict` は既定の書体で合格します。既定の `packed` は項を詰めて並べ、指数に分数を使うため `--strict` では止まります。

```powershell
uv run --locked --extra dev python examples/representative_report.py --output build/reports/representative/grid --term-columns grid --xlsx --strict
````--preview` を指定した場合だけ、開発用 PyMuPDF で全ページの PNG を `previews/` へ保存します。

通常の PDF・JSON 出力には PyMuPDF は不要です。インストールした `gridlayoutpdf` がある環境へ、このスクリプトと `assets/` を一緒にコピーして実行できます。

```powershell
python representative_report.py --output ./reports
python representative_report.py --font "MS Mincho" --image C:/images/bridge.png --output ./reports/custom.pdf
```

`assets/bridge-overview.png` はこの例のために描いた河川橋の概念図です。参照 PDF や写真の転載ではなく、実在する構造物の寸法を表しません。

## 個別の部品例

- `typography_proof.py`: 日本語・数学記号・複雑な数式。
- `equation_proof.py`: 等号アンカーと数式折り返し。
- `table_proof.py`: 複数段ヘッダーと結合セル。
- `figure_proof.py`: 寸法図、矢印、透過画像。
- `pagination_proof.py`: 改ページと用紙切替。

これらは開発用の個別確認例です。書体は既定の IPAex明朝 に固定し、`--font` は受け付けません。利用アプリへコピーする入口には `representative_report.py` を使ってください。
