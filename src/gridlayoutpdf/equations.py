"""Semantic equation wrapping without resizing or splitting math atoms."""

from dataclasses import KW_ONLY, dataclass, replace
import math
from typing import NoReturn

from .blocks import Paragraph
from .errors import FontError, LayoutOverflowError
from .fonts import FontRegistry
from .layout import LayoutContext, LayoutPart, MeasuredBlock, measurement_inputs
from .math import (
    BreakHint, MathBox, MathNode, Operator, Row, TermStop, as_math, compose_row, literal_box,
)
from .styles import TextStyle, _finite_number
from .validation import _identifier, _integer


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
    """Share grid-column anchors across immutable equations and display lines.

    A top-level RHS Row containing TermStop atoms is laid out in term columns
    shared by the group's other such rows; term_gap (default: gap) separates
    the columns. A fitting row ignores its BreakHints and only its result may move
    to its own line. A row whose aligned line exceeds the full RHS width falls
    back to ordinary wrapping, with an allowed break at each non-leading TermStop,
    and no longer contributes to the shared columns.
    """

    equations: tuple[Equation, ...]
    anchors: EquationAnchors | None
    label_columns: int | None
    gap: float
    term_gap: float | None
    style: TextStyle | None
    block_id: str

    def __init__(self, *equations: Equation, anchors: EquationAnchors | None = None,
                 label_columns: int | None = None, gap: float = 4.0,
                 term_gap: float | None = None,
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
        if term_gap is not None:
            term_gap = _finite_number(term_gap, "term_gap")
            if term_gap < 0:
                raise ValueError("term_gap must be nonnegative")
        _style_and_id(style, block_id)
        for name, value in (("equations", tuple(equations)), ("anchors", anchors),
                            ("label_columns", label_columns), ("gap", gap),
                            ("term_gap", term_gap), ("style", style), ("block_id", block_id)):
            object.__setattr__(self, name, value)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        available_width = measurement_inputs(context, available_width)
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
        segments, columns, fallback = _term_layout(
            measured, tuple(_term_segments(item, context) for item in measured), rhs_start,
            available_width - rhs_start, self.gap if self.term_gap is None else self.term_gap)
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
            if segments[index] is None:
                wrapped = item
                if fallback[index]:
                    wrapped = replace(item, equation=replace(
                        item.equation, rhs=_term_fallback_row(item.equation.rhs)))
                rhs_lines, separate_result = _wrap_rhs(wrapped, context, rhs_end - rhs_start,
                                                       available_width - rhs_start)
            else:
                rhs_lines, separate_result = _term_rhs(item, segments[index], columns, rhs_start,
                                                       rhs_end - rhs_start)
            if not rhs_lines:
                rhs_lines = (MathBox(0, 0, 0, (), item.style.size * .25),)
            label = Paragraph(item.equation.label, style=item.style, block_id=item.path + ".label",
                              min_first=1, min_last=1).measure(context, label_width) if item.equation.label else None
            common_metadata = {"equation_index": index, "anchors_pt": points,
                               "rhs_start_pt": rhs_start, "label_width_pt": label_width}
            if segments[index] is not None:
                common_metadata["term_columns_pt"] = columns[:len(segments[index])]
            if fallback[index]:
                common_metadata["term_fallback"] = True
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


def _term_segments(item: _EquationMeasure,
                   context: LayoutContext) -> tuple[tuple[TermStop, MathBox], ...] | None:
    """Split a top-level RHS Row at TermStop atoms; None keeps ordinary wrapping."""
    rhs = item.equation.rhs
    if not isinstance(rhs, Row) or not any(isinstance(atom, TermStop) for atom in rhs.items):
        return None
    path = item.path + ".rhs"
    if isinstance(rhs.items[-1], TermStop):
        raise ValueError(f"{path}: TermStop requires a following term (no trailing stop)")
    stops: list[TermStop] = [TermStop()]
    groups: list[list[MathBox]] = [[]]
    for index, atom in enumerate(rhs.items):
        if isinstance(atom, BreakHint):
            continue  # Hints take no space; they matter only after a fallback.
        if isinstance(atom, TermStop):
            if index == 0:
                stops[0] = atom
            else:
                stops.append(atom)
                groups.append([])
            continue
        groups[-1].append(_measure(atom, context.fonts, item.style, f"{path}[{index}]"))
    gap = item.style.size * 0.15 if rhs.gap is None else rhs.gap
    return tuple((stop, compose_row(boxes, gap, item.style.size * .25))
                 for stop, boxes in zip(stops, groups))


def _term_columns(items: tuple[_EquationMeasure, ...],
                  segments: tuple[tuple[tuple[TermStop, MathBox], ...] | None, ...],
                  rhs_start: float, term_gap: float) -> tuple[tuple[float, float, str], ...] | None:
    """Share each column's alignment and widest term (or minimum width) across the group."""
    aligns: list[str] = []
    widths: list[float] = []
    for item, row in zip(items, segments):
        for column, (stop, box) in enumerate(row or ()):
            if column == len(aligns):
                aligns.append(stop.align)
                widths.append(0.0)
            elif aligns[column] != stop.align:
                raise ValueError(f"{item.path}.rhs: term column {column} align {stop.align!r} "
                                 f"conflicts with {aligns[column]!r}")
            widths[column] = max(widths[column], box.width, stop.width or 0.0)
    if not aligns:
        return None
    columns = []
    left = rhs_start
    for align, width in zip(aligns, widths):
        columns.append((left, width, align))
        left += width + term_gap
    return tuple(columns)


def _term_layout(items: tuple[_EquationMeasure, ...],
                 segments: tuple[tuple[tuple[TermStop, MathBox], ...] | None, ...],
                 rhs_start: float, full_width: float, term_gap: float,
                 ) -> tuple[tuple, tuple[tuple[float, float, str], ...] | None, tuple[bool, ...]]:
    """Drop rows whose aligned line exceeds the full RHS width until the columns settle.

    A row first falls back when its own columns alone are too wide, so a long row
    never drags the others; the rest are then rechecked in their shared columns.
    Without a result the normal RHS region already spans the full width, so one
    limit serves every row. Removing rows only narrows columns, so this ends.
    """
    def too_wide(row, columns) -> bool:
        left, width, _ = columns[len(row) - 1]
        return left + width - rhs_start > max(0, full_width)

    _term_columns(items, segments, rhs_start, term_gap)  # Alignment is shared by every row.
    fallback = [row is not None and too_wide(row, _term_columns((item,), (row,), rhs_start, term_gap))
                for item, row in zip(items, segments)]
    while True:
        kept = tuple(None if dropped else row for dropped, row in zip(fallback, segments))
        columns = _term_columns(items, kept, rhs_start, term_gap)
        added = False
        for index, row in enumerate(kept):
            if row is not None and too_wide(row, columns):
                fallback[index] = added = True
        if not added:
            return kept, columns, tuple(fallback)


def _term_fallback_row(rhs: Row) -> Row:
    """Replace each non-leading TermStop with an allowed break, keeping hints and gap."""
    return Row(*(BreakHint("allowed") if isinstance(atom, TermStop) else atom
                 for index, atom in enumerate(rhs.items)
                 if index or not isinstance(atom, TermStop)), gap=rhs.gap)


def _term_rhs(item: _EquationMeasure, row: tuple[tuple[TermStop, MathBox], ...],
              columns: tuple[tuple[float, float, str], ...], rhs_start: float,
              normal_width: float) -> tuple[tuple[MathBox, ...], bool]:
    """Place one term-aligned RHS, known to fit the full width, on a single line."""
    axis = item.style.size * .25
    commands = []
    ascent = descent = 0.0
    for (_, box), (left, width, align) in zip(row, columns):
        slack = width - box.width
        x = left - rhs_start + (slack if align == "right" else slack / 2 if align == "center" else 0)
        dy = box.axis - axis
        commands.extend(box.translated(x, dy))
        ascent = max(ascent, box.ascent - dy)
        descent = max(descent, box.descent + dy)
    last_left, last_width, _ = columns[len(row) - 1]
    line = MathBox(last_left + last_width - rhs_start, ascent, descent, tuple(commands), axis)
    # Only an equation with a result has a normal region narrower than the full width.
    return (line,), line.width > max(0, normal_width)


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
    """Measure a relation once, keeping its box and advance-centred edges."""
    normalized = context.fonts.normalize_text(text)
    try:
        metrics = context.fonts.measure(normalized, style)
    except FontError as exc:
        raise FontError(f"{path}: {exc}") from exc
    return _Relation(literal_box(normalized, metrics, style),
                     metrics.width / 2 - metrics.bounds.x,
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


# An automatic label reserves its measured width, at most this paper width (six 16.08 pt reference
# columns); a longer label wraps. A fixed number of columns would vanish on a fine placement grid.
AUTOMATIC_LABEL_MAX_PT = 96.48


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
    columns = min(max(1, _floor_column(AUTOMATIC_LABEL_MAX_PT, pitch)), max(1, _ceil_column(natural, pitch)))
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
        available_width = measurement_inputs(context, available_width)
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
    _identifier(block_id)


def _column(value: int, name: str) -> None:
    _integer(value, name, 0, message=f"{name} must be a nonnegative integer column")


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
    _identifier(block_id)
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
            # The atoms are already measured; composing avoids a second pass.
            lines.append(compose_row(boxes[start:end], gap, style.size * 0.25))
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
