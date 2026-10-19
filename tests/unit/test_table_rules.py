"""Selective global table boundaries, including part seams drawn once."""

from dataclasses import FrozenInstanceError, dataclass, replace

import pytest

from gridlayoutpdf import (
    BorderStyle, Cell, FontRegistry, GridSpec, LayoutContext, LayoutOverflowError, LayoutPart,
    Line, MeasuredBlock, PageProfile, Rectangle, ReportStyle, Table, TableBorders,
    command_bounds, measure_block,
)


HAIR, THIN, MEDIUM = BorderStyle.HAIR, BorderStyle.THIN, BorderStyle.MEDIUM
THICK, DOUBLE = BorderStyle.THICK, BorderStyle.DOUBLE


def ruled_table(*args, horizontal=None, vertical=None, default=None, **kwargs):
    """A table with only the named boundaries ruled, like the source's selective tables."""
    return Table(*args, borders=TableBorders(default, horizontal=horizontal or {}, vertical=vertical or {}),
                 **kwargs)


def atomic_table(*args, **kwargs):
    assert "split" in Table.__dataclass_fields__, "Table needs an opt-in indivisible mode"
    return ruled_table(*args, split=False, **kwargs)


def all_lines(part):
    return [*part.commands, *part.opening, *part.joining, *part.closing]


def test_indivisible_table_merges_selected_seams_and_retains_header_source_ids(context):
    result = measure_block(atomic_table((3, 3, 3), (("", "", ""),) * 3, header_rows=1,
                           horizontal={0: THICK, 1: THIN, 3: THICK}, vertical={1: THIN},
                           row_heights=(1, 2, 1), block_id="atomic"), context, 100)
    assert result.rows == 4 and len(result.parts) == 1 and result.prefix == ()
    assert result.split(3) is None
    metadata = result.parts[0].metadata
    assert metadata["source_rows"] == (0, 1, 2) and metadata["row_heights"] == (1, 2, 1)
    assert [c["cell_id"] for c in metadata["cells"]] == [f"atomic.rows[{r}].cells[{c}]" for r in range(3) for c in range(3)]
    horizontal = [c for c in result.commands if c.y1 == c.y2]
    vertical = [c for c in result.commands if c.x1 == c.x2]
    assert horizontal == [Line(.75, .75, 89.25, .75, 1.5), Line(.25, 20, 89.75, 20, .5),
                          Line(.75, 79.25, 89.25, 79.25, 1.5)]
    assert vertical == [Line(30, .25, 30, 79.75, .5)]


def test_indivisible_merged_header_and_rowspan_keep_suppressed_interiors(context):
    result = measure_block(atomic_table((3, 3), (
        (Cell("", colspan=2),), (Cell("", rowspan=2), ""), ("",),
    ), header_rows=1, horizontal={0: THICK, 1: MEDIUM, 2: THIN, 3: THICK},
        vertical={0: MEDIUM, 1: THICK, 2: MEDIUM}), context, 100)
    assert len(result.parts) == 1 and result.prefix == ()
    assert Line(30, 40, 59.75, 40, .5) in result.commands
    vertical = [line for line in result.commands if line.x1 == line.x2 == 30]
    assert vertical == [Line(30, 20, 30, 59.25, 1.5)]


@pytest.mark.parametrize("headers", [0, 2])
def test_indivisible_all_header_or_no_header_and_empty_tables(context, headers):
    result = Table((3,), (("",), ("",)), header_rows=headers, split=False).measure(context, 100)
    assert len(result.parts) == 1 and result.prefix == () and result.split(1) is None
    empty = Table((3,), (), row_heights=(), split=False).measure(context, 100)
    assert empty.rows == 0 and not empty.parts


@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_split_option_rejects_non_boolean(value):
    assert "split" in Table.__dataclass_fields__
    with pytest.raises(ValueError, match="split"):
        Table((3,), (("",),), split=value)


@pytest.fixture
def context():
    fonts = FontRegistry()
    return LayoutContext(fonts, PageProfile("rules", 300, 400, GridSpec(20, 20, 10, 20, 20, 18)), ReportStyle())


def test_borders_copy_mappings_validate_and_default_to_thin(context):
    plain = Table((3, 3), (("", ""),))
    assert plain.borders == TableBorders() and plain.borders.default is THIN
    horizontal = {0: "thick", 1: None}
    table = Table((3, 3), (("", ""),), borders=TableBorders(horizontal=horizontal))
    horizontal[0] = "hair"
    assert table.borders.horizontal == ((0, THICK), (1, None))
    with pytest.raises(FrozenInstanceError):
        table.borders = TableBorders()
    with pytest.raises(FrozenInstanceError):
        table.borders.default = THICK
    assert replace(plain, borders=TableBorders()).measure(context, 100) == plain.measure(context, 100)


@pytest.mark.parametrize("borders", [
    [], 1, False, "12", .5, (THIN,), TableBorders(horizontal={2: THIN}), TableBorders(vertical={3: THIN}),
    TableBorders(horizontal_edges={(0, 2): THIN}), TableBorders(vertical_edges={(1, 0): THIN}),
])
def test_invalid_borders_are_rejected_before_measurement(borders):
    with pytest.raises(ValueError, match="borders|BorderStyle"):
        Table((3, 3), (("", ""),), borders=borders)


def test_p26_pattern_omits_body_grid_and_draws_the_selected_styles(context):
    table = ruled_table((3, 3, 3), (("", "", ""),) * 3, header_rows=1,
                        horizontal={0: THICK, 1: THIN, 3: THICK}, vertical={1: THIN})
    measured = measure_block(table, context, 100)
    # Each part keeps its lines inside itself; the header's lower seam is drawn once.
    assert measured.rows == 3 and len(measured.prefix) == 1 and len(measured.parts) == 2
    horizontal = [line for line in measured.commands if line.y1 == line.y2]
    vertical = [line for line in measured.commands if line.x1 == line.x2]
    assert [(line.y1, line.width) for line in horizontal] == [(.75, 1.5), (20, .5), (59.25, 1.5)]
    # Three row groups; the two below another one bridge their top half stroke.
    assert [(line.x1, line.width) for line in vertical] == [(30, 0.5)] * 5
    assert all(line.x1 < line.x2 for line in horizontal)
    assert not any(line.x1 == line.x2 in (0, 60, 90) for line in measured.commands)


def test_asymmetric_rules_inset_each_line_by_its_own_thickness(context):
    measured = measure_block(ruled_table((3, 3), (("", ""),), horizontal={0: THICK, 1: MEDIUM},
                                         vertical={0: HAIR, 1: THIN, 2: DOUBLE}), context, 100)
    expected = (
        Line(.75, .75, 59.25, .75, 1.5), Line(.5, 19.5, 59.5, 19.5, 1),
        Line(.125, .125, .125, 19.875, .25), Line(30, .25, 30, 19.75, .5),
        Line(58.75, .25, 58.75, 19.75, .5), Line(59.75, .25, 59.75, 19.75, .5),
    )
    assert measured.commands == expected
    for command in measured.commands:
        bounds = command_bounds(command, context.fonts)
        assert bounds.x >= 0 and bounds.y >= 0 and bounds.right <= 60 and bounds.bottom <= 20


@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
def test_omitted_axis_does_not_change_other_axis_default(context, axis):
    options = {axis: {0: None, 1: None} if axis == "horizontal" else {0: None, 1: None, 2: None}}
    result = measure_block(Table((3, 3), (("", ""),), borders=TableBorders(**options)), context, 100)
    assert len(result.commands) == (3 if axis == "horizontal" else 2)
    assert all(line.width == 0.5 for line in result.commands)
    assert all((line.x1 == line.x2) if axis == "horizontal" else (line.y1 == line.y2) for line in result.commands)


def test_spans_suppress_selected_internal_boundaries_even_when_they_are_thick(context):
    result = measure_block(ruled_table((3, 3), (
        (Cell("", colspan=2),), (Cell("", rowspan=2), ""), ("",),
    ), header_rows=1, horizontal={0: THICK, 1: MEDIUM, 2: THIN, 3: THICK},
        vertical={0: MEDIUM, 1: THICK, 2: MEDIUM}), context, 100)
    assert not any(line.x1 == line.x2 == 30 for line in all_lines(result.prefix[0]))
    internal = [line for line in all_lines(result.parts[0]) if line.y1 == line.y2 == 20]
    assert internal == [Line(30, 20, 59.75, 20, 0.5)]
    assert result.parts[0].metadata["source_rows"] == (1, 2)


def test_absent_boundary_stays_absent_at_prefix_splits_and_adjacent_groups(context):
    table = ruled_table((3,), (("",),) * 5, header_rows=1, horizontal={0: THICK, 2: MEDIUM, 5: THICK})
    measured = measure_block(table, context, 100)
    head, tail = measured.split(3)
    assert head.prefix == tail.prefix == measured.prefix
    assert [p.metadata["source_rows"] for p in head.parts] == [(1,), (2,)]
    assert [p.metadata["source_rows"] for p in tail.parts] == [(3,), (4,)]
    assert all_lines(tail.parts[0]) == []  # No closed top edge invented on this fragment.
    assert [(c.y1, c.width) for c in head.commands] == [(.75, 1.5), (40, 1)]
    assert [(c.y1, c.width) for c in tail.commands] == [(.75, 1.5), (59.25, 1.5)]


@dataclass(frozen=True)
class FixedBlock:
    width: float
    commands: tuple

    def measure(self, context, available_width):
        return MeasuredBlock(self.width, context.profile.grid.pitch_y, (LayoutPart(1, self.commands),))


def test_absent_rules_allow_ink_touching_cell_frame_but_never_exceeding_it(context):
    child = FixedBlock(30, (Rectangle(0.5, 0.5, 29, 19, 1),))
    table = Table((3,), ((Cell(child, padding=0),),), borders=None)
    measured = measure_block(table, context, 100)
    assert measured.rows == 1 and measured.commands == child.commands
    with pytest.raises(LayoutOverflowError):
        replace(table, rows=((Cell(FixedBlock(30, (Rectangle(0, 0.5, 29, 19, 1),)), padding=0),),)).measure(context, 100)


@pytest.mark.parametrize("horizontal,vertical,allowed", [
    ({}, {}, True), ({0: MEDIUM}, {}, True), ({}, {0: MEDIUM}, True),
    ({0: THICK}, {}, False), ({}, {0: THICK}, False),
    ({1: THICK}, {}, False), ({}, {1: THICK}, False),
])
def test_content_clearance_uses_real_adjacent_strokes(context, horizontal, vertical, allowed):
    # Actual ink envelope is [1.2, 1.2, 28.6, 18.6] in a 30x20 cell.
    content = FixedBlock(30, (Rectangle(1.7, 1.7, 26.4, 16.4, 1),))
    table = ruled_table((3,), ((Cell(content, padding=0),),), horizontal=horizontal, vertical=vertical)
    if allowed:
        measure_block(table, context, 100)
    else:
        with pytest.raises(LayoutOverflowError, match="clearance"):
            table.measure(context, 100)


def tiny_context(context, pitch_x=1, pitch_y=1):
    grid = GridSpec(10, 10, pitch_x, pitch_y, int(80 / pitch_x), int(80 / pitch_y))
    return replace(context, profile=PageProfile("tiny", 100, 100, grid))


@pytest.mark.parametrize("horizontal,vertical", [({0: THICK}, {}), ({1: THICK}, {}),
                                               ({}, {0: THICK}), ({}, {1: THICK})])
def test_style_that_consumes_cell_dimension_is_rejected(context, horizontal, vertical):
    table = ruled_table((1,), ((Cell(FixedBlock(1, ()), padding=0),),), horizontal=horizontal,
                        vertical=vertical, block_id="thick")
    with pytest.raises(LayoutOverflowError, match="thick.*border thickness") as caught:
        measure_block(table, tiny_context(context), 10)
    assert caught.value.needed == 1.5 and caught.value.available == 1


def test_a_default_that_every_boundary_overrides_has_no_effect(context):
    table = ruled_table((3,), (("",),), horizontal={0: None, 1: None}, vertical={0: None, 1: None}, default=THICK)
    assert measure_block(table, context, 100).commands == ()
    assert ruled_table((3,), (), horizontal={0: None}).measure(context, 100).rows == 0


@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
@pytest.mark.parametrize("style,allowed", [(MEDIUM, True), (THICK, False)])
def test_internal_boundaries_require_half_stroke_clearance(context, axis, style, allowed):
    # Ink [0.7, 0.7, 29.3, 19.3]: 0.7 pt from the cell edge, between medium's and thick's halves.
    content = FixedBlock(30, (Rectangle(1.2, 1.2, 27.6, 17.6, 1),))
    if axis == "vertical":
        table = ruled_table((3, 3), ((Cell(content, padding=0), Cell(content, padding=0)),), vertical={1: style})
    else:
        # The rowspan makes y=20 internal to one LayoutPart, not a split seam.
        table = ruled_table((3, 3), ((Cell("", rowspan=2, padding=0), Cell(content, padding=0)),
                                      (Cell(content, padding=0),)), horizontal={1: style})
    if allowed:
        measure_block(table, context, 100)
    else:
        with pytest.raises(LayoutOverflowError, match="clearance"):
            table.measure(context, 100)


@pytest.mark.parametrize("horizontal,vertical", [({0: THICK, 1: THICK}, {}), ({}, {0: THICK, 1: THICK})])
def test_opposing_rules_cannot_consume_even_an_empty_cell_frame(context, horizontal, vertical):
    table = ruled_table((2,), ((Cell(FixedBlock(2, ()), padding=0),),), horizontal=horizontal, vertical=vertical)
    with pytest.raises(LayoutOverflowError, match="opposing rules"):
        table.measure(tiny_context(context, 1, 2), 10)


def test_fully_suppressed_rules_do_not_affect_spanned_cell_dimensions(context):
    table = ruled_table((3, 3), ((Cell("", rowspan=2, colspan=2),), ()),
                        horizontal={0: None, 1: THICK, 2: None}, vertical={0: None, 1: THICK, 2: None})
    assert measure_block(table, context, 100).commands == ()


def test_rule_color_and_metadata_are_preserved_when_only_styles_change(context):
    plain = Table((3, 3), (("", ""),), border_color=(0.2, 0.4, 0.6))
    table = ruled_table((3, 3), (("", ""),), horizontal={0: MEDIUM, 1: THICK}, vertical={1: DOUBLE},
                        border_color=(0.2, 0.4, 0.6))
    measured = measure_block(table, context, 100)

    def without_borders(metadata):
        return {**metadata, "cells": [{k: v for k, v in cell.items() if k != "borders"}
                                      for cell in metadata["cells"]]}

    assert without_borders(measured.parts[0].metadata) == without_borders(plain.measure(context, 100).parts[0].metadata)
    assert all(line.color == (0.2, 0.4, 0.6) for line in measured.commands)


def test_wide_horizontal_rule_cannot_reverse_a_narrow_surviving_segment(context):
    profile = PageProfile("narrow", 100, 100, GridSpec(10, 10, 1, 10, 60, 8))
    local = replace(context, profile=profile)
    table = ruled_table((1, 59), (
        (Cell("", padding=0), Cell("", padding=0, rowspan=2)), (Cell("", padding=0),),
    ), horizontal={1: THICK})
    with pytest.raises(LayoutOverflowError, match="border"):
        table.measure(local, 60)


def test_wide_vertical_rule_cannot_reverse_a_short_surviving_segment(context):
    profile = PageProfile("short", 120, 100, GridSpec(10, 10, 10, 1, 10, 80))
    local = replace(context, profile=profile)
    rows = [(Cell("", padding=0, colspan=2), Cell("", padding=0, rowspan=10))]
    rows.extend((Cell("", padding=0, colspan=2),) for _ in range(8))
    rows.append((Cell("", padding=0), Cell("", padding=0)))
    table = ruled_table((3, 3, 3), rows, vertical={1: THICK})
    with pytest.raises(LayoutOverflowError, match="border"):
        table.measure(local, 100)
