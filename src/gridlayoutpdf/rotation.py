"""Atomic right-angle rotation of locally measured text and vector blocks."""

from dataclasses import KW_ONLY, dataclass, replace

from .bounds import command_bounds
from .containers import _block, _child_trace, _identifier, _measure_child, _measurement_inputs
from .errors import LayoutOverflowError
from .geometry import GridSpec, Point
from .layout import Block, LayoutContext, LayoutPart, MeasuredBlock, _has_visible_commands
from .profiles import PageProfile
from .scene import Line, Polyline, Rectangle, Text


def _rotate_command(command, turns, width, height):
    """Flatten a single orthogonal transform into an existing command type."""
    def point(x, y):
        return (y, width - x) if turns == 1 else (height - y, x)

    if isinstance(command, Text):
        x, y = point(command.x, command.y)
        # Glyph-local shear stays inside the composed rigid rotation.
        return replace(command, x=x, y=y, quarter_turns=(command.quarter_turns + turns) % 4)
    if isinstance(command, Line):
        x1, y1 = point(command.x1, command.y1)
        x2, y2 = point(command.x2, command.y2)
        return replace(command, x1=x1, y1=y1, x2=x2, y2=y2)
    if isinstance(command, Polyline):
        return replace(command, points=tuple(Point(*point(p.x, p.y)) for p in command.points))
    if isinstance(command, Rectangle):
        corners = [point(x, y) for x in (command.x, command.x + command.width)
                   for y in (command.y, command.y + command.height)]
        return replace(command, x=min(x for x, _ in corners), y=min(y for _, y in corners),
                       width=command.height, height=command.width)
    raise ValueError(f"QuarterTurn does not support {type(command).__name__} commands")


@dataclass(frozen=True, slots=True)
class QuarterTurn:
    """Rotate one block 90° counterclockwise (+1) or clockwise (-1).

    The zero-origin local_grid sets explicit, unscaled child measurement
    capacity. Only the child's actual measured width and height are reserved,
    with the rotated height rounded up to whole rows of the outer grid. The
    result is one indivisible part. Raster images are intentionally unsupported.

    Metadata preserves child coordinates and part offsets. ``local_to_part``
    is (a, b, c, d, e, f): x' = a*x + c*y + e, y' = b*x + d*y + f.
    Add the part's eventual placement translation exactly once for page pt.
    """

    block: Block
    _: KW_ONLY
    turns: int
    local_grid: GridSpec
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        _block(self.block)
        if isinstance(self.turns, bool) or not isinstance(self.turns, int) or self.turns not in (-1, 1):
            raise ValueError("turns must be the integer +1 or -1")
        if not isinstance(self.local_grid, GridSpec) or self.local_grid.origin_x != 0 or self.local_grid.origin_y != 0:
            raise ValueError("local_grid must be a GridSpec with origin (0, 0)")

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = _measurement_inputs(context, available_width)
        location = self.block_id or "QuarterTurn"
        grid = self.local_grid
        local_width, local_height = grid.columns * grid.pitch_x, grid.rows * grid.pitch_y
        local_profile = PageProfile(f"{location}.local", local_width, local_height, grid)
        child = _measure_child(self.block, LayoutContext(context.fonts, local_profile, context.style),
                               local_width, f"{location}.block")
        if child.height > local_height + 1e-7:
            raise LayoutOverflowError(
                f"{location}: child height {child.height} exceeds local_grid height {local_height}",
                block_id=location, needed=child.height, available=local_height,
            )
        commands = child.commands
        if not _has_visible_commands(commands):
            raise ValueError(f"{location}: child must contain visible drawing commands")
        rotated = tuple(_rotate_command(command, self.turns, child.width, child.height) for command in commands)
        width, height = child.height, child.width
        if width > available_width + 1e-7:
            raise LayoutOverflowError(
                f"{location}: rotated width {width} exceeds available width {available_width}",
                block_id=location, needed=width, available=available_width,
            )
        rows = context.rows_for(height)
        capacity = context.profile.body_end_row - context.profile.body_start_row
        if rows > capacity:
            raise LayoutOverflowError(
                f"{location}: rotated height requires {rows} rows but body has {capacity}",
                block_id=location, needed=rows * context.profile.grid.pitch_y,
                available=capacity * context.profile.grid.pitch_y,
            )
        # Check the true rotated rectangle, before outer-row rounding adds blank space.
        for index, command in enumerate(rotated):
            bounds = command_bounds(command, context.fonts)
            if (bounds.x < -1e-7 or bounds.y < -1e-7
                    or bounds.right > width + 1e-7 or bounds.bottom > height + 1e-7):
                horizontal = bounds.x < -1e-7 or bounds.right > width + 1e-7
                raise LayoutOverflowError(
                    f"{location}.commands[{index}]: rotated bounds exceed ({width}, {height})",
                    block_id=location, needed=bounds.width if horizontal else bounds.height,
                    available=width if horizontal else height,
                )
        child_trace = _child_trace(child, 0, 0)
        for group in ("prefix", "parts"):
            for part in child_trace[group]:
                part["y_pt"] = part["row"] * child.row_pitch
        matrix = (0, -1, 1, 0, 0, child.width) if self.turns == 1 else (0, 1, -1, 0, child.height, 0)
        metadata = {
            "turns": self.turns, "local_to_part": matrix,
            "local_grid": {"origin_x": grid.origin_x, "origin_y": grid.origin_y,
                           "pitch_x": grid.pitch_x, "pitch_y": grid.pitch_y,
                           "columns": grid.columns, "rows": grid.rows},
            "child": child_trace,
        }
        return MeasuredBlock(width, context.profile.grid.pitch_y,
                             (LayoutPart(rows, rotated, metadata),), keep_together=True,
                             keep_with_next=child.keep_with_next, block_id=self.block_id or child.block_id)
