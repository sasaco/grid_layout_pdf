# GridLayoutPdf

グリッドに沿った PDF 計算書を組み立てる Python ライブラリです。
文章・構造化した数式・結合セル表・図を組み合わせ、文字サイズを保って等号列と行位置を揃えます。自動改ページ、ページ番号、A4／A3の混在に対応します。

## ローカルインストール

Python 3.12 以上と uv を使用します。実行時の依存ライブラリ ReportLab・Pillow はインストール時に自動で導入されます。
以下は Windows / PowerShell の例です。

このリポジトリのルートで通常インストールする場合:

```powershell
uv venv --python 3.12
uv pip install .
.\.venv\Scripts\python.exe -c "from importlib.metadata import version; import gridlayoutpdf; print(version('gridlayoutpdf')); print(gridlayoutpdf.__file__)"
```

別のプロジェクトから使う場合は、そのプロジェクトの仮想環境へこのリポジトリのパスを指定してインストールします。
仮想環境がまだなければ、先に `uv venv --python 3.12` で作成します。

```powershell
uv pip install "C:/Users/sasai/Documents/GridLayoutPdf"
```

GridLayoutPdf のソース変更をそのまま反映させる開発用インストール:

```powershell
uv pip install -e "C:/Users/sasai/Documents/GridLayoutPdf"
```

リポジトリ内で実行するときは `uv pip install -e .` も使えます。
通常インストール後にソースを変更した場合は、`uv pip install --reinstall "C:/Users/sasai/Documents/GridLayoutPdf"` で入れ直してください。
編集可能インストールではリポジトリを同じ場所に保持し、依存関係やパッケージ設定を変更したときに再インストールします。
特定の仮想環境を指定するときは、各 `uv pip install` に `--python "C:/path/to/.venv/Scripts/python.exe"` を付けます。

## 使用例

インストール先の Python で実行します。ソースディレクトリの追加や `PYTHONPATH` の設定は不要です。

埋め込み可能なTrueTypeフォントを用意して、パスを置き換えます。

```python
from gridlayoutpdf import (
    Document, Equation, EquationGroup, FontRegistry, Heading,
    Operator, PageDecoration, Paragraph, Row, Script,
)

fonts = FontRegistry()
fonts.register("body", "C:/path/to/ipaexm.ttf")

report = Document(
    Heading("断面諸量"),
    Paragraph("寸法と計算済みの表示値を共通の書式で配置します。"),
    EquationGroup(
        Equation("A", Row("4.50", Operator("×"), "2.70"),
                 label="断面積", result="12.150",
                 unit=Script("m", superscript="2")),
    ),
    fonts=fonts,
    footer=PageDecoration("{page} / {pages}", align="center"),
)
report.render("report.pdf")
```

数式の計算や値の丸めは利用アプリで行い、表示用文字列を渡します。部品の詳しい組み方は [APIガイド](docs/api.md)、責務の分離は [アーキテクチャ](docs/architecture.md)、検証条件は [検証方法](docs/validation.md) を参照してください。

密な表には`CellLines`の明示行間と`Insets`の四辺余白を使えます。`Table(split=False)`は不可分表の共有罫線を統合し、`Image(width_pt=..., height_pt=...)`は物理寸法を保持します。添字のサイズと基線位置も`Script`で明示できます。

数式・結合表・寸法図・画像とA4／A3を組み合わせた [代表帳票の例](examples/README.md) も用意しています。リポジトリ内では次のコマンドで通常PDF、グリッド付きPDF、配置JSONを生成できます。

```powershell
uv run --locked python examples/representative_report.py --font tests/fixtures/fonts/ipaexm.ttf --output build/reports/representative/standard
```

グリッドや書体計測も単独で利用できます。

```python
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE

page = A4_PORTRAIT_REFERENCE
print(page.width, page.height)      # 595, 842 (pt)
print(page.grid.columns, page.grid.rows)  # 30, 47
print(page.grid.x(1), page.grid.y(1))     # 66.96, 70.078 (pt)
```

文字幅の計測では、利用するフォントファイルを明示して登録します。
フォントはパッケージに同梱せず、OS からの自動検索もしません。
使用する文字を含む TrueType フォントを用意し、次のパスを置き換えてください。
TrueType collection (TTC) は `face_index` で書体を指定できます。CFF 形式の OpenType フォントには対応していません。

```python
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.styles import TextStyle

fonts = FontRegistry()
fonts.register("body", "C:/path/to/ipaexm.ttf")
metrics = fonts.measure("計算書", TextStyle(font="body", size=10))
print(metrics.width, metrics.ascent, metrics.descent)  # 単位は pt
```

## 開発と配布物の作成

リポジトリのルートで実行します。

```powershell
uv sync --locked
uv run --locked --extra dev python -X utf8 .agents/skills/_shared/run_tests.py --target tests --expect pass --label local-validation
uv build
```

`uv build` は `dist/` に wheel とソース配布物を作成します。
配布物にはライブラリ本体とパッケージ情報を含め、テスト・参照 PDF・テスト用フォントは含めません。
