from dataclasses import FrozenInstanceError, replace
import importlib
import math
from pathlib import Path

import pytest

from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.errors import FontError, LayoutOverflowError
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.scene import Line, Text
from gridlayoutpdf.styles import ReportStyle, TextStyle


def api():
    try:
        return importlib.import_module("gridlayoutpdf.layout")
    except ModuleNotFoundError:
        pytest.fail("Common layout contracts are not implemented")


@pytest.fixture
def fonts():
    registry = FontRegistry()
    return registry


def make_context(fonts):
    return api().LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())


def test_context_baselines_advance_whole_rows_and_heights_round_up(fonts):
    context = make_context(fonts)
    assert context.baseline_for(8.798828125) == 11
    assert context.rows_for(11 + 1.9873046875) == 1
    assert context.baseline_for(11) == 11
    assert context.baseline_for(11.001) == pytest.approx(26.48)
    assert context.baseline_for(26.48) == pytest.approx(26.48)
    assert context.baseline_for(26.4801) == pytest.approx(41.96)
    assert context.rows_for(44.96) == 3
    assert context.rows_for(0) == 0
    assert context.rows_for(15.48) == 1
    assert context.rows_for(15.4800001) == 2
    with pytest.raises(FrozenInstanceError):
        context.style = ReportStyle()


@pytest.mark.parametrize("boundary,next_baseline", [(22.1, 34.1), (34.1, 46.1), (130.1, 142.1)])
@pytest.mark.parametrize("direction", [-math.inf, None, math.inf])
def test_context_baseline_distinguishes_exact_offset_boundary_from_adjacent_floats(
    fonts, boundary, next_baseline, direction
):
    profile = replace(
        A4_PORTRAIT_REFERENCE,
        grid=replace(A4_PORTRAIT_REFERENCE.grid, pitch_y=12),
    )
    context = api().LayoutContext(fonts, profile, ReportStyle(baseline_offset=10.1))
    ascent = boundary if direction is None else math.nextafter(boundary, direction)
    expected = next_baseline if direction == math.inf else boundary
    assert context.baseline_for(ascent) == expected


@pytest.mark.parametrize("field,value", [("fonts", None), ("profile", None), ("style", TextStyle())])
def test_context_rejects_wrong_types(fonts, field, value):
    values = {"fonts": fonts, "profile": A4_PORTRAIT_REFERENCE, "style": ReportStyle()}
    values[field] = value
    with pytest.raises(ValueError, match=field):
        api().LayoutContext(**values)


@pytest.mark.parametrize("value", [-1, True, float("inf"), float("nan"), "10"])
def test_context_helpers_reject_invalid_extents(fonts, value):
    context = make_context(fonts)
    with pytest.raises(ValueError):
        context.baseline_for(value)
    with pytest.raises(ValueError):
        context.rows_for(value)


def test_layout_part_is_an_immutable_snapshot_of_commands_and_nested_metadata():
    commands = [Text(2, 11, "A", TextStyle())]
    metadata = {"names": ["first", {"value": 3}], "flag": True, "none": None}
    part = api().LayoutPart(2, commands, metadata)
    commands.clear()
    metadata["names"][1]["value"] = 99
    assert len(part.commands) == 1
    assert part.metadata["names"][1]["value"] == 3
    with pytest.raises(FrozenInstanceError):
        part.rows = 3
    with pytest.raises(TypeError):
        part.metadata["names"][1]["value"] = 4
    with pytest.raises(TypeError):
        part.metadata["extra"] = 5
    assert api().LayoutPart(1).commands == ()


@pytest.mark.parametrize("rows", [0, -1, True, 1.5, float("nan"), float("inf")])
def test_layout_part_rejects_invalid_rows(rows):
    with pytest.raises(ValueError, match="rows"):
        api().LayoutPart(rows)


@pytest.mark.parametrize("commands", [None, [object()], "bad"])
def test_layout_part_rejects_invalid_commands(commands):
    with pytest.raises(ValueError, match="commands"):
        api().LayoutPart(1, commands)


@pytest.mark.parametrize("metadata", [None, {2: "value"}, {"bad": object()}, {"bad": float("nan")}])
def test_layout_part_rejects_non_json_metadata(metadata):
    with pytest.raises(ValueError, match="metadata"):
        api().LayoutPart(1, metadata=metadata)


def test_layout_part_rejects_metadata_cycles():
    data = {"loop": []}
    data["loop"].append(data)
    with pytest.raises(ValueError, match="cycle"):
        api().LayoutPart(1, metadata=data)


def test_measured_block_offsets_prefix_and_parts_without_mutating_inputs():
    module = api()
    header = module.LayoutPart(1, (Text(2, 11, "H", TextStyle()),))
    first = module.LayoutPart(2, (Text(2, 11, "A", TextStyle()),))
    last = module.LayoutPart(1, (Text(2, 11, "B", TextStyle()),))
    source_parts, source_prefix = [first, last], [header]
    block = module.MeasuredBlock(100, 15.48, source_parts, prefix=source_prefix, block_id="table")
    source_parts.clear()
    source_prefix.clear()
    assert block.rows == 4
    assert block.height == pytest.approx(61.92)
    assert [command.text for command in block.commands] == ["H", "A", "B"]
    assert [command.y for command in block.commands] == pytest.approx([11, 26.48, 57.44])
    moved = block.translated(20, 30)
    assert [command.x for command in moved] == [22, 22, 22]
    assert [command.y for command in moved] == pytest.approx([41, 56.48, 87.44])
    assert first.commands[0].y == 11
    assert block.commands == block.commands
    with pytest.raises(FrozenInstanceError):
        block.parts = ()


def test_empty_measured_block_has_no_rows_height_or_commands():
    block = api().MeasuredBlock(100, 15.48)
    assert (block.rows, block.height, block.commands) == (0, 0, ())
    assert block.translated(10, 20) == ()


@pytest.mark.parametrize("field,value", [
    ("width", 0), ("width", -1), ("width", True), ("width", float("nan")),
    ("row_pitch", 0), ("row_pitch", -1), ("row_pitch", False), ("row_pitch", float("inf")),
    ("min_first", 0), ("min_first", True), ("min_first", 1.5),
    ("min_last", -1), ("min_last", False),
    ("keep_together", 1), ("keep_with_next", None), ("prefer_keep", "yes"),
    ("block_id", 3), ("parts", [object()]), ("prefix", [object()]),
])
def test_measured_block_rejects_invalid_contract_values(field, value):
    values = {"width": 100, "row_pitch": 15.48, "parts": (api().LayoutPart(1),)}
    values[field] = value
    with pytest.raises(ValueError, match=field):
        api().MeasuredBlock(**values)


def test_measured_block_rejects_header_without_body_and_nonfinite_height():
    with pytest.raises(ValueError, match="prefix"):
        api().MeasuredBlock(100, 15.48, prefix=(api().LayoutPart(1),))
    with pytest.raises(ValueError, match="height"):
        api().MeasuredBlock(100, 1e308, (api().LayoutPart(2),))


@pytest.mark.parametrize("cuts", [(-1,), (0,), (3,), (True,), (1.5,), 2])
def test_measured_block_rejects_invalid_part_boundaries(cuts):
    parts = (api().LayoutPart(1),) * 3
    with pytest.raises(ValueError, match="break_after"):
        api().MeasuredBlock(100, 15.48, parts, break_after=cuts)


def parts_with_rows(*rows):
    return tuple(api().LayoutPart(count, (Text(2, 11, str(index), TextStyle()),),
                                  {"index": index})
                 for index, count in enumerate(rows))


def test_split_uses_last_fitting_boundary_with_no_empty_fragment():
    block = api().MeasuredBlock(100, 15.48, parts_with_rows(1, 2, 1), block_id="mixed")
    assert block.minimum_rows == 1
    head, tail = block.split(3)
    assert (head.rows, tail.rows) == (3, 1)
    assert [part.metadata["index"] for part in head.parts] == [0, 1]
    assert [part.metadata["index"] for part in tail.parts] == [2]
    head, tail = block.split(2)
    assert (head.rows, tail.rows) == (1, 3)
    assert tail.commands[0].y == 11
    assert head.block_id == tail.block_id == "mixed"
    assert block.split(0) is None
    assert block.split(4) is None
    assert block.split(100) is None


def test_paragraph_avoids_single_display_line_fragments_and_short_text_still_fits():
    module = api()
    paragraph = module.MeasuredBlock(100, 15.48, parts_with_rows(1, 1, 1, 1),
                                     min_first=2, min_last=2)
    assert paragraph.minimum_rows == 2
    assert tuple(fragment.rows for fragment in paragraph.split(3)) == (2, 2)
    assert tuple(fragment.rows for fragment in paragraph.split(2)) == (2, 2)
    assert paragraph.split(1) is None
    three = module.MeasuredBlock(100, 15.48, parts_with_rows(1, 1, 1), min_first=2, min_last=2)
    assert three.split(2) is None
    assert three.minimum_rows == 3
    one = module.MeasuredBlock(100, 15.48, parts_with_rows(1), min_first=2, min_last=2)
    assert one.minimum_rows == 1
    assert one.split(1) is None


def test_line_minima_count_parts_even_when_each_line_uses_multiple_grid_rows():
    paragraph = api().MeasuredBlock(100, 15.48, parts_with_rows(2, 2, 2, 2),
                                    min_first=2, min_last=2)
    assert paragraph.minimum_rows == 4
    assert paragraph.split(3) is None
    head, tail = paragraph.split(6)
    assert (head.rows, tail.rows) == (4, 4)
    assert (len(head.parts), len(tail.parts)) == (2, 2)


def test_repeated_split_preserves_minimum_display_lines_on_every_tail():
    block = api().MeasuredBlock(100, 15.48, parts_with_rows(1, 1, 1, 1, 1, 1),
                               min_first=2, min_last=2)
    first, tail = block.split(2)
    assert (tail.min_first, tail.min_last) == (2, 2)
    middle, last = tail.split(3)
    assert (len(first.parts), len(middle.parts), len(last.parts)) == (2, 2, 2)
    assert middle.parts + last.parts == tail.parts
    assert last.split(1) is None


def test_prefix_repeats_once_per_fragment_and_never_forms_a_header_only_head():
    module = api()
    header = (module.LayoutPart(1, (Text(2, 11, "H1", TextStyle()),)),
              module.LayoutPart(2, (Text(2, 11, "H2", TextStyle()),)))
    block = module.MeasuredBlock(100, 15.48, parts_with_rows(2, 1, 3), prefix=header)
    assert block.rows == 9
    assert block.minimum_rows == 5
    assert block.split(3) is None
    assert block.split(4) is None
    head, tail = block.split(6)
    assert (head.rows, tail.rows) == (6, 6)
    assert head.prefix == tail.prefix == header
    assert [command.text for command in head.commands] == ["H1", "H2", "0", "1"]
    assert [command.text for command in tail.commands] == ["H1", "H2", "2"]
    assert [command.y for command in head.commands] == pytest.approx([11, 26.48, 57.44, 88.4])
    assert [command.y for command in tail.commands] == pytest.approx([11, 26.48, 57.44])


def test_explicit_cuts_are_copied_and_rebased_without_enabling_forbidden_cuts():
    cuts = [4, 2, 2]
    block = api().MeasuredBlock(100, 15.48, parts_with_rows(1, 1, 1, 1, 1, 1), break_after=cuts)
    cuts.clear()
    assert block.break_after == (2, 4)
    assert block.minimum_rows == 2
    head, tail = block.split(5)
    assert len(head.parts) == 4
    assert head.break_after == (2,)
    assert tail.break_after == ()
    assert tail.minimum_rows == 2
    assert tail.split(1) is None
    first, remaining = block.split(3)
    assert len(first.parts) == 2
    assert remaining.break_after == (2,)
    assert remaining.minimum_rows == 2


def test_keep_flags_preserve_their_fragment_semantics():
    module = api()
    block = module.MeasuredBlock(100, 15.48, parts_with_rows(1, 1, 1),
                                 keep_with_next=True, prefer_keep=True)
    head, tail = block.split(2)
    assert head.keep_with_next is False and tail.keep_with_next is True
    assert head.prefer_keep is True and tail.prefer_keep is True
    together = module.MeasuredBlock(100, 15.48, block.parts, keep_together=True)
    assert together.minimum_rows == 3
    assert together.split(2) is None
    unbreakable = module.MeasuredBlock(100, 15.48, block.parts, break_after=())
    assert unbreakable.minimum_rows == 3
    assert unbreakable.split(2) is None
    empty = module.MeasuredBlock(100, 15.48)
    assert empty.minimum_rows == 0 and empty.split(0) is None


@pytest.mark.parametrize("rows", [-1, True, 1.0, float("inf"), None])
def test_split_rejects_invalid_available_rows(rows):
    block = api().MeasuredBlock(100, 15.48, parts_with_rows(1, 1))
    with pytest.raises(ValueError, match="available_rows"):
        block.split(rows)


class SampleBlock:
    block_id = "source-block"

    def __init__(self, result=None, error=None):
        self.result, self.error = result, error
        self.received = None

    def measure(self, context, available_width):
        self.received = (context, available_width)
        if self.error is not None:
            raise self.error
        return self.result


def test_measure_block_validates_a_runtime_block_without_drawing_or_rejecting_overlap(fonts, monkeypatch):
    module = api()
    context = make_context(fonts)
    from reportlab.pdfgen import canvas

    def no_canvas(*args, **kwargs):
        pytest.fail("Measuring must not construct a PDF canvas")

    monkeypatch.setattr(canvas, "Canvas", no_canvas)
    # Internal overlap is deliberate: math and figures may compose such commands.
    part = module.LayoutPart(1, (Line(1, 2, 9, 2), Line(1, 2, 9, 2)))
    measured = module.MeasuredBlock(100, 15.48, (part,), block_id="result-block")
    block = SampleBlock(measured)
    assert isinstance(block, module.Block)
    assert module.measure_block(block, context, 120) is measured
    assert block.received == (context, 120)


@pytest.mark.parametrize("width", [0, -1, True, float("nan"), float("inf"), "100"])
def test_measure_block_rejects_invalid_available_width_before_calling_the_component(fonts, width):
    block = SampleBlock()
    with pytest.raises(ValueError, match="available_width"):
        api().measure_block(block, make_context(fonts), width)
    assert block.received is None


def test_measure_block_rejects_invalid_context_block_result_and_pitch(fonts):
    module = api()
    context = make_context(fonts)
    with pytest.raises(ValueError, match="context"):
        module.measure_block(SampleBlock(), None, 100)
    with pytest.raises(ValueError, match="measure"):
        module.measure_block(object(), context, 100)
    with pytest.raises(ValueError, match="MeasuredBlock"):
        module.measure_block(SampleBlock(result="bad"), context, 100)
    mismatched = module.MeasuredBlock(100, 20, (module.LayoutPart(1),), block_id="pitch-block")
    with pytest.raises(ValueError, match="pitch-block.*row_pitch"):
        module.measure_block(SampleBlock(mismatched), context, 100)


def test_measure_block_reports_reserved_width_overflow_and_needed_available(fonts):
    module = api()
    measured = module.MeasuredBlock(101, 15.48, (module.LayoutPart(1),), block_id="wide")
    with pytest.raises(LayoutOverflowError, match="wide.*width") as caught:
        module.measure_block(SampleBlock(measured), make_context(fonts), 100)
    assert caught.value.block_id == "wide"
    assert caught.value.needed == 101 and caught.value.available == 100


@pytest.mark.parametrize("location,command", [
    ("parts", Line(0, 1, 9, 1, width=1)),
    ("parts", Line(1, 1, 100, 1, width=1)),
    ("parts", Line(1, 0, 9, 0, width=1)),
    ("parts", Line(1, 15.4, 9, 15.4, width=1)),
    ("prefix", Text(0.01, 11, "j", TextStyle())),
    ("prefix", Text(1, 14, "g", TextStyle())),
])
def test_measure_block_checks_each_body_or_prefix_part_with_real_bounds(fonts, location, command):
    module = api()
    options = {"parts": (module.LayoutPart(1),), "prefix": ()}
    options[location] = (module.LayoutPart(1, (command,)),)
    result = module.MeasuredBlock(100, 15.48, **options, block_id="item")
    with pytest.raises(LayoutOverflowError, match=f"item.*{location}\\[0\\].commands\\[0\\].*bounds") as caught:
        module.measure_block(SampleBlock(result), make_context(fonts), 100)
    assert caught.value.block_id == "item"


def test_measure_block_allows_only_tiny_roundoff_at_part_boundaries(fonts):
    module = api()
    context = make_context(fonts)
    almost = module.MeasuredBlock(100 + 5e-8, 15.48 + 5e-8,
        (module.LayoutPart(1, (Line(0.5 - 5e-8, 1, 99.5 + 5e-8, 1, width=1),)),))
    assert module.measure_block(SampleBlock(almost), context, 100) is almost
    visibly_out = module.MeasuredBlock(100, 15.48,
        (module.LayoutPart(1, (Line(0.5 - 5e-6, 1, 99.5, 1, width=1),)),))
    with pytest.raises(LayoutOverflowError):
        module.measure_block(SampleBlock(visibly_out), context, 100)


def test_font_errors_include_the_block_context_and_preserve_the_original_cause(fonts):
    module = api()
    context = make_context(fonts)
    original = FontError("Font body missing U+10FFFF")
    with pytest.raises(FontError, match="source-block.*U\\+10FFFF") as caught:
        module.measure_block(SampleBlock(error=original), context, 100)
    assert caught.value.__cause__ is original
    measured = module.MeasuredBlock(100, 15.48,
        (module.LayoutPart(1, (Text(1, 11, "\U0010ffff", TextStyle()),)),), block_id="glyph-block")
    with pytest.raises(FontError, match="glyph-block.*parts\\[0\\].commands\\[0\\].*U\\+10FFFF") as caught:
        module.measure_block(SampleBlock(measured), context, 100)
    assert isinstance(caught.value.__cause__, FontError)


def test_component_overflow_error_retains_dimensions_and_gains_an_identifier(fonts):
    original = LayoutOverflowError("too wide", needed=150, available=100)
    with pytest.raises(LayoutOverflowError, match="source-block.*too wide") as caught:
        api().measure_block(SampleBlock(error=original), make_context(fonts), 100)
    assert caught.value.__cause__ is original
    assert caught.value.block_id == "source-block"
    assert (caught.value.needed, caught.value.available) == (150, 100)


def test_measure_child_keeps_type_errors_unless_the_caller_owns_them(fonts):
    """Containers let a TypeError through; a cell turns it into input guidance."""
    context = make_context(fonts)

    class Broken:
        def measure(self, context, available_width):
            raise TypeError("not measurable")

    with pytest.raises(TypeError, match="not measurable"):
        api().measure_child(Broken(), context, 100.0, "Stack.children[0]")
    with pytest.raises(ValueError, match=r"cells\[0\]: not measurable; needs MathBlock"):
        api().measure_child(Broken(), context, 100.0, "T.rows[0].cells[0]",
                            type_errors=True, hint="; needs MathBlock")
