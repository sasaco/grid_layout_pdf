"""Rule: a separator across the body on a grid-row boundary (FR-026)."""

import importlib

import pytest


def api():
    return importlib.import_module("gridlayoutpdf")


@pytest.fixture
def context():
    module = api()
    profile = module.PageProfile("rule", 300, 400, module.GridSpec(20, 20, 10, 20, 20, 18))
    return module.LayoutContext(module.FontRegistry(), profile, module.ReportStyle())


def test_default_rule_is_one_thin_line_on_the_top_boundary_of_one_row_across_the_width(context):
    module = api()
    measured = module.measure_block(module.Rule(), context, 150)
    assert (measured.width, measured.rows, len(measured.parts)) == (150, 1, 1)
    assert measured.commands == (module.Line(.25, .25, 149.75, .25, .5),)
    assert measured.parts[0].metadata["rule"] == {"style": "thin", "width_pt": 150}


def test_columns_fix_the_width_in_grid_columns_and_must_fit(context):
    module = api()
    measured = module.measure_block(module.Rule(module.BorderStyle.MEDIUM, columns=4), context, 150)
    assert measured.width == 40
    assert measured.commands == (module.Line(.5, .5, 39.5, .5, 1),)
    with pytest.raises(module.LayoutOverflowError, match="rule") as caught:
        module.measure_block(module.Rule(columns=16, block_id="rule"), context, 150)
    assert (caught.value.needed, caught.value.available) == (160, 150)


def test_double_and_dashed_rules_use_the_style_geometry(context):
    module = api()
    double = module.measure_block(module.Rule("double", columns=3, color=(.2, .3, .4)), context, 150)
    assert double.commands == (module.Line(.25, .25, 29.75, .25, .5, (.2, .3, .4)),
                               module.Line(.25, 1.25, 29.75, 1.25, .5, (.2, .3, .4)))
    dashed = module.measure_block(module.Rule(module.BorderStyle.DASH_DOT, columns=3), context, 150)
    assert dashed.commands == (module.Line(.25, .25, 29.75, .25, .5, dash=(6, 1.5, 1.5, 1.5)),)


def test_rule_flows_on_the_grid_like_any_block():
    module = api()
    profile = module.PageProfile("rule", 300, 400, module.GridSpec(20, 20, 10, 20, 20, 18))
    pages = module.Document(module.Spacer(2), module.Rule(columns=5, block_id="sep"),
                            profile=profile).layout()
    line, = [command for command in pages[0].commands if isinstance(command, module.Line)]
    assert (line.x1, line.y1, line.x2) == (20.25, 60.25, 69.75)
    assert pages[0].metadata["placements"][-1]["block_id"] == "sep"


@pytest.mark.parametrize("options", [
    {"style": .5}, {"style": 1}, {"style": None}, {"style": "solid"},
    {"columns": 0}, {"columns": 1.5}, {"columns": True},
    {"color": "black"}, {"color": (0, 0)}, {"block_id": 3},
])
def test_invalid_rules_are_rejected(options):
    with pytest.raises(ValueError):
        api().Rule(**options)


def test_old_width_keyword_is_not_accepted():
    with pytest.raises(TypeError):
        api().Rule(width=.72)
