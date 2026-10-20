"""Excel border styles, their PDF strokes, and per-edge table borders.

A border is chosen from Excel's border styles (FR-022), never as a pt width.
Each style draws one stroke, or two for ``double``, along an edge. Its PDF
geometry is fixed here so that every component draws the same style alike:

========================  =========  =========================================
style                     stroke pt  PDF dash (on, off, ... pt) / strokes
========================  =========  =========================================
hair                      0.25       solid
thin                      0.5        solid
medium                    1.0        solid
thick                     1.5        solid
double                    0.5 x 2    solid; stroke centres 1.0 pt apart, so a
                                     0.5 pt gap and 1.5 pt in all
dotted                    0.5        0.5, 1.0
dashed                    0.5        3.0, 1.5
dashDot                   0.5        6.0, 1.5, 1.5, 1.5
dashDotDot                0.5        6.0, 1.5, 1.5, 1.5, 1.5, 1.5
mediumDashed              1.0        6.0, 2.0
mediumDashDot             1.0        6.0, 2.0, 2.0, 2.0
mediumDashDotDot          1.0        6.0, 2.0, 2.0, 2.0, 2.0, 2.0
slantDashDot              1.0        6.0, 1.0, 2.0, 1.0 (the slant is not drawn)
========================  =========  =========================================

``TableBorders`` gives every table edge a style or no line (``None``), from
the most specific setting: one edge, then one whole boundary, then the outer
frame, then the table default.
"""

from collections.abc import Mapping
from dataclasses import KW_ONLY, dataclass
from enum import StrEnum
from numbers import Number

from .scene import Color, Line
from .semantics import Role, Scope, Tag, tagged


class BorderStyle(StrEnum):
    """Excel's border styles; the value is the OOXML ``ST_BorderStyle`` name."""

    HAIR = "hair"
    THIN = "thin"
    MEDIUM = "medium"
    THICK = "thick"
    DOUBLE = "double"
    DOTTED = "dotted"
    DASHED = "dashed"
    DASH_DOT = "dashDot"
    DASH_DOT_DOT = "dashDotDot"
    MEDIUM_DASHED = "mediumDashed"
    MEDIUM_DASH_DOT = "mediumDashDot"
    MEDIUM_DASH_DOT_DOT = "mediumDashDotDot"
    SLANT_DASH_DOT = "slantDashDot"

    @property
    def stroke_width(self) -> float:
        """The width of each PDF stroke in pt."""
        return _GEOMETRY[self][0]

    @property
    def offsets(self) -> tuple[float, ...]:
        """Stroke centres relative to the edge's centre line, in pt."""
        return _GEOMETRY[self][1]

    @property
    def dash(self) -> tuple[float, ...]:
        """The PDF dash pattern in pt; empty for a solid stroke."""
        return _GEOMETRY[self][2]

    @property
    def thickness(self) -> float:
        """The ink across the edge, from the outer side of one stroke to the other."""
        return max(self.offsets) - min(self.offsets) + self.stroke_width

    def lines(self, x1: float, y1: float, x2: float, y2: float,
              color: Color = (0, 0, 0)) -> tuple[Line, ...]:
        """Return the strokes of this style along a horizontal or vertical edge.

        The coordinates are the edge's centre line. ``double`` returns two
        lines, offset perpendicular to the edge; every other style one.
        """
        horizontal, vertical = y1 == y2, x1 == x2
        if horizontal == vertical:
            raise ValueError("a border edge must be horizontal or vertical and have a length")
        return tuple(
            Line(x1, y1 + offset, x2, y2 + offset, self.stroke_width, color, dash=self.dash)
            if horizontal else
            Line(x1 + offset, y1, x2 + offset, y2, self.stroke_width, color, dash=self.dash)
            for offset in self.offsets
        )


def _border_lines(style: BorderStyle, x1: float, y1: float, x2: float, y2: float, color: Color,
                  role: Role, path: tuple[Scope, ...] = (), **data) -> tuple[Line, ...]:
    """``style.lines()`` with each stroke tagged by ``role``, its style and its number.

    ``stroke`` counts the strokes of one edge from 0: for ``double``, 0 is the
    upper (horizontal) or left (vertical) line.
    """
    return tuple(tagged((line,), Tag(role, path, {**data, "style": style.value, "stroke": index}))[0]
                 for index, line in enumerate(style.lines(x1, y1, x2, y2, color)))


_SINGLE = (0.0,)
_GEOMETRY: dict[BorderStyle, tuple[float, tuple[float, ...], tuple[float, ...]]] = {
    BorderStyle.HAIR: (0.25, _SINGLE, ()),
    BorderStyle.THIN: (0.5, _SINGLE, ()),
    BorderStyle.MEDIUM: (1.0, _SINGLE, ()),
    BorderStyle.THICK: (1.5, _SINGLE, ()),
    BorderStyle.DOUBLE: (0.5, (-0.5, 0.5), ()),
    BorderStyle.DOTTED: (0.5, _SINGLE, (0.5, 1.0)),
    BorderStyle.DASHED: (0.5, _SINGLE, (3.0, 1.5)),
    BorderStyle.DASH_DOT: (0.5, _SINGLE, (6.0, 1.5, 1.5, 1.5)),
    BorderStyle.DASH_DOT_DOT: (0.5, _SINGLE, (6.0, 1.5, 1.5, 1.5, 1.5, 1.5)),
    BorderStyle.MEDIUM_DASHED: (1.0, _SINGLE, (6.0, 2.0)),
    BorderStyle.MEDIUM_DASH_DOT: (1.0, _SINGLE, (6.0, 2.0, 2.0, 2.0)),
    BorderStyle.MEDIUM_DASH_DOT_DOT: (1.0, _SINGLE, (6.0, 2.0, 2.0, 2.0, 2.0, 2.0)),
    BorderStyle.SLANT_DASH_DOT: (1.0, _SINGLE, (6.0, 1.0, 2.0, 1.0)),
}


def _border_style(value: object, name: str, *, allow_none: bool = True) -> BorderStyle | None:
    """Return ``value`` as a BorderStyle, or None for no line when allowed.

    Excel style names such as ``"thin"`` are accepted. Numbers are rejected:
    pt widths are no longer a way to choose a border (FR-022).
    """
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{name} must be a BorderStyle")
    if isinstance(value, BorderStyle):
        return value
    if isinstance(value, str):
        try:
            return BorderStyle(value)
        except ValueError:
            pass
    names = ", ".join(style.value for style in BorderStyle)
    if isinstance(value, Number) and not isinstance(value, bool):
        raise ValueError(f"{name} must be a BorderStyle ({names}); pt widths are no longer accepted")
    raise ValueError(f"{name} must be a BorderStyle ({names}){' or None' if allow_none else ''}")


class _Inherit:
    """The outer frame takes the table default unless it is set."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<default>"

    def __reduce__(self) -> str:
        # Copies and pickles resolve to the one module-level sentinel.
        return "_INHERIT"


_INHERIT = _Inherit()

Styles = Mapping[int, "BorderStyle | str | None"] | tuple[tuple[int, "BorderStyle | None"], ...]
EdgeStyles = (Mapping[tuple[int, int], "BorderStyle | str | None"]
              | tuple[tuple[tuple[int, int], "BorderStyle | None"], ...])


def _index(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} keys must be nonnegative integer indices")
    return value


def _styles_by(values: object, name: str, pair: bool) -> tuple:
    """Snapshot a mapping of indices to styles as sorted (key, style) pairs.

    Sorted pairs (the stored form, e.g. through ``replace()``) are accepted
    too, but a key may appear only once.
    """
    if isinstance(values, tuple) and all(isinstance(item, tuple) and len(item) == 2 for item in values):
        try:
            keys = [key for key, _ in values]
            if len(set(keys)) != len(keys):
                raise ValueError(f"{name} has duplicate keys")
            values = dict(values)
        except TypeError as exc:
            raise ValueError(f"{name} keys must be {'(row, column) index pairs' if pair else 'integer indices'}") from exc
    if not isinstance(values, Mapping):
        raise ValueError(f"{name} must be a mapping of {'(row, column)' if pair else 'boundary'} "
                         "indices to BorderStyle or None")
    items = []
    for key, style in values.items():
        if pair:
            if not isinstance(key, tuple) or len(key) != 2:
                raise ValueError(f"{name} keys must be (row, column) index pairs")
            key = (_index(key[0], name), _index(key[1], name))
        else:
            key = _index(key, name)
        items.append((key, _border_style(style, f"{name}[{key!r}]")))
    return tuple(sorted(items, key=lambda item: item[0]))


@dataclass(frozen=True, slots=True)
class TableBorders:
    """Every table edge's style, resolved from the most specific setting.

    ``default`` applies to every edge and ``outer`` to the frame (it takes
    ``default`` unless set; ``frame`` gives the style the frame resolves to).
    ``horizontal`` maps a row boundary (0 is the top, the row count the
    bottom) to a style across all columns, and ``vertical`` a column boundary
    (0 is the left) down all rows. ``horizontal_edges`` maps (row boundary,
    column) and ``vertical_edges`` (row, column boundary) to the style of one
    edge, which allows a rule under some columns only.

    A one-edge setting overrides a boundary, a boundary the frame and the
    frame the default, whatever the order they are written in. ``None`` means
    no line. Styles may be given by their Excel names. Edges inside a merged
    cell are never drawn; naming one in ``horizontal_edges`` or
    ``vertical_edges`` is an error. The four mappings are stored as sorted
    ``(key, style)`` pairs, which are accepted back as well.
    """

    default: BorderStyle | str | None = BorderStyle.THIN
    _: KW_ONLY
    outer: BorderStyle | str | None | _Inherit = _INHERIT
    horizontal: Styles = ()
    vertical: Styles = ()
    horizontal_edges: EdgeStyles = ()
    vertical_edges: EdgeStyles = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "default", _border_style(self.default, "default"))
        if self.outer is not _INHERIT:
            object.__setattr__(self, "outer", _border_style(self.outer, "outer"))
        for name, pair in (("horizontal", False), ("vertical", False),
                           ("horizontal_edges", True), ("vertical_edges", True)):
            object.__setattr__(self, name, _styles_by(getattr(self, name), name, pair))

    @property
    def frame(self) -> BorderStyle | None:
        """The style of the outer frame: ``outer`` if set, otherwise ``default``."""
        return self.default if self.outer is _INHERIT else self.outer

    def _check(self, rows: int, columns: int, location: str) -> None:
        """Reject indices outside a table of ``rows`` x ``columns``."""
        for name, limit in (("horizontal", rows), ("vertical", columns)):
            for index, _ in getattr(self, name):
                if index > limit:
                    raise ValueError(f"{location}: borders.{name} boundary {index} is outside 0..{limit}")
        for name, row_limit, column_limit in (("horizontal_edges", rows, columns - 1),
                                              ("vertical_edges", rows - 1, columns)):
            for (row, column), _ in getattr(self, name):
                if row > row_limit or column > column_limit:
                    raise ValueError(f"{location}: borders.{name} edge {(row, column)} is outside the table")

    def resolve(self, rows: int, columns: int) -> tuple[tuple[tuple[BorderStyle | None, ...], ...],
                                                        tuple[tuple[BorderStyle | None, ...], ...]]:
        """Return (horizontal[row boundary][column], vertical[row][column boundary]) styles.

        Merged cells are not known here; ``Table`` clears the edges inside them.
        """
        frame = self.frame
        lines = dict(self.horizontal)
        edges = dict(self.horizontal_edges)
        horizontal = tuple(
            tuple(edges[(boundary, column)] if (boundary, column) in edges else lines.get(
                boundary, frame if boundary in (0, rows) else self.default)
                for column in range(columns))
            for boundary in range(rows + 1))
        lines = dict(self.vertical)
        edges = dict(self.vertical_edges)
        vertical = tuple(
            tuple(edges[(row, boundary)] if (row, boundary) in edges else lines.get(
                boundary, frame if boundary in (0, columns) else self.default)
                for boundary in range(columns + 1))
            for row in range(rows))
        return horizontal, vertical


def _table_borders(value: object, name: str = "borders") -> TableBorders:
    """Accept TableBorders, one style for every edge, or None for no lines."""
    if isinstance(value, TableBorders):
        return value
    try:
        return TableBorders(_border_style(value, name))
    except ValueError as exc:
        raise ValueError(f"{exc}; or a TableBorders") from exc
