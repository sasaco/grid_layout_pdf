"""Fonts resolved by name and the shared text measuring path."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import struct
import unicodedata

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont

from .errors import FontError
from .fontfinder import FontLocation, face_names_at, find_font, forget
from .geometry import Rect
from .styles import TextStyle, _finite_number


@dataclass(frozen=True, slots=True)
class FontFace:
    """A resolved face: the requested name, its file and the PDF font name.

    ``family`` is the face's English family name (nameID 1), the name Windows
    and Excel use; ``name`` is the name the caller asked for.
    """

    name: str
    path: Path
    face_index: int
    sha256: str
    pdf_name: str
    family: str = ""


@dataclass(frozen=True, slots=True)
class TextMetrics:
    """Advance and visual bounds in pt, relative to the text run's baseline."""

    width: float
    ascent: float
    descent: float
    ink_bounds: Rect | None = None

    def __post_init__(self) -> None:
        for name in ("width", "ascent", "descent"):
            value = _finite_number(getattr(self, name), name)
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
            object.__setattr__(self, name, value)
        if self.ink_bounds is not None and not isinstance(self.ink_bounds, Rect):
            raise ValueError("ink_bounds must be a Rect or None")

    @property
    def bounds(self) -> Rect:
        """Union of the advance/typographic rectangle and actual glyph ink."""
        if self.ink_bounds is None:
            return Rect(0, -self.ascent, self.width, self.ascent + self.descent)
        left = min(0, self.ink_bounds.x)
        top = min(-self.ascent, self.ink_bounds.y)
        right = max(self.width, self.ink_bounds.right)
        bottom = max(self.descent, self.ink_bounds.bottom)
        return Rect(left, top, right - left, bottom - top)


GlyphBox = tuple[int, int, int, int]


def _read_glyph_boxes(font: TTFont) -> tuple[GlyphBox | None, ...]:
    """Read TrueType glyf headers using ReportLab's already resolved loca table."""
    face = font.face
    data = face.get_table("glyf")
    positions = face.glyphPos
    if len(positions) != face.numGlyphs + 1:
        raise ValueError("Invalid glyph location count")
    boxes: list[GlyphBox | None] = []
    for start, end in zip(positions, positions[1:]):
        if not 0 <= start <= end <= len(data):
            raise ValueError("Glyph location falls outside the glyf table")
        if start == end:
            boxes.append(None)
            continue
        if end - start < 10:
            raise ValueError("Truncated glyph header")
        contours, left, bottom, right, top = struct.unpack_from(">hhhhh", data, start)
        if left > right or bottom > top:
            raise ValueError("Invalid glyph bounding box")
        boxes.append((left, bottom, right, top) if contours else None)
    if any(not 0 <= glyph < len(boxes) for glyph in face.charToGlyph.values()):
        raise ValueError("Character map refers to an absent glyph")
    return tuple(boxes)


# Glyph boxes depend only on the font bytes, which the PDF name pins by SHA-256.
_GLYPH_BOXES: dict[str, tuple[GlyphBox | None, ...]] = {}


def _load_face(name: str, location: FontLocation) -> FontFace:
    """Read, verify and register one located face with ReportLab."""
    path, face_index = location.path, location.face_index
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise FontError(f"Cannot read font {name!r} from {path}: {exc}") from exc
    signature = data[:4]
    if signature not in (b"\x00\x01\x00\x00", b"true", b"ttcf"):
        raise FontError(f"Unsupported font format for {name!r} (TrueType outlines are required): {path}")
    digest = sha256(data).hexdigest()
    if location.expected_sha256 is not None and digest != location.expected_sha256:
        raise FontError(f"The bundled font {path.name} does not match its pinned SHA-256; "
                        "reinstall gridlayoutpdf")
    # A folder index may predate a replaced file; trust only the bytes read now.
    try:
        names = face_names_at(BytesIO(data), face_index)
    except FontError as exc:
        forget()
        raise FontError(f"Cannot read font {name!r} from {path} face {face_index}: {exc}") from exc
    if name not in names.names:
        forget()
        raise FontError(f"Font {name!r} is no longer named in {path} face {face_index}; "
                        "the font file changed after it was indexed")
    pdf_name = f"GLP_{digest}_f{face_index}"
    registered = pdf_name in pdfmetrics.getRegisteredFontNames()
    try:
        if registered:
            font = pdfmetrics.getFont(pdf_name)
        else:
            font = TTFont(pdf_name, BytesIO(data), subfontIndex=face_index, shapable=False)
        boxes = _GLYPH_BOXES.get(pdf_name)
        if boxes is None:
            boxes = _read_glyph_boxes(font)
    except (
        TTFError, ValueError, KeyError, IndexError, EOFError, struct.error, ArithmeticError
    ) as exc:
        raise FontError(f"Cannot load font {name!r}, face {face_index}, {path}: {exc}") from exc
    if not registered:
        # ReportLab also aliases by face.name, even when fontName differs.
        font.face.name = pdf_name.encode("ascii")
        pdfmetrics.registerFont(font)
    _GLYPH_BOXES[pdf_name] = boxes
    return FontFace(name, path, face_index, digest, pdf_name, location.family)


class FontRegistry:
    """Resolve font names to bundled or Windows font files on first use.

    ``TextStyle.font`` holds a family or full name, in English or Japanese,
    from the font's name table. Names are looked up by
    :func:`gridlayoutpdf.fontfinder.find_font` only when first measured or
    drawn; each registry then keeps the resolved face for that name.
    Subclasses may override :meth:`resolve` and :meth:`measure`.
    """

    def __init__(self) -> None:
        self._faces: dict[str, FontFace] = {}

    def resolve(self, name: str) -> FontFace:
        if isinstance(name, str):
            name = unicodedata.normalize("NFC", name)
        face = self._faces.get(name) if isinstance(name, str) else None
        if face is None:
            face = _load_face(name, find_font(name))
            self._faces[name] = face
        return face

    def measure(self, text: str, style: TextStyle) -> TextMetrics:
        if not isinstance(style, TextStyle):
            raise ValueError("style must be a TextStyle")
        text = self.normalize_text(text)
        face = self.resolve(style.font)
        boxes = _GLYPH_BOXES.get(face.pdf_name)
        if boxes is None:
            raise FontError(f"Font {style.font!r} resolved to {face.pdf_name!r}, which FontRegistry did "
                            "not load; a subclass's resolve must return a face from FontRegistry.resolve")
        font = pdfmetrics.getFont(face.pdf_name)
        scale = style.size / font.face.unitsPerEm
        cursor = 0.0
        ink_extents: tuple[float, float, float, float] | None = None
        for index, character in enumerate(text):
            codepoint = ord(character)
            glyph = font.face.charToGlyph.get(codepoint, 0)
            if not glyph:
                raise FontError(
                    f"Font {style.font!r} is missing U+{codepoint:04X} ({character!r})"
                )
            if unicodedata.category(character).startswith("M"):
                raise FontError(
                    f"Font {style.font!r}: unsupported combining character "
                    f"U+{codepoint:04X} ({character!r}) after NFC normalization"
                )
            if index:
                cursor += style.tracking
            box = boxes[glyph]
            if box is not None:
                xmin, ymin, xmax, ymax = box
                left, top = cursor + xmin * scale, -ymax * scale
                right, bottom = cursor + xmax * scale, -ymin * scale
                if ink_extents is not None:
                    left = min(left, ink_extents[0])
                    top = min(top, ink_extents[1])
                    right = max(right, ink_extents[2])
                    bottom = max(bottom, ink_extents[3])
                ink_extents = left, top, right, bottom
            cursor += (font.face.charWidths[codepoint] / 1000) * style.size
        if ink_extents is None:
            ink_bounds = Rect(0, 0, 0, 0)
        else:
            left, top, right, bottom = ink_extents
            ink_bounds = Rect(left, top, right - left, bottom - top)
        return TextMetrics(
            font.stringWidth(text, style.size) + max(0, len(text) - 1) * style.tracking,
            max(0, (font.face.ascent / 1000) * style.size, -ink_bounds.y),
            max(0, (-font.face.descent / 1000) * style.size, ink_bounds.bottom),
            ink_bounds,
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize composable marks identically before measuring and drawing."""
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        return unicodedata.normalize("NFC", text)


_DEFAULT_FONTS: FontRegistry | None = None


def default_fonts() -> FontRegistry:
    """The registry shared by calls that omit ``fonts``; created on first use."""
    global _DEFAULT_FONTS
    if _DEFAULT_FONTS is None:
        _DEFAULT_FONTS = FontRegistry()
    return _DEFAULT_FONTS
