from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from gridlayoutpdf.errors import FontError, LayoutOverflowError
from gridlayoutpdf.fonts import FontRegistry, TextMetrics
from gridlayoutpdf.styles import TextStyle
from gridlayoutpdf.text import TextLine, fit_tracking, wrap_text


@pytest.fixture(scope="module")
def fonts():
    registry = FontRegistry()
    return registry


def test_japanese_wrap_uses_natural_ten_point_advance(fonts):
    style = TextStyle()
    lines = wrap_text("日本語橋脚", fonts, style, 32.16)
    assert [line.text for line in lines] == ["日本語", "橋脚"]
    assert [line.metrics.width for line in lines] == [30, 20]
    assert [line.paragraph_end for line in lines] == [False, True]
    assert all(line.style is style and line.x == 0 for line in lines)
    assert wrap_text("日本語橋脚", fonts, style, 32.16) == lines
    assert [line.text for line in wrap_text("日本語橋脚", fonts, style, 50)] == ["日本語橋脚"]
    assert [line.text for line in wrap_text("日本語橋脚", fonts, TextStyle(size=12), 32.16)] == ["日本", "語橋", "脚"]


def test_latin_alphanumeric_words_are_kept_and_boundary_spaces_trimmed(fonts):
    text = "  日本  AB12  test  語  "
    lines = wrap_text(text, fonts, TextStyle(), 43)
    assert [line.text for line in lines] == ["日本", "AB12", "test  語"]
    assert "".join(line.text for line in lines).replace(" ", "") == text.replace(" ", "")
    assert wrap_text("日本  語", fonts, TextStyle(), 100)[0].text == "日本  語"


def test_unbreakable_latin_token_reports_needed_width_and_block(fonts):
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_text("日本 abcdefghijklmnop", fonts, TextStyle(), 30, block_id="body[2]")
    assert caught.value.needed > 30
    assert caught.value.available == 30
    assert caught.value.block_id == "body[2]"
    assert "body[2]" in str(caught.value)
    assert "abcdefghijklmnop" in str(caught.value)


@pytest.mark.parametrize("text, expected", [
    ("", []), ("   ", [""]), ("\n", ["", ""]),
    ("日本\n\n語\n", ["日本", "", "語", ""]),
    ("日本\r\n語\r橋", ["日本", "語", "橋"]),
])
def test_explicit_newlines_preserve_blank_and_trailing_lines(fonts, text, expected):
    lines = wrap_text(text, fonts, TextStyle(), 100)
    assert [line.text for line in lines] == expected
    assert all(line.paragraph_end for line in lines)


def test_nfc_precedes_breaking_and_metrics(fonts):
    expected = wrap_text("ががが", fonts, TextStyle(), 20)
    assert [line.text for line in expected] == ["がが", "が"]
    assert wrap_text("か\u3099か\u3099か\u3099", fonts, TextStyle(), 20) == expected


@pytest.mark.parametrize("text, width, expected", [
    ("日本、語", 20, ["日", "本、", "語"]),
    ("日「本語」", 20, ["日", "「本", "語」"]),
    ("日（本）語", 30, ["日", "（本）", "語"]),
    ("日本 、語", 20, ["日", "本 、", "語"]),
])
def test_kinsoku_moves_break_before_closing_or_opening_group(fonts, text, width, expected):
    # A space before punctuation is preserved if internal, so give that case room.
    if " " in text:
        width = 23
    lines = wrap_text(text, fonts, TextStyle(), width)
    assert [line.text for line in lines] == expected
    assert "".join(line.text for line in lines).replace(" ", "") == text.replace(" ", "")


def test_kinsoku_unsplittable_group_overflow_is_explicit(fonts):
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_text("あ。", fonts, TextStyle(), 10, block_id="narrow")
    assert caught.value.needed == 20
    assert caught.value.available == 10
    assert caught.value.block_id == "narrow"
    # Hard line boundaries remain the caller's explicit instruction.
    assert [line.text for line in wrap_text("あ\n。", fonts, TextStyle(), 10)] == ["あ", "。"]


@pytest.mark.parametrize("width", [0, -1, True, float("inf"), float("nan"), "20", None])
def test_wrap_rejects_invalid_width_even_for_empty_input(fonts, width):
    with pytest.raises(ValueError, match="available_width"):
        wrap_text("", fonts, TextStyle(), width)


@pytest.mark.parametrize("kwargs", [
    {"align": "spread"}, {"align": []}, {"max_tracking_em": -1},
    {"max_tracking_em": True}, {"max_tracking_em": float("inf")}, {"block_id": 2},
])
def test_wrap_rejects_invalid_options(fonts, kwargs):
    with pytest.raises(ValueError):
        wrap_text("", fonts, TextStyle(), 20, **kwargs)


@pytest.mark.parametrize("text", [None, 3, "A\tB"])
def test_wrap_rejects_nontext_or_tab(fonts, text):
    with pytest.raises(ValueError):
        wrap_text(text, fonts, TextStyle(), 20)


@pytest.mark.parametrize("text, style, diagnostic", [
    ("語\U0010ffff", TextStyle(), "U+10FFFF"),
    ("か\u3099\u3099", TextStyle(), "U+3099"),
    ("語", TextStyle(font="unknown"), "unknown"),
])
def test_font_diagnostics_keep_block_path_and_cause(fonts, text, style, diagnostic):
    with pytest.raises(FontError) as caught:
        wrap_text(text, fonts, style, 100, block_id="section[2].body")
    assert "section[2].body" in str(caught.value)
    assert diagnostic in str(caught.value)
    assert isinstance(caught.value.__cause__, FontError)


def test_wrap_validates_style_and_font_registry(fonts):
    with pytest.raises(ValueError, match="style"):
        wrap_text("", fonts, None, 20)
    with pytest.raises(ValueError, match="fonts"):
        wrap_text("", None, TextStyle(), 20)


@pytest.mark.parametrize("align, origin", [("left", .5419921875), ("right", 6.9580078125), ("center", 3.75)])
def test_alignment_uses_actual_ink_and_compensates_negative_bearing(fonts, align, origin):
    line, = wrap_text("j", fonts, TextStyle(), 10, align=align)
    assert line.x == pytest.approx(origin)
    assert line.metrics.width == 3.0419921875
    assert line.metrics.bounds.width == 3.583984375
    assert line.x + line.metrics.bounds.x >= 0
    assert line.x + line.metrics.bounds.right <= 10


def test_overhang_must_fit_even_when_advance_fits(fonts):
    for text, width in [("j", 3.1), ("Å", 7.25), ("√", 5.4)]:
        with pytest.raises(LayoutOverflowError):
            wrap_text(text, fonts, TextStyle(), width)


@pytest.mark.parametrize("align, x", [("left", 0), ("justify", 0), ("center", 10), ("right", 20)])
def test_blank_line_alignment_is_defined(fonts, align, x):
    line, = wrap_text(" ", fonts, TextStyle(), 20, align=align)
    assert line.x == x


def test_tracking_only_adds_intercharacter_space_without_changing_size(fonts):
    original = TextStyle(size=10, tracking=.2)
    fitted = fit_tracking("日本語", fonts, original, 31)
    assert fitted.size == 10 and fitted.font == original.font
    assert fitted.tracking == pytest.approx(.5)
    assert original.tracking == .2
    assert fonts.measure("日本語", fitted).bounds.width == pytest.approx(31)
    assert fit_tracking("日本語", fonts, fitted, 31) is fitted
    assert fit_tracking("日", fonts, original, 10) is original
    assert fit_tracking("", fonts, original, 0) is original


def test_tracking_uses_actual_bounds_for_overhang_and_nfc(fonts):
    fitted = fit_tracking("jÅ", fonts, TextStyle(tracking=.25), 11.3)
    assert fitted.tracking == pytest.approx(.4064453125)
    assert fonts.measure("jÅ", fitted).bounds.width == pytest.approx(11.3)
    fitted = fit_tracking("か\u3099か\u3099", fonts, TextStyle(), 20.4)
    assert fitted.tracking == pytest.approx(.4)


@pytest.mark.parametrize("text, target, cap", [
    ("日本", 19, .05), ("日本", 20.6, .05), ("日", 11, .05),
    ("", 1, .05), ("日本", 20.1, 0),
])
def test_impossible_tracking_fit_fails_with_widths_and_block(fonts, text, target, cap):
    with pytest.raises(LayoutOverflowError) as caught:
        fit_tracking(text, fonts, TextStyle(), target, max_extra_em=cap, block_id="label[1]")
    assert caught.value.block_id == "label[1]"
    assert "label[1]" in str(caught.value)
    assert caught.value.needed is not None and caught.value.available is not None


def test_tracking_cap_applies_only_to_automatic_addition(fonts):
    style = TextStyle(tracking=2)
    fitted = fit_tracking("日本", fonts, style, 22.5)
    assert fitted.tracking == pytest.approx(2.5)
    with pytest.raises(LayoutOverflowError):
        fit_tracking("日本", fonts, style, 21)


@pytest.mark.parametrize("kwargs", [
    {"target_width": -1}, {"target_width": True}, {"target_width": float("inf")},
    {"target_width": float("nan")}, {"max_extra_em": -1}, {"max_extra_em": True},
    {"max_extra_em": float("nan")}, {"block_id": 3},
])
def test_tracking_rejects_invalid_numeric_options(fonts, kwargs):
    options = {"target_width": 20, **kwargs}
    with pytest.raises(ValueError):
        fit_tracking("日本", fonts, TextStyle(), **options)


def test_tracking_is_single_line_and_keeps_font_diagnostics(fonts):
    for text in ("日\n本", "日\r本", "日\t本"):
        with pytest.raises(ValueError):
            fit_tracking(text, fonts, TextStyle(), 30)
    with pytest.raises(FontError, match="label") as caught:
        fit_tracking("\U0010ffff", fonts, TextStyle(), 20, block_id="label")
    assert isinstance(caught.value.__cause__, FontError)


def test_justification_only_fits_nonfinal_soft_lines(fonts):
    style = TextStyle()
    lines = wrap_text("日本語橋脚\n日本\n", fonts, style, 20.4, align="justify")
    assert [line.text for line in lines] == ["日本", "語橋", "脚", "日本", ""]
    assert [line.paragraph_end for line in lines] == [False, False, True, True, True]
    assert [line.style.tracking for line in lines] == pytest.approx([.4, .4, 0, 0, 0])
    assert [line.metrics.bounds.width for line in lines] == pytest.approx([20.4, 20.4, 10, 20, 0])
    assert all(line.style.size == 10 for line in lines)


def test_justification_falls_back_to_latest_natural_break_when_cap_cannot_fill(fonts):
    style = TextStyle()
    lines = wrap_text("日本語橋脚", fonts, style, 25, align="justify", block_id="body")
    assert [line.text for line in lines] == ["日本", "語橋", "脚"]
    assert [line.metrics.bounds.width for line in lines] == [20, 20, 10]
    assert all(line.style is style and line.x == 0 for line in lines)
    assert lines == wrap_text("日本語橋脚", fonts, style, 25)
    single_character_lines = wrap_text("日本", fonts, style, 10.2, align="justify")
    assert [line.text for line in single_character_lines] == ["日", "本"]
    assert all(line.style is style for line in single_character_lines)
    with pytest.raises(LayoutOverflowError) as caught:
        wrap_text("あ。", fonts, style, 10, align="justify", block_id="narrow")
    assert caught.value.block_id == "narrow"
    assert (caught.value.needed, caught.value.available) == (20, 10)


def test_justification_honors_base_tracking_and_explicit_extra_cap(fonts):
    lines = wrap_text("日本語", fonts, TextStyle(tracking=.2), 20.8,
                      align="justify", max_tracking_em=.06)
    assert lines[0].style.tracking == pytest.approx(.8)
    assert lines[-1].style.tracking == .2
    natural = wrap_text("日本語", fonts, TextStyle(tracking=.2), 20.8, align="justify")
    assert [line.text for line in natural] == ["日本", "語"]
    assert [line.style.tracking for line in natural] == [.2, .2]
    assert [line.metrics.bounds.width for line in natural] == pytest.approx([20.2, 10])


def test_text_line_is_immutable_and_validated(fonts):
    line, = wrap_text("日本", fonts, TextStyle(), 20)
    with pytest.raises(FrozenInstanceError):
        line.x = 10
    values = dict(text="日", style=TextStyle(), metrics=TextMetrics(10, 9, 2), x=0, paragraph_end=True)
    for key, invalid in [("text", None), ("style", None), ("metrics", None),
                         ("x", True), ("x", float("nan")), ("paragraph_end", 1)]:
        with pytest.raises(ValueError, match=key):
            TextLine(**{**values, key: invalid})


def test_wrap_tolerates_only_floating_point_roundoff_at_width_boundary(fonts):
    # 0.5 pt steps (FR-023) whose measured width exceeds the exact width by roundoff.
    assert fonts.measure("日本語", TextStyle(size=4.5)).width > 13.5
    assert fonts.measure("日本語", TextStyle(size=9)).width > 27
    assert [line.text for line in wrap_text("日本語", fonts, TextStyle(size=4.5), 13.5)] == ["日本語"]
    assert [line.text for line in wrap_text("日本語", fonts, TextStyle(size=4.5), 13.499)] == ["日本", "語"]
    assert [line.text for line in wrap_text("日本語", fonts, TextStyle(size=9), 27)] == ["日本語"]


def test_cjk_numerals_are_breakable_but_fullwidth_latin_numbers_are_words(fonts):
    assert [line.text for line in wrap_text("一二三四", fonts, TextStyle(), 20)] == ["一二", "三四"]
    with pytest.raises(LayoutOverflowError):
        wrap_text("ＡＢ１２", fonts, TextStyle(), 30)


def test_a_decimal_point_or_digit_group_separator_between_digits_is_not_a_break(fonts):
    # UAX #14 (IS between NU): 2.200 and 1,234.5 are one number; the line breaks before them.
    assert [line.text for line in wrap_text("日本語2.200", fonts, TextStyle(), 45)] == ["日本語", "2.200"]
    assert [line.text for line in wrap_text("長さ1,234.5", fonts, TextStyle(), 50)] == ["長さ", "1,234.5"]
    # A separator not between two digits still allows the break after it.
    assert [line.text for line in wrap_text("日本語2.日本", fonts, TextStyle(), 45)] == ["日本語2.", "日本"]
    assert [line.text for line in wrap_text("日本語、200", fonts, TextStyle(), 45)] == ["日本語、", "200"]


def test_fit_tracking_accepts_a_script_style_and_keeps_its_size(fonts):
    from gridlayoutpdf.styles import _script_style
    script = _script_style(TextStyle(size=12), .65)
    target = fonts.measure("ab", script).width + .1
    fitted = fit_tracking("ab", fonts, script, target)
    assert fitted.size == script.size and fitted.tracking > script.tracking
