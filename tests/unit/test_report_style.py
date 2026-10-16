from dataclasses import FrozenInstanceError

import pytest

from gridlayoutpdf import styles


def report_style(**kwargs):
    assert hasattr(styles, "ReportStyle"), "ReportStyle is not implemented"
    return styles.ReportStyle(**kwargs)


def test_report_style_defaults_are_immutable_typographic_settings():
    style = report_style()
    assert style.body == styles.TextStyle(size=10)
    assert style.heading == styles.TextStyle(size=12)
    assert style.baseline_offset == 11
    assert style.max_tracking_em == 0.05
    assert (style.min_first_lines, style.min_last_lines) == (2, 2)
    with pytest.raises(FrozenInstanceError):
        style.baseline_offset = 12
    body = styles.TextStyle(font="custom", size=9, tracking=0.1)
    changed = report_style(body=body, baseline_offset=10, max_tracking_em=0,
                           min_first_lines=1, min_last_lines=3)
    assert changed.body is body
    assert changed.max_tracking_em == 0


@pytest.mark.parametrize("field,value", [
    ("body", None), ("heading", "bold"),
    ("baseline_offset", 0), ("baseline_offset", -1),
    ("baseline_offset", True), ("baseline_offset", float("inf")),
    ("baseline_offset", float("nan")), ("baseline_offset", "11"),
    ("max_tracking_em", -0.01), ("max_tracking_em", True),
    ("max_tracking_em", float("nan")), ("max_tracking_em", float("inf")),
    ("min_first_lines", 0), ("min_first_lines", True), ("min_first_lines", 2.0),
    ("min_last_lines", -1), ("min_last_lines", False), ("min_last_lines", 1.5),
])
def test_invalid_report_style_is_rejected_at_construction(field, value):
    with pytest.raises(ValueError, match=field):
        report_style(**{field: value})
