"""Find font files from the names stored in their TrueType name tables.

A requested name may be any Windows-platform English (0x409) or Japanese
(0x411) family name (nameID 1 or 16) or full name (nameID 4), matched exactly
after NFC normalization. The search order is the fonts bundled with this
package, then ``%WINDIR%\\Fonts``, then
``%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts``. Other operating systems search
only the bundled fonts. Nothing is read until a name is looked up.

Within the first folder that has a match, matches are tried in tiers: full
name (nameID 4), then family name (nameID 1), then typographic family name
(nameID 16). Two different faces matching in the same tier are ambiguous and
raise :class:`FontError` instead of picking one.

The bundled folder is indexed from its manifest only. A bundled file that is
missing, unreadable or does not carry its pinned names is an installation error,
never a reason to fall back to a Windows font of the same name.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
import json
import os
from pathlib import Path
import re
import struct
import sys
from typing import BinaryIO
import unicodedata

from .errors import FontError

__all__ = [
    "BUNDLED_DIRECTORY", "FONT_SUFFIXES", "FaceNames", "FontLocation", "face_names_at",
    "face_names_from", "find_font", "forget", "read_face_names", "search_directories",
]

BUNDLED_DIRECTORY = Path(__file__).resolve().with_name("font_data")
FONT_SUFFIXES = (".ttf", ".ttc", ".otf", ".otc")
_FAMILY_ID, _FULL_NAME_ID, _TYPOGRAPHIC_FAMILY_ID = 1, 4, 16
_NAME_IDS = (_FAMILY_ID, _FULL_NAME_ID, _TYPOGRAPHIC_FAMILY_ID)
_ENGLISH, _JAPANESE = 0x409, 0x411
_LANGUAGES = (_ENGLISH, _JAPANESE)
_WINDOWS_PLATFORM, _UNICODE_ENCODINGS = 3, (0, 1, 10)
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class FaceNames:
    """English and Japanese names of one face.

    ``family`` is the English family name (nameID 1), the name Windows and
    Excel use for the face; it falls back to the typographic family, the full
    name and then the Japanese names.
    """

    face_index: int
    families: tuple[str, ...]
    full_names: tuple[str, ...]
    family: str
    typographic_families: tuple[str, ...] = ()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.full_names + self.families + self.typographic_families))


@dataclass(frozen=True, slots=True)
class FontLocation:
    """A face selected by name. Bundled faces always carry their pinned SHA-256."""

    path: Path
    face_index: int
    family: str
    expected_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise ValueError("path must be an absolute Path")
        if isinstance(self.face_index, bool) or not isinstance(self.face_index, int) or self.face_index < 0:
            raise ValueError("face_index must be a nonnegative integer")
        if not isinstance(self.family, str):
            raise ValueError("family must be text")
        if self.expected_sha256 is not None and (
                not isinstance(self.expected_sha256, str) or not _SHA256.fullmatch(self.expected_sha256)):
            raise ValueError("expected_sha256 must be 64 lowercase hexadecimal digits or None")

    @property
    def bundled(self) -> bool:
        return self.expected_sha256 is not None


class _Unreadable(Exception):
    """A file in a font folder whose name table cannot be read."""


def _is_windows() -> bool:
    return sys.platform == "win32"


def _absolute(variable: str) -> Path | None:
    value = os.environ.get(variable)
    if not value:
        return None
    path = Path(value)
    # A relative value would search relative to the working directory.
    return path if path.is_absolute() else None


def search_directories() -> tuple[Path, ...]:
    """Folders searched in order; Windows folders only exist on Windows.

    ``%WINDIR%`` falls back to ``%SystemRoot%``. Unset or relative values are
    not searched.
    """
    directories = [BUNDLED_DIRECTORY]
    if _is_windows():
        windows = _absolute("WINDIR") or _absolute("SystemRoot")
        if windows is not None:
            directories.append(windows / "Fonts")
        local = _absolute("LOCALAPPDATA")
        if local is not None:
            directories.append(local / "Microsoft" / "Windows" / "Fonts")
    return tuple(directories)


@dataclass(frozen=True, slots=True)
class _BundledFont:
    file: str
    face_index: int
    family: str
    family_ja: str
    sha256: str


@cache
def _bundled_manifest() -> tuple[_BundledFont, ...]:
    """The validated manifest of the bundled fonts (cached; errors are not)."""
    try:
        data = json.loads((BUNDLED_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FontError(f"Cannot read the bundled font manifest: {exc}") from exc
    try:
        if data["schema_version"] != 1 or not isinstance(data["fonts"], list) or not data["fonts"]:
            raise ValueError("expected schema_version 1 and a nonempty fonts list")
        fonts = []
        for entry in data["fonts"]:
            font = _BundledFont(entry["file"], entry["face_index"], entry["family"],
                                entry["family_ja"], entry["sha256"])
            if (not isinstance(font.file, str) or Path(font.file).name != font.file
                    or isinstance(font.face_index, bool) or not isinstance(font.face_index, int)
                    or font.face_index < 0 or not isinstance(font.family, str) or not font.family
                    or not isinstance(font.family_ja, str) or not font.family_ja
                    or not isinstance(font.sha256, str) or not _SHA256.fullmatch(font.sha256)):
                raise ValueError(f"invalid entry {entry!r}")
            fonts.append(font)
        if len({font.file for font in fonts}) != len(fonts):
            raise ValueError("duplicate font files")
    except (KeyError, TypeError, ValueError) as exc:
        raise FontError(f"The bundled font manifest is invalid: {exc}; reinstall gridlayoutpdf") from exc
    return tuple(fonts)


def _read(handle: BinaryIO, offset: int, size: int, file_size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > file_size:
        raise _Unreadable("table falls outside the file")
    handle.seek(offset)
    data = handle.read(size)
    if len(data) != size:
        raise _Unreadable("truncated file")
    return data


def _face_offsets(handle: BinaryIO, file_size: int) -> tuple[int, ...]:
    header = _read(handle, 0, 12, file_size)
    if header[:4] != b"ttcf":
        return (0,)
    count = struct.unpack_from(">I", header, 8)[0]
    if not 0 < count <= 4096:
        raise _Unreadable(f"invalid collection face count {count}")
    return struct.unpack(f">{count}I", _read(handle, 12, 4 * count, file_size))


def _name_table(handle: BinaryIO, offset: int, file_size: int) -> bytes:
    count = struct.unpack(">H", _read(handle, offset + 4, 2, file_size))[0]
    directory = _read(handle, offset + 12, 16 * count, file_size)
    for index in range(count):
        tag, _, start, length = struct.unpack_from(">4sIII", directory, 16 * index)
        if tag == b"name":
            return _read(handle, start, length, file_size)
    raise _Unreadable("no name table")


def _names(table: bytes) -> dict[tuple[int, int], tuple[str, ...]]:
    """Decoded Windows Unicode names keyed by (name ID, language ID)."""
    if len(table) < 6:
        raise _Unreadable("truncated name table")
    _, count, storage = struct.unpack_from(">HHH", table)
    if 6 + 12 * count > len(table):
        raise _Unreadable("truncated name records")
    found: dict[tuple[int, int], list[str]] = {}
    for index in range(count):
        platform, encoding, language, name_id, length, offset = struct.unpack_from(
            ">HHHHHH", table, 6 + 12 * index)
        if (platform != _WINDOWS_PLATFORM or encoding not in _UNICODE_ENCODINGS
                or language not in _LANGUAGES or name_id not in _NAME_IDS):
            continue
        raw = table[storage + offset:storage + offset + length]
        if len(raw) != length or length % 2:
            continue
        try:
            text = unicodedata.normalize("NFC", raw.decode("utf-16-be"))
        except UnicodeDecodeError:
            continue
        if text and text not in found.setdefault((name_id, language), []):
            found[(name_id, language)].append(text)
    return {key: tuple(values) for key, values in found.items()}


def _face_names(face_index: int, table: bytes) -> FaceNames:
    names = _names(table)

    def collect(name_id: int) -> tuple[str, ...]:
        return tuple(dict.fromkeys(text for language in _LANGUAGES
                                   for text in names.get((name_id, language), ())))

    preferred = [names.get((name_id, language), ())
                 for language in _LANGUAGES for name_id in (_FAMILY_ID, _TYPOGRAPHIC_FAMILY_ID, _FULL_NAME_ID)]
    family = next((values[0] for values in preferred if values), "")
    return FaceNames(face_index, collect(_FAMILY_ID), collect(_FULL_NAME_ID), family,
                     collect(_TYPOGRAPHIC_FAMILY_ID))


def face_names_from(handle: BinaryIO) -> tuple[FaceNames, ...]:
    """Read the names of every face from an open binary font file.

    Raises :class:`FontError` when the data is not a readable sfnt.
    """
    try:
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        return tuple(_face_names(index, _name_table(handle, offset, file_size))
                     for index, offset in enumerate(_face_offsets(handle, file_size)))
    except (OSError, _Unreadable, struct.error) as exc:
        raise FontError(f"Cannot read font names: {exc}") from exc


def face_names_at(handle: BinaryIO, face_index: int) -> FaceNames:
    """Read the names of one face, ignoring damage in the collection's other faces.

    Raises :class:`FontError` when that face is absent or unreadable.
    """
    try:
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        offsets = _face_offsets(handle, file_size)
        if not 0 <= face_index < len(offsets):
            raise _Unreadable(f"face {face_index} is absent ({len(offsets)} faces)")
        return _face_names(face_index, _name_table(handle, offsets[face_index], file_size))
    except (OSError, _Unreadable, struct.error) as exc:
        raise FontError(f"Cannot read font names: {exc}") from exc


def read_face_names(path: str | Path) -> tuple[FaceNames, ...]:
    """Read the English and Japanese names of every face in a font file.

    Raises :class:`FontError` when the file is not a readable sfnt.
    """
    path = Path(path)
    try:
        with path.open("rb") as handle:
            return face_names_from(handle)
    except OSError as exc:
        raise FontError(f"Cannot read font names from {path}: {exc}") from exc
    except FontError as exc:
        raise FontError(f"Cannot read font names from {path}: {exc.__cause__ or exc}") from exc


def _readable_faces(path: Path) -> tuple[tuple[FaceNames, ...], bool]:
    """Faces that can be read from one file, and whether any face was damaged."""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        faces, damaged = [], False
        for index, offset in enumerate(_face_offsets(handle, file_size)):
            try:
                faces.append(_face_names(index, _name_table(handle, offset, file_size)))
            except (_Unreadable, struct.error):
                damaged = True
        return tuple(faces), damaged


@dataclass(frozen=True, slots=True)
class _Entry:
    path: Path
    face_index: int
    family: str
    full_names: tuple[str, ...]
    families: tuple[str, ...]
    typographic_families: tuple[str, ...]
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class _Index:
    entries: tuple[_Entry, ...]
    unreadable: tuple[str, ...]


_FileKey = tuple[Path, int, int, int]
_INDEXES: dict[Path, tuple[tuple[_FileKey, ...], _Index]] = {}


def forget() -> None:
    """Drop every cached folder index so the next lookup reads the folders again."""
    _INDEXES.clear()


def _font_files(directory: Path) -> tuple[_FileKey, ...]:
    try:
        with os.scandir(directory) as entries:
            files = []
            for entry in entries:
                if not entry.name.lower().endswith(FONT_SUFFIXES):
                    continue
                try:
                    if not entry.is_file():
                        continue
                    status = entry.stat()
                    files.append((Path(entry.path), status.st_size, status.st_mtime_ns, entry.inode()))
                except OSError:
                    files.append((Path(entry.path), -1, -1, -1))
    except (FileNotFoundError, NotADirectoryError):
        return ()
    except OSError as exc:
        raise FontError(f"Cannot list font folder {directory}: {exc}") from exc
    return tuple(sorted(files, key=lambda item: item[0].name.lower()))


def _entries(path: Path, faces: tuple[FaceNames, ...], sha256: str | None = None) -> list[_Entry]:
    return [_Entry(path, face.face_index, face.family, face.full_names, face.families,
                   face.typographic_families, sha256) for face in faces]


def _index(directory: Path) -> _Index:
    """Names of every font file in one folder, rebuilt when the files change."""
    files = _font_files(directory)
    cached = _INDEXES.get(directory)
    if cached is not None and cached[0] == files:
        return cached[1]
    entries: list[_Entry] = []
    unreadable: list[str] = []
    for path, _, _, _ in files:
        try:
            faces, damaged = _readable_faces(path)
            resolved = path.resolve()
        except (OSError, _Unreadable, struct.error):
            unreadable.append(path.name)
            continue
        if damaged:
            unreadable.append(path.name)
        entries.extend(_entries(resolved, faces))
    index = _Index(tuple(entries), tuple(unreadable))
    _INDEXES[directory] = (files, index)
    return index


def _bundled_index() -> _Index:
    """The bundled faces listed in the manifest, each checked for its names."""
    entries: list[_Entry] = []
    for font in _bundled_manifest():
        path = BUNDLED_DIRECTORY / font.file
        try:
            faces, damaged = _readable_faces(path)
        except (OSError, _Unreadable, struct.error) as exc:
            raise FontError(f"The bundled font {font.file} is missing or unreadable ({exc}); "
                            "reinstall gridlayoutpdf") from exc
        face = next((face for face in faces if face.face_index == font.face_index), None)
        if damaged or face is None or not {font.family, font.family_ja} <= set(face.names):
            raise FontError(f"The bundled font {font.file} does not carry its pinned names "
                            f"{font.family!r} and {font.family_ja!r}; reinstall gridlayoutpdf")
        entries.extend(_entries(path.resolve(), (face,), font.sha256))
    return _Index(tuple(entries), ())


def _describe(entry: _Entry) -> str:
    names = ", ".join(entry.full_names) or entry.family
    return f"{entry.path.name} face {entry.face_index} (full names: {names})"


_TIERS = ("full_names", "families", "typographic_families")


def _select(name: str, directory: Path, index: _Index) -> _Entry | None:
    for tier in _TIERS:
        matches = [entry for entry in index.entries if name in getattr(entry, tier)]
        if len(matches) == 1:
            return matches[0]
        if matches:
            candidates = "; ".join(_describe(entry) for entry in matches)
            raise FontError(f"Font name {name!r} is ambiguous in {directory}: {candidates}; "
                            "use a full name that identifies one face")
    return None


def _bundled_names() -> str:
    try:
        names = (name for font in _bundled_manifest() for name in (font.family, font.family_ja))
        return ", ".join(dict.fromkeys(names))
    except FontError:
        return "unavailable"


def find_font(name: str) -> FontLocation:
    """Locate the face whose English or Japanese name is ``name``."""
    if not isinstance(name, str) or not name.strip():
        raise FontError(f"Font name must be nonempty text: {name!r}")
    name = unicodedata.normalize("NFC", name)
    directories = search_directories()
    skipped: list[str] = []
    for directory in directories:
        bundled = directory == BUNDLED_DIRECTORY
        index = _bundled_index() if bundled else _index(directory)
        skipped.extend(index.unreadable)
        entry = _select(name, directory, index)
        if entry is None:
            continue
        return FontLocation(entry.path, entry.face_index, entry.family, entry.sha256)
    if _is_windows():
        searched = ", ".join(str(directory) for directory in directories[1:])
        scope = (f"the bundled fonts and {searched}" if searched else
                 "the bundled fonts only (WINDIR, SystemRoot and LOCALAPPDATA give no absolute font folder)")
        if searched and _absolute("WINDIR") is None and _absolute("SystemRoot") is None:
            scope += " (WINDIR and SystemRoot are unset or relative, so the system font folder was not searched)"
    else:
        scope = "only the bundled fonts (other operating systems do not search system fonts)"
    detail = ""
    if skipped:
        shown = ", ".join(skipped[:5]) + (", ..." if len(skipped) > 5 else "")
        detail = f"; {len(skipped)} unreadable font files were skipped ({shown})"
    raise FontError(f"Font {name!r} was not found in {scope}; bundled names: {_bundled_names()}{detail}")
