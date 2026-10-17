"""Shared input validation and whole-grid-unit rounding, all lengths in pt."""

import math
from numbers import Real


# The only absolute roundoff allowed at measurement boundaries, in pt. Shared so
# that every boundary admits the same slack instead of its own literal.
TOLERANCE = 1e-7


def _finite(value, name: str) -> None:
    """Reject non-numeric and non-finite pt values, including booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number in pt")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be a finite number in pt")


def _finite_number(value: Real, name: str) -> float:
    """Return a finite float, rejecting booleans and non-real numbers."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _integer(value, name: str, minimum: int | None = 0, *, message: str = "") -> None:
    """Require a plain integer, rejecting booleans, at or above ``minimum``.

    ``minimum`` None accepts any integer. ``message`` replaces the default text
    where a caller's established wording differs.
    """
    if (isinstance(value, bool) or not isinstance(value, int)
            or (minimum is not None and value < minimum)):
        if message:
            raise ValueError(message)
        if minimum is None:
            raise ValueError(f"{name} must be an integer")
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _identifier(block_id) -> None:
    """Require the diagnostic identifier every component carries."""
    if not isinstance(block_id, str):
        raise ValueError("block_id must be a string")


def whole_units_ceil(length: float, pitch: float) -> int:
    """Return the whole units of ``pitch`` covering a nonnegative ``length``.

    Compare actual boundaries rather than adding an epsilon that could hide a
    real overflow immediately beyond an exact boundary.
    """
    count = math.ceil(length / pitch)
    if count > 0 and (count - 1) * pitch >= length:
        count -= 1
    elif count * pitch < length:
        count += 1
    return count


def whole_units_in(start: float, end: float, pitch: float) -> int:
    """Return the complete ``pitch`` units inside the interval [start, end].

    The boundaries are compared at the coordinates used for drawing, so an
    exact boundary counts and float drift never invents or drops a unit.
    """
    count = math.floor((end - start) / pitch)
    if start + (count + 1) * pitch <= end:
        count += 1
    elif start + count * pitch > end:
        count -= 1
    return count
