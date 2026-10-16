"""Structured mathematics measured in pt relative to baseline (0, 0)."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math as _math
from typing import Protocol, cast, runtime_checkable

from .errors import LayoutError
from .fonts import FontRegistry
from .geometry import Point
from .scene import Command, Line, Polyline, Rectangle, Text
from .styles import TextStyle, _finite_number


def _validate_context(fonts: FontRegistry, style: TextStyle) -> None:
    if not isinstance(style, TextStyle):
        raise ValueError("style must be a TextStyle")
    if (
        not callable(getattr(fonts, "measure", None))
        or not callable(getattr(fonts, "normalize_text", None))
    ):
        raise ValueError("fonts must provide text measurement and normalization")


@dataclass(frozen=True, slots=True)
class MathBox:
    """Nonnegative extents and commands; axis is a distance above baseline."""

    width: float
    ascent: float
    descent: float
    commands: tuple[Command, ...]
    axis: float

    def __post_init__(self) -> None:
        for name in ("width", "ascent", "descent", "axis"):
            value = _finite_number(getattr(self, name), name)
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
            object.__setattr__(self, name, value)
        _finite_number(self.height, "height")
        try:
            commands = tuple(self.commands)
        except TypeError as exc:
            raise ValueError("commands must be a sequence of drawing commands") from exc
        if any(not isinstance(command, (Text, Line, Polyline, Rectangle)) for command in commands):
            raise ValueError("commands must contain supported drawing commands")
        object.__setattr__(self, "commands", commands)

    @property
    def height(self) -> float:
        return self.ascent + self.descent

    def translated(self, dx: float, dy: float) -> tuple[Command, ...]:
        dx = _finite_number(dx, "dx")
        dy = _finite_number(dy, "dy")
        return tuple(command.translated(dx, dy) for command in self.commands)


@runtime_checkable
class MathNode(Protocol):
    """The narrow measuring contract shared by structured math components."""

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox: ...


@dataclass(frozen=True, slots=True)
class Literal:
    """A single text atom; the text is never interpreted as TeX."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or any(c in self.text for c in "\n\r\t"):
            raise ValueError("text must be a single-line string without tabs")

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        _validate_context(fonts, style)
        text = fonts.normalize_text(self.text)
        metrics = fonts.measure(text, style)
        bounds = metrics.bounds
        return MathBox(
            bounds.width, max(0, -bounds.y), max(0, bounds.bottom),
            (Text(-bounds.x, 0, text, style),), style.size * 0.25,
        )


@dataclass(frozen=True, slots=True)
class Symbol(Literal):
    """A symbolic text atom."""


@dataclass(frozen=True, slots=True)
class Operator(Literal):
    """An operator atom retaining its role for later structural wrapping."""


@dataclass(frozen=True, slots=True)
class BreakHint:
    """A semantic boundary interpreted only by top-level equation wrapping."""

    mode: str = "preferred"

    def __post_init__(self) -> None:
        if not isinstance(self.mode, str) or self.mode not in ("forced", "preferred", "allowed"):
            raise ValueError("mode must be forced, preferred, or allowed")

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        raise LayoutError("BreakHint requires equation wrapping")


@dataclass(frozen=True, slots=True, init=False)
class Row:
    """Math atoms on a shared axis; default gaps are 0.15 times text size."""

    items: tuple[MathNode, ...]
    gap: float | None

    def __init__(self, *items: MathNode | str, gap: float | None = None) -> None:
        if gap is not None:
            gap = _finite_number(gap, "gap")
            if gap < 0:
                raise ValueError("gap must be nonnegative")
        object.__setattr__(self, "items", tuple(as_math(item) for item in items))
        object.__setattr__(self, "gap", gap)

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        _validate_context(fonts, style)
        axis = style.size * 0.25
        gap = style.size * 0.15 if self.gap is None else self.gap
        commands: list[Command] = []
        width = ascent = descent = 0.0
        for index, item in enumerate(self.items):
            box = item.measure(fonts, style)
            dy = box.axis - axis
            if index:
                width += gap
            commands.extend(box.translated(width, dy))
            width += box.width
            ascent = max(ascent, box.ascent - dy)
            descent = max(descent, box.descent + dy)
        return MathBox(width, ascent, descent, tuple(commands), axis)


@dataclass(frozen=True, slots=True)
class Fraction:
    """A stacked fraction with unscaled numerator and denominator."""

    numerator: MathNode | str
    denominator: MathNode | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "numerator", as_math(self.numerator))
        object.__setattr__(self, "denominator", as_math(self.denominator))

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        _validate_context(fonts, style)
        numerator = cast(MathNode, self.numerator).measure(fonts, style)
        denominator = cast(MathNode, self.denominator).measure(fonts, style)
        axis = style.size * 0.25
        padding = gap = style.size * 0.15
        stroke = style.size * 0.05
        width = max(numerator.width, denominator.width) + 2 * padding
        numerator_y = -axis - stroke / 2 - gap - numerator.descent
        denominator_y = -axis + stroke / 2 + gap + denominator.ascent
        commands = (
            *numerator.translated((width - numerator.width) / 2, numerator_y),
            *denominator.translated((width - denominator.width) / 2, denominator_y),
            Line(stroke / 2, -axis, width - stroke / 2, -axis, width=stroke),
        )
        return MathBox(
            width,
            max(0, numerator.ascent - numerator_y, axis + stroke / 2),
            max(0, denominator_y + denominator.descent, -axis + stroke / 2),
            commands, axis,
        )


@dataclass(frozen=True, slots=True)
class Script:
    """A base with optional upper/lower scripts at 65% of its text size."""

    base: MathNode | str
    superscript: MathNode | str | None = None
    subscript: MathNode | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "base", as_math(self.base))
        for name in ("superscript", "subscript"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, as_math(value))

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        _validate_context(fonts, style)
        base = cast(MathNode, self.base).measure(fonts, style)
        axis = style.size * 0.25
        base_y = base.axis - axis
        ascent = max(0, base.ascent - base_y)
        descent = max(0, base.descent + base_y)
        commands = list(base.translated(0, base_y))
        if self.superscript is None and self.subscript is None:
            return MathBox(base.width, ascent, descent, tuple(commands), axis)
        script_style = replace(style, size=style.size * 0.65)
        upper_node = cast(MathNode | None, self.superscript)
        lower_node = cast(MathNode | None, self.subscript)
        upper = upper_node.measure(fonts, script_style) if upper_node is not None else None
        lower = lower_node.measure(fonts, script_style) if lower_node is not None else None
        upper_y = -max(style.size * 0.6, ascent - style.size * 0.2,
                       upper.descent + style.size * 0.15) if upper is not None else 0.0
        lower_y = max(style.size * 0.3, descent + style.size * 0.1,
                      lower.ascent - style.size * 0.1) if lower is not None else 0.0
        if upper is not None and lower is not None:
            lower_y = max(lower_y, upper_y + upper.descent + style.size * 0.15 + lower.ascent)
        script_x = base.width + style.size * 0.1
        width = base.width
        for box, y in ((upper, upper_y), (lower, lower_y)):
            if box is not None:
                commands.extend(box.translated(script_x, y))
                width = max(width, script_x + box.width)
                ascent = max(ascent, box.ascent - y)
                descent = max(descent, box.descent + y)
        return MathBox(width, ascent, descent, tuple(commands), axis)


@dataclass(frozen=True, slots=True)
class Root:
    """A square root formed from vector strokes around its body."""

    body: MathNode | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", as_math(self.body))

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        _validate_context(fonts, style)
        body = cast(MathNode, self.body).measure(fonts, style)
        axis = style.size * 0.25
        body_y = body.axis - axis
        stroke = style.size * 0.05
        lead = style.size * 0.65
        body_x = lead + style.size * 0.1
        width = body_x + body.width + style.size * 0.1
        bar_y = body_y - body.ascent - style.size * 0.15 - stroke / 2
        bottom_y = max(0, body_y + body.descent) - stroke / 2
        points = (
            Point(stroke / 2, -axis + style.size * 0.1),
            Point(lead * 0.22, -axis + style.size * 0.05),
            Point(lead * 0.48, bottom_y),
            Point(lead, bar_y),
            Point(width - stroke / 2, bar_y),
        )
        return MathBox(
            width,
            max(0, body.ascent - body_y, -min(p.y for p in points) + stroke / 2),
            max(0, body.descent + body_y, max(p.y for p in points) + stroke / 2),
            (Polyline(points, width=stroke), *body.translated(body_x, body_y)),
            axis,
        )


@dataclass(frozen=True, slots=True)
class Delimited:
    """Vector round/square brackets or bars around a structured body."""

    body: MathNode | str
    left: str = "("
    right: str = ")"

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", as_math(self.body))
        if not isinstance(self.left, str) or self.left not in ("(", "[", "|", ""):
            raise ValueError("unsupported left delimiter; expected (, [, |, or empty")
        if not isinstance(self.right, str) or self.right not in (")", "]", "|", ""):
            raise ValueError("unsupported right delimiter; expected ), ], |, or empty")

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        _validate_context(fonts, style)
        body = cast(MathNode, self.body).measure(fonts, style)
        axis = style.size * 0.25
        body_y = body.axis - axis
        body_ascent = max(0, body.ascent - body_y)
        body_descent = max(0, body.descent + body_y)
        if not self.left and not self.right:
            return MathBox(body.width, body_ascent, body_descent, body.translated(0, body_y), axis)
        stroke = style.size * 0.05
        slot = style.size * 0.4
        gap = style.size * 0.1
        radius = max(body_ascent - axis, body_descent + axis, style.size * 0.25) + gap
        body_x = slot + gap if self.left else 0.0
        width = body_x + body.width + (slot + gap if self.right else 0.0)
        commands = list(body.translated(body_x, body_y))
        if self.left:
            commands.append(_delimiter(self.left, 0, slot, axis, radius, stroke))
        if self.right:
            commands.append(_delimiter(self.right, body_x + body.width + gap, slot, axis, radius, stroke))
        return MathBox(width, axis + radius, max(0, radius - axis), tuple(commands), axis)


def _delimiter(symbol: str, x: float, slot: float, axis: float, radius: float, stroke: float) -> Polyline:
    """Sample round brackets; all paths remain half a stroke inside their box."""
    half = stroke / 2
    left, right = x + half, x + slot - half
    top, bottom = -axis - radius + half, -axis + radius - half
    if symbol in ("(", ")"):
        points = []
        for index in range(25):
            angle = -_math.pi / 2 + index * _math.pi / 24
            curve_x = 1 - _math.cos(angle) if symbol == "(" else _math.cos(angle)
            points.append(Point(left + (slot - stroke) * curve_x,
                                -axis + (radius - half) * _math.sin(angle)))
    elif symbol == "[":
        points = [Point(right, top), Point(left, top), Point(left, bottom), Point(right, bottom)]
    elif symbol == "]":
        points = [Point(left, top), Point(right, top), Point(right, bottom), Point(left, bottom)]
    else:
        points = [Point(x + slot / 2, top), Point(x + slot / 2, bottom)]
    return Polyline(tuple(points), width=stroke)


def as_math(value: MathNode | str) -> MathNode:
    """Lift literal strings while keeping existing structured nodes."""
    if isinstance(value, str):
        return Literal(value)
    if isinstance(value, MathNode) and callable(value.measure):
        return value
    raise ValueError("expected a math node or literal string")
