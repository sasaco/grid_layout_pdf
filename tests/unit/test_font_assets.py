"""The checked-in font fixture must be usable without local system fonts."""

import hashlib
import json
from pathlib import Path
import struct

from reportlab.pdfbase.ttfonts import TTFont


FONT_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "fonts"
REQUIRED_TEXT = (
    "日本語 橋脚 計算書 σ τ φ Σ √ × ÷ ≦ ≧ ± = ＝ α β γ μ ² ³ − "
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789 ()[]{}.,:/"
)


def _manifest() -> dict:
    manifest_path = FONT_DIR / "manifest.json"
    assert manifest_path.is_file(), "Pinned test-font manifest is missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["fonts"], "At least one reproducible font is required"
    return manifest


def test_font_assets_and_licenses_match_their_pinned_hashes():
    manifest = _manifest()
    for entry in manifest["fonts"]:
        assert entry["source"]["page_url"].startswith("https://moji.or.jp/")
        assert entry["source"]["archive_url"].startswith("https://moji.or.jp/")
        assert len(entry["source"]["archive_sha256"]) == 64
        for asset in (entry, entry["license"], *entry["supporting_files"]):
            path = FONT_DIR / asset["file"]
            assert path.is_file(), f"Required test-font asset is missing: {path}"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
        assert entry["license"]["id"] == "IPA"


def test_pinned_face_has_required_japanese_latin_greek_and_math_glyphs():
    manifest = _manifest()
    assert set(REQUIRED_TEXT) <= set(manifest["required_text"])
    for entry in manifest["fonts"]:
        font = TTFont(
            "Fixture-" + entry["id"],
            str(FONT_DIR / entry["file"]),
            subfontIndex=entry["face_index"],
        )
        assert font.face.name.decode("ascii") == entry["postscript_name"]
        missing = [
            f"U+{ord(char):04X} {char}"
            for char in set(REQUIRED_TEXT)
            if not font.face.charToGlyph.get(ord(char), 0)
        ]
        assert not missing, f"Required glyphs absent from {entry['file']}: {missing}"
        assert all(font.face.charWidths[ord(char)] > 0 for char in REQUIRED_TEXT)
        # A positive width alone is insufficient: TTFont may return .notdef's width.
        assert not font.face.charToGlyph.get(0x10FFFF, 0)


def test_pinned_font_is_truetype_with_unrestricted_embedding_flags():
    for entry in _manifest()["fonts"]:
        data = (FONT_DIR / entry["file"]).read_bytes()
        assert data[:4] == b"\x00\x01\x00\x00", "Use a TrueType sfnt, not CFF"
        assert entry["face_index"] == 0  # This fixture is a standalone face, not a TTC.
        table_count = struct.unpack_from(">H", data, 4)[0]
        tables = {}
        for index in range(table_count):
            tag, _checksum, offset, length = struct.unpack_from(">4sIII", data, 12 + 16 * index)
            tables[tag] = data[offset : offset + length]
        assert b"glyf" in tables and b"loca" in tables
        assert b"CFF " not in tables and b"CFF2" not in tables
        fs_type = struct.unpack_from(">H", tables[b"OS/2"], 8)[0]
        assert fs_type == 0, "Embedding and subsetting must not be restricted"
