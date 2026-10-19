from dataclasses import FrozenInstanceError, replace

import pytest

from gridlayoutpdf.styles import TextStyle, _script_style


def test_text_style_defaults_and_explicit_settings_are_immutable():
    style = TextStyle()
    assert (style.font, style.size, style.tracking) == ("IPAex明朝", 10.0, 0.0)
    custom = TextStyle(font="math", size=7.5, tracking=0.2)
    assert (custom.font, custom.size, custom.tracking) == ("math", 7.5, 0.2)
    with pytest.raises(FrozenInstanceError):
        custom.size = 9


@pytest.mark.parametrize("size", [0, -1, True, float("nan"), float("inf"), "10", None])
def test_size_must_be_a_finite_positive_number(size):
    with pytest.raises(ValueError, match="size"):
        TextStyle(size=size)


@pytest.mark.parametrize("tracking", [-0.1, True, float("nan"), float("inf"), "0", None])
def test_tracking_must_be_finite_and_nonnegative(tracking):
    with pytest.raises(ValueError, match="tracking"):
        TextStyle(tracking=tracking)


@pytest.mark.parametrize("font", ["", " ", None, 1])
def test_font_name_must_be_nonempty_text(font):
    with pytest.raises(ValueError, match="font"):
        TextStyle(font=font)


# FR-023: sizes are 0.5 pt steps across the library (PDF and grid Excel).
@pytest.mark.parametrize("size", [9.9, 9.8, 9.058, 8.056, 0.1, 0.25, 1.1, 7.8, 10.25, 10.4])
def test_size_must_be_a_half_point_step(size):
    with pytest.raises(ValueError, match=r"size must be a multiple of 0\.5 pt"):
        TextStyle(size=size)


@pytest.mark.parametrize("size", [0.5, 1, 6.5, 7.5, 9, 9.5, 10, 10.5, 12, 409])
def test_half_point_sizes_are_accepted_exactly(size):
    style = TextStyle(size=size)
    assert style.size == float(size)
    assert type(style.size) is float


def test_floating_point_noise_snaps_to_the_intended_half_point_step():
    for noisy, intended in ((0.1 * 3 * 15, 4.5), (12 * 0.7 * 0.5 + 0.1 * 3, 4.5)):
        assert noisy != intended
        assert TextStyle(size=noisy).size == intended


def test_replace_applies_the_same_half_point_rule():
    style = TextStyle("MS Mincho", size=10)
    assert replace(style, size=9.5).size == 9.5
    with pytest.raises(ValueError, match=r"multiple of 0\.5 pt"):
        replace(style, size=9.9)


def test_script_sizes_come_only_from_the_internal_scaled_style():
    base = TextStyle("MS Mincho", size=12, tracking=.2)
    script = _script_style(base, .65)
    assert (script.font, script.size, script.tracking) == ("MS Mincho", pytest.approx(7.8), .2)
    nested = _script_style(script, .65)
    assert nested.size == pytest.approx(12 * .65 * .65)
    assert isinstance(nested, TextStyle)
    # Public construction keeps the rule: no loophole via the derived size.
    with pytest.raises(ValueError, match=r"multiple of 0\.5 pt"):
        TextStyle(script.font, script.size, script.tracking)
    # Re-creating the script style with its own size keeps the exemption, so a
    # custom MathNode inside a script may still change the font or tracking.
    assert replace(script).size == script.size
    assert replace(script, font="IPAexゴシック", tracking=.3).size == script.size
    assert replace(script, tracking=.3) == replace(replace(script, tracking=.3))
    # A new size, even through replace() of a script style, follows the rule.
    with pytest.raises(ValueError, match=r"multiple of 0\.5 pt"):
        replace(script, size=9.9)
    assert replace(script, size=9.5).size == 9.5


def test_on_step_script_sizes_are_plain_text_styles():
    # 10 pt x 0.65 = 6.5 pt is itself a 0.5 pt step; it needs no exemption.
    script = _script_style(TextStyle(size=10), .65)
    assert type(script) is TextStyle and script == TextStyle(size=6.5)
    off = _script_style(TextStyle(size=12), .65)
    assert off == _script_style(TextStyle(size=12), .65)
    assert hash(off) == hash(_script_style(TextStyle(size=12), .65))


@pytest.mark.parametrize("scale", [0, -1, 1.01, True, float("nan"), float("inf"), "0.5", None])
def test_internal_scaled_style_rejects_invalid_scale(scale):
    with pytest.raises(ValueError, match="scale"):
        _script_style(TextStyle(), scale)


@pytest.mark.parametrize("style", [None, 10, "IPAex明朝"])
def test_internal_scaled_style_requires_a_text_style(style):
    with pytest.raises(ValueError, match="style"):
        _script_style(style, .65)


def test_half_point_check_handles_extreme_magnitudes():
    # Every float this large is a whole number, so it is a 0.5 pt step; the
    # check must not overflow. Measuring then reports the non-finite metrics.
    assert TextStyle(size=1e308).size == 1e308
    # Within roundoff of 0 pt: below the smallest step rather than off-step.
    with pytest.raises(ValueError, match=r"at least 0\.5 pt"):
        TextStyle(size=1e-12)
    with pytest.raises(ValueError, match=r"multiple of 0\.5 pt"):
        TextStyle(size=0.25)
