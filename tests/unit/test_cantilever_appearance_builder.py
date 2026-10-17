"""Source typography and native semantic placement must be explicit."""
import importlib.util
from pathlib import Path
import sys

import pytest

from gridlayoutpdf import A4_PORTRAIT_REFERENCE, LayoutContext, Paragraph, ReportStyle, Text, TextStyle, measure_block

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests/fixtures/cantilever_p01_37"


def module(name):
    key = f"cantilever_fixture_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, FIXTURE / f"{name}.py")
        result = importlib.util.module_from_spec(spec)
        sys.modules[key] = result
        spec.loader.exec_module(result)
    return sys.modules[key]


def test_default_fixture_registers_the_two_original_fixed_width_faces():
    fonts = module("builder").fixture_fonts()
    assert fonts.resolve("body").path.name == "msmincho.ttc"
    assert fonts.resolve("heading").path.name == "msgothic.ttc"
    assert fonts.resolve("body").face_index == fonts.resolve("heading").face_index == 0
    assert fonts.measure("Wi", TextStyle()).width == 10


def test_source_tracking_is_computed_from_font_advance_without_resizing():
    fonts = module("builder").fixture_fonts()
    box = module("appearance").SourceLiteral("1片2").measure(fonts, TextStyle(size=10))
    text = [c for c in box.commands if isinstance(c, Text)]
    assert [c.x for c in text] == pytest.approx([0, 5.04, 15.12])
    assert {c.style.size for c in text} == {10}
    assert box.width == pytest.approx(20.16)


def test_source_scripts_use_authored_size_and_baseline_instead_of_larger_default():
    appearance = module("appearance")
    fonts = module("builder").fixture_fonts()
    node = appearance.SourceScript(appearance.SourceLiteral("S"), subscript=appearance.SourceLiteral("10"))
    box = node.measure(fonts, TextStyle(size=10))
    text = [c for c in box.commands if isinstance(c, Text)]
    assert [c.style.size for c in text] == [10, 6.7]
    assert text[1].y == pytest.approx(1.92)
    assert text[1].x == pytest.approx(5.04)


def test_page_frame_keeps_absolute_baseline_and_descendant_identity():
    appearance = module("appearance")
    fonts = module("builder").fixture_fonts()
    child = Paragraph("13.1 heading", style=TextStyle("heading",10), block_id="p01-section")
    frame = appearance.PageFrame(1, ((child, {"id":"p01-section","kind":"paragraph","x":68.04,"baseline":100.678,"width":400}),), ("p01-section",))
    measured = measure_block(frame, LayoutContext(fonts,A4_PORTRAIT_REFERENCE,ReportStyle()), A4_PORTRAIT_REFERENCE.body_rect.width)
    command = next(c for c in measured.commands if isinstance(c,Text))
    assert command.x + A4_PORTRAIT_REFERENCE.grid.origin_x == pytest.approx(68.04)
    assert command.y + A4_PORTRAIT_REFERENCE.grid.origin_y == pytest.approx(100.678)
    assert "p01-section" in repr(measured.parts[0].metadata)


def test_source_frame_rejects_unmatched_line_anchors_instead_of_dropping_them():
    from gridlayoutpdf import LayoutOverflowError
    appearance = module("appearance")
    fonts = module("builder").fixture_fonts()
    child=Paragraph("one line",block_id="p01-body")
    geometry={"id":"p01-body","kind":"paragraph","x":70,"baseline":90,"width":300,
              "lines":[{"baseline":90,"start_x":70},{"baseline":110,"start_x":70}]}
    frame=appearance.PageFrame(1,((child,geometry),),("p01-body",))
    with pytest.raises(LayoutOverflowError,match="source line count differs"):
        measure_block(frame,LayoutContext(fonts,A4_PORTRAIT_REFERENCE,ReportStyle()),482.4)


def test_changed_original_font_hash_is_rejected(monkeypatch):
    builder=module("builder")
    profile=builder.font_profile()
    profile["fonts"]["heading"]["sha256"]="0"*64
    monkeypatch.setattr(builder,"font_profile",lambda:profile)
    with pytest.raises(ValueError,match="Original font hash changed: heading"):
        builder.fixture_fonts()


def test_mixed_heading_uses_original_body_run_start():
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    node=appearance.StyledSourceLiteral("a) 起点桁　4 箇所",(
        {"start":0,"stop":5,"font":"heading"},
        {"start":5,"stop":8,"font":"body","x":204.6}),111.6)
    commands=node.measure(fonts,TextStyle("heading",10)).commands
    body=next(c for c in commands if c.style.font=="body" and c.text.strip())
    assert body.x+111.6==pytest.approx(204.6)
    assert {c.style.font for c in commands}=={"body","heading"}


def test_equal_plus_minus_anchor_centers_the_equal_character():
    from gridlayoutpdf import Equation, EquationGroup
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    context=appearance.local_context(LayoutContext(fonts,A4_PORTRAIT_REFERENCE,ReportStyle()))
    equation=Equation("G1","12.3",relation=" ",result_relation="＝±",result="45.6",unit="kN")
    group=EquationGroup(equation,block_id="p01-equation")
    geometry={"x":100,"equations":[{"baseline":150,"lhs_start":100,"rhs_start":150,
              "second_equal":250,"result_right":320,"unit_start":330}]}
    measured,x,y=appearance.placed_equations(group,geometry,context,300)
    equal=next(c for c in measured.commands if isinstance(c,Text) and c.text=="＝±")
    assert equal.x+x+fonts.measure("＝",equal.style).width/2==pytest.approx(250)


def test_source_rule_keeps_centerline_and_endpoints_within_its_ink_frame():
    from gridlayoutpdf import Line
    builder=module("builder")
    appearance=module("appearance")
    fonts=builder.fixture_fonts()
    source={"id":"p16-rule","kind":"rule","x":123.48,"y":115.198,"width":.72,"height":142.32}
    geometry=builder._rule_outer_edges(source)
    block=builder.build_block({"id":"p16-rule","type":"rule"},geometry)
    frame=appearance.PageFrame(16,((block,geometry),),("p16-rule",))
    context=LayoutContext(fonts,A4_PORTRAIT_REFERENCE,ReportStyle())
    measured=measure_block(frame,context,482.4)
    line=next(c for c in measured.commands if isinstance(c,Line))
    origin=context.profile.grid
    assert line.x1+origin.origin_x==pytest.approx(source["x"])
    assert line.x2+origin.origin_x==pytest.approx(source["x"])
    assert line.y1+origin.origin_y==pytest.approx(source["y"])
    assert line.y2+origin.origin_y==pytest.approx(source["y"]+source["height"])


def test_native_table_rules_join_part_seams_without_closing_merged_cell_gaps():
    from gridlayoutpdf import Line
    appearance=module("appearance")
    commands=(Line(0,.48,0,19.52,width=.96),Line(0,20.48,0,39.52,width=.96),
              Line(10,.48,10,9.52,width=.96),Line(10,20.48,10,39.52,width=.96))
    joined=appearance.continuous_table_rules(commands)
    outer=[line for line in joined if line.x1==0]
    inner=[line for line in joined if line.x1==10]
    assert len(outer)==1
    assert (outer[0].y1,outer[0].y2)==pytest.approx((.48,39.52))
    assert len(inner)==2


def test_source_shear_targets_only_authored_base_atom_and_preserves_advance():
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    node=appearance.SourceScript(appearance.SourceLiteral("D"),subscript=appearance.SourceLiteral("1"))
    original=node.measure(fonts,TextStyle(size=10))
    styled=appearance.shear_atoms(node,({"text":"D","shear_x":.342},)).measure(fonts,TextStyle(size=10))
    assert styled.width==original.width
    commands=[command for command in styled.commands if isinstance(command,Text)]
    assert commands[0].text=="D" and commands[0].shear_x==.342
    assert commands[1].text=="1" and commands[1].shear_x==0


def test_source_spaces_preserve_script_structure_and_native_word_positions():
    from gridlayoutpdf import Row
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    node=Row(appearance.SourceLiteral("1.0"),
             appearance.SourceScript(appearance.SourceLiteral("L"),subscript=appearance.SourceLiteral("R")),
             appearance.SourceLiteral("+ 1.23B"),gap=0)
    restored=appearance.source_whitespace(node,"1.0 LR + 1.23B")
    commands=restored.measure(fonts,TextStyle(size=10)).commands
    letter=next(c for c in commands if c.text.strip()=="L")
    subscript=next(c for c in commands if c.text=="R")
    plus=next(c for c in commands if "+" in c.text)
    assert letter.x+appearance.SourceLiteral(" ").measure(fonts,letter.style).width==pytest.approx(20.16)
    assert subscript.style.size==6.7 and subscript.y==1.92
    assert plus.x+appearance.SourceLiteral(" ").measure(fonts,plus.style).width==pytest.approx(33.6168)


def test_vertical_open_parenthesis_uses_ink_position_above_the_next_kanji():
    appearance=module("appearance")
    builder=module("builder")
    fonts=builder.fixture_fonts()
    anchor={"start_x":9.09,"baseline":64.8553,"local_quarter_turns":3,
            "source_bbox":[9.09,54.8366,18.99,64.8553]}
    cell=appearance.SourceCell((appearance.SourceLiteral("（"),),(TextStyle(size=10),),
                               (anchor,),106.08,vertical_glyphs=builder.font_profile()["vertical_glyphs"])
    measured=cell.measure(appearance.local_context(LayoutContext(fonts,A4_PORTRAIT_REFERENCE,ReportStyle())),29.1)
    command=next(c for c in measured.commands if isinstance(c,Text))
    ink=appearance.text_ink_bounds(command,fonts)
    assert command.quarter_turns==3 and command.style.size==9.9
    assert ink.x+ink.width/2==pytest.approx(14.04)
    assert ink.y+ink.height/2==pytest.approx(54.46480859375)
    assert ink.bottom<58.59


def test_semantic_operand_anchors_restore_large_operator_spacing():
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    line={"baseline":188.038,"start_x":204,"semantic_runs":[
        {"text":"517.77","character_offset":0,"start_x":204},
        {"text":"×","character_offset":6,"start_x":242.28},
        {"text":"0.471","character_offset":7,"start_x":264.6}]}
    commands=appearance.anchored_commands(appearance.SourceLiteral("517.77×0.471"),line,fonts,TextStyle())
    assert [(c.text,c.x) for c in commands]==[("517.77",204),("×",242.28),("0.471",264.6)]
    assert {c.style.size for c in commands}=={10}


def test_semantic_script_run_retains_large_authored_gap_without_flattening():
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    node=appearance.SourceScript(appearance.SourceLiteral("1.50"),superscript=appearance.SourceLiteral("2"))
    line={"baseline":350,"start_x":209.04,"semantic_runs":[
        {"text":"1.502","character_offset":0,"start_x":209.04,"script_offsets":{"sup_x":32.76}}]}
    commands=appearance.anchored_commands(node,line,fonts,TextStyle())
    exponent=next(command for command in commands if command.text=="2")
    assert exponent.x==pytest.approx(241.8)
    assert exponent.style.size==6.7 and exponent.y==pytest.approx(347.6)


def test_semantic_script_offsets_preserve_distinct_source_vertical_positions():
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    node=appearance.SourceScript(appearance.SourceLiteral("A"),
          superscript=appearance.SourceLiteral("2"),subscript=appearance.SourceLiteral("1"))
    line={"baseline":546.958,"start_x":209.04,"semantic_runs":[
        {"text":"A12","character_offset":0,"start_x":209.04,
         "script_offsets":{"sup_y":-5.64,"sub_y":2.28}}]}
    commands=appearance.anchored_commands(node,line,fonts,TextStyle())
    assert next(c for c in commands if c.text=="2").y==pytest.approx(541.318)
    assert next(c for c in commands if c.text=="1").y==pytest.approx(549.238)


def test_fraction_rhs_is_rejected_explicitly_in_source_semantic_placement():
    from gridlayoutpdf import Equation,EquationGroup,Fraction
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    context=appearance.local_context(LayoutContext(fonts,A4_PORTRAIT_REFERENCE,ReportStyle()))
    group=EquationGroup(Equation(appearance.SourceLiteral("X"),Fraction("1","2")),block_id="probe")
    geometry={"x":100,"equations":[{"baseline":150,"lhs_start":100,"first_equal":140,"rhs_start":160}]}
    with pytest.raises(ValueError,match="Unsupported source semantic node: Fraction"):
        appearance.placed_equations(group,geometry,context,300)


def test_unsupported_remaining_atom_cannot_be_silently_dropped():
    from gridlayoutpdf import Fraction,Row
    appearance=module("appearance")
    with pytest.raises(ValueError,match="Unsupported source semantic node: Fraction"):
        appearance._split_nodes(Row(appearance.SourceLiteral("A"),Fraction("1","2"),gap=0),[1])


@pytest.mark.parametrize("baseline, fits", [(7.9, True), (6.9, False), (12.3, False)])
def test_source_table_uses_real_ink_clearance_without_moving_authored_baseline(baseline, fits):
    from gridlayoutpdf import Cell, LayoutOverflowError, Table
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    style=TextStyle(size=9.9)
    original_metrics=fonts.measure("A",style)
    cell=appearance.SourceCell((appearance.SourceLiteral("A"),),(style,),
          ({"start_x":2,"baseline":baseline},),12,block_id="ink-cell")
    table=Table((2000,),((Cell(cell,align="left",padding=0),),),
                row_heights=(1200,),border_width=.5,block_id="ink-table")
    frame=appearance.PageFrame(1,((table,{"kind":"table","x":70,"y":100,"width":20}),),
                               ("ink-table",))
    context=LayoutContext(fonts,A4_PORTRAIT_REFERENCE,ReportStyle())
    if not fits:
        with pytest.raises(LayoutOverflowError):
            measure_block(frame,context,482.4)
        return
    measured=measure_block(frame,context,482.4)
    text=next(command for command in measured.commands if isinstance(command,Text))
    assert text.y+context.profile.grid.origin_y==pytest.approx(100+baseline)
    assert (text.style.font,text.style.size,text.text)==(style.font,style.size,"A")
    assert original_metrics.ascent>baseline
    assert baseline+original_metrics.ink_bounds.y>.5
    assert fonts.measure("A",style)==original_metrics


def test_relation_anchor_cannot_replace_the_semantic_manuscript_character():
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    line={"start_x":100,"baseline":150,"relations":[
          {"character_offset":1,"text":"X","center":130}]}
    with pytest.raises(ValueError,match="Source relation transcript differs"):
        appearance.anchored_commands(appearance.SourceLiteral("A=B"),line,fonts,TextStyle())


def test_cell_cannot_silently_drop_lines_without_matching_styles():
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    cell=appearance.SourceCell((appearance.SourceLiteral("FIRST"),appearance.SourceLiteral("SECOND")),
          (TextStyle(),),({"start_x":1,"baseline":10},),20)
    context=appearance.local_context(LayoutContext(fonts,A4_PORTRAIT_REFERENCE,ReportStyle()))
    with pytest.raises(ValueError,match="cell lines and styles differ"):
        cell.measure(context,100)


@pytest.mark.parametrize("baseline, fits", [(9.0, True), (8.9, False)])
def test_only_documented_header_ink_contact_allows_less_than_point_zero_five_shift(baseline, fits):
    from gridlayoutpdf import LayoutOverflowError, command_bounds
    appearance=module("appearance")
    fonts=module("builder").fixture_fonts()
    ink_fonts=appearance.SourceTableInkFonts(fonts)
    cell=appearance.SourceCell((appearance.SourceLiteral("組合せ"),),(TextStyle(size=9.9),),
          ({"start_x":2,"baseline":baseline},),11.34,
          block_id="p30-combinations-md-r0-cell1",clearance=(.061,.961,.061,.061))
    context=appearance.local_context(LayoutContext(ink_fonts,A4_PORTRAIT_REFERENCE,ReportStyle()))
    if not fits:
        with pytest.raises(LayoutOverflowError,match="ink clearance exceeds 0.05 pt"):
            cell.measure(context,40)
        return
    measured=cell.measure(context,40)
    text=next(c for c in measured.commands if isinstance(c,Text))
    assert text.y==pytest.approx(9.043421875)
    assert command_bounds(text,ink_fonts).y==pytest.approx(.961)
