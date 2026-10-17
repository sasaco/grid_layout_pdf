"""ReportLab drawing boundary: convert top-origin coordinates exactly once."""

import os
from io import BytesIO
from pathlib import Path
import tempfile

from PIL import Image as PILImage
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader

from ..bounds import command_bounds
from ..fonts import FontRegistry
from ..errors import FontError, LayoutOverflowError
from ..geometry import Rect
from ..scene import Circle, Line, Polyline, RasterImage, Rectangle, ScenePage, Text, _text_matrix


def _grid_commands(page: ScenePage) -> tuple[Line, ...]:
    grid = page.profile.grid
    color = (0.84, 0.87, 0.9)
    return tuple(
        Line(grid.x(col), grid.y(0), grid.x(col), grid.y(grid.rows), 0.96, color)
        for col in range(grid.columns + 1)
    ) + tuple(
        Line(grid.x(0), grid.y(row), grid.x(grid.columns), grid.y(row), 0.96, color)
        for row in range(grid.rows + 1)
    )


def _draw(canvas: Canvas, command, height: float, fonts: FontRegistry) -> None:
    canvas.saveState()
    try:
        if isinstance(command, RasterImage):
            canvas.drawImage(ImageReader(BytesIO(command.data)), command.x,
                             height - command.y - command.height,
                             command.width, command.height, mask="auto")
            return
        if isinstance(command, Text):
            canvas.setFillColorRGB(0, 0, 0)
            text = canvas.beginText(command.x, height - command.y)
            if command.quarter_turns or command.shear_x:
                # PDF text matrices use y upwards; the scene uses y downwards.
                a, b, c, d = _text_matrix(command.quarter_turns, command.shear_x)
                text.setTextTransform(a, -b, -c, d, command.x, height - command.y)
            text.setFont(fonts.resolve(command.style.font).pdf_name, command.style.size)
            text.setCharSpace(command.style.tracking)
            text.setHorizScale(100)
            text.setTextRenderMode(0)
            text.setRise(0)
            text.textOut(fonts.normalize_text(command.text))
            canvas.drawText(text)
            return
        if not isinstance(command, (Line, Polyline, Rectangle, Circle)):
            raise ValueError(f"Unsupported drawing command: {type(command).__name__}")
        area = isinstance(command, (Rectangle, Circle))
        canvas.setStrokeColorRGB(*command.color)
        canvas.setLineWidth(command.stroke_width if area else command.width)
        canvas.setLineCap(0)
        canvas.setLineJoin(1)
        canvas.setDash(list(getattr(command, "dash", ())))
        if area and command.fill is not None:
            canvas.setFillColorRGB(*command.fill)
        paint = {"stroke": int(command.stroke), "fill": int(command.fill is not None)} if area else {}
        if isinstance(command, Line):
            canvas.line(command.x1, height - command.y1, command.x2, height - command.y2)
        elif isinstance(command, Rectangle):
            canvas.rect(command.x, height - command.y - command.height,
                        command.width, command.height, **paint)
        elif isinstance(command, Circle):
            canvas.circle(command.x, height - command.y, command.radius, **paint)
        else:
            path = canvas.beginPath()
            path.moveTo(command.points[0].x, height - command.points[0].y)
            for point in command.points[1:]:
                path.lineTo(point.x, height - point.y)
            if command.closed:
                path.close()
            canvas.drawPath(path, stroke=1, fill=0)
    finally:
        canvas.restoreState()


def _prepare(pages, fonts: FontRegistry, debug_grid: bool):
    try:
        pages = tuple(pages)
    except TypeError as exc:
        raise ValueError("pages must be a nonempty iterable of ScenePage objects") from exc
    if not pages or any(not isinstance(page, ScenePage) for page in pages):
        raise ValueError("pages must contain at least one ScenePage and no other values")
    prepared = []
    for page_number, page in enumerate(pages, start=1):
        paper = Rect(0, 0, page.profile.width, page.profile.height)
        commands = []
        groups = [("commands", page.commands)]
        if debug_grid:
            groups.insert(0, ("grid", _grid_commands(page)))
        for group, items in groups:
            for index, command in enumerate(items):
                block_id = f"page[{page_number}].{group}[{index}]"
                if isinstance(command, RasterImage):
                    try:
                        with PILImage.open(BytesIO(command.data)) as decoded:
                            if decoded.format not in ("PNG", "JPEG"):
                                raise ValueError("only PNG and JPEG are supported")
                            if getattr(decoded, "n_frames", 1) != 1:
                                raise ValueError("only single-frame images are supported")
                            decoded.verify()
                        ImageReader(BytesIO(command.data)).getRGBData()
                    except (OSError, ValueError, SyntaxError, PILImage.DecompressionBombError) as exc:
                        raise ValueError(f"{block_id}: invalid RasterImage data: {exc}") from exc
                try:
                    bounds = command_bounds(command, fonts)
                except FontError as exc:
                    raise FontError(f"{block_id}: {exc}") from exc
                except ValueError as exc:
                    raise ValueError(f"{exc} at {block_id}") from exc
                if not paper.contains(bounds):
                    horizontal = bounds.x < 0 or bounds.right > paper.right
                    raise LayoutOverflowError(
                        f"{block_id}: {type(command).__name__} bounds "
                        f"({bounds.x}, {bounds.y}, {bounds.right}, {bounds.bottom}) "
                        f"exceed paper (0, 0, {paper.right}, {paper.bottom})",
                        block_id=block_id,
                        needed=bounds.width if horizontal else bounds.height,
                        available=paper.width if horizontal else paper.height,
                    )
                commands.append(command)
        prepared.append((page.profile, tuple(commands)))
    return tuple(prepared)


def render_pdf(pages, path: str | Path, fonts: FontRegistry, debug_grid: bool = False,
               *, invariant: bool = False) -> None:
    """Validate every page, then atomically replace the destination on success.

    Text y values are baselines. Lines use butt caps and round joins. Their
    conservative half-width stroke envelope must fit on paper, as must the union
    of font extents, advance widths and actual glyph ink. Blank pages are kept;
    an empty sequence is an input error. ``invariant=True`` omits the creation
    time and document ID, so identical pages produce identical bytes.
    """
    if not isinstance(fonts, FontRegistry):
        raise ValueError("fonts must be a FontRegistry")
    if not isinstance(debug_grid, bool):
        raise ValueError("debug_grid must be a boolean")
    if not isinstance(invariant, bool):
        raise ValueError("invariant must be a boolean")
    prepared = _prepare(pages, fonts, debug_grid)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        # None keeps ReportLab's configured default when invariance is not requested.
        canvas = Canvas(str(temporary), pageCompression=1, invariant=1 if invariant else None)
        for profile, commands in prepared:
            canvas.setPageSize((profile.width, profile.height))
            for command in commands:
                _draw(canvas, command, profile.height, fonts)
            canvas.showPage()
        canvas.save()
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
