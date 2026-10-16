"""JSON diagnostics for already positioned pages, without layout or reflow."""

from collections.abc import Iterable, Mapping
from hashlib import sha256

from .bounds import command_bounds
from .errors import FontError
from .fonts import FontRegistry
from .geometry import Rect
from .scene import Line, Polyline, RasterImage, Rectangle, ScenePage, Text


def _json_value(value):
    """Copy scene metadata into JSON containers without changing local values."""
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


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
    elif isinstance(command, Line):
        trace.update(x1=command.x1, y1=command.y1, x2=command.x2, y2=command.y2,
                     width=command.width, color=list(command.color))
    elif isinstance(command, Polyline):
        trace.update(points=[[point.x, point.y] for point in command.points],
                     width=command.width, color=list(command.color), closed=command.closed)
    elif isinstance(command, Rectangle):
        trace.update(x=command.x, y=command.y, width=command.width, height=command.height,
                     stroke_width=command.stroke_width, color=list(command.color))
    elif isinstance(command, RasterImage):
        trace.update(x=command.x, y=command.y, width=command.width, height=command.height,
                     sha256=sha256(command.data).hexdigest(), byte_count=len(command.data))
    return trace


def layout_trace(pages: Iterable[ScenePage], fonts: FontRegistry) -> dict:
    """Describe fixed pages as JSON-compatible data using the rendering fonts.

    Page numbers are 1-based positions in the supplied sequence. Command
    positions and bounds are absolute top-origin points; metadata is copied
    verbatim, including any block-local anchors, baselines and origins.
    Images are represented by their byte count and SHA-256, never raw bytes.
    No component measurement, pagination or PDF rendering is performed.
    """
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
            "metadata": _json_value(page.metadata),
            "commands": [_command(command, fonts, command_index, f"page[{index}].commands[{command_index}]")
                         for command_index, command in enumerate(page.commands)],
        })
    return {"schema_version": 1, "coordinate_system": "top-left-pt",
            "page_count": len(result), "pages": result}
