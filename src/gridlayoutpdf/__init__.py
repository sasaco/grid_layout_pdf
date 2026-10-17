"""Grid-aligned PDF calculation reports."""

from .blocks import Heading, PageBreak, Paragraph, Spacer
from .bounds import command_bounds
from .containers import At, Columns, KeepTogether, Stack
from .diagnostics import layout_trace
from .document import Document, PageDecoration, PageSection
from .equations import Equation, EquationAnchors, EquationGroup, MathBlock, wrap_math
from .errors import FontError, LayoutError, LayoutOverflowError
from .figures import Arrow, Figure, Image, Label
from .fonts import FontFace, FontRegistry, TextMetrics
from .geometry import GridSpec, Point, Rect
from .layout import Block, LayoutContext, LayoutPart, MeasuredBlock, measure_block
from .math import (
    BreakHint, Delimited, Fraction, Literal, MathBox, MathNode, Operator,
    Root, Row, Script, Symbol, as_math,
)
from .profiles import (
    A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE, PageProfile, derived_profile,
)
from .renderers.reportlab import render_pdf
from .rotation import QuarterTurn
from .scene import Color, Command, Line, Polyline, RasterImage, Rectangle, ScenePage, Text
from .styles import ReportStyle, TextStyle
from .tables import Cell, Table
from .text import TextLine, fit_tracking, wrap_text


__all__ = [
    "A3_LANDSCAPE_REFERENCE", "A4_PORTRAIT_REFERENCE", "PageProfile", "derived_profile",
    "Point", "Rect", "GridSpec", "TextStyle", "ReportStyle",
    "FontRegistry", "FontFace", "TextMetrics", "FontError", "LayoutError", "LayoutOverflowError",
    "Block", "LayoutContext", "LayoutPart", "MeasuredBlock", "measure_block",
    "Document", "PageDecoration", "PageSection", "Paragraph", "Heading", "Spacer", "PageBreak",
    "Stack", "Columns", "KeepTogether", "At", "QuarterTurn", "Cell", "Table", "Figure", "Image", "Arrow", "Label",
    "MathNode", "MathBox", "Literal", "Symbol", "Operator", "Row", "Fraction", "Root", "Script",
    "Delimited", "BreakHint", "as_math", "MathBlock", "Equation", "EquationGroup", "EquationAnchors",
    "wrap_math", "TextLine", "wrap_text", "fit_tracking",
    "Color", "Command", "Text", "Line", "Polyline", "Rectangle", "RasterImage", "ScenePage",
    "command_bounds", "render_pdf", "layout_trace",
]
