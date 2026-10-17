"""Horizontal text wrapping without resizing glyphs."""

from dataclasses import dataclass, replace
import unicodedata

from .errors import FontError, LayoutOverflowError
from .fonts import FontRegistry, TextMetrics
from .styles import TextStyle, _finite_number

_OPENING = frozenset("([{（［｛〔〈《「『【〖〘〚‘“｟«")
_CLOSING = frozenset(
    ")]}）］｝〕〉》」』】〗〙〛’”｠»、。，．・：；？！!?.,:;"
    "ー々ゝゞヽヾぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ"
)
_TOLERANCE = 1e-7


@dataclass(frozen=True, slots=True)
class TextLine:
    """A normalized line; x is its baseline origin, including bearing correction.

    paragraph_end marks the last line before an explicit newline or end of input.
    """

    text: str
    style: TextStyle
    metrics: TextMetrics
    x: float
    paragraph_end: bool

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if not isinstance(self.style, TextStyle):
            raise ValueError("style must be a TextStyle")
        if not isinstance(self.metrics, TextMetrics):
            raise ValueError("metrics must be TextMetrics")
        object.__setattr__(self, "x", _finite_number(self.x, "x"))
        if not isinstance(self.paragraph_end, bool):
            raise ValueError("paragraph_end must be a bool")


def _word_character(character: str) -> bool:
    return unicodedata.category(character).startswith("N") or "LATIN" in unicodedata.name(character, "")


def _numeric_separator(text, index):
    """A decimal point or digit-group comma between two digits joins one number (UAX #14, IS between NU)."""
    return (index >= 2 and text[index - 1] in ".," and unicodedata.category(text[index - 2]) == "Nd"
            and unicodedata.category(text[index]) == "Nd")


def _breaks(text):
    for index in range(1, len(text) + 1):
        if index < len(text):
            if _word_character(text[index - 1]) and _word_character(text[index]):
                continue
            if _numeric_separator(text, index):
                continue
            left, right = text[:index].rstrip(" "), text[index:].lstrip(" ")
            if (left and left[-1] in _OPENING) or (right and right[0] in _CLOSING):
                continue
        yield index


def _inputs(text, fonts, style, width, width_name, maximum, maximum_name, block_id):
    if not isinstance(fonts, FontRegistry):
        raise ValueError("fonts must be a FontRegistry")
    if not isinstance(style, TextStyle):
        raise ValueError("style must be a TextStyle")
    if not isinstance(block_id, str):
        raise ValueError("block_id must be a string")
    width = _finite_number(width, width_name)
    if width < 0 or (width_name == "available_width" and width == 0):
        raise ValueError(f"{width_name} must be {'positive' if width_name == 'available_width' else 'nonnegative'}")
    maximum = _finite_number(maximum, maximum_name)
    if maximum < 0:
        raise ValueError(f"{maximum_name} must be nonnegative")
    text = fonts.normalize_text(text)
    if "\t" in text:
        raise ValueError("text must not contain tabs")
    return text, width, maximum


def _measure(text, fonts, style, block_id):
    try:
        return fonts.measure(text, style)
    except FontError as exc:
        raise FontError(f"{block_id or 'text'}: {exc}") from exc


def wrap_text(
    text: str, fonts: FontRegistry, style: TextStyle, available_width: float, *,
    align: str = "left", max_tracking_em: float = .05, block_id: str = "",
) -> tuple[TextLine, ...]:
    """Wrap normalized text without changing size or horizontal glyph scale.

    ASCII spaces inside a line retain their exact count; spaces at hard/soft
    line edges are discarded. Other supported whitespace is measured normally.
    CRLF and CR become LF. An empty input has no lines, while every explicit
    newline, including a trailing newline, preserves its blank lines. Tabs are
    rejected. Contiguous Latin letters/numeric-category characters are words;
    Japanese characters (including kanji numerals) can break at basic kinsoku
    boundaries. This is horizontal Japanese/Latin wrapping, not a full Unicode
    line-breaking or complex-script shaping implementation.

    Justification fits only non-final soft lines. If bounded positive tracking
    cannot fill any valid candidate, retain the latest fitting legal break at
    the original tracking. A line that cannot fit naturally still raises.
    """
    text, available_width, max_tracking_em = _inputs(
        text, fonts, style, available_width, "available_width", max_tracking_em, "max_tracking_em", block_id)
    if align not in ("left", "right", "center", "justify"):
        raise ValueError("align must be left, right, center, or justify")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        return ()
    return tuple(line for paragraph in text.split("\n")
                 for line in _wrap_paragraph(paragraph, fonts, style, available_width, align,
                                             max_tracking_em, block_id))


def _line(text, fonts, style, available_width, align, paragraph_end, block_id):
    metrics = _measure(text, fonts, style, block_id)
    spare = available_width - metrics.bounds.width
    space = spare if align == "right" else spare / 2 if align == "center" else 0
    return TextLine(text, style, metrics, space - metrics.bounds.x, paragraph_end)


def _wrap_paragraph(text, fonts, style, available_width, align, max_tracking_em, block_id):
    lines = []
    text = text.strip(" ")
    _measure(text, fonts, style, block_id)
    if not text:
        return (_line("", fonts, style, available_width, align, True, block_id),)
    while text:
        end = 0
        candidates = []
        for index in _breaks(text):
            candidate = text[:index].rstrip(" ")
            metrics = _measure(candidate, fonts, style, block_id)
            if metrics.bounds.width > available_width + _TOLERANCE:
                break
            end = index
            candidates.append(index)
        if not end:
            raise LayoutOverflowError(f"{block_id or 'text'}: text {candidate!r} does not fit", block_id=block_id,
                                      needed=metrics.bounds.width,
                                      available=available_width)
        line_style = style
        if align == "justify" and end < len(text):
            for boundary in reversed(candidates):
                try:
                    line_style = fit_tracking(text[:boundary].rstrip(" "), fonts, style,
                                              available_width, max_extra_em=max_tracking_em,
                                              block_id=block_id)
                except LayoutOverflowError:
                    continue
                else:
                    end = boundary
                    break
        value, text = text[:end].rstrip(" "), text[end:].lstrip(" ")
        lines.append(_line(value, fonts, line_style, available_width, align, not text, block_id))
    return tuple(lines)


def fit_tracking(
    text: str, fonts: FontRegistry, style: TextStyle, target_width: float, *,
    max_extra_em: float = .05, block_id: str = "",
) -> TextStyle:
    """Fit one line by adding at most ``max_extra_em * size`` to each gap.

    Existing explicit tracking is retained. The target includes actual glyph
    bearings, so advance-width arithmetic alone is insufficient.
    """
    text, target_width, max_extra_em = _inputs(
        text, fonts, style, target_width, "target_width", max_extra_em, "max_extra_em", block_id)
    if "\n" in text or "\r" in text:
        raise ValueError("tracking requires a single line")
    natural = _measure(text, fonts, style, block_id).bounds.width
    if abs(natural - target_width) <= _TOLERANCE:
        return style
    if target_width < natural:
        raise LayoutOverflowError(
            f"{block_id or 'text'}: target {target_width:g} is smaller than text width {natural:g}; negative tracking is prohibited",
            block_id=block_id, needed=natural, available=target_width)
    if len(text) < 2:
        raise LayoutOverflowError(
            f"{block_id or 'text'}: cannot add tracking to {len(text)} characters without an intercharacter gap",
            block_id=block_id, needed=target_width, available=natural)
    maximum = replace(style, tracking=style.tracking + max_extra_em * style.size)
    limit = _measure(text, fonts, maximum, block_id).bounds.width
    if target_width > limit + _TOLERANCE:
        raise LayoutOverflowError(
            f"{block_id or 'text'}: target {target_width:g} exceeds width {limit:g} at tracking cap {max_extra_em:g}em",
            block_id=block_id, needed=target_width, available=limit)
    if abs(limit - target_width) <= _TOLERANCE:
        return maximum
    low, high = style.tracking, maximum.tracking
    # Bounds are continuous and nondecreasing, but can change slope as a glyph
    # overhang becomes the outer edge. Keep the lower, fitting side of the root.
    for _ in range(64):
        middle = (low + high) / 2
        candidate = replace(style, tracking=middle)
        width = _measure(text, fonts, candidate, block_id).bounds.width
        if width <= target_width:
            low = middle
        else:
            high = middle
    fitted = replace(style, tracking=low)
    if target_width - _measure(text, fonts, fitted, block_id).bounds.width > _TOLERANCE:
        raise LayoutOverflowError(
            f"{block_id or 'text'}: tracking cannot reach target width precisely",
            block_id=block_id, needed=target_width, available=limit)
    return fitted
