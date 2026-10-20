"""Semantic tags: what a drawing command means in the report that drew it.

Every library component tags the commands it draws (Step 5 of the grid Excel
plan), so a later consumer such as the grid Excel mapping can tell a fraction
bar from a table border, or the numerator of one fraction from the next one,
from the tags and the page metadata alone. Tags never change drawing,
equality or hashing: every command holds its tag in a ``compare=False`` field.

A ``Tag`` has three parts:

* ``role`` (``Role``): what the command itself is, e.g. a table border or a
  math glyph run.
* ``path``: the ``Scope`` chain, outermost first, of the structures the
  command lies in, e.g. equation 3, display line 0, term 2, the numerator of
  a fraction. Components measure bottom-up, so a parent prepends its own
  scope to every child command (``within``).
* ``data``: facts of the command's own, e.g. a border's boundary and style.

A structure is identified by the path up to its scope with the part removed
(``Tag.key``), so the numerator, denominator and bar of one fraction share a
key. Paths are unique within one placement on a page (multi-child containers
number their children); the page metadata gives each placement's command
range. ``docs/architecture.md`` lists every role, scope kind and data field.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import StrEnum
from math import isfinite


class Role(StrEnum):
    """What one drawing command is."""

    TEXT = "text"                  # prose: Paragraph/Heading lines, cell strings, decorations
    MATH = "math"                  # a math glyph run (Literal, Symbol, Operator, an equation relation)
    FRACTION_BAR = "fraction_bar"
    RADICAL = "radical"            # the sign of a Root
    DELIMITER = "delimiter"        # a bracket or bar of Delimited
    TABLE_BORDER = "table_border"  # a Table edge line
    RULE = "rule"                  # a Rule separator
    SIDE_RULE = "side_rule"        # a SideRule bar
    FIGURE = "figure"              # any command of a Figure, its text included
    IMAGE = "image"                # the RasterImage of an Image
    OTHER = "other"                # a command from user code placed inside a library structure


# Only these become cell borders in a grid Excel sheet (DESIGN Key Decisions).
BORDER_ROLES = frozenset({Role.TABLE_BORDER, Role.RULE, Role.SIDE_RULE})


class Kind(StrEnum):
    """The structure a scope stands for; ``part`` and ``index`` say where in it."""

    STACK = "stack"                  # index: child
    COLUMNS = "columns"              # index: child
    PARAGRAPH = "paragraph"          # index: display line; data: align, heading
    DECORATION = "decoration"        # part: header | footer; data: template, align
    TABLE = "table"                  # data: block_id
    TABLE_CELL = "table_cell"        # data: cell_id, row, col, rowspan, colspan, align, valign
    CELL_LINES = "cell_lines"        # index: display line; data: align
    EQUATION = "equation"            # index: equation in its group
    EQUATION_LINE = "equation_line"  # index: display line; data: continuation, result_line
    EQUATION_PART = "equation_part"  # part: label | lhs | relation | rhs | term | result_relation
    #                                  | result | unit; index and data.align: the term column
    MATH_BLOCK = "math_block"
    ROW = "row"                      # index: item of the Row (source index, hints included)
    FRACTION = "fraction"            # part: numerator | denominator | bar
    SCRIPT = "script"                # part: base | superscript | subscript
    ROOT = "root"                    # part: sign | radicand
    DELIMITED = "delimited"          # part: left | right | body
    FIGURE = "figure"                # data: block_id
    FIGURE_ITEM = "figure_item"      # index: item; data: kind (raw, align, rounded)
    QUARTER_TURN = "quarter_turn"    # data: turns, local_grid, block_id


class FrozenData(Mapping):
    """An immutable, hashable mapping of JSON-compatible values.

    Keys are strings. Values are None, bool, int, finite float, str (string
    enums become plain str), tuples (from lists or tuples) and FrozenData
    (from mappings). Anything else raises ValueError.
    """

    __slots__ = ("_items", "_hash")

    def __init__(self, items: Mapping[str, object] | Iterable[tuple[str, object]] = ()) -> None:
        pairs = items.items() if isinstance(items, Mapping) else items
        frozen = {}
        for key, value in pairs:
            if not isinstance(key, str):
                raise ValueError("tag data keys must be strings")
            frozen[str(key)] = _freeze(value)
        object.__setattr__(self, "_items", frozen)
        object.__setattr__(self, "_hash", None)

    def __setattr__(self, name, value):
        raise AttributeError("FrozenData is immutable")

    def __getitem__(self, key: str) -> object:
        return self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        if self._hash is None:
            object.__setattr__(self, "_hash", hash(frozenset(self._items.items())))
        return self._hash

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self._items) == dict(other)
        return NotImplemented

    def __repr__(self) -> str:
        return f"FrozenData({self._items!r})"

    def __reduce__(self):
        return FrozenData, (tuple(self._items.items()),)

    def to_json(self) -> dict:
        return {key: _json(value) for key, value in self._items.items()}


EMPTY = FrozenData()


def _freeze(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("tag data numbers must be finite")
        return float(value)
    if isinstance(value, str):
        return str.__str__(value)
    if isinstance(value, FrozenData):
        return value
    if isinstance(value, Mapping):
        return FrozenData(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    raise ValueError(f"unsupported tag data value: {type(value).__name__}")


def _json(value: object) -> object:
    if isinstance(value, FrozenData):
        return value.to_json()
    if isinstance(value, tuple):
        return [_json(item) for item in value]
    return value


def _data(value: object) -> FrozenData:
    if isinstance(value, FrozenData):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("tag data must be a mapping")
    return FrozenData(value)


def _member(enum: type[StrEnum], value: object, name: str) -> StrEnum:
    try:
        return enum(value)
    except ValueError:
        raise ValueError(f"unknown tag {name}: {value!r}") from None


@dataclass(frozen=True, slots=True)
class Scope:
    """One structure a command lies in: its kind, the part and index within it."""

    kind: Kind
    part: str | None = None
    index: int | None = None
    data: Mapping[str, object] = field(default=EMPTY)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _member(Kind, self.kind, "kind"))
        if self.part is not None and (not isinstance(self.part, str) or not self.part):
            raise ValueError("scope part must be a nonempty string or None")
        if self.index is not None and (isinstance(self.index, bool) or not isinstance(self.index, int)
                                       or self.index < 0):
            raise ValueError("scope index must be a nonnegative integer or None")
        object.__setattr__(self, "data", _data(self.data))

    def to_json(self) -> dict:
        result: dict = {"kind": self.kind.value}
        if self.part is not None:
            result["part"] = self.part
        if self.index is not None:
            result["index"] = self.index
        if self.data:
            result["data"] = self.data.to_json()
        return result


@dataclass(frozen=True, slots=True)
class Tag:
    """A command's role, its scope path (outermost first) and its own data."""

    role: Role
    path: tuple[Scope, ...] = ()
    data: Mapping[str, object] = field(default=EMPTY)

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _member(Role, self.role, "role"))
        if isinstance(self.path, (str, bytes)):
            raise ValueError("tag path must be a sequence of Scope objects")
        try:
            path = tuple(self.path)
        except TypeError as exc:
            raise ValueError("tag path must be a sequence of Scope objects") from exc
        if any(not isinstance(scope, Scope) for scope in path):
            raise ValueError("tag path must contain only Scope objects")
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "data", _data(self.data))

    def within(self, *scopes: Scope) -> Tag:
        """Return this tag inside the outer ``scopes`` (given outermost first)."""
        if any(not isinstance(scope, Scope) for scope in scopes):
            raise ValueError("tag path must contain only Scope objects")
        # Every part is already validated, so the copy skips __post_init__.
        tag = object.__new__(Tag)
        object.__setattr__(tag, "role", self.role)
        object.__setattr__(tag, "path", (*scopes, *self.path))
        object.__setattr__(tag, "data", self.data)
        return tag

    def find(self, kind: Kind | str) -> int | None:
        """Return the position of the innermost scope of ``kind`` in the path."""
        kind = _member(Kind, kind, "kind")
        for position in range(len(self.path) - 1, -1, -1):
            if self.path[position].kind is kind:
                return position
        return None

    def scope(self, kind: Kind | str) -> Scope | None:
        """Return the innermost scope of ``kind``, or None."""
        position = self.find(kind)
        return None if position is None else self.path[position]

    def key(self, kind: Kind | str) -> tuple[Scope, ...] | None:
        """Identify the innermost structure of ``kind`` the command belongs to.

        The path up to that scope, with its part removed, is the same for
        every command of one structure (a fraction's numerator, denominator
        and bar) and differs between structures in one placement.
        """
        position = self.find(kind)
        if position is None:
            return None
        return (*self.path[:position], replace(self.path[position], part=None))

    def to_json(self) -> dict:
        result: dict = {"role": self.role.value, "path": [scope.to_json() for scope in self.path]}
        if self.data:
            result["data"] = self.data.to_json()
        return result


def tagged(commands: Iterable, tag: Tag) -> tuple:
    """Return the commands with ``tag``, replacing whatever tag they had."""
    if not isinstance(tag, Tag):
        raise ValueError("tag must be a Tag")
    return tuple(_with_tag(command, tag) for command in commands)


def within(commands: Iterable, *scopes: Scope) -> tuple:
    """Return the commands inside the outer ``scopes`` (given outermost first).

    A command without a tag came from user code; it becomes ``Role.OTHER``
    so that it still records the library structure it was placed in.
    """
    other = Tag(Role.OTHER, scopes)
    return tuple(_with_tag(command, other if command.tag is None else command.tag.within(*scopes))
                 for command in commands)


# Field names of plain slots dataclasses (the scene commands), or () to use replace().
_SLOT_FIELDS: dict[type, tuple[str, ...]] = {}


def _slot_fields(cls: type) -> tuple[str, ...]:
    if not is_dataclass(cls) or cls.__dictoffset__:
        return ()
    names = tuple(item.name for item in fields(cls))
    slots = {name for klass in cls.__mro__ for name in getattr(klass, "__slots__", ())}
    return names if "tag" in names and set(names) <= slots else ()


def _with_tag(command, tag: Tag):
    """Return a copy of an already validated command that carries ``tag``.

    Components re-tag every command once per enclosing structure, so the
    copy takes the validated fields as they are instead of re-running
    ``__post_init__`` through ``replace`` (the result is the same command).
    """
    cls = type(command)
    names = _SLOT_FIELDS.get(cls)
    if names is None:
        names = _SLOT_FIELDS.setdefault(cls, _slot_fields(cls))
    if not names:
        return replace(command, tag=tag)
    clone = object.__new__(cls)
    for name in names:
        object.__setattr__(clone, name, getattr(command, name))
    object.__setattr__(clone, "tag", tag)
    return clone
