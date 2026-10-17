"""Rigid quarter-turn layout, independently hand-computed in top-origin pt."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import gridlayoutpdf as api
from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, Cell, Document, FontRegistry, GridSpec, LayoutContext,
    LayoutOverflowError, LayoutPart, Line, MeasuredBlock, PageProfile, Point,
    Polyline, RasterImage, Rectangle, ReportStyle, Stack, Table, Text, TextStyle,
    layout_trace, measure_block,
)


def quarter_turn(*args, **kwargs):
    assert hasattr(api, "QuarterTurn"), "QuarterTurn must be a public component"
    return api.QuarterTurn(*args, **kwargs)


@pytest.fixture
def context():
    fonts = FontRegistry()
    fonts.register("body", Path(__file__).parents[1] / "fixtures/fonts/ipaexm.ttf")
    profile = PageProfile("outer", 300, 400, GridSpec(20, 20, 10, 15, 20, 20))
    return LayoutContext(fonts, profile, ReportStyle())


class FixedBlock:
    block_id = "child"

    def __init__(self, result):
        self.result = result
        self.calls = []

    def measure(self, context, available_width):
        self.calls.append((context, available_width))
        return self.result


def drawing_block():
    return FixedBlock(MeasuredBlock(80, 10, (
        LayoutPart(3, (
            Text(10, 20, "AB", TextStyle(size=10, tracking=0.25)),
            Line(2, 3, 70, 3, 2, (0.2, 0.3, 0.4)),
            Polyline((Point(2, 5), Point(70, 5), Point(70, 25)), 2, closed=True),
            Rectangle(4, 6, 60, 20, 2, (0.4, 0.3, 0.2)),
        ), {"anchors": {"equals": [20, 40]}, "frame": {"x": 4, "y": 6}}),
        LayoutPart(2, (Text(10, 12, "CD", TextStyle(), quarter_turns=0),),
                   {"content_origin": {"x": 10, "y": 12}}),
    ), prefix=(LayoutPart(1, (Text(2, 8, "H", TextStyle(size=6)),), {"header": True}),),
        keep_with_next=True, block_id="child"))


@pytest.mark.parametrize("turns", [1, -1])
def test_rotation_measures_in_local_grid_without_scaling_and_reserves_actual_child_size(context, turns):
    child = drawing_block()
    grid = GridSpec(0, 0, 10, 10, 12, 9)
    block = quarter_turn(child, turns=turns, local_grid=grid, block_id="turned")
    measured = measure_block(block, context, 100)
    assert measured.width == 60 and measured.rows == 6 and measured.row_pitch == 15
    assert len(measured.parts) == 1 and not measured.prefix
    assert measured.keep_together and measured.keep_with_next
    assert measured.split(5) is None
    assert measured.block_id == "turned"
    local_context, available = child.calls[0]
    assert available == 120
    assert local_context.fonts is context.fonts and local_context.style is context.style
    assert local_context.profile.grid is grid
    assert local_context.profile.body_rect.width == 120
    assert local_context.profile.body_rect.height == 90
    assert child.result.rows == 6 and child.result.width == 80
    with pytest.raises(FrozenInstanceError):
        block.turns = -turns


@pytest.mark.parametrize("turns,expected", [
    (1, (
        Text(8, 78, "H", TextStyle(size=6), quarter_turns=1),
        Text(30, 70, "AB", TextStyle(size=10, tracking=0.25), quarter_turns=1),
        Line(13, 78, 13, 10, 2, (0.2, 0.3, 0.4)),
        Polyline((Point(15, 78), Point(15, 10), Point(35, 10)), 2, closed=True),
        Rectangle(16, 16, 20, 60, 2, (0.4, 0.3, 0.2)),
        Text(52, 70, "CD", TextStyle(), quarter_turns=1),
    )),
    (-1, (
        Text(52, 2, "H", TextStyle(size=6), quarter_turns=3),
        Text(30, 10, "AB", TextStyle(size=10, tracking=0.25), quarter_turns=3),
        Line(47, 2, 47, 70, 2, (0.2, 0.3, 0.4)),
        Polyline((Point(45, 2), Point(45, 70), Point(25, 70)), 2, closed=True),
        Rectangle(24, 4, 20, 60, 2, (0.4, 0.3, 0.2)),
        Text(8, 10, "CD", TextStyle(), quarter_turns=3),
    )),
])
def test_rotation_transforms_all_primitives_and_prefix_part_offsets_once(context, turns, expected):
    child = drawing_block()
    measured = measure_block(quarter_turn(child, turns=turns, local_grid=GridSpec(0, 0, 10, 10, 12, 9)), context, 100)
    assert measured.commands == expected
    assert measured.block_id == "child"


@pytest.mark.parametrize("existing,turns,combined", [(0, 1, 1), (1, 1, 2), (2, 1, 3), (3, 1, 0),
                                                         (0, -1, 3), (1, -1, 0), (2, -1, 1), (3, -1, 2)])
def test_text_orientation_composes_modulo_four(context, existing, turns, combined):
    command = Text(25, 25, "jÅ", TextStyle(tracking=0.25), quarter_turns=existing)
    child = FixedBlock(MeasuredBlock(60, 10, (LayoutPart(5, (command,)),)))
    result = measure_block(quarter_turn(child, turns=turns, local_grid=GridSpec(0, 0, 10, 10, 6, 5)), context, 100)
    text = result.commands[0]
    assert text.quarter_turns == combined
    assert text.style is command.style and text.text == command.text


@pytest.mark.parametrize("turns,matrix", [(1, (0, -1, 1, 0, 0, 80)), (-1, (0, 1, -1, 0, 60, 0))])
def test_metadata_keeps_local_child_parts_anchors_and_explicit_transform(context, turns, matrix):
    child = drawing_block()
    measured = measure_block(quarter_turn(child, turns=turns, local_grid=GridSpec(0, 0, 10, 10, 12, 9)), context, 100)
    metadata = measured.parts[0].metadata
    assert metadata["turns"] == turns
    assert metadata["local_to_part"] == matrix
    assert metadata["local_grid"] == {"origin_x": 0, "origin_y": 0, "pitch_x": 10, "pitch_y": 10, "columns": 12, "rows": 9}
    snapshot = metadata["child"]
    assert snapshot["block_id"] == "child" and snapshot["row_pitch"] == 10
    assert [p["y_pt"] for p in (*snapshot["prefix"], *snapshot["parts"])] == [0, 10, 40]
    assert snapshot["parts"][0]["metadata"]["anchors"]["equals"] == (20, 40)
    assert snapshot["parts"][0]["metadata"]["frame"] == {"x": 4, "y": 6}
    assert snapshot["parts"][1]["metadata"]["content_origin"] == {"x": 10, "y": 12}
    with pytest.raises(TypeError):
        snapshot["parts"][0]["metadata"]["anchors"]["equals"] = ()


@pytest.mark.parametrize("turns", [True, False, 0, 2, -2, 1.0, "1", None])
def test_invalid_turns_fail_explicitly(turns):
    with pytest.raises(ValueError, match="turns"):
        quarter_turn(drawing_block(), turns=turns, local_grid=GridSpec(0, 0, 10, 10, 12, 9))


@pytest.mark.parametrize("grid", [None, {}, GridSpec(1, 0, 10, 10, 12, 9), GridSpec(0, -1, 10, 10, 12, 9)])
def test_local_grid_requires_grid_spec_with_zero_origin(grid):
    with pytest.raises(ValueError, match="local_grid"):
        quarter_turn(drawing_block(), turns=1, local_grid=grid)


def test_invalid_child_and_identifier_fail_explicitly():
    grid = GridSpec(0, 0, 10, 10, 12, 9)
    for child in (None, object()):
        with pytest.raises(ValueError, match="block"):
            quarter_turn(child, turns=1, local_grid=grid)
    with pytest.raises(ValueError, match="block_id"):
        quarter_turn(drawing_block(), turns=1, local_grid=grid, block_id=None)


@pytest.mark.parametrize("result", [None, object(), MeasuredBlock(40, 9, (LayoutPart(1),)),
                                       MeasuredBlock(40, 10), MeasuredBlock(40, 10, (LayoutPart(1),)),
                                       MeasuredBlock(40, 10, (LayoutPart(1, (Text(2, 8, "  ", TextStyle(size=6)),)),))])
def test_invalid_or_no_visible_child_measurement_fails(context, result):
    child = FixedBlock(result)
    with pytest.raises(ValueError):
        measure_block(quarter_turn(child, turns=1, local_grid=GridSpec(0, 0, 10, 10, 12, 9)), context, 100)


@pytest.mark.parametrize("width", [None, True, 0, -1, float("inf")])
def test_direct_measure_validates_arguments(context, width):
    block = quarter_turn(drawing_block(), turns=1, local_grid=GridSpec(0, 0, 10, 10, 12, 9))
    with pytest.raises(ValueError, match="available_width"):
        block.measure(context, width)
    with pytest.raises(ValueError, match="context"):
        block.measure(None, 100)


@pytest.mark.parametrize("kind", ["local-width", "local-height", "outer-width", "outer-height", "ink", "stroke"])
def test_capacity_or_ink_excess_raises_layout_overflow_without_shrinking(context, kind):
    grid = GridSpec(0, 0, 10, 10, 12, 9)
    child = drawing_block()
    available = 100
    if kind == "local-width":
        grid = GridSpec(0, 0, 10, 10, 7, 9)
    elif kind == "local-height":
        grid = GridSpec(0, 0, 10, 10, 12, 5)
    elif kind == "outer-width":
        available = 59
    elif kind == "outer-height":
        context = replace(context, profile=PageProfile("short", 300, 100, GridSpec(20, 20, 10, 15, 20, 5)))
    elif kind == "ink":
        child = FixedBlock(MeasuredBlock(80, 10, (LayoutPart(3, (Text(0, 20, "jÅ", TextStyle()),)),)))
    else:
        child = FixedBlock(MeasuredBlock(80, 10, (LayoutPart(3, (Rectangle(0, 0, 80, 30, 2),)),)))
    with pytest.raises(LayoutOverflowError) as caught:
        measure_block(quarter_turn(child, turns=1, local_grid=grid, block_id="turned"), context, available)
    assert caught.value.needed is not None and caught.value.available is not None
    assert "turned" in str(caught.value)


def test_raster_image_and_unknown_commands_are_rejected(context):
    grid = GridSpec(0, 0, 10, 10, 12, 9)
    part = LayoutPart(1, (RasterImage(1, 1, 5, 5, b"encoded"),))
    with pytest.raises(ValueError, match="RasterImage"):
        measure_block(quarter_turn(FixedBlock(MeasuredBlock(80, 10, (part,))), turns=1, local_grid=grid), context, 100)
    object.__setattr__(part, "commands", (object(),))
    with pytest.raises(ValueError, match="Unsupported"):
        measure_block(quarter_turn(FixedBlock(MeasuredBlock(80, 10, (part,))), turns=1, local_grid=grid), context, 100)


def test_rotated_table_nested_in_stack_preserves_local_frames_and_page_translation(context):
    table = Table(columns=(4, 4), rows=((Cell("A"), Cell("B")),), block_id="table")
    turned = quarter_turn(table, turns=1, local_grid=GridSpec(0, 0, 10, 10, 12, 9), block_id="turned")
    pages = Document(Stack(turned, block_id="stack"), fonts=context.fonts,
                     profile=context.profile, style=context.style).layout()
    assert len(pages) == 1
    assert all(c.quarter_turns == 1 for c in pages[0].commands if isinstance(c, Text))
    trace = layout_trace(pages, context.fonts)
    assert trace["pages"][0]["commands"][0]["direction"] == [0, -1]
    # Table metadata is retained under the child's local part, never rewritten.
    placement = pages[0].metadata["placements"][0]
    assert context.profile.grid.x(placement["col"]) == 20
    assert context.profile.grid.y(placement["row"]) == 20
    rotated = placement["parts"][0]["metadata"]
    assert rotated["local_to_part"] == (0, -1, 1, 0, 0, 80)
    local_part = rotated["child"]["parts"][0]
    assert local_part["row"] == 0 and local_part["y_pt"] == 0
    assert local_part["metadata"]["cells"][0]["frame"]["x_pt"] == 0
    text = next(c for c in pages[0].commands if isinstance(c, Text))
    measured = table.measure(LayoutContext(context.fonts, PageProfile("local", 120, 90, GridSpec(0, 0, 10, 10, 12, 9)), context.style), 120)
    source = next(c for c in measured.commands if isinstance(c, Text))
    assert (text.x, text.y) == pytest.approx((20 + source.y, 20 + 80 - source.x))
