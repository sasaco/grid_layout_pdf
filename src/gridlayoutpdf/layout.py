"""Immutable measurements shared by text, equations and document flow."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import KW_ONLY, dataclass, field, replace
from typing import Protocol, runtime_checkable

from .bounds import command_bounds
from .errors import FontError, LayoutOverflowError
from .fonts import FontRegistry
from .metadata import freeze_metadata
from .profiles import PageProfile
from .scene import COMMAND_TYPES, Command, Text
from .styles import ReportStyle, _finite_number
from .validation import TOLERANCE, _integer


def _has_visible_commands(commands: Iterable[Command]) -> bool:
    """Whitespace reserves layout space but cannot satisfy a heading's keep rule."""
    return any(not isinstance(command, Text) or bool(command.text.strip()) for command in commands)


@dataclass(frozen=True, slots=True)
class LayoutContext:
    fonts: FontRegistry
    profile: PageProfile
    style: ReportStyle

    def __post_init__(self) -> None:
        for name, expected in (("fonts", FontRegistry), ("profile", PageProfile), ("style", ReportStyle)):
            if not isinstance(getattr(self, name), expected):
                raise ValueError(f"{name} must be a {expected.__name__}")

    def baseline_for(self, ascent: float) -> float:
        """Place a baseline at offset plus whole rows, leaving ascent above it."""
        ascent = _finite_number(ascent, "ascent")
        if ascent < 0:
            raise ValueError("ascent must be nonnegative")
        offset = self.style.baseline_offset
        rows = self.rows_for(max(0, ascent - offset))
        pitch = self.profile.grid.pitch_y
        # Subtracting the offset can round an exact baseline past its row.
        # Compare actual baselines to retain strict nextafter boundaries.
        if rows > 0 and offset + (rows - 1) * pitch >= ascent:
            rows -= 1
        elif offset + rows * pitch < ascent:
            rows += 1
        return _finite_number(offset + rows * pitch, "baseline")

    def rows_for(self, height: float) -> int:
        return self.profile.grid.rows_for(height)


@runtime_checkable
class Block(Protocol):
    """A component measures without drawing or changing the caller's inputs."""

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock: ...


def measurement_inputs(context: LayoutContext, available_width: float) -> float:
    """Validate the arguments every measure(context, available_width) accepts."""
    if not isinstance(context, LayoutContext):
        raise ValueError("context must be a LayoutContext")
    width = _finite_number(available_width, "available_width")
    if width <= 0:
        raise ValueError("available_width must be positive")
    return width


def require_block(block) -> None:
    """Require the measuring contract before a component is measured."""
    if not isinstance(block, Block) or not callable(block.measure):
        raise ValueError("block must implement measure(context, available_width)")


# The commands a part draws only at the edges of the fragment it is placed in.
EDGE_COMMANDS = ("opening", "continuing", "joining", "closing")


@dataclass(frozen=True, slots=True)
class LayoutPart:
    """An indivisible vertical unit with commands relative to its top-left.

    ``commands`` are always drawn. The fragment-edge commands depend on where
    the part lands when a block (or a fragment of it after a page split) is
    placed: ``opening`` only when the part comes first and ``continuing``
    otherwise, when the previous part lies directly above it; ``closing`` only
    when it comes last and ``joining`` otherwise, when the next part follows
    directly. ``joining`` may reach into the next part and ``continuing`` up
    into the previous one, never past it, so a boundary shared by two parts
    can be drawn once, on the boundary. Document places every fragment cut by
    a page break at a page top, so a later part's ``opening`` is drawn only
    there (FR-026).
    """

    rows: int
    commands: tuple[Command, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    _: KW_ONLY
    opening: tuple[Command, ...] = ()
    continuing: tuple[Command, ...] = ()
    joining: tuple[Command, ...] = ()
    closing: tuple[Command, ...] = ()

    def __post_init__(self) -> None:
        _integer(self.rows, "rows", 1, message="rows must be a positive integer")
        for name in ("commands", *EDGE_COMMANDS):
            try:
                commands = tuple(getattr(self, name))
            except TypeError as exc:
                raise ValueError(f"{name} must be an iterable of drawing commands") from exc
            if any(not isinstance(command, COMMAND_TYPES) for command in commands):
                raise ValueError(f"{name} must contain supported drawing commands")
            object.__setattr__(self, name, commands)
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def placed(self, *, first: bool, last: bool) -> tuple[Command, ...]:
        """Return what the part draws at one position in a placed fragment."""
        return (*self.commands, *(self.opening if first else self.continuing),
                *(self.closing if last else self.joining))


@dataclass(frozen=True, slots=True)
class MeasuredBlock:
    """A reserved width and a sequence of indivisible grid-height parts.

    min_first/min_last count body parts (display lines), not physical grid rows.
    prefix parts are repeated on every fragment and never count toward those
    minimum line counts. discard_at_page_top drops the block when flow would
    place it before anything else on a page. ``commands`` draws the parts as
    one placed fragment: the first part's ``opening`` and every other part's
    ``continuing``, the last part's ``closing`` and every other part's
    ``joining``.
    """

    width: float
    row_pitch: float
    parts: tuple[LayoutPart, ...] = ()
    _: KW_ONLY
    prefix: tuple[LayoutPart, ...] = ()
    break_after: tuple[int, ...] | None = None
    min_first: int = 1
    min_last: int = 1
    keep_together: bool = False
    keep_with_next: bool = False
    prefer_keep: bool = False
    discard_at_page_top: bool = False
    block_id: str = ""
    _rows: int = field(init=False, repr=False, compare=False, default=0)

    def __post_init__(self) -> None:
        for name in ("width", "row_pitch"):
            value = _finite_number(getattr(self, name), name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        for name in ("parts", "prefix"):
            try:
                parts = tuple(getattr(self, name))
            except TypeError as exc:
                raise ValueError(f"{name} must be an iterable of LayoutPart objects") from exc
            if any(not isinstance(part, LayoutPart) for part in parts):
                raise ValueError(f"{name} must contain only LayoutPart objects")
            object.__setattr__(self, name, parts)
        object.__setattr__(self, "_rows", sum(part.rows for part in (*self.prefix, *self.parts)))
        if self.prefix and not self.parts:
            raise ValueError("prefix requires at least one body part")
        for name in ("min_first", "min_last"):
            _integer(getattr(self, name), name, 1, message=f"{name} must be a positive integer")
        for name in ("keep_together", "keep_with_next", "prefer_keep", "discard_at_page_top"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")
        if not isinstance(self.block_id, str):
            raise ValueError("block_id must be a string")
        if self.break_after is not None:
            try:
                cuts = tuple(self.break_after)
            except TypeError as exc:
                raise ValueError("break_after must be an iterable of part boundaries") from exc
            if any(isinstance(cut, bool) or not isinstance(cut, int)
                   or not 1 <= cut < len(self.parts) for cut in cuts):
                raise ValueError("break_after boundaries must be between 1 and len(parts)-1")
            object.__setattr__(self, "break_after", tuple(sorted(set(cuts))))
        try:
            _finite_number(self.height, "height")
        except OverflowError as exc:
            raise ValueError("height must be finite") from exc

    @property
    def rows(self) -> int:
        """The validated total, counted once, so flow never re-sums the parts."""
        return self._rows

    @property
    def height(self) -> float:
        return self.rows * self.row_pitch

    @property
    def commands(self) -> tuple[Command, ...]:
        commands = []
        rows = 0
        parts = (*self.prefix, *self.parts)
        for index, part in enumerate(parts):
            placed = part.placed(first=index == 0, last=index == len(parts) - 1)
            commands.extend(command.translated(0, rows * self.row_pitch) for command in placed)
            rows += part.rows
        return tuple(commands)

    def translated(self, dx: float, dy: float) -> tuple[Command, ...]:
        dx, dy = _finite_number(dx, "dx"), _finite_number(dy, "dy")
        return tuple(command.translated(dx, dy) for command in self.commands)

    def _valid_cuts(self):
        """Yield body-part boundaries and their prefix-inclusive grid rows."""
        if self.keep_together:
            return
        allowed = None if self.break_after is None else set(self.break_after)
        rows = sum(part.rows for part in self.prefix)
        for index, part in enumerate(self.parts, start=1):
            rows += part.rows
            if (self.min_first <= index <= len(self.parts) - self.min_last
                    and (allowed is None or index in allowed)):
                yield index, rows

    @property
    def minimum_rows(self) -> int:
        """The smallest first fragment in grid rows, or all rows if indivisible."""
        return next((rows for _, rows in self._valid_cuts()), self.rows)

    def split(self, available_rows: int) -> tuple[MeasuredBlock, MeasuredBlock] | None:
        """Choose the last fitting legal cut, retaining a nonempty body on both sides."""
        if (isinstance(available_rows, bool) or not isinstance(available_rows, int)
                or available_rows < 0):
            raise ValueError("available_rows must be a nonnegative integer")
        if available_rows >= self.rows:
            return None
        cut = None
        for index, rows in self._valid_cuts():
            if rows > available_rows:
                break
            cut = index
        if cut is None:
            return None
        head_cuts = tail_cuts = None
        if self.break_after is not None:
            head_cuts = tuple(index for index in self.break_after if index < cut)
            tail_cuts = tuple(index - cut for index in self.break_after if index > cut)
        return (
            replace(self, parts=self.parts[:cut], break_after=head_cuts, keep_with_next=False),
            replace(self, parts=self.parts[cut:], break_after=tail_cuts),
        )


def part_descriptors(measured: MeasuredBlock) -> dict[str, list[dict]]:
    """Describe prefix and body parts by their row offset inside the block."""
    descriptors: dict[str, list[dict]] = {}
    row = 0
    for name, parts in (("prefix", measured.prefix), ("parts", measured.parts)):
        group = []
        for part in parts:
            group.append({"row": row, "rows": part.rows, "metadata": part.metadata})
            row += part.rows
        descriptors[name] = group
    return descriptors


def block_trace(measured: MeasuredBlock, x_pt: float, y_pt: float) -> dict:
    """Snapshot a measured block's origin and part metadata, without commands."""
    return {
        "block_id": measured.block_id, "x_pt": x_pt, "y_pt": y_pt,
        "width": measured.width, "rows": measured.rows, "row_pitch": measured.row_pitch,
        **part_descriptors(measured),
    }


def measure_child(block: Block, context: LayoutContext, available_width: float, location: str,
                  *, own_block_id: bool = False, type_errors: bool = False,
                  hint: str = "") -> MeasuredBlock:
    """Measure a nested block, keeping its diagnostics inside the caller's path.

    ``own_block_id`` reports ``location`` instead of the child's identifier,
    for frames that own the failing region. ``type_errors`` also treats a
    TypeError as an input error, and ``hint`` appends caller guidance to it.
    """
    try:
        return measure_block(block, context, available_width)
    except FontError as exc:
        raise FontError(f"{location}: {exc}") from exc
    except LayoutOverflowError as exc:
        raise LayoutOverflowError(
            f"{location}: {exc}",
            block_id=location if own_block_id else (exc.block_id or location),
            needed=exc.needed, available=exc.available,
        ) from exc
    except ValueError as exc:
        raise ValueError(f"{location}: {exc}{hint}") from exc
    except TypeError as exc:
        if not type_errors:
            raise
        raise ValueError(f"{location}: {exc}{hint}") from exc


def measure_block(block: Block, context: LayoutContext, available_width: float) -> MeasuredBlock:
    """Measure and validate a component at the shared layout boundary.

    Only tiny absolute floating-point roundoff is tolerated. Parts may overlap
    internally, but every command's ink/stroke envelope must fit its own part.
    A part whose metadata records ``overhang_pt`` (set by ``Leading``) may
    extend that far below its last row, ``joining`` commands into the part
    that follows it and ``continuing`` commands into the part before it,
    never past that part.
    """
    available_width = measurement_inputs(context, available_width)
    require_block(block)
    source_id = getattr(block, "block_id", "")
    source_id = source_id if isinstance(source_id, str) and source_id else type(block).__name__
    try:
        result = block.measure(context, available_width)
    except FontError as exc:
        raise FontError(f"{source_id}: {exc}") from exc
    except LayoutOverflowError as exc:
        raise LayoutOverflowError(
            f"{source_id}: {exc}", block_id=exc.block_id or source_id,
            needed=exc.needed, available=exc.available,
        ) from exc
    if not isinstance(result, MeasuredBlock):
        raise ValueError(f"{source_id}: measure must return a MeasuredBlock")
    block_id = result.block_id or source_id
    if result.width > available_width + TOLERANCE:
        raise LayoutOverflowError(
            f"{block_id}: reserved width {result.width} exceeds available width {available_width}",
            block_id=block_id, needed=result.width, available=available_width,
        )
    if abs(result.row_pitch - context.profile.grid.pitch_y) > TOLERANCE:
        raise ValueError(f"{block_id}: row_pitch must match the context grid pitch")
    for group_name, parts in (("prefix", result.prefix), ("parts", result.parts)):
        for part_index, part in enumerate(parts):
            height = part.rows * result.row_pitch
            overhang = _finite_number(part.metadata.get("overhang_pt", 0.0),
                                      f"{block_id}.{group_name}[{part_index}] overhang_pt")
            if overhang < 0:
                raise ValueError(f"{block_id}.{group_name}[{part_index}] overhang_pt must not be negative")
            height += overhang
            following = _following_rows(result, group_name, part_index) * result.row_pitch
            preceding = _preceding_rows(result, group_name, part_index) * result.row_pitch
            for name in ("commands", *EDGE_COMMANDS):
                top = -preceding if name == "continuing" else 0.0
                bottom = height + following if name == "joining" else height
                for command_index, command in enumerate(getattr(part, name)):
                    location = f"{block_id}.{group_name}[{part_index}].{name}[{command_index}]"
                    _check_part_bounds(command, context, location, block_id, result.width, top, bottom)
    return result


def _following_rows(measured: MeasuredBlock, group_name: str, index: int) -> int:
    """Rows of the shortest part that can directly follow a part when it joins.

    Any body part can follow the last prefix part once the block is split;
    nothing follows the last body part, so its ``joining`` is never drawn.
    """
    parts = measured.prefix if group_name == "prefix" else measured.parts
    if index + 1 < len(parts):
        return parts[index + 1].rows
    if group_name == "prefix":
        return min(part.rows for part in measured.parts)
    return 0


def _preceding_rows(measured: MeasuredBlock, group_name: str, index: int) -> int:
    """Rows of the shortest part that can lie directly above a continuing part.

    The last prefix part can come before any body part once the block is
    split; nothing comes before the first prefix part, or before the first
    body part of a block without a prefix.
    """
    parts = measured.prefix if group_name == "prefix" else measured.parts
    candidates = [parts[index - 1].rows] if index else []
    if group_name == "parts" and measured.prefix:
        candidates.append(measured.prefix[-1].rows)
    return min(candidates, default=0)


def _check_part_bounds(command: Command, context: LayoutContext, location: str, block_id: str,
                       width: float, top: float, bottom: float) -> None:
    """Require a command's ink/stroke envelope to lie in (0, top, width, bottom)."""
    try:
        bounds = command_bounds(command, context.fonts)
    except FontError as exc:
        raise FontError(f"{location}: {exc}") from exc
    if (bounds.x < -TOLERANCE or bounds.y < top - TOLERANCE
            or bounds.right > width + TOLERANCE
            or bounds.bottom > bottom + TOLERANCE):
        horizontal = bounds.x < -TOLERANCE or bounds.right > width + TOLERANCE
        raise LayoutOverflowError(
            f"{location}: {type(command).__name__} bounds "
            f"({bounds.x}, {bounds.y}, {bounds.right}, {bounds.bottom}) "
            f"exceed part (0, {top}, {width}, {bottom})",
            block_id=block_id,
            needed=bounds.width if horizontal else bounds.height,
            available=width if horizontal else bottom - top,
        )
