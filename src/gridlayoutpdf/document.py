"""Immutable report documents and bounded grid-row pagination."""

from dataclasses import KW_ONLY, dataclass, replace
from pathlib import Path
from string import Formatter

from .blocks import PageBreak, Paragraph
from .containers import At, Stack
from .errors import LayoutError, LayoutOverflowError
from .fonts import FontRegistry, default_fonts
from .layout import (
    LayoutContext, LayoutPart, MeasuredBlock, _has_visible_commands, measure_child, part_descriptors,
)
from .profiles import A4_PORTRAIT_REFERENCE, PageProfile
from .renderers.reportlab import render_pdf
from .scene import ScenePage
from .styles import ReportStyle, TextStyle
from .validation import _integer, whole_units_in


@dataclass(frozen=True, slots=True)
class PageDecoration:
    """Text in a fixed grid-row frame outside the page body."""

    text: str
    _: KW_ONLY
    rows: int = 1
    gap_rows: int = 1
    align: str = "left"
    style: TextStyle | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or "\t" in self.text:
            raise ValueError("decoration text must be a string without tabs")
        for name, value, minimum in (("rows", self.rows, 1), ("gap_rows", self.gap_rows, 0)):
            _integer(value, name, minimum)
        if self.align not in ("left", "center", "right"):
            raise ValueError("decoration align must be left, center or right")
        if self.style is not None and not isinstance(self.style, TextStyle):
            raise ValueError("decoration style must be a TextStyle or None")
        for _, field, spec, conversion in Formatter().parse(self.text):
            if field is not None:
                if field not in ("page", "pages") or conversion or "{" in spec or "}" in spec:
                    raise ValueError("decoration supports only page/pages integer fields")
                format(1, spec)


@dataclass(frozen=True, slots=True, init=False)
class PageSection:
    """A scoped page-profile switch; entering and leaving require new pages."""

    profile: PageProfile
    children: tuple[object, ...]

    def __init__(self, profile: PageProfile, *blocks) -> None:
        if not isinstance(profile, PageProfile):
            raise ValueError("profile must be a PageProfile")
        object.__setattr__(self, "profile", profile)
        object.__setattr__(self, "children", tuple(blocks))


@dataclass(frozen=True, slots=True, init=False)
class Document:
    blocks: tuple[object, ...]
    fonts: FontRegistry
    profile: PageProfile
    style: ReportStyle
    header: PageDecoration | None
    footer: PageDecoration | None

    def __init__(self, *blocks, fonts: FontRegistry | None = None,
                 profile: PageProfile = A4_PORTRAIT_REFERENCE,
                 style: ReportStyle = ReportStyle(), header=None, footer=None) -> None:
        if fonts is None:
            fonts = default_fonts()
        for name, value, expected in (("fonts", fonts, FontRegistry), ("profile", profile, PageProfile),
                                      ("style", style, ReportStyle)):
            if not isinstance(value, expected):
                raise ValueError(f"{name} must be a {expected.__name__}")
        for decoration in (header, footer):
            if decoration is not None and not isinstance(decoration, PageDecoration):
                raise ValueError("header and footer must be PageDecoration or None")
        for name, value in (("blocks", tuple(blocks)), ("fonts", fonts), ("profile", profile),
                            ("style", style), ("header", header), ("footer", footer)):
            object.__setattr__(self, name, value)

    def layout(self) -> tuple[ScenePage, ...]:
        events = tuple(_events(self.blocks, self, self.profile, "Document.blocks"))
        return _decorate_pages(_Paginator(self).run(events), self)

    def render(self, path: str | Path, *, debug_grid: bool = False, invariant: bool = False) -> Path:
        """Layout completely, then atomically replace the destination PDF."""
        pages = self.layout()
        if not pages:
            raise LayoutError("cannot render an empty Document")
        destination = Path(path)
        render_pdf(pages, destination, self.fonts, debug_grid=debug_grid, invariant=invariant)
        return destination


@dataclass(frozen=True, slots=True)
class _Event:
    kind: str
    profile: PageProfile
    source_path: str
    measured: MeasuredBlock | None = None
    at: At | None = None


def _events(blocks, document: Document, profile: PageProfile, prefix: str):
    context = LayoutContext(document.fonts, profile, document.style)
    for index, block in enumerate(blocks):
        path = f"{prefix}[{index}]"
        if isinstance(block, PageBreak):
            yield _Event("break", profile, path)
        elif isinstance(block, Stack):
            yield from _events(block.children, document, profile, path + ".children")
        elif isinstance(block, PageSection):
            children = tuple(_events(block.children, document, block.profile, path + ".children"))
            if any(event.measured is not None and event.measured.rows for event in children):
                yield _Event("boundary", block.profile, path)
                yield from children
                yield _Event("boundary", profile, path)
        elif isinstance(block, At):
            yield _at_event(block, context, profile, path)
        else:
            yield _Event("block", profile, path, measure_child(block, context, profile.body_rect.width, path))


def _at_event(block: At, context: LayoutContext, profile: PageProfile, path: str) -> _Event:
    """Validate an explicit frame and measure its atomic child before pagination."""
    source = block.block_id or path
    if not profile.body_start_row <= block.row <= profile.body_end_row:
        raise LayoutError(f"{source}: At row {block.row} is outside the body")
    if block.col + block.col_span > profile.grid.columns:
        raise LayoutOverflowError(
            f"{source}: At columns exceed the page grid", block_id=source,
            needed=block.col_span * profile.grid.pitch_x,
            available=max(0, profile.grid.columns - block.col) * profile.grid.pitch_x,
        )
    measured = measure_child(block.block, context, block.col_span * profile.grid.pitch_x, path + ".block")
    if block.block_id:
        measured = replace(measured, block_id=block.block_id)
    if measured.rows > profile.body_end_row - block.row:
        _row_overflow(measured.block_id or source, measured.rows, profile.body_end_row - block.row)
    return _Event("at", profile, path, measured, block)


class _Paginator:
    def __init__(self, document: Document) -> None:
        self.profile = document.profile
        self.cursor = self.profile.body_start_row
        self.pages = []
        self.commands = []
        self.placements = []

    @property
    def capacity(self) -> int:
        return self.profile.body_end_row - self.profile.body_start_row

    def run(self, events: tuple[_Event, ...]) -> tuple[ScenePage, ...]:
        index = 0
        while index < len(events):
            event = events[index]
            index += 1
            if event.kind == "break":
                self.flush()
                continue
            if event.kind == "boundary":
                self.flush()
                self.profile = event.profile
                self.cursor = self.profile.body_start_row
                continue
            if event.kind == "at":
                self.explicit(event)
                continue
            measured = event.measured
            if not measured.rows:
                continue
            if measured.keep_with_next and _has_visible_commands(measured.commands):
                index = self.keep_chain(events, index - 1)
                continue
            self.flow(event, measured)
        self.flush()
        return tuple(self.pages)

    def explicit(self, event: _Event) -> None:
        at, measured = event.at, event.measured
        source = measured.block_id or event.source_path
        if at.row < self.cursor:
            raise LayoutError(f"{source}: At row {at.row} precedes cursor {self.cursor}")
        if measured.keep_with_next and _has_visible_commands(measured.commands):
            raise LayoutError(f"{source}: At cannot leave keep_with_next outside its atomic child")
        if measured.rows:
            self.cursor = at.row
            self.place(event, measured, col=at.col)

    def keep_chain(self, events: tuple[_Event, ...], start: int) -> int:
        chain_rows = 0
        end = start
        while end < len(events):
            event = events[end]
            if event.kind != "block":
                break
            measured = event.measured
            if end > start and _has_visible_commands(measured.commands) and not measured.keep_with_next:
                minimum = chain_rows + _minimum_visible_rows(measured)
                if minimum > self.capacity:
                    _row_overflow(events[start].measured.block_id or events[start].source_path,
                                  minimum, self.capacity)
                whole = chain_rows + measured.rows
                reserve = whole if measured.prefer_keep and whole <= self.capacity else minimum
                if reserve > self.profile.body_end_row - self.cursor:
                    self.flush()
                for heading_event in events[start:end]:
                    if heading_event.measured.rows and not self.discards(heading_event.measured):
                        self.place(heading_event, heading_event.measured)
                self.flow(event, measured, suppress_prefer=whole > self.capacity)
                return end + 1
            chain_rows += measured.rows
            end += 1
        source = events[start].measured.block_id or events[start].source_path
        boundary = events[end].kind if end < len(events) else "document end"
        raise LayoutError(f"{source}: keep_with_next reaches {boundary} before a visible body block")

    def flow(self, event: _Event, measured: MeasuredBlock, *, suppress_prefer: bool = False) -> None:
        while measured.rows:
            if self.discards(measured):
                return
            available = self.profile.body_end_row - self.cursor
            if measured.rows <= available:
                self.place(event, measured)
                return
            if (measured.prefer_keep and not suppress_prefer and measured.rows <= self.capacity
                    and self.placements):
                self.flush()
                continue
            fragments = measured.split(available)
            if fragments is not None:
                head, tail = fragments
                if (not isinstance(head, MeasuredBlock) or not isinstance(tail, MeasuredBlock)
                        or not head.parts or not tail.parts
                        or len(tail.parts) >= len(measured.parts)
                        or head.rows > available or head.rows <= 0):
                    raise LayoutError(f"{measured.block_id or event.source_path}: split must make progress and reduce body parts")
                self.place(event, head)
                self.flush()
                measured = tail
                suppress_prefer = False
                continue
            if self.placements:
                self.flush()
                continue
            _row_overflow(measured.block_id or event.source_path, measured.minimum_rows, self.capacity)

    def discards(self, measured: MeasuredBlock) -> bool:
        """Drop an opt-in spacer that would be the first thing on a page."""
        return (measured.discard_at_page_top and not self.placements
                and self.cursor == self.profile.body_start_row)

    def place(self, event: _Event, measured: MeasuredBlock, *, col: int = 0) -> None:
        grid = self.profile.grid
        self.commands.extend(measured.translated(grid.x(col), grid.y(self.cursor)))
        placement = {"block_id": measured.block_id or event.source_path,
                     "source_path": event.source_path, "row": self.cursor, "col": col,
                     "rows": measured.rows, "width": measured.width,
                     **part_descriptors(measured)}
        self.placements.append(placement)
        self.cursor += measured.rows

    def flush(self) -> None:
        if self.placements:
            self.pages.append(ScenePage(self.profile, tuple(self.commands), {
                "page_number": len(self.pages) + 1, "placements": self.placements,
            }))
        self.commands = []
        self.placements = []
        self.cursor = self.profile.body_start_row


def _row_overflow(block_id: str, needed: int, available: int) -> None:
    raise LayoutOverflowError(
        f"{block_id}: needs {needed} rows; available {available} rows",
        block_id=block_id, needed=needed, available=available,
    )


def _part_visible(part: LayoutPart, first: bool, prefix: bool = False) -> bool:
    """Whether a part draws something where it lands after a keep chain.

    The first part of the fragment draws its opening, any other its
    continuing. A body part draws its joining or its closing lines, depending
    on the cut; a prefix part is always followed by a body part, so it draws
    its joining.
    """
    return (_has_visible_commands(part.commands)
            or _has_visible_commands(part.opening if first else part.continuing)
            or (_has_visible_commands(part.joining)
                and (prefix or _has_visible_commands(part.closing))))


def _minimum_visible_rows(measured: MeasuredBlock) -> int:
    """Reserve the first legal fragment containing actual text or artwork."""
    first_visible = 0
    if not any(_part_visible(part, index == 0, prefix=True) for index, part in enumerate(measured.prefix)):
        first_visible = next((index for index, part in enumerate(measured.parts, start=1)
                              if _part_visible(part, not measured.prefix and index == 1)),
                             len(measured.parts))
    return next((rows for cut, rows in measured._valid_cuts() if cut >= first_visible), measured.rows)


def _decorate_pages(pages: tuple[ScenePage, ...], document: Document) -> tuple[ScenePage, ...]:
    return tuple(_decorate_page(page, number, len(pages), document)
                 for number, page in enumerate(pages, start=1))


def _decorate_page(page: ScenePage, number: int, total: int, document: Document) -> ScenePage:
    """Add fixed-frame decorations after the final page count is known."""
    profile = page.profile
    body, pitch = profile.body_rect, profile.grid.pitch_y
    commands = list(page.commands)
    decorations = {}
    for side, decoration in (("header", document.header), ("footer", document.footer)):
        if decoration is None:
            continue
        source = f"page[{number}].{side}"
        required = decoration.rows + decoration.gap_rows
        if side == "header":
            top = body.y - required * pitch
        else:
            top = body.y + body.height + decoration.gap_rows * pitch
        if top < 0 or top + decoration.rows * pitch > profile.height:
            available = (_whole_rows(0, body.y, pitch) if side == "header" else
                         decoration.gap_rows + _whole_rows(top, profile.height, pitch))
            _row_overflow(source, required, max(0, available))
        text = decoration.text.format(page=number, pages=total)
        style = decoration.style or replace(document.style.body, size=9)
        context = LayoutContext(document.fonts, profile, document.style)
        block = Paragraph(text, style=style, align=decoration.align, block_id=source,
                          min_first=1, min_last=1)
        measured = measure_child(block, context, body.width, source)
        if measured.rows > decoration.rows:
            _row_overflow(source, measured.rows, decoration.rows)
        commands.extend(measured.translated(body.x, top))
        decorations[side] = {"text": text, "x_pt": body.x, "y_pt": top,
                             "width": body.width, "height": decoration.rows * pitch,
                             "rows": decoration.rows}
    metadata = dict(page.metadata)
    if decorations:
        metadata["decorations"] = decorations
    return ScenePage(profile, tuple(commands), metadata)


def _whole_rows(start: float, end: float, pitch: float) -> int:
    """Count complete row boundaries using the coordinates used for drawing."""
    return whole_units_in(start, end, pitch)
