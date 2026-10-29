"""A filled closed Polyline in the PDF, and unfilled polylines byte for byte as before (FR-029)."""

from hashlib import sha256

import pymupdf
import pytest

from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE as A4, FontRegistry, Point, Polyline, ScenePage, render_pdf, render_xlsx,
)


@pytest.fixture
def fonts():
    return FontRegistry()


def unfilled_polylines():
    return ScenePage(A4, (
        Polyline((Point(60, 80), Point(90, 100), Point(120, 80))),
        Polyline(((150, 80), (170, 110), (190, 80)), 1.25, (0, 0.5, 0), True),
        Polyline(((60, 140), (120, 140), (120, 170)), .75, dash=(3, 1)),
        Polyline(((150, 140), (190, 140), (190, 170), (150, 170)), .5, (1, 0, 0), True, dash=(2, 2)),
    ))


# SHA-256 of the same pages rendered by 0.3.0 (85b0389), before polylines could be filled.
UNFILLED_PDF_SHA256 = "b03dd831c7594de85236bca089444e54e2c2d0ea4ac3a9b142fe4a7ae058bc58"
UNFILLED_XLSX_SHA256 = "4e137c5ea0f0e70540e2cfbed86c7ff1aea22d28e16805c66be0039e72d295ad"


def test_unfilled_polylines_render_the_same_bytes_as_before(fonts, tmp_path):
    render_pdf([unfilled_polylines()], tmp_path / "out.pdf", fonts, invariant=True)
    assert sha256((tmp_path / "out.pdf").read_bytes()).hexdigest() == UNFILLED_PDF_SHA256
    render_xlsx([("図", [unfilled_polylines()])], tmp_path / "out.xlsx", fonts)
    assert sha256((tmp_path / "out.xlsx").read_bytes()).hexdigest() == UNFILLED_XLSX_SHA256


def test_a_closed_polyline_is_filled_with_or_without_its_stroke(fonts, tmp_path):
    output = tmp_path / "filled.pdf"
    page = ScenePage(A4, (
        Polyline(((60, 80), (100, 80), (80, 110)), 1.25, (0, 0, 1), True, fill=(1, 0, 0)),
        Polyline(((150, 80), (190, 80), (170, 110)), closed=True, fill=(0, 0.5, 0), stroke=False),
        Polyline(((60, 140), (100, 140), (80, 170)), closed=True),
    ))
    render_pdf([page], output, fonts, invariant=True)
    with pymupdf.open(output) as pdf:
        both, bare, plain = pdf[0].get_drawings()
    assert both["type"] == "fs" and both["fill"] == (1, 0, 0) and both["color"] == (0, 0, 1)
    assert both["width"] == pytest.approx(1.25)
    assert tuple(both["rect"]) == pytest.approx((60, 80, 100, 110))
    assert bare["type"] == "f" and bare["fill"] == pytest.approx((0, 0.5, 0), abs=.01)
    assert tuple(bare["rect"]) == pytest.approx((150, 80, 190, 110))
    assert plain["type"] == "s" and plain["fill"] is None
