"""Grid Excel output (FR-021): tagged pages mapped to a standard-library SpreadsheetML writer (ADR-0001)."""

from ._map import (
    FALLBACK_KINDS, SHIFT_REASONS, XlsxError, XlsxFallback, XlsxResult, XlsxSheet, XlsxShift, XlsxStrictError,
    render_xlsx,
)

__all__ = ["FALLBACK_KINDS", "SHIFT_REASONS", "XlsxError", "XlsxFallback", "XlsxResult", "XlsxSheet", "XlsxShift",
           "XlsxStrictError", "render_xlsx"]
