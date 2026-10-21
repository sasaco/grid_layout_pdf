"""Local-point vector figures, grid-framed raster images and vector PDF pages."""

from dataclasses import KW_ONLY, dataclass, field
from io import BytesIO
from math import hypot
from pathlib import Path

from PIL import Image as PILImage, ImageOps

from .bounds import command_bounds
from .errors import FontError, LayoutOverflowError
from .layout import LayoutContext, LayoutPart, MeasuredBlock, measurement_inputs
from .pdfpages import pdf_page_box
from .scene import Circle, Color, Line, Polyline, RasterImage, Rectangle, Text, VectorPage
from .semantics import Kind, Role, Scope, Tag, tagged
from .styles import TextStyle, _finite_number
from .validation import TOLERANCE, _identifier, _integer


def _frame(col_span, rows, block_id):
    for name, value in (("col_span", col_span), ("rows", rows)):
        _integer(value, name, 1, message=f"{name} must be a positive integer")
    _identifier(block_id)


def _frame_size(context, col_span, rows, available_width, block_id):
    available_width = measurement_inputs(context, available_width)
    width = _finite_number(col_span * context.profile.grid.pitch_x, "frame width")
    height = _finite_number(rows * context.profile.grid.pitch_y, "frame height")
    if width > available_width + TOLERANCE:
        raise LayoutOverflowError(
            f"{block_id}: frame width {width:g} exceeds available width {available_width:g}",
            block_id=block_id, needed=width, available=available_width)
    return width, height


@dataclass(frozen=True, slots=True)
class Arrow:
    """An oriented vector shaft and open two-sided head ending at (x2, y2)."""

    x1: float
    y1: float
    x2: float
    y2: float
    _: KW_ONLY
    head_length: float = 6.0
    head_width: float = 4.0
    width: float = .6
    color: Color = (0, 0, 0)

    def __post_init__(self) -> None:
        shaft = Line(self.x1, self.y1, self.x2, self.y2, self.width, self.color)
        for name in ("x1", "y1", "x2", "y2", "width", "color"):
            object.__setattr__(self, name, getattr(shaft, name))
        for name in ("head_length", "head_width"):
            value = _finite_number(getattr(self, name), name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        length = _finite_number(hypot(self.x2 - self.x1, self.y2 - self.y1), "axis length")
        if length == 0 or self.head_length > length:
            raise ValueError("arrow axis must be nonzero and at least head_length long")

    def _commands(self) -> tuple[Line, Polyline]:
        """The shaft, then the head (``Figure`` tags them as parts shaft and head)."""
        length = hypot(self.x2 - self.x1, self.y2 - self.y1)
        ux, uy = (self.x2 - self.x1) / length, (self.y2 - self.y1) / length
        bx, by = self.x2 - ux * self.head_length, self.y2 - uy * self.head_length
        px, py = -uy * self.head_width / 2, ux * self.head_width / 2
        return (
            Line(self.x1, self.y1, self.x2, self.y2, self.width, self.color),
            Polyline(((bx + px, by + py), (self.x2, self.y2), (bx - px, by - py)),
                     self.width, self.color),
        )


@dataclass(frozen=True, slots=True)
class Label:
    """Single-line text anchored by its complete measured horizontal bounds."""

    x: float
    y: float
    text: str
    _: KW_ONLY
    style: TextStyle | None = None
    align: str = "left"

    def __post_init__(self) -> None:
        for name in ("x", "y"):
            object.__setattr__(self, name, _finite_number(getattr(self, name), name))
        if not isinstance(self.text, str) or any(char in self.text for char in "\r\n\t"):
            raise ValueError("text must be a single line without tabs")
        if self.style is not None and not isinstance(self.style, TextStyle):
            raise ValueError("style must be a TextStyle or None")
        if self.align not in ("left", "center", "right"):
            raise ValueError("align must be left, center or right")

    def _command(self, context: LayoutContext) -> Text:
        style = self.style if self.style is not None else context.style.body
        text = context.fonts.normalize_text(self.text)
        bounds = context.fonts.measure(text, style).bounds
        offset = bounds.width if self.align == "right" else bounds.width / 2 if self.align == "center" else 0
        return Text(self.x - bounds.x - offset, self.y, text, style)


@dataclass(frozen=True, slots=True, init=False)
class Figure:
    """An indivisible grid frame containing immutable local-point artwork."""

    col_span: int
    rows: int
    items: tuple
    block_id: str

    def __init__(self, col_span, rows, *items, block_id=""):
        _frame(col_span, rows, block_id)
        if any(not isinstance(item, (Line, Polyline, Rectangle, Circle, Text, Arrow, Label, TextBox, TextDiamond,
                                     Connector)) for item in items):
            raise ValueError("items must contain drawing commands, Arrow, Label, TextBox, TextDiamond or Connector")
        object.__setattr__(self, "col_span", col_span)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "block_id", block_id)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        source = self.block_id or "Figure"
        width, height = _frame_size(context, self.col_span, self.rows, available_width, source)
        figure = Scope(Kind.FIGURE, data={"block_id": self.block_id})
        commands = []
        for index, item in enumerate(self.items):
            try:
                expanded = (item._commands() if isinstance(item, (Arrow, Connector)) else
                            item._commands(context, source) if isinstance(item, (TextBox, TextDiamond)) else
                            (item._command(context),) if isinstance(item, Label) else (item,))
            except FontError as exc:
                raise FontError(f"{source}.items[{index}]: {exc}") from exc
            for command in expanded:
                self._check_bounds(command, context, width, height, source, index)
            commands.extend(_figure_item(expanded, item, figure, index))
        return MeasuredBlock(width,
                             context.profile.grid.pitch_y,
                             (LayoutPart(self.rows, tuple(commands)),),
                             keep_together=True, block_id=self.block_id)

    @staticmethod
    def _check_bounds(command, context, width, height, source, index):
        try:
            bounds = command_bounds(command, context.fonts)
        except FontError as exc:
            raise FontError(f"{source}.items[{index}]: {exc}") from exc
        if (bounds.x < -TOLERANCE or bounds.y < -TOLERANCE or bounds.right > width + TOLERANCE
                or bounds.bottom > height + TOLERANCE):
            horizontal = bounds.x < 0 or bounds.right > width
            raise LayoutOverflowError(
                f"{source}.items[{index}]: bounds {bounds} exceed figure frame (0, 0, {width}, {height})",
                block_id=source, needed=bounds.width if horizontal else bounds.height,
                available=width if horizontal else height)


@dataclass(frozen=True, slots=True)
class Image:
    """Snapshot one PNG/JPEG at measurement time and fit it without distortion.

    ``width_pt`` and ``height_pt`` request an exact physical size. Without a
    grid frame, width is reserved exactly and height rounds up to complete rows.
    An optional ``col_span``/``rows`` pair supplies a larger alignment frame;
    physical dimensions are never shrunk to fit. Pixel rounding is limited to
    half a pixel on each axis after EXIF orientation.

    EXIF orientation is applied before sizing. RGB/RGBA PNG snapshot bytes keep
    alpha and are independent of the source path after measurement. Repeating
    measurement reads the current file again, without changing an earlier result.
    """

    path: Path
    _: KW_ONLY
    col_span: int | None = None
    rows: int | None = None
    width_pt: float | None = None
    height_pt: float | None = None
    align: str = "center"
    valign: str = "middle"
    block_id: str = ""

    def __post_init__(self) -> None:
        if (self.col_span is None) != (self.rows is None):
            raise ValueError("col_span and rows must be specified together")
        if (self.width_pt is None) != (self.height_pt is None):
            raise ValueError("width_pt and height_pt must be specified together")
        if self.col_span is None and self.width_pt is None:
            raise ValueError("Image requires col_span/rows or width_pt/height_pt")
        if self.col_span is not None:
            _frame(self.col_span, self.rows, self.block_id)
        else:
            _identifier(self.block_id)
        if self.width_pt is not None:
            for name in ("width_pt", "height_pt"):
                value = _finite_number(getattr(self, name), name)
                if value <= 0:
                    raise ValueError(f"{name} must be positive")
                object.__setattr__(self, name, value)
        try:
            object.__setattr__(self, "path", Path(self.path))
        except TypeError as exc:
            raise ValueError("path must be a filesystem path") from exc
        if self.align not in ("left", "center", "right"):
            raise ValueError("align must be left, center or right")
        if self.valign not in ("top", "middle", "bottom"):
            raise ValueError("valign must be top, middle or bottom")

    def _snapshot(self) -> tuple[bytes, int, int]:
        try:
            data = self.path.read_bytes()
            with PILImage.open(BytesIO(data)) as source:
                if source.format not in ("PNG", "JPEG"):
                    raise ValueError("only PNG and JPEG are supported")
                if getattr(source, "n_frames", 1) != 1:
                    raise ValueError("only single-frame images are supported")
                source.verify()
            with PILImage.open(BytesIO(data)) as source:
                source.load()
                with ImageOps.exif_transpose(source) as oriented:
                    alpha = "A" in oriented.getbands() or "transparency" in oriented.info
                    with oriented.convert("RGBA" if alpha else "RGB") as normalized:
                        output = BytesIO()
                        normalized.save(output, format="PNG")
                        return output.getvalue(), normalized.width, normalized.height
        except (OSError, ValueError, SyntaxError, PILImage.DecompressionBombError) as exc:
            raise ValueError(f"{self.block_id or 'Image'}: cannot load {self.path}: {exc}") from exc

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        source = self.block_id or "Image"
        if self.col_span is not None:
            width, height = _frame_size(context, self.col_span, self.rows, available_width, source)
            rows = self.rows
        else:
            available_width = measurement_inputs(context, available_width)
            width = self.width_pt
            rows = context.profile.grid.rows_for(self.height_pt)
            height = _finite_number(rows * context.profile.grid.pitch_y, "frame height")
            if width > available_width + TOLERANCE:
                raise LayoutOverflowError(
                    f"{source}: physical width {width:g} exceeds available width {available_width:g}",
                    block_id=source, needed=width, available=available_width)
        if self.width_pt is not None:
            for dimension, needed, available in (("width", self.width_pt, width),
                                                ("height", self.height_pt, height)):
                if needed > available + TOLERANCE:
                    raise LayoutOverflowError(
                        f"{source}: physical {dimension} {needed:g} exceeds frame {available:g}",
                        block_id=source, needed=needed, available=available)
        data, image_width, image_height = self._snapshot()
        if self.width_pt is None:
            scale = min(width / image_width, height / image_height)
            image_width, image_height = image_width * scale, image_height * scale
        else:
            lower = max(_finite_number((image_width - .5) / self.width_pt, "pixel scale"),
                        _finite_number((image_height - .5) / self.height_pt, "pixel scale"))
            upper = min(_finite_number((image_width + .5) / self.width_pt, "pixel scale"),
                        _finite_number((image_height + .5) / self.height_pt, "pixel scale"))
            if lower > upper:
                raise ValueError(f"{source}: physical aspect ratio differs by more than half a pixel per axis")
            image_width, image_height = self.width_pt, self.height_pt
        x = {"left": 0, "center": (width - image_width) / 2, "right": width - image_width}[self.align]
        y = {"top": 0, "middle": (height - image_height) / 2, "bottom": height - image_height}[self.valign]
        command = RasterImage(x, y, image_width, image_height, data,
                              tag=Tag(Role.IMAGE, (), {"block_id": self.block_id}))
        return MeasuredBlock(width, context.profile.grid.pitch_y,
                             (LayoutPart(rows, (command,)),), keep_together=True,
                             block_id=self.block_id)


@dataclass(frozen=True, slots=True)
class PdfFigure:
    """One page of a vector PDF fitted into a grid frame, drawn as vector artwork.

    The frame is ``col_span`` columns by ``rows`` rows. The page's crop box is
    scaled to fit it with its aspect kept, enlarged or reduced, and placed by
    ``align`` (left, center, right) and ``valign`` (top, middle, bottom).
    ``page`` counts from 0. ``data`` is snapshotted and read when the figure
    is made: a ValueError says when it is not a readable PDF, is encrypted,
    has no such page, the page is rotated or its box has no area.

    The PDF draws the page as one form XObject (``pdfpages``). A grid Excel
    sheet cannot hold PDF artwork: it shows ``preview`` (PNG or JPEG bytes
    of the same picture, its pixel size within half a pixel per axis of the
    page's aspect) over the same box, or else only a frame there, recorded
    as the fallback "pdf_figure_frame" (refused by ``strict=True``).
    """

    col_span: int
    rows: int
    data: bytes
    _: KW_ONLY
    page: int = 0
    preview: bytes | None = None
    align: str = "center"
    valign: str = "middle"
    block_id: str = ""
    _box: tuple[float, float, float, float] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _frame(self.col_span, self.rows, self.block_id)
        source = self.block_id or "PdfFigure"
        if not isinstance(self.data, (bytes, bytearray, memoryview)) or not self.data:
            raise ValueError(f"{source}: data must contain nonempty PDF bytes")
        object.__setattr__(self, "data", bytes(self.data))
        if isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 0:
            raise ValueError(f"{source}: page must be a nonnegative integer")
        if self.align not in ("left", "center", "right"):
            raise ValueError("align must be left, center or right")
        if self.valign not in ("top", "middle", "bottom"):
            raise ValueError("valign must be top, middle or bottom")
        try:
            box = pdf_page_box(self.data, self.page)
        except ValueError as exc:
            raise ValueError(f"{source}: {exc}") from exc
        object.__setattr__(self, "_box", box)
        if self.preview is not None:
            if not isinstance(self.preview, (bytes, bytearray, memoryview)) or not self.preview:
                raise ValueError(f"{source}: preview must contain nonempty PNG or JPEG bytes or be None")
            object.__setattr__(self, "preview", bytes(self.preview))
            _check_preview(self.preview, box[2], box[3], source)

    def measure(self, context: LayoutContext, available_width: float) -> MeasuredBlock:
        source = self.block_id or "PdfFigure"
        width, height = _frame_size(context, self.col_span, self.rows, available_width, source)
        _, _, box_width, box_height = self._box
        scale = min(width / box_width, height / box_height)
        drawn_width, drawn_height = box_width * scale, box_height * scale
        x = {"left": 0, "center": (width - drawn_width) / 2, "right": width - drawn_width}[self.align]
        y = {"top": 0, "middle": (height - drawn_height) / 2, "bottom": height - drawn_height}[self.valign]
        command = VectorPage(x, y, drawn_width, drawn_height, self.data, self.page, preview=self.preview,
                             tag=Tag(Role.IMAGE, (), {"block_id": self.block_id}))
        return MeasuredBlock(width, context.profile.grid.pitch_y,
                             (LayoutPart(self.rows, (command,)),), keep_together=True,
                             block_id=self.block_id)


def _check_preview(data: bytes, box_width: float, box_height: float, source: str) -> None:
    """A preview is one PNG or JPEG image whose pixels have the page's aspect within half a pixel per axis."""
    try:
        with PILImage.open(BytesIO(data)) as image:
            found, frames = image.format, getattr(image, "n_frames", 1)
            image.verify()
        with PILImage.open(BytesIO(data)) as image:
            image.load()
            pixels_x, pixels_y = image.size
    except (OSError, ValueError, SyntaxError, PILImage.DecompressionBombError) as exc:
        raise ValueError(f"{source}: preview is not a readable image: {exc}") from exc
    if found not in ("PNG", "JPEG", "MPO") or frames != 1:
        raise ValueError(f"{source}: preview must be a single PNG or JPEG image, not {found}")
    lower = max((pixels_x - .5) / box_width, (pixels_y - .5) / box_height)
    upper = min((pixels_x + .5) / box_width, (pixels_y + .5) / box_height)
    if lower > upper:
        raise ValueError(f"{source}: preview of {pixels_x} x {pixels_y} px differs from the page's aspect "
                         f"({box_width:g} x {box_height:g} pt) by more than half a pixel per axis")


# The kind of a drawing command written by the user (a "raw" figure item).
_RAW_KINDS = ((Line, "line"), (Polyline, "polyline"), (Rectangle, "rect"), (Circle, "circle"), (Text, "text"))


def _figure_item(commands: tuple, item, figure: Scope, index: int) -> tuple:
    """Tag the commands of one figure item as figure artwork, never as anything else.

    Every command of a figure is ``Role.FIGURE``, its text included, whatever
    tag a user-written command carried: only Table, Rule and SideRule lines
    become cell borders in a grid Excel sheet.
    """
    if isinstance(item, Arrow):
        data, leaves = {"kind": "arrow"}, [{"part": "shaft"}, {"part": "head"}]
    elif isinstance(item, Connector):
        data, leaves = {"kind": "connector"}, [{"part": "path"}, {"part": "head"}]
    elif isinstance(item, (TextBox, TextDiamond)):
        data = {"kind": "textbox", "rounded": item.rounded} if isinstance(item, TextBox) else {"kind": "diamond"}
        leaves = [{"part": "outline"}, *({"part": "text", "line": line} for line in range(len(commands) - 1))]
    elif isinstance(item, Label):
        data, leaves = {"kind": "label", "align": item.align}, [{"part": "text"}]
    else:
        kind = next(name for command_type, name in _RAW_KINDS if isinstance(item, command_type))
        data, leaves = {"kind": kind, "raw": True}, [{}]
    path = (figure, Scope(Kind.FIGURE_ITEM, index=index, data=data))
    return tuple(tagged((command,), Tag(Role.FIGURE, path, leaf))[0]
                 for command, leaf in zip(commands, leaves, strict=True))


def _lines(lines) -> tuple[str, ...]:
    if isinstance(lines, str) or not isinstance(lines, (tuple, list)):
        raise ValueError("lines must be a tuple or list of strings")
    lines = tuple(lines)
    if not lines:
        raise ValueError("lines must contain at least one line")
    for line in lines:
        if not isinstance(line, str) or not line or any(char in line for char in "\r\n\t"):
            raise ValueError("each line must be a nonempty single line without tabs")
    return lines


def _text_shape(item) -> None:
    """Validate the frame, lines, text settings and outline of a TextBox or TextDiamond."""
    for name in ("x", "y", "width", "height", "padding"):
        object.__setattr__(item, name, _finite_number(getattr(item, name), name))
    for name in ("width", "height"):
        if getattr(item, name) <= 0:
            raise ValueError(f"{name} must be positive")
    if item.padding < 0:
        raise ValueError("padding must be nonnegative")
    object.__setattr__(item, "lines", _lines(item.lines))
    if item.style is not None and not isinstance(item.style, TextStyle):
        raise ValueError("style must be a TextStyle or None")
    if item.leading is not None:
        leading = _finite_number(item.leading, "leading")
        if leading <= 0:
            raise ValueError("leading must be positive")
        object.__setattr__(item, "leading", leading)
    outline = Rectangle(item.x, item.y, item.width, item.height, item.stroke_width, item.color)
    for name in ("stroke_width", "color"):
        object.__setattr__(item, name, getattr(outline, name))


def _centred_lines(item, context: LayoutContext, source: str, cx: float, cy: float, height: float,
                   half_width) -> tuple[Text, ...]:
    """The lines of *item* centred on (cx, cy), ``leading`` apart (1.4 × the size by default).

    The lines from the first ascent to the last descent must fit in *height*; a line whose ink reaches *dy* from cy
    must fit in ``2 × half_width(dy)``. Nothing is shrunk: a line that does not fit is a LayoutOverflowError.
    """
    style = item.style if item.style is not None else context.style.body
    leading = item.leading if item.leading is not None else 1.4 * style.size
    texts = [context.fonts.normalize_text(line) for line in item.lines]
    metrics = [context.fonts.measure(text, style) for text in texts]
    span = metrics[0].ascent + (len(texts) - 1) * leading + metrics[-1].descent
    if span > height + TOLERANCE:
        raise LayoutOverflowError(f"{source}: {len(texts)} lines need {span:g} pt of height; {height:g} pt is free",
                                  block_id=source, needed=span, available=height)
    first = cy - span / 2 + metrics[0].ascent
    commands = []
    for index, (text, metric) in enumerate(zip(texts, metrics)):
        y = first + index * leading
        bounds = metric.bounds
        free = max(0.0, half_width(max(abs(y - metric.ascent - cy), abs(y + metric.descent - cy))))
        if bounds.width > 2 * free + TOLERANCE:
            raise LayoutOverflowError(f"{source}: line {index} needs {bounds.width:g} pt; {2 * free:g} pt is free",
                                      block_id=source, needed=bounds.width, available=2 * free)
        commands.append(Text(cx - bounds.x - bounds.width / 2, y, text, style))
    return tuple(commands)


@dataclass(frozen=True, slots=True)
class TextBox:
    """A flowchart step: a box at (x, y) with its lines of text centred in it.

    ``rounded`` makes it a terminal, its ends rounded with half the shorter side. The lines must fit inside the box
    less ``padding`` on every side; ``leading`` is baseline to baseline (1.4 × the size by default).
    """

    x: float
    y: float
    width: float
    height: float
    lines: tuple[str, ...]
    _: KW_ONLY
    style: TextStyle | None = None
    leading: float | None = None
    padding: float = 3.0
    rounded: bool = False
    stroke_width: float = .6
    color: Color = (0, 0, 0)

    def __post_init__(self) -> None:
        _text_shape(self)
        if not isinstance(self.rounded, bool):
            raise ValueError("rounded must be a boolean")

    def _commands(self, context: LayoutContext, source: str) -> tuple:
        radius = min(self.width, self.height) / 2 if self.rounded else 0.0
        outline = Rectangle(self.x, self.y, self.width, self.height, self.stroke_width, self.color,
                            corner_radius=radius)
        inner = self.width - 2 * self.padding
        texts = _centred_lines(self, context, source, self.x + self.width / 2, self.y + self.height / 2,
                               self.height - 2 * self.padding, lambda dy: inner / 2)
        return (outline, *texts)


@dataclass(frozen=True, slots=True)
class TextDiamond:
    """A flowchart decision: a rhombus in the box (x, y, width, height) with its lines of text centred in it.

    Each line must fit inside the rhombus at the height of its ink, ``padding`` from the outline measured across,
    and the lines together within the height less ``padding`` above and below.
    """

    x: float
    y: float
    width: float
    height: float
    lines: tuple[str, ...]
    _: KW_ONLY
    style: TextStyle | None = None
    leading: float | None = None
    padding: float = 3.0
    stroke_width: float = .6
    color: Color = (0, 0, 0)

    def __post_init__(self) -> None:
        _text_shape(self)

    def _commands(self, context: LayoutContext, source: str) -> tuple:
        cx, cy = self.x + self.width / 2, self.y + self.height / 2
        outline = Polyline(((cx, self.y), (self.x + self.width, cy), (cx, self.y + self.height), (self.x, cy)),
                           self.stroke_width, self.color, closed=True)
        texts = _centred_lines(self, context, source, cx, cy, self.height - 2 * self.padding,
                               lambda dy: self.width / 2 * (1 - dy / (self.height / 2)) - self.padding)
        return (outline, *texts)


@dataclass(frozen=True, slots=True)
class Connector:
    """A flowchart line along ``points`` with an open arrow head at the last point, as Arrow draws it on the last
    segment. Consecutive points must differ, and the last segment must be at least ``head_length`` long."""

    points: tuple
    _: KW_ONLY
    head_length: float = 6.0
    head_width: float = 4.0
    width: float = .6
    color: Color = (0, 0, 0)

    def __post_init__(self) -> None:
        if isinstance(self.points, str) or not isinstance(self.points, (tuple, list)) or len(self.points) < 2:
            raise ValueError("points must hold at least two points")
        path = Polyline(tuple(self.points), self.width, self.color)
        if any(first == second for first, second in zip(path.points, path.points[1:])):
            raise ValueError("consecutive points must differ")
        start, end = path.points[-2], path.points[-1]
        head = Arrow(start.x, start.y, end.x, end.y, head_length=self.head_length, head_width=self.head_width,
                     width=self.width, color=self.color)
        object.__setattr__(self, "points", path.points)
        for name in ("head_length", "head_width", "width", "color"):
            object.__setattr__(self, name, getattr(head, name))

    def _commands(self) -> tuple[Polyline, Polyline]:
        start, end = self.points[-2], self.points[-1]
        head = Arrow(start.x, start.y, end.x, end.y, head_length=self.head_length, head_width=self.head_width,
                     width=self.width, color=self.color)._commands()[1]
        return Polyline(self.points, self.width, self.color), head
