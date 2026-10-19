"""Immutable typographic settings shared by measuring and rendering."""

from dataclasses import dataclass, field
import math

from .validation import _finite_number, _integer


@dataclass(frozen=True, slots=True)
class Insets:
    """Nonnegative point distances in top, right, bottom, left order."""

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    def __post_init__(self) -> None:
        for name in ("top", "right", "bottom", "left"):
            value = _finite_number(getattr(self, name), name)
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
            object.__setattr__(self, name, value)


def _resolve_insets(value: float | Insets, name: str) -> Insets:
    if isinstance(value, Insets):
        return value
    scalar = _finite_number(value, name)
    if scalar < 0:
        raise ValueError(f"{name} must be nonnegative")
    return Insets(scalar, scalar, scalar, scalar)


# Font sizes are multiples of this many points (FR-023).
_SIZE_STEP = 0.5
_SIZE_STEP_TOLERANCE = 1e-9


def _half_point_step(size: float) -> float:
    """Return a positive ``size`` snapped to its 0.5 pt step, rejecting others.

    Only floating-point noise (for example ``0.1 * 3 * 15``) is snapped;
    a size such as 9.9 pt is an error rather than being rounded silently.
    The remainder is exact (``math.fmod``) and cannot overflow.
    """
    remainder = math.fmod(size, _SIZE_STEP)
    if remainder <= _SIZE_STEP_TOLERANCE:
        snapped = size - remainder
    elif _SIZE_STEP - remainder <= _SIZE_STEP_TOLERANCE:
        snapped = size - remainder + _SIZE_STEP
    else:
        raise ValueError(f"size must be a multiple of 0.5 pt (got {size!r})")
    if snapped < _SIZE_STEP:
        raise ValueError(f"size must be at least 0.5 pt (got {size!r})")
    return snapped


def _check_text_style(style: "TextStyle", *, half_point_step: bool) -> None:
    if not isinstance(style.font, str) or not style.font.strip():
        raise ValueError("font must be a nonempty name")
    size = _finite_number(style.size, "size")
    tracking = _finite_number(style.tracking, "tracking")
    if size <= 0:
        raise ValueError("size must be positive")
    if half_point_step:
        size = _half_point_step(size)
    if tracking < 0:
        raise ValueError("tracking must be nonnegative")
    object.__setattr__(style, "size", size)
    object.__setattr__(style, "tracking", tracking)


@dataclass(frozen=True, slots=True)
class TextStyle:
    """A font name, point size, and extra spacing between characters.

    ``font`` is a family or full name from the font file, in English or
    Japanese. It is looked up only when text is measured or drawn.
    ``size`` is a positive multiple of 0.5 pt, the step of Excel font sizes,
    so PDF and grid Excel output share one size (FR-023). Construction and
    ``dataclasses.replace`` both enforce it; only the scaled sizes of math
    scripts are exempt (see ``_script_style``).
    """

    font: str = "IPAex明朝"
    size: float = 10.0
    tracking: float = 0.0

    def __post_init__(self) -> None:
        _check_text_style(self, half_point_step=True)


@dataclass(frozen=True, slots=True)
class ReportStyle:
    """Shared body/heading typography and paragraph fragmentation preferences."""

    body: TextStyle = TextStyle()
    heading: TextStyle = TextStyle(size=12)
    baseline_offset: float = 11.0
    max_tracking_em: float = 0.05
    min_first_lines: int = 2
    min_last_lines: int = 2

    def __post_init__(self) -> None:
        for name in ("body", "heading"):
            if not isinstance(getattr(self, name), TextStyle):
                raise ValueError(f"{name} must be a TextStyle")
        baseline = _finite_number(self.baseline_offset, "baseline_offset")
        tracking = _finite_number(self.max_tracking_em, "max_tracking_em")
        if baseline <= 0:
            raise ValueError("baseline_offset must be positive")
        if tracking < 0:
            raise ValueError("max_tracking_em must be nonnegative")
        for name in ("min_first_lines", "min_last_lines"):
            _integer(getattr(self, name), name, 1,
                     message=f"{name} must be a positive integer")
        object.__setattr__(self, "baseline_offset", baseline)
        object.__setattr__(self, "max_tracking_em", tracking)


@dataclass(frozen=True, slots=True)
class _ScriptTextStyle(TextStyle):
    """Internal: a math script's style whose size is off the 0.5 pt steps.

    The size is exempt only while it equals ``_script_size``, the size that
    ``_script_style`` derived from ``Script.scale``. ``dataclasses.replace``
    keeps that value, so a custom MathNode inside a script may change the
    font or tracking; any other size follows the ``TextStyle`` rule again.
    Neither this class nor ``_script_size`` is public API.
    """

    _script_size: float = field(default=0.0, repr=False, compare=False)

    def __post_init__(self) -> None:
        exempt = self._script_size
        _check_text_style(self, half_point_step=not (
            type(exempt) is float and math.isfinite(exempt) and exempt > 0
            and type(self.size) is float and self.size == exempt))


def _script_style(style: TextStyle, scale: float) -> TextStyle:
    """The style of a math script at ``scale`` times its base size (internal).

    Script sizes follow ``Script.scale`` (12 pt x 0.65 = 7.8 pt, nested
    scripts scale again) and are exempt from the 0.5 pt rule (FR-023): grid
    Excel writes them as superscript/subscript runs, not as font sizes. This
    is the only path that builds an exempt style. A size that is exactly a
    0.5 pt step (10 pt x 0.65 = 6.5 pt) is returned as a plain ``TextStyle``.
    ``scale`` is in (0, 1], so a script never grows beyond a checked base.
    """
    if not isinstance(style, TextStyle):
        raise ValueError("style must be a TextStyle")
    scale = _finite_number(scale, "scale")
    if not 0 < scale <= 1:
        raise ValueError("scale must be greater than zero and at most one")
    size = style.size * scale
    if not size > 0:
        raise ValueError("scaled script size must be positive")
    if math.fmod(size, _SIZE_STEP) == 0:
        return TextStyle(style.font, size, style.tracking)
    return _ScriptTextStyle(style.font, size, style.tracking, _script_size=size)
