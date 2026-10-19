"""Per-edge table borders chosen from Excel border styles (FR-022, FR-026)."""

from dataclasses import dataclass, replace
import importlib

import pytest


def api():
    return importlib.import_module("gridlayoutpdf")


@pytest.fixture
def context():
    module = api()
    profile = module.PageProfile("borders", 300, 400, module.GridSpec(20, 20, 10, 20, 20, 18))
    return module.LayoutContext(module.FontRegistry(), profile, module.ReportStyle())


def lines(commands, axis):
    module = api()
    found = [command for command in commands if isinstance(command, module.Line)]
    return [line for line in found if (line.y1 == line.y2 if axis == "h" else line.x1 == line.x2)]


@dataclass(frozen=True)
class Ink:
    """Content whose exact ink is the box (x, y, right, bottom) of its cell."""

    box: tuple
    width: float = 30

    def measure(self, context, available_width):
        module = api()
        x, y, right, bottom = self.box
        ink = module.Rectangle(x, y, right - x, bottom - y, fill=(0, 0, 0), stroke=False)
        return module.MeasuredBlock(self.width, context.profile.grid.pitch_y, (module.LayoutPart(1, (ink,)),))


# Defaults and the removed pt-width arguments.

def test_every_edge_is_thin_by_default_and_frame_lines_sit_inside_the_table(context):
    module = api()
    measured = module.measure_block(module.Table((3, 3), (("", ""),)), context, 100)
    assert measured.commands == (
        module.Line(.25, .25, 59.75, .25, .5), module.Line(.25, 19.75, 59.75, 19.75, .5),
        module.Line(.25, .25, .25, 19.75, .5), module.Line(30, .25, 30, 19.75, .5),
        module.Line(59.75, .25, 59.75, 19.75, .5),
    )
    assert module.Table((3,), (("",),)).borders == module.TableBorders()
    assert module.TableBorders().default is module.BorderStyle.THIN


@pytest.mark.parametrize("name,value", [("border_width", .5), ("horizontal_rules", (1, 1)),
                                        ("vertical_rules", (1, 1))])
def test_removed_pt_width_arguments_are_errors(name, value):
    with pytest.raises(TypeError, match=name):
        api().Table((3,), (("",),), **{name: value})


@pytest.mark.parametrize("value", [.5, 0, 2, True])
def test_a_number_is_not_a_border_style_anywhere(value):
    module = api()
    with pytest.raises(ValueError, match="pt widths are no longer accepted|BorderStyle"):
        module.Table((3,), (("",),), borders=value)
    with pytest.raises(ValueError, match="BorderStyle"):
        module.TableBorders(module.BorderStyle.THIN, horizontal={0: value})
    with pytest.raises(ValueError, match="BorderStyle"):
        module.TableBorders(module.BorderStyle.THIN, vertical_edges={(0, 0): value})


def test_one_style_or_none_stands_for_every_edge(context):
    module = api()
    table = module.Table((3,), (("",),), borders="medium")
    assert table.borders == module.TableBorders(module.BorderStyle.MEDIUM)
    assert all(line.width == 1 for line in module.measure_block(table, context, 100).commands)
    assert module.measure_block(module.Table((3,), (("",),), borders=None), context, 100).commands == ()


# Resolution: the most specific setting wins, whatever order it is written in.

def test_one_edge_beats_a_boundary_which_beats_the_frame_which_beats_the_default():
    module = api()
    style = module.BorderStyle
    borders = module.TableBorders(
        style.HAIR, outer=style.MEDIUM, horizontal={0: style.THICK, 1: None}, vertical={1: style.DOUBLE},
        horizontal_edges={(0, 1): style.DASHED, (1, 0): style.THIN}, vertical_edges={(0, 0): None})
    horizontal, vertical = borders.resolve(2, 2)
    assert horizontal == ((style.THICK, style.DASHED), (style.THIN, None), (style.MEDIUM, style.MEDIUM))
    assert vertical == ((None, style.DOUBLE, style.MEDIUM), (style.MEDIUM, style.DOUBLE, style.MEDIUM))
    reordered = module.TableBorders(
        style.HAIR, vertical_edges={(0, 0): None}, horizontal_edges={(1, 0): "thin", (0, 1): "dashed"},
        vertical={1: "double"}, horizontal={1: None, 0: "thick"}, outer="medium")
    assert reordered == borders and reordered.resolve(2, 2) == (horizontal, vertical)


def test_outer_takes_the_default_until_it_is_set_and_none_removes_the_frame():
    module = api()
    style = module.BorderStyle
    horizontal, vertical = module.TableBorders(style.HAIR).resolve(1, 1)
    assert horizontal == ((style.HAIR,), (style.HAIR,)) and vertical == ((style.HAIR, style.HAIR),)
    horizontal, vertical = module.TableBorders(style.HAIR, outer=None).resolve(2, 2)
    assert horizontal == ((None, None), (style.HAIR, style.HAIR), (None, None))
    assert vertical == ((None, style.HAIR, None),) * 2


def test_mappings_are_snapshotted_and_survive_replace():
    module = api()
    source = {1: "thin"}
    borders = module.TableBorders(None, horizontal=source)
    source[1] = "thick"
    assert borders.horizontal == ((1, module.BorderStyle.THIN),)
    assert replace(borders, default="hair").horizontal == borders.horizontal
    hash(borders)


@pytest.mark.parametrize("options,match", [
    ({"horizontal": {3: "thin"}}, "horizontal boundary 3"),
    ({"vertical": {3: "thin"}}, "vertical boundary 3"),
    ({"horizontal_edges": {(0, 2): "thin"}}, "horizontal_edges"),
    ({"horizontal_edges": {(3, 0): "thin"}}, "horizontal_edges"),
    ({"vertical_edges": {(2, 0): "thin"}}, "vertical_edges"),
    ({"vertical_edges": {(0, 3): "thin"}}, "vertical_edges"),
])
def test_indices_outside_the_table_are_rejected(options, match):
    module = api()
    with pytest.raises(ValueError, match=match):
        module.Table((3, 3), (("", ""), ("", "")), borders=module.TableBorders(**options))


@pytest.mark.parametrize("options", [
    {"horizontal": {-1: "thin"}}, {"horizontal": {True: "thin"}}, {"horizontal": [(0, "thin")]},
    {"horizontal_edges": {0: "thin"}}, {"vertical_edges": {(0,): "thin"}}, {"vertical_edges": {(0, 1.0): "thin"}},
])
def test_malformed_mappings_are_rejected(options):
    with pytest.raises(ValueError):
        api().TableBorders(**options)


def test_borders_must_be_table_borders_a_style_or_none():
    with pytest.raises(ValueError, match="BorderStyle"):
        api().Table((3,), (("",),), borders=object())


# Merged cells and partial rules.

def test_edges_inside_merged_cells_are_never_drawn(context):
    module = api()
    table = module.Table((3, 3), ((module.Cell("", colspan=2),), (module.Cell("", rowspan=2), ""), ("",)),
                         borders=module.TableBorders("thin", horizontal={1: "thick", 2: "thick"},
                                                     vertical={1: "thick"}), split=False)
    commands = module.measure_block(table, context, 100).commands
    assert not [line for line in lines(commands, "v") if line.x1 == 30 and line.y1 < 20]
    assert [line for line in lines(commands, "h") if line.y1 == 40] == [module.Line(30, 40, 59.25, 40, 1.5)]
    assert [(line.y1, line.y2) for line in lines(commands, "v") if line.x1 == 30] == [(20, 59.25)]


@pytest.mark.parametrize("options", [{"horizontal_edges": {(1, 0): "thin"}}, {"vertical_edges": {(0, 1): "thin"}}])
def test_naming_an_edge_inside_a_merged_cell_is_an_error(options):
    module = api()
    with pytest.raises(ValueError, match="inside a merged cell"):
        module.Table((3, 3), ((module.Cell("", colspan=2, rowspan=2),), ()),
                     borders=module.TableBorders(**options))


def test_a_rule_under_some_columns_only(context):
    module = api()
    borders = module.TableBorders(None, horizontal_edges={(1, 1): "thin", (1, 2): "thin"})
    table = module.Table((3, 3, 3), (("", "", ""), ("", "", "")), borders=borders, split=False)
    assert module.measure_block(table, context, 100).commands == (module.Line(30, 20, 89.75, 20, .5),)


def test_a_column_rule_beside_some_rows_only_ends_on_the_row_boundary(context):
    module = api()
    borders = module.TableBorders(None, vertical_edges={(0, 1): "thin", (2, 1): "thin"})
    table = module.Table((3, 3), (("", ""),) * 3, borders=borders, split=False)
    assert module.measure_block(table, context, 100).commands == (
        module.Line(30, .25, 30, 20, .5), module.Line(30, 40, 30, 59.75, .5))


def test_cells_record_alignment_and_the_style_of_each_of_their_edges(context):
    module = api()
    table = module.Table((3, 3), ((module.Cell("", colspan=2, valign="top"),), ("", module.Cell("1", align="right"))),
                         borders=module.TableBorders("thin", outer="medium", horizontal_edges={(1, 1): None}))
    measured = module.measure_block(table, context, 100)
    first, = measured.parts[0].metadata["cells"]
    assert (first["align"], first["valign"]) == ("left", "top")
    assert first["borders"] == {"top": ("medium", "medium"), "bottom": ("thin", None),
                                "left": ("medium",), "right": ("medium",)}
    second = measured.parts[1].metadata["cells"][1]
    assert (second["align"], second["valign"]) == ("right", "middle")
    assert second["borders"] == {"top": (None,), "bottom": ("medium",), "left": ("thin",), "right": ("medium",)}


# Splitting: one line per seam, and the page-top fragment draws its own top.

def ink(commands):
    """The exact butt-capped ink of solid lines: merged intervals per line position and width."""
    found = {}
    for line in lines(commands, "h") + lines(commands, "v"):
        horizontal = line.y1 == line.y2
        key = ("h", line.y1, line.width) if horizontal else ("v", line.x1, line.width)
        found.setdefault(key, []).append(tuple(sorted((line.x1, line.x2) if horizontal else (line.y1, line.y2))))
    merged = {}
    for key, intervals in found.items():
        result = []
        for start, stop in sorted(intervals):
            if result and start <= result[-1][1] + 1e-9:
                result[-1] = (result[-1][0], max(result[-1][1], stop))
            else:
                result.append((start, stop))
        merged[key] = [(round(a, 9), round(b, 9)) for a, b in result]
    return merged


def test_split_table_on_one_page_draws_each_seam_once_like_an_indivisible_table(context):
    module = api()
    rows = (("", ""),) * 3
    split = module.measure_block(module.Table((3, 3), rows, header_rows=1), context, 100)
    whole = module.measure_block(module.Table((3, 3), rows, header_rows=1, split=False), context, 100)
    assert len(split.prefix) == 1 and len(split.parts) == 2
    assert lines(split.commands, "h") == lines(whole.commands, "h") == [
        module.Line(.25, y, 59.75, y, .5) for y in (.25, 20, 40, 59.75)]
    assert ink(split.commands) == ink(whole.commands)


@pytest.mark.parametrize("options", [
    {"horizontal": {1: None}, "vertical_edges": {(1, 1): "medium"}},           # a line starts at the seam
    {"horizontal": {1: None}, "vertical_edges": {(0, 1): "thin", (1, 1): "thick"}},  # the style changes
    {"horizontal": {1: None, 2: None}, "vertical_edges": {(2, 1): None}},       # header over unequal rows
    {"horizontal": {2: None}, "vertical": {1: "double"}},
    {"outer": "thick", "horizontal": {1: "double"}},
])
@pytest.mark.parametrize("header_rows", [0, 1])
def test_split_table_has_the_same_solid_ink_as_an_indivisible_one(context, options, header_rows):
    module = api()
    rows = (("", ""),) * 3
    borders = module.TableBorders("thin", **options)
    split = module.measure_block(module.Table((3, 3), rows, header_rows=header_rows, borders=borders), context, 100)
    whole = module.measure_block(module.Table((3, 3), rows, header_rows=header_rows, borders=borders, split=False),
                                 context, 100)
    assert len(split.parts) + len(split.prefix) == 3
    assert ink(split.commands) == ink(whole.commands)


def test_double_and_dashed_seams_are_single_edges_too(context):
    module = api()
    borders = module.TableBorders("dashed", horizontal={1: "double"})
    measured = module.measure_block(module.Table((3,), (("",),) * 2, borders=borders), context, 100)
    assert lines(measured.commands, "h") == [
        module.Line(.25, .25, 29.75, .25, .5, dash=(3, 1.5)),
        module.Line(.25, 19.5, 29.75, 19.5, .5), module.Line(.25, 20.5, 29.75, 20.5, .5),
        module.Line(.25, 39.75, 29.75, 39.75, .5, dash=(3, 1.5))]


def small_page(rows):
    module = api()
    return module.PageProfile("small", 300, 400, module.GridSpec(20, 20, 10, 20, 20, 18), 1, 1 + rows)


def page_lines(page, axis):
    return sorted((line.y1 - 40, line.x1 - 20, line.x2 - 20, line.width) if axis == "h"
                  else (line.x1 - 20, line.y1 - 40, line.y2 - 40) for line in lines(page.commands, axis))


def test_a_fragment_at_a_page_top_draws_its_own_top_and_the_cut_closes_the_page_above():
    module = api()
    table = module.Table((3,), (("",),) * 3, borders="medium", block_id="t")
    first, second = module.Document(table, profile=small_page(2)).layout()
    assert page_lines(first, "h") == [(.5, .5, 29.5, 1), (20, .5, 29.5, 1), (39.5, .5, 29.5, 1)]
    assert page_lines(second, "h") == [(.5, .5, 29.5, 1), (19.5, .5, 29.5, 1)]
    assert page_lines(second, "v") == [(.5, .5, 19.5), (29.5, .5, 19.5)]
    for page in (first, second):
        for x in (.5, 29.5):
            segments = [(top, bottom) for left, top, bottom in page_lines(page, "v") if left == x]
            assert all(after[0] <= before[1] for before, after in zip(segments, segments[1:]))


def test_a_repeated_header_closes_the_seam_and_the_body_fragment_draws_no_second_top():
    module = api()
    borders = module.TableBorders("thin", horizontal={1: "double"})
    table = module.Table((3,), (("",),) * 4, header_rows=1, borders=borders)
    first, second = module.Document(table, profile=small_page(3)).layout()
    assert [(y, width) for y, *_, width in page_lines(first, "h")] == [
        (.25, .5), (19.5, .5), (20.5, .5), (40, .5), (59.75, .5)]
    assert [(y, width) for y, *_, width in page_lines(second, "h")] == [
        (.25, .5), (19.5, .5), (20.5, .5), (39.75, .5)]


def test_a_table_below_other_blocks_still_draws_its_top_frame():
    module = api()
    pages = module.Document(module.Spacer(1), module.Table((3,), (("",),) * 2), profile=small_page(4)).layout()
    page, = pages
    assert [y for y, *_ in page_lines(page, "h")] == [20.25, 40, 59.75]


# Clearance between cell content and every style, including double and dashed.

@pytest.mark.parametrize("style,inset", [("double", 1.5), ("mediumDashDot", 1), ("dotted", .5), ("hair", .25)])
def test_outer_edges_need_the_full_thickness_of_the_style(context, style, inset):
    module = api()
    for edge in range(4):
        box = [3, 3, 27, 17]
        box[edge] = inset + .05 if edge < 2 else (30, 20)[edge - 2] - inset - .05
        table = module.Table((3,), ((module.Cell(Ink(tuple(box)), padding=0),),), borders=style)
        module.measure_block(table, context, 100)
        box[edge] = inset - .05 if edge < 2 else (30, 20)[edge - 2] - inset + .05
        table = module.Table((3,), ((module.Cell(Ink(tuple(box)), padding=0),),), borders=style)
        with pytest.raises(module.LayoutOverflowError, match="clearance"):
            table.measure(context, 100)


@pytest.mark.parametrize("style,half", [("double", .75), ("dashed", .25), ("thick", .75)])
def test_interior_edges_need_half_the_thickness(context, style, half):
    module = api()
    borders = module.TableBorders(None, vertical={1: style})
    for right, allowed in ((30 - half - .05, True), (30 - half + .05, False)):
        cell = module.Cell(Ink((3, 3, right, 17)), padding=0)
        table = module.Table((3, 3), ((cell, ""),), borders=borders)
        if allowed:
            module.measure_block(table, context, 100)
        else:
            with pytest.raises(module.LayoutOverflowError, match="clearance"):
                table.measure(context, 100)


def test_split_seams_need_the_full_thickness_because_they_may_open_a_page(context):
    module = api()
    borders = module.TableBorders(None, horizontal={1: "double"})
    top = module.Cell(Ink((3, 3, 27, 20 - 1.45)), padding=0)
    module.measure_block(module.Table((3,), ((top,), ("",)), borders=borders, split=False), context, 100)
    with pytest.raises(module.LayoutOverflowError, match="clearance"):
        module.Table((3,), ((top,), ("",)), borders=borders).measure(context, 100)


def test_missing_edges_let_content_touch_but_never_cross_the_cell_frame(context):
    module = api()
    table = module.Table((3,), ((module.Cell(Ink((0, 0, 30, 20)), padding=0),),), borders=None)
    assert len(module.measure_block(table, context, 100).commands) == 1
    with pytest.raises(module.LayoutOverflowError):
        module.Table((3,), ((module.Cell(Ink((-.1, 0, 30, 20)), padding=0),),), borders=None).measure(context, 100)


def test_a_style_thicker_than_a_cell_is_rejected(context):
    module = api()
    profile = module.PageProfile("tiny", 100, 100, module.GridSpec(10, 10, 1, 1, 80, 80))
    tiny = replace(context, profile=profile)
    with pytest.raises(module.LayoutOverflowError, match="cell.*border thickness") as caught:
        module.Table((1,), ((module.Cell("", padding=0),),), borders="thick", block_id="t").measure(tiny, 10)
    assert (caught.value.needed, caught.value.available) == (1.5, 1)
    taller = replace(tiny, profile=module.PageProfile("taller", 100, 100, module.GridSpec(10, 10, 1, 2, 80, 40)))
    with pytest.raises(module.LayoutOverflowError, match="opposing"):
        module.Table((2,), ((module.Cell("", padding=0),),), borders="thick").measure(taller, 10)


# The fragment-edge commands of a LayoutPart.

def edge_part(**options):
    module = api()
    return module.LayoutPart(1, (module.Line(1, 5, 9, 5),), **options)


def test_measured_commands_draw_opening_or_continuing_and_closing_or_joining_by_position():
    module = api()
    line = module.Line
    parts = tuple(edge_part(opening=(line(1, 1, 9, 1),), continuing=(line(1, 0, 9, 0),),
                            joining=(line(1, 20, 9, 20),), closing=(line(1, 19, 9, 19),)) for _ in range(3))
    measured = module.MeasuredBlock(10, 20, parts)
    assert measured.commands == (line(1, 5, 9, 5), line(1, 1, 9, 1), line(1, 20, 9, 20),
                                 line(1, 25, 9, 25), line(1, 20, 9, 20), line(1, 40, 9, 40),
                                 line(1, 45, 9, 45), line(1, 40, 9, 40), line(1, 59, 9, 59))
    head, tail = measured.split(2)
    assert head.commands[-1] == line(1, 39, 9, 39)
    assert tail.commands == (line(1, 5, 9, 5), line(1, 1, 9, 1), line(1, 19, 9, 19))


def test_prefix_parts_join_the_first_body_part():
    module = api()
    line = module.Line
    header = edge_part(opening=(line(1, 1, 9, 1),), joining=(line(1, 20, 9, 20),), closing=(line(1, 19, 9, 19),))
    body = edge_part(opening=(line(2, 1, 8, 1),), continuing=(line(2, 0, 8, 0),))
    measured = module.MeasuredBlock(10, 20, (body,), prefix=(header,))
    assert measured.commands == (line(1, 5, 9, 5), line(1, 1, 9, 1), line(1, 20, 9, 20),
                                 line(1, 25, 9, 25), line(2, 20, 8, 20))


def test_only_joining_commands_may_reach_into_the_part_that_follows(context):
    module = api()

    @dataclass(frozen=True)
    class Fixed:
        part: object
        following: int = 2
        prefix: bool = False

        def measure(self, context, available_width):
            following = (module.LayoutPart(self.following), module.LayoutPart(1))
            if self.prefix:
                return module.MeasuredBlock(10, context.profile.grid.pitch_y, following, prefix=(self.part,))
            return module.MeasuredBlock(10, context.profile.grid.pitch_y, (self.part, *following))

    below = (module.Line(1, 20, 9, 20),)
    module.measure_block(Fixed(edge_part(joining=below)), context, 10)
    for name in ("opening", "closing"):
        with pytest.raises(module.LayoutOverflowError, match=name):
            module.measure_block(Fixed(edge_part(**{name: below})), context, 10)
    far = (module.Line(1, 59, 9, 59),)  # inside the next two rows, past a 1-row part
    module.measure_block(Fixed(edge_part(joining=far)), context, 10)
    with pytest.raises(module.LayoutOverflowError, match="joining"):
        module.measure_block(Fixed(edge_part(joining=far), following=1), context, 10)
    # Any body part may follow a repeated prefix after a split: the shortest one bounds it.
    with pytest.raises(module.LayoutOverflowError, match=r"prefix\[0\]\.joining"):
        module.measure_block(Fixed(edge_part(joining=far), prefix=True), context, 10)
    # Nothing follows the last body part, so its joining may not leave it.
    with pytest.raises(module.LayoutOverflowError, match="joining"):
        _measure_fixed_parts(module, context, (edge_part(joining=below),))


def test_only_continuing_commands_may_reach_up_into_the_part_before(context):
    module = api()
    above = (module.Line(1, 0, 9, 0),)
    _measure_fixed_parts(module, context, (module.LayoutPart(1), edge_part(continuing=above)))
    with pytest.raises(module.LayoutOverflowError, match="opening"):
        _measure_fixed_parts(module, context, (module.LayoutPart(1), edge_part(opening=above)))
    with pytest.raises(module.LayoutOverflowError, match="commands"):
        _measure_fixed_parts(module, context, (module.LayoutPart(1), module.LayoutPart(1, above)))
    # Nothing precedes the first part, and a 1-row part bounds how far the next one reaches.
    with pytest.raises(module.LayoutOverflowError, match=r"parts\[0\]\.continuing"):
        _measure_fixed_parts(module, context, (edge_part(continuing=above),))
    far = (module.Line(1, -21, 9, -21),)
    _measure_fixed_parts(module, context, (module.LayoutPart(2), edge_part(continuing=far)))
    with pytest.raises(module.LayoutOverflowError, match="continuing"):
        _measure_fixed_parts(module, context, (module.LayoutPart(1), edge_part(continuing=far)))

    @dataclass(frozen=True)
    class Prefixed:
        def measure(self, context, available_width):
            return module.MeasuredBlock(10, context.profile.grid.pitch_y,
                                        (module.LayoutPart(2), edge_part(continuing=far)),
                                        prefix=(module.LayoutPart(1),))

    # After a split the repeated 1-row prefix may come just before it.
    with pytest.raises(module.LayoutOverflowError, match=r"parts\[1\]\.continuing"):
        module.measure_block(Prefixed(), context, 10)


def _measure_fixed_parts(module, context, parts):
    @dataclass(frozen=True)
    class Parts:
        def measure(self, context, available_width):
            return module.MeasuredBlock(10, context.profile.grid.pitch_y, parts)

    return module.measure_block(Parts(), context, 10)


@pytest.mark.parametrize("name", ["opening", "continuing", "joining", "closing"])
def test_edge_commands_are_validated_and_indent_shifts_them(context, name):
    module = api()
    with pytest.raises(ValueError, match="commands"):
        module.LayoutPart(1, **{name: ("line",)})

    @dataclass(frozen=True)
    class Fixed:
        def measure(self, context, available_width):
            return module.MeasuredBlock(10, context.profile.grid.pitch_y,
                                        (edge_part(**{name: (module.Line(1, 2, 9, 2),)}),))

    shifted = module.measure_block(module.Indent(Fixed(), 5), context, 20)
    assert getattr(shifted.parts[0], name) == (module.Line(6, 2, 14, 2),)


def test_table_borders_survive_copy_and_pickle_with_an_unset_frame():
    import copy
    import pickle
    module = api()
    borders = module.TableBorders(module.BorderStyle.HAIR, horizontal={1: "thick"})
    for clone in (copy.deepcopy(borders), copy.copy(borders), pickle.loads(pickle.dumps(borders))):
        assert clone == borders and clone.resolve(2, 1) == borders.resolve(2, 1)
    table = module.Table((3,), (("",),), borders=borders)
    assert copy.deepcopy(table).borders == borders


def test_a_group_below_bridges_its_own_side_lines_up_to_the_boundary(context):
    module = api()
    measured = module.measure_block(module.Table((3, 3), (("", ""),) * 3, header_rows=1), context, 100)
    header, (first, second) = measured.prefix[0], measured.parts
    # The group above stops on the boundary; the one below starts there when it follows a part.
    assert [line for line in lines(header.joining, "v") if line.x1 == 30] == [module.Line(30, .25, 30, 20, .5)]
    assert [line for line in lines(header.closing, "v") if line.x1 == 30] == [module.Line(30, .25, 30, 19.75, .5)]
    assert [line for line in lines(first.commands, "v") if line.x1 == 30] == []
    assert [line for line in lines(second.commands, "v") if line.x1 == 30] == [module.Line(30, .25, 30, 19.75, .5)]
    assert [line for line in lines(second.continuing, "v") if line.x1 == 30] == [module.Line(30, 0, 30, .25, .5)]
    assert second.opening == (module.Line(.25, .25, 59.75, .25, .5),)


def test_a_repeated_header_line_keeps_clear_of_every_body_group_that_can_follow_it(context):
    module = api()
    borders = module.TableBorders("thin", horizontal={1: "thick", 2: None, 3: None})
    for top, allowed in ((.8, True), (.7, False)):
        below = (module.Cell(Ink((3, top, 27, 17)), padding=0),)
        rows = (("",), (module.Cell(Ink((3, 3, 27, 17)), padding=0),), below, below)
        table = module.Table((3,), rows, header_rows=1, borders=borders)
        if allowed:
            module.measure_block(table, context, 100)
        else:
            # Rows 2 and 3 sit under the header's 1.5 pt line after a page break.
            with pytest.raises(module.LayoutOverflowError, match=r"rows\[2\].*clearance"):
                table.measure(context, 100)


def test_edge_lines_make_a_part_visible_to_a_heading_that_keeps_with_it():
    module = api()
    table = module.Table((3,), (("",),) * 2, borders=module.TableBorders(None, horizontal={1: "thin"}), block_id="t")
    first, second = module.Document(module.Spacer(1), module.KeepWithNext(module.Rule(columns=3, block_id="keep")),
                                    table, profile=small_page(3)).layout()
    assert [placement["block_id"] for placement in first.metadata["placements"]][-2:] == ["keep", "t"]
    assert [placement["block_id"] for placement in second.metadata["placements"]] == ["t"]


def test_a_rule_on_a_fine_grid_takes_as_many_rows_as_its_thickness(context):
    module = api()
    fine = module.LayoutContext(context.fonts, module.PageProfile(
        "fine", 300, 400, module.GridSpec(20, 20, .01, .01, 20000, 30000)), context.style)
    for style, rows in (("hair", 25), ("thin", 50), ("double", 150)):
        measured = module.measure_block(module.Rule(style, columns=1000), fine, 100)
        assert measured.rows == rows


def test_leading_refuses_to_move_the_rows_of_parts_with_edge_lines(context):
    module = api()
    table = module.Table((3,), (("",),) * 3)
    with pytest.raises(ValueError, match="edge"):
        module.measure_block(module.Leading(table, 2, minimum=True), context, 100)
    assert module.measure_block(module.Leading(table, 1), context, 100).rows == 3


def test_duplicate_keys_and_other_numbers_are_reported_clearly():
    from decimal import Decimal
    from fractions import Fraction
    module = api()
    with pytest.raises(ValueError, match="duplicate"):
        module.TableBorders(horizontal=((1, "thin"), (1, "hair")))
    for value in (Decimal("0.5"), Fraction(1, 2)):
        with pytest.raises(ValueError, match="pt widths are no longer accepted"):
            module.TableBorders(value)
    with pytest.raises(ValueError, match="TableBorders"):
        module.Table((3,), (("",),), borders={"default": "thin"})


def test_outer_frame_reports_whether_it_follows_the_default():
    module = api()
    assert module.TableBorders("hair").frame is module.BorderStyle.HAIR
    assert module.TableBorders("hair", outer="thick").frame is module.BorderStyle.THICK
    assert module.TableBorders("hair", outer=None).frame is None


def test_leading_keeps_parts_whose_rows_it_does_not_change(context):
    module = api()
    tall = module.Table((3,), (("",),) * 3, row_heights=(2, 2, 2))
    kept = module.measure_block(module.Leading(tall, 1, minimum=True), context, 100)
    assert kept == module.measure_block(tall, context, 100)
    with pytest.raises(module.LayoutOverflowError, match="smaller than a measured line"):
        module.measure_block(module.Leading(tall, 1), context, 100)


@pytest.mark.parametrize("options", [{"horizontal_edges": (([0, 1], "thin"),)}, {"horizontal": (([1], "thin"),)}])
def test_unhashable_keys_in_pairs_are_value_errors_naming_the_field(options):
    name, = options
    with pytest.raises(ValueError, match=name):
        api().TableBorders(**options)


def test_a_boolean_is_not_mistaken_for_a_pt_width():
    with pytest.raises(ValueError, match=r"or None$"):
        api().TableBorders(True)


def test_the_header_lower_line_clearance_applies_only_to_the_first_row_of_each_body_group(context):
    module = api()
    borders = module.TableBorders("thin", horizontal={1: "thick", 2: None, 3: None})
    safe = module.Cell(Ink((3, 3, 27, 17)), padding=0)
    # 0.6 pt clears the header's own 0.5 pt frame; the header never lies under itself.
    header = module.Cell(Ink((3, .6, 27, 17)), padding=0)
    # Row 3 continues the group that row 2's rowspan starts, so the header never lies on it.
    inner = module.Cell(Ink((3, .1, 27, 17)), padding=0)
    table = module.Table((3, 3), ((header, ""), (safe, safe), (module.Cell("", rowspan=2), safe), (inner,)),
                         header_rows=1, borders=borders)
    measured = module.measure_block(table, context, 100)
    assert [part.metadata["source_rows"] for part in measured.parts] == [(1,), (2, 3)]


def test_a_first_part_that_draws_only_its_opening_lines_is_visible_to_a_heading():
    module = api()

    @dataclass(frozen=True)
    class OpeningOnly:
        block_id: str = "opening"

        def measure(self, context, available_width):
            first = module.LayoutPart(1, opening=(module.Line(1, 1, 9, 1),))
            rest = tuple(module.LayoutPart(1, (module.Line(1, 5, 9, 5),)) for _ in range(4))
            return module.MeasuredBlock(10, context.profile.grid.pitch_y, (first, *rest), block_id=self.block_id)

    pages = module.Document(module.Spacer(2), module.KeepWithNext(module.Rule(columns=3, block_id="keep")),
                            OpeningOnly(), profile=small_page(4)).layout()
    assert [p["block_id"] for p in pages[0].metadata["placements"]][-2:] == ["keep", "opening"]


@pytest.mark.parametrize("overhang,error", [(25, ValueError), (10, "overflow")])
def test_leading_overhang_cannot_move_edge_lines_and_a_short_overhang_overflows_first(context, overhang, error):
    module = api()
    tall = module.Table((3,), (("",),) * 3, row_heights=(2, 2, 2))
    expected = module.LayoutOverflowError if error == "overflow" else ValueError
    with pytest.raises(expected):
        module.measure_block(module.Leading(tall, 1, overhang=overhang), context, 100)


@pytest.mark.parametrize("where", ["prefix-joining", "body-continuing"])
def test_edge_only_parts_next_to_a_prefix_count_as_visible(where):
    module = api()

    @dataclass(frozen=True)
    class EdgeOnly:
        block_id: str = "edges"

        def measure(self, context, available_width):
            line = (module.Line(1, 5, 9, 5),)
            header = module.LayoutPart(1, joining=line) if where == "prefix-joining" else module.LayoutPart(1)
            first = module.LayoutPart(1, continuing=line) if where == "body-continuing" else module.LayoutPart(1)
            rest = tuple(module.LayoutPart(1) for _ in range(5)) + (module.LayoutPart(1, line),)
            return module.MeasuredBlock(10, context.profile.grid.pitch_y, (first, *rest), prefix=(header,),
                                        block_id=self.block_id)

    pages = module.Document(module.Spacer(2), module.KeepWithNext(module.Rule(columns=3, block_id="keep")),
                            EdgeOnly(), profile=small_page(5)).layout()
    assert [p["block_id"] for p in pages[0].metadata["placements"]][-2:] == ["keep", "edges"]
