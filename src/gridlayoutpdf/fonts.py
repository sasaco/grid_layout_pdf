"""Explicit font files and the shared text measuring path."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import struct
import unicodedata

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont

from .errors import FontError
from .geometry import Rect
from .styles import TextStyle, _finite_number


@dataclass(frozen=True, slots=True)
class FontFace:
    name: str
    path: Path
    face_index: int
    sha256: str
    pdf_name: str


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


class FontRegistry:
    """Resolve named fonts without searching the operating system."""

    def __init__(self) -> None:
        self._faces: dict[str, FontFace] = {}
        self._glyph_boxes: dict[str, tuple[GlyphBox | None, ...]] = {}

    def register(self, name: str, path: str | Path, face_index: int = 0) -> FontFace:
        if not isinstance(name, str) or not name.strip():
            raise FontError("Font name must be nonempty text")
        if isinstance(face_index, bool) or not isinstance(face_index, int) or face_index < 0:
            raise FontError(f"Invalid font face index: {face_index!r}")
        try:
            path = Path(path).resolve()
            data = path.read_bytes()
        except (TypeError, ValueError, OSError) as exc:
            raise FontError(f"Cannot read font {name!r} from {path!s}: {exc}") from exc
        signature = data[:4]
        if signature not in (b"\x00\x01\x00\x00", b"true", b"ttcf"):
            raise FontError(f"Unsupported font format for {name!r}: {path}")
        if signature == b"ttcf":
            count = struct.unpack_from(">I", data, 8)[0] if len(data) >= 12 else 0
        else:
            count = 1
        if face_index >= count:
            raise FontError(f"Font face {face_index} is absent from {path}")
        digest = sha256(data).hexdigest()
        pdf_name = f"GLP_{digest}_f{face_index}"
        if name in self._faces:
            previous = self._faces[name]
            if (previous.sha256, previous.face_index) != (digest, face_index):
                raise FontError(f"Font name {name!r} is already registered to a different face")
            return previous
        registered = pdf_name in pdfmetrics.getRegisteredFontNames()
        try:
            if registered:
                font = pdfmetrics.getFont(pdf_name)
            else:
                font = TTFont(pdf_name, BytesIO(data), subfontIndex=face_index, shapable=False)
            boxes = self._glyph_boxes.get(pdf_name)
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
        face = FontFace(name, path, face_index, digest, pdf_name)
        self._glyph_boxes[pdf_name] = boxes
        self._faces[name] = face
        return face

    def resolve(self, name: str) -> FontFace:
        if not isinstance(name, str) or name not in self._faces:
            raise FontError(f"Unknown font name: {name!r}")
        return self._faces[name]

    def measure(self, text: str, style: TextStyle) -> TextMetrics:
        if not isinstance(style, TextStyle):
            raise ValueError("style must be a TextStyle")
        text = self.normalize_text(text)
        face = self.resolve(style.font)
        font = pdfmetrics.getFont(face.pdf_name)
        boxes = self._glyph_boxes[face.pdf_name]
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
