"""Immutable drawing commands, expressed in top-origin point coordinates."""

from collections.abc import Mapping
from dataclasses import KW_ONLY, dataclass, field, replace

from .geometry import Point
from .metadata import freeze_metadata
from .profiles import PageProfile
from .styles import TextStyle, _finite_number


Color = tuple[float, float, float]


def _coordinates(command, *names: str) -> None:
    for name in names:
        object.__setattr__(command, name, _finite_number(getattr(command, name), name))


def _stroke(command, width_name: str) -> None:
    _coordinates(command, width_name)
    if getattr(command, width_name) <= 0:
        raise ValueError(f"{width_name} must be positive")
    object.__setattr__(command, "color", _color(command.color, "color"))


def _color(value, name: str) -> Color:
    try:
        color = tuple(_finite_number(component, name) for component in value)
    except TypeError as exc:
        raise ValueError(f"{name} must contain three numeric components") from exc
    if len(color) != 3 or any(component < 0 or component > 1 for component in color):
        raise ValueError(f"{name} must contain three components between 0 and 1")
    return color


def _dash(command) -> None:
    """Snapshot on/off lengths in pt; an empty pattern draws a solid stroke."""
    if isinstance(command.dash, (str, bytes)):
        raise ValueError("dash must be a sequence of positive finite lengths")
    try:
        lengths = tuple(_finite_number(length, "dash") for length in command.dash)
    except (TypeError, ValueError) as exc:
        raise ValueError("dash must be a sequence of positive finite lengths") from exc
    if any(length <= 0 for length in lengths):
        raise ValueError("dash lengths must be positive")
    object.__setattr__(command, "dash", lengths)


def _paint(command) -> None:
    """Validate an area's outline stroke and optional fill."""
    _stroke(command, "stroke_width")
    if not isinstance(command.stroke, bool):
        raise ValueError("stroke must be a boolean")
    if command.fill is not None:
        object.__setattr__(command, "fill", _color(command.fill, "fill"))
    if not command.stroke and command.fill is None:
        raise ValueError("a shape must have a stroke or fill")


def _offset(dx: float, dy: float) -> tuple[float, float]:
    return _finite_number(dx, "dx"), _finite_number(dy, "dy")


def _text_rotation(quarter_turns: int) -> tuple[int, int, int, int]:
    """Return a rigid top-origin matrix (a, b, c, d), counterclockwise."""
    if isinstance(quarter_turns, bool) or not isinstance(quarter_turns, int) or not 0 <= quarter_turns <= 3:
        raise ValueError("quarter_turns must be an integer between 0 and 3")
    return ((1, 0, 0, 1), (0, -1, 1, 0), (-1, 0, 0, -1), (0, 1, -1, 0))[quarter_turns]


def _text_matrix(quarter_turns: int, shear_x: float) -> tuple[float, float, float, float]:
    """Shear glyphs about their baseline, then rotate, in top-origin pt."""
    a, b, c, d = _text_rotation(quarter_turns)
    return a, b, c - a * shear_x, d - b * shear_x


@dataclass(frozen=True, slots=True)
class Text:
    """A text run at its baseline origin, turned counterclockwise in 90° steps.

    ``shear_x`` is a finite coefficient, not an angle: positive values lean
    the glyph tops to the right before rotation. In baseline-local coordinates
    (y downwards), x' = x - shear_x*y and y' = y. Baseline advances and tracking
    stay unchanged; the ink envelope can grow beyond the original advance.
    """

    x: float
    y: float
    text: str
    style: TextStyle
    quarter_turns: int = 0
    shear_x: float = 0.0

    def __post_init__(self) -> None:
        _coordinates(self, "x", "y", "shear_x")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if not isinstance(self.style, TextStyle):
            raise ValueError("style must be a TextStyle")
        _text_rotation(self.quarter_turns)

    def translated(self, dx: float, dy: float) -> "Text":
        dx, dy = _offset(dx, dy)
        return replace(self, x=self.x + dx, y=self.y + dy)


@dataclass(frozen=True, slots=True)
class Line:
    """A butt-capped segment; ``dash`` lists on/off lengths in pt from (x1, y1)."""

    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 0.5
    color: Color = (0, 0, 0)
    _: KW_ONLY
    dash: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        _coordinates(self, "x1", "y1", "x2", "y2")
        _stroke(self, "width")
        _dash(self)

    def translated(self, dx: float, dy: float) -> "Line":
        dx, dy = _offset(dx, dy)
        return replace(self, x1=self.x1 + dx, y1=self.y1 + dy,
                       x2=self.x2 + dx, y2=self.y2 + dy)


@dataclass(frozen=True, slots=True)
class Polyline:
    """Connected segments; a dash pattern continues across the vertices."""

    points: tuple[Point, ...]
    width: float = 0.5
    color: Color = (0, 0, 0)
    closed: bool = False
    _: KW_ONLY
    dash: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        try:
            points = tuple(
                point if isinstance(point, Point) else Point(*point) for point in self.points
            )
        except TypeError as exc:
            raise ValueError("points must contain Point objects or coordinate pairs") from exc
        if not isinstance(self.closed, bool):
            raise ValueError("closed must be a boolean")
        minimum = 3 if self.closed else 2
        if len(points) < minimum:
            raise ValueError(f"Polyline requires at least {minimum} points")
        object.__setattr__(self, "points", points)
        _stroke(self, "width")
        _dash(self)

    def translated(self, dx: float, dy: float) -> "Polyline":
        dx, dy = _offset(dx, dy)
        return replace(self, points=tuple(Point(p.x + dx, p.y + dy) for p in self.points))


@dataclass(frozen=True, slots=True)
class Rectangle:
    """An axis-aligned box stroked in ``color`` and optionally filled.

    ``stroke=False`` paints only ``fill``; the bounds are then the exact box.
    A positive ``corner_radius`` rounds the corners (at most half the shorter side); the bounds stay the box.
    """

    x: float
    y: float
    width: float
    height: float
    stroke_width: float = 0.5
    color: Color = (0, 0, 0)
    _: KW_ONLY
    fill: Color | None = None
    stroke: bool = True
    corner_radius: float = 0.0

    def __post_init__(self) -> None:
        _coordinates(self, "x", "y", "width", "height")
        for name in ("width", "height"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        _finite_number(self.x + self.width, "right")
        _finite_number(self.y + self.height, "bottom")
        _paint(self)
        radius = _finite_number(self.corner_radius, "corner_radius")
        if radius < 0 or radius > min(self.width, self.height) / 2:
            raise ValueError("corner_radius must be between 0 and half the shorter side")
        object.__setattr__(self, "corner_radius", radius)

    def translated(self, dx: float, dy: float) -> "Rectangle":
        dx, dy = _offset(dx, dy)
        return replace(self, x=self.x + dx, y=self.y + dy)


@dataclass(frozen=True, slots=True)
class Circle:
    """A circle centered at (x, y), stroked in ``color`` and optionally filled."""

    x: float
    y: float
    radius: float
    _: KW_ONLY
    stroke_width: float = 0.5
    color: Color = (0, 0, 0)
    fill: Color | None = None
    stroke: bool = True

    def __post_init__(self) -> None:
        _coordinates(self, "x", "y", "radius")
        if self.radius <= 0:
            raise ValueError("radius must be positive")
        for extent in (self.x - self.radius, self.x + self.radius,
                       self.y - self.radius, self.y + self.radius):
            _finite_number(extent, "radius extent")
        _paint(self)

    def translated(self, dx: float, dy: float) -> "Circle":
        dx, dy = _offset(dx, dy)
        return replace(self, x=self.x + dx, y=self.y + dy)


@dataclass(frozen=True, slots=True)
class RasterImage:
    """A validated rectangle and immutable encoded image snapshot.

    Decoding is checked by the renderer before it touches the destination.
    """
    x: float
    y: float
    width: float
    height: float
    data: bytes

    def __post_init__(self) -> None:
        _coordinates(self, "x", "y", "width", "height")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image width and height must be positive")
        _finite_number(self.x + self.width, "right")
        _finite_number(self.y + self.height, "bottom")
        if not isinstance(self.data, (bytes, bytearray, memoryview)) or not self.data:
            raise ValueError("data must contain nonempty image bytes")
        object.__setattr__(self, "data", bytes(self.data))

    def translated(self, dx: float, dy: float) -> "RasterImage":
        dx, dy = _offset(dx, dy)
        return replace(self, x=self.x + dx, y=self.y + dy)


Command = Text | Line | Polyline | Rectangle | Circle | RasterImage
COMMAND_TYPES = (Text, Line, Polyline, Rectangle, Circle, RasterImage)


@dataclass(frozen=True, slots=True)
class ScenePage:
    """A page whose commands and JSON-compatible metadata are fixed snapshots."""

    profile: PageProfile
    commands: tuple[Command, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, PageProfile):
            raise ValueError("profile must be a PageProfile")
        try:
            commands = tuple(self.commands)
        except TypeError as exc:
            raise ValueError("commands must be a sequence of drawing commands") from exc
        if any(not isinstance(command, COMMAND_TYPES) for command in commands):
            raise ValueError("commands must contain only supported drawing commands")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        object.__setattr__(self, "commands", commands)
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
