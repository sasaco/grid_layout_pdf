"""Grid-sized tables with atomic merged cells and repeatable headers."""

from dataclasses import KW_ONLY, dataclass, field

from .blocks import Paragraph
from .bounds import command_bounds
from .errors import FontError, LayoutOverflowError
from .layout import Block, LayoutContext, LayoutPart, MeasuredBlock, measure_block
from .scene import Line
from .styles import TextStyle, _finite_number


# Match the absolute roundoff allowance at the shared measurement boundary.
_ROUNDING_TOLERANCE = 1e-7


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _rule_widths(values, count, name):
    if values is None:
        return None
    try:
        widths = tuple(_finite_number(value, name) for value in values)
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence of rule widths or None") from exc
    if len(widths) != count or any(width < 0 for width in widths):
        raise ValueError(f"{name} must contain {count} finite nonnegative rule widths")
    return widths


@dataclass(frozen=True, slots=True)
class Cell:
    content: str | Block = ""
    _: KW_ONLY
    colspan: int = 1
    rowspan: int = 1
    align: str | None = None
    valign: str = "middle"
    padding: float = 3.0
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
        padding = _finite_number(self.padding, "padding")
        if padding < 0:
            raise ValueError("padding must be nonnegative")
        object.__setattr__(self, "padding", padding)
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
class Table:
    """A table with independently contained merged row groups and headers.

    None rules use border_width on every edge, preserving closed fragments.
    Explicit horizontal_rules/vertical_rules address original row/column
    boundaries; zero omits an edge. Spans suppress interior edges. Widths are
    per stroke: adjacent groups draw their shared edge independently inside
    their own bounds, so a shared seam can appear twice as thick. Splitting
    retains source boundary indices and does not invent fragment frames.

    row_heights optionally fixes each source row's height in local grid rows.
    Content and padding must fit those exact allocations, including rowspans;
    insufficient space raises instead of expanding rows or shrinking content.
    None preserves automatic row allocation.
    """

    columns: tuple[int, ...]
    rows: tuple[tuple[Cell, ...], ...]
    _: KW_ONLY
    header_rows: int = 0
    row_heights: tuple[int, ...] | None = None
    numeric_columns: tuple[int, ...] = ()
    border_width: float = 0.5
    border_color: tuple[float, float, float] = (0, 0, 0)
    horizontal_rules: tuple[float, ...] | None = None
    vertical_rules: tuple[float, ...] | None = None
    block_id: str = ""
    _cells: tuple[_PlacedCell, ...] = field(init=False, repr=False)

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
        width = _finite_number(self.border_width, "border_width")
        if width <= 0:
            raise ValueError("border_width must be positive")
        object.__setattr__(self, "border_width", width)
        try:
            color = tuple(_finite_number(c, "border_color") for c in self.border_color)
        except TypeError as exc:
            raise ValueError("border_color must have three components") from exc
        if len(color) != 3 or any(c < 0 or c > 1 for c in color):
            raise ValueError("border_color must have three components between 0 and 1")
        object.__setattr__(self, "border_color", color)
        object.__setattr__(self, "horizontal_rules", _rule_widths(self.horizontal_rules, len(rows) + 1, "horizontal_rules"))
        object.__setattr__(self, "vertical_rules", _rule_widths(self.vertical_rules, len(columns) + 1, "vertical_rules"))
        if not isinstance(self.block_id, str):
            raise ValueError("block_id must be a string")
        object.__setattr__(self, "_cells", self._place_cells())

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
        if not isinstance(context, LayoutContext):
            raise ValueError("context must be a LayoutContext")
        available_width = _finite_number(available_width, "available_width")
        if available_width <= 0:
            raise ValueError("available_width must be positive")
        width = sum(self.columns) * context.profile.grid.pitch_x
        if width > available_width + _ROUNDING_TOLERANCE:
            raise LayoutOverflowError(
                f"{self.block_id or 'Table'}: table width {width} exceeds {available_width}",
                block_id=self.block_id or "Table", needed=width, available=available_width,
            )
        if not self.rows:
            return MeasuredBlock(width, context.profile.grid.pitch_y, block_id=self.block_id)
        pitch = context.profile.grid.pitch_y
        column_edges = [sum(self.columns[:index]) * context.profile.grid.pitch_x
                        for index in range(len(self.columns) + 1)]
        measured = []
        row_heights = [1] * len(self.rows) if self.row_heights is None else list(self.row_heights)
        for placed in self._cells:
            cell = placed.cell
            content, align = self._measure_cell(context, placed)
            measured.append((placed, content, align))
            if self.row_heights is None and cell.rowspan == 1:
                row_heights[placed.row] = max(row_heights[placed.row], context.rows_for(content.height + 2 * cell.padding))
        for placed, content, _ in sorted(measured, key=lambda item: (item[0].cell.rowspan, item[0].row, item[0].col)):
            cell = placed.cell
            stop = placed.row + cell.rowspan
            if self.row_heights is not None:
                needed = content.height + 2 * cell.padding
                available = sum(row_heights[placed.row:stop]) * pitch
                if needed > available + _ROUNDING_TOLERANCE:
                    raise LayoutOverflowError(
                        f"{self._path(placed)}: content and padding require {needed} pt "
                        f"but row_heights provide {available} pt",
                        block_id=self._path(placed), needed=needed, available=available,
                    )
            elif cell.rowspan > 1:
                required = context.rows_for(content.height + 2 * cell.padding)
                deficit = required - sum(row_heights[placed.row:stop])
                if deficit > 0:
                    row_heights[stop - 1] += deficit
        parts = tuple(self._make_part(context, start, stop, row_heights, column_edges, measured)
                      for start, stop in self._row_groups())
        if self.header_rows and self.header_rows < len(self.rows):
            prefix, body = parts[:1], parts[1:]
        else:
            prefix, body = (), parts
        return MeasuredBlock(width, pitch, body, prefix=prefix, block_id=self.block_id)

    def _measure_cell(self, context: LayoutContext, placed: _PlacedCell) -> tuple[MeasuredBlock, str]:
        cell = placed.cell
        cell_width = self._cell_width(placed, context.profile.grid.pitch_x)
        path = self._path(placed)
        available = cell_width - 2 * cell.padding
        if available <= 0:
            raise LayoutOverflowError(
                f"{path}: padding leaves no content width", block_id=path,
                needed=2 * cell.padding, available=cell_width,
            )
        align = cell.align or ("right" if cell.colspan == 1 and placed.col in self.numeric_columns else "left")
        block = Paragraph(cell.content, style=cell.style, align=align, block_id=path) if isinstance(cell.content, str) else cell.content
        try:
            content = measure_block(block, context, available)
        except FontError as exc:
            raise FontError(f"{path}: {exc}") from exc
        except LayoutOverflowError as exc:
            raise LayoutOverflowError(
                f"{path}: {exc}", block_id=path, needed=exc.needed, available=exc.available,
            ) from exc
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"{path}: {exc}; content requires Block.measure(context, width); mathematical nodes require MathBlock"
            ) from exc
        return content, align

    def _row_groups(self) -> list[tuple[int, int]]:
        """Return the header and body intervals without cutting a rowspan."""
        groups = []
        if self.header_rows:
            groups.append((0, self.header_rows))
        start = self.header_rows
        for stop in range(start + 1, len(self.rows) + 1):
            if not any(placed.row < stop < placed.row + placed.cell.rowspan for placed in self._cells):
                groups.append((start, stop))
                start = stop
        return groups

    def _path(self, placed):
        return f"{self.block_id or 'Table'}.rows[{placed.row}].cells[{placed.col}]"

    def _cell_width(self, placed, pitch_x):
        # Subtracting distant column edges makes equal spans position-dependent.
        return sum(self.columns[placed.col:placed.col + placed.cell.colspan]) * pitch_x

    def _make_part(self, context, start, stop, row_heights, column_edges, measured):
        pitch = context.profile.grid.pitch_y
        row_edges = {r: sum(row_heights[start:r]) * pitch for r in range(start, stop + 1)}
        width, height = column_edges[-1], row_edges[stop]
        uniform = self.horizontal_rules is None and self.vertical_rules is None
        if uniform and self.border_width >= min(width, height):
            raise LayoutOverflowError(
                f"{self.block_id or 'Table'}: border_width exceeds part dimensions",
                block_id=self.block_id or "Table", needed=self.border_width, available=min(width, height),
            )
        horizontal, vertical = {}, {}
        commands, cells = [], []
        for placed, content, align in measured:
            if not start <= placed.row < stop:
                continue
            cell = placed.cell
            x0, x1 = column_edges[placed.col], column_edges[placed.col + cell.colspan]
            cell_width = self._cell_width(placed, context.profile.grid.pitch_x)
            y0, y1 = row_edges[placed.row], row_edges[placed.row + cell.rowspan]
            left_width = self.border_width if self.vertical_rules is None else self.vertical_rules[placed.col]
            right_width = self.border_width if self.vertical_rules is None else self.vertical_rules[placed.col + cell.colspan]
            top_width = self.border_width if self.horizontal_rules is None else self.horizontal_rules[placed.row]
            bottom_width = self.border_width if self.horizontal_rules is None else self.horizontal_rules[placed.row + cell.rowspan]
            if uniform and self.border_width >= min(cell_width, y1 - y0):
                raise LayoutOverflowError(
                    f"{self._path(placed)}: border_width exceeds cell dimensions",
                    block_id=self._path(placed), needed=self.border_width,
                    available=min(cell_width, y1 - y0),
                )
            if not uniform:
                # Each line's conservative envelope expands at its endpoints,
                # too. A surviving edge of a small cell must fit before it is
                # merged with neighbors; spans may leave that edge isolated.
                available = min(cell_width, y1 - y0)
                for stroke in (left_width, right_width, top_width, bottom_width):
                    if stroke and stroke >= available:
                        raise LayoutOverflowError(
                            f"{self._path(placed)}: rule width exceeds cell or part dimensions",
                            block_id=self._path(placed), needed=stroke, available=available,
                        )
            content_x = x0 + cell.padding + (cell_width - 2 * cell.padding - content.width) * {"left": 0, "center": 0.5, "right": 1}[align]
            content_y = y0 + cell.padding + (y1 - y0 - 2 * cell.padding - content.height) * {"top": 0, "middle": 0.5, "bottom": 1}[cell.valign]
            translated = content.translated(content_x, content_y)
            left = x0 + (left_width if x0 == 0 else left_width / 2)
            right = x1 - (right_width if x1 == width else right_width / 2)
            top = y0 + (top_width if y0 == 0 else top_width / 2)
            bottom = y1 - (bottom_width if y1 == height else bottom_width / 2)
            if not uniform and (left >= right or top >= bottom):
                raise LayoutOverflowError(
                    f"{self._path(placed)}: opposing rules consume the cell frame",
                    block_id=self._path(placed),
                    needed=(left - x0) + (x1 - right) if left >= right else (top - y0) + (y1 - bottom),
                    available=cell_width if left >= right else y1 - y0,
                )
            for command in translated:
                bounds = command_bounds(command, context.fonts)
                if ((bounds.x <= left if left_width else bounds.x < x0 - _ROUNDING_TOLERANCE)
                        or (bounds.right >= right if right_width else bounds.right > x1 + _ROUNDING_TOLERANCE)
                        or (bounds.y <= top if top_width else bounds.y < y0 - _ROUNDING_TOLERANCE)
                        or (bounds.bottom >= bottom if bottom_width else bounds.bottom > y1 + _ROUNDING_TOLERANCE)):
                    raise LayoutOverflowError(
                        f"{self._path(placed)}: content lacks clearance from border strokes",
                        block_id=self._path(placed), needed=bounds.width, available=max(0, right - left),
                    )
            commands.extend(translated)
            cells.append({
                "row": placed.row, "col": placed.col, "rowspan": cell.rowspan, "colspan": cell.colspan,
                "frame": {"x_pt": x0, "y_pt": y0, "width": cell_width, "height": y1 - y0},
                "content": _content_trace(content, content_x, content_y),
            })
            for edge, stroke in ((y0, top_width), (y1, bottom_width)):
                if stroke:
                    half = stroke / 2
                    y = max(half, min(height - half, edge))
                    horizontal.setdefault((y, stroke), []).append((max(half, x0), min(width - half, x1)))
            for edge, stroke in ((x0, left_width), (x1, right_width)):
                if stroke:
                    half = stroke / 2
                    x = max(half, min(width - half, edge))
                    vertical.setdefault((x, stroke), []).append((max(half, y0), min(height - half, y1)))
        for (y, stroke), intervals in sorted(horizontal.items()):
            commands.extend(Line(a, y, b, y, stroke, self.border_color) for a, b in _merged(intervals))
        for (x, stroke), intervals in sorted(vertical.items()):
            commands.extend(Line(x, a, x, b, stroke, self.border_color) for a, b in _merged(intervals))
        return LayoutPart(sum(row_heights[start:stop]), tuple(commands), {
            "columns_pt": tuple(columns * context.profile.grid.pitch_x for columns in self.columns),
            "source_rows": tuple(range(start, stop)), "row_heights": tuple(row_heights[start:stop]), "cells": cells,
        })


def _merged(intervals):
    """Merge collinear shared edges without painting any segment twice."""
    result = []
    for start, stop in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], stop))
        else:
            result.append((start, stop))
    return result


def _content_trace(content, x_pt, y_pt):
    trace = {"block_id": content.block_id, "x_pt": x_pt, "y_pt": y_pt,
             "width": content.width, "rows": content.rows, "row_pitch": content.row_pitch}
    row = 0
    for name, parts in (("prefix", content.prefix), ("parts", content.parts)):
        descriptors = []
        for part in parts:
            descriptors.append({"row": row, "rows": part.rows, "metadata": part.metadata})
            row += part.rows
        trace[name] = descriptors
    return trace
