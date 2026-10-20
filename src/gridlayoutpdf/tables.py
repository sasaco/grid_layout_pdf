"""Grid-sized tables with atomic merged cells and repeatable headers."""

from dataclasses import KW_ONLY, dataclass, field
from itertools import accumulate

from .blocks import Paragraph
from .borders import BorderStyle, TableBorders, _border_lines, _table_borders
from .bounds import command_bounds
from .errors import LayoutOverflowError
from .layout import (
    Block, LayoutContext, LayoutPart, MeasuredBlock, block_trace, measure_child,
    measurement_inputs,
)
from .scene import Line
from .semantics import Kind, Role, Scope, within
from .styles import Insets, TextStyle, _finite_number, _resolve_insets
from .validation import TOLERANCE, _identifier, _integer


# Content that cannot be measured names the contract it is missing.
_CONTENT_HINT = ("; content requires Block.measure(context, width); "
                 "mathematical nodes require MathBlock")


def proportional_spans(weights, total: int) -> tuple[int, ...]:
    """Divide ``total`` grid units among columns in proportion to ``weights``.

    Each boundary is the rounded cumulative share, so the spans always sum to
    ``total`` and rounding never accumulates across columns. Every resulting
    column must receive at least one unit.
    """
    try:
        values = tuple(_finite_number(weight, "weights") for weight in weights)
    except TypeError as exc:
        raise ValueError("weights must be a sequence of nonnegative numbers") from exc
    _integer(total, "total", 1)
    if not values or any(value < 0 for value in values) or not sum(values) > 0:
        raise ValueError("weights must be nonnegative with a positive sum")
    boundaries = [round(total * sum(values[:index]) / sum(values)) for index in range(len(values) + 1)]
    spans = tuple(right - left for left, right in zip(boundaries, boundaries[1:]))
    if any(span < 1 for span in spans):
        raise ValueError(f"total {total} leaves a column without a grid unit")
    return spans


@dataclass(frozen=True, slots=True)
class Cell:
    content: str | Block = ""
    _: KW_ONLY
    colspan: int = 1
    rowspan: int = 1
    align: str | None = None
    valign: str = "middle"
    padding: float | Insets = 3.0
    style: TextStyle | None = None

    def __post_init__(self):
        if not isinstance(self.content, str) and (
            not isinstance(self.content, Block) or not callable(self.content.measure)
        ):
            raise ValueError("content must be a display string or measurable Block")
        _integer(self.colspan, "colspan", 1)
        _integer(self.rowspan, "rowspan", 1)
        if self.align not in (None, "left", "center", "right"):
            raise ValueError("align must be None, left, center or right")
        if self.valign not in ("top", "middle", "bottom"):
            raise ValueError("valign must be top, middle or bottom")
        resolved = _resolve_insets(self.padding, "padding")
        if not isinstance(self.padding, Insets):
            object.__setattr__(self, "padding", resolved.top)
        if self.style is not None:
            if not isinstance(self.style, TextStyle):
                raise ValueError("style must be a TextStyle or None")
            if not isinstance(self.content, str):
                raise ValueError("style applies only to string content")


@dataclass(frozen=True, slots=True)
class _PlacedCell:
    row: int
    col: int
    cell: Cell


@dataclass(frozen=True, slots=True)
class _MeasuredCell:
    """One placed cell with its measured content and height requirement."""

    placed: _PlacedCell
    path: str
    padding: Insets
    align: str
    content: MeasuredBlock
    requirement: dict


@dataclass(frozen=True, slots=True)
class _Geometry:
    """Boundaries as whole grid units, so every pt value rounds exactly once."""

    pitch_x: float
    pitch_y: float
    column_starts: tuple[int, ...]
    row_starts: tuple[int, ...]
    by_row: tuple[tuple[_MeasuredCell, ...], ...]
    row_heights: tuple[int, ...]
    allocations: tuple[dict, ...]

    def x(self, column: int) -> float:
        return self.column_starts[column] * self.pitch_x

    def y(self, row: int, start: int) -> float:
        """Return a source row boundary relative to the part starting at start."""
        return (self.row_starts[row] - self.row_starts[start]) * self.pitch_y


@dataclass(frozen=True, slots=True)
class _CellBox:
    """A cell's part-local frame with the border thickness on each side.

    ``strokes`` is (left, right, top, bottom): the thickest style along that
    side, 0 where no line is drawn.
    """

    x0: float
    x1: float
    y0: float
    y1: float
    width: float
    strokes: tuple[float, float, float, float]

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True, slots=True)
class Table:
    """A table with independently contained merged row groups and headers.

    ``borders`` gives every edge an Excel border style or no line (FR-022,
    FR-026): a TableBorders, one BorderStyle for every edge, or None for none.
    Every edge is thin by default. Edges inside a merged cell are never drawn.
    The outer frame lies inside the table; other edges are centred on their
    boundary. A boundary between two row groups is drawn once, by the upper
    group, as when the table is not split. When a page break cuts the table
    there, the upper group closes the page with that boundary inside it and
    the lower group draws it as its top inside itself, at the next page top.
    A repeated header keeps its own lower boundary and the body group below
    it draws no second top. Content keeps clear of each line it may meet: the
    whole thickness at the top and bottom of a row group, half of it inside,
    and the body groups also keep clear of half the repeated header's lower
    line, which lies over whichever of them follows it on a later page.
    On one page a split table has the same solid ink as an indivisible one;
    a dashed pattern starts afresh in each row group.

    row_heights optionally fixes each source row's height in local grid rows.
    Content and padding must fit those exact allocations, including rowspans;
    insufficient space raises instead of expanding rows or shrinking content.
    None preserves automatic row allocation.

    split=False emits one indivisible part including the header. The default
    True keeps row groups and the repeatable header as separate parts for
    pagination, with each boundary between them drawn once.
    """

    columns: tuple[int, ...]
    rows: tuple[tuple[Cell, ...], ...]
    _: KW_ONLY
    header_rows: int = 0
    row_heights: tuple[int, ...] | None = None
    split: bool = True
    numeric_columns: tuple[int, ...] = ()
    borders: TableBorders = TableBorders()
    border_color: tuple[float, float, float] = (0, 0, 0)
    block_id: str = ""
    _cells: tuple[_PlacedCell, ...] = field(init=False, repr=False)
    # Resolved styles, None inside merged cells: [row boundary][column] and [row][column boundary].
    _horizontal: tuple[tuple[BorderStyle | None, ...], ...] = field(init=False, repr=False, compare=False)
    _vertical: tuple[tuple[BorderStyle | None, ...], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        try:
            columns = tuple(self.columns)
        except TypeError as exc:
            raise ValueError("columns must be a nonempty sequence of positive integers") from exc
        if not columns:
            raise ValueError("columns must not be empty")
        for column in columns:
            _integer(column, "columns", 1)
        object.__setattr__(self, "columns", columns)
        try:
            if isinstance(self.rows, str):
                raise ValueError("rows must be sequences of cells")
            rows = []
            for row in self.rows:
                if isinstance(row, str):
                    raise ValueError("rows must be sequences of cells")
                cells = tuple(Cell(cell) if isinstance(cell, str) else cell for cell in row)
                if any(not isinstance(cell, Cell) for cell in cells):
                    raise ValueError("rows must contain Cell objects or strings")
                rows.append(cells)
        except TypeError as exc:
            raise ValueError("rows must be sequences of cells") from exc
        object.__setattr__(self, "rows", tuple(rows))
        if self.row_heights is not None:
            try:
                heights = tuple(self.row_heights)
            except TypeError as exc:
                raise ValueError("row_heights must be a sequence of positive integers or None") from exc
            if len(heights) != len(rows):
                raise ValueError("row_heights must contain one height per table row")
            for height in heights:
                _integer(height, "row_heights", 1)
                _finite_number(height, "row_heights")
            object.__setattr__(self, "row_heights", heights)
        _integer(self.header_rows, "header_rows")
        if not isinstance(self.split, bool):
            raise ValueError("split must be a boolean")
        if self.header_rows > len(rows):
            raise ValueError("header_rows must not exceed the number of rows")
        try:
            numeric = tuple(self.numeric_columns)
        except TypeError as exc:
            raise ValueError("numeric_columns must be a sequence of table column indices") from exc
        for index in numeric:
            _integer(index, "numeric_columns")
            if index >= len(columns):
                raise ValueError("numeric_columns index is outside the table")
        object.__setattr__(self, "numeric_columns", tuple(sorted(set(numeric))))
        object.__setattr__(self, "borders", _table_borders(self.borders))
        try:
            color = tuple(_finite_number(c, "border_color") for c in self.border_color)
        except TypeError as exc:
            raise ValueError("border_color must have three components") from exc
        if len(color) != 3 or any(c < 0 or c > 1 for c in color):
            raise ValueError("border_color must have three components between 0 and 1")
        object.__setattr__(self, "border_color", color)
        _identifier(self.block_id)
        self.borders._check(len(rows), len(columns), self.block_id or "Table")
        object.__setattr__(self, "_cells", self._place_cells())
        self._resolve_borders()

    def _resolve_borders(self) -> None:
        """Resolve every edge's style and clear the edges inside merged cells."""
        horizontal, vertical = self.borders.resolve(len(self.rows), len(self.columns))
        horizontal = [list(boundary) for boundary in horizontal]
        vertical = [list(row) for row in vertical]
        inside_h, inside_v = set(), set()
        for placed in self._cells:
            rows = range(placed.row, placed.row + placed.cell.rowspan)
            columns = range(placed.col, placed.col + placed.cell.colspan)
            inside_h.update((boundary, column) for boundary in rows[1:] for column in columns)
            inside_v.update((row, boundary) for row in rows for boundary in columns[1:])
        location = self.block_id or "Table"
        for name, inside in (("horizontal_edges", inside_h), ("vertical_edges", inside_v)):
            for edge, _ in getattr(self.borders, name):
                if edge in inside:
                    raise ValueError(f"{location}: borders.{name} edge {edge} lies inside a merged cell")
        for boundary, column in inside_h:
            horizontal[boundary][column] = None
        for row, boundary in inside_v:
            vertical[row][boundary] = None
        object.__setattr__(self, "_horizontal", tuple(tuple(boundary) for boundary in horizontal))
        object.__setattr__(self, "_vertical", tuple(tuple(row) for row in vertical))

    def _place_cells(self):
        occupied = [[False] * len(self.columns) for _ in self.rows]
        placed = []
        for row_index, row in enumerate(self.rows):
            for cell in row:
                col = next((c for c, used in enumerate(occupied[row_index]) if not used), len(self.columns))
                path = f"{self.block_id or 'Table'}.rows[{row_index}].cells[{col}]"
                if col + cell.colspan > len(self.columns) or row_index + cell.rowspan > len(self.rows):
                    raise ValueError(f"{path}: span exceeds table rows/columns")
                if row_index < self.header_rows < row_index + cell.rowspan:
                    raise ValueError(f"{path}: rowspan crosses header/body boundary")
                for r in range(row_index, row_index + cell.rowspan):
                    for c in range(col, col + cell.colspan):
                        if occupied[r][c]:
                            raise ValueError(f"{path}: span overlaps an occupied cell")
                        occupied[r][c] = True
                placed.append(_PlacedCell(row_index, col, cell))
            if not all(occupied[row_index]):
                raise ValueError(f"{self.block_id or 'Table'}.rows[{row_index}]: unoccupied cell hole")
        return tuple(placed)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
        pitch_x, pitch = context.profile.grid.pitch_x, context.profile.grid.pitch_y
        width = sum(self.columns) * pitch_x
        if width > available_width + TOLERANCE:
            raise LayoutOverflowError(
                f"{self.block_id or 'Table'}: table width {width} exceeds {available_width}",
                block_id=self.block_id or "Table", needed=width, available=available_width,
            )
        if not self.rows:
            return MeasuredBlock(width, pitch, block_id=self.block_id)
        cells = tuple(self._measure_cell(context, placed) for placed in self._cells)
        row_heights, allocations = self._allocate_rows(cells, pitch)
        by_row = [[] for _ in self.rows]
        for cell in cells:
            by_row[cell.placed.row].append(cell)
        geometry = _Geometry(
            pitch_x, pitch,
            tuple(accumulate(self.columns, initial=0)),
            tuple(accumulate(row_heights, initial=0)),
            tuple(tuple(group) for group in by_row),
            tuple(row_heights), tuple(allocations),
        )
        groups = self._row_groups() if self.split else [(0, len(self.rows))]
        repeated = self.split and self.header_rows and self.header_rows < len(self.rows)
        # Any body group can lie under the repeated header's centred lower line.
        under = tuple(style.thickness / 2 if style else 0.0
                      for style in self._horizontal[self.header_rows]) if repeated else None
        parts = tuple(self._make_part(context, start, stop, geometry,
                                      under if repeated and index else None)
                      for index, (start, stop) in enumerate(groups))
        if repeated:
            prefix, body = parts[:1], parts[1:]
        else:
            prefix, body = (), parts
        return MeasuredBlock(width, pitch, body, prefix=prefix, block_id=self.block_id)

    def _measure_cell(self, context: LayoutContext, placed: _PlacedCell) -> _MeasuredCell:
        cell = placed.cell
        cell_width = self._cell_width(placed, context.profile.grid.pitch_x)
        path = self._path(placed)
        padding = _resolve_insets(cell.padding, "padding")
        available = cell_width - (padding.left + padding.right)
        if available <= 0:
            raise LayoutOverflowError(
                f"{path}: padding leaves no content width", block_id=path,
                needed=padding.left + padding.right, available=cell_width,
            )
        align = cell.align or ("right" if cell.colspan == 1 and placed.col in self.numeric_columns else "left")
        block = Paragraph(cell.content, style=cell.style, align=align, block_id=path) if isinstance(cell.content, str) else cell.content
        content = measure_child(block, context, available, path, own_block_id=True,
                                type_errors=True, hint=_CONTENT_HINT)
        required_height = content.height + (padding.top + padding.bottom)
        required_rows = context.rows_for(required_height)
        return _MeasuredCell(placed, path, padding, align, content, {
            "child_reserved_height_pt": content.height,
            "required_height_pt": required_height,
            "required_rows": required_rows,
            "outer_rounding_added_pt": required_rows * context.profile.grid.pitch_y - required_height,
            "child_rounding_then_outer_padding": bool(padding.top + padding.bottom) and any(
                part.metadata.get("height_rounding") == "single" for part in content.parts),
        })

    def _allocate_rows(self, cells: tuple[_MeasuredCell, ...], pitch: float):
        """Resolve every source row's grid height and record how it was reached."""
        automatic = self.row_heights is None
        row_heights = [1] * len(self.rows) if automatic else list(self.row_heights)
        allocations = [{"row": index, "specified_rows": None if automatic else height,
                        "controlling_cell_ids": [], "rowspan_added_rows": 0}
                       for index, height in enumerate(row_heights)]
        if automatic:
            for cell in cells:
                if cell.placed.cell.rowspan != 1:
                    continue
                row, required = cell.placed.row, cell.requirement["required_rows"]
                previous = row_heights[row]
                row_heights[row] = max(previous, required)
                if required >= previous:
                    controllers = allocations[row]["controlling_cell_ids"]
                    if required > previous:
                        controllers.clear()
                    controllers.append(cell.path)
        order = sorted(cells, key=lambda item: (item.placed.cell.rowspan, item.placed.row, item.placed.col))
        for cell in order:
            placed = cell.placed
            stop = placed.row + placed.cell.rowspan
            if not automatic:
                needed = cell.requirement["required_height_pt"]
                available = sum(row_heights[placed.row:stop]) * pitch
                if needed > available + TOLERANCE:
                    raise LayoutOverflowError(
                        f"{cell.path}: content and padding require {needed} pt "
                        f"but row_heights provide {available} pt (shortage {needed - available} pt)",
                        block_id=cell.path, needed=needed, available=available,
                    )
            elif placed.cell.rowspan > 1:
                required = cell.requirement["required_rows"]
                deficit = required - sum(row_heights[placed.row:stop])
                if deficit > 0:
                    row_heights[stop - 1] += deficit
                    allocations[stop - 1]["rowspan_added_rows"] += deficit
                    allocations[stop - 1]["controlling_cell_ids"].append(cell.path)
        for allocation, height in zip(allocations, row_heights, strict=True):
            allocation["allocated_rows"] = height
            allocation["allocated_height_pt"] = height * pitch
        return row_heights, allocations

    def _row_groups(self) -> list[tuple[int, int]]:
        """Return the header and body intervals without cutting a rowspan."""
        crossed = [False] * (len(self.rows) + 1)
        for placed in self._cells:
            for boundary in range(placed.row + 1, placed.row + placed.cell.rowspan):
                crossed[boundary] = True
        groups = []
        if self.header_rows:
            groups.append((0, self.header_rows))
        start = self.header_rows
        for stop in range(start + 1, len(self.rows) + 1):
            if not crossed[stop]:
                groups.append((start, stop))
                start = stop
        return groups

    def _path(self, placed):
        return f"{self.block_id or 'Table'}.rows[{placed.row}].cells[{placed.col}]"

    def _cell_width(self, placed, pitch_x):
        # Subtracting distant column edges makes equal spans position-dependent.
        return sum(self.columns[placed.col:placed.col + placed.cell.colspan]) * pitch_x

    def _make_part(self, context, start, stop, geometry: _Geometry,
                   under: tuple[float, ...] | None) -> LayoutPart:
        """Draw and check one row group, then describe it for diagnostics.

        ``under`` gives, per column, how far a repeated header's lower line
        reaches into this group when the header lies directly above it.
        """
        width, height = geometry.x(len(self.columns)), geometry.y(stop, start)
        commands, records = [], []
        table = Scope(Kind.TABLE, data={"block_id": self.block_id})
        for row in range(start, stop):
            for cell in geometry.by_row[row]:
                box = self._cell_box(cell, geometry, start, under)
                self._check_strokes(cell, box)
                content_x, content_y = self._content_origin(cell, box)
                translated = cell.content.translated(content_x, content_y)
                self._check_clearance(context, cell, box, translated, width, height)
                commands.extend(within(translated, table, self._cell_scope(cell)))
                records.append(self._cell_record(cell, box, content_x, content_y))
        edges = _Edges(self, geometry, start, stop, width, height, table)
        commands.extend(edges.always)
        return LayoutPart(geometry.row_starts[stop] - geometry.row_starts[start], tuple(commands), {
            "columns_pt": tuple(columns * geometry.pitch_x for columns in self.columns),
            "source_rows": tuple(range(start, stop)),
            "row_heights": tuple(geometry.row_heights[start:stop]), "cells": records,
            "height_mode": "automatic" if self.row_heights is None else "explicit",
            "row_allocations": list(geometry.allocations[start:stop]),
        }, opening=tuple(edges.opening), continuing=tuple(edges.continuing),
           joining=tuple(edges.joining), closing=tuple(edges.closing))

    @staticmethod
    def _cell_scope(cell: _MeasuredCell) -> Scope:
        """The cell a content command lies in, with its span and alignment."""
        placed = cell.placed
        return Scope(Kind.TABLE_CELL, data={
            "cell_id": cell.path, "row": placed.row, "col": placed.col,
            "rowspan": placed.cell.rowspan, "colspan": placed.cell.colspan,
            "align": cell.align, "valign": placed.cell.valign})

    def _cell_edges(self, placed: _PlacedCell) -> dict[str, list[BorderStyle | None]]:
        """Return the style of every grid edge around one placed cell."""
        rows = range(placed.row, placed.row + placed.cell.rowspan)
        columns = range(placed.col, placed.col + placed.cell.colspan)
        return {
            "top": [self._horizontal[rows.start][column] for column in columns],
            "bottom": [self._horizontal[rows.stop][column] for column in columns],
            "left": [self._vertical[row][columns.start] for row in rows],
            "right": [self._vertical[row][columns.stop] for row in rows],
        }

    def _cell_box(self, cell: _MeasuredCell, geometry: _Geometry, start: int,
                  under: tuple[float, ...] | None = None) -> _CellBox:
        placed = cell.placed
        columns, rows = placed.cell.colspan, placed.cell.rowspan
        edges = self._cell_edges(placed)
        thickness = {side: max((style.thickness for style in styles if style is not None), default=0)
                     for side, styles in edges.items()}
        if under is not None and placed.row == start:
            thickness["top"] = max(thickness["top"], *under[placed.col:placed.col + columns])
        return _CellBox(
            geometry.x(placed.col), geometry.x(placed.col + columns),
            geometry.y(placed.row, start), geometry.y(placed.row + rows, start),
            self._cell_width(placed, geometry.pitch_x),
            (thickness["left"], thickness["right"], thickness["top"], thickness["bottom"]),
        )

    def _check_strokes(self, cell: _MeasuredCell, box: _CellBox) -> None:
        available = min(box.width, box.height)
        # Each line's conservative envelope expands at its endpoints, too. A
        # surviving edge of a small cell must fit before it is merged with
        # neighbors; spans may leave that edge isolated.
        for stroke in box.strokes:
            if stroke and stroke >= available:
                raise LayoutOverflowError(
                    f"{cell.path}: border thickness exceeds cell dimensions",
                    block_id=cell.path, needed=stroke, available=available,
                )

    @staticmethod
    def _content_origin(cell: _MeasuredCell, box: _CellBox) -> tuple[float, float]:
        padding, content = cell.padding, cell.content
        return (
            box.x0 + padding.left + (box.width - (padding.left + padding.right) - content.width)
            * {"left": 0, "center": 0.5, "right": 1}[cell.align],
            box.y0 + padding.top + (box.height - (padding.top + padding.bottom) - content.height)
            * {"top": 0, "middle": 0.5, "bottom": 1}[cell.placed.cell.valign],
        )

    @staticmethod
    def _inner_edges(box: _CellBox, width: float, height: float) -> tuple[float, float, float, float]:
        """Return the cell's content boundaries inside its own strokes.

        A line on the part's edge may lie wholly inside the part (the frame,
        or a row-group boundary drawn at a page break), so content keeps clear
        of its whole thickness there; elsewhere a line is centred on its edge.
        """
        left_width, right_width, top_width, bottom_width = box.strokes
        return (
            box.x0 + (left_width if box.x0 == 0 else left_width / 2),
            box.x1 - (right_width if box.x1 == width else right_width / 2),
            box.y0 + (top_width if box.y0 == 0 else top_width / 2),
            box.y1 - (bottom_width if box.y1 == height else bottom_width / 2),
        )

    def _check_clearance(self, context, cell: _MeasuredCell, box: _CellBox, commands,
                         width: float, height: float) -> None:
        left, right, top, bottom = self._inner_edges(box, width, height)
        left_width, right_width, top_width, bottom_width = box.strokes
        if left >= right or top >= bottom:
            raise LayoutOverflowError(
                f"{cell.path}: opposing rules consume the cell frame", block_id=cell.path,
                needed=(left - box.x0) + (box.x1 - right) if left >= right else (top - box.y0) + (box.y1 - bottom),
                available=box.width if left >= right else box.height,
            )
        for command in commands:
            bounds = command_bounds(command, context.fonts)
            crowded_x = ((bounds.x <= left if left_width else bounds.x < box.x0 - TOLERANCE)
                         or (bounds.right >= right if right_width else bounds.right > box.x1 + TOLERANCE))
            crowded_y = ((bounds.y <= top if top_width else bounds.y < box.y0 - TOLERANCE)
                         or (bounds.bottom >= bottom if bottom_width else bounds.bottom > box.y1 + TOLERANCE))
            if crowded_x or crowded_y:
                # Report the axis that is actually short, so the measurement a
                # caller changes is the one the numbers describe.
                axis = "horizontal" if crowded_x else "vertical"
                raise LayoutOverflowError(
                    f"{cell.path}: content lacks clearance from border strokes ({axis})",
                    block_id=cell.path,
                    needed=bounds.width if crowded_x else bounds.height,
                    available=max(0, right - left) if crowded_x else max(0, bottom - top),
                )

    def _cell_record(self, cell: _MeasuredCell, box: _CellBox,
                     content_x: float, content_y: float) -> dict:
        placed, padding = cell.placed, cell.padding
        return {
            "row": placed.row, "col": placed.col,
            "rowspan": placed.cell.rowspan, "colspan": placed.cell.colspan,
            "frame": {"x_pt": box.x0, "y_pt": box.y0, "width": box.width, "height": box.height},
            "cell_id": cell.path,
            "align": cell.align, "valign": placed.cell.valign,
            "borders": {side: [None if style is None else style.value for style in styles]
                        for side, styles in self._cell_edges(placed).items()},
            "padding_pt": {edge: getattr(padding, edge) for edge in ("top", "right", "bottom", "left")},
            "height_allocation": {**cell.requirement,
                                  "allocated_height_pt": box.height,
                                  "available_content_height_pt": box.height - padding.top - padding.bottom},
            "content": block_trace(cell.content, content_x, content_y),
        }


class _Edges:
    """The border lines of one row group, sorted by when they are drawn.

    Every edge run is one call to ``BorderStyle.lines`` (one line, or two for
    ``double``) for one style along one boundary, and each line is tagged
    with its boundary, its columns or rows (absolute, stop exclusive), its
    style, its stroke number and the list it is drawn from (``drawn``).
    ``always`` holds the frame and inner lines. A group below another one
    draws its top only in ``opening`` (at a page top). A group above another
    one draws its bottom centred on the boundary in ``joining``, or inside
    itself in ``closing`` when a page break follows it; its vertical lines
    reaching that boundary end on it, or half a stroke above it. A group
    below another one starts its vertical lines half a stroke down, and in
    ``continuing`` bridges that half stroke up to the boundary, so the lines
    meet whatever group comes above it.
    """

    def __init__(self, table: Table, geometry: _Geometry, start: int, stop: int,
                 width: float, height: float, scope: Scope) -> None:
        self.always: list[Line] = []
        self.opening: list[Line] = []
        self.continuing: list[Line] = []
        self.joining: list[Line] = []
        self.closing: list[Line] = []
        self.color = table.border_color
        self.width, self.height = width, height
        self.path = (scope,)
        seam_above, seam_below = start > 0, stop < len(table.rows)
        for boundary in range(start, stop + 1):
            for style, first, stop_column in _runs(table._horizontal[boundary]):
                x0, x1 = geometry.x(first), geometry.x(stop_column)
                edge = (style, x0, x1, boundary, first, stop_column)
                if boundary == start:
                    self._horizontal("opening" if seam_above else "always", *edge, style.thickness / 2)
                elif boundary == stop and seam_below:
                    self._horizontal("joining", *edge, height)
                    self._horizontal("closing", *edge, height - style.thickness / 2)
                elif boundary == stop:
                    self._horizontal("always", *edge, height - style.thickness / 2)
                else:
                    self._horizontal("always", *edge, geometry.y(boundary, start))
        columns = len(table.columns)
        for boundary in range(columns + 1):
            for style, first, stop_row in _runs(tuple(table._vertical[row][boundary] for row in range(start, stop))):
                x = (style.thickness / 2 if boundary == 0 else
                     width - style.thickness / 2 if boundary == columns else geometry.x(boundary))
                half = style.stroke_width / 2
                y0 = max(half, geometry.y(start + first, start))
                y1 = geometry.y(start + stop_row, start)
                edge = (style, x, boundary, start + first, start + stop_row)
                if first == 0 and seam_above:
                    self._vertical("continuing", *edge, 0.0, y0)
                if start + stop_row < stop:
                    self._vertical("always", *edge, y0, min(height - half, y1))
                elif not seam_below:
                    self._vertical("always", *edge, y0, height - half)
                else:
                    self._vertical("joining", *edge, y0, height)
                    self._vertical("closing", *edge, y0, height - half)

    def _horizontal(self, drawn: str, style: BorderStyle, x0: float, x1: float,
                    boundary: int, first: int, stop: int, y: float) -> None:
        half = style.stroke_width / 2
        getattr(self, drawn).extend(_border_lines(
            style, max(half, x0), y, min(self.width - half, x1), y, self.color, Role.TABLE_BORDER, self.path,
            orientation="horizontal", boundary=boundary, first=first, stop=stop, drawn=drawn))

    def _vertical(self, drawn: str, style: BorderStyle, x: float,
                  boundary: int, first: int, stop: int, y0: float, y1: float) -> None:
        getattr(self, drawn).extend(_border_lines(
            style, x, y0, x, y1, self.color, Role.TABLE_BORDER, self.path,
            orientation="vertical", boundary=boundary, first=first, stop=stop, drawn=drawn))


def _runs(styles: tuple[BorderStyle | None, ...]):
    """Yield (style, first, stop) for each run of equal, drawn styles; stop is exclusive."""
    first = 0
    for index in range(1, len(styles) + 1):
        if index == len(styles) or styles[index] != styles[first]:
            if styles[first] is not None:
                yield styles[first], first, index
            first = index
