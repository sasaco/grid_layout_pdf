"""Shared real-ink and stroke envelopes for scene and layout validation."""

from .fonts import FontRegistry
from .geometry import Rect
from .scene import Line, Polyline, RasterImage, Rectangle, Text, _text_matrix


def transformed_text_bounds(command: Text, bounds: Rect) -> Rect:
    """Place a baseline-local rectangle through the command's own text matrix.

    Callers that need an upright, unsheared run's exact width and height test
    for that case before calling, because recovering them from the transformed
    corners would re-round both extents.
    """
    a, b, c, d = _text_matrix(command.quarter_turns, command.shear_x)
    corners = [(a * x + c * y, b * x + d * y)
               for x in (bounds.x, bounds.right) for y in (bounds.y, bounds.bottom)]
    left, right = min(x for x, _ in corners), max(x for x, _ in corners)
    top, bottom = min(y for _, y in corners), max(y for _, y in corners)
    return Rect(command.x + left, command.y + top, right - left, bottom - top)


def command_bounds(command, fonts: FontRegistry) -> Rect:
    """Return a command's top-origin bounds, including ink and half stroke.

    Stroke envelopes assume bounded joins (the renderer uses round joins).
    Overlapping commands are valid; this function only describes one envelope.
    """
    if isinstance(command, RasterImage):
        return Rect(command.x, command.y, command.width, command.height)
    if isinstance(command, Text):
        bounds = fonts.measure(fonts.normalize_text(command.text), command.style).bounds
        if command.quarter_turns == 0 and command.shear_x == 0:
            return Rect(command.x + bounds.x, command.y + bounds.y,
                        bounds.width, bounds.height)
        return transformed_text_bounds(command, bounds)
    if isinstance(command, Line):
        left, right = sorted((command.x1, command.x2))
        top, bottom = sorted((command.y1, command.y2))
        radius = command.width / 2
    elif isinstance(command, Polyline):
        left, right = min(p.x for p in command.points), max(p.x for p in command.points)
        top, bottom = min(p.y for p in command.points), max(p.y for p in command.points)
        radius = command.width / 2
    elif isinstance(command, Rectangle):
        left, right = command.x, command.x + command.width
        top, bottom = command.y, command.y + command.height
        radius = command.stroke_width / 2
    else:
        raise ValueError(f"Unsupported drawing command: {type(command).__name__}")
    return Rect(left - radius, top - radius,
                right - left + 2 * radius, bottom - top + 2 * radius)
