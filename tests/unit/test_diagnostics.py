from dataclasses import replace
import importlib
import json
from pathlib import Path

import pytest

from gridlayoutpdf.errors import FontError
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.geometry import Point
from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE
from gridlayoutpdf.scene import Line, Polyline, RasterImage, Rectangle, ScenePage, Text
from gridlayoutpdf.styles import TextStyle


def api():
    try:
        return importlib.import_module("gridlayoutpdf.diagnostics")
    except ModuleNotFoundError:
        pytest.fail("layout_trace is not implemented")


@pytest.fixture
def fonts():
    registry = FontRegistry()
    registry.register("body", Path(__file__).parents[1] / "fixtures/fonts/ipaexm.ttf")
    return registry


def test_trace_serializes_page_profile_grid_body_and_nested_local_metadata(fonts):
    profile = replace(A4_PORTRAIT_REFERENCE, body_start_row=2, body_end_row=40)
    metadata = {"page_number": 7, "placements": [{"x_pt": 100, "y_pt": 200,
        "parts": [{"row": 3, "metadata": {"baseline_pt": 11, "anchors": {"equals": [32.16, 64.32]}}}]}]}
    pages = [ScenePage(profile, metadata=metadata), ScenePage(A3_LANDSCAPE_REFERENCE)]
    trace = api().layout_trace(pages, fonts)
    assert trace["schema_version"] == 1
    assert trace["coordinate_system"] == "top-left-pt"
    assert trace["page_count"] == 2
    assert [page["page_number"] for page in trace["pages"]] == [1, 2]
    page = trace["pages"][0]
    assert page["profile"]["name"] == "A4_PORTRAIT_REFERENCE"
    assert (page["profile"]["width"], page["profile"]["height"]) == (595, 842)
    assert page["profile"]["grid"] == {"origin_x": 50.88, "origin_y": 54.598,
        "pitch_x": 16.08, "pitch_y": 15.48, "columns": 30, "rows": 47}
    assert (page["profile"]["body_start_row"], page["profile"]["body_end_row"]) == (2, 40)
    assert page["profile"]["body_rect"] == pytest.approx({"x": 50.88, "y": 85.558, "width": 482.4, "height": 588.24})
    assert page["metadata"] == metadata
    assert page["commands"] == []
    assert trace["pages"][1]["profile"]["width"] == 1191
    assert json.loads(json.dumps(trace, ensure_ascii=False)) == trace
    page["metadata"]["placements"][0]["parts"][0]["metadata"]["anchors"]["equals"][0] = 999
    assert pages[0].metadata["placements"][0]["parts"][0]["metadata"]["anchors"]["equals"][0] == 32.16


def test_trace_text_retains_style_baseline_and_actual_glyph_overhang(fonts):
    page = ScenePage(A4_PORTRAIT_REFERENCE, (Text(20, 30, "jÅ", TextStyle()),))
    command = api().layout_trace((page,), fonts)["pages"][0]["commands"][0]
    assert (command["type"], command["index"], command["text"], command["normalized_text"]) == ("Text", 0, "jÅ", "jÅ")
    assert (command["x"], command["baseline_y"]) == (20, 30)
    assert command["style"] == {"font": "body", "size": 10, "tracking": 0}
    # Pinned glyf/advance values at 10pt with no added tracking.
    assert command["bounds"] == pytest.approx({"x": 19.4580078125, "y": 20.849609375,
        "width": 10.8935546875, "height": 11.1376953125})


def test_trace_text_preserves_source_and_reports_normalized_rendered_text(fonts):
    style = TextStyle(size=12, tracking=0.25)
    command = Text(10, 20, "か\u3099Ａ", style)
    traced = api().layout_trace((ScenePage(A4_PORTRAIT_REFERENCE, (command,)),), fonts)["pages"][0]["commands"][0]
    assert traced["text"] == "か\u3099Ａ"
    assert traced["normalized_text"] == "がＡ"
    assert traced["style"] == {"font": "body", "size": 12, "tracking": 0.25}
    assert command.text == "か\u3099Ａ" and command.style is style


def test_trace_records_all_primitives_bounds_and_image_identity_without_bytes(fonts):
    commands = (
        Line(1, 2, 9, 10, width=2, color=(1, 0, 0)),
        Polyline((Point(2, 3), Point(7, 11), Point(4, 8)), width=2, closed=True),
        Rectangle(20, 30, 8, 9, stroke_width=2, color=(0, 0, 1)),
        RasterImage(40, 50, 12, 16, b"abc"),
    )
    trace = api().layout_trace((ScenePage(A4_PORTRAIT_REFERENCE, commands),), fonts)
    line, polyline, rect, image = trace["pages"][0]["commands"]
    assert [c["type"] for c in (line, polyline, rect, image)] == ["Line", "Polyline", "Rectangle", "RasterImage"]
    assert [c["index"] for c in (line, polyline, rect, image)] == [0, 1, 2, 3]
    assert line["bounds"] == {"x": 0, "y": 1, "width": 10, "height": 10}
    assert (line["x1"], line["y1"], line["x2"], line["y2"], line["width"], line["color"]) == (1, 2, 9, 10, 2, [1, 0, 0])
    assert polyline["bounds"] == {"x": 1, "y": 2, "width": 7, "height": 10}
    assert polyline["points"] == [[2, 3], [7, 11], [4, 8]] and polyline["closed"] is True
    assert rect["bounds"] == {"x": 19, "y": 29, "width": 10, "height": 11}
    assert (rect["x"], rect["y"], rect["width"], rect["height"], rect["stroke_width"]) == (20, 30, 8, 9, 2)
    assert image["bounds"] == {"x": 40, "y": 50, "width": 12, "height": 16}
    assert image["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert image["byte_count"] == 3 and "data" not in image
    assert "abc" not in json.dumps(trace)


def test_trace_does_not_measure_blocks_reflow_or_require_precomputed_bounds(fonts, monkeypatch):
    import gridlayoutpdf.layout as layout
    from gridlayoutpdf.blocks import Paragraph
    from gridlayoutpdf.document import Document

    def forbidden(*args, **kwargs):
        pytest.fail("Tracing must not measure a block or reflow a document")

    monkeypatch.setattr(layout, "measure_block", forbidden)
    monkeypatch.setattr(Paragraph, "measure", forbidden)
    monkeypatch.setattr(Document, "layout", forbidden)
    page = ScenePage(A4_PORTRAIT_REFERENCE, (Line(-2, 3, 5, 3),), {})
    trace = api().layout_trace(iter((page,)), fonts)
    assert trace["pages"][0]["commands"][0]["bounds"]["x"] == -2.25
    assert page.metadata == {} and page.commands == (Line(-2, 3, 5, 3),)


def test_trace_accepts_empty_page_sequence(fonts):
    trace = api().layout_trace((), fonts)
    assert trace["pages"] == [] and trace["page_count"] == 0
    json.dumps(trace)


def test_trace_missing_glyph_uses_supplied_registry_and_reports_page_command(fonts):
    pages = (ScenePage(A4_PORTRAIT_REFERENCE),
             ScenePage(A4_PORTRAIT_REFERENCE, (Line(1, 2, 9, 2), Text(20, 30, "\U0010ffff", TextStyle()))))
    with pytest.raises(FontError, match="page\\[2\\].commands\\[1\\].*U\\+10FFFF") as caught:
        api().layout_trace(pages, fonts)
    assert isinstance(caught.value.__cause__, FontError)
    page = ScenePage(A4_PORTRAIT_REFERENCE, (Text(20, 30, "A", TextStyle()),))
    with pytest.raises(FontError, match="page\\[1\\].commands\\[0\\].*body"):
        api().layout_trace((page,), FontRegistry())


@pytest.mark.parametrize("pages", [None, [None], [object()], "bad"])
def test_trace_rejects_invalid_pages_with_clear_diagnostic(fonts, pages):
    with pytest.raises(ValueError, match="pages"):
        api().layout_trace(pages, fonts)


def test_trace_rejects_invalid_font_registry():
    with pytest.raises(ValueError, match="fonts"):
        api().layout_trace((), None)


def test_rotated_text_trace_records_orientation_without_changing_horizontal_shape(fonts):
    assert "quarter_turns" in Text.__dataclass_fields__
    page = ScenePage(A4_PORTRAIT_REFERENCE, (
        Text(20, 30, "jÅ", TextStyle(tracking=0.25), quarter_turns=1),
        Text(20, 40, "jÅ", TextStyle(tracking=0.25)),
    ))
    rotated, horizontal = api().layout_trace((page,), fonts)["pages"][0]["commands"]
    assert rotated["quarter_turns"] == 1
    assert rotated["direction"] == [0, -1]
    assert rotated["bounds"] == {"x": 10.849609375, "y": 19.3984375,
                                  "width": 11.1376953125, "height": 11.1435546875}
    assert "quarter_turns" not in horizontal and "direction" not in horizontal
