"""Structured mathematics measured in pt relative to baseline (0, 0)."""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
import math as _math
from typing import Protocol, cast, runtime_checkable

from .bounds import command_bounds, transformed_text_bounds
from .errors import LayoutError
from .fonts import FontRegistry, TextMetrics
from .geometry import Point, Rect
from .scene import Circle, Command, Line, Polyline, Rectangle, Text
from .semantics import Kind, Role, Scope, Tag, tagged, within
from .styles import TextStyle, _finite_number, _script_style


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
        if any(not isinstance(command, (Text, Line, Polyline, Rectangle, Circle)) for command in commands):
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


def _within(box: MathBox, kind: Kind, part: str | None = None, index: int | None = None) -> MathBox:
    """Return the box with every command inside one more structure (outermost)."""
    return MathBox(box.width, box.ascent, box.descent,
                   within(box.commands, Scope(kind, part, index)), box.axis)


# The tag of a glyph run, by atom: Literal, Symbol, Operator, or an equation's relation.
_ATOM_TAGS = {atom: Tag(Role.MATH, (), {"atom": atom}) for atom in ("literal", "symbol", "operator", "relation")}


def _part_tag(role: Role, kind: Kind, part: str, **data) -> Tag:
    """The tag of a stroke a structure draws itself (a bar, a sign, a bracket)."""
    return Tag(role, (Scope(kind, part),), data)


def literal_box(text: str, metrics: TextMetrics, style: TextStyle) -> MathBox:
    """Build a text atom's box from metrics already measured for that text."""
    bounds = metrics.bounds
    return MathBox(
        bounds.width, max(0, -bounds.y), max(0, bounds.bottom),
        (Text(-bounds.x, 0, text, style),), style.size * 0.25,
    )


def compose_row(boxes, gap: float, axis: float) -> MathBox:
    """Place measured boxes left to right on one axis, separated by gap."""
    commands: list[Command] = []
    width = ascent = descent = 0.0
    for index, box in enumerate(boxes):
        dy = box.axis - axis
        if index:
            width += gap
        commands.extend(box.translated(width, dy))
        width += box.width
        ascent = max(ascent, box.ascent - dy)
        descent = max(descent, box.descent + dy)
    return MathBox(width, ascent, descent, tuple(commands), axis)


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
        box = literal_box(text, fonts.measure(text, style), style)
        atom = "operator" if isinstance(self, Operator) else "symbol" if isinstance(self, Symbol) else "literal"
        return MathBox(box.width, box.ascent, box.descent, tagged(box.commands, _ATOM_TAGS[atom]), box.axis)


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


@dataclass(frozen=True, slots=True)
class TermStop:
    """A zero-width boundary in a top-level equation RHS Row starting an aligned term column."""

    align: str = "left"
    width: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.align, str) or self.align not in ("left", "center", "right"):
            raise ValueError("align must be left, center, or right")
        if self.width is not None:
            width = _finite_number(self.width, "width")
            if width <= 0:
                raise ValueError("width must be positive")
            object.__setattr__(self, "width", width)

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        raise LayoutError("TermStop requires equation layout")


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
        gap = style.size * 0.15 if self.gap is None else self.gap
        return compose_row([_within(item.measure(fonts, style), Kind.ROW, index=index)
                            for index, item in enumerate(self.items)],
                           gap, style.size * 0.25)


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
        numerator = _within(cast(MathNode, self.numerator).measure(fonts, style), Kind.FRACTION, "numerator")
        denominator = _within(cast(MathNode, self.denominator).measure(fonts, style), Kind.FRACTION, "denominator")
        axis = style.size * 0.25
        padding = gap = style.size * 0.15
        stroke = style.size * 0.05
        width = max(numerator.width, denominator.width) + 2 * padding
        numerator_y = -axis - stroke / 2 - gap - numerator.descent
        denominator_y = -axis + stroke / 2 + gap + denominator.ascent
        commands = (
            *numerator.translated((width - numerator.width) / 2, numerator_y),
            *denominator.translated((width - denominator.width) / 2, denominator_y),
            Line(stroke / 2, -axis, width - stroke / 2, -axis, width=stroke,
                 tag=_part_tag(Role.FRACTION_BAR, Kind.FRACTION, "bar")),
        )
        return MathBox(
            width,
            max(0, numerator.ascent - numerator_y, axis + stroke / 2),
            max(0, denominator_y + denominator.descent, -axis + stroke / 2),
            commands, axis,
        )


def _script_ink(commands: tuple[Command, ...], fonts: FontRegistry) -> tuple[Rect, ...]:
    """Actual ink for explicit-script checks, without changing layout bounds."""
    result = []
    for command in commands:
        if isinstance(command, Text):
            metrics = fonts.measure(fonts.normalize_text(command.text), command.style)
            bounds = metrics.ink_bounds if metrics.ink_bounds is not None else metrics.bounds
            if bounds.width == 0 or bounds.height == 0:
                continue
            result.append(transformed_text_bounds(command, bounds))
        else:
            result.append(command_bounds(command, fonts))
    return tuple(result)


def _script_contacts(first: tuple[Rect, ...], second: tuple[Rect, ...]) -> bool:
    return any(a.x <= b.right + 1e-9 and b.x <= a.right + 1e-9
               and a.y <= b.bottom + 1e-9 and b.y <= a.bottom + 1e-9
               for a in first for b in second)


@dataclass(frozen=True, slots=True)
class Script:
    """A base with scripts, preserving automatic placement by default.

    Explicit rise/drop are positive pt distances from the base baseline. They
    are never clamped. Opt-in placement validates actual ink roles around the
    math axis, base contact and upper/lower clearance; only automatic offsets
    may move to achieve clearance. Box extents remain conservative layout bounds.
    """

    base: MathNode | str
    superscript: MathNode | str | None = None
    subscript: MathNode | str | None = None
    _: KW_ONLY
    scale: float = .65
    superscript_rise: float | None = None
    subscript_drop: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "base", as_math(self.base))
        for name in ("superscript", "subscript"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, as_math(value))
        scale = _finite_number(self.scale, "scale")
        if not 0 < scale <= 1:
            raise ValueError("scale must be greater than zero and at most one")
        object.__setattr__(self, "scale", scale)
        for name, child in (("superscript_rise", self.superscript),
                            ("subscript_drop", self.subscript)):
            value = getattr(self, name)
            if value is not None:
                value = _finite_number(value, name)
                if value <= 0:
                    raise ValueError(f"{name} must be positive")
                if child is None:
                    raise ValueError(f"{name} requires its corresponding script")
                object.__setattr__(self, name, value)

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        _validate_context(fonts, style)
        base = _within(cast(MathNode, self.base).measure(fonts, style), Kind.SCRIPT, "base")
        axis = style.size * 0.25
        base_y = base.axis - axis
        ascent = max(0, base.ascent - base_y)
        descent = max(0, base.descent + base_y)
        commands = list(base.translated(0, base_y))
        if self.superscript is None and self.subscript is None:
            return MathBox(base.width, ascent, descent, tuple(commands), axis)
        script_style = _script_style(style, self.scale)
        upper_node = cast(MathNode | None, self.superscript)
        lower_node = cast(MathNode | None, self.subscript)
        upper = (_within(upper_node.measure(fonts, script_style), Kind.SCRIPT, "superscript")
                 if upper_node is not None else None)
        lower = (_within(lower_node.measure(fonts, script_style), Kind.SCRIPT, "subscript")
                 if lower_node is not None else None)
        upper_y = -max(style.size * 0.6, ascent - style.size * 0.2,
                       upper.descent + style.size * 0.15) if upper is not None else 0.0
        lower_y = max(style.size * 0.3, descent + style.size * 0.1,
                      lower.ascent - style.size * 0.1) if lower is not None else 0.0
        if upper is not None and lower is not None:
            lower_y = max(lower_y, upper_y + upper.descent + style.size * 0.15 + lower.ascent)
        script_x = base.width + style.size * 0.1
        if self.superscript_rise is not None:
            upper_y = base_y - self.superscript_rise
        if self.subscript_drop is not None:
            lower_y = base_y + self.subscript_drop
        if self.scale != .65 or self.superscript_rise is not None or self.subscript_drop is not None:
            upper_y, lower_y = self._safe_offsets(
                fonts, style, base, base_y, upper, lower, script_x, upper_y, lower_y, axis)
        width = base.width
        for box, y in ((upper, upper_y), (lower, lower_y)):
            if box is not None:
                commands.extend(box.translated(script_x, y))
                width = max(width, script_x + box.width)
                ascent = max(ascent, box.ascent - y)
                descent = max(descent, box.descent + y)
        return MathBox(width, ascent, descent, tuple(commands), axis)

    def _safe_offsets(self, fonts: FontRegistry, style: TextStyle, base: MathBox,
                      base_y: float, upper: MathBox | None, lower: MathBox | None,
                      script_x: float, upper_y: float, lower_y: float,
                      axis: float) -> tuple[float, float]:
        base_ink = _script_ink(base.translated(0, base_y), fonts)
        gap = style.size * .15
        positions = [upper_y, lower_y]
        scripts = (upper, lower)
        explicit = (self.superscript_rise is not None, self.subscript_drop is not None)
        for index, box in enumerate(scripts):
            if box is None:
                continue
            ink = _script_ink(box.translated(script_x, positions[index]), fonts)
            if not ink:
                continue
            center = (min(rect.y for rect in ink) + max(rect.bottom for rect in ink)) / 2
            wrong_role = center >= -axis if index == 0 else center <= -axis
            name = "superscript" if index == 0 else "subscript"
            if wrong_role:
                if explicit[index]:
                    raise LayoutError(f"Script: explicit {name} ink violates its role around the math axis")
                positions[index] += -axis - center + (-gap if index == 0 else gap)
                ink = _script_ink(box.translated(script_x, positions[index]), fonts)
            if _script_contacts(base_ink, ink):
                if explicit[index]:
                    raise LayoutError(f"Script: explicit {name} ink contacts the base")
                if index == 0:
                    positions[index] += min(rect.y for rect in base_ink) - gap - max(rect.bottom for rect in ink)
                else:
                    positions[index] += max(rect.bottom for rect in base_ink) + gap - min(rect.y for rect in ink)
        upper_ink = _script_ink(upper.translated(script_x, positions[0]), fonts) if upper else ()
        lower_ink = _script_ink(lower.translated(script_x, positions[1]), fonts) if lower else ()
        if upper_ink and lower_ink:
            missing = max(rect.bottom for rect in upper_ink) + gap - min(rect.y for rect in lower_ink)
            if missing > 1e-9:
                if not explicit[1]:
                    positions[1] += missing
                elif not explicit[0]:
                    positions[0] -= missing
                else:
                    raise LayoutError("Script: explicit scripts have insufficient ink clearance")
        return positions[0], positions[1]


@dataclass(frozen=True, slots=True)
class Root:
    """A square root formed from vector strokes around its body."""

    body: MathNode | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", as_math(self.body))

    def measure(self, fonts: FontRegistry, style: TextStyle) -> MathBox:
        _validate_context(fonts, style)
        body = _within(cast(MathNode, self.body).measure(fonts, style), Kind.ROOT, "radicand")
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
            (Polyline(points, width=stroke, tag=_part_tag(Role.RADICAL, Kind.ROOT, "sign")),
             *body.translated(body_x, body_y)),
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
        body = _within(cast(MathNode, self.body).measure(fonts, style), Kind.DELIMITED, "body")
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
            commands.append(_delimiter(self.left, 0, slot, axis, radius, stroke, "left"))
        if self.right:
            commands.append(_delimiter(self.right, body_x + body.width + gap, slot, axis, radius, stroke, "right"))
        return MathBox(width, axis + radius, max(0, radius - axis), tuple(commands), axis)


def _delimiter(symbol: str, x: float, slot: float, axis: float, radius: float, stroke: float,
               side: str) -> Polyline:
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
    return Polyline(tuple(points), width=stroke,
                    tag=_part_tag(Role.DELIMITER, Kind.DELIMITED, side, symbol=symbol))


def as_math(value: MathNode | str) -> MathNode:
    """Lift literal strings while keeping existing structured nodes."""
    if isinstance(value, str):
        return Literal(value)
    if isinstance(value, MathNode) and callable(value.measure):
        return value
    raise ValueError("expected a math node or literal string")
