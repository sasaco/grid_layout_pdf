"""Immutable composition containers and explicit grid-placement directives."""

from dataclasses import dataclass, replace

from .errors import FontError, LayoutOverflowError
from .layout import Block, LayoutContext, LayoutPart, MeasuredBlock, _has_visible_commands, measure_block
from .styles import _finite_number


def _identifier(block_id: str) -> None:
    if not isinstance(block_id, str):
        raise ValueError("block_id must be a string")


def _integer(value: int, name: str, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _block(block: Block) -> None:
    if not isinstance(block, Block) or not callable(block.measure):
        raise ValueError("block must implement measure(context, available_width)")


def _measurement_inputs(context: LayoutContext, available_width: float) -> float:
    if not isinstance(context, LayoutContext):
        raise ValueError("context must be a LayoutContext")
    width = _finite_number(available_width, "available_width")
    if width <= 0:
        raise ValueError("available_width must be positive")
    return width


def _measure_child(child, context, width, location) -> MeasuredBlock:
    """Keep the child diagnostic and exception chain inside its container path."""
    try:
        return measure_block(child, context, width)
    except FontError as exc:
        raise FontError(f"{location}: {exc}") from exc
    except LayoutOverflowError as exc:
        raise LayoutOverflowError(
            f"{location}: {exc}", block_id=exc.block_id,
            needed=exc.needed, available=exc.available,
        ) from exc
    except ValueError as exc:
        raise ValueError(f"{location}: {exc}") from exc


def _child_trace(measured: MeasuredBlock, x_pt: float, y_pt: float) -> dict:
    """Snapshot origins and local part metadata without embedding commands."""
    trace = {
        "block_id": measured.block_id, "x_pt": x_pt, "y_pt": y_pt,
        "width": measured.width, "rows": measured.rows, "row_pitch": measured.row_pitch,
    }
    row = 0
    for name, parts in (("prefix", measured.prefix), ("parts", measured.parts)):
        descriptors = []
        for part in parts:
            descriptors.append({"row": row, "rows": part.rows, "metadata": part.metadata})
            row += part.rows
        trace[name] = descriptors
    return trace


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
        available_width = _measurement_inputs(context, available_width)
        pitch = context.profile.grid.pitch_y
        commands, rows, width, keep_next = [], 0, 0.0, False
        children = []
        for index, child in enumerate(self.children):
            location = f"{self.block_id or 'Stack'}.children[{index}]"
            measured = _measure_child(child, context, available_width, location)
            child_commands = measured.commands
            children.append(_child_trace(measured, 0, rows * pitch))
            commands.extend(command.translated(0, rows * pitch) for command in child_commands)
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
        available_width = _measurement_inputs(context, available_width)
        pitch_x, pitch_y = context.profile.grid.pitch_x, context.profile.grid.pitch_y
        total_columns = sum(self.col_spans) + max(0, len(self.children) - 1) * self.gap_cols
        width = total_columns * pitch_x
        # Cell padding arithmetic can differ from an equal grid span by an ulp.
        if width > available_width + 1e-7:
            raise LayoutOverflowError(
                f"{self.block_id or 'Columns'}: column width {width} exceeds available width {available_width}",
                block_id=self.block_id or "Columns", needed=width, available=available_width,
            )
        commands, rows, col, keep_next = [], 0, 0, False
        children = []
        for index, (child, span) in enumerate(zip(self.children, self.col_spans)):
            location = f"{self.block_id or 'Columns'}.children[{index}]"
            measured = _measure_child(child, context, span * pitch_x, location)
            child_commands = measured.commands
            children.append(_child_trace(measured, col * pitch_x, 0))
            commands.extend(command.translated(col * pitch_x, 0) for command in child_commands)
            rows = max(rows, measured.rows)
            if _has_visible_commands(child_commands):
                keep_next = keep_next or measured.keep_with_next
            col += span + self.gap_cols
        parts = (LayoutPart(rows, tuple(commands), {"children": children}),) if rows else ()
        return MeasuredBlock(
            width or available_width, pitch_y, parts,
            keep_together=True, keep_with_next=keep_next, block_id=self.block_id,
        )


@dataclass(frozen=True, slots=True)
class KeepTogether:
    """Preserve a child's measurement while prohibiting page splits."""

    block: Block
    block_id: str = ""

    def __post_init__(self) -> None:
        _identifier(self.block_id)
        _block(self.block)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = _measurement_inputs(context, available_width)
        measured = _measure_child(
            self.block, context, available_width, f"{self.block_id or 'KeepTogether'}.block",
        )
        return replace(measured, keep_together=True, block_id=self.block_id or measured.block_id)


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
        _block(self.block)
