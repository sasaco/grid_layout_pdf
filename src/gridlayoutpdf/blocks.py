"""Grid-height paragraph, heading and spacing components."""

from dataclasses import dataclass, replace

from .layout import LayoutContext, LayoutPart, MeasuredBlock
from .scene import Text
from .styles import TextStyle, _finite_number
from .text import wrap_text


@dataclass(frozen=True, slots=True)
class Paragraph:
    """Text measured afresh using explicit style or the context's body style.

    Each display line is an indivisible part. min_first/min_last count those
    lines rather than the physical grid rows occupied by large glyphs.
    """

    text: str
    style: TextStyle | None = None
    align: str = "left"
    block_id: str = ""
    min_first: int | None = None
    min_last: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if "\t" in self.text:
            raise ValueError("text must not contain tabs")
        if self.style is not None and not isinstance(self.style, TextStyle):
            raise ValueError("style must be a TextStyle or None")
        if self.align not in ("left", "right", "center", "justify"):
            raise ValueError("align must be left, right, center, or justify")
        if not isinstance(self.block_id, str):
            raise ValueError("block_id must be a string")
        for name in ("min_first", "min_last"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
                raise ValueError(f"{name} must be a positive integer or None")

    def _default_style(self, context: LayoutContext) -> TextStyle:
        return context.style.body

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        if not isinstance(context, LayoutContext):
            raise ValueError("context must be a LayoutContext")
        style = self.style if self.style is not None else self._default_style(context)
        lines = wrap_text(self.text, context.fonts, style, available_width,
                          align=self.align, max_tracking_em=context.style.max_tracking_em,
                          block_id=self.block_id)
        parts = []
        for index, line in enumerate(lines):
            baseline = context.baseline_for(line.metrics.ascent)
            rows = context.rows_for(baseline + line.metrics.descent)
            commands = (Text(line.x, baseline, line.text, line.style),) if line.text else ()
            parts.append(LayoutPart(rows, commands, {
                "text": line.text, "line_index": index, "paragraph_end": line.paragraph_end,
            }))
        return MeasuredBlock(
            available_width, context.profile.grid.pitch_y, tuple(parts),
            min_first=context.style.min_first_lines if self.min_first is None else self.min_first,
            min_last=context.style.min_last_lines if self.min_last is None else self.min_last,
            block_id=self.block_id,
        )


@dataclass(frozen=True, slots=True)
class Heading(Paragraph):
    """An indivisible heading that must accompany the next block's first part."""

    def _default_style(self, context: LayoutContext) -> TextStyle:
        return context.style.heading

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        return replace(Paragraph.measure(self, context, available_width),
                       keep_together=True, keep_with_next=True)


@dataclass(frozen=True, slots=True)
class Spacer:
    """Reserve a whole number of grid rows; zero produces an empty block."""

    rows: int

    def __post_init__(self) -> None:
        if isinstance(self.rows, bool) or not isinstance(self.rows, int) or self.rows < 0:
            raise ValueError("rows must be a nonnegative integer")

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        if not isinstance(context, LayoutContext):
            raise ValueError("context must be a LayoutContext")
        available_width = _finite_number(available_width, "available_width")
        if available_width <= 0:
            raise ValueError("available_width must be positive")
        parts = (LayoutPart(self.rows),) if self.rows else ()
        return MeasuredBlock(available_width, context.profile.grid.pitch_y, parts)


@dataclass(frozen=True, slots=True)
class PageBreak:
    """An explicit page-flow marker, consumed by pagination."""
