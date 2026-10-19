"""Test-only builders for small TrueType variants of the pinned IPAex font.

The helpers rebuild sfnt files from their tables so tests can give a font new
names, gather faces into a collection, or change one metric without touching
the checked-in font files.
"""

from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_FONT = ROOT / "tests" / "fixtures" / "fonts" / "ipaexm.ttf"
WINDOWS_ENGLISH, WINDOWS_JAPANESE = 0x409, 0x411


def _checksum(raw: bytes) -> int:
    raw = bytes(raw) + b"\x00" * ((-len(raw)) % 4)
    return sum(struct.unpack(f">{len(raw) // 4}I", raw)) & 0xFFFFFFFF


def read_tables(data: bytes, offset: int = 0) -> dict[bytes, bytes]:
    """Return the tables of one standalone sfnt in directory order."""
    count = struct.unpack_from(">H", data, offset + 4)[0]
    tables = {}
    for index in range(count):
        tag, _, start, length = struct.unpack_from(">4sIII", data, offset + 12 + 16 * index)
        tables[tag] = data[start:start + length]
    return tables


def name_table(records) -> bytes:
    """Build a format-0 name table of Windows Unicode BMP records.

    ``records`` holds ``(name_id, language_id, text)`` tuples.
    """
    encoded = [(name_id, language, text.encode("utf-16-be"))
               for name_id, language, text in sorted(records, key=lambda item: (item[1], item[0]))]
    header = struct.pack(">HHH", 0, len(encoded), 6 + 12 * len(encoded))
    directory, strings = b"", b""
    for name_id, language, raw in encoded:
        directory += struct.pack(">HHHHHH", 3, 1, language, name_id, len(raw), len(strings))
        strings += raw
    return header + directory + strings


def names(family: str, *, full: str | None = None, japanese: str | None = None,
          typographic: str | None = None) -> bytes:
    """Name records for one face: family, full name and optional extras."""
    records = [(1, WINDOWS_ENGLISH, family), (2, WINDOWS_ENGLISH, "Regular"),
               (4, WINDOWS_ENGLISH, full or family),
               (6, WINDOWS_ENGLISH, "GLPTest-%08X" % zlib.crc32(family.encode("utf-8")))]
    if japanese is not None:
        records += [(1, WINDOWS_JAPANESE, japanese), (4, WINDOWS_JAPANESE, japanese)]
    if typographic is not None:
        records.append((16, WINDOWS_ENGLISH, typographic))
    return name_table(records)


def _directory(tables: dict[bytes, bytes], version: bytes, base: int):
    """Table directory and padded table data placed at ``base`` in the file."""
    count = len(tables)
    power = 1 << (count.bit_length() - 1)
    header = version + struct.pack(">HHHH", count, power * 16, power.bit_length() - 1, count * 16 - power * 16)
    entries, body = b"", b""
    cursor = base
    for tag in sorted(tables):
        raw = tables[tag]
        entries += struct.pack(">4sIII", tag, _checksum(raw), cursor + len(body), len(raw))
        body += raw + b"\x00" * ((-len(raw)) % 4)
    return header + entries, body


def build_font(tables: dict[bytes, bytes], *, version: bytes = b"\x00\x01\x00\x00") -> bytes:
    """Assemble a standalone sfnt with valid checksums."""
    tables = dict(tables)
    head = bytearray(tables[b"head"])
    struct.pack_into(">I", head, 8, 0)
    tables[b"head"] = bytes(head)
    directory, body = _directory(tables, version, 12 + 16 * len(tables))
    data = bytearray(directory + body)
    head_offset = next(struct.unpack_from(">I", data, 12 + 16 * index + 8)[0]
                       for index, tag in enumerate(sorted(tables)) if tag == b"head")
    struct.pack_into(">I", data, head_offset + 8, (0xB1B0AFBA - _checksum(bytes(data))) & 0xFFFFFFFF)
    return bytes(data)


def build_collection(faces: list[dict[bytes, bytes]]) -> bytes:
    """Assemble a TrueType collection whose faces do not share tables.

    Table checksums are computed, but head.checkSumAdjustment is left as copied;
    the font loaders used here do not verify it.
    """
    header_size = 12 + 4 * len(faces)
    directory_sizes = [12 + 16 * len(tables) for tables in faces]
    data_start = header_size + sum(directory_sizes)
    directories, bodies, offsets = b"", b"", []
    for tables in faces:
        offsets.append(header_size + len(directories))
        directory, body = _directory(tables, b"\x00\x01\x00\x00", data_start + len(bodies))
        directories += directory
        bodies += body
    header = b"ttcf" + struct.pack(">HHI", 1, 0, len(faces)) + b"".join(struct.pack(">I", item) for item in offsets)
    return header + directories + bodies


def fixture_tables() -> dict[bytes, bytes]:
    return read_tables(FIXTURE_FONT.read_bytes())


def renamed(family: str, **kwargs) -> dict[bytes, bytes]:
    """Tables of the pinned font under a new name."""
    return {**fixture_tables(), b"name": names(family, **kwargs)}


def write_font(path: Path, tables: dict[bytes, bytes], **kwargs) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_font(tables, **kwargs))
    return path


def widened_capital_a(tables: dict[bytes, bytes], extra_units: int = 64) -> dict[bytes, bytes]:
    """Widen U+0041's advance without changing any other glyph."""
    from reportlab.pdfbase.ttfonts import TTFont

    glyph = TTFont("glp-test-original-fixture", str(FIXTURE_FONT)).face.charToGlyph[ord("A")]
    hmtx = bytearray(tables[b"hmtx"])
    advance = struct.unpack_from(">H", hmtx, 4 * glyph)[0]
    struct.pack_into(">H", hmtx, 4 * glyph, advance + extra_units)
    return {**tables, b"hmtx": bytes(hmtx)}


def zero_units_per_em(tables: dict[bytes, bytes]) -> dict[bytes, bytes]:
    head = bytearray(tables[b"head"])
    struct.pack_into(">H", head, 18, 0)
    return {**tables, b"head": bytes(head)}
