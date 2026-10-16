from dataclasses import FrozenInstanceError

import pytest

from gridlayoutpdf.styles import TextStyle


def test_text_style_defaults_and_explicit_settings_are_immutable():
    style = TextStyle()
    assert (style.font, style.size, style.tracking) == ("body", 10.0, 0.0)
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
