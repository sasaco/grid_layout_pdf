"""pt to Excel unit conversions measured in Excel 16.0 at 96 DPI."""

import pytest

from gridlayoutpdf.renderers.xlsx._model import Font
from gridlayoutpdf.renderers.xlsx._units import (
    EMU_PER_PT,
    column_width_chars,
    excel_column_width_pt,
    excel_row_height_pt,
    max_digit_width_px,
    pt_to_emu,
)


@pytest.mark.parametrize(("font", "mdw"), [
    (Font("游ゴシック", 11), 8), (Font("Yu Gothic", 11), 8), (Font("Calibri", 11), 7),
    (Font("ＭＳ 明朝", 11), 8), (Font("ＭＳ ゴシック", 11), 8), (Font("ＭＳ Ｐゴシック", 11), 8),
    (Font("游明朝", 11), 8), (Font("游ゴシック", 10), 7), (Font("ＭＳ 明朝", 10.5), 7),
])
def test_measured_maximum_digit_widths(font, mdw):
    assert max_digit_width_px(font) == mdw


def test_unmeasured_default_font_is_an_error():
    with pytest.raises(ValueError, match="measured"):
        max_digit_width_px(Font("Unknown Sans", 11))


@pytest.mark.parametrize(("width_pt", "excel_pt"), [
    (16.08, 15.75), (15.48, 15.75), (8.04, 8.25), (0.75, 0.75), (100, 99.75), (4.02, 3.75), (12, 12), (30, 30),
])
def test_column_width_rounds_to_the_nearest_whole_pixel_like_excel(width_pt, excel_pt):
    assert excel_column_width_pt(width_pt) == excel_pt


@pytest.mark.parametrize("font", [Font("游ゴシック", 11), Font("Calibri", 11), Font("ＭＳ 明朝", 10.5)])
@pytest.mark.parametrize("pixels", [1, 2, 5, 11, 21, 64, 133, 1000])
def test_column_width_chars_turn_back_into_the_same_pixels_by_the_ecma_formula(font, pixels):
    mdw = max_digit_width_px(font)
    width = column_width_chars(pixels * 0.75, font)
    assert (width * 256).is_integer()
    assert int(((256 * width + int(128 / mdw)) / 256) * mdw) == pixels


@pytest.mark.parametrize(("height_pt", "excel_pt"), [
    (15.48, 15.75), (15.0, 15.0), (12.0, 12.0), (10.5, 10.5), (15.6, 15.75), (20.64, 21.0), (7.74, 7.5),
    (1, 0.75), (409, 408.75), (15.3, 15.0), (0.375, 0.75),
])
def test_row_height_rounds_half_up_to_a_whole_pixel(height_pt, excel_pt):
    assert excel_row_height_pt(height_pt) == excel_pt


@pytest.mark.parametrize("value", [0.37, 0.0, -1])
def test_lengths_below_half_a_pixel_are_errors(value):
    with pytest.raises(ValueError, match="pixel"):
        excel_row_height_pt(value)
    with pytest.raises(ValueError, match="pixel"):
        excel_column_width_pt(value)


def test_points_to_emu():
    assert EMU_PER_PT == 12_700
    assert pt_to_emu(1) == 12_700
    assert pt_to_emu(15.75) == 200_025
    assert pt_to_emu(0.5) == 6_350


# --- print scale ------------------------------------------------------------

from gridlayoutpdf.renderers.xlsx._model import Margins, PageSetup, Sheet  # noqa: E402
from gridlayoutpdf.renderers.xlsx._units import fit_scale_percent, page_heights_pt, print_fit  # noqa: E402

PAGE = PageSetup(margins=Margins(36, 36, 36, 36, 18, 18))  # A4 portrait: 523.28 x 769.89 pt printable
GOTHIC = Font("游ゴシック", 11)


def _scale(sheet, **options):
    return fit_scale_percent(sheet, GOTHIC, **options)


def _fit(sheet, **options):
    return print_fit(sheet, GOTHIC, **options)


def test_page_heights_sum_excel_row_heights_between_manual_breaks():
    assert page_heights_pt((15.48,) * 5, (2, 4)) == (31.5, 31.5, 15.75)
    assert page_heights_pt((12.0, 15.0), ()) == (27.0,)


def test_fit_scale_below_twenty_percent_is_an_error():
    with pytest.raises(ValueError, match="20 %"):
        _scale(Sheet("S", (16.08,) * 400, (15.48,) * 10, page=PAGE))


@pytest.mark.parametrize("maximum", [9, 19, 101, 100.0])
def test_fit_scale_maximum_must_be_an_excel_scale(maximum):
    with pytest.raises(ValueError):
        _scale(Sheet("S", (16.08,), (15.48,), page=PAGE), maximum=maximum)


# --- review round 1 ----------------------------------------------------------


def _grid(columns, rows, breaks=(), page=PAGE):
    return Sheet("S", (16.08,) * columns, (15.48,) * rows, row_breaks=breaks, page=page)


def test_fit_scale_takes_a_validated_sheet():
    # 523.28 / (551.25 * 1.04) = 91.3 %; Excel's own limit for this grid was 93 %.
    assert _scale(_grid(35, 150, (50, 100))) == 91
    with pytest.raises(ValueError, match="Sheet"):
        fit_scale_percent((16.08,) * 35, GOTHIC)


def test_reference_a4_grid_prints_at_100_percent_with_margins_left_for_the_print_factor():
    # 30 x 47 cells of A4.pdf; left/top margins at the grid origin, right/bottom where 100 % still fits.
    page = PageSetup(margins=Margins(left=50.88, top=54.598, right=50.6, bottom=47.0, header=18, footer=18))
    assert _scale(_grid(30, 47, (), page)) == 100


@pytest.mark.parametrize(("columns", "scale"), [
    (33, 96),  # 1.04: 523.28 / (519.75 * 1.04) = 96.8 %
    (36, 87),  # 1.04 gives 88.7 % (< 90), so 1.05: 87.9 %
    (60, 51),  # 1.05 gives 52.7 % (< 55), so 1.08: 51.3 %
    (100, 30),  # 1.08: 523.28 / (1575 * 1.08) = 30.8 %
])
def test_column_factor_bands(columns, scale):
    assert _scale(_grid(columns, 10)) == scale


def test_maximum_below_a_band_uses_the_low_scale_factor():
    assert _fit(_grid(5, 5), maximum=50) == (50, "maximum", 1.08, 1.025)
    # 36 columns: 1.04 allows 88.7 %, so the 55 % band applies (1.05: 87.9 %).
    assert _fit(_grid(36, 10), maximum=89) == (87, "width", 1.05, 1.01)


def test_landscape_and_a3_printable_sizes():
    margins = Margins(36, 36, 36, 36, 18, 18)
    assert PageSetup(orientation="landscape", margins=margins).printable_size_pt == pytest.approx((769.8898, 523.2756))
    assert PageSetup(paper="A3", margins=margins).paper_size_pt == (841.8898, 1190.5512)


# --- review round 2 ----------------------------------------------------------

from gridlayoutpdf.renderers.xlsx._units import (  # noqa: E402
    MAX_FIT_SCALE,
    MEASURED_CELL_PIXELS,
    MIN_FIT_SCALE,
    PRINT_MEASURED_FONTS,
)


def test_print_fit_reports_what_limits_the_scale():
    assert _fit(_grid(35, 50)) == (91, "width", 1.04, 1.0)
    assert _fit(_grid(10, 80, (60,))).limited_by == "height"
    assert _fit(_grid(5, 5)) == (100, "maximum", 1.04, 1.0)


def test_print_fit_accepts_only_the_fonts_whose_printing_was_measured():
    assert fit_scale_percent(_grid(35, 50), Font("ＭＳ 明朝", 10.5)) == 91
    for font in (Font("Calibri", 11), Font("游ゴシック", 11, bold=True), "游ゴシック"):
        with pytest.raises(ValueError, match="measured"):
            fit_scale_percent(_grid(35, 50), font)


def test_scales_below_twenty_percent_are_not_used():
    assert MIN_FIT_SCALE == 20
    assert _scale(_grid(120, 10)) == 25  # 523.28 / (1890 * 1.08) = 25.6 %
    with pytest.raises(ValueError, match="20 %"):
        _scale(_grid(250, 10))  # 523.28 / (3937.5 * 1.08) = 12.3 %


def test_reference_a3_landscape_grid_prints_at_100_percent_with_margins_left_for_the_print_factor():
    # 67 x 47 cells: 1055.25 * 1.04 = 1097.5 pt wide (right margin at most 42.21 pt by the band factor);
    # at 100 % the measured printed sizes need 67 x 16.08 x 1.006 + 4.5 = 1088.3 pt (at most 51.34 pt).
    page = PageSetup(paper="A3", orientation="landscape",
                     margins=Margins(left=50.88, top=54.598, right=42.2, bottom=47.0, header=18, footer=18))
    assert _fit(_grid(67, 47, (), page)) == (100, "maximum", 1.04, 1.0)
    narrower = PageSetup(paper="A3", orientation="landscape",
                         margins=Margins(left=50.88, top=54.598, right=51.35, bottom=47.0, header=18, footer=18))
    assert _fit(_grid(67, 47, (), narrower)) == (99, "width", 1.04, 1.0)


def test_a4_pdf_margins_print_the_reference_grid_at_98_percent():
    # A4_PORTRAIT_REFERENCE: left 50.88, top 54.598, right 61.72, bottom 59.842 pt.
    page = PageSetup(margins=Margins(left=50.88, top=54.598, right=61.72, bottom=59.842, header=18, footer=18))
    assert _scale(_grid(30, 47, (), page)) == 98


@pytest.mark.parametrize(("heights", "breaks"), [
    ((True, 15.0), ()), ((15.0, "15"), ()), ((15.0, 15.0), {1}), ((15.0, 15.0), (1.0,)), ("15", ()),
    (memoryview(b"\x0f\x0f"), ()), ((15.0, 15.0), memoryview(b"\x01")), ((500.0,), ()), ((), ()),
])
def test_page_heights_reject_what_a_sheet_rejects(heights, breaks):
    with pytest.raises(ValueError):
        page_heights_pt(heights, breaks)


# --- review round 3 ----------------------------------------------------------


def test_print_fit_needs_the_workbook_default_font():
    with pytest.raises(TypeError):
        fit_scale_percent(_grid(5, 5))
    with pytest.raises(TypeError):
        print_fit(_grid(5, 5))


def test_fit_scale_maximum_is_the_largest_measured_scale():
    assert MAX_FIT_SCALE == 100
    assert _scale(_grid(5, 5)) == 100


def _measured():
    import json
    from pathlib import Path

    path = Path(__file__).parents[2] / "scripts" / "xlsx_probe" / "print_pitch.json"
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def test_print_factors_stay_above_every_measured_factor_with_margin():
    from gridlayoutpdf.renderers.xlsx._units import _PRINT_FACTORS, DOCUWORKS_PDF_MAXIMA

    records = _measured()
    upper = 101
    for lowest, column_factor, row_factor in _PRINT_FACTORS:
        band = [record for record in records if lowest <= record["scale"] < upper]
        widest = max(band, key=lambda record: record["column_factor"])
        tallest = max(band, key=lambda record: record["row_factor"])
        assert column_factor >= widest["column_factor"] * 1.006, widest
        assert row_factor >= tallest["row_factor"] * 1.006, tallest
        other_column, other_row = DOCUWORKS_PDF_MAXIMA[lowest]
        assert column_factor >= other_column * 1.006 and row_factor >= other_row * 1.006
        upper = lowest


def test_every_whole_scale_the_helper_can_return_was_measured_for_each_font_and_size():
    records = _measured()
    measured = {(record["font"], record["size"], record["pixels"], record["scale"]) for record in records}
    fonts = {(record["font"], record["size"]) for record in records}
    assert fonts == set(PRINT_MEASURED_FONTS)
    for font, size in fonts:
        for pixels in MEASURED_CELL_PIXELS:
            missing = [scale for scale in range(MIN_FIT_SCALE, MAX_FIT_SCALE + 1)
                       if (font, size, pixels, scale) not in measured]
            assert missing == [], (font, pixels)


def test_at_100_percent_only_yu_gothic_prints_the_a4_reference_grid_pitch():
    # 21 px cells print as 16.08 x 15.48 pt (A4.pdf's grid) with 游ゴシック 11 as the Normal font,
    # but as 15.84 x 14.52 pt with ＭＳ 明朝 10.5.
    sizes = {(record["font"], record["size"]): (record["printed_column_pt"], record["printed_row_pt"])
             for record in _measured() if record["pixels"] == 21 and record["scale"] == 100}
    assert sizes[("游ゴシック", 11.0)] == pytest.approx((16.08, 15.48), abs=0.005)
    assert sizes[("ＭＳ 明朝", 10.5)] == pytest.approx((15.84, 14.52), abs=0.005)


# --- review round 4 ----------------------------------------------------------


@pytest.mark.parametrize(("paper", "orientation", "columns", "right"), [
    ("A4", "portrait", 30, 54.6), ("A3", "landscape", 67, 51.34),
])
def test_handoff_margins_for_100_percent_are_exact_upper_limits(paper, orientation, columns, right):
    # Grid origin 50.88 / 54.598 pt (A4_PORTRAIT_REFERENCE); 47 rows of 15.48 pt. At 100 % the measured
    # printed sizes (full_scale_size_pt) set the limits; beyond them the band factors give 99 %.
    def fit(right_margin, bottom_margin):
        margins = Margins(left=50.88, top=54.598, right=right_margin, bottom=bottom_margin, header=18, footer=18)
        return _fit(_grid(columns, 47, (), PageSetup(paper=paper, orientation=orientation, margins=margins)))
    assert fit(right, 50.86).scale == 100
    assert fit(right + 0.01, 40.0) == (99, "width", 1.04, 1.0)
    assert fit(40.0, 50.87) == (99, "height", 1.04, 1.0)


def test_a4_pdf_margins_alone_give_98_percent_on_either_side():
    def fit(right, bottom):
        return _fit(_grid(30, 47, (), PageSetup(margins=Margins(50.88, 54.598, right, bottom, 18, 18))))
    assert fit(61.72, 47.0) == (98, "width", 1.04, 1.0)
    assert fit(50.6, 59.842) == (98, "height", 1.04, 1.0)


def test_print_fit_rejects_a_colored_default_font_and_accepts_the_smallest_maximum():
    with pytest.raises(ValueError, match="measured"):
        fit_scale_percent(_grid(5, 5), Font("游ゴシック", 11, color=(1, 0, 0)))
    assert _scale(_grid(5, 5), maximum=20) == 20


@pytest.mark.parametrize("value", [1e305, 1e307, 1e308, -1e305, -1.5e308, -1.7976931348623157e308])
def test_huge_lengths_are_value_errors(value):
    with pytest.raises(ValueError):
        Sheet("S", (value, value), (15.0,))
    with pytest.raises(ValueError):
        Sheet("S", (15.0,), (value,))
    with pytest.raises(ValueError):
        excel_column_width_pt(value)
    with pytest.raises(ValueError):
        excel_row_height_pt(value)
    with pytest.raises(ValueError):
        page_heights_pt((value,), ())


def test_print_pitch_data_was_measured_with_docuworks_printer():
    import json
    from pathlib import Path

    path = Path(__file__).parents[2] / "scripts" / "xlsx_probe" / "print_pitch.json"
    assert "active printer DocuWorks Printer" in json.loads(path.read_text(encoding="utf-8"))["excel"]


# --- review round 6 ----------------------------------------------------------


def _excel_test_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[1] / "integration" / "test_xlsx_excel_core.py"
    spec = importlib.util.spec_from_file_location("xlsx_excel_core_cases", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(pixels, scale, column_factor, row_factor):
    return {"font": "游ゴシック", "size": 11.0, "pixels": pixels, "scale": scale,
            "column_factor": column_factor, "row_factor": row_factor}


def test_worst_case_generator_skips_conditions_print_fit_cannot_return():
    module = _excel_test_module()
    records = [
        _record(12, 100, 1.03, 0.995),  # largest at 100 %: a case that expects "maximum"
        _record(12, 93, 1.02, 0.99),
        _record(13, 54, 1.04, 1.0),  # 54 % in the 20 % band: the 55 % band takes it
        _record(13, 28, 1.03, 0.98),
        _record(14, 63, 1.03, 0.99),
    ]
    cases = module._worst_measured_cases(records)
    assert sorted(cases) == sorted([
        "columns-12px-100-percent-yu-gothic", "rows-12px-100-percent-yu-gothic",  # "maximum" at 100 %
        "columns-14px-63-percent-yu-gothic", "rows-14px-63-percent-yu-gothic",
        "columns-13px-28-percent-yu-gothic", "rows-13px-54-percent-yu-gothic",  # rows at 54 % stay in their band
    ])
    assert all(module._fits_as_expected(case) for case in cases.values())
    with pytest.raises(ValueError, match="no records"):
        module._worst_measured_cases(records[:2])


@pytest.mark.parametrize("value", [True, 10**400, 749_999.9, 749_999.7, "15"])
def test_unit_conversions_reject_what_the_model_rejects(value):
    with pytest.raises(ValueError):
        excel_column_width_pt(value)
    with pytest.raises(ValueError):
        excel_row_height_pt(value)


def test_print_fit_rejects_columns_wider_than_255_characters():
    sheet = Sheet("S", (16.08, 1_700.0), (15.48,), page=PageSetup(paper="A3", orientation="landscape"))
    with pytest.raises(ValueError, match="255"):
        _fit(sheet)


def test_lengths_just_below_the_pixel_limit_are_accepted():
    assert excel_column_width_pt(749_999.2) == 999_999 * 0.75



def _measure_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[2] / "scripts" / "xlsx_probe" / "measure_print_pitch.py"
    spec = importlib.util.spec_from_file_location("measure_print_pitch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_measurement_printer_names_ignore_only_the_port():
    name = _measure_module().printer_name
    assert name("X on Y on Ne01:") == name("Excel 16.0, active printer X on Y on Ne04:") == "X on Y"
    assert name("X on Z on Ne01:") != name("X on Y on Ne01:")
    assert name(None) == ""


def test_measured_data_survives_a_failed_replacement_and_another_printers_file(tmp_path, monkeypatch):
    import json
    import os
    from pathlib import Path

    module = _measure_module()
    out = tmp_path / "print_pitch.json"
    data = json.dumps({"excel": "active printer P on Ne01:", "records": [1]})

    def dated_files():
        return sorted(path for path in tmp_path.iterdir() if path != out)

    assert module._store(data, out, "P on Ne02:") == 0  # no file yet
    assert json.loads(out.read_text(encoding="utf-8"))["records"] == [1] and dated_files() == []

    out.write_text(json.dumps({"excel": "active printer P on Ne09:", "records": [0]}), encoding="utf-8")
    assert module._store(data, out, "P on Ne02:") == 0  # same printer on another port: replaced
    assert json.loads(out.read_text(encoding="utf-8"))["records"] == [1] and dated_files() == []

    other = json.dumps({"excel": "active printer Q on Ne01:", "records": [0]})
    for previous in (other, json.dumps([1, 2]), json.dumps({"excel": None}), "not json"):
        out.write_text(previous, encoding="utf-8")
        assert module._store(data, out, "P on Ne02:") == module.KEPT_DATED
        assert out.read_text(encoding="utf-8") == previous
    assert len(dated_files()) == 4
    assert all(json.loads(path.read_text(encoding="utf-8"))["records"] == [1] for path in dated_files())

    out.write_text(json.dumps({"excel": "active printer P on Ne09:"}), encoding="utf-8")
    real_replace = os.replace

    def fail_on_out(source, target):
        if Path(target) == out:
            raise PermissionError("open in an editor")
        real_replace(source, target)

    monkeypatch.setattr(module.os, "replace", fail_on_out)
    assert module._store(data, out, "P on Ne02:") == module.KEPT_DATED
    assert len(dated_files()) == 5


def test_measured_data_saved_twice_in_the_same_second_keeps_both_files(tmp_path, monkeypatch):
    import datetime
    import json

    module = _measure_module()

    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 20, 12, 0, 0)

    monkeypatch.setattr(module.datetime, "datetime", Frozen)
    out = tmp_path / "print_pitch.json"
    out.write_text(json.dumps({"excel": "active printer Q on Ne01:"}), encoding="utf-8")
    for records in ([1], [2]):
        data = json.dumps({"records": records})
        assert module._store(data, out, "P on Ne01:") == module.KEPT_DATED
    kept = sorted(json.loads(path.read_text(encoding="utf-8"))["records"] for path in tmp_path.iterdir() if path != out)
    assert kept == [[1], [2]]
    with pytest.raises(SystemExit, match="empty"):
        module._store("{}", out, "")


def test_pt_to_emu_and_sheet_name_key_reject_non_values():
    from gridlayoutpdf.renderers.xlsx._model import sheet_name_key

    for value in (True, float("inf"), 1e308 * 10, "1", 10**400, 10**305):
        with pytest.raises(ValueError):
            pt_to_emu(value)
    with pytest.raises(ValueError):
        sheet_name_key(None)


def test_worst_case_generator_names_an_empty_band():
    module = _excel_test_module()
    records = [_record(14, 63, 1.03, 0.99), _record(13, 28, 1.03, 0.98)]  # nothing from 90 %
    with pytest.raises(ValueError, match="no records from 90"):
        module._worst_measured_cases(records)


def test_measurement_saves_its_data_before_the_temporary_folder_is_removed():
    import ast
    from pathlib import Path

    source = (Path(__file__).parents[2] / "scripts" / "xlsx_probe" / "measure_print_pitch.py").read_text(
        encoding="utf-8")
    main = next(node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    block = next(node for node in ast.walk(main) if isinstance(node, ast.With)
                 and ast.unparse(node.items[0].context_expr).startswith("tempfile.TemporaryDirectory"))
    # Cleanup errors (a PDF still open) must not raise, and the data is stored inside the block.
    assert "ignore_cleanup_errors=True" in ast.unparse(block.items[0].context_expr)
    assert any(isinstance(node, ast.Call) and ast.unparse(node.func) == "_store" for node in ast.walk(block))
