"""Semantic equation wrapping without resizing or splitting math atoms."""

from dataclasses import KW_ONLY, dataclass
import math
from typing import NoReturn

from .blocks import Paragraph
from .errors import FontError, LayoutOverflowError
from .fonts import FontRegistry
from .layout import LayoutContext, LayoutPart, MeasuredBlock
from .math import BreakHint, Literal, MathBox, MathNode, Operator, Row, as_math
from .styles import TextStyle, _finite_number


@dataclass(frozen=True, slots=True)
class EquationAnchors:
    """Integer column boundaries measured from the block's left edge."""

    first_equal: int
    second_equal: int | None = None
    result_right: int | None = None
    unit_start: int | None = None

    def __post_init__(self) -> None:
        previous = -1
        for name in ("first_equal", "second_equal", "result_right", "unit_start"):
            value = getattr(self, name)
            if value is None and name != "first_equal":
                continue
            _column(value, name)
            if value <= previous:
                raise ValueError("anchor columns must be in strictly increasing order")
            previous = value


@dataclass(frozen=True, slots=True)
class Equation:
    """One labeled equation with optional displayed result and unit.

    Strings remain literal display data. Equation style overrides its group's
    style; no arithmetic, parsing or numeric rounding is performed.
    """

    lhs: MathNode | str
    rhs: MathNode | str
    _: KW_ONLY
    label: str = ""
    result: MathNode | str | None = None
    unit: MathNode | str | None = None
    relation: str = "="
    result_relation: str = "="
    style: TextStyle | None = None
    block_id: str = ""

    def __post_init__(self) -> None:
        for name in ("lhs", "rhs", "result", "unit"):
            value = getattr(self, name)
            if value is not None or name in ("lhs", "rhs"):
                object.__setattr__(self, name, as_math(value))
        if self.unit is not None and self.result is None:
            raise ValueError("unit requires a result; include RHS units in a Row")
        if not isinstance(self.label, str) or "\t" in self.label:
            raise ValueError("label must be text without tabs")
        for name in ("relation", "result_relation"):
            text = getattr(self, name)
            if not isinstance(text, str) or not text or any(c in text for c in "\n\r\t"):
                raise ValueError(f"{name} must be nonempty single-line text")
        _style_and_id(self.style, self.block_id)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        return EquationGroup(self, block_id=self.block_id).measure(context, available_width)


@dataclass(frozen=True, slots=True, init=False)
class EquationGroup:
    """Share grid-column anchors across immutable equations and display lines."""

    equations: tuple[Equation, ...]
    anchors: EquationAnchors | None
    label_columns: int | None
    gap: float
    style: TextStyle | None
    block_id: str

    def __init__(self, *equations: Equation, anchors: EquationAnchors | None = None,
                 label_columns: int | None = None, gap: float = 4.0,
                 style: TextStyle | None = None, block_id: str = "") -> None:
        if any(not isinstance(equation, Equation) for equation in equations):
            raise ValueError("equations must contain only Equation objects")
        if anchors is not None and not isinstance(anchors, EquationAnchors):
            raise ValueError("anchors must be EquationAnchors or None")
        if label_columns is not None:
            _column(label_columns, "label_columns")
        gap = _finite_number(gap, "gap")
        if gap < 0:
            raise ValueError("gap must be nonnegative")
        _style_and_id(style, block_id)
        for name, value in (("equations", tuple(equations)), ("anchors", anchors),
                            ("label_columns", label_columns), ("gap", gap),
                            ("style", style), ("block_id", block_id)):
            object.__setattr__(self, name, value)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = _block_width(context, available_width)
        if not self.equations:
            return MeasuredBlock(available_width, context.profile.grid.pitch_y,
                                 prefer_keep=True, block_id=self.block_id)
        measured = tuple(_measure_equation(equation, self, context, index)
                         for index, equation in enumerate(self.equations))
        pitch = context.profile.grid.pitch_x
        label_width = _label_columns(self, measured, context) * pitch
        label_reserve = label_width + self.gap if label_width else 0
        anchors = self.anchors or _automatic_anchors(measured, pitch, available_width, self.gap, label_reserve)
        if any(item.result is not None for item in measured):
            if anchors.second_equal is None or anchors.result_right is None:
                raise ValueError("results require second_equal and result_right anchors")
        if any(item.unit is not None for item in measured) and anchors.unit_start is None:
            raise ValueError("units require a unit_start anchor")
        points = _anchor_points(anchors, pitch, available_width, self.block_id or "EquationGroup")
        first_left = max(item.first.left for item in measured)
        first_right = max(item.first.right for item in measured)
        second_left = max((item.second.left for item in measured if item.second), default=0)
        second_right = max((item.second.right for item in measured if item.second), default=0)
        rhs_start = _ceil_column(points["first_equal"] + first_right + self.gap, pitch) * pitch
        parts = []
        for index, item in enumerate(measured):
            first = points["first_equal"]
            _require_width(label_reserve + item.lhs.width + first_left + self.gap, first, item.path + ".lhs")
            _require_width(item.first.right, available_width - first, item.path + ".relation")
            leading = [(item.lhs, first - first_left - self.gap - item.lhs.width),
                       (item.first.box, first - item.first.left)]
            trailing = []
            rhs_end = available_width
            if item.result is not None:
                second, result_right = points["second_equal"], points["result_right"]
                _require_width(item.second.left, second, item.path + ".result_relation")
                _require_width(item.result.width + second_right + self.gap,
                               result_right - second, item.path + ".result")
                rhs_end = _floor_column(second - second_left - self.gap, pitch) * pitch
                trailing.extend(((item.second.box, second - item.second.left),
                                 (item.result, result_right - item.result.width)))
            if item.unit is not None:
                unit_start = points["unit_start"]
                _require_width(self.gap, unit_start - points["result_right"], item.path + ".unit")
                _require_width(item.unit.width, available_width - unit_start, item.path + ".unit")
                trailing.append((item.unit, unit_start))
            rhs_lines, separate_result = _wrap_rhs(item, context, rhs_end - rhs_start,
                                                   available_width - rhs_start)
            if not rhs_lines:
                rhs_lines = (MathBox(0, 0, 0, (), item.style.size * .25),)
            label = Paragraph(item.equation.label, style=item.style, block_id=item.path + ".label",
                              min_first=1, min_last=1).measure(context, label_width) if item.equation.label else None
            common_metadata = {"equation_index": index, "anchors_pt": points,
                               "rhs_start_pt": rhs_start, "label_width_pt": label_width}
            for line_index, rhs in enumerate(rhs_lines):
                positioned = (leading if line_index == 0 else []) + [(rhs, rhs_start)]
                if line_index == len(rhs_lines) - 1 and not separate_result:
                    positioned += trailing
                parts.append(_equation_part(context, item.style, positioned, {
                    **common_metadata, "line_index": line_index,
                    "continuation": line_index > 0, "result_line": False,
                }, label if line_index == 0 else None))
            if separate_result:
                parts.append(_equation_part(context, item.style, trailing, {
                    **common_metadata, "line_index": len(rhs_lines),
                    "continuation": False, "result_line": True,
                }))
        return MeasuredBlock(available_width, context.profile.grid.pitch_y, tuple(parts),
                             prefer_keep=True, block_id=self.block_id)


@dataclass(frozen=True, slots=True)
class _Relation:
    box: MathBox
    left: float
    right: float


@dataclass(frozen=True, slots=True)
class _EquationMeasure:
    equation: Equation
    style: TextStyle
    path: str
    lhs: MathBox
    first: _Relation
    result: MathBox | None
    second: _Relation | None
    unit: MathBox | None


def _wrap_rhs(item: _EquationMeasure, context: LayoutContext, normal_width: float,
               full_width: float) -> tuple[tuple[MathBox, ...], bool]:
    if normal_width > 0:
        try:
            return wrap_math(item.equation.rhs, context.fonts, item.style,
                             normal_width, block_id=item.path), False
        except LayoutOverflowError:
            if item.result is None:
                raise
    if full_width <= 0:
        return _wrap_without_rhs_space(item, context, full_width), False
    return wrap_math(item.equation.rhs, context.fonts, item.style,
                     full_width, block_id=item.path), item.result is not None


def _wrap_without_rhs_space(item: _EquationMeasure, context: LayoutContext,
                            full_width: float) -> tuple[MathBox, ...]:
    rhs = item.equation.rhs
    atoms = enumerate(rhs.items) if isinstance(rhs, Row) else ((None, rhs),)
    for index, atom in atoms:
        if isinstance(atom, BreakHint):
            continue
        path = item.path + ".rhs" + (f"[{index}]" if index is not None else "")
        box = _measure(atom, context.fonts, item.style, path)
        if box.width:
            _overflow(box.width, 0, path)
    # Zero-width atoms can still have gaps or forced display lines. Run the
    # normal parser so hints retain their validation and ordering semantics.
    try:
        lines = wrap_math(rhs, context.fonts, item.style,
                          context.profile.body_rect.width, block_id=item.path)
    except LayoutOverflowError as exc:
        _overflow(exc.needed, 0, exc.block_id)
    needed = max(-full_width, max((line.width for line in lines), default=0))
    if needed:
        _overflow(needed, 0, item.path + ".rhs")
    return lines


def _relation(text: str, context: LayoutContext, style: TextStyle, path: str) -> _Relation:
    box = _measure(Literal(text), context.fonts, style, path)
    metrics = context.fonts.measure(context.fonts.normalize_text(text), style)
    return _Relation(box, metrics.width / 2 - metrics.bounds.x,
                     metrics.bounds.right - metrics.width / 2)


def _measure_equation(equation: Equation, group: EquationGroup,
                      context: LayoutContext, index: int) -> _EquationMeasure:
    style = equation.style or group.style or context.style.body
    path = equation.block_id or f"{group.block_id or 'EquationGroup'}.equations[{index}]"
    return _EquationMeasure(
        equation, style, path,
        _measure(equation.lhs, context.fonts, style, path + ".lhs"),
        _relation(equation.relation, context, style, path + ".relation"),
        _measure(equation.result, context.fonts, style, path + ".result") if equation.result is not None else None,
        _relation(equation.result_relation, context, style, path + ".result_relation") if equation.result is not None else None,
        _measure(equation.unit, context.fonts, style, path + ".unit") if equation.unit is not None else None,
    )


def _automatic_anchors(items: tuple[_EquationMeasure, ...], pitch: float,
                       width: float, gap: float, label_reserve: float) -> EquationAnchors:
    widest_lhs = max(items, key=lambda item: item.lhs.width)
    first_left = max(item.first.left for item in items)
    first_need = label_reserve + widest_lhs.lhs.width + gap + first_left
    _require_width(first_need, width, widest_lhs.path + ".lhs")
    first = _ceil_column(first_need, pitch)
    _require_width(first * pitch, width, widest_lhs.path + ".lhs")
    with_result = tuple(item for item in items if item.result is not None)
    if not with_result:
        return EquationAnchors(first)
    with_unit = tuple(item for item in items if item.unit is not None)
    unit = None
    if with_unit:
        widest_unit = max(with_unit, key=lambda item: item.unit.width)
        _require_width(widest_unit.unit.width, width, widest_unit.path + ".unit")
        unit = _floor_column(width - widest_unit.unit.width, pitch)
        _require_width(gap, unit * pitch, widest_unit.path + ".unit")
    right = _floor_column(unit * pitch - gap if unit is not None else width, pitch)
    if unit is not None:
        right = min(right, unit - 1)
    widest_result = max(with_result, key=lambda item: item.result.width)
    result_need = widest_result.result.width + gap + max(item.second.right for item in with_result)
    _require_width(result_need, right * pitch, widest_result.path + ".result")
    second = _floor_column(right * pitch - result_need, pitch)
    _require_width((first + 1) * pitch, second * pitch, widest_lhs.path + ".rhs")
    return EquationAnchors(first, second, right, unit)


def _label_columns(group: EquationGroup, items: tuple[_EquationMeasure, ...],
                   context: LayoutContext) -> int:
    labeled = tuple(item for item in items if item.equation.label)
    if group.label_columns is not None:
        if group.label_columns == 0 and labeled:
            raise ValueError("label_columns must be positive when labels are present")
        return group.label_columns
    if not labeled:
        return 0
    pitch = context.profile.grid.pitch_x
    natural = 0.0
    for item in labeled:
        try:
            for line in item.equation.label.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
                metrics = context.fonts.measure(context.fonts.normalize_text(line), item.style)
                natural = max(natural, metrics.bounds.width)
        except FontError as exc:
            raise FontError(f"{item.path}.label: {exc}") from exc
    columns = min(6, max(1, _ceil_column(natural, pitch)))
    if group.anchors is not None:
        room = (group.anchors.first_equal * pitch - max(item.first.left for item in items)
                - max(item.lhs.width for item in items) - 2 * group.gap)
        _require_width(pitch, room, labeled[0].path + ".label")
        columns = min(columns, _floor_column(room, pitch))
    return columns


def _anchor_points(anchors: EquationAnchors, pitch: float, width: float, path: str) -> dict[str, float | None]:
    points = {}
    for name in ("first_equal", "second_equal", "result_right", "unit_start"):
        column = getattr(anchors, name)
        point = column * pitch if column is not None else None
        if point is not None:
            _require_width(point, width, path + ".anchors." + name)
        points[name] = point
    return points


def _ceil_column(value: float, pitch: float) -> int:
    column = math.ceil(value / pitch)
    if (column - 1) * pitch >= value:
        return column - 1
    return column + 1 if column * pitch < value else column


def _floor_column(value: float, pitch: float) -> int:
    column = math.floor(value / pitch)
    if (column + 1) * pitch <= value:
        return column + 1
    return column - 1 if column * pitch > value else column


def _require_width(needed: float, available: float, path: str) -> None:
    if needed > max(0, available):
        _overflow(needed, max(0, available), path)


def _equation_part(context: LayoutContext, style: TextStyle,
                   positioned: list[tuple[MathBox, float]], metadata: dict,
                   label: MeasuredBlock | None = None) -> LayoutPart:
    axis = style.size * .25
    ascent = max((box.ascent - (box.axis - axis) for box, _ in positioned), default=0)
    descent = max((box.descent + (box.axis - axis) for box, _ in positioned), default=0)
    baseline = context.baseline_for(max(0, ascent))
    label_commands = ()
    label_height = 0.0
    if label is not None:
        first_commands = label.parts[0].commands
        label_baseline = (first_commands[0].y if first_commands else
                          context.baseline_for(context.fonts.measure("", style).ascent))
        baseline = max(baseline, label_baseline)
        shift = baseline - label_baseline
        label_commands = label.translated(0, shift)
        label_height = label.height + shift
    commands = tuple(command for box, x in positioned
                     for command in box.translated(x, baseline + box.axis - axis))
    return LayoutPart(max(1, context.rows_for(max(label_height, baseline + max(0, descent)))),
                      (*label_commands, *commands),
                      {**metadata, "baseline_pt": baseline})


@dataclass(frozen=True, slots=True)
class MathBlock:
    """Adapt one indivisible math node to the grid-height block contract."""

    expression: MathNode | str
    style: TextStyle | None = None
    block_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "expression", as_math(self.expression))
        _style_and_id(self.style, self.block_id)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = _block_width(context, available_width)
        style = self.style or context.style.body
        box = _measure(self.expression, context.fonts, style, self.block_id or "MathBlock")
        if box.width > available_width:
            _overflow(box.width, available_width, self.block_id or "MathBlock")
        parts = ()
        if box.commands or box.width or box.height:
            baseline = context.baseline_for(box.ascent)
            parts = (LayoutPart(context.rows_for(baseline + box.descent),
                                box.translated(0, baseline), {"baseline_pt": baseline}),)
        return MeasuredBlock(box.width or available_width, context.profile.grid.pitch_y,
                             parts, keep_together=True, block_id=self.block_id)


def _style_and_id(style: TextStyle | None, block_id: str) -> None:
    if style is not None and not isinstance(style, TextStyle):
        raise ValueError("style must be a TextStyle or None")
    if not isinstance(block_id, str):
        raise ValueError("block_id must be a string")


def _column(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer column")


def _block_width(context: LayoutContext, available_width: float) -> float:
    if not isinstance(context, LayoutContext):
        raise ValueError("context must be a LayoutContext")
    width = _finite_number(available_width, "available_width")
    if width <= 0:
        raise ValueError("available_width must be positive")
    return width


def wrap_math(
    node: MathNode | str,
    fonts: FontRegistry,
    style: TextStyle,
    available_width: float,
    *,
    block_id: str = "",
) -> tuple[MathBox, ...]:
    """Return baseline-relative lines within a finite positive width in pt.

    Only a top-level Row is split. Its hints occupy no space, and each line
    retains its original gap and text size. Forced boundaries end a segment;
    within it, fitting preferred hints outrank relations, additive operators,
    and allowed hints. Ties choose the farthest boundary. Operators stay on the
    following line. A segment that fits is kept whole.

    Empty rows return (). Malformed hints raise ValueError. Atomic or
    unsplittable overflow raises LayoutOverflowError with a source item path;
    missing glyphs retain FontError and their original cause.
    """
    available_width = _finite_number(available_width, "available_width")
    if available_width <= 0:
        raise ValueError("available_width must be positive")
    if not isinstance(block_id, str):
        raise ValueError("block_id must be a string")
    node = as_math(node)
    path = f"{block_id}.rhs" if block_id else "rhs"
    if not isinstance(node, Row):
        box = _measure(node, fonts, style, path)
        if box.width > available_width:
            _overflow(box.width, available_width, path)
        return (box,)

    Row().measure(fonts, style)  # Validate the context even for an empty row.
    atoms, source_indices, candidates, forced_ends = _parse_wrap_row(node)
    boxes = tuple(
        _measure(item, fonts, style, f"{path}[{source_index}]")
        for item, source_index in zip(atoms, source_indices)
    )
    for index, box in enumerate(boxes):
        if box.width > available_width:
            _overflow(box.width, available_width, f"{path}[{source_indices[index]}]")
    gap = style.size * 0.15 if node.gap is None else node.gap
    lines: list[MathBox] = []
    start = 0
    for stop in (*forced_ends, len(boxes)):
        while start < stop:
            width = 0.0
            fitting: list[int] = []
            end = start
            while end < stop:
                if end > start:
                    if end in candidates:
                        fitting.append(end)
                    width += gap
                width += boxes[end].width
                if width > available_width:
                    break
                end += 1
            if end < stop:
                if not fitting:
                    end = next((i for i in range(start + 1, stop) if i in candidates), stop)
                    needed = _width(boxes[start:end], gap)
                    first, last = source_indices[start], source_indices[end - 1] + 1
                    _overflow(needed, available_width, f"{path}[{first}:{last}]")
                end = min(fitting, key=lambda index: (candidates[index], -index))
            lines.append(Row(*atoms[start:end], gap=node.gap).measure(fonts, style))
            start = end
    return tuple(lines)


def _parse_wrap_row(node: Row) -> tuple[list[MathNode], list[int], dict[int, int], list[int]]:
    """Separate atoms from hints, retaining source indices and break priorities."""
    atoms: list[MathNode] = []
    source_indices: list[int] = []
    candidates: dict[int, int] = {}
    forced_ends: list[int] = []
    if node.items and isinstance(node.items[-1], BreakHint):
        raise ValueError("break hint requires a following atom (no trailing empty line)")
    for source_index, item in enumerate(node.items):
        position = len(atoms)
        if isinstance(item, BreakHint):
            if item.mode == "forced":
                if position == (forced_ends[-1] if forced_ends else 0):
                    raise ValueError("forced break would create an empty line")
                forced_ends.append(position)
            else:
                priority = 1 if item.mode == "preferred" else 4
                candidates[position] = min(priority, candidates.get(position, priority))
            continue
        if isinstance(item, Operator):
            if item.text in ("=", "＝", "<", ">", "≦", "≧", "≤", "≥", "≈", "≠"):
                priority = 2
            elif item.text in ("+", "-", "−"):
                priority = 3
            else:
                priority = None
            if priority is not None:
                candidates[position] = min(priority, candidates.get(position, priority))
        atoms.append(item)
        source_indices.append(source_index)
    return atoms, source_indices, candidates, forced_ends


def _measure(node: MathNode, fonts: FontRegistry, style: TextStyle, path: str) -> MathBox:
    try:
        return node.measure(fonts, style)
    except FontError as exc:
        raise FontError(f"{path}: {exc}") from exc


def _width(boxes: tuple[MathBox, ...], gap: float) -> float:
    width = 0.0
    for index, box in enumerate(boxes):
        if index:
            width += gap
        width += box.width
    return width


def _overflow(needed: float, available: float, path: str) -> NoReturn:
    raise LayoutOverflowError(
        f"{path} needs {needed:g} pt; available width is {available:g} pt",
        block_id=path, needed=needed, available=available,
    )
