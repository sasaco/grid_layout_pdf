"""Font files are found from the names stored in their name tables (FR-024)."""

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest

from gridlayoutpdf import fontfinder
from gridlayoutpdf.errors import FontError
from gridlayoutpdf.styles import ReportStyle, TextStyle

from _sfnt import FIXTURE_FONT, build_collection, renamed, write_font


ROOT = Path(__file__).resolve().parents[2]
BUNDLED = ROOT / "src" / "gridlayoutpdf" / "font_data"
WINDOWS_FONTS = Path(os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "C:/Windows") / "Fonts"
needs_ms_fonts = pytest.mark.skipif(
    sys.platform != "win32" or not (WINDOWS_FONTS / "msmincho.ttc").is_file()
    or not (WINDOWS_FONTS / "msgothic.ttc").is_file(),
    reason="MS Mincho and MS Gothic are only available from a Windows font folder",
)


@pytest.fixture
def windows(tmp_path, monkeypatch):
    """Point both Windows font folders at empty temporary directories."""
    system = tmp_path / "windir" / "Fonts"
    user = tmp_path / "localappdata" / "Microsoft" / "Windows" / "Fonts"
    system.mkdir(parents=True)
    user.mkdir(parents=True)
    monkeypatch.setenv("WINDIR", str(tmp_path / "windir"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(fontfinder, "_is_windows", lambda: True)
    return system, user


@pytest.mark.parametrize(("name", "file", "family"), [
    ("IPAexMincho", "ipaexm.ttf", "IPAexMincho"),
    ("IPAex明朝", "ipaexm.ttf", "IPAexMincho"),
    ("IPAexGothic", "ipaexg.ttf", "IPAexGothic"),
    ("IPAexゴシック", "ipaexg.ttf", "IPAexGothic"),
])
def test_bundled_fonts_are_found_by_english_and_japanese_names(name, file, family):
    location = fontfinder.find_font(name)
    assert location.path == (BUNDLED / file).resolve()
    assert location.face_index == 0
    assert location.family == family
    assert location.bundled


def test_bundled_fonts_are_unmodified_licensed_ipaex_004_01():
    manifest = json.loads((BUNDLED / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    entries = {entry["file"]: entry for entry in manifest["fonts"]}
    assert set(entries) == {"ipaexm.ttf", "ipaexg.ttf"}
    for entry in entries.values():
        assert entry["version"] == "004.01"
        assert entry["source"]["archive_url"].startswith("https://moji.or.jp/wp-content/ipafont/IPAexfont/")
        assert len(entry["source"]["archive_sha256"]) == 64
        assert entry["license"]["file"] == "IPA_Font_License_Agreement_v1.0.txt"
        for asset in (entry, entry["license"], *entry["supporting_files"]):
            path = BUNDLED / asset["file"]
            assert path.is_file(), path
            assert sha256(path.read_bytes()).hexdigest() == asset["sha256"]
    assert entries["ipaexm.ttf"]["sha256"] == sha256(FIXTURE_FONT.read_bytes()).hexdigest()
    assert entries["ipaexm.ttf"]["sha256"] == "7a306386f930fee80922f71eebf4ffe0f1ff2817da8e619230953487673d71c7"
    assert entries["ipaexg.ttf"]["source"]["archive_url"].endswith("/ipaexg00401.zip")
    assert sorted(path.name for path in BUNDLED.iterdir() if path.suffix in fontfinder.FONT_SUFFIXES) == [
        "ipaexg.ttf", "ipaexm.ttf"]


def test_read_face_names_reads_every_face_of_a_collection(tmp_path):
    path = tmp_path / "pair.ttc"
    path.write_bytes(build_collection([
        renamed("GLP Pair Alpha", japanese="GLP組甲"),
        renamed("GLP Pair Beta", full="GLP Pair Beta Regular"),
    ]))
    faces = fontfinder.read_face_names(path)
    assert [face.face_index for face in faces] == [0, 1]
    assert set(faces[0].names) == {"GLP Pair Alpha", "GLP組甲"}
    assert faces[0].family == "GLP Pair Alpha"
    assert set(faces[1].full_names) == {"GLP Pair Beta Regular"}
    assert set(faces[1].families) == {"GLP Pair Beta"}


def test_collection_face_index_comes_from_the_requested_name(windows):
    system, _ = windows
    (system / "pair.ttc").write_bytes(build_collection([
        renamed("GLP Pair Alpha", japanese="GLP組甲"),
        renamed("GLP Pair Beta", japanese="GLP組乙"),
    ]))
    assert fontfinder.find_font("GLP Pair Alpha").face_index == 0
    assert fontfinder.find_font("GLP組甲").face_index == 0
    beta = fontfinder.find_font("GLP組乙")
    assert (beta.path, beta.face_index, beta.family) == ((system / "pair.ttc").resolve(), 1, "GLP Pair Beta")
    assert not beta.bundled and beta.expected_sha256 is None


def test_typographic_family_name_16_is_accepted(windows):
    system, _ = windows
    write_font(system / "light.ttf", renamed("GLP Typo Light", full="GLP Typo Light",
                                             typographic="GLP Typo"))
    location = fontfinder.find_font("GLP Typo")
    assert location.path.name == "light.ttf"
    assert location.family == "GLP Typo Light"  # nameID 1, the name Windows and Excel use.


def test_bundled_fonts_take_priority_over_windows_fonts_with_the_same_name(windows):
    system, user = windows
    write_font(system / "impostor.ttf", renamed("IPAexMincho", japanese="IPAex明朝"))
    write_font(user / "impostor.ttf", renamed("IPAexMincho", japanese="IPAex明朝"))
    assert fontfinder.find_font("IPAex明朝").path == (BUNDLED / "ipaexm.ttf").resolve()


def test_windows_folder_is_searched_before_the_user_font_folder(windows):
    system, user = windows
    write_font(user / "shared.ttf", renamed("GLP Shared"))
    assert fontfinder.find_font("GLP Shared").path == (user / "shared.ttf").resolve()
    write_font(system / "shared.ttf", renamed("GLP Shared"))
    assert fontfinder.find_font("GLP Shared").path == (system / "shared.ttf").resolve()


def test_full_name_match_beats_a_family_match_in_the_same_folder(windows):
    system, _ = windows
    write_font(system / "regular.ttf", renamed("GLP Weight", full="GLP Weight"))
    write_font(system / "bold.ttf", renamed("GLP Weight", full="GLP Weight Bold"))
    assert fontfinder.find_font("GLP Weight").path.name == "regular.ttf"
    assert fontfinder.find_font("GLP Weight Bold").path.name == "bold.ttf"


def test_two_faces_with_the_same_name_in_one_folder_are_ambiguous(windows):
    system, _ = windows
    write_font(system / "one.ttf", renamed("GLP Twin", full="GLP Twin One"))
    write_font(system / "two.ttf", renamed("GLP Twin", full="GLP Twin Two"))
    with pytest.raises(FontError, match="ambiguous") as caught:
        fontfinder.find_font("GLP Twin")
    assert "one.ttf" in str(caught.value) and "two.ttf" in str(caught.value)
    assert "GLP Twin One" in str(caught.value) and "GLP Twin Two" in str(caught.value)
    assert fontfinder.find_font("GLP Twin Two").path.name == "two.ttf"


def test_missing_name_reports_the_searched_folders(windows):
    system, user = windows
    with pytest.raises(FontError, match="GLP Absent") as caught:
        fontfinder.find_font("GLP Absent")
    message = str(caught.value)
    assert str(system) in message and str(user) in message
    assert "IPAex明朝" in message


def test_names_must_match_exactly(windows):
    for name in ("ipaexmincho", "IPAex 明朝", "IPAexMincho "):
        with pytest.raises(FontError):
            fontfinder.find_font(name)


@pytest.mark.parametrize("name", ["", " ", None, 2])
def test_invalid_names_are_font_errors(name):
    with pytest.raises(FontError, match="name"):
        fontfinder.find_font(name)


def test_unreadable_or_damaged_files_are_skipped_and_counted(windows):
    system, _ = windows
    (system / "garbage.ttf").write_bytes(b"not a font")
    (system / "short.ttc").write_bytes(b"ttcf\x00\x01\x00\x00\x00\x00\x00\x09")
    (system / "notes.txt").write_text("GLP Found", encoding="utf-8")
    write_font(system / "found.ttf", renamed("GLP Found"))
    assert fontfinder.find_font("GLP Found").path.name == "found.ttf"
    with pytest.raises(FontError, match="2 unreadable"):
        fontfinder.find_font("GLP Elsewhere")


def test_other_operating_systems_search_only_the_bundled_fonts(windows, monkeypatch):
    system, _ = windows
    write_font(system / "windows-only.ttf", renamed("GLP Windows Only"))
    assert fontfinder.find_font("GLP Windows Only").path.name == "windows-only.ttf"
    monkeypatch.setattr(fontfinder, "_is_windows", lambda: False)
    with pytest.raises(FontError, match="only the bundled fonts"):
        fontfinder.find_font("GLP Windows Only")
    assert fontfinder.find_font("IPAexGothic").path.name == "ipaexg.ttf"


def test_search_directories_follow_the_documented_order(windows, tmp_path, monkeypatch):
    system, user = windows
    assert fontfinder.search_directories() == (BUNDLED.resolve(), system, user)
    monkeypatch.delenv("LOCALAPPDATA")
    assert fontfinder.search_directories() == (BUNDLED.resolve(), system)
    monkeypatch.setattr(fontfinder, "_is_windows", lambda: False)
    assert fontfinder.search_directories() == (BUNDLED.resolve(),)


def test_index_is_refreshed_when_a_font_is_added_to_a_folder(windows):
    system, _ = windows
    with pytest.raises(FontError):
        fontfinder.find_font("GLP Later")
    write_font(system / "later.ttf", renamed("GLP Later"))
    assert fontfinder.find_font("GLP Later").path.name == "later.ttf"


@needs_ms_fonts
@pytest.mark.parametrize(("name", "file", "index"), [
    ("MS Mincho", "msmincho.ttc", 0),
    ("ＭＳ 明朝", "msmincho.ttc", 0),
    ("MS PMincho", "msmincho.ttc", 1),
    ("ＭＳ Ｐ明朝", "msmincho.ttc", 1),
    ("MS Gothic", "msgothic.ttc", 0),
    ("ＭＳ ゴシック", "msgothic.ttc", 0),
])
def test_windows_ms_fonts_are_found_with_their_collection_face(name, file, index):
    location = fontfinder.find_font(name)
    assert location.path.name.lower() == file
    assert location.face_index == index
    assert not location.bundled


def test_text_styles_default_to_the_bundled_mincho_name():
    assert TextStyle().font == "IPAex明朝"
    style = ReportStyle()
    assert style.body.font == style.heading.font == "IPAex明朝"


def test_import_and_style_creation_do_not_open_or_search_font_files(tmp_path):
    probe = """
import sys
events = []
def hook(event, args):
    if event in ("open", "os.scandir", "os.listdir"):
        events.append((event, str(args[0]) if args else ""))
sys.addaudithook(hook)
import gridlayoutpdf
from gridlayoutpdf import Document, FontRegistry, Paragraph, ReportStyle, TextStyle
TextStyle(); TextStyle(font="MS Mincho", size=9); ReportStyle(); FontRegistry()
Document(Paragraph("x"))
paths = [item[1].lower().replace(chr(92), "/") for item in events]
bad = [path for path in paths
       if path.endswith((".ttf", ".ttc", ".otf")) or "/windows/fonts" in path or "font_data" in path]
print(repr(bad))
FontRegistry().resolve("IPAex明朝")
print(any("font_data" in item[1].replace(chr(92), "/") for item in events))
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", probe], capture_output=True, text=True,
                            encoding="utf-8", cwd=tmp_path, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["[]", "True"]  # The hook does see the later lookup.


@pytest.mark.parametrize("data", [
    b"",
    b"not a font at all",
    b"ttcf" + bytes(8),
    b"ttcf\x00\x01\x00\x00\x00\x00\x00\x01\xff\xff\xff\xff",
    b"\x00\x01\x00\x00" + bytes(8),
])
def test_read_face_names_reports_damaged_files_as_font_errors(tmp_path, data):
    path = tmp_path / "damaged.ttf"
    path.write_bytes(data)
    with pytest.raises(FontError, match="damaged.ttf"):
        fontfinder.read_face_names(path)


def test_font_without_a_name_table_is_unreadable(tmp_path):
    from _sfnt import build_font, fixture_tables

    tables = {tag: data for tag, data in fixture_tables().items() if tag != b"name"}
    path = tmp_path / "nameless.ttf"
    path.write_bytes(build_font(tables))
    with pytest.raises(FontError, match="no name table"):
        fontfinder.read_face_names(path)


def test_records_that_cannot_be_decoded_are_ignored(tmp_path):
    from _sfnt import WINDOWS_ENGLISH, build_font, fixture_tables, name_table

    table = bytearray(name_table([(1, WINDOWS_ENGLISH, "GLP Odd"), (4, WINDOWS_ENGLISH, "GLP Odd Full")]))
    # Give the second record an odd byte length so it is not valid UTF-16.
    struct_offset = 6 + 12 + 8
    table[struct_offset:struct_offset + 2] = (len("GLP Odd Full") * 2 - 1).to_bytes(2, "big")
    path = tmp_path / "odd.ttf"
    path.write_bytes(build_font({**fixture_tables(), b"name": bytes(table)}))
    (face,) = fontfinder.read_face_names(path)
    assert face.families == ("GLP Odd",) and face.full_names == ()


def test_folder_listing_failure_is_a_font_error(windows, monkeypatch):
    system, _ = windows
    real_scandir = fontfinder.os.scandir

    def scandir(path):
        if Path(path) == system:
            raise PermissionError("access denied")
        return real_scandir(path)

    monkeypatch.setattr(fontfinder.os, "scandir", scandir)
    assert fontfinder.find_font("IPAexMincho").bundled
    with pytest.raises(FontError, match="Cannot list font folder"):
        fontfinder.find_font("GLP Behind A Locked Folder")


def test_missing_font_folder_is_skipped(windows, tmp_path, monkeypatch):
    monkeypatch.setenv("WINDIR", str(tmp_path / "no-such-windows"))
    with pytest.raises(FontError, match="was not found"):
        fontfinder.find_font("GLP Nowhere")


def test_bundled_locations_carry_the_manifest_hash():
    location = fontfinder.find_font("IPAexMincho")
    assert location.expected_sha256 == "7a306386f930fee80922f71eebf4ffe0f1ff2817da8e619230953487673d71c7"


def test_unreadable_manifest_is_a_font_error(monkeypatch, tmp_path):
    monkeypatch.setattr(fontfinder, "BUNDLED_DIRECTORY", tmp_path)
    fontfinder._bundled_manifest.cache_clear()
    try:
        with pytest.raises(FontError, match="bundled font manifest"):
            fontfinder.find_font("IPAex明朝")
    finally:
        fontfinder._bundled_manifest.cache_clear()


def test_family_name_1_beats_a_typographic_family_name_16(windows):
    system, _ = windows
    write_font(system / "regular.ttf", renamed("GLP Tier", full="GLP Tier Regular"))
    write_font(system / "light.ttf", renamed("GLP Tier Light", full="GLP Tier Light", typographic="GLP Tier"))
    assert fontfinder.find_font("GLP Tier").path.name == "regular.ttf"
    assert fontfinder.find_font("GLP Tier Light").path.name == "light.ttf"


@pytest.fixture
def bundled_copy(tmp_path, monkeypatch):
    """A writable copy of the bundled folder used in place of the installed one."""
    copy = tmp_path / "font_data"
    shutil.copytree(BUNDLED, copy)
    monkeypatch.setattr(fontfinder, "BUNDLED_DIRECTORY", copy)
    fontfinder._bundled_manifest.cache_clear()
    yield copy
    fontfinder._bundled_manifest.cache_clear()


@pytest.mark.parametrize("damage", ["corrupt", "delete", "rename"])
def test_damaged_bundled_font_never_falls_back_to_a_windows_font(windows, bundled_copy, damage):
    system, _ = windows
    write_font(system / "impostor.ttf", renamed("IPAexMincho", japanese="IPAex明朝"))
    target = bundled_copy / "ipaexm.ttf"
    if damage == "corrupt":
        target.write_bytes(b"damaged")
    elif damage == "delete":
        target.unlink()
    else:
        write_font(target, renamed("GLP Not IPAex"))
    with pytest.raises(FontError, match="reinstall"):
        fontfinder.find_font("IPAex明朝")


@pytest.mark.parametrize("manifest", ["{}", "[]", '{"schema_version": 1, "fonts": [{"file": "ipaexm.ttf"}]}',
                                      '{"schema_version": 2, "fonts": []}'])
def test_invalid_bundled_manifest_is_a_font_error(bundled_copy, manifest):
    (bundled_copy / "manifest.json").write_text(manifest, encoding="utf-8")
    with pytest.raises(FontError, match="manifest"):
        fontfinder.find_font("IPAex明朝")


def test_system_root_is_used_when_windir_is_absent(windows, tmp_path, monkeypatch):
    system, user = windows
    monkeypatch.delenv("WINDIR")
    monkeypatch.setenv("SystemRoot", str(tmp_path / "windir"))
    assert fontfinder.search_directories() == (BUNDLED.resolve(), system, user)
    monkeypatch.delenv("SystemRoot")
    monkeypatch.delenv("LOCALAPPDATA")
    with pytest.raises(FontError) as caught:
        fontfinder.find_font("GLP Absent")
    assert "other operating systems" not in str(caught.value) and "WINDIR" in str(caught.value)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    with pytest.raises(FontError, match="system font folder was not searched"):
        fontfinder.find_font("GLP Absent")


def test_relative_font_folder_variables_are_not_searched(windows, tmp_path, monkeypatch):
    planted = tmp_path / "Win" / "Fonts"
    write_font(planted / "planted.ttf", renamed("GLP Planted"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WINDIR", "Win")
    monkeypatch.delenv("SystemRoot", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "Win")
    assert fontfinder.search_directories() == (BUNDLED.resolve(),)
    with pytest.raises(FontError):
        fontfinder.find_font("GLP Planted")


def test_font_location_keeps_the_bundled_hash_invariant(tmp_path):
    path = (tmp_path / "x.ttf").resolve()
    assert not fontfinder.FontLocation(path, 0, "x").bundled
    assert fontfinder.FontLocation(path, 0, "x", "a" * 64).bundled
    for arguments in ((path, 0, "x", "not-a-hash"), (path, -1, "x"), (path, True, "x"),
                      (Path("relative.ttf"), 0, "x"), ("text-path", 0, "x")):
        with pytest.raises(ValueError):
            fontfinder.FontLocation(*arguments)


def test_one_damaged_collection_face_does_not_hide_the_others(windows):
    system, _ = windows
    data = bytearray(build_collection([renamed("GLP Good Face"), renamed("GLP Bad Face")]))
    struct.pack_into(">I", data, 16, len(data) + 1000)  # The second face's offset.
    (system / "partly.ttc").write_bytes(bytes(data))
    assert fontfinder.find_font("GLP Good Face").face_index == 0
    with pytest.raises(FontError, match="1 unreadable font files were skipped [(]partly.ttc[)]"):
        fontfinder.find_font("GLP Bad Face")
    from gridlayoutpdf.fonts import FontRegistry

    fonts = FontRegistry()
    assert fonts.resolve("GLP Good Face").face_index == 0
    assert fonts.measure("A", TextStyle(font="GLP Good Face")).width > 0
    with fontfinder.Path(system / "partly.ttc").open("rb") as handle:
        with pytest.raises(FontError, match="Cannot read font names"):
            fontfinder.face_names_at(handle, 1)
        with pytest.raises(FontError, match="face 2 is absent"):
            fontfinder.face_names_at(handle, 2)


def test_unpaired_surrogate_records_are_ignored(tmp_path):
    from _sfnt import WINDOWS_ENGLISH, build_font, fixture_tables, name_table

    table = bytearray(name_table([(1, WINDOWS_ENGLISH, "GLP Pair"), (4, WINDOWS_ENGLISH, "GLP Pair Full")]))
    start = len(table) - len("GLP Pair Full") * 2
    table[start:start + 2] = b"\xd8\x00"  # A lone high surrogate.
    path = tmp_path / "surrogate.ttf"
    path.write_bytes(build_font({**fixture_tables(), b"name": bytes(table)}))
    (face,) = fontfinder.read_face_names(path)
    assert face.families == ("GLP Pair",) and face.full_names == ()


@pytest.fixture
def added(monkeypatch):
    """An empty list of added font folders for this test only.

    The change counter is restored too, so a registry that resolved a name
    while the test's folders were added drops that face afterwards.
    """
    monkeypatch.setattr(fontfinder, "_ADDED_DIRECTORIES", [])
    monkeypatch.setattr(fontfinder, "_search_changes", fontfinder._search_changes)
    return fontfinder._ADDED_DIRECTORIES


def test_added_folders_come_after_the_bundled_fonts_and_before_the_windows_folders(windows, added, tmp_path):
    system, user = windows
    first, second = tmp_path / "first", tmp_path / "second"
    fontfinder.add_directory(first)
    fontfinder.add_directory(str(second))
    assert fontfinder.search_directories() == (BUNDLED.resolve(), first, second, system, user)
    write_font(system / "shared.ttf", renamed("GLP Added Shared"))
    assert fontfinder.find_font("GLP Added Shared").path == (system / "shared.ttf").resolve()
    write_font(second / "shared.ttf", renamed("GLP Added Shared"))
    assert fontfinder.find_font("GLP Added Shared").path == (second / "shared.ttf").resolve()
    write_font(first / "shared.ttf", renamed("GLP Added Shared"))
    assert fontfinder.find_font("GLP Added Shared").path == (first / "shared.ttf").resolve()
    write_font(first / "impostor.ttf", renamed("IPAexMincho", japanese="IPAex明朝"))
    assert fontfinder.find_font("IPAex明朝").path == (BUNDLED / "ipaexm.ttf").resolve()


def test_added_folders_are_searched_on_other_operating_systems(windows, added, tmp_path, monkeypatch):
    system, _ = windows
    monkeypatch.setattr(fontfinder, "_is_windows", lambda: False)
    folder = tmp_path / "engine-fonts"
    write_font(folder / "engine.ttf", renamed("GLP Engine"))
    write_font(system / "windows-only.ttf", renamed("GLP Windows Only"))
    fontfinder.add_directory(folder)
    assert fontfinder.search_directories() == (BUNDLED.resolve(), folder)
    assert fontfinder.find_font("GLP Engine").path == (folder / "engine.ttf").resolve()
    with pytest.raises(FontError) as caught:
        fontfinder.find_font("GLP Windows Only")
    message = str(caught.value)
    assert f"the bundled fonts and {folder}" in message
    assert "other operating systems do not search system fonts" in message


def test_adding_a_folder_again_keeps_its_first_place(windows, added, tmp_path):
    system, user = windows
    first, second = tmp_path / "first", tmp_path / "second"
    for path in (first, second, str(first), first, Path(str(second))):
        fontfinder.add_directory(path)
    assert added == [first, second]
    assert fontfinder.search_directories() == (BUNDLED.resolve(), first, second, system, user)


def test_a_folder_listed_twice_is_searched_at_its_first_place(windows, added):
    system, user = windows
    fontfinder.add_directory(user)
    fontfinder.add_directory(BUNDLED.resolve())
    assert fontfinder.search_directories() == (BUNDLED.resolve(), user, system)


@pytest.mark.parametrize("path", ["fonts", "", ".", Path("fonts"), b"C:/fonts", None, 3])
def test_relative_or_non_path_folders_are_rejected(added, path):
    with pytest.raises(ValueError, match="font folder"):
        fontfinder.add_directory(path)
    with pytest.raises(ValueError, match="font folder"):
        fontfinder.remove_directory(path)
    assert added == []


def test_missing_added_folder_is_skipped_and_reported(windows, added, tmp_path):
    system, _ = windows
    missing = tmp_path / "no-such-fonts"
    not_a_folder = tmp_path / "file.ttf"
    write_font(not_a_folder, renamed("GLP Not A Folder"))
    fontfinder.add_directory(missing)
    fontfinder.add_directory(not_a_folder)
    write_font(system / "system.ttf", renamed("GLP System"))
    assert fontfinder.find_font("GLP System").path.name == "system.ttf"
    with pytest.raises(FontError, match="was not found") as caught:
        fontfinder.find_font("GLP Nowhere")
    assert str(missing) in str(caught.value)
    assert not missing.exists()
    write_font(missing / "later.ttf", renamed("GLP Later Added"))
    assert fontfinder.find_font("GLP Later Added").path == (missing / "later.ttf").resolve()


def test_collection_face_index_in_an_added_folder_comes_from_the_name(windows, added, tmp_path):
    folder = tmp_path / "engine-fonts"
    folder.mkdir()
    (folder / "pair.ttc").write_bytes(build_collection([
        renamed("GLP Added Alpha"),
        renamed("GLP Added Beta", japanese="GLP足し乙"),
    ]))
    fontfinder.add_directory(folder)
    beta = fontfinder.find_font("GLP足し乙")
    assert (beta.path, beta.face_index, beta.family) == ((folder / "pair.ttc").resolve(), 1, "GLP Added Beta")
    assert not beta.bundled


def test_removed_folder_is_no_longer_searched(windows, added, tmp_path):
    system, user = windows
    folder = tmp_path / "engine-fonts"
    write_font(folder / "engine.ttf", renamed("GLP Removed"))
    fontfinder.remove_directory(folder)  # Never added: nothing changes.
    assert added == []
    fontfinder.add_directory(folder)
    assert fontfinder.find_font("GLP Removed").path.name == "engine.ttf"
    fontfinder.remove_directory(str(folder))
    assert fontfinder.search_directories() == (BUNDLED.resolve(), system, user)
    with pytest.raises(FontError):
        fontfinder.find_font("GLP Removed")


def test_adding_a_folder_reads_nothing(tmp_path):
    folder = tmp_path / "engine-fonts"
    write_font(folder / "engine.ttf", renamed("GLP Not Read"))
    probe = """
import sys
events = []
def hook(event, args):
    if event in ("open", "os.scandir", "os.listdir", "os.stat"):
        events.append(str(args[0]) if args else "")
from gridlayoutpdf import fontfinder
sys.addaudithook(hook)
fontfinder.add_directory(sys.argv[1])
fontfinder.add_directory(sys.argv[1] + "-missing")
print(repr([path for path in events if "engine-fonts" in path]))
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", probe, str(folder)], capture_output=True,
                            text=True, encoding="utf-8", cwd=tmp_path, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["[]"]


def test_font_registry_drops_faces_resolved_before_the_folders_change(windows, added, tmp_path):
    from gridlayoutpdf.fonts import FontRegistry

    system, _ = windows
    write_font(system / "system.ttf", renamed("GLP Moved"))
    fonts = FontRegistry()
    before = fonts.resolve("GLP Moved")
    assert before.path == (system / "system.ttf").resolve()
    assert fonts.resolve("GLP Moved") is before
    folder = tmp_path / "engine-fonts"
    write_font(folder / "engine.ttf", renamed("GLP Moved"))
    fontfinder.add_directory(folder)
    after = fonts.resolve("GLP Moved")
    assert after.path == (folder / "engine.ttf").resolve()
    assert fonts.resolve("GLP Moved") is after
    fontfinder.add_directory(folder)  # Already added: the resolved face is kept.
    assert fonts.resolve("GLP Moved") is after
    fontfinder.remove_directory(folder)
    assert fonts.resolve("GLP Moved").path == (system / "system.ttf").resolve()


@needs_ms_fonts
def test_ms_fonts_copied_into_an_added_folder_are_used_on_every_os(windows, added, tmp_path, monkeypatch):
    from gridlayoutpdf.fonts import FontRegistry

    folder = tmp_path / "engine-fonts"
    folder.mkdir()
    for file in ("msmincho.ttc", "msgothic.ttc"):
        shutil.copyfile(WINDOWS_FONTS / file, folder / file)
    fontfinder.add_directory(folder)
    monkeypatch.setattr(fontfinder, "_is_windows", lambda: False)
    for name, file, index in (("MS Mincho", "msmincho.ttc", 0), ("ＭＳ 明朝", "msmincho.ttc", 0),
                              ("MS Gothic", "msgothic.ttc", 0), ("MS PGothic", "msgothic.ttc", 2),
                              ("ＭＳ Ｐゴシック", "msgothic.ttc", 2)):
        location = fontfinder.find_font(name)
        assert (location.path, location.face_index) == ((folder / file).resolve(), index), name
        assert not location.bundled
    assert FontRegistry().measure("計算書", TextStyle(font="MS PGothic")).width > 0
