"""Selective global table boundaries, including independent part seams."""

from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import pytest

from gridlayoutpdf import (
    Cell, FontRegistry, GridSpec, LayoutContext, LayoutOverflowError, LayoutPart,
    Line, MeasuredBlock, PageProfile, Rectangle, ReportStyle, Table, Text,
    TextStyle, command_bounds, measure_block,
)


def ruled_table(*args, **kwargs):
    assert "horizontal_rules" in Table.__dataclass_fields__
    assert "vertical_rules" in Table.__dataclass_fields__
    return Table(*args, **kwargs)


def atomic_table(*args, **kwargs):
    assert "split" in Table.__dataclass_fields__, "Table needs an opt-in indivisible mode"
    return Table(*args, split=False, **kwargs)


def test_indivisible_table_merges_selected_seams_and_retains_header_source_ids(context):
    result = measure_block(atomic_table((3, 3, 3), (("", "", ""),) * 3, header_rows=1,
                           horizontal_rules=(2, .5, 0, 2), vertical_rules=(0, .5, 0, 0),
                           row_heights=(1, 2, 1), block_id="atomic"), context, 100)
    assert result.rows == 4 and len(result.parts) == 1 and result.prefix == ()
    assert result.split(3) is None
    metadata = result.parts[0].metadata
    assert metadata["source_rows"] == (0, 1, 2) and metadata["row_heights"] == (1, 2, 1)
    assert [c["cell_id"] for c in metadata["cells"]] == [f"atomic.rows[{r}].cells[{c}]" for r in range(3) for c in range(3)]
    horizontal = [c for c in result.commands if c.y1 == c.y2]
    vertical = [c for c in result.commands if c.x1 == c.x2]
    assert horizontal == [Line(1, 1, 89, 1, 2), Line(.25, 20, 89.75, 20, .5), Line(1, 79, 89, 79, 2)]
    assert vertical == [Line(30, .25, 30, 79.75, .5)]


def test_indivisible_merged_header_and_rowspan_keep_suppressed_interiors(context):
    result = measure_block(atomic_table((3, 3), (
        (Cell("", colspan=2),), (Cell("", rowspan=2), ""), ("",),
    ), header_rows=1, horizontal_rules=(2, 1, .5, 2), vertical_rules=(1, 3, 1)), context, 100)
    assert len(result.parts) == 1 and result.prefix == ()
    assert Line(30, 40, 59.75, 40, .5) in result.commands
    vertical = [line for line in result.commands if line.x1 == line.x2 == 30]
    assert vertical == [Line(30, 20, 30, 58.5, 3)]


@pytest.mark.parametrize("headers", [0, 2])
def test_indivisible_all_header_or_no_header_and_empty_tables(context, headers):
    result = atomic_table((3,), (("",), ("",)), header_rows=headers).measure(context, 100)
    assert len(result.parts) == 1 and result.prefix == () and result.split(1) is None
    empty = atomic_table((3,), (), row_heights=()).measure(context, 100)
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


def test_rules_copy_lists_validate_length_and_keep_default_none(context):
    plain = Table((3, 3), (("", ""),))
    assert getattr(plain, "horizontal_rules", "absent") is None
    assert getattr(plain, "vertical_rules", "absent") is None
    horizontal, vertical = [1, 2], [0, 0.5, 0]
    table = ruled_table((3, 3), (("", ""),), horizontal_rules=horizontal, vertical_rules=vertical)
    horizontal[0], vertical[0] = 99, 99
    assert table.horizontal_rules == (1, 2) and table.vertical_rules == (0, 0.5, 0)
    with pytest.raises(FrozenInstanceError):
        table.horizontal_rules = ()
    assert replace(plain, horizontal_rules=None, vertical_rules=None).measure(context, 100) == plain.measure(context, 100)


@pytest.mark.parametrize("field,values", [
    ("horizontal_rules", []), ("horizontal_rules", [1]), ("horizontal_rules", [1, 2, 3]),
    ("vertical_rules", []), ("vertical_rules", [1, 2]), ("vertical_rules", [1, 2, 3, 4]),
    ("horizontal_rules", 1), ("vertical_rules", False), ("horizontal_rules", "12"),
    ("horizontal_rules", [0, -1]), ("vertical_rules", [0, 0, True]),
    ("horizontal_rules", [0, float("inf")]), ("vertical_rules", [0, float("nan"), 0]),
    ("horizontal_rules", [None, 0]), ("vertical_rules", [0, "1", 0]),
])
def test_invalid_rules_are_rejected_before_measurement(field, values):
    with pytest.raises(ValueError, match=field):
        ruled_table((3, 3), (("", ""),), **{field: values})


def test_p26_pattern_omits_body_grid_and_uses_selected_stroke_widths(context):
    table = ruled_table((3, 3, 3), (("", "", ""),) * 3, header_rows=1,
                        horizontal_rules=(2, 0.5, 0, 2), vertical_rules=(0, 0.5, 0, 0))
    measured = measure_block(table, context, 100)
    # Each part independently contains its edge strokes, as in the default API.
    assert measured.rows == 3 and len(measured.prefix) == 1 and len(measured.parts) == 2
    horizontal = [line for line in measured.commands if line.y1 == line.y2]
    vertical = [line for line in measured.commands if line.x1 == line.x2]
    assert [(line.y1, line.width) for line in horizontal] == [(1, 2), (19.75, 0.5), (20.25, 0.5), (59, 2)]
    assert [(line.x1, line.width) for line in vertical] == [(30, 0.5)] * 3
    assert all(line.x1 < line.x2 for line in horizontal)
    assert not any(line.x1 == line.x2 in (0, 60, 90) for line in measured.commands)


def test_asymmetric_rules_inset_each_line_by_its_own_half_width(context):
    measured = measure_block(ruled_table((3, 3), (("", ""),),
                                         horizontal_rules=(2, 4), vertical_rules=(1, 3, 5)), context, 100)
    expected = (
        Line(1, 1, 59, 1, 2), Line(2, 18, 58, 18, 4),
        Line(0.5, 0.5, 0.5, 19.5, 1), Line(30, 1.5, 30, 18.5, 3),
        Line(57.5, 2.5, 57.5, 17.5, 5),
    )
    assert measured.commands == expected
    for command in measured.commands:
        bounds = command_bounds(command, context.fonts)
        assert bounds.x >= 0 and bounds.y >= 0 and bounds.right <= 60 and bounds.bottom <= 20


@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
def test_omitted_axis_does_not_change_other_axis_default(context, axis):
    options = {f"{axis}_rules": (0, 0) if axis == "horizontal" else (0, 0, 0)}
    result = measure_block(ruled_table((3, 3), (("", ""),), **options), context, 100)
    assert len(result.commands) == (3 if axis == "horizontal" else 2)
    assert all(line.width == 0.5 for line in result.commands)
    assert all((line.x1 == line.x2) if axis == "horizontal" else (line.y1 == line.y2) for line in result.commands)


def test_spans_suppress_selected_internal_boundaries_even_when_they_are_thick(context):
    result = measure_block(ruled_table((3, 3), (
        (Cell("", colspan=2),), (Cell("", rowspan=2), ""), ("",),
    ), header_rows=1, horizontal_rules=(2, 1, 0.5, 2), vertical_rules=(1, 3, 1)), context, 100)
    assert not any(line.x1 == line.x2 == 30 for line in result.prefix[0].commands)
    internal = [line for line in result.parts[0].commands if line.y1 == line.y2 == 20]
    assert internal == [Line(30, 20, 59.75, 20, 0.5)]
    assert result.parts[0].metadata["source_rows"] == (1, 2)


def test_zero_boundary_stays_absent_at_prefix_splits_and_adjacent_groups(context):
    table = ruled_table((3,), (("",),) * 5, header_rows=1,
                        horizontal_rules=(2, 0, 1, 0, 0, 2), vertical_rules=(0, 0))
    measured = measure_block(table, context, 100)
    head, tail = measured.split(3)
    assert head.prefix == tail.prefix == measured.prefix
    assert [p.metadata["source_rows"] for p in head.parts] == [(1,), (2,)]
    assert [p.metadata["source_rows"] for p in tail.parts] == [(3,), (4,)]
    assert tail.parts[0].commands == ()  # No closed top edge invented on this fragment.
    assert [(c.y1, c.width) for c in head.commands] == [(1, 2), (39.5, 1), (40.5, 1)]
    assert [(c.y1, c.width) for c in tail.commands] == [(1, 2), (59, 2)]


@dataclass(frozen=True)
class FixedBlock:
    width: float
    commands: tuple

    def measure(self, context, available_width):
        return MeasuredBlock(self.width, context.profile.grid.pitch_y, (LayoutPart(1, self.commands),))


def test_zero_rules_allow_ink_touching_cell_frame_but_never_exceeding_it(context):
    child = FixedBlock(30, (Rectangle(0.5, 0.5, 29, 19, 1),))
    table = ruled_table((3,), ((Cell(child, padding=0),),), horizontal_rules=(0, 0), vertical_rules=(0, 0))
    measured = measure_block(table, context, 100)
    assert measured.rows == 1 and measured.commands == child.commands
    with pytest.raises(LayoutOverflowError):
        replace(table, rows=((Cell(FixedBlock(30, (Rectangle(0, 0.5, 29, 19, 1),)), padding=0),),)).measure(context, 100)


@pytest.mark.parametrize("horizontal,vertical,allowed", [
    ((0, 0), (0, 0), True), ((2, 0), (0, 0), True),
    ((0, 0), (2, 0), True), ((4, 0), (0, 0), False),
    ((0, 0), (4, 0), False), ((0, 5), (0, 0), False),
    ((0, 0), (0, 5), False),
])
def test_content_clearance_uses_real_adjacent_strokes(context, horizontal, vertical, allowed):
    # Actual ink envelope is [3,3,26,16] in a 30x20 cell.
    content = FixedBlock(30, (Rectangle(3.5, 3.5, 22, 12, 1),))
    table = ruled_table((3,), ((Cell(content, padding=0),),), horizontal_rules=horizontal, vertical_rules=vertical)
    if allowed:
        measure_block(table, context, 100)
    else:
        with pytest.raises(LayoutOverflowError, match="clearance"):
            table.measure(context, 100)


@pytest.mark.parametrize("horizontal,vertical", [((20, 0), (0, 0)), ((0, 20), (0, 0)),
                                               ((0, 0), (30, 0)), ((0, 0), (0, 30))])
def test_rule_that_consumes_cell_dimension_is_rejected(context, horizontal, vertical):
    table = ruled_table((3,), ((Cell("", padding=0),),), horizontal_rules=horizontal, vertical_rules=vertical, block_id="thick")
    with pytest.raises(LayoutOverflowError, match="thick.*rule") as caught:
        measure_block(table, context, 100)
    assert caught.value.needed is not None and caught.value.available is not None


def test_unused_default_width_has_no_effect_when_both_axes_explicit(context):
    table = ruled_table((3,), (("",),), horizontal_rules=(0, 0), vertical_rules=(0, 0), border_width=1000)
    assert measure_block(table, context, 100).commands == ()
    assert ruled_table((3,), (), horizontal_rules=(0,), vertical_rules=(0, 0)).measure(context, 100).rows == 0


@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
@pytest.mark.parametrize("stroke,allowed", [(5, True), (6, False)])
def test_internal_boundaries_require_half_stroke_clearance(context, axis, stroke, allowed):
    content = FixedBlock(30, (Rectangle(3.5, 3.5, 22, 12, 1),))
    if axis == "vertical":
        table = ruled_table((3, 3), ((Cell(content, padding=0), Cell(content, padding=0)),),
                            horizontal_rules=(0, 0), vertical_rules=(0, stroke, 0))
    else:
        # The rowspan makes y=20 internal to one LayoutPart, not a split seam.
        table = ruled_table((3, 3), ((Cell("", rowspan=2, padding=0), Cell(content, padding=0)),
                                      (Cell(content, padding=0),)),
                            horizontal_rules=(0, stroke, 0), vertical_rules=(0, 0, 0))
    if allowed:
        measure_block(table, context, 100)
    else:
        with pytest.raises(LayoutOverflowError, match="clearance"):
            table.measure(context, 100)


@pytest.mark.parametrize("horizontal,vertical", [((10, 10), (0, 0)), ((0, 0), (15, 15))])
def test_opposing_rules_cannot_consume_even_an_empty_cell_frame(context, horizontal, vertical):
    table = ruled_table((3,), ((Cell("", padding=0),),), horizontal_rules=horizontal, vertical_rules=vertical)
    with pytest.raises(LayoutOverflowError, match="opposing rules"):
        table.measure(context, 100)


def test_fully_suppressed_rules_do_not_affect_spanned_cell_dimensions(context):
    table = ruled_table((3, 3), ((Cell("", rowspan=2, colspan=2),), ()),
                        horizontal_rules=(0, 1000, 0), vertical_rules=(0, 1000, 0))
    assert measure_block(table, context, 100).commands == ()


def test_rule_color_and_metadata_are_preserved_when_only_widths_change(context):
    plain = Table((3, 3), (("", ""),), border_color=(0.2, 0.4, 0.6))
    table = ruled_table((3, 3), (("", ""),), border_color=(0.2, 0.4, 0.6),
                        horizontal_rules=(1, 2), vertical_rules=(0, 3, 0))
    measured = measure_block(table, context, 100)
    assert measured.parts[0].metadata == plain.measure(context, 100).parts[0].metadata
    assert all(line.color == (0.2, 0.4, 0.6) for line in measured.commands)


def test_wide_horizontal_rule_cannot_reverse_a_narrow_surviving_segment(context):
    profile = PageProfile("narrow", 100, 100, GridSpec(10, 10, 1, 10, 60, 8))
    local = replace(context, profile=profile)
    table = ruled_table((1, 59), (
        (Cell("", padding=0), Cell("", padding=0, rowspan=2)), (Cell("", padding=0),),
    ), horizontal_rules=(0, 3, 0), vertical_rules=(0, 0, 0))
    with pytest.raises(LayoutOverflowError, match="rule"):
        table.measure(local, 60)


def test_wide_vertical_rule_cannot_reverse_a_short_surviving_segment(context):
    profile = PageProfile("short", 120, 100, GridSpec(10, 10, 10, 1, 10, 80))
    local = replace(context, profile=profile)
    rows = [(Cell("", padding=0, colspan=2), Cell("", padding=0, rowspan=10))]
    rows.extend((Cell("", padding=0, colspan=2),) for _ in range(8))
    rows.append((Cell("", padding=0), Cell("", padding=0)))
    table = ruled_table((3, 3, 3), rows, horizontal_rules=(0,) * 11, vertical_rules=(0, 3, 0, 0))
    with pytest.raises(LayoutOverflowError, match="rule"):
        table.measure(local, 100)
