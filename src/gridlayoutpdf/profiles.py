"""Measured paper references and derived grids, all dimensions in pt."""

from dataclasses import dataclass
import math

from .geometry import GridSpec, Rect, _finite


@dataclass(frozen=True)
class PageProfile:
    """Paper and its top-origin placement grid, with a body row interval."""

    name: str
    width: float
    height: float
    grid: GridSpec
    body_start_row: int = 0
    body_end_row: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        for name in ("width", "height"):
            value = getattr(self, name)
            _finite(value, name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if not isinstance(self.grid, GridSpec):
            raise ValueError("grid must be a GridSpec")
        grid_rect = Rect(
            self.grid.origin_x,
            self.grid.origin_y,
            self.grid.columns * self.grid.pitch_x,
            self.grid.rows * self.grid.pitch_y,
        )
        if not Rect(0, 0, self.width, self.height).contains(grid_rect):
            raise ValueError("grid must be wholly inside the paper")
        start_row = self.body_start_row
        end_row = self.grid.rows if self.body_end_row is None else self.body_end_row
        if isinstance(start_row, bool) or not isinstance(start_row, int):
            raise ValueError("body_start_row must be an integer")
        if isinstance(end_row, bool) or not isinstance(end_row, int):
            raise ValueError("body_end_row must be an integer")
        if not 0 <= start_row < end_row <= self.grid.rows:
            raise ValueError("body rows must satisfy 0 <= start < end <= grid.rows")
        object.__setattr__(self, "body_end_row", end_row)

    @property
    def body_rect(self) -> Rect:
        """The body area in pt; the end row is an exclusive cell boundary."""
        end_row = self.grid.rows if self.body_end_row is None else self.body_end_row
        return Rect(
            self.grid.origin_x,
            self.grid.y(self.body_start_row),
            self.grid.columns * self.grid.pitch_x,
            (end_row - self.body_start_row) * self.grid.pitch_y,
        )


A4_PORTRAIT_REFERENCE = PageProfile(
    "A4_PORTRAIT_REFERENCE", 595, 842,
    GridSpec(50.88, 54.598, 16.08, 15.48, 30, 47),
)

A3_LANDSCAPE_REFERENCE = PageProfile(
    "A3_LANDSCAPE_REFERENCE", 1191, 842,
    GridSpec(50.88, 54.598, 16.08, 15.48, 67, 47),
)


def derived_profile(name: str, width: float, height: float) -> PageProfile:
    """Derive full cells with fixed pitch, 61.72 pt right/59.842 pt bottom margins.

    Remaining space is added to the right and bottom margins. These generated
    profiles do not claim measurements from an original reference PDF.
    """
    for field, value in (("width", width), ("height", height)):
        _finite(value, field)
        if value <= 0:
            raise ValueError(f"{field} must be positive")
    reference = A4_PORTRAIT_REFERENCE.grid
    columns = _full_cells(width, reference.origin_x, reference.pitch_x, 61.72)
    rows = _full_cells(height, reference.origin_y, reference.pitch_y, 59.842)
    if columns < 1 or rows < 1:
        raise ValueError("paper must fit at least one whole grid cell and its margins")
    return PageProfile(
        name, width, height,
        GridSpec(
            reference.origin_x, reference.origin_y,
            reference.pitch_x, reference.pitch_y, columns, rows,
        ),
    )


def _full_cells(length: float, origin: float, pitch: float, margin: float) -> int:
    """Floor the available interval, correcting only float boundary rounding."""
    count = math.floor((length - origin - margin) / pitch)
    if math.fsum((origin, (count + 1) * pitch, margin)) <= length:
        count += 1
    elif math.fsum((origin, count * pitch, margin)) > length:
        count -= 1
    return count
