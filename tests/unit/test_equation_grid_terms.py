"""Term columns assigned in whole grid columns (FR-025, EquationGroup(term_columns="grid"))."""

import hashlib
import math

import pytest

from gridlayoutpdf import equations
from gridlayoutpdf.document import Document
from gridlayoutpdf.equations import Equation, EquationAnchors, EquationGroup
from gridlayoutpdf.errors import LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.math import BreakHint, Fraction, Operator, Row, Script, TermStop
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.scene import Text
from gridlayoutpdf.semantics import Kind
from gridlayoutpdf.styles import ReportStyle, TextStyle


class FixedFonts(FontRegistry):
    def measure(self, text, style):
        return TextMetrics(len(text) * style.size * 0.6, style.size * 0.8, style.size * 0.2)


FONTS = FixedFonts()
CONTEXT = LayoutContext(FONTS, A4_PORTRAIT_REFERENCE, ReportStyle())
PITCH = 16.08
WIDTH = 30 * PITCH
PAD = 2.4  # one side, 10 pt text
# RHS starts at column 9 (first_equal 8 + "=" half 3 + gap 4); the result relation at column 24
# leaves the normal RHS region up to column 23 (14 columns); the full RHS region is 21 columns.
ANCHORS = EquationAnchors(8, 24, 28, 29)
RHS_COLUMN = 9


def find_text(part, text):
    return next(command for command in part.commands if isinstance(command, Text) and command.text == text)


def texts(part, text):
    return [command for command in part.commands if isinstance(command, Text) and command.text == text]


def grid(*equations_, **options):
    return EquationGroup(*equations_, term_columns="grid", **options)


def substitution(first, operator, second, third):
    return Row(first, TermStop("center"), Operator(operator), TermStop("right"), second,
               TermStop("center"), Operator(operator), TermStop("right"), third, gap=0)


# --- the padding constant and function ---------------------------------------------------------

def test_cell_padding_constant_and_function_cover_larger_text():
    assert equations.EXCEL_CELL_PADDING_PT == 2.4
    pad = equations.excel_cell_padding_pt
    assert pad(10) == 2.4 and pad(12.0) == 2.4 and pad(6.5) == 2.4
    assert pad(14) == pytest.approx(2.8) and pad(24) == pytest.approx(4.8)
    assert isinstance(pad(10), float)


@pytest.mark.parametrize("size", [0, -1, float("nan"), float("inf"), True, "10", None])
def test_cell_padding_function_rejects_invalid_sizes(size):
    with pytest.raises(ValueError, match="size"):
        equations.excel_cell_padding_pt(size)


# --- option validation --------------------------------------------------------------------------

def test_term_columns_default_and_values():
    assert EquationGroup().term_columns == "packed"
    assert EquationGroup(term_columns="grid").term_columns == "grid"
    assert EquationGroup(term_columns="packed", term_gap=3).term_gap == 3


@pytest.mark.parametrize("value", ["Grid", "pt", "", None, 1, True])
def test_term_columns_rejects_unknown_values(value):
    with pytest.raises(ValueError, match="term_columns"):
        EquationGroup(term_columns=value)


def test_term_gap_is_rejected_with_grid_term_columns():
    with pytest.raises(ValueError, match="term_gap"):
        EquationGroup(term_columns="grid", term_gap=0)


# --- columns start at grid boundaries and use the fewest columns ---------------------------------

def test_each_term_starts_at_a_column_boundary_with_the_fewest_columns():
    group = grid(
        Equation("kv", substitution("5.1", "x", "0.5", "68600"), result="1", unit="m"),
        Equation("kh", substitution("5.1", "xx", "10.25", "6"), result="2", unit="m"),
        anchors=ANCHORS,
    )
    first, second = measure_block(group, CONTEXT, WIDTH).parts
    # Widest terms + 2 x 2.4 pt: 18 -> 2, ops 12 -> 2, 30 -> 3, ops 12 -> 2, 30 -> 3 columns.
    expected = ((9, 2, "left"), (11, 2, "center"), (13, 3, "right"), (16, 2, "center"), (18, 3, "right"))
    assert first.metadata["term_columns_grid"] == expected
    assert second.metadata["term_columns_grid"] == expected
    assert first.metadata["term_cell_padding_pt"] == PAD
    pts = first.metadata["term_columns_pt"]
    assert [(left, width, align) for left, width, align in pts] == [
        (pytest.approx(start * PITCH), pytest.approx(count * PITCH), align) for start, count, align in expected]
    # Every column's left edge is an integer column from the block's left edge.
    for left, _, _ in pts:
        assert left / PITCH == pytest.approx(round(left / PITCH), abs=1e-9)
    # Terms sit inside their columns, padded like an Excel cell.
    assert find_text(first, "5.1").x == pytest.approx(9 * PITCH + PAD)
    assert find_text(first, "0.5").x + 18 == pytest.approx(16 * PITCH - PAD)
    assert find_text(second, "10.25").x + 30 == pytest.approx(16 * PITCH - PAD)
    assert find_text(first, "68600").x + 30 == pytest.approx(21 * PITCH - PAD)
    assert find_text(second, "6").x + 6 == pytest.approx(21 * PITCH - PAD)
    assert [c.x + 3 for c in texts(first, "x")] == pytest.approx([12 * PITCH, 17 * PITCH])
    assert [c.x + 6 for c in texts(second, "xx")] == pytest.approx([12 * PITCH, 17 * PITCH])
    # The result keeps its anchors on the same line.
    assert [c.text for c in first.commands][-3:] == ["=", "1", "m"]
    assert not first.metadata["result_line"]


@pytest.mark.parametrize("columns", [1, 2, 3, 5])
def test_column_count_is_the_smallest_that_holds_the_widest_term_and_padding(columns):
    for need in (columns * PITCH, columns * PITCH - 0.01, (columns - 1) * PITCH + 0.01):
        content = need - 2 * PAD
        if content <= 0:
            continue
        rhs = Row("a", TermStop("left", width=content), "b", gap=0)
        part, = measure_block(grid(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
        _, count, _ = part.metadata["term_columns_grid"][1]
        assert count * PITCH >= content + 2 * PAD - 1e-9
        assert (count - 1) * PITCH < content + 2 * PAD
        assert count == columns


def test_exact_fit_does_not_take_an_extra_column():
    content = 2 * PITCH - 2 * PAD
    part, = measure_block(grid(Equation("A", Row("a", TermStop(width=content), "b", gap=0)),
                               anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert part.metadata["term_columns_grid"][1][1] == 2


def test_empty_terms_take_no_columns_and_a_leading_stop_sets_column_zero():
    rhs = Row(TermStop("right", width=30), "abc", TermStop(), TermStop("center"), "d", gap=0)
    part, = measure_block(grid(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert part.metadata["term_columns_grid"] == ((9, 3, "right"), (12, 0, "left"), (12, 1, "center"))
    assert find_text(part, "abc").x + 18 == pytest.approx(12 * PITCH - PAD)
    assert find_text(part, "d").x + 3 == pytest.approx(12.5 * PITCH)


def test_each_equation_pads_its_terms_by_its_own_text_size():
    big = TextStyle(size=14)
    group = grid(Equation("A", Row("0.5", TermStop("right"), "1", gap=0), style=big),
                 Equation("B", Row("0.5", TermStop("right"), "1", gap=0)), anchors=ANCHORS)
    large, small = measure_block(group, CONTEXT, WIDTH).parts
    # 14 pt: "0.5" is 25.2 pt + 2 x 2.8 = 30.8 -> 2 columns; 10 pt needs 18 + 4.8 -> 2 columns.
    assert large.metadata["term_columns_grid"] == ((9, 2, "left"), (11, 1, "right"))
    assert large.metadata["term_cell_padding_pt"] == pytest.approx(2.8)
    assert small.metadata["term_cell_padding_pt"] == PAD
    assert find_text(large, "0.5").x == pytest.approx(9 * PITCH + 2.8)
    assert find_text(small, "0.5").x == pytest.approx(9 * PITCH + PAD)
    assert find_text(large, "1").x + 8.4 == pytest.approx(12 * PITCH - 2.8)


def test_math_terms_take_contiguous_whole_columns():
    rhs = Row(Fraction("12.5", "3"), TermStop("center"), Operator("+"), TermStop("right"),
              Script("2.70", superscript="3"), gap=0)
    part, = measure_block(grid(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    starts = [start for start, _, _ in part.metadata["term_columns_grid"]]
    counts = [count for _, count, _ in part.metadata["term_columns_grid"]]
    assert starts[0] == RHS_COLUMN and starts[1] == starts[0] + counts[0] and starts[2] == starts[1] + counts[1]
    for left, width, _ in part.metadata["term_columns_pt"]:
        assert width / PITCH == pytest.approx(round(width / PITCH))


# --- tags and metadata -----------------------------------------------------------------------------

def test_terms_keep_their_tags_and_the_metadata_is_parallel():
    rhs = Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75", gap=0)
    part, = measure_block(grid(Equation("S", rhs, result="21.25", unit="kN"), anchors=ANCHORS),
                          CONTEXT, WIDTH).parts
    terms = {}
    for command in part.commands:
        scope = next((s for s in command.tag.path if s.kind is Kind.EQUATION_PART), None)
        if scope is not None and scope.part == "term":
            terms.setdefault(scope.index, set()).add((command.text, scope.data["align"]))
    assert terms == {0: {("12.50", "left")}, 1: {("+", "center")}, 2: {("8.75", "right")}}
    grid_columns = part.metadata["term_columns_grid"]
    assert len(grid_columns) == len(part.metadata["term_columns_pt"]) == 3
    assert [align for _, _, align in grid_columns] == ["left", "center", "right"]
    assert part.metadata["rhs_start_pt"] == pytest.approx(RHS_COLUMN * PITCH)


def test_packed_metadata_has_no_grid_keys():
    part, = measure_block(EquationGroup(Equation("A", Row("a", TermStop(), "b")), anchors=ANCHORS),
                          CONTEXT, WIDTH).parts
    assert "term_columns_pt" in part.metadata
    assert "term_columns_grid" not in part.metadata and "term_cell_padding_pt" not in part.metadata


# --- fitting and fallback (same rules as packed columns) -----------------------------------------------

def test_grid_line_too_wide_for_normal_region_moves_result_to_its_own_line():
    narrow = EquationAnchors(8, 18, 24, 25)  # normal region: columns 9-16 (8), full: 21
    rhs = Row("X" * 20, TermStop("right"), "YYYYY", gap=0)  # 120 -> 8 columns, 30 -> 3 columns
    first, final = measure_block(grid(Equation("A", rhs, result="9", unit="m"), anchors=narrow),
                                 CONTEXT, WIDTH).parts
    assert first.metadata["term_columns_grid"] == ((9, 8, "left"), (17, 3, "right"))
    assert [c.text for c in final.commands] == ["=", "9", "m"]
    assert final.metadata["result_line"]
    assert final.metadata["term_columns_grid"] == first.metadata["term_columns_grid"]


def test_grid_columns_that_exceed_the_full_region_fall_back_to_wrapping():
    # 22 one-character terms: packed 22 x 6 + 21 x 4 = 216 pt fits the full region (21 columns),
    # but each grid term takes a whole column (6 + 2 x 2.4 pt), 22 columns > 21.
    items = []
    for number in range(22):
        items.extend((TermStop(),) if number else ())
        items.append("1")
    rhs = Row(*items, gap=0)
    packed, = measure_block(EquationGroup(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert "term_fallback" not in packed.metadata
    parts = measure_block(grid(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert all(part.metadata["term_fallback"] is True for part in parts)
    assert all("term_columns_grid" not in part.metadata and "term_columns_pt" not in part.metadata
               for part in parts)
    assert [c.text for c in parts[0].commands] == ["A", "="] + ["1"] * 22
    # A row that falls back in both modes is laid out exactly as the packed fallback:
    # ordinary wrapping with an allowed break at each stop (132 + 6 + 210 + 8 > 337.68 pt).
    long = Row("X" * 22, TermStop("center"), Operator("+"), TermStop("right"), "Y" * 35, gap=0)
    gridded = measure_block(grid(Equation("A", long, result="9", unit="m"), anchors=ANCHORS), CONTEXT, WIDTH)
    packed_long = measure_block(EquationGroup(Equation("A", long, result="9", unit="m"), anchors=ANCHORS),
                                CONTEXT, WIDTH)
    assert all(part.metadata["term_fallback"] for part in gridded.parts)
    assert gridded.parts == packed_long.parts


def test_fallback_row_does_not_widen_the_other_rows_grid_columns():
    short = Row("a", TermStop("right"), "bb", gap=0)
    long = Row("Z" * 40, TermStop("right"), "Y" * 30, gap=0)
    group = grid(Equation("A", short), Equation("B", long), anchors=ANCHORS)
    short_part, *long_parts = measure_block(group, CONTEXT, WIDTH).parts
    assert short_part.metadata["term_columns_grid"] == ((9, 1, "left"), (10, 2, "right"))
    assert all(part.metadata["term_fallback"] for part in long_parts)


def test_rows_that_fit_alone_but_not_in_shared_grid_columns_both_fall_back():
    first_row = Row("Z" * 30, TermStop(), "a", gap=0)   # alone 12 + 1 columns
    second_row = Row("a", TermStop(), "Y" * 30, gap=0)  # alone 1 + 12; shared 12 + 12 > 21
    first, second = measure_block(grid(Equation("A", first_row), Equation("B", second_row),
                                       anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert first.metadata["term_fallback"] and second.metadata["term_fallback"]


def test_break_hints_take_no_space_in_fitting_grid_rows():
    hinted = Row("a", TermStop(), "b", BreakHint(), "c", gap=1)
    plain = Row("a", TermStop(), "b", "c", gap=1)

    def parts(rhs):
        return measure_block(grid(Equation("A", rhs, result="1", unit="m"), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert parts(hinted) == parts(plain)


def test_grid_fallback_overflow_names_the_source_term():
    rhs = Row("X" * 60, TermStop("right"), "Y" * 10, gap=0)
    with pytest.raises(LayoutOverflowError) as caught:
        grid(Equation("A", rhs, block_id="wide"), anchors=ANCHORS).measure(CONTEXT, WIDTH)
    assert caught.value.block_id == "wide.rhs[0]"


def test_conflicting_alignment_is_still_an_error_with_grid_columns():
    group = grid(Equation("A", Row("a", TermStop("right"), "b")), Equation("B", Row("a", TermStop("left"), "b")),
                 anchors=ANCHORS)
    with pytest.raises(ValueError, match="align"):
        group.measure(CONTEXT, WIDTH)


def test_equations_without_term_stops_are_unchanged_by_grid_columns():
    plain = (Equation("A", Row("aaaaa", Operator("+"), "bbbbb", gap=0), label="式名", result="999", unit="m"),
             Equation("B", "X" * 30, result="9", unit="m"))
    assert (measure_block(grid(*plain, anchors=ANCHORS), CONTEXT, WIDTH).parts
            == measure_block(EquationGroup(*plain, anchors=ANCHORS), CONTEXT, WIDTH).parts)


def test_automatic_anchors_work_with_grid_columns():
    part, = measure_block(grid(Equation("A", Row("1.5", TermStop("center"), Operator("+"), TermStop("right"),
                                                 "2.5", gap=0), result="4.0", unit="kN")),
                          CONTEXT, WIDTH).parts
    start = part.metadata["rhs_start_pt"] / PITCH
    assert start == pytest.approx(round(start))
    assert part.metadata["term_columns_grid"][0][0] == round(start)


def test_grid_terms_start_at_page_grid_columns_in_a_document():
    pad = equations.excel_cell_padding_pt(10)
    rhs = Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75")
    page, = Document(grid(Equation("S", rhs, result="21.25", unit="kN")), fonts=FONTS).layout()
    origin = A4_PORTRAIT_REFERENCE.grid.origin_x
    left = find_text_on_page(page, "12.50").x - pad - origin
    assert left / PITCH == pytest.approx(round(left / PITCH), abs=1e-9)
    right = find_text_on_page(page, "8.75").x + 4 * 10 * 0.6 + pad - origin
    assert right / PITCH == pytest.approx(round(right / PITCH), abs=1e-9)


def find_text_on_page(page, text):
    return next(command for command in page.commands if isinstance(command, Text) and command.text == text)


# --- the default output is unchanged (HEAD 3e42e18) ---------------------------------------------------------

def canonical(measured) -> str:
    lines = []
    for part in measured.parts:
        lines.append(f"part rows={part.rows!r} metadata={sorted(part.metadata.items())!r}")
        for command in part.commands:
            lines.append(f"  {command!r} tag={command.tag!r}")
    return "\n".join(lines)


def default_scenarios():
    narrow = EquationAnchors(8, 18, 24, 25)
    yield EquationGroup(Equation("kv", substitution("5.1", "x", "0.5", "68600"), result="1", unit="m"),
                        Equation("kh", substitution("5.1", "xx", "10.25", "6"), result="2", unit="m"),
                        anchors=narrow)
    yield EquationGroup(Equation("A", Row("a", TermStop("right", width=40), "bb", gap=0)), anchors=narrow,
                        term_gap=10)
    yield EquationGroup(Equation("A", Row(TermStop("right", width=30), "abc", TermStop(), TermStop("center"),
                                          "d", gap=0)), anchors=narrow, term_gap=0)
    yield EquationGroup(Equation("A", Row("A" * 30, TermStop("center"), Operator("+"), TermStop("right"),
                                          "B" * 30, gap=0), result="9", unit="m"), anchors=narrow)
    yield EquationGroup(Equation("A", Row("X" * 20, TermStop("right"), "YYYYY", gap=0), result="9", unit="m"),
                        anchors=narrow)
    yield EquationGroup(Equation("A", Row("a", TermStop(), "b", gap=0), result="1", unit="m"),
                        Equation("B", Row("a", TermStop(), "b", TermStop(), "Z" * 20, gap=0), result="2", unit="m"),
                        anchors=narrow, term_gap=0)
    yield EquationGroup(Equation("A", Row("aaaaa", Operator("+"), "bbbbb", gap=0), label="式名", result="999",
                                 unit="m"),
                        Equation("I", Fraction(Row("4.50", Operator("×"), Script("2.70", superscript="3")), "12"),
                                 label="断面二次モーメント", result="7.381125", unit=Script("m", superscript="4")),
                        Equation("D", Row("1", TermStop("right"), "22", gap=0), result="9", unit="m"))
    yield EquationGroup(Equation("S", Row("1.50", Operator("+"), "2.50", BreakHint("forced"), Operator("+"),
                                          "3.00"), label="水平力の合計", result="7.00", unit="kN"),
                        anchors=EquationAnchors(10, 22, 26, 27))


# sha256 of canonical() over default_scenarios(), computed with the HEAD 3e42e18 equations.py
# before FR-025 (Step 6). It proves that term_columns="packed" lays out exactly as before. If a
# later step changes the scene, the tags or the equation layout on purpose, regenerate it from
# that step's base commit (hashlib.sha256 of the joined canonical() text, as in the test below)
# and say so in the execution record, or remove this check once Step 6 is committed.
HEAD_DEFAULT_DIGEST = "ebd81f7ef1983670e79f774faebdd39b1f144918d01b068ebd6760d198b8d86a"


def test_default_output_is_the_same_as_before_grid_term_columns():
    text = "\n\n".join(canonical(measure_block(group, CONTEXT, WIDTH)) for group in default_scenarios())
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == HEAD_DEFAULT_DIGEST
    explicit = "\n\n".join(
        canonical(measure_block(EquationGroup(*group.equations, anchors=group.anchors,
                                              label_columns=group.label_columns, gap=group.gap,
                                              term_gap=group.term_gap, style=group.style,
                                              block_id=group.block_id, term_columns="packed"),
                                CONTEXT, WIDTH))
        for group in default_scenarios())
    assert explicit == text


def test_no_nan_in_grid_metadata():
    part, = measure_block(grid(Equation("A", Row("a", TermStop(), "b")), anchors=ANCHORS), CONTEXT, WIDTH).parts
    for left, width, _ in part.metadata["term_columns_pt"]:
        assert math.isfinite(left) and math.isfinite(width)


# --- the representative example written with grid term columns ----------------------------------------

@pytest.fixture(scope="module")
def example():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "examples/representative_report.py"
    spec = importlib.util.spec_from_file_location("representative_report_grid_terms", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def picture(tmp_path_factory):
    from PIL import Image as PILImage

    path = tmp_path_factory.mktemp("grid-terms") / "picture.png"
    with PILImage.new("RGB", (240, 160), (220, 232, 238)) as image:
        image.save(path)
    return path


def equation_placements(pages, block_id):
    return [placement for page in pages for placement in page.metadata["placements"]
            if placement["block_id"] == block_id]


@pytest.mark.parametrize("variant", ["standard", "long"])
def test_grid_example_lays_every_term_row_out_in_grid_columns(example, picture, variant):
    pages = example.build_report(picture, variant=variant, term_columns="grid").layout()
    terms = {}
    for block_id in ("section-properties", "load-totals"):
        placement, = equation_placements(pages, block_id)
        page_columns = next(page.profile.grid.columns for page in pages
                            if placement in page.metadata["placements"])
        for part in placement["parts"]:
            metadata = part["metadata"]
            assert "term_fallback" not in metadata
            if "term_columns_grid" in metadata and not metadata["result_line"]:
                columns = metadata["term_columns_grid"]
                assert columns[0][0] * PITCH == metadata["rhs_start_pt"]
                assert all(start + count == following for (start, count, _), (following, _, _)
                           in zip(columns, columns[1:]))
                assert placement["col"] + columns[-1][0] + columns[-1][1] <= page_columns
                terms[(block_id, metadata["equation_index"])] = [(count, align) for _, count, align in columns]
    # IPAex明朝 10 pt: values 2 columns, operators 1.
    pattern = [(2, "right"), (1, "center"), (2, "right")]
    assert terms == {("section-properties", 0): pattern,                  # A = 4.50 x 2.70
                     ("load-totals", 0): pattern + pattern[1:] * 6,      # S: 8 values, 7 operators
                     ("load-totals", 1): pattern + pattern[1:]}          # H: 3 values


def test_grid_example_has_no_fraction_inside_a_script(example, picture):
    packed = example.build_report(picture).layout()
    gridded = example.build_report(picture, term_columns="grid").layout()

    def fraction_in_script(pages):
        found = 0
        for page in pages:
            for command in page.commands:
                kinds = [scope.kind for scope in getattr(command.tag, "path", ())]
                if Kind.SCRIPT in kinds and Kind.FRACTION in kinds[kinds.index(Kind.SCRIPT):]:
                    found += 1
        return found
    assert fraction_in_script(packed) > 0  # the default keeps its fractional exponent
    assert fraction_in_script(gridded) == 0


def test_grid_example_stops_when_a_font_makes_terms_fall_back(example, picture, tmp_path, capsys):
    with pytest.raises(example.GridTermFallbackError, match="load-totals") as caught:
        example.write_report(tmp_path, image_path=picture, font="IPAexゴシック", term_columns="grid")
    assert isinstance(caught.value, ValueError) and caught.value.block_ids == ("load-totals",)
    assert not (tmp_path / "representative-report.pdf").exists()
    with pytest.raises(SystemExit) as stopped:
        example.main(["--output", str(tmp_path), "--image", str(picture), "--font", "IPAexゴシック",
                      "--term-columns", "grid"])
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert "--term-columns grid" in error and "load-totals" in error
    pages = example.build_report(picture, font="IPAexゴシック", term_columns="grid").layout()
    assert example.grid_fallbacks(pages) == ("load-totals",)
    assert example.grid_fallbacks(example.build_report(picture, term_columns="grid").layout()) == ()


def test_grid_example_default_is_packed_and_rejects_unknown_term_columns(example, picture):
    """The default equals explicit "packed"; equality with HEAD is test_default_output_is_the_same_..."""
    standard = example.build_report(picture).layout()
    packed = example.build_report(picture, term_columns="packed").layout()
    assert [page.commands for page in standard] == [page.commands for page in packed]
    assert all("term_columns_grid" not in part["metadata"]
               for placement in equation_placements(standard, "load-totals") for part in placement["parts"])
    with pytest.raises(ValueError, match="term_columns"):
        example.build_report(picture, term_columns="Grid")


def test_grid_example_command_line_option(example, picture, tmp_path):
    example.main(["--output", str(tmp_path), "--image", str(picture), "--term-columns", "grid"])
    import json

    trace = json.loads((tmp_path / "representative-report.json").read_text(encoding="utf-8"))
    assert "term_columns_grid" in json.dumps(trace)
    assert (tmp_path / "representative-report.pdf").stat().st_size > 0


# --- review round 1 ------------------------------------------------------------------------------------

def profile_with(pitch_x, columns):
    """The A4 reference grid with another column pitch and count, on paper wide enough for it."""
    from dataclasses import replace as dc_replace

    reference = A4_PORTRAIT_REFERENCE
    width = max(reference.width, reference.grid.origin_x + columns * pitch_x + 61.72)
    return dc_replace(reference, width=width,
                      grid=dc_replace(reference.grid, pitch_x=pitch_x, columns=columns))


def exact_rows(rhs_column, end_column, pitch):
    """Rows of two terms whose grid columns end exactly at ``end_column`` (every split)."""
    total = end_column - rhs_column
    for last in range(1, total):
        first = total - last
        yield first, last, Row(TermStop(width=first * pitch - 2 * PAD), "a",
                               TermStop(width=last * pitch - 2 * PAD), "b", gap=0)


def rhs_column_of(group_anchors, context, width):
    probe, = measure_block(grid(Equation("A", Row("a", TermStop(), "b")), anchors=group_anchors),
                           context, width).parts
    return round(probe.metadata["rhs_start_pt"] / context.profile.grid.pitch_x)


@pytest.mark.parametrize("pitch", [16.08, 15.48, 14.52, 10.8])
@pytest.mark.parametrize("columns", [13, 25, 26, 30, 31, 48])
def test_rows_ending_exactly_at_the_right_edge_do_not_fall_back(pitch, columns):
    context = LayoutContext(FONTS, profile_with(pitch, columns), ReportStyle())
    width = columns * pitch
    anchors = EquationAnchors(2)
    rhs_column = rhs_column_of(anchors, context, width)
    for first, last, rhs in exact_rows(rhs_column, columns, pitch):
        part, = measure_block(grid(Equation("A", rhs), anchors=anchors), context, width).parts
        assert "term_fallback" not in part.metadata, (first, last)
        assert part.metadata["term_columns_grid"][-1][0] + part.metadata["term_columns_grid"][-1][1] == columns


@pytest.mark.parametrize("pitch", [16.08, 15.48])
@pytest.mark.parametrize("second", [14, 18, 24, 26])
def test_rows_ending_exactly_at_the_normal_region_keep_their_result_on_the_line(pitch, second):
    context = LayoutContext(FONTS, profile_with(pitch, 30), ReportStyle())
    width = 30 * pitch
    # first_equal 8 -> RHS from column 9; the result relation at `second` ends the normal region at second - 1.
    for first, last, rhs in exact_rows(9, second - 1, pitch):
        parts = measure_block(grid(Equation("A", rhs, result="1", unit="m"),
                                   anchors=EquationAnchors(8, second, 28, 29)), context, width).parts
        assert len(parts) == 1 and not parts[0].metadata["result_line"], (first, last)
        assert [c.text for c in parts[0].commands][-3:] == ["=", "1", "m"]


def test_one_column_more_than_the_region_still_falls_back():
    anchors = EquationAnchors(2)
    rhs_column = rhs_column_of(anchors, CONTEXT, WIDTH)
    rhs = Row(TermStop(width=12 * PITCH - 2 * PAD), "a",
              TermStop(width=(31 - rhs_column - 12) * PITCH - 2 * PAD), "b", gap=0)
    parts = measure_block(grid(Equation("A", rhs), anchors=anchors), CONTEXT, WIDTH).parts
    assert all(part.metadata["term_fallback"] for part in parts)  # the columns would end at 31 > 30


def test_grid_term_tags_carry_the_column_count_and_padding():
    rhs = Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75", gap=0)
    part, = measure_block(grid(Equation("S", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    found = {}
    for command in part.commands:
        scope = next((s for s in command.tag.path if s.kind is Kind.EQUATION_PART), None)
        if scope is not None and scope.part == "term":
            found[scope.index] = dict(scope.data)
    expected = {index: {"align": align, "first_column": start, "columns": count, "cell_padding_pt": PAD}
                for index, (start, count, align) in enumerate(part.metadata["term_columns_grid"])}
    assert found == expected
    packed, = measure_block(EquationGroup(Equation("S", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    for command in packed.commands:
        scope = next((s for s in command.tag.path if s.kind is Kind.EQUATION_PART), None)
        if scope is not None and scope.part == "term":
            assert set(scope.data) == {"align"}


def test_an_empty_term_stays_at_its_zero_width_column():
    rhs = Row("a", TermStop("right"), "", TermStop("center"), "b", gap=0)
    part, = measure_block(grid(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert part.metadata["term_columns_grid"] == ((9, 1, "left"), (10, 0, "right"), (10, 1, "center"))
    empty = [c for c in part.commands if isinstance(c, Text) and c.text == ""]
    assert all(c.x == pytest.approx(10 * PITCH) for c in empty)


def test_columns_follow_the_widest_padded_need_not_the_widest_term():
    # 10 pt: 27.3 + 4.8 = 32.1 -> 2 columns; 14 pt: 26.6 + 5.6 = 32.2 -> 3 columns.
    group = grid(Equation("A", Row("a", TermStop(width=27.3), "b", gap=0)),
                 Equation("B", Row("a", TermStop(width=26.6), "b", gap=0), style=TextStyle(size=14)),
                 anchors=ANCHORS)
    small, large = measure_block(group, CONTEXT, WIDTH).parts
    assert small.metadata["term_columns_grid"][1][1] == 3
    assert large.metadata["term_columns_grid"] == small.metadata["term_columns_grid"]


def test_grid_metadata_is_exact_whole_columns():
    group = grid(Equation("kv", substitution("5.1", "x", "0.5", "68600"), result="1", unit="m"),
                 Equation("kh", Row(Fraction("12.5", "3"), TermStop("center"), Operator("+"), TermStop("right"),
                                    Script("2.70", superscript="3"), gap=0), result="2", unit="m"),
                 anchors=ANCHORS)
    for part in measure_block(group, CONTEXT, WIDTH).parts:
        grid_columns = part.metadata["term_columns_grid"]
        assert grid_columns[0][0] * PITCH == part.metadata["rhs_start_pt"]
        assert len(grid_columns) == len(part.metadata["term_columns_pt"])
        for (start, count, align), pts in zip(grid_columns, part.metadata["term_columns_pt"]):
            assert pts == (start * PITCH, count * PITCH, align) and count >= 0
        assert all(a + n == b for (a, n, _), (b, _, _) in zip(grid_columns, grid_columns[1:]))


@pytest.mark.parametrize("wrapper", ["columns", "indent-pitch", "at"])
def test_grid_terms_stay_on_page_columns_in_column_aligned_containers(wrapper):
    from gridlayoutpdf.containers import At, Columns, Indent
    from gridlayoutpdf.equations import MathBlock

    group = grid(Equation("S", Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75")))
    block = {"columns": lambda: Columns(MathBlock("x"), group, col_spans=(3, 26)),
             "indent-pitch": lambda: Indent(group, PITCH),
             "at": lambda: At(6, 4, 26, group)}[wrapper]()
    page, = Document(block, fonts=FONTS).layout()
    left = find_text_on_page(page, "12.50").x - PAD - A4_PORTRAIT_REFERENCE.grid.origin_x
    assert left / PITCH == pytest.approx(round(left / PITCH), abs=1e-9)


def test_a_point_indent_moves_grid_terms_off_the_page_columns():
    """Documented limit: columns count from the block's left edge (docs/api.md)."""
    from gridlayoutpdf.containers import Indent

    group = grid(Equation("S", Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75")))
    page, = Document(Indent(group, 8), fonts=FONTS).layout()
    left = find_text_on_page(page, "12.50").x - PAD - A4_PORTRAIT_REFERENCE.grid.origin_x
    assert (left - 8) / PITCH == pytest.approx(round((left - 8) / PITCH), abs=1e-9)


def test_grid_groups_compare_by_their_term_columns():
    equation = Equation("A", Row("a", TermStop(), "b"))
    assert EquationGroup(equation) != EquationGroup(equation, term_columns="grid")
    assert EquationGroup(equation, term_columns="grid") == EquationGroup(equation, term_columns="grid")
    assert hash(EquationGroup(equation, term_columns="grid")) == hash(EquationGroup(equation, term_columns="grid"))


# --- review round 2 ------------------------------------------------------------------------------------

def test_other_value_errors_are_not_blamed_on_grid_term_columns(example, tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not a png")
    with pytest.raises(ValueError) as caught:
        example.main(["--output", str(tmp_path), "--image", str(broken), "--term-columns", "grid"])
    assert not isinstance(caught.value, example.GridTermFallbackError)


@pytest.mark.parametrize("span, left", [(9, 2), (9, 5), (12, 7)])
def test_rows_ending_exactly_at_the_edge_of_an_indent_in_columns_do_not_fall_back(span, left):
    from gridlayoutpdf.containers import Columns, Indent
    from gridlayoutpdf.equations import MathBlock

    width = span - left
    anchors = EquationAnchors(2)
    rhs_column = rhs_column_of(anchors, CONTEXT, width * PITCH)
    for first, last, rhs in exact_rows(rhs_column, width, PITCH):
        block = Columns(MathBlock("x"), Indent(grid(Equation("A", rhs), anchors=anchors), left * PITCH),
                        col_spans=(3, span))
        parts = [part for part in measure_block(block, CONTEXT, WIDTH).parts]
        trace = [child for part in parts for child in part.metadata.get("children", ())]
        found = [metadata for child in trace for metadata in _part_metadata(child)]
        assert found and all("term_fallback" not in metadata for metadata in found), (span, left, first, last)
        grid_columns = found[0]["term_columns_grid"]
        assert grid_columns[-1][0] + grid_columns[-1][1] == width


def _part_metadata(trace):
    for part in trace.get("parts", ()):
        metadata = part["metadata"]
        if "equation_index" in metadata:
            yield metadata
        for child in metadata.get("children", ()):
            yield from _part_metadata(child)


def test_rows_ending_exactly_at_the_edge_of_an_a3_indent_do_not_fall_back():
    from gridlayoutpdf.containers import Indent
    from gridlayoutpdf.profiles import A3_LANDSCAPE_REFERENCE

    context = LayoutContext(FONTS, A3_LANDSCAPE_REFERENCE, ReportStyle())
    columns = A3_LANDSCAPE_REFERENCE.grid.columns
    pitch = A3_LANDSCAPE_REFERENCE.grid.pitch_x
    left = 44
    anchors = EquationAnchors(2)
    rhs_column = rhs_column_of(anchors, context, (columns - left) * pitch)
    for first, last, rhs in exact_rows(rhs_column, columns - left, pitch):
        part, = measure_block(Indent(grid(Equation("A", rhs), anchors=anchors), left * pitch), context,
                              columns * pitch).parts
        assert "term_fallback" not in part.metadata, (first, last)


def test_a_block_a_hair_narrower_than_the_columns_still_falls_back():
    anchors = EquationAnchors(2)
    rhs_column = rhs_column_of(anchors, CONTEXT, WIDTH)
    first, last, rhs = next(exact_rows(rhs_column, 30, PITCH))
    assert "term_fallback" not in measure_block(grid(Equation("A", rhs), anchors=anchors),
                                                CONTEXT, WIDTH).parts[0].metadata
    narrower = measure_block(grid(Equation("A", rhs), anchors=anchors), CONTEXT, WIDTH - 1e-6).parts
    assert all(part.metadata["term_fallback"] for part in narrower)


@pytest.mark.parametrize("extra, columns", [(5e-8, 2), (2e-7, 3)])
def test_term_width_tolerance_is_the_shared_roundoff_only(extra, columns):
    rhs = Row("a", TermStop(width=2 * PITCH - 2 * PAD + extra), "b", gap=0)
    part, = measure_block(grid(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    assert part.metadata["term_columns_grid"][1][1] == columns


def test_a_smaller_text_with_the_wider_term_can_decide_the_columns():
    # 10 pt: 27.3 + 4.8 = 32.1 -> 2 columns; 14 pt: 20.0 + 5.6 = 25.6 -> 2 columns.
    # The widest term plus the largest padding (27.3 + 5.6 = 32.9) would wrongly give 3.
    group = grid(Equation("A", Row("a", TermStop(width=27.3), "b", gap=0)),
                 Equation("B", Row("a", TermStop(width=20.0), "b", gap=0), style=TextStyle(size=14)),
                 anchors=ANCHORS)
    small, large = measure_block(group, CONTEXT, WIDTH).parts
    assert small.metadata["term_columns_grid"][1][1] == 2 == large.metadata["term_columns_grid"][1][1]


def test_term_tags_carry_their_first_column_from_the_block_edge():
    rhs = Row("a", TermStop("right"), "12.50", Row(), TermStop("left"), Row(), "8.75", TermStop(), "", gap=0)
    part, = measure_block(grid(Equation("A", rhs), anchors=ANCHORS), CONTEXT, WIDTH).parts
    found = {}
    for command in part.commands:
        scope = next((s for s in command.tag.path if s.kind is Kind.EQUATION_PART), None)
        if scope is not None and scope.part == "term":
            found[scope.index] = (scope.data["first_column"], scope.data["columns"], scope.data["cell_padding_pt"])
    expected = {index: (start, count, PAD if count else 0.0)
                for index, (start, count, _) in enumerate(part.metadata["term_columns_grid"])}
    assert found == {index: value for index, value in expected.items() if index in found}
    assert set(found) >= {0, 1, 2}



# --- review round 3 ------------------------------------------------------------------------------------

def test_rows_ending_exactly_at_a_normal_region_made_by_subtraction_keep_their_result():
    # 9 * 16.08 - 3 - 13.08 is an ulp short of 8 columns; the region still ends at column 8.
    anchors = EquationAnchors(2, 9, 12)
    probe, = measure_block(grid(Equation("A", Row("a", TermStop(), "b"), result="1"), anchors=anchors,
                                gap=13.08), CONTEXT, WIDTH).parts
    rhs_column = round(probe.metadata["rhs_start_pt"] / PITCH)
    rows = list(exact_rows(rhs_column, 8, PITCH))
    assert rows
    for first, last, rhs in rows:
        parts = measure_block(grid(Equation("A", rhs, result="1"), anchors=anchors, gap=13.08),
                              CONTEXT, WIDTH).parts
        assert len(parts) == 1 and not parts[0].metadata["result_line"], (first, last)


def test_grid_fallback_error_keeps_its_block_ids_through_a_copy(example):
    import copy

    error = example.GridTermFallbackError("message", ("load-totals",))
    assert copy.copy(error).args == error.args
    assert copy.copy(error).block_ids == ("load-totals",)
    assert copy.deepcopy(error).block_ids == ("load-totals",)  # rebuilt through __reduce__, as pickle does
    assert example.GridTermFallbackError("message").block_ids == ()


def test_an_indent_in_columns_a_hair_too_wide_still_falls_back():
    from gridlayoutpdf.containers import Columns, Indent
    from gridlayoutpdf.equations import MathBlock

    span, left = 9, 2
    anchors = EquationAnchors(2)
    rhs_column = rhs_column_of(anchors, CONTEXT, (span - left) * PITCH)
    for first, last, rhs in exact_rows(rhs_column, span - left, PITCH):
        block = Columns(MathBlock("x"), Indent(grid(Equation("A", rhs), anchors=anchors), left * PITCH + 1e-6),
                        col_spans=(3, span))
        found = [metadata for part in measure_block(block, CONTEXT, WIDTH).parts
                 for child in part.metadata.get("children", ()) for metadata in _part_metadata(child)]
        assert found and all(metadata.get("term_fallback") for metadata in found), (first, last)


def _page_column_of_first_term(page, offset_pt):
    """The documented page column: placement col + container offset / pitch + the tag's first_column."""
    placement, = page.metadata["placements"]
    command = next(c for c in page.commands if isinstance(c, Text) and c.text == "12.50")
    scope = next(s for s in command.tag.path if s.kind is Kind.EQUATION_PART)
    total = placement["col"] + offset_pt / PITCH + scope.data["first_column"]
    assert documented_on_page_columns(total)  # off the page columns otherwise (docs/api.md)
    return round(total), command


def documented_on_page_columns(total_columns):
    """docs/api.md: on the page columns unless the distance to the nearest integer exceeds 1e-6 pt."""
    return abs(total_columns - round(total_columns)) * PITCH <= 1e-6


def _documented_offset_pt(trace):
    """Sum the container offsets the docs name on the path: each part's indent_pt and child x_pt."""
    for part in trace.get("parts", ()):
        metadata = part["metadata"]
        if "equation_index" in metadata:
            return metadata.get("indent_pt", 0.0)
        for child in metadata.get("children", ()):
            found = _documented_offset_pt(child)
            if found is not None:
                return metadata.get("indent_pt", 0.0) + child["x_pt"] + found
    return None


@pytest.mark.parametrize("wrapper", ["page", "columns", "columns-indent", "indent-pitch", "at",
                                     "indent-columns", "columns-stack", "indent-stack"])
def test_the_documented_page_column_matches_the_text(wrapper):
    from gridlayoutpdf.blocks import Paragraph
    from gridlayoutpdf.containers import At, Columns, Indent, Stack
    from gridlayoutpdf.equations import MathBlock

    group = grid(Equation("S", Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75")))
    block = {"page": lambda: group,
             "columns": lambda: Columns(MathBlock("x"), group, col_spans=(3, 26)),
             "columns-indent": lambda: Columns(MathBlock("x"), Indent(group, 2 * PITCH), col_spans=(3, 26)),
             "indent-pitch": lambda: Indent(group, 2 * PITCH),
             "at": lambda: At(6, 4, 26, group),
             "indent-columns": lambda: Indent(Columns(MathBlock("x"), group, col_spans=(3, 20)),
                                              2 * PITCH),
             "columns-stack": lambda: Columns(MathBlock("x"), Stack(Paragraph("y"), group), col_spans=(3, 26)),
             "indent-stack": lambda: Indent(Stack(Paragraph("y"), group), 2 * PITCH)}[wrapper]()
    page, = Document(block, fonts=FONTS).layout()
    placement, = page.metadata["placements"]
    offset = _documented_offset_pt(placement)
    assert offset is not None
    column, command = _page_column_of_first_term(page, offset)
    from gridlayoutpdf.renderers.xlsx._map import map_reports

    _, result = map_reports([("s", (page,))], FONTS, cell_padding_pt=equations.excel_cell_padding_pt)
    assert not [fallback for fallback in result.fallbacks if fallback.kind == "term_off_grid"]
    left = (command.x - PAD - A4_PORTRAIT_REFERENCE.grid.origin_x) / PITCH
    assert column == pytest.approx(left, abs=1e-9)


def test_nested_indents_give_the_page_column_by_the_documented_rule():
    """Indent records the whole shift of nested indents in indent_pt (containers.py)."""
    from gridlayoutpdf.containers import Indent

    group = grid(Equation("S", Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75")))
    page, = Document(Indent(Indent(group, 2 * PITCH), PITCH), fonts=FONTS).layout()
    placement, = page.metadata["placements"]
    assert placement["parts"][0]["metadata"]["indent_pt"] == pytest.approx(3 * PITCH)
    column, command = _page_column_of_first_term(page, _documented_offset_pt(placement))
    left = (command.x - PAD - A4_PORTRAIT_REFERENCE.grid.origin_x) / PITCH
    assert column == pytest.approx(left, abs=1e-9)


def test_a_point_indent_is_seen_as_off_the_page_columns_by_the_documented_rule():
    from gridlayoutpdf.containers import Indent

    group = grid(Equation("S", Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75")))
    page, = Document(Indent(group, 10.0), fonts=FONTS).layout()
    placement, = page.metadata["placements"]
    command = next(c for c in page.commands if isinstance(c, Text) and c.text == "12.50")
    scope = next(s for s in command.tag.path if s.kind is Kind.EQUATION_PART)
    total = placement["col"] + _documented_offset_pt(placement) / PITCH + scope.data["first_column"]
    assert not documented_on_page_columns(total)


@pytest.mark.parametrize("shift_pt, on_columns", [(5e-7, True), (2e-6, False), (5e-6, False)])
def test_the_documented_alignment_rule_is_in_pt(shift_pt, on_columns):
    from gridlayoutpdf.containers import Indent

    group = grid(Equation("S", Row("12.50", TermStop("center"), Operator("+"), TermStop("right"), "8.75")))
    page, = Document(Indent(group, 2 * PITCH + shift_pt), fonts=FONTS).layout()
    placement, = page.metadata["placements"]
    command = next(c for c in page.commands if isinstance(c, Text) and c.text == "12.50")
    scope = next(s for s in command.tag.path if s.kind is Kind.EQUATION_PART)
    total = placement["col"] + _documented_offset_pt(placement) / PITCH + scope.data["first_column"]
    assert documented_on_page_columns(total) is on_columns
    # The grid Excel mapping applies the same rule (docs/api.md says so).
    from gridlayoutpdf.renderers.xlsx._map import map_reports

    _, result = map_reports([("s", (page,))], FONTS, cell_padding_pt=equations.excel_cell_padding_pt)
    off_grid = [fallback for fallback in result.fallbacks if fallback.kind == "term_off_grid"]
    assert bool(off_grid) is not on_columns
    assert all("not on a page column boundary" in fallback.detail for fallback in off_grid)


# --- review round 4 ------------------------------------------------------------------------------------

def _subtraction_region_parts(rhs, gap=13.08):
    return measure_block(grid(Equation("A", rhs, result="1"), anchors=EquationAnchors(2, 9, 12), gap=gap),
                         CONTEXT, WIDTH).parts


def _subtraction_rhs_column(gap=13.08):
    probe, = measure_block(grid(Equation("A", Row("a", TermStop(), "b"), result="1"),
                                anchors=EquationAnchors(2, 9, 12), gap=gap), CONTEXT, WIDTH).parts
    return round(probe.metadata["rhs_start_pt"] / PITCH)


def test_rows_one_column_past_a_subtracted_normal_region_move_their_result():
    rows = list(exact_rows(_subtraction_rhs_column(), 9, PITCH))
    assert rows
    for first, last, rhs in rows:
        parts = _subtraction_region_parts(rhs)
        assert parts[-1].metadata["result_line"] and "term_fallback" not in parts[0].metadata, (first, last)


def test_rows_at_a_normal_region_a_hair_too_short_move_their_result():
    # 1e-6 pt more gap leaves the normal region short of column 8 (the RHS then starts at column 4).
    gap = 13.08 + 1e-6
    rows = list(exact_rows(_subtraction_rhs_column(gap), 8, PITCH))
    assert rows
    for first, last, rhs in rows:
        parts = _subtraction_region_parts(rhs, gap=gap)
        assert parts[-1].metadata["result_line"], (first, last)


@pytest.mark.parametrize("pitch", [16.08, 15.48])
@pytest.mark.parametrize("second", [14, 18, 24, 26])
def test_rows_one_column_past_the_normal_region_move_their_result(pitch, second):
    context = LayoutContext(FONTS, profile_with(pitch, 30), ReportStyle())
    anchors = EquationAnchors(8, second, 28, 29)
    rhs_column = rhs_column_of(anchors, context, 30 * pitch)
    assert rhs_column == 9  # the normal region then ends at second - 1
    for first, last, rhs in exact_rows(rhs_column, second, pitch):
        parts = measure_block(grid(Equation("A", rhs, result="1", unit="m"), anchors=anchors),
                              context, 30 * pitch).parts
        assert parts[-1].metadata["result_line"] and "term_fallback" not in parts[0].metadata, (first, last)

