"""Immutable composition containers and explicit grid-placement directives."""

from dataclasses import KW_ONLY, dataclass, replace

from .borders import BorderStyle, _border_lines, _border_style
from .errors import LayoutOverflowError
from .layout import (
    EDGE_COMMANDS, Block, LayoutContext, LayoutPart, MeasuredBlock, _has_visible_commands,
    block_trace, measure_child, measurement_inputs, require_block,
)
from .scene import Rectangle, _color
from .semantics import Kind, Role, Scope, Tag, within
from .validation import TOLERANCE, _finite_number, _identifier, _integer


@dataclass(frozen=True, slots=True, init=False)
class Stack:
    """Vertical children; atomic when measured inside another container.

    Document flow expands children directly to preserve their split rules.
    Explicit blank children provide spacing; Stack introduces no extra gap.
    """

    children: tuple[object, ...]
    block_id: str

    def __init__(self, *blocks, block_id: str = "") -> None:
        _identifier(block_id)
        object.__setattr__(self, "children", tuple(blocks))
        object.__setattr__(self, "block_id", block_id)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        pitch = context.profile.grid.pitch_y
        commands, rows, width, keep_next = [], 0, 0.0, False
        children = []
        for index, child in enumerate(self.children):
            location = f"{self.block_id or 'Stack'}.children[{index}]"
            measured = measure_child(child, context, available_width, location)
            child_commands = measured.commands
            children.append(block_trace(measured, 0, rows * pitch))
            # Numbering the children keeps two figures (or tables...) of one stack apart.
            commands.extend(within((command.translated(0, rows * pitch) for command in child_commands),
                                   Scope(Kind.STACK, index=index)))
            rows += measured.rows
            width = max(width, measured.width)
            if _has_visible_commands(child_commands):
                keep_next = measured.keep_with_next
        parts = (LayoutPart(rows, tuple(commands), {"children": children}),) if rows else ()
        return MeasuredBlock(
            width or available_width, pitch, parts,
            keep_together=True, keep_with_next=keep_next, block_id=self.block_id,
        )


@dataclass(frozen=True, slots=True, init=False)
class Columns:
    """Atomic side-by-side children with explicit grid-column widths."""

    children: tuple[object, ...]
    col_spans: tuple[int, ...]
    gap_cols: int
    block_id: str

    def __init__(self, *blocks, col_spans, gap_cols: int = 1, block_id: str = "") -> None:
        _identifier(block_id)
        _integer(gap_cols, "gap_cols", 0)
        try:
            spans = tuple(col_spans)
        except TypeError as exc:
            raise ValueError("col_spans must be an iterable of positive integers") from exc
        if len(spans) != len(blocks):
            raise ValueError("col_spans must match the number of children")
        for span in spans:
            _integer(span, "col_spans", 1)
        object.__setattr__(self, "children", tuple(blocks))
        object.__setattr__(self, "col_spans", spans)
        object.__setattr__(self, "gap_cols", gap_cols)
        object.__setattr__(self, "block_id", block_id)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        pitch_x, pitch_y = context.profile.grid.pitch_x, context.profile.grid.pitch_y
        total_columns = sum(self.col_spans) + max(0, len(self.children) - 1) * self.gap_cols
        width = total_columns * pitch_x
        # Cell padding arithmetic can differ from an equal grid span by an ulp.
        if width > available_width + TOLERANCE:
            raise LayoutOverflowError(
                f"{self.block_id or 'Columns'}: column width {width} exceeds available width {available_width}",
                block_id=self.block_id or "Columns", needed=width, available=available_width,
            )
        commands, rows, col, keep_next = [], 0, 0, False
        children = []
        for index, (child, span) in enumerate(zip(self.children, self.col_spans)):
            location = f"{self.block_id or 'Columns'}.children[{index}]"
            measured = measure_child(child, context, span * pitch_x, location)
            child_commands = measured.commands
            children.append(block_trace(measured, col * pitch_x, 0))
            commands.extend(within((command.translated(col * pitch_x, 0) for command in child_commands),
                                   Scope(Kind.COLUMNS, index=index)))
            rows = max(rows, measured.rows)
            if _has_visible_commands(child_commands):
                keep_next = keep_next or measured.keep_with_next
            col += span + self.gap_cols
        parts = (LayoutPart(rows, tuple(commands), {"children": children}),) if rows else ()
        return MeasuredBlock(
            width or available_width, pitch_y, parts,
            keep_together=True, keep_with_next=keep_next, block_id=self.block_id,
        )


def _with_flow_rule(wrapper, context: LayoutContext, available_width: float, **rule) -> MeasuredBlock:
    """Measure a wrapper's child and set one pagination flag, keeping its parts."""
    available_width = measurement_inputs(context, available_width)
    measured = measure_child(
        wrapper.block, context, available_width,
        f"{wrapper.block_id or type(wrapper).__name__}.block",
    )
    return replace(measured, **rule, block_id=wrapper.block_id or measured.block_id)


@dataclass(frozen=True, slots=True)
class KeepTogether:
    """Preserve a child's measurement while prohibiting page splits."""

    block: Block
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        require_block(self.block)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        return _with_flow_rule(self, context, available_width, keep_together=True)


@dataclass(frozen=True, slots=True)
class KeepWithNext:
    """Keep a block on the same page as the next visible block's first part.

    The child's measurement and split rules are otherwise unchanged, as for
    a Heading.
    """

    block: Block
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        require_block(self.block)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        return _with_flow_rule(self, context, available_width, keep_with_next=True)


@dataclass(frozen=True, slots=True)
class PreferKeepTogether:
    """Move a block to a fresh page when it fits one; otherwise split it.

    Unlike KeepTogether, a block taller than an empty page keeps its legal
    split points instead of raising an overflow.
    """

    block: Block
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        require_block(self.block)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        return _with_flow_rule(self, context, available_width, prefer_keep=True)


@dataclass(frozen=True, slots=True)
class Indent:
    """Measure a block ``left`` pt narrower and shift it right by that amount.

    The offset is in points from the block's own left edge, independent of the
    grid columns. Every part records it as ``indent_pt`` metadata.
    """

    block: Block
    left: float
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        require_block(self.block)
        left = _finite_number(self.left, "left")
        if left < 0:
            raise ValueError("left must be nonnegative")
        object.__setattr__(self, "left", left)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        location = self.block_id or "Indent"
        if self.left >= available_width:
            raise LayoutOverflowError(
                f"{location}: indent {self.left} leaves no width of {available_width}",
                block_id=location, needed=self.left, available=available_width,
            )
        child = measure_child(self.block, context, available_width - self.left, f"{location}.block")

        def shifted(parts: tuple[LayoutPart, ...]) -> tuple[LayoutPart, ...]:
            return tuple(replace(part, metadata={**part.metadata, "indent_pt": self.left},
                                 **{name: tuple(command.translated(self.left, 0)
                                                for command in getattr(part, name))
                                    for name in ("commands", *EDGE_COMMANDS)})
                         for part in parts)

        return replace(child, width=child.width + self.left, parts=shifted(child.parts),
                       prefix=shifted(child.prefix), block_id=self.block_id or child.block_id)


@dataclass(frozen=True, slots=True)
class SideRule:
    """Draw a vertical rule ``x`` pt from the block's left edge beside every part.

    The rule has a border ``style`` (FR-022), thin by default; ``x`` is the
    centre of its ink. Each part, prefix included, gets the rule over its
    whole height. Solid styles are filled bars (two for ``double``, whose
    centres are 1.0 pt apart), so the bars of adjacent parts join on a page
    and the rule breaks with the page. Dashed styles are dashed lines kept
    half a stroke inside each part. ``top`` shortens the rule of the first
    body part and ``bottom`` that of the last one. The child's measurement and
    flow flags are otherwise unchanged; every part records ``side_rule_pt``
    and ``side_rule_style`` (the style's Excel name).
    """

    block: Block
    x: float
    _: KW_ONLY
    style: BorderStyle | str = BorderStyle.THIN
    top: float = 0.0
    bottom: float = 0.0
    color: tuple[float, float, float] = (0, 0, 0)
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        require_block(self.block)
        object.__setattr__(self, "style", _border_style(self.style, "style", allow_none=False))
        for name in ("x", "top", "bottom"):
            value = _finite_number(getattr(self, name), name)
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
            object.__setattr__(self, name, value)
        if self.x < self.style.thickness / 2:
            raise ValueError("x must leave half the rule thickness at the left edge")
        object.__setattr__(self, "color", _color(self.color, "color"))

    def _bars(self, top: float, bottom: float, height: float) -> tuple:
        """Return the rule from ``top`` to ``bottom`` in a part ``height`` pt tall."""
        style, width = self.style, self.style.stroke_width
        if not style.dash:
            return tuple(Rectangle(self.x + offset - width / 2, top, width, bottom - top,
                                   fill=self.color, stroke=False,
                                   tag=Tag(Role.SIDE_RULE, (), {"style": style.value, "stroke": index}))
                         for index, offset in enumerate(style.offsets))
        # A stroke's envelope reaches half its width past each end.
        start, stop = max(top, width / 2), min(bottom, height - width / 2)
        if stop <= start:
            raise ValueError(f"{self.block_id or 'SideRule'}: top and bottom leave no dashed rule "
                             f"in a part of {height} pt")
        return _border_lines(style, self.x, start, self.x, stop, self.color, Role.SIDE_RULE)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        location = self.block_id or "SideRule"
        right = self.x + self.style.thickness / 2
        if right > available_width + TOLERANCE:
            raise LayoutOverflowError(
                f"{location}: rule at {self.x} exceeds available width {available_width}",
                block_id=location, needed=right, available=available_width,
            )
        child = measure_child(self.block, context, available_width, f"{location}.block")
        pitch = child.row_pitch

        def ruled(part: LayoutPart, top: float, bottom: float) -> LayoutPart:
            height = part.rows * pitch
            if height - top - bottom <= 0:
                raise ValueError(f"{location}: top and bottom leave no rule in a part of {height} pt")
            bars = self._bars(top, height - bottom, height)
            return replace(part, commands=(*part.commands, *bars),
                           metadata={**part.metadata, "side_rule_pt": self.x,
                                     "side_rule_style": self.style.value})

        last = len(child.parts) - 1
        parts = tuple(ruled(part, self.top if index == 0 else 0.0, self.bottom if index == last else 0.0)
                      for index, part in enumerate(child.parts))
        prefix = tuple(ruled(part, 0.0, 0.0) for part in child.prefix)
        return replace(child, width=max(child.width, right), parts=parts, prefix=prefix,
                       block_id=self.block_id or child.block_id)


@dataclass(frozen=True, slots=True)
class Leading:
    """Give every body part (display line) exactly ``rows`` grid rows.

    A part needing more rows raises an overflow. ``minimum=True`` instead
    raises only shorter parts to ``rows`` and leaves taller ones unchanged.
    ``overhang`` (pt) lets a part exceed ``rows`` by at most that height and
    still advance by ``rows``; its drawing is unchanged and spills into the
    next line, and the excess is recorded as ``overhang_pt`` in its metadata.
    Repeating prefix parts are rejected, because their advance is ambiguous,
    and so is changing the rows of a part with fragment-edge commands (a
    table's row-group boundaries), which are drawn on its own edges.
    """

    block: Block
    rows: int
    _: KW_ONLY
    minimum: bool = False
    overhang: float = 0.0
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        require_block(self.block)
        _integer(self.rows, "rows", 1, message="rows must be a positive integer")
        if not isinstance(self.minimum, bool):
            raise ValueError("minimum must be a boolean")
        overhang = _finite_number(self.overhang, "overhang")
        if overhang < 0:
            raise ValueError("overhang must be a finite non-negative number")
        object.__setattr__(self, "overhang", overhang)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        location = self.block_id or "Leading"
        child = measure_child(self.block, context, available_width, f"{location}.block")
        if child.prefix:
            raise ValueError(f"{location}: Leading applies to body lines, not a repeating prefix")
        parts = []
        for part in child.parts:
            excess = (part.rows - self.rows) * child.row_pitch
            total = excess + part.metadata.get("overhang_pt", 0.0)
            if excess > 0 and total <= self.overhang + TOLERANCE:
                rows, metadata = self.rows, {**part.metadata, "overhang_pt": total}
            elif excess > 0 and not self.minimum:
                raise LayoutOverflowError(
                    f"{location}: leading of {self.rows} rows is smaller than a measured "
                    f"line of {part.rows} rows",
                    block_id=self.block_id or child.block_id or location,
                    needed=part.rows * child.row_pitch, available=self.rows * child.row_pitch,
                )
            else:
                rows, metadata = max(part.rows, self.rows), part.metadata
            if rows != part.rows and any(getattr(part, name) for name in EDGE_COMMANDS):
                raise ValueError(f"{location}: leading would move the edge lines of a part "
                                 f"of {part.rows} rows (a split table's boundaries)")
            parts.append(replace(part, rows=rows, metadata=metadata))
        return replace(child, parts=tuple(parts), block_id=self.block_id or child.block_id)


@dataclass(frozen=True, slots=True)
class At:
    """Place an atomic block at explicit grid indices during document flow.

    This directive is not measurable: page bounds and occupied regions are
    resolved by Document using the current page profile and flow cursor.
    """

    row: int
    col: int
    col_span: int
    block: Block
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        _integer(self.row, "row", 0)
        _integer(self.col, "col", 0)
        _integer(self.col_span, "col_span", 1)
        require_block(self.block)
