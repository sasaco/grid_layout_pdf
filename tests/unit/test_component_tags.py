"""Every library component tags the commands it draws (Step 5).

Step 8 maps pages to a grid Excel sheet from the tags and the page metadata
alone, so each test reads only those, never positions or sizes.
"""

from dataclasses import replace
import importlib

from PIL import Image as PILImage
import pytest

from gridlayoutpdf.blocks import Heading, Paragraph, Rule
from gridlayoutpdf.cell_content import CellLines
from gridlayoutpdf.containers import Columns, SideRule, Stack
from gridlayoutpdf.document import Document, PageDecoration
from gridlayoutpdf.equations import Equation, EquationAnchors, EquationGroup, MathBlock, wrap_math
from gridlayoutpdf.figures import Arrow, Connector, Figure, Image, Label, TextBox, TextDiamond
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.geometry import GridSpec
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.math import BreakHint, Delimited, Fraction, Operator, Root, Row, Script, TermStop
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE, PageProfile
from gridlayoutpdf.renderers.reportlab import render_pdf
from gridlayoutpdf.rotation import QuarterTurn
from gridlayoutpdf.scene import Circle, Line, Polyline, RasterImage, Rectangle, ScenePage, Text
from gridlayoutpdf.styles import ReportStyle, TextStyle
from gridlayoutpdf.tables import Cell, Table


def semantics():
    return importlib.import_module("gridlayoutpdf.semantics")


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * 0.6, style.size * 0.8, style.size * 0.2)


FONTS = FixedFonts()
STYLE = TextStyle(size=10)
CONTEXT = LayoutContext(FONTS, A4_PORTRAIT_REFERENCE, ReportStyle(body=STYLE))
PITCH = 16.08
WIDTH = 30 * PITCH
ANCHORS = EquationAnchors(8, 18, 24, 25)


def kinds(command):
    return [scope.kind for scope in command.tag.path]


def text(commands, value):
    return next(command for command in commands if isinstance(command, Text) and command.text == value)


def small_page(rows):
    return PageProfile("small", 300, 400, GridSpec(20, 20, 10, 20, 20, 18), 2, 2 + rows)


# 1. Fractions -----------------------------------------------------------------

def test_fraction_numerator_denominator_and_bar_name_their_own_fraction_when_nested():
    s = semantics()
    commands = MathBlock(Fraction(Fraction("a", "b"), "c")).measure(CONTEXT, 200).commands
    bars = [command for command in commands if isinstance(command, Line)]
    assert {bar.tag.role for bar in bars} == {s.Role.FRACTION_BAR}
    outer, inner = sorted(bars, key=lambda bar: len(bar.tag.path))
    assert kinds(outer) == ["math_block", "fraction"] and outer.tag.scope(s.Kind.FRACTION).part == "bar"
    assert kinds(inner) == ["math_block", "fraction", "fraction"]
    a, b, c = (text(commands, value) for value in "abc")
    assert a.tag.role is s.Role.MATH and a.tag.data["atom"] == "literal"
    assert kinds(a) == ["math_block", "fraction", "fraction"]
    assert [scope.part for scope in a.tag.path[1:]] == ["numerator", "numerator"]
    assert [scope.part for scope in b.tag.path[1:]] == ["numerator", "denominator"]
    assert [scope.part for scope in c.tag.path[1:]] == ["denominator"]
    assert a.tag.key(s.Kind.FRACTION) == b.tag.key(s.Kind.FRACTION) == inner.tag.key(s.Kind.FRACTION)
    assert c.tag.key(s.Kind.FRACTION) == outer.tag.key(s.Kind.FRACTION) != inner.tag.key(s.Kind.FRACTION)


def test_row_items_are_numbered_so_sibling_fractions_stay_apart():
    s = semantics()
    commands = MathBlock(Row(Fraction("a", "b"), Operator("+"), Fraction("c", "d"))).measure(CONTEXT, 200).commands
    first, second = (command for command in commands if isinstance(command, Line))
    assert first.tag.key(s.Kind.FRACTION) != second.tag.key(s.Kind.FRACTION)
    assert first.tag.scope(s.Kind.ROW).index == 0 and second.tag.scope(s.Kind.ROW).index == 2
    plus = text(commands, "+")
    assert plus.tag.scope(s.Kind.ROW).index == 1 and plus.tag.data["atom"] == "operator"


# 2. Scripts -------------------------------------------------------------------

def test_script_base_superscript_and_subscript_nest_with_fractions_and_rows():
    s = semantics()
    commands = MathBlock(Row(Script(Fraction("a", "b"), Script("x", "n"), "i"),
                             Script(Row("p", "q"), "2"))).measure(CONTEXT, 300).commands

    def parts(value):
        return [(scope.kind, scope.part) for scope in text(commands, value).tag.path[2:]]

    assert parts("a") == [("script", "base"), ("fraction", "numerator")]
    assert parts("x") == [("script", "superscript"), ("script", "base")]
    assert parts("n") == [("script", "superscript"), ("script", "superscript")]
    assert parts("i") == [("script", "subscript")]
    assert parts("q") == [("script", "base"), ("row", None)]
    assert text(commands, "q").tag.path[-1].index == 1
    assert text(commands, "2").tag.key(s.Kind.SCRIPT) == text(commands, "p").tag.key(s.Kind.SCRIPT)
    assert text(commands, "2").tag.key(s.Kind.SCRIPT) != text(commands, "i").tag.key(s.Kind.SCRIPT)


# 3. Roots and delimiters ------------------------------------------------------

def test_root_and_delimited_polylines_name_their_sign_side_and_symbol():
    s = semantics()
    commands = MathBlock(Row(Root("x"), Delimited("y", "[", "|"))).measure(CONTEXT, 200).commands
    sign, left, right = (command for command in commands if isinstance(command, Polyline))
    assert sign.tag.role is s.Role.RADICAL and sign.tag.scope(s.Kind.ROOT).part == "sign"
    assert text(commands, "x").tag.scope(s.Kind.ROOT).part == "radicand"
    assert sign.tag.key(s.Kind.ROOT) == text(commands, "x").tag.key(s.Kind.ROOT)
    assert (left.tag.role, left.tag.scope(s.Kind.DELIMITED).part, left.tag.data["symbol"]) == (
        s.Role.DELIMITER, "left", "[")
    assert (right.tag.role, right.tag.scope(s.Kind.DELIMITED).part, right.tag.data["symbol"]) == (
        s.Role.DELIMITER, "right", "|")
    assert text(commands, "y").tag.scope(s.Kind.DELIMITED).part == "body"


# 4. Equations -----------------------------------------------------------------

def equation_parts(part):
    s = semantics()
    return [(command.text, command.tag.scope(s.Kind.EQUATION_PART).part) for command in part.commands]


def test_equation_commands_carry_equation_number_display_line_and_part():
    s = semantics()
    group = EquationGroup(Equation("A", Row("a", Operator("+"), "b"), label="(1)", result="9", unit="m"),
                          Equation("B", "c"), anchors=ANCHORS)
    first, second = measure_block(group, CONTEXT, WIDTH).parts
    assert equation_parts(first) == [
        ("(1)", "label"), ("A", "lhs"), ("=", "relation"), ("a", "rhs"), ("+", "rhs"), ("b", "rhs"),
        ("=", "result_relation"), ("9", "result"), ("m", "unit")]
    for command in first.commands:
        assert command.tag.scope(s.Kind.EQUATION).index == 0
        line = command.tag.scope(s.Kind.EQUATION_LINE)
        assert (line.index, dict(line.data)) == (0, {"continuation": False, "result_line": False})
    assert {command.tag.scope(s.Kind.EQUATION).index for command in second.commands} == {1}
    label = text(first.commands, "(1)")
    assert label.tag.role is s.Role.TEXT
    assert kinds(label) == ["equation", "equation_line", "equation_part", "paragraph"]
    relation = first.commands[2]
    assert relation.tag.role is s.Role.MATH and relation.tag.data["atom"] == "relation"
    assert text(first.commands, "+").tag.scope(s.Kind.ROW).index == 1


def test_continuation_and_result_lines_are_marked_on_their_line_scope():
    s = semantics()
    wrapped = measure_block(EquationGroup(Equation("A", Row("a", BreakHint("forced"), "b"))), CONTEXT, WIDTH)
    _, continuation = wrapped.parts
    b = text(continuation.commands, "b")
    line = b.tag.scope(s.Kind.EQUATION_LINE)
    assert (line.index, line.data["continuation"], line.data["result_line"]) == (1, True, False)
    assert b.tag.scope(s.Kind.ROW).index == 2
    result = measure_block(EquationGroup(Equation("A", "X" * 30, result="999", unit="m"), anchors=ANCHORS),
                           CONTEXT, WIDTH)
    first, final = result.parts
    assert equation_parts(first) == [("A", "lhs"), ("=", "relation"), ("X" * 30, "rhs")]
    assert equation_parts(final) == [("=", "result_relation"), ("999", "result"), ("m", "unit")]
    line = final.commands[0].tag.scope(s.Kind.EQUATION_LINE)
    assert (line.index, line.data["continuation"], line.data["result_line"]) == (1, False, True)


def test_term_columns_carry_their_column_number_and_alignment():
    s = semantics()
    rhs = Row(TermStop(), "a", Operator("+"), TermStop("right"), "bb", TermStop("center"), "c")
    part, = measure_block(EquationGroup(Equation("y", rhs)), CONTEXT, WIDTH).parts
    for value, column, align, item in (("a", 0, "left", 1), ("+", 0, "left", 2),
                                       ("bb", 1, "right", 4), ("c", 2, "center", 6)):
        command = text(part.commands, value)
        term = command.tag.scope(s.Kind.EQUATION_PART)
        assert (term.part, term.index, dict(term.data)) == ("term", column, {"align": align})
        assert command.tag.scope(s.Kind.ROW).index == item
    assert text(part.commands, "y").tag.scope(s.Kind.EQUATION_PART).part == "lhs"


def test_a_term_row_that_falls_back_to_wrapping_keeps_its_source_item_numbers():
    s = semantics()
    rhs = Row(TermStop(), "x" * 40, TermStop(), "y" * 40)
    measured = measure_block(EquationGroup(Equation("y", rhs)), CONTEXT, WIDTH)
    assert all(part.metadata.get("term_fallback") for part in measured.parts)
    commands = measured.commands
    for value, item in (("x" * 40, 1), ("y" * 40, 3)):
        command = text(commands, value)
        assert command.tag.scope(s.Kind.EQUATION_PART).part == "rhs"
        assert command.tag.scope(s.Kind.ROW).index == item


def test_wrap_math_numbers_the_top_level_row_items_it_wraps():
    s = semantics()
    lines = wrap_math(Row("a", Operator("+"), "b"), FONTS, STYLE, 200)
    assert [(command.text, command.tag.scope(s.Kind.ROW).index) for line in lines for command in line.commands] == [
        ("a", 0), ("+", 1), ("b", 2)]


# 5. Tables --------------------------------------------------------------------

def border_key(command):
    data = command.tag.data
    return data["orientation"], data["boundary"], data["first"], data["stop"]


def test_cell_content_carries_its_cell_and_cell_lines_their_line_and_alignment():
    s = semantics()
    table = Table((4, 4), (("a", Cell(CellLines(("x", "y"), align="right"), align="center")),
                           (Cell("c", colspan=2, valign="top"),)),
                  numeric_columns=(0,), block_id="t")
    commands = table.measure(CONTEXT, WIDTH).commands
    a, x, y, c = (text(commands, value) for value in "axyc")
    assert kinds(a) == ["table", "table_cell", "paragraph"]
    assert a.tag.path[0].data == {"block_id": "t"}
    assert dict(a.tag.scope(s.Kind.TABLE_CELL).data) == {
        "cell_id": "t.rows[0].cells[0]", "row": 0, "col": 0, "rowspan": 1, "colspan": 1,
        "align": "right", "valign": "middle"}
    assert a.tag.scope(s.Kind.PARAGRAPH).data["align"] == "right"
    assert x.tag.role is s.Role.MATH and kinds(x) == ["table", "table_cell", "cell_lines"]
    assert [(command.tag.scope(s.Kind.CELL_LINES).index, command.tag.scope(s.Kind.CELL_LINES).data["align"])
            for command in (x, y)] == [(0, "right"), (1, "right")]
    assert x.tag.scope(s.Kind.TABLE_CELL).data["align"] == "center"
    cell = c.tag.scope(s.Kind.TABLE_CELL).data
    assert (cell["row"], cell["col"], cell["rowspan"], cell["colspan"], cell["valign"]) == (1, 0, 1, 2, "top")


def test_table_borders_name_their_boundary_range_style_and_when_they_are_drawn():
    s = semantics()
    table = Table((4, 4), (("a", "b"), (Cell("c", colspan=2),)), block_id="t")
    lines = [command for command in table.measure(CONTEXT, WIDTH).commands if isinstance(command, Line)]
    assert {line.tag.role for line in lines} == {s.Role.TABLE_BORDER}
    assert {line.tag.path for line in lines} == {(s.Scope(s.Kind.TABLE, data={"block_id": "t"}),)}
    assert {line.tag.data["style"] for line in lines} == {"thin"}
    assert {line.tag.data["stroke"] for line in lines} == {0}
    drawn = {border_key(line): line.tag.data["drawn"] for line in lines}
    assert {key: value for key, value in drawn.items() if key[0] == "horizontal"} == {
        ("horizontal", 0, 0, 2): "always", ("horizontal", 1, 0, 2): "joining", ("horizontal", 2, 0, 2): "always"}
    assert sorted(key for key in drawn if key[0] == "vertical") == [
        ("vertical", 0, 0, 1), ("vertical", 0, 1, 2), ("vertical", 1, 0, 1),
        ("vertical", 2, 0, 1), ("vertical", 2, 1, 2)]
    vertical = [(border_key(line), line.tag.data["drawn"]) for line in lines if line.tag.data["orientation"] == "vertical"]
    assert (("vertical", 0, 1, 2), "continuing") in vertical and (("vertical", 0, 1, 2), "always") in vertical
    unsplit = Table((4, 4), (("a", "b"), (Cell("c", colspan=2),)), split=False)
    assert {line.tag.data["drawn"] for line in unsplit.measure(CONTEXT, WIDTH).commands
            if isinstance(line, Line)} == {"always"}


def test_each_stroke_of_a_double_border_is_numbered():
    s = semantics()
    lines = [command for command in Table((4,), (("a",),), borders="double").measure(CONTEXT, WIDTH).commands
             if isinstance(command, Line)]
    assert len(lines) == 8
    by_edge = {}
    for line in lines:
        assert line.tag.role is s.Role.TABLE_BORDER and line.tag.data["style"] == "double"
        by_edge.setdefault(border_key(line), []).append(line.tag.data["stroke"])
    assert all(strokes == [0, 1] for strokes in by_edge.values()) and len(by_edge) == 4


def test_a_split_seam_is_tagged_as_closing_above_and_opening_below_the_page_break():
    s = semantics()
    table = Table((3,), (("",),) * 3, borders="medium", block_id="t")
    first, second = Document(table, profile=small_page(2)).layout()
    def drawn(page):
        return {(border_key(c), c.tag.data["drawn"]) for c in page.commands
                if c.tag.data["orientation"] == "horizontal"}
    assert (("horizontal", 2, 0, 1), "closing") in drawn(first)
    assert (("horizontal", 2, 0, 1), "opening") in drawn(second)
    assert all(command.tag.role is s.Role.TABLE_BORDER for page in (first, second) for command in page.commands)


# 6. Rule and SideRule ---------------------------------------------------------

def test_rule_and_side_rule_lines_carry_their_border_style_and_stroke():
    s = semantics()
    rule = Rule("double", block_id="r").measure(CONTEXT, 100).commands
    assert [(line.tag.role, dict(line.tag.data)) for line in rule] == [
        (s.Role.RULE, {"style": "double", "stroke": 0}), (s.Role.RULE, {"style": "double", "stroke": 1})]
    dashed = SideRule(Paragraph("x"), 5, style="dashed").measure(CONTEXT, 100).commands
    bar = next(command for command in dashed if isinstance(command, Line))
    assert (bar.tag.role, dict(bar.tag.data)) == (s.Role.SIDE_RULE, {"style": "dashed", "stroke": 0})
    assert text(dashed, "x").tag.role is s.Role.TEXT
    solid = SideRule(Paragraph("x"), 5, style="double").measure(CONTEXT, 100).commands
    bars = [command for command in solid if isinstance(command, Rectangle)]
    assert [(bar.tag.role, bar.tag.data["style"], bar.tag.data["stroke"]) for bar in bars] == [
        (s.Role.SIDE_RULE, "double", 0), (s.Role.SIDE_RULE, "double", 1)]


def test_a_users_own_line_in_a_figure_is_figure_artwork_never_a_border():
    s = semantics()
    forged = Line(1, 1, 10, 1, tag=s.Tag(s.Role.TABLE_BORDER))
    line, = Figure(2, 1, forged, block_id="f").measure(CONTEXT, 100).commands
    assert line.tag.role is s.Role.FIGURE and line.tag.role not in s.BORDER_ROLES
    assert line.tag.path == (s.Scope(s.Kind.FIGURE, data={"block_id": "f"}),
                             s.Scope(s.Kind.FIGURE_ITEM, index=0, data={"kind": "line", "raw": True}))
    in_table = Table((4,), ((Cell(Figure(2, 1, Line(1, 1, 10, 1)), padding=0),),), borders=None)
    line, = in_table.measure(CONTEXT, WIDTH).commands
    assert line.tag.role is s.Role.FIGURE and kinds(line) == ["table", "table_cell", "figure", "figure_item"]


# 7. Paragraphs and headings ---------------------------------------------------

def test_paragraph_lines_keep_their_number_alignment_and_heading_flag():
    s = semantics()
    lines = Paragraph("aaa\nbbb", align="right").measure(CONTEXT, 100).commands
    assert [command.tag for command in lines] == [
        s.Tag(s.Role.TEXT, (s.Scope(s.Kind.PARAGRAPH, index=index, data={"align": "right", "heading": False}),))
        for index in range(2)]
    heading, = Heading("H").measure(CONTEXT, 100).commands
    assert heading.tag.scope(s.Kind.PARAGRAPH).data == {"align": "left", "heading": True}


# 8. Figures -------------------------------------------------------------------

def test_figure_items_name_their_number_kind_and_part():
    s = semantics()
    figure = Figure(
        10, 5,
        Line(1, 1, 10, 1), Arrow(1, 5, 30, 5), Polyline(((1, 1), (5, 5))), Rectangle(1, 1, 5, 5),
        TextBox(40, 1, 60, 40, ("p", "q"), rounded=True), TextDiamond(110, 1, 40, 40, ("d",)),
        Label(80, 70, "L", align="center"), Connector(((1, 60), (40, 60))), Text(1, 70, "t", STYLE),
        Circle(150, 60, 5), block_id="fig")
    commands = figure.measure(CONTEXT, WIDTH).commands
    assert {command.tag.role for command in commands} == {s.Role.FIGURE}
    assert {command.tag.path[0] for command in commands} == {s.Scope(s.Kind.FIGURE, data={"block_id": "fig"})}
    described = [(command.tag.path[1].index, command.tag.path[1].data["kind"], command.tag.data.get("part"))
                 for command in commands]
    assert described == [
        (0, "line", None), (1, "arrow", "shaft"), (1, "arrow", "head"), (2, "polyline", None), (3, "rect", None),
        (4, "textbox", "outline"), (4, "textbox", "text"), (4, "textbox", "text"),
        (5, "diamond", "outline"), (5, "diamond", "text"), (6, "label", "text"),
        (7, "connector", "path"), (7, "connector", "head"), (8, "text", None), (9, "circle", None)]
    raw = {command.tag.path[1].index for command in commands if command.tag.path[1].data.get("raw")}
    assert raw == {0, 2, 3, 8, 9}
    assert [command.tag.data["line"] for command in commands if command.tag.path[1].index == 4
            and command.tag.data["part"] == "text"] == [0, 1]
    assert commands[5].tag.path[1].data["rounded"] is True
    assert text(commands, "L").tag.path[1].data["align"] == "center"


def test_a_subclass_of_a_drawing_command_is_tagged_by_its_base_kind():
    s = semantics()

    class Guide(Line):
        __slots__ = ()

    line, = Figure(2, 1, Guide(1, 1, 10, 1)).measure(CONTEXT, 100).commands
    assert type(line) is Guide
    assert line.tag.path[1].data == {"kind": "line", "raw": True}
    assert line.tag.role is s.Role.FIGURE


@pytest.mark.parametrize("container", [
    lambda a, b: Columns(a, b, col_spans=(2, 2)), lambda a, b: Stack(a, b),
])
def test_two_figures_in_one_placement_have_different_identities(container):
    s = semantics()
    block = container(Figure(2, 1, Line(1, 1, 10, 1)), Figure(2, 1, Line(1, 1, 10, 1)))
    first, second = measure_block(block, CONTEXT, WIDTH).commands
    assert first.tag.key(s.Kind.FIGURE) != second.tag.key(s.Kind.FIGURE)


def test_an_image_is_tagged_as_an_image(tmp_path):
    s = semantics()
    path = tmp_path / "pixel.png"
    PILImage.new("RGB", (2, 2), "white").save(path)
    image, = Image(path, col_span=2, rows=2, block_id="img").measure(CONTEXT, WIDTH).commands
    assert isinstance(image, RasterImage)
    assert image.tag == s.Tag(s.Role.IMAGE, (), {"block_id": "img"})


# 9 and page metadata. Decorations and command ranges --------------------------

def test_page_metadata_gives_command_ranges_for_placements_parts_and_decorations():
    s = semantics()
    table = Table((3,), (("",),) * 3, borders="medium", block_id="t")
    header = PageDecoration("calc {page}/{pages}", align="center")
    footer = PageDecoration("{page}", align="right")
    pages = Document(table, profile=small_page(2), header=header, footer=footer).layout()
    assert len(pages) == 2
    for page in pages:
        cursor = 0
        for placement in page.metadata["placements"]:
            assert placement["block_type"] == "Table"
            start, stop = placement["commands"]
            assert start == cursor and stop > start
            ranges = [*placement["prefix_commands"], *placement["part_commands"]]
            assert len(placement["prefix_commands"]) == len(placement["prefix"])
            assert len(placement["part_commands"]) == len(placement["parts"])
            assert ranges[0][0] == start and ranges[-1][1] == stop
            assert all(left[1] == right[0] for left, right in zip(ranges, ranges[1:]))
            cursor = stop
        decorations = page.metadata["decorations"]
        assert decorations["header"]["commands"][0] == cursor
        assert tuple(decorations["footer"]["commands"]) == (decorations["header"]["commands"][1], len(page.commands))
        for side, decoration in (("header", header), ("footer", footer)):
            frame = decorations[side]
            assert (frame["template"], frame["align"]) == (decoration.text, decoration.align)
            start, stop = frame["commands"]
            assert stop > start
            for command in page.commands[start:stop]:
                assert command.tag.role is s.Role.TEXT
                scope = command.tag.path[0]
                assert (scope.kind, scope.part, dict(scope.data)) == (
                    "decoration", side, {"template": decoration.text, "align": decoration.align})
    # The fragment-edge lines are counted in the part that draws them.
    first, second = pages
    start, stop = first.metadata["placements"][0]["part_commands"][-1]
    assert any(command.tag.data["drawn"] == "closing" for command in first.commands[start:stop])
    start, stop = second.metadata["placements"][0]["part_commands"][0]
    assert any(command.tag.data["drawn"] == "opening" for command in second.commands[start:stop])


# 10. QuarterTurn --------------------------------------------------------------

def test_quarter_turn_records_its_turns_and_local_grid_on_every_rotated_command():
    s = semantics()
    measured = QuarterTurn(Paragraph("ab"), turns=-1, local_grid=GridSpec(0, 0, 10, 10, 4, 3),
                           block_id="q").measure(CONTEXT, 200)
    command, = measured.commands
    scope = command.tag.scope(s.Kind.QUARTER_TURN)
    assert command.tag.path[0] == scope
    assert dict(scope.data) == {"turns": -1, "block_id": "q", "local_grid": {
        "origin_x": 0, "origin_y": 0, "pitch_x": 10, "pitch_y": 10, "columns": 4, "rows": 3}}


# Tags never change the PDF ----------------------------------------------------

def test_tags_do_not_change_the_rendered_pdf(tmp_path):
    pages = Document(
        Heading("見出し"), Paragraph("本文の段落。"),
        EquationGroup(Equation("M", Fraction("a", "b"), label="(1)", result="1.0", unit="kN")),
        Table((4, 4), (("a", "b"), ("c", "d")), borders="double"), Rule("dashed"),
        SideRule(Paragraph("x"), 5), Figure(4, 2, Line(1, 1, 10, 1), TextBox(20, 2, 40, 25, ("箱",))),
        header=PageDecoration("{page}/{pages}"),
    ).layout()
    assert all(command.tag is not None for page in pages for command in page.commands)
    stripped = tuple(ScenePage(page.profile, tuple(replace(command, tag=None) for command in page.commands),
                               page.metadata) for page in pages)
    tagged_pdf, plain_pdf = tmp_path / "tagged.pdf", tmp_path / "plain.pdf"
    render_pdf(pages, tagged_pdf, invariant=True)
    render_pdf(stripped, plain_pdf, invariant=True)
    assert tagged_pdf.read_bytes() == plain_pdf.read_bytes()
