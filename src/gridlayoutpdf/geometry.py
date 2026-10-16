"""Immutable geometry in points, with x rightwards and y downwards."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _finite(value: float, name: str) -> None:
    """Reject non-numeric and non-finite pt values, including booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number in pt")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be a finite number in pt")


@dataclass(frozen=True)
class Point:
    """A position in pt; local coordinates may be negative."""

    x: float
    y: float

    def __post_init__(self) -> None:
        _finite(self.x, "x")
        _finite(self.y, "y")


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in pt, including its boundary."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        for name in ("x", "y", "width", "height"):
            _finite(getattr(self, name), name)
        if self.width < 0:
            raise ValueError("width must be non-negative")
        if self.height < 0:
            raise ValueError("height must be non-negative")
        _finite(self.right, "right")
        _finite(self.bottom, "bottom")

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def contains(self, other: Point | Rect) -> bool:
        """Return whether a point or whole rectangle lies within this rectangle."""
        if isinstance(other, Point):
            return self.x <= other.x <= self.right and self.y <= other.y <= self.bottom
        if isinstance(other, Rect):
            return (
                self.x <= other.x <= other.right <= self.right
                and self.y <= other.y <= other.bottom <= self.bottom
            )
        raise ValueError("other must be a Point or Rect")


@dataclass(frozen=True)
class GridSpec:
    """Placement grid in pt; row and column indices denote cell boundaries."""

    origin_x: float
    origin_y: float
    pitch_x: float
    pitch_y: float
    columns: int
    rows: int

    def __post_init__(self) -> None:
        for name in ("origin_x", "origin_y", "pitch_x", "pitch_y"):
            _finite(getattr(self, name), name)
        for name in ("pitch_x", "pitch_y"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("columns", "rows"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
            _finite(value, name)
        _finite(self.columns * self.pitch_x, "grid width")
        _finite(self.rows * self.pitch_y, "grid height")
        _finite(self.x(self.columns), "grid right")
        _finite(self.y(self.rows), "grid bottom")

    def x(self, col: int) -> float:
        """Return the x coordinate of boundary 0 through columns, inclusive."""
        if isinstance(col, bool) or not isinstance(col, int) or not 0 <= col <= self.columns:
            raise ValueError(f"col must be an integer between 0 and {self.columns}")
        return self.origin_x + col * self.pitch_x

    def y(self, row: int) -> float:
        """Return the y coordinate of boundary 0 through rows, inclusive."""
        if isinstance(row, bool) or not isinstance(row, int) or not 0 <= row <= self.rows:
            raise ValueError(f"row must be an integer between 0 and {self.rows}")
        return self.origin_y + row * self.pitch_y

    def rows_for(self, height: float) -> int:
        """Return the rows covering a height in pt, without a page-size limit."""
        _finite(height, "height")
        if height < 0:
            raise ValueError("height must be non-negative")
        _finite(height / self.pitch_y, "height / pitch_y")
        count = math.ceil(height / self.pitch_y)
        # Compare actual boundaries rather than adding an epsilon that could
        # hide a real overflow immediately beyond an exact grid boundary.
        if count > 0 and (count - 1) * self.pitch_y >= height:
            count -= 1
        elif count * self.pitch_y < height:
            count += 1
        return count
