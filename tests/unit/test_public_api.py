"""Public imports are exercised through guide imports and small compositions."""

import ast
from pathlib import Path
import re


ROOT = Path(__file__).parents[2]


def test_api_guide_imports_are_available_through_the_public_all():
    import gridlayoutpdf

    namespace = {}
    exec("from gridlayoutpdf import *", namespace)
    guide = (ROOT / "docs/api.md").read_text(encoding="utf-8")
    expected = set()
    for snippet in re.findall(r"```python\n(.*?)```", guide, re.DOTALL):
        for node in ast.walk(ast.parse(snippet)):
            if isinstance(node, ast.ImportFrom) and node.module == "gridlayoutpdf":
                expected.update(alias.name for alias in node.names)
    assert expected, "The API guide should contain public imports"
    assert expected <= namespace.keys()
    assert len(gridlayoutpdf.__all__) == len(set(gridlayoutpdf.__all__))


def test_public_types_support_document_composition_and_custom_block_measurement():
    from gridlayoutpdf import (
        Block, Cell, Columns, Document, FontFace, FontRegistry, LayoutContext,
        LayoutPart, MathBlock, MathBox, MathNode, MeasuredBlock, Paragraph,
        ReportStyle, Symbol, Table, TextMetrics, A4_PORTRAIT_REFERENCE, measure_block,
    )

    fonts = FontRegistry()
    face = fonts.resolve("IPAex明朝")
    assert isinstance(face, FontFace)
    context = LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())
    symbol = Symbol("A")
    assert isinstance(symbol, MathNode) and isinstance(symbol.measure(fonts, context.style.body), MathBox)
    assert isinstance(fonts.measure("A", context.style.body), TextMetrics)
    columns = Columns(MathBlock(symbol), Paragraph("断面積"), col_spans=(3, 26))
    measured = measure_block(columns, context, 482.4)
    assert isinstance(columns, Block) and isinstance(measured, MeasuredBlock)
    assert isinstance(measured.parts[0], LayoutPart)
    assert measured.rows == 1
    table = Table((8, 8), [[Cell("表示値"), "12.150"]], numeric_columns=(1,))
    document = Document(columns, table, fonts=fonts)
    assert document.blocks == (columns, table)


def test_public_low_level_scene_diagnostics_and_extension_helpers_remain_available():
    from gridlayoutpdf import (
        Arrow, Figure, Image, Label, RasterImage, Point, Rect, GridSpec, PageProfile,
        ScenePage, Line, Polyline, Rectangle, Text, TextStyle, LayoutError,
        LayoutOverflowError, FontError, FontRegistry, derived_profile,
        command_bounds, layout_trace, render_pdf, fit_tracking, wrap_text, wrap_math,
    )

    grid = GridSpec(10, 10, 10, 10, 5, 5)
    profile = PageProfile("custom", 100, 100, grid)
    scene = ScenePage(profile, (Line(2, 3, 8, 3),))
    trace = layout_trace((scene,), FontRegistry())
    assert trace["pages"][0]["commands"][0]["bounds"] == {"x": 1.75, "y": 2.75, "width": 6.5, "height": 0.5}
    assert Image is not RasterImage
    assert issubclass(LayoutOverflowError, LayoutError) and issubclass(FontError, LayoutError)
    assert derived_profile("landscape", 842, 595).grid.pitch_x == 16.08
    assert callable(render_pdf) and callable(command_bounds)
    assert callable(fit_tracking) and callable(wrap_text) and callable(wrap_math)
