"""Grid-height paragraph, heading, spacing and separator components."""

from dataclasses import KW_ONLY, dataclass, replace

from .borders import BorderStyle, _border_lines, _border_style
from .errors import LayoutOverflowError
from .layout import LayoutContext, LayoutPart, MeasuredBlock, measurement_inputs
from .scene import Color, Text, _color
from .semantics import Kind, Role, Scope, Tag
from .styles import TextStyle
from .text import wrap_text
from .validation import TOLERANCE, _identifier, _integer


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
        _identifier(self.block_id)
        for name in ("min_first", "min_last"):
            value = getattr(self, name)
            if value is not None:
                _integer(value, name, 1, message=f"{name} must be a positive integer or None")

    def _default_style(self, context: LayoutContext) -> TextStyle:
        return context.style.body

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        style = self.style if self.style is not None else self._default_style(context)
        lines = wrap_text(self.text, context.fonts, style, available_width,
                          align=self.align, max_tracking_em=context.style.max_tracking_em,
                          block_id=self.block_id)
        parts = []
        # The alignment is baked into each line's x; the tag keeps it (and the line number).
        heading = isinstance(self, Heading)
        for index, line in enumerate(lines):
            baseline = context.baseline_for(line.metrics.ascent)
            rows = context.rows_for(baseline + line.metrics.descent)
            tag = Tag(Role.TEXT, (Scope(Kind.PARAGRAPH, index=index,
                                        data={"align": self.align, "heading": heading}),))
            commands = (Text(line.x, baseline, line.text, line.style, tag=tag),) if line.text else ()
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
    """Reserve a whole number of grid rows; zero produces an empty block.

    With ``discard_at_page_top=True`` document flow drops the rows when they
    would come first on a page, like LaTeX's ``\\vspace`` (not ``\\vspace*``).
    """

    rows: int
    _: KW_ONLY
    discard_at_page_top: bool = False

    def __post_init__(self) -> None:
        _integer(self.rows, "rows", 0, message="rows must be a nonnegative integer")
        if not isinstance(self.discard_at_page_top, bool):
            raise ValueError("discard_at_page_top must be a boolean")

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        parts = (LayoutPart(self.rows),) if self.rows else ()
        return MeasuredBlock(available_width, context.profile.grid.pitch_y, parts,
                             discard_at_page_top=self.discard_at_page_top)


@dataclass(frozen=True, slots=True)
class PageBreak:
    """An explicit page-flow marker, consumed by pagination."""


@dataclass(frozen=True, slots=True)
class Rule:
    """A separator across the body, drawn on a grid-row boundary (FR-026).

    The rule takes one grid row (as many as its thickness needs on a fine
    grid) and lies along the top boundary of those rows, kept inside them.
    ``style`` is a border style or its Excel name (thin by default). The line
    spans the available width, or ``columns`` grid columns from the left edge.
    """

    style: BorderStyle | str = BorderStyle.THIN
    _: KW_ONLY
    columns: int | None = None
    color: Color = (0, 0, 0)
    block_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "style", _border_style(self.style, "style", allow_none=False))
        if self.columns is not None:
            _integer(self.columns, "columns", 1, message="columns must be a positive integer or None")
        object.__setattr__(self, "color", _color(self.color, "color"))
        _identifier(self.block_id)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        location = self.block_id or "Rule"
        width = available_width if self.columns is None else self.columns * context.profile.grid.pitch_x
        if width > available_width + TOLERANCE:
            raise LayoutOverflowError(
                f"{location}: rule width {width} exceeds available width {available_width}",
                block_id=location, needed=width, available=available_width,
            )
        style, half = self.style, self.style.stroke_width / 2
        centre = style.thickness / 2
        lines = _border_lines(style, half, centre, width - half, centre, self.color, Role.RULE)
        part = LayoutPart(max(1, context.rows_for(style.thickness)), lines,
                          {"rule": {"style": style.value, "width_pt": width}})
        return MeasuredBlock(width, context.profile.grid.pitch_y, (part,), block_id=self.block_id)
