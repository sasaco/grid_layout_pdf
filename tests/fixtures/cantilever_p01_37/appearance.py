"""Fixture-only math nodes for the two original glyph treatments the library has no node for.

Both wrap the library's own Literal measurement and change only how its glyphs
are drawn, never where a line or cell sits: the page and table positions come
from the library parts on the page grid (FR-027). This module never opens the
source PDF or an expected transcript.
"""

from dataclasses import dataclass, replace
import math

from gridlayoutpdf import Literal, MathBox, Text, command_bounds


@dataclass(frozen=True)
class Sheared:
    """Draw a math node's glyphs with the original's synthetic italic (Text.shear_x).

    The box and the tags are the node's own; the glyph matrix leans (p1: the D
    of the dead loads, shear 0.342). With ``script_gap`` (pt from the base's
    advance to its script, the original's explicit gap) the advance widens by
    what the library Script does not already leave (``script_em`` em), so a
    following script clears the leaning glyph.
    """

    node: object
    shear_x: float
    script_gap: float | None = None
    script_em: float = .1

    def __post_init__(self):
        if not math.isfinite(self.shear_x) or (self.script_gap is not None
                                                and (not math.isfinite(self.script_gap) or self.script_gap < 0)):
            raise ValueError("Sheared needs a finite shear and a nonnegative script gap")

    def measure(self, fonts, style):
        box = self.node.measure(fonts, style)
        extra = 0.0 if self.script_gap is None else max(0.0, self.script_gap - self.script_em * style.size)
        return replace(box, width=box.width + extra,
                       commands=tuple(replace(command, shear_x=self.shear_x)
                                      if isinstance(command, Text) else command
                                      for command in box.commands))


@dataclass(frozen=True)
class VerticalGlyph:
    """One glyph turned clockwise (quarter_turns=3) for a vertical heading (p21, p22).

    The original sets the parentheses of 「安全性（破壊）」 in a vertical
    direction while the kanji stay upright. The turned glyph's bounds (its
    command_bounds) are centred on the box of one upright character (one em
    wide, the font's ascent and descent), so the line advances like a kanji
    line. The Text keeps the tags of the library Literal it comes from.
    """

    text: str

    def measure(self, fonts, style):
        upright = Literal(self.text).measure(fonts, style)
        if len(upright.commands) != 1 or not isinstance(upright.commands[0], Text):
            raise ValueError("VerticalGlyph needs one glyph run")
        turned = replace(upright.commands[0], x=0.0, y=0.0, quarter_turns=3)
        ink = command_bounds(turned, fonts)
        metrics = fonts.measure(self.text, replace(style, tracking=0))
        em = style.size
        # Centre the turned ink on the upright em box: x in [0, em], y in [-ascent, descent].
        dx = em / 2 - (ink.x + ink.right) / 2
        dy = (metrics.descent - metrics.ascent) / 2 - (ink.y + ink.bottom) / 2
        return MathBox(em, metrics.ascent, metrics.descent, (turned.translated(dx, dy),), style.size * .25)
