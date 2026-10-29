"""A filled closed Polyline in a grid Excel sheet is a filled freeform (FR-029)."""

import zipfile

import pytest

from gridlayoutpdf import A4_PORTRAIT_REFERENCE, Figure, Polyline, ScenePage
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.renderers.xlsx import render_xlsx
from gridlayoutpdf.renderers.xlsx import _model as xl
from gridlayoutpdf.renderers.xlsx._map import map_reports
from gridlayoutpdf.document import Document


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * 0.6, style.size * 0.8, style.size * 0.2)


FONTS = FixedFonts()
A4 = A4_PORTRAIT_REFERENCE
OX, OY, PX, PY = 50.88, 54.598, 16.08, 15.48


def padding(size):
    return 2.4


def drawings(*commands):
    workbook, result = map_reports([("図", (ScenePage(A4, commands),))], FONTS, cell_padding_pt=padding)
    return workbook.sheets[0].drawings, result


def triangle(**kwargs):
    return Polyline(((OX + PX, OY + PY), (OX + 3 * PX, OY + PY), (OX + 2 * PX, OY + 3 * PY)), closed=True,
                    **kwargs)


def test_a_filled_polyline_is_a_filled_freeform():
    (shape, bare), result = drawings(triangle(fill=(1, 0, 0)), triangle(fill=(0, 0, 1), stroke=False))
    assert isinstance(shape, xl.Polyline) and shape.closed
    assert shape.fill == (1, 0, 0) and shape.stroke is True
    assert isinstance(bare, xl.Polyline) and bare.fill == (0, 0, 1) and bare.stroke is False
    assert result.fallbacks == ()


def test_an_unfilled_polyline_is_mapped_as_before():
    (shape,), _ = drawings(triangle())
    assert shape.fill is None and shape.stroke is True


def test_a_filled_polyline_of_no_area_without_a_stroke_is_dropped():
    flat = Polyline(((OX + PX, OY + PY), (OX + 3 * PX, OY + PY), (OX + PX, OY + PY)), closed=True,
                    fill=(0, 0, 0), stroke=False)
    shapes, result = drawings(flat)
    assert shapes == () and len(result.dropped) == 1
    stroked = Polyline(flat.points, closed=True, fill=(0, 0, 0))
    (line,), _ = drawings(stroked)
    assert isinstance(line, xl.Line)


def test_the_fill_is_written_into_the_drawing(tmp_path):
    pages = Document(Figure(4, 3, Polyline(((2, 2), (40, 2), (20, 30)), closed=True, fill=(1, 0, 0), stroke=False)),
                     fonts=FONTS, profile=A4).layout()
    path = tmp_path / "out.xlsx"
    render_xlsx([("図", pages)], path, FONTS, strict=True, cell_padding_pt=padding)
    with zipfile.ZipFile(path) as package:
        drawing = package.read("xl/drawings/drawing1.xml").decode("utf-8")
    assert "<a:custGeom>" in drawing and "<a:close/>" in drawing
    assert '<a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>' in drawing
    assert "<a:ln><a:noFill/></a:ln>" in drawing
    first = path.read_bytes()
    render_xlsx([("図", pages)], path, FONTS, strict=True, cell_padding_pt=padding)
    assert path.read_bytes() == first
