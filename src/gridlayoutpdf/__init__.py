"""Grid-aligned PDF calculation reports."""

from .blocks import Heading, PageBreak, Paragraph, Spacer
from .bounds import command_bounds
from .cell_content import CellLines
from .containers import At, Columns, Indent, KeepTogether, KeepWithNext, Leading, PreferKeepTogether, SideRule, Stack
from .diagnostics import layout_trace
from .document import Document, PageDecoration, PageSection
from .equations import Equation, EquationAnchors, EquationGroup, MathBlock, wrap_math
from .errors import FontError, LayoutError, LayoutOverflowError
from .figures import Arrow, Connector, Figure, Image, Label, TextBox, TextDiamond
from .fonts import FontFace, FontRegistry, TextMetrics
from .geometry import GridSpec, Point, Rect
from .layout import Block, LayoutContext, LayoutPart, MeasuredBlock, measure_block
from .math import (
    BreakHint, Delimited, Fraction, Literal, MathBox, MathNode, Operator,
    Root, Row, Script, Symbol, TermStop, as_math,
)
from .profiles import (
    A3_LANDSCAPE_REFERENCE, A4_PORTRAIT_REFERENCE, PageProfile, derived_profile,
)
from .renderers.reportlab import render_pdf
from .rotation import QuarterTurn
from .scene import Circle, Color, Command, Line, Polyline, RasterImage, Rectangle, ScenePage, Text
from .styles import Insets, ReportStyle, TextStyle
from .tables import Cell, Table, proportional_spans
from .text import TextLine, fit_tracking, wrap_text


__all__ = [
    "A3_LANDSCAPE_REFERENCE", "A4_PORTRAIT_REFERENCE", "PageProfile", "derived_profile",
    "Point", "Rect", "GridSpec", "TextStyle", "ReportStyle", "Insets",
    "FontRegistry", "FontFace", "TextMetrics", "FontError", "LayoutError", "LayoutOverflowError",
    "Block", "LayoutContext", "LayoutPart", "MeasuredBlock", "measure_block",
    "Document", "PageDecoration", "PageSection", "Paragraph", "Heading", "Spacer", "PageBreak",
    "Stack", "Columns", "KeepTogether", "KeepWithNext", "PreferKeepTogether", "Indent", "Leading", "SideRule",
    "At", "QuarterTurn", "Cell", "CellLines", "Table", "proportional_spans", "Figure", "Image", "Arrow", "Label", "TextBox", "TextDiamond", "Connector",
    "MathNode", "MathBox", "Literal", "Symbol", "Operator", "Row", "Fraction", "Root", "Script",
    "Delimited", "BreakHint", "TermStop", "as_math", "MathBlock", "Equation", "EquationGroup", "EquationAnchors",
    "wrap_math", "TextLine", "wrap_text", "fit_tracking",
    "Color", "Command", "Text", "Line", "Polyline", "Rectangle", "Circle", "RasterImage", "ScenePage",
    "command_bounds", "render_pdf", "layout_trace",
]
