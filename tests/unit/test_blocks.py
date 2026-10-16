from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from gridlayoutpdf.blocks import Heading, PageBreak, Paragraph, Spacer
from gridlayoutpdf.errors import FontError, LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry
from gridlayoutpdf.layout import LayoutContext, measure_block
from gridlayoutpdf.profiles import A4_PORTRAIT_REFERENCE
from gridlayoutpdf.scene import Text
from gridlayoutpdf.styles import ReportStyle, TextStyle


@pytest.fixture(scope="module")
def context():
    fonts = FontRegistry()
    fonts.register("body", Path(__file__).resolve().parents[1] / "fixtures/fonts/ipaexm.ttf")
    return LayoutContext(fonts, A4_PORTRAIT_REFERENCE, ReportStyle())


def test_paragraph_emits_one_grid_part_per_line_at_context_baseline(context):
    paragraph = Paragraph("日本語橋脚", block_id="paragraph")
    result = measure_block(paragraph, context, 32.16)
    assert result.width == 32.16 and result.row_pitch == 15.48
    assert (result.rows, result.height, result.block_id) == (2, 30.96, "paragraph")
    assert result.min_first == result.min_last == 2
    assert [part.rows for part in result.parts] == [1, 1]
    assert result.commands == (
        Text(0, 11, "日本語", TextStyle()), Text(0, 26.48, "橋脚", TextStyle()))
    assert [dict(part.metadata) for part in result.parts] == [
        {"text": "日本語", "line_index": 0, "paragraph_end": False},
        {"text": "橋脚", "line_index": 1, "paragraph_end": True},
    ]
    assert measure_block(paragraph, context, 32.16) == result
    assert paragraph.style is None
    with pytest.raises(FrozenInstanceError):
        paragraph.text = "変更"
    with pytest.raises(TypeError):
        result.parts[0].metadata["text"] = "変更"


def test_heading_inherits_heading_style_and_stays_with_following_block(context):
    context = replace(context, style=ReportStyle(body=TextStyle(size=9), heading=TextStyle(size=14)))
    result = measure_block(Heading("日本語", block_id="heading"), context, 30)
    assert [command.text for command in result.commands] == ["日本", "語"]
    assert all(command.style.size == 14 for command in result.commands)
    assert result.keep_together and result.keep_with_next
    assert result.split(result.rows - 1) is None
    override = TextStyle(size=10, tracking=.25)
    result = measure_block(Heading("日本", style=override), context, 30)
    assert result.commands[0].style is override


def test_paragraph_remeasures_context_style_width_and_baseline(context):
    paragraph = Paragraph("日本語橋")
    first = measure_block(paragraph, context, 20)
    wider = measure_block(paragraph, context, 40)
    larger = measure_block(paragraph, replace(context, style=ReportStyle(body=TextStyle(size=20))), 40)
    shifted = measure_block(paragraph, replace(context, style=ReportStyle(baseline_offset=12)), 20)
    assert [command.text for command in first.commands] == ["日本", "語橋"]
    assert [command.text for command in wider.commands] == ["日本語橋"]
    assert [command.text for command in larger.commands] == ["日本", "語橋"]
    assert [part.rows for part in larger.parts] == [2, 2]
    assert larger.commands[0].y == 26.48
    assert shifted.commands[0].y == 12
    assert measure_block(paragraph, context, 20) == first


def test_actual_ascent_can_reserve_another_grid_row(context):
    # IPAex Å at 12.5pt rises 11.43798828125pt above its baseline.
    paragraph = Paragraph("Å", style=TextStyle(size=12.5))
    measured = measure_block(paragraph, context, 20)
    assert measured.commands[0].y == 26.48
    assert measured.parts[0].rows == 2
    assert measured.commands[0].x == pytest.approx(.03662109375)


@pytest.mark.parametrize("kind", [Paragraph, Heading])
@pytest.mark.parametrize("kwargs", [
    {"text": None}, {"text": "日\t本"}, {"style": "body"},
    {"align": "spread"}, {"align": None}, {"block_id": 1},
    {"min_first": 0}, {"min_first": True}, {"min_first": 1.5},
    {"min_last": -1}, {"min_last": False}, {"min_last": "2"},
])
def test_paragraph_and_heading_validate_at_construction(kind, kwargs):
    with pytest.raises(ValueError):
        kind(**{"text": "日本", **kwargs})


@pytest.mark.parametrize("kind", [Paragraph, Heading])
def test_paragraph_and_heading_measure_validates_context_and_width(context, kind):
    block = kind("")
    with pytest.raises(ValueError, match="context"):
        block.measure(None, 20)
    for width in (0, -1, True, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="available_width"):
            block.measure(context, width)


def test_spacer_reserves_only_requested_grid_rows(context):
    spacer = Spacer(3)
    measured = measure_block(spacer, context, 32.16)
    assert measured.rows == 3 and measured.height == 46.44
    assert len(measured.parts) == 1 and measured.parts[0].commands == ()
    assert measured.commands == ()
    assert measure_block(Spacer(0), context, 32.16).parts == ()
    assert measure_block(spacer, context, 32.16) == measured
    with pytest.raises(FrozenInstanceError):
        spacer.rows = 2


@pytest.mark.parametrize("rows", [-1, True, 1.5, "2", None])
def test_spacer_validates_integer_rows_at_construction(rows):
    with pytest.raises(ValueError, match="rows"):
        Spacer(rows)


def test_spacer_measure_validates_context_and_width(context):
    with pytest.raises(ValueError, match="context"):
        Spacer(0).measure(None, 20)
    for width in (0, -1, True, float("inf")):
        with pytest.raises(ValueError, match="available_width"):
            Spacer(0).measure(context, width)


def test_page_break_is_an_immutable_flow_marker():
    marker = PageBreak()
    assert marker == PageBreak()
    assert not hasattr(marker, "measure")
    assert not hasattr(marker, "__dict__")


def test_paragraph_split_respects_two_first_and_last_display_lines(context):
    four = measure_block(Paragraph("日本語橋脚計算書"), context, 20)
    head, tail = four.split(3)
    assert (len(head.parts), len(tail.parts)) == (2, 2)
    assert [part.metadata["line_index"] for part in tail.parts] == [2, 3]
    assert tail.commands[0].y == 11
    assert four.minimum_rows == 2
    three = measure_block(Paragraph("日本語橋脚計"), context, 20)
    assert three.split(2) is None
    assert three.minimum_rows == 3
    assert len(measure_block(Paragraph("日本語"), context, 30).parts) == 1


def test_paragraph_explicit_or_context_minimum_lines_are_respected(context):
    context = replace(context, style=ReportStyle(min_first_lines=3, min_last_lines=1))
    measured = measure_block(Paragraph("日本語橋脚計算書"), context, 20)
    head, tail = measured.split(3)
    assert (len(head.parts), len(tail.parts)) == (3, 1)
    measured = measure_block(Paragraph("日本語橋脚計", min_first=1, min_last=1), context, 20)
    head, tail = measured.split(2)
    assert (len(head.parts), len(tail.parts)) == (2, 1)


@pytest.mark.parametrize("text, rows, values", [
    ("", 0, []), (" ", 1, [""]), ("\n", 2, ["", ""]),
    ("日\r\n\n本\r", 4, ["日", "", "本", ""]),
])
def test_paragraph_preserves_explicit_empty_lines_without_drawing_empty_text(context, text, rows, values):
    measured = measure_block(Paragraph(text), context, 30)
    assert measured.rows == rows
    assert [part.metadata["text"] for part in measured.parts] == values
    assert [command.text for command in measured.commands] == [value for value in values if value]


def test_paragraph_nfc_and_ink_alignment_match_draw_commands(context):
    normalized = measure_block(Paragraph("が\nj", align="right"), context, 10)
    assert measure_block(Paragraph("か\u3099\nj", align="right"), context, 10) == normalized
    assert normalized.commands[1].x == pytest.approx(6.9580078125)
    assert normalized.commands[1].style.size == 10


def test_paragraph_justification_uses_report_cap_and_keeps_last_line_natural(context):
    paragraph = Paragraph("日本語", align="justify")
    context = replace(context, style=ReportStyle(max_tracking_em=.08))
    measured = measure_block(paragraph, context, 20.8)
    assert measured.commands[0].style.tracking == pytest.approx(.8)
    assert measured.commands[1].style.tracking == 0
    natural = measure_block(paragraph, replace(context, style=ReportStyle()), 20.8)
    assert [command.text for command in natural.commands] == ["日本", "語"]
    assert all(command.style.tracking == 0 for command in natural.commands)


@pytest.mark.parametrize("base_tracking", [0, .2])
def test_paragraph_justification_fallback_keeps_natural_style_and_grid_height(context, base_tracking):
    style = TextStyle(size=10, tracking=base_tracking)
    paragraph = Paragraph("日本語橋脚", style=style, align="justify")
    measured = measure_block(paragraph, context, 25)
    assert [command.text for command in measured.commands] == ["日本", "語橋", "脚"]
    assert all(command.style is style for command in measured.commands)
    assert [part.rows for part in measured.parts] == [1, 1, 1]
    assert measured.rows == 3 and measured.height == 46.44
    assert [command.y for command in measured.commands] == pytest.approx([11, 26.48, 41.96])
    assert [context.fonts.measure(command.text, command.style).bounds.width
            for command in measured.commands] == pytest.approx([20 + base_tracking, 20 + base_tracking, 10])


@pytest.mark.parametrize("block_id", ["section.body", ""])
def test_paragraph_error_preserves_source_path_and_original_font_cause(context, block_id):
    with pytest.raises(FontError) as caught:
        measure_block(Paragraph("\U0010ffff", block_id=block_id), context, 20)
    assert (block_id or "Paragraph") in str(caught.value)
    assert "U+10FFFF" in str(caught.value)
    assert isinstance(caught.value.__cause__, FontError)
    with pytest.raises(LayoutOverflowError) as caught:
        measure_block(Paragraph("abcdefghijk", block_id=block_id), context, 20)
    assert caught.value.block_id == (block_id or "Paragraph")
    assert caught.value.needed > caught.value.available
