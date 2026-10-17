"""Immutable typographic settings shared by measuring and rendering."""

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class TextStyle:
    """A named font, point size, and extra spacing between characters."""

    font: str = "body"
    size: float = 10.0
    tracking: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.font, str) or not self.font.strip():
            raise ValueError("font must be a nonempty name")
        size = _finite_number(self.size, "size")
        tracking = _finite_number(self.tracking, "tracking")
        if size <= 0:
            raise ValueError("size must be positive")
        if tracking < 0:
            raise ValueError("tracking must be nonnegative")
        object.__setattr__(self, "size", size)
        object.__setattr__(self, "tracking", tracking)


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
