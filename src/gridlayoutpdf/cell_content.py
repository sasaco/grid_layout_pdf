"""Explicit point-spaced lines with one final grid-height reservation."""

from dataclasses import KW_ONLY, dataclass

from .bounds import command_bounds, transformed_text_bounds
from .errors import FontError, LayoutOverflowError
from .geometry import Rect
from .layout import LayoutContext, LayoutPart, MeasuredBlock, measurement_inputs
from .math import MathBox, MathNode, as_math
from .scene import Command, Text
from .semantics import Kind, Scope, within
from .styles import Insets, TextStyle, _finite_number, _resolve_insets
from .text import wrap_text
from .validation import TOLERANCE, _identifier


def _ink_bounds(command: Command, context: LayoutContext) -> Rect | None:
    """Use existing glyph ink only for contact; reservation stays conservative."""
    if not isinstance(command, Text):
        return command_bounds(command, context.fonts)
    metrics = context.fonts.measure(context.fonts.normalize_text(command.text), command.style)
    bounds = metrics.ink_bounds
    if bounds is None:
        return command_bounds(command, context.fonts)
    if bounds.width == 0 or bounds.height == 0:
        return None
    return transformed_text_bounds(command, bounds)


@dataclass(frozen=True, slots=True)
class CellLines:
    """Explicit string/math lines, without scaling or baseline repair.

    ``wrap=True`` first breaks string lines with wrap_text inside the width
    left by the horizontal inner padding; otherwise lines are never wrapped.

    Lines share a fixed point advance. Their conservative math envelopes, edge
    padding and minimum height are combined before a single grid rounding.
    Remaining vertical space is centered between the top and bottom padding,
    unless ``first_baseline`` gives the first baseline in pt from the top of
    the reserved height: then lines are not centred, so cells of one table row
    that share it share their baseline whatever the math extent of their
    lines (a subscript no longer moves its line), and the reservation grows to
    hold the descent below it. ``align`` positions each line within the widest line, independently of a
    containing Cell's alignment. Use outer Cell.padding=0 to avoid a second
    height rounding. Empty lines and even an empty sequence reserve space.
    """

    lines: tuple[str | MathNode, ...]
    _: KW_ONLY
    style: TextStyle | None = None
    line_styles: tuple[TextStyle | None, ...] | None = None
    line_advance: float = 12.8
    min_height: float = 0.0
    inner_padding: float | Insets = 0.0
    align: str = "left"
    wrap: bool = False
    first_baseline: float | None = None
    block_id: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.lines, str):
            raise ValueError("lines must be a sequence of single-line strings or MathNode objects")
        try:
            lines = tuple(self.lines)
            for line in lines:
                as_math(line)
        except (TypeError, ValueError) as exc:
            raise ValueError("lines must contain single-line strings or MathNode objects") from exc
        object.__setattr__(self, "lines", lines)
        if self.style is not None and not isinstance(self.style, TextStyle):
            raise ValueError("style must be a TextStyle or None")
        if self.line_styles is not None:
            try:
                styles = tuple(self.line_styles)
            except TypeError as exc:
                raise ValueError("line_styles must match lines") from exc
            if len(styles) != len(lines) or any(value is not None and not isinstance(value, TextStyle) for value in styles):
                raise ValueError("line_styles must match lines and contain TextStyle or None")
            object.__setattr__(self, "line_styles", styles)
        if self.first_baseline is not None:
            try:
                value = _finite_number(self.first_baseline, "first_baseline")
            except (TypeError, ValueError) as exc:
                raise ValueError("first_baseline must be a positive finite number or None") from exc
            if value <= 0:
                raise ValueError("first_baseline must be a positive finite number or None")
            object.__setattr__(self, "first_baseline", value)
        for name, positive in (("line_advance", True), ("min_height", False)):
            value = _finite_number(getattr(self, name), name)
            if value < 0 or (positive and value == 0):
                raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
            object.__setattr__(self, name, value)
        padding = _resolve_insets(self.inner_padding, "inner_padding")
        if not isinstance(self.inner_padding, Insets):
            object.__setattr__(self, "inner_padding", padding.top)
        if self.align not in ("left", "center", "right"):
            raise ValueError("align must be left, center or right")
        if not isinstance(self.wrap, bool):
            raise ValueError("wrap must be a boolean")
        _identifier(self.block_id)

    def _display_lines(self, context: LayoutContext, content_width: float):
        """Pair each display line with its style, wrapping strings if requested.

        Wrapping follows wrap_text without tracking: an empty string yields no
        display line and every explicit newline starts one. Math lines and
        their styles pass through unchanged.
        """
        default_style = self.style or context.style.body
        for index, line in enumerate(self.lines):
            style = (self.line_styles[index] if self.line_styles else None) or default_style
            if not self.wrap or not isinstance(line, str):
                yield line, style
                continue
            for wrapped in wrap_text(line, context.fonts, style, content_width,
                                     align=self.align, max_tracking_em=0, block_id=self.block_id):
                yield wrapped.text, style

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        identifier = self.block_id or "CellLines"
        padding = _resolve_insets(self.inner_padding, "inner_padding")
        horizontal = padding.left + padding.right
        if horizontal >= available_width:
            raise LayoutOverflowError(f"{identifier}: inner_padding leaves no content width",
                                      block_id=identifier, needed=horizontal, available=available_width)
        boxes: list[MathBox] = []
        for index, (line, style) in enumerate(self._display_lines(context, available_width - horizontal)):
            try:
                box = as_math(line).measure(context.fonts, style)
            except FontError as exc:
                raise FontError(f"{identifier}: line {index + 1}: {exc}") from exc
            if not isinstance(box, MathBox):
                raise ValueError(f"{identifier}: line {index + 1} must measure to MathBox")
            if box.width + horizontal > available_width + TOLERANCE:
                raise LayoutOverflowError(f"{identifier}: line {index + 1} exceeds available width",
                                          block_id=identifier, needed=box.width + horizontal, available=available_width)
            boxes.append(box)
        widest = max((box.width for box in boxes), default=0)
        width = widest + horizontal if widest else available_width
        baseline = boxes[0].ascent if boxes else 0
        top = min((baseline + index * self.line_advance - box.ascent for index, box in enumerate(boxes)), default=0)
        bottom = max((baseline + index * self.line_advance + box.descent for index, box in enumerate(boxes)), default=0)
        if self.first_baseline is None:
            required = max(self.min_height, bottom - top + padding.top + padding.bottom)
            rows = max(1, context.rows_for(required))
            height = rows * context.profile.grid.pitch_y
            offset = padding.top + (height - (padding.top + padding.bottom) - (bottom - top)) / 2 - top
        else:
            above = baseline - top
            if self.first_baseline - above < padding.top - TOLERANCE:
                raise LayoutOverflowError(
                    f"{identifier}: first_baseline {self.first_baseline:g} leaves no room for the ascent {above:g}",
                    block_id=identifier, needed=above + padding.top, available=self.first_baseline)
            required = max(self.min_height, self.first_baseline + bottom - baseline + padding.bottom)
            rows = max(1, context.rows_for(required))
            height = rows * context.profile.grid.pitch_y
            offset = self.first_baseline - baseline
        commands: list[Command] = []
        ink_by_line: list[list[Rect]] = []
        baselines = []
        for index, box in enumerate(boxes):
            x = padding.left + (width - horizontal - box.width) * {"left": 0, "center": .5, "right": 1}[self.align]
            y = baseline + offset + index * self.line_advance
            baselines.append(y)
            translated = within(box.translated(x, y),
                                Scope(Kind.CELL_LINES, index=index, data={"align": self.align}))
            ink = []
            for command in translated:
                bounds = command_bounds(command, context.fonts)
                if bounds.x < padding.left - TOLERANCE or bounds.right > width - padding.right + TOLERANCE:
                    # Include displacement, not just command width: leftward
                    # overflow also needs more space at its existing position.
                    needed = max(width - padding.right, bounds.right) - min(padding.left, bounds.x)
                    raise LayoutOverflowError(f"{identifier}: line {index + 1} exceeds reserved content bounds (horizontal)",
                                              block_id=identifier, needed=needed, available=width - horizontal)
                if bounds.y < padding.top - TOLERANCE or bounds.bottom > height - padding.bottom + TOLERANCE:
                    needed = max(height - padding.bottom, bounds.bottom) - min(padding.top, bounds.y)
                    raise LayoutOverflowError(f"{identifier}: line {index + 1} exceeds reserved content bounds (vertical)",
                                              block_id=identifier, needed=needed, available=height - padding.top - padding.bottom)
                visible = _ink_bounds(command, context)
                if visible is not None:
                    ink.append(visible)
            for previous, other_ink in enumerate(ink_by_line):
                if any(a.x <= b.right + TOLERANCE and b.x <= a.right + TOLERANCE
                       and a.y <= b.bottom + TOLERANCE and b.y <= a.bottom + TOLERANCE
                       for a in ink for b in other_ink):
                    raise LayoutOverflowError(f"{identifier}: line {index + 1} glyph ink touches line {previous + 1}",
                                              block_id=identifier, needed=self.line_advance, available=self.line_advance)
            ink_by_line.append(ink)
            commands.extend(translated)
        metadata = {
            "line_count": len(boxes), "line_advance": self.line_advance, "baselines_pt": baselines,
            "height_rounding": "single", "required_height_pt": required,
            "minimum_height_pt": self.min_height, "rounding_added_pt": height - required,
            "first_baseline_pt": self.first_baseline,
            "inner_padding_pt": {edge: getattr(padding, edge) for edge in ("top", "right", "bottom", "left")},
        }
        return MeasuredBlock(width, context.profile.grid.pitch_y,
                             (LayoutPart(rows, tuple(commands), metadata),), block_id=self.block_id)
