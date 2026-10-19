"""Excel border styles and their PDF strokes (FR-022)."""

import importlib
import re

import pymupdf
import pytest


def api():
    return importlib.import_module("gridlayoutpdf")


EXCEL_NAMES = ("hair", "thin", "medium", "thick", "double", "dotted", "dashed", "dashDot",
               "dashDotDot", "mediumDashed", "mediumDashDot", "mediumDashDotDot", "slantDashDot")

# (stroke width, stroke centre offsets, dash) recorded in borders.py and the plan.
GEOMETRY = {
    "hair": (.25, (0,), ()), "thin": (.5, (0,), ()), "medium": (1, (0,), ()), "thick": (1.5, (0,), ()),
    "double": (.5, (-.5, .5), ()),
    "dotted": (.5, (0,), (.5, 1)), "dashed": (.5, (0,), (3, 1.5)),
    "dashDot": (.5, (0,), (6, 1.5, 1.5, 1.5)), "dashDotDot": (.5, (0,), (6, 1.5, 1.5, 1.5, 1.5, 1.5)),
    "mediumDashed": (1, (0,), (6, 2)), "mediumDashDot": (1, (0,), (6, 2, 2, 2)),
    "mediumDashDotDot": (1, (0,), (6, 2, 2, 2, 2, 2)), "slantDashDot": (1, (0,), (6, 1, 2, 1)),
}


def test_border_styles_are_exactly_excels_names():
    style = api().BorderStyle
    assert tuple(member.value for member in style) == EXCEL_NAMES
    assert style("dashDot") is style.DASH_DOT and style.THIN == "thin"


@pytest.mark.parametrize("name", EXCEL_NAMES)
def test_each_style_has_its_recorded_pdf_geometry(name):
    style = api().BorderStyle(name)
    width, offsets, dash = GEOMETRY[name]
    assert (style.stroke_width, style.offsets, style.dash) == (width, offsets, dash)
    assert style.thickness == pytest.approx(max(offsets) - min(offsets) + width)


def test_the_four_solid_weights_and_the_double_line():
    style = api().BorderStyle
    assert [style(name).thickness for name in ("hair", "thin", "medium", "thick")] == [.25, .5, 1, 1.5]
    # Two 0.5 pt strokes whose centres are 1.0 pt apart: a 0.5 pt gap, 1.5 pt in all.
    first, second = style.DOUBLE.lines(0, 10, 50, 10)
    assert (first.width, second.width) == (.5, .5)
    assert second.y1 - first.y1 == 1 and second.y1 - first.y1 - first.width == .5
    assert style.DOUBLE.thickness == 1.5


def test_lines_follow_the_edge_and_offset_double_strokes_perpendicular_to_it():
    module = api()
    style = module.BorderStyle
    assert style.THIN.lines(1, 2, 9, 2, (.1, .2, .3)) == (module.Line(1, 2, 9, 2, .5, (.1, .2, .3)),)
    assert style.DASHED.lines(4, 0, 4, 9) == (module.Line(4, 0, 4, 9, .5, dash=(3, 1.5)),)
    assert style.DOUBLE.lines(4, 0, 4, 9) == (module.Line(3.5, 0, 3.5, 9, .5), module.Line(4.5, 0, 4.5, 9, .5))
    for bad in ((0, 0, 5, 5), (3, 3, 3, 3)):
        with pytest.raises(ValueError, match="horizontal or vertical"):
            style.THIN.lines(*bad)


@pytest.mark.parametrize("value", [.5, 1, 0, True, "Thin", "solid", object()])
def test_pt_widths_and_unknown_names_are_not_border_styles(value):
    with pytest.raises(ValueError, match="BorderStyle"):
        api().TableBorders(value)


def test_pdf_strokes_have_each_styles_width_dash_and_double_offsets(tmp_path):
    module = api()
    profile = module.PageProfile("borders", 300, 400, module.GridSpec(20, 20, 10, 20, 20, 18))
    blocks = [module.Rule(module.BorderStyle(name), columns=10) for name in EXCEL_NAMES]
    output = tmp_path / "borders.pdf"
    module.Document(*blocks, profile=profile).render(output)
    with pymupdf.open(output) as pdf:
        drawings = pdf[0].get_drawings()
    by_row = {}
    for drawing in drawings:
        (start, end), = [(item[1], item[2]) for item in drawing["items"] if item[0] == "l"]
        assert start.y == end.y
        by_row.setdefault(int((start.y - 20) // 20), []).append((start.y, drawing))
    assert sorted(by_row) == list(range(len(EXCEL_NAMES)))
    for row, name in enumerate(EXCEL_NAMES):
        width, offsets, dash = GEOMETRY[name]
        strokes = sorted(by_row[row], key=lambda item: item[0])
        assert [drawing["width"] for _, drawing in strokes] == pytest.approx([width] * len(offsets))
        thickness = max(offsets) - min(offsets) + width
        top = 20 + 20 * row
        # Inside the Rule's row, along its top boundary.
        assert [y - top for y, _ in strokes] == pytest.approx([thickness / 2 + o for o in offsets])
        for _, drawing in strokes:
            pattern, _, phase = drawing["dashes"].strip().rpartition("]")
            values = [float(value) for value in re.findall(r"[-+]?\d*\.?\d+", pattern)]
            assert values == pytest.approx(list(dash)) and float(phase or 0) == 0
