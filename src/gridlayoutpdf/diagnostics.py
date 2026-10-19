"""JSON diagnostics for already positioned pages, without layout or reflow."""

from collections.abc import Iterable
from hashlib import sha256

from .bounds import command_bounds
from .errors import FontError
from .fonts import FontRegistry, default_fonts
from .geometry import Rect
from .metadata import json_value
from .scene import Circle, Line, Polyline, RasterImage, Rectangle, ScenePage, Text, _text_rotation


def _rect(rect: Rect) -> dict:
    return {"x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height}


def _command(command, fonts: FontRegistry, index: int, location: str) -> dict:
    try:
        bounds = command_bounds(command, fonts)
    except FontError as exc:
        raise FontError(f"{location}: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{location}: {exc}") from exc
    trace = {"index": index, "type": type(command).__name__, "bounds": _rect(bounds)}
    if isinstance(command, Text):
        trace.update(
            text=command.text, normalized_text=fonts.normalize_text(command.text),
            x=command.x, baseline_y=command.y,
            style={"font": command.style.font, "size": command.style.size, "tracking": command.style.tracking},
        )
        if command.quarter_turns:
            a, b, _, _ = _text_rotation(command.quarter_turns)
            trace.update(quarter_turns=command.quarter_turns, direction=[a, b])
        if command.shear_x:
            trace["shear_x"] = command.shear_x
    elif isinstance(command, Line):
        trace.update(x1=command.x1, y1=command.y1, x2=command.x2, y2=command.y2,
                     width=command.width, color=list(command.color))
    elif isinstance(command, Polyline):
        trace.update(points=[[point.x, point.y] for point in command.points],
                     width=command.width, color=list(command.color), closed=command.closed)
    elif isinstance(command, Rectangle):
        trace.update(x=command.x, y=command.y, width=command.width, height=command.height,
                     stroke_width=command.stroke_width, color=list(command.color))
        if command.corner_radius:
            trace["corner_radius"] = command.corner_radius
    elif isinstance(command, Circle):
        trace.update(x=command.x, y=command.y, radius=command.radius,
                     stroke_width=command.stroke_width, color=list(command.color))
    # Optional paint is listed only when used, so solid outlines trace as before.
    if getattr(command, "dash", ()):
        trace["dash"] = list(command.dash)
    if isinstance(command, (Rectangle, Circle)):
        if command.fill is not None:
            trace["fill"] = list(command.fill)
        if not command.stroke or isinstance(command, Circle):
            trace["stroke"] = command.stroke
    elif isinstance(command, RasterImage):
        trace.update(x=command.x, y=command.y, width=command.width, height=command.height,
                     sha256=sha256(command.data).hexdigest(), byte_count=len(command.data))
    return trace


def layout_trace(pages: Iterable[ScenePage], fonts: FontRegistry | None = None) -> dict:
    """Describe fixed pages as JSON-compatible data using the rendering fonts.

    Page numbers are 1-based positions in the supplied sequence. Command
    positions and bounds are absolute top-origin points; metadata is copied
    verbatim, including any block-local anchors, baselines and origins.
    Images are represented by their byte count and SHA-256, never raw bytes.
    No component measurement, pagination or PDF rendering is performed.
    Omitting ``fonts`` uses the shared default registry; pass the registry
    the pages were laid out with when it is not the default one.
    """
    if fonts is None:
        fonts = default_fonts()
    if not isinstance(fonts, FontRegistry):
        raise ValueError("fonts must be a FontRegistry")
    try:
        pages = tuple(pages)
    except TypeError as exc:
        raise ValueError("pages must be an iterable of ScenePage objects") from exc
    result = []
    for index, page in enumerate(pages, 1):
        if not isinstance(page, ScenePage):
            raise ValueError(f"pages[{index - 1}] must be a ScenePage")
        profile, grid = page.profile, page.profile.grid
        result.append({
            "page_number": index,
            "profile": {
                "name": profile.name, "width": profile.width, "height": profile.height,
                "grid": {"origin_x": grid.origin_x, "origin_y": grid.origin_y,
                         "pitch_x": grid.pitch_x, "pitch_y": grid.pitch_y,
                         "columns": grid.columns, "rows": grid.rows},
                "body_start_row": profile.body_start_row, "body_end_row": profile.body_end_row,
                "body_rect": _rect(profile.body_rect),
            },
            "metadata": json_value(page.metadata),
            "commands": [_command(command, fonts, command_index, f"page[{index}].commands[{command_index}]")
                         for command_index, command in enumerate(page.commands)],
        })
    return {"schema_version": 1, "coordinate_system": "top-left-pt",
            "page_count": len(result), "pages": result}
