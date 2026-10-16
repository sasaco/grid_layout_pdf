"""Immutable drawing commands, expressed in top-origin point coordinates."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from math import isfinite
from types import MappingProxyType

from .geometry import Point
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
    try:
        color = tuple(_finite_number(value, "color") for value in command.color)
    except TypeError as exc:
        raise ValueError("color must contain three numeric components") from exc
    if len(color) != 3 or any(value < 0 or value > 1 for value in color):
        raise ValueError("color must contain three components between 0 and 1")
    object.__setattr__(command, "color", color)


def _offset(dx: float, dy: float) -> tuple[float, float]:
    return _finite_number(dx, "dx"), _finite_number(dy, "dy")


@dataclass(frozen=True, slots=True)
class Text:
    """A text run whose y coordinate denotes its baseline."""

    x: float
    y: float
    text: str
    style: TextStyle

    def __post_init__(self) -> None:
        _coordinates(self, "x", "y")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if not isinstance(self.style, TextStyle):
            raise ValueError("style must be a TextStyle")

    def translated(self, dx: float, dy: float) -> "Text":
        dx, dy = _offset(dx, dy)
        return replace(self, x=self.x + dx, y=self.y + dy)


@dataclass(frozen=True, slots=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 0.5
    color: Color = (0, 0, 0)

    def __post_init__(self) -> None:
        _coordinates(self, "x1", "y1", "x2", "y2")
        _stroke(self, "width")

    def translated(self, dx: float, dy: float) -> "Line":
        dx, dy = _offset(dx, dy)
        return replace(self, x1=self.x1 + dx, y1=self.y1 + dy,
                       x2=self.x2 + dx, y2=self.y2 + dy)


@dataclass(frozen=True, slots=True)
class Polyline:
    points: tuple[Point, ...]
    width: float = 0.5
    color: Color = (0, 0, 0)
    closed: bool = False

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

    def translated(self, dx: float, dy: float) -> "Polyline":
        dx, dy = _offset(dx, dy)
        return replace(self, points=tuple(Point(p.x + dx, p.y + dy) for p in self.points))


@dataclass(frozen=True, slots=True)
class Rectangle:
    x: float
    y: float
    width: float
    height: float
    stroke_width: float = 0.5
    color: Color = (0, 0, 0)

    def __post_init__(self) -> None:
        _coordinates(self, "x", "y", "width", "height")
        for name in ("width", "height"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        _finite_number(self.x + self.width, "right")
        _finite_number(self.y + self.height, "bottom")
        _stroke(self, "stroke_width")

    def translated(self, dx: float, dy: float) -> "Rectangle":
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


Command = Text | Line | Polyline | Rectangle | RasterImage


def _freeze_metadata(value, active: set[int]):
    """Copy JSON-compatible values to recursively immutable containers."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("metadata numbers must be finite")
        return value
    if isinstance(value, (Mapping, list, tuple)):
        identity = id(value)
        if identity in active:
            raise ValueError("metadata must not contain cycles")
        active.add(identity)
        try:
            if isinstance(value, Mapping):
                if any(not isinstance(key, str) for key in value):
                    raise ValueError("metadata keys must be strings")
                return MappingProxyType({
                    key: _freeze_metadata(item, active) for key, item in value.items()
                })
            return tuple(_freeze_metadata(item, active) for item in value)
        finally:
            active.remove(identity)
    raise ValueError(f"Unsupported metadata value: {type(value).__name__}")


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
        if any(not isinstance(command, (Text, Line, Polyline, Rectangle, RasterImage)) for command in commands):
            raise ValueError("commands must contain only supported drawing commands")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        object.__setattr__(self, "commands", commands)
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata, set()))
