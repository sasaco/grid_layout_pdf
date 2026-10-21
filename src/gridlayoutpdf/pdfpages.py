"""One page of a vector PDF: reading it with pypdf and embedding it as a form XObject.

The page's content becomes the stream of one form XObject whose ``BBox`` is
the page's crop box, so the artwork stays vector and is clipped to that box.
The objects the page's resources reach (fonts, images, nested forms ...) are
copied with their encoded bytes and filters unchanged. Every object is named
from the SHA-256 of the PDF bytes, so one PDF drawn several times in a
document is written once, and the same pages give the same bytes.

Only the page's content is drawn: annotations, form fields and the document
structure are not. Rotated (``/Rotate``) and encrypted PDFs are refused.
"""

from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import zlib

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import (
    ArrayObject, DictionaryObject, IndirectObject, NullObject, PdfObject, StreamObject,
)
from reportlab.pdfbase.pdfdoc import PDFObject, PDFObjectReference, format as pdf_format, xObjectName


_READ_ERRORS = (PyPdfError, ValueError, KeyError, TypeError, AttributeError, IndexError, OSError,
                RecursionError, zlib.error)
_STREAM_KEYS_DROPPED = ("/Length",)  # recomputed from the copied bytes


def _page(data: bytes, page: int):
    """Return the parsed page; every failure is a ValueError that says why."""
    if isinstance(page, bool) or not isinstance(page, int) or page < 0:
        raise ValueError("page must be a nonnegative integer")
    try:
        reader = PdfReader(BytesIO(data))
        encrypted = reader.is_encrypted
    except _READ_ERRORS as exc:
        raise ValueError(f"data is not a readable PDF: {exc}") from exc
    if encrypted:
        raise ValueError("data is an encrypted PDF")
    try:
        count = len(reader.pages)
    except _READ_ERRORS as exc:
        raise ValueError(f"data is not a readable PDF: {exc}") from exc
    if page >= count:
        raise ValueError(f"the PDF has no page {page} (it has {count})")
    try:
        result = reader.pages[page]
        rotation = int(result.get("/Rotate", 0) or 0)
    except _READ_ERRORS as exc:
        raise ValueError(f"data is not a readable PDF: {exc}") from exc
    if rotation % 360:
        raise ValueError(f"page {page} is rotated by {rotation} degrees; draw it unrotated")
    return result


def _box(page) -> tuple[float, float, float, float]:
    try:
        x0, y0, x1, y1 = (float(value) for value in page.cropbox)
    except _READ_ERRORS as exc:
        raise ValueError(f"the page box is not readable: {exc}") from exc
    left, bottom, width, height = min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
    if not width > 0 or not height > 0 or not all(map(_finite, (left, bottom, width, height))):
        raise ValueError("the page box has no area")
    return left, bottom, width, height


def _finite(value: float) -> bool:
    return value - value == 0


def _contents(page) -> bytes:
    """The page's decoded content streams joined by line feeds (b"" when it has none)."""
    try:
        contents = page.get("/Contents")
        if contents is None:
            return b""
        contents = contents.get_object()
        streams = contents if isinstance(contents, ArrayObject) else [contents]
        return b"\n".join(stream.get_object().get_data() for stream in streams)
    except _READ_ERRORS as exc:
        raise ValueError(f"the page content is not readable: {exc}") from exc


def pdf_page_box(data: bytes, page: int = 0) -> tuple[float, float, float, float]:
    """Return ``(left, bottom, width, height)`` of a page's crop box in PDF pt.

    ``page`` counts from 0. A ValueError says why ``data`` cannot be drawn:
    not a readable PDF, encrypted, no such page, a rotated page, a box of no
    area or unreadable content.
    """
    found = _page(data, page)
    box = _box(found)
    _contents(found)
    return box


# --- ReportLab objects that keep pypdf's serialization ---------------------------------------


def _raw(value: PdfObject) -> bytes:
    buffer = BytesIO()
    value.write_to_stream(buffer)
    return buffer.getvalue()


class _Value(PDFObject):
    """A scalar (number, name, string, boolean, null) as written by pypdf."""

    def __init__(self, data: bytes) -> None:
        self.data = data

    def format(self, document) -> bytes:
        return self.data


class _Dictionary(PDFObject):
    def __init__(self) -> None:
        self.items: list[tuple[bytes, object]] = []

    def format(self, document, extra: bytes = b"") -> bytes:
        return b"<<" + b"".join(key + b" " + pdf_format(value, document) + b"\n"
                                for key, value in self.items) + extra + b">>"


class _Array(PDFObject):
    def __init__(self) -> None:
        self.items: list[object] = []

    def format(self, document) -> bytes:
        return b"[" + b" ".join(pdf_format(value, document) for value in self.items) + b"]"


class _Stream(PDFObject):
    """A stream whose bytes are written as they are, under its own filters."""

    __RefOnly__ = 1

    def __init__(self) -> None:
        self.dictionary = _Dictionary()
        self.data = b""

    def format(self, document) -> bytes:
        length = b"/Length " + str(len(self.data)).encode()
        return self.dictionary.format(document, length) + b"\nstream\n" + self.data + b"\nendstream\n"


class _Copier:
    """Copy pypdf objects into a ReportLab document under names made from the PDF's digest."""

    def __init__(self, document, prefix: str) -> None:
        self.document = document
        self.prefix = prefix

    def value(self, value):
        if isinstance(value, IndirectObject):
            return self.reference(value)
        if isinstance(value, DictionaryObject):  # a stream read from a file is always an indirect object
            result = _Dictionary()
            self.fill_dictionary(result, value)
            return result
        if isinstance(value, ArrayObject):
            result = _Array()
            result.items = [self.value(item) for item in value]
            return result
        return _Value(_raw(NullObject() if value is None else value))

    def fill_dictionary(self, result: _Dictionary, value: DictionaryObject, dropped=()) -> None:
        result.items = [(_raw(key), self.value(item)) for key, item in value.items() if key not in dropped]

    def reference(self, reference: IndirectObject) -> PDFObjectReference:
        name = f"{self.prefix}.{reference.idnum}.{reference.generation}"
        if name in self.document.idToObject:
            return PDFObjectReference(name)
        target = reference.get_object()
        if isinstance(target, StreamObject):
            stream = _Stream()
            self.document.Reference(stream, name)  # registered first: the object may refer back to itself
            self.fill_dictionary(stream.dictionary, target, _STREAM_KEYS_DROPPED)
            # pypdf keeps a stream's bytes as read, still encoded, in _data (its write_to_stream writes them).
            stream.data = target._data
        elif isinstance(target, DictionaryObject):
            dictionary = _Dictionary()
            self.document.Reference(dictionary, name)
            self.fill_dictionary(dictionary, target)
        elif isinstance(target, ArrayObject):
            array = _Array()
            self.document.Reference(array, name)
            array.items = [self.value(item) for item in target]
        else:
            self.document.Reference(_Value(_raw(NullObject() if target is None else target)), name)
        return PDFObjectReference(name)


def embed_pdf_page(canvas, data: bytes, page: int = 0) -> tuple[str, tuple[float, float, float, float]]:
    """Register one page as a form XObject of ``canvas``'s document.

    Return the form's name for ``canvas.doForm`` and the page box
    ``(left, bottom, width, height)``. A page registered before is reused.
    """
    digest = sha256(data).hexdigest()[:32]
    prefix = f"PdfFigure.{digest}"
    name = f"{prefix}.page{page}"
    found = _page(data, page)
    box = _box(found)
    document = canvas._doc  # ReportLab's document; forms are registered on it under xObjectName
    if xObjectName(name) in document.idToObject:
        return name, box
    content = _contents(found)
    copier = _Copier(document, prefix)
    try:
        resources = found.get("/Resources")
        form = _Stream()
        left, bottom, width, height = box
        dictionary = form.dictionary
        dictionary.items = [
            (b"/Type", _Value(b"/XObject")), (b"/Subtype", _Value(b"/Form")), (b"/FormType", _Value(b"1")),
            (b"/BBox", _Value(b"[" + b" ".join(_number(value) for value in
                                               (left, bottom, left + width, bottom + height)) + b"]")),
            (b"/Resources", copier.value(resources) if resources is not None else _Dictionary()),
        ]
        group = found.get("/Group")
        if group is not None:
            dictionary.items.append((b"/Group", copier.value(group)))
        dictionary.items.append((b"/Filter", _Value(b"/FlateDecode")))
        form.data = zlib.compress(content)
    except _READ_ERRORS as exc:
        raise ValueError(f"the page resources are not readable: {exc}") from exc
    document.Reference(form, xObjectName(name))
    return name, box


def _number(value: float) -> bytes:
    """Write a box value exactly, without an exponent: the shortest decimal that reads back as ``value``."""
    text = format(Decimal(repr(value)), "f")
    return (text.rstrip("0").rstrip(".") if "." in text else text).encode()
