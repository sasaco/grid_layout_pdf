"""Diagnostics for report layout and font resolution."""


class LayoutError(Exception):
    """A report cannot be laid out or rendered as requested."""


class LayoutOverflowError(LayoutError):
    """A block cannot fit its available layout region."""

    def __init__(
        self,
        message: str,
        *,
        block_id: str = "",
        needed: float | None = None,
        available: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.block_id = block_id
        self.needed = needed
        self.available = available


class FontError(LayoutError):
    """A requested font or glyph cannot be resolved."""
