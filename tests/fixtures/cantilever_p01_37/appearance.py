"""Native semantic components with explicitly authored source typography.

Only block, formula-role and line anchors are accepted. This module never
opens the source PDF, an expected transcript, or a list of glyph coordinates.
"""
from dataclasses import dataclass, replace
import math

from gridlayoutpdf import (
    A4_PORTRAIT_REFERENCE, EquationGroup, FontRegistry, GridSpec, LayoutContext, LayoutOverflowError,
    LayoutPart, Line, Literal, MathBox, MathBlock, MeasuredBlock, PageProfile, Paragraph,
    ReportStyle, Row, Text, TextStyle, command_bounds, measure_block, wrap_math,
)

PITCH = .01

# These original header glyphs touch the inside of their 0.96 pt top rule.
# Reserve only their measured ink clearance, never a general font-box shift.
SOURCE_INK_CLEARANCE_CELLS = frozenset({
    "p30-combinations-md-r0-cell1", "p31-combinations-md-r0-cell1",
    "p32-combinations-vd-r0-cell1", "p33-combinations-vd-r0-cell1",
    "p34-combinations-mt-r0-cell1", "p35-combinations-mt-r0-cell1",
    "p32-combinations-vd-r0-cell2", "p33-combinations-vd-r0-cell2",
})


class SourceTableInkFonts(FontRegistry):
    """Fixture-only table measurement using actual glyph ink and advance.

    The original's tight rows contain the glyphs but not necessarily a face's
    global ascent rectangle. Keep every native command and all ink checks;
    only omit that unrelated face-wide vertical reservation inside tables.
    The document and renderer retain the caller's unmodified registry.
    """

    def __init__(self, fonts):
        super().__init__()
        self.source = fonts

    def resolve(self, name):
        return self.source.resolve(name)

    def measure(self, text, style):
        metrics = self.source.measure(text, style)
        ink = metrics.ink_bounds
        if ink is None:
            raise ValueError("Source table requires explicit glyph ink bounds")
        return replace(metrics, ascent=max(0, -ink.y), descent=max(0, ink.bottom))


def local_context(context, *, width=800, height=800):
    columns, rows = math.ceil(width/PITCH), math.ceil(height/PITCH)
    profile = PageProfile("cantilever-source-local", columns*PITCH, rows*PITCH,
                          GridSpec(0,0,PITCH,PITCH,columns,rows))
    return LayoutContext(context.fonts, profile, replace(context.style,baseline_offset=9))


@dataclass(frozen=True)
class SourceLiteral:
    text: str

    def measure(self, fonts, style):
        Literal(self.text)  # Preserve the public atom's input contract.
        runs = []
        for char in self.text:
            advance = fonts.measure(char,replace(style,tracking=0)).width
            tracking = advance*.008
            if runs and abs(runs[-1][0]-tracking)<1e-10:
                runs[-1][1] += char
            else:
                runs.append([tracking,char])
        width = ascent = descent = 0
        commands = []
        for tracking, text in runs:
            run_style = replace(style,tracking=tracking)
            box = Literal(text).measure(fonts,run_style)
            commands.extend(box.translated(width,0))
            width += box.width+tracking
            ascent,descent=max(ascent,box.ascent),max(descent,box.descent)
        return MathBox(width,ascent,descent,tuple(commands),style.size*.25)


@dataclass(frozen=True)
class StyledSourceLiteral:
    text: str
    runs: tuple
    origin_x: float = 0

    def measure(self,fonts,style):
        pieces=[]
        offset=0
        active=None
        value=""
        for char in self.text:
            font=next((run["font"] for run in self.runs if run["start"]<=offset<run["stop"]),style.font)
            if active is not None and active!=font:
                pieces.append((active,value));value=""
            active=font;value+=char
            if not char.isspace():offset+=1
        if value:pieces.append((active,value))
        width=ascent=descent=0;commands=[]
        offset=0
        for font,text in pieces:
            anchor=next((run.get("x") for run in self.runs if run["start"]==offset and "x" in run),None)
            if anchor is not None:
                width=anchor-self.origin_x
                text=text.lstrip()
            box=SourceLiteral(text).measure(fonts,replace(style,font=font))
            commands.extend(box.translated(width,0));width+=box.width
            ascent=max(ascent,box.ascent);descent=max(descent,box.descent)
            offset+=len("".join(text.split()))
        return MathBox(width,ascent,descent,tuple(commands),style.size*.25)


@dataclass(frozen=True)
class SourceFont:
    node: object
    font: str

    def measure(self,fonts,style):return self.node.measure(fonts,replace(style,font=self.font))


@dataclass(frozen=True)
class SourceShear:
    node: object
    shear_x: float

    def measure(self,fonts,style):
        box=self.node.measure(fonts,style)
        return replace(box,commands=tuple(replace(command,shear_x=self.shear_x)
                       if isinstance(command,Text) else command for command in box.commands))


def shear_atoms(node,atoms):
    """Apply authored emphasis to complete semantic atoms, never glyph positions."""
    if isinstance(node,(Literal,SourceLiteral)):
        value=next((atom["shear_x"] for atom in atoms if atom["text"]==node.text),None)
        return SourceShear(node,value) if value is not None else node
    if isinstance(node,Row):
        return Row(*(shear_atoms(child,atoms) for child in node.items),gap=node.gap)
    if isinstance(node,SourceScript):
        gap=next((atom.get("script_gap",node.gap) for atom in atoms if atom["text"]==_flatten_text(node.base)),node.gap)
        return replace(node,base=shear_atoms(node.base,atoms),gap=gap,
                       superscript=shear_atoms(node.superscript,atoms) if node.superscript else None,
                       subscript=shear_atoms(node.subscript,atoms) if node.subscript else None)
    return node


def _font_runs(node,runs,offset=0):
    count=len("".join(_flatten_text(node).split()))
    names={run["font"] for run in runs if run["start"]<offset+count and run["stop"]>offset}
    if len(names)==1:return SourceFont(node,next(iter(names)))
    if isinstance(node,Row):
        children=[]
        for child in node.items:
            children.append(_font_runs(child,runs,offset))
            offset+=len("".join(_flatten_text(child).split()))
        return Row(*children,gap=node.gap)
    if isinstance(node,(Literal,SourceLiteral)):
        return StyledSourceLiteral(node.text,tuple({**run,"start":run["start"]-offset,"stop":run["stop"]-offset} for run in runs))
    return node


@dataclass(frozen=True)
class SourceScript:
    base: object
    superscript: object | None = None
    subscript: object | None = None
    gap: float = 0
    superscript_x: float | None = None
    subscript_x: float | None = None
    superscript_y: float = -2.4
    subscript_y: float = 1.92

    def measure(self,fonts,style):
        base = self.base.measure(fonts,style)
        commands = list(base.commands)
        width,ascent,descent=base.width,base.ascent,base.descent
        script_size = 6.6 if abs(style.size-9.9)<.01 else round(style.size*.67,1)
        script_style=replace(style,size=script_size)
        for node,y,offset in ((self.superscript,self.superscript_y,self.superscript_x),
                              (self.subscript,self.subscript_y,self.subscript_x)):
            if node is not None:
                box=node.measure(fonts,script_style)
                x=base.width+self.gap if offset is None else offset
                commands.extend(box.translated(x,y))
                width=max(width,x+box.width)
                ascent=max(ascent,box.ascent-y)
                descent=max(descent,box.descent+y)
        return MathBox(width,ascent,descent,tuple(commands),style.size*.25)


@dataclass(frozen=True)
class SourceCell:
    lines: tuple
    styles: tuple
    anchors: tuple
    height: float
    block_id: str = ""
    clearance: tuple = (.061,.061,.061,.061)
    vertical_glyphs: dict | None = None

    def measure(self,context,available_width):
        if len(self.lines)!=len(self.styles):
            raise ValueError(f"{self.block_id}: cell lines and styles differ")
        nonempty=[(node,style) for node,style in zip(self.lines,self.styles) if _flatten_text(node).strip()]
        if len(nonempty)!=len(self.anchors):
            if not self.anchors or any("text" not in anchor for anchor in self.anchors):
                raise ValueError(f"{self.block_id}: authored cell lines differ from source anchors")
            nodes=_split_nodes(Row(*(node for node,_ in nonempty),gap=0),
                               [len("".join(anchor["text"].split())) for anchor in self.anchors])
            nonempty=[(node,self.styles[min(anchor.get("authored_line_index",0),len(self.styles)-1)])
                      for node,anchor in zip(nodes,self.anchors)]
        commands=[]
        for (node,style),anchor in zip(nonempty,self.anchors):
            if anchor.get("text_with_spaces") is not None:
                node=source_whitespace(node,anchor["text_with_spaces"])
            vertical=(self.vertical_glyphs or {}).get(_flatten_text(node))
            if vertical:style=replace(style,size=vertical["size"])
            box=node.measure(context.fonts,style)
            x,y=anchor["start_x"],anchor["baseline"]
            quarter=anchor.get("local_quarter_turns",0)
            if quarter:
                if any(not isinstance(c,Text) for c in box.commands):
                    raise ValueError("Only source vertical text runs may turn inside a cell")
                turned=[]
                for command in box.commands:
                    dx,dy=command.x,command.y
                    for _ in range(quarter):dx,dy=dy,-dx
                    turned.append(replace(command,x=x+dx,y=y+dy,quarter_turns=quarter))
                source_box=anchor.get("source_bbox")
                if source_box:
                    bounds=[text_ink_bounds(c,context.fonts) if vertical else command_bounds(c,context.fonts) for c in turned]
                    actual=(min(b.x for b in bounds),min(b.y for b in bounds),max(b.right for b in bounds),max(b.bottom for b in bounds))
                    if vertical:
                        xmin,ymin,xmax,ymax=vertical["glyph_bounds"]
                        scale=vertical["size"]/vertical["units_per_em"]
                        source_box=(source_box[0]+xmin*scale,source_box[1]-ymax*scale*vertical["matrix_y"],
                                    source_box[0]+xmax*scale,source_box[1]-ymin*scale*vertical["matrix_y"])
                    dx=(source_box[0]+source_box[2]-actual[0]-actual[2])/2
                    dy=(source_box[1]+source_box[3]-actual[1]-actual[3])/2
                    turned=[c.translated(dx,dy) for c in turned]
                commands.extend(turned)
                continue
            if anchor.get("semantic_runs") or anchor.get("relations"):
                placed=anchored_commands(node,anchor,context.fonts,style)
                commands.extend(placed)
            else:
                commands.extend(box.translated(x,y))
        if self.block_id in SOURCE_INK_CLEARANCE_CELLS and commands:
            top=min(command_bounds(command,context.fonts).y for command in commands)
            adjustment=max(0,self.clearance[1]-top)
            if adjustment>.05:
                raise LayoutOverflowError(f"{self.block_id}: source glyph ink clearance exceeds 0.05 pt",block_id=self.block_id)
            commands=[command.translated(0,adjustment) for command in commands]
        return MeasuredBlock(available_width,PITCH,(LayoutPart(round(self.height/PITCH),tuple(commands)),),block_id=self.block_id)


def text_ink_bounds(command,fonts):
    from gridlayoutpdf import Rect
    ink=fonts.measure(command.text,command.style).ink_bounds
    points=[]
    for x,y in ((ink.x,ink.y),(ink.right,ink.y),(ink.right,ink.bottom),(ink.x,ink.bottom)):
        for _ in range(command.quarter_turns):x,y=y,-x
        points.append((command.x+x,command.y+y))
    left,top=min(x for x,y in points),min(y for x,y in points)
    return Rect(left,top,max(x for x,y in points)-left,max(y for x,y in points)-top)


def source_whitespace(node,text):
    """Restore authored spaces while retaining Script/Row structure and characters."""
    if "".join(_flatten_text(node).split())!="".join(text.split()):
        raise ValueError("Source whitespace transcript differs from semantic content")
    pending={};offset=0
    for char in text:
        if char.isspace():pending[offset]=pending.get(offset,"")+char
        else:offset+=1
    offset=0
    def visit(part):
        nonlocal offset
        if isinstance(part,(SourceFont,SourceShear)):
            return replace(part,node=visit(part.node))
        if isinstance(part,(Literal,SourceLiteral,StyledSourceLiteral)):
            value=""
            for char in "".join(part.text.split()):
                value+=pending.pop(offset,"")+char;offset+=1
            return replace(part,text=value) if isinstance(part,StyledSourceLiteral) else SourceLiteral(value)
        if isinstance(part,Row):return Row(*(visit(child) for child in part.items),gap=0)
        if isinstance(part,SourceScript):
            base=visit(part.base)
            sub=visit(part.subscript) if part.subscript else None
            sup=visit(part.superscript) if part.superscript else None
            return replace(part,base=base,superscript=sup,subscript=sub)
        return part
    result=visit(node)
    trailing=pending.pop(offset,"")
    if pending:raise ValueError("Source whitespace boundary is not a supported semantic atom")
    return Row(result,SourceLiteral(trailing),gap=0) if trailing else result


def child_trace(measured,x,y):
    trace={"block_id":measured.block_id,"x_pt":x,"y_pt":y,"width":measured.width,
           "rows":measured.rows,"row_pitch":measured.row_pitch}
    row=0
    for group,parts in (("prefix",measured.prefix),("parts",measured.parts)):
        trace[group]=[]
        for part in parts:
            trace[group].append({"row":row,"rows":part.rows,"metadata":part.metadata})
            row+=part.rows
    return trace


def _baseline(commands):
    texts=[c for c in commands if isinstance(c,Text)]
    if not texts:
        return 0
    largest=max(c.style.size for c in texts)
    return next(c.y for c in texts if c.style.size==largest)


def _placed_lines(block,geometry,context,width):
    """Place measured semantic lines, retaining their complete native commands."""
    measured=measure_block(block,context,width)
    lines=geometry.get("lines",[])
    if not lines:
        lines=[{"baseline":geometry["baseline"],"start_x":geometry["x"]}]
    if len(lines)!=len(measured.parts):
        raise LayoutOverflowError(f"{block.block_id}: source line count differs: {len(lines)} versus {len(measured.parts)}",block_id=block.block_id)
    output=[]
    top=min(line["baseline"] for line in lines)-max((command_bounds(c,context.fonts).height for c in measured.commands),default=10)
    left=min(line.get("start_x",geometry["x"]) for line in lines)
    character_offset=0
    for part,line in zip(measured.parts,lines):
        commands=part.commands
        node=None
        if isinstance(block,Paragraph) and commands:
            text=next(c for c in commands if isinstance(c,Text))
            runs=tuple({**run,"start":run["start"]-character_offset,"stop":run["stop"]-character_offset} for run in geometry.get("font_runs",[]))
            node=StyledSourceLiteral(text.text,runs,line.get("start_x",geometry["x"])) if runs else SourceLiteral(text.text)
            commands=node.measure(context.fonts,text.style).commands
            character_offset+=len("".join(text.text.split()))
        elif isinstance(block,MathBlock):
            node=block.expression
            if geometry.get("font_runs"):
                node=_font_runs(node,geometry["font_runs"])
                commands=node.measure(context.fonts,block.style or context.style.body).commands
        if node is not None and line.get("text_with_spaces") is not None:
            node=source_whitespace(node,line["text_with_spaces"])
            commands=node.measure(context.fonts,block.style or context.style.body).commands
        if node is not None and (line.get("relations") or line.get("semantic_runs")):
            absolute=anchored_commands(node,line,context.fonts,block.style or context.style.body)
            output.extend(c.translated(-left,-top) for c in absolute)
            continue
        baseline=_baseline(commands)
        output.extend(c.translated(line.get("start_x",geometry["x"])-left,line["baseline"]-top-baseline) for c in commands)
    bounds=[command_bounds(c,context.fonts) for c in output]
    shift=min((b.y for b in bounds),default=0)
    output=[c.translated(0,-shift) for c in output]
    top+=shift
    height=max((b.bottom-shift for b in bounds),default=1)
    tight_width=max((b.right for b in bounds),default=width)
    result=MeasuredBlock(tight_width,PITCH,(LayoutPart(max(1,math.ceil(height/PITCH)),tuple(output)),),block_id=block.block_id)
    return result,left,top


def _flatten_text(node):
    if isinstance(node,(SourceFont,SourceShear)):return _flatten_text(node.node)
    if isinstance(node,(Literal,SourceLiteral,StyledSourceLiteral)):
        return node.text
    if isinstance(node,Row):
        return "".join(_flatten_text(child) for child in node.items)
    if isinstance(node,SourceScript):
        return _flatten_text(node.base)+(_flatten_text(node.subscript) if node.subscript else "")+(_flatten_text(node.superscript) if node.superscript else "")
    raise ValueError(f"Unsupported source semantic node: {type(node).__name__}")


def anchored_commands(node,line,fonts,style):
    if line.get("text_with_spaces") is not None:
        node=source_whitespace(node,line["text_with_spaces"])
    runs=line.get("semantic_runs")
    if runs:
        counts=[len("".join(run["text"].split())) for run in runs]
        if any(count==0 for count in counts):raise ValueError("Empty semantic source run")
        pieces=_split_nodes(node,counts)
        commands=[]
        offset=0
        for piece,run,count in zip(pieces,runs,counts):
            if run["character_offset"]!=offset:raise ValueError("Source semantic runs are not contiguous")
            piece=source_whitespace(piece,run.get("text_with_spaces",run["text"]))
            if "script_gap" in run:
                piece=script_gap(piece,run["script_gap"])
            if "script_offsets" in run:
                piece=script_gap(piece,offsets=run["script_offsets"])
            relations=[{**relation,"character_offset":relation["character_offset"]-offset}
                       for relation in line.get("relations",[]) if offset<=relation["character_offset"]<offset+count]
            if relations:
                subline={"start_x":run["start_x"],"baseline":run.get("baseline",line["baseline"]),"relations":relations}
                commands.extend(anchored_commands(piece,subline,fonts,style))
            else:
                box=piece.measure(fonts,style)
                commands.extend(box.translated(run["start_x"],run.get("baseline",line["baseline"])))
            offset+=count
        return tuple(commands)
    relations=line.get("relations",[])
    if not relations:
        return node.measure(fonts,style).translated(line["start_x"],line["baseline"])
    count=len("".join(_flatten_text(node).split()))
    counts=[];previous=0
    for relation in relations:
        counts.extend((relation["character_offset"]-previous,len(relation["text"])))
        previous=relation["character_offset"]+len(relation["text"])
    counts.append(count-previous)
    if min(counts)<0:raise ValueError("Source relation anchors exceed semantic text")
    pieces=_split_nodes(node,counts)
    commands=[];x=line["start_x"]
    for index,piece in enumerate(pieces):
        if index%2:
            relation=relations[index//2]
            text="".join(_flatten_text(piece).split())
            if text!="".join(relation["text"].split()):
                raise ValueError("Source relation transcript differs from semantic content")
            box=Literal(text).measure(fonts,style)
            natural=fonts.measure(text,replace(style,tracking=0)).width
            x=relation["center"]-natural/2
            commands.extend(box.translated(x,relation.get("baseline",line["baseline"])))
            x+=natural
        else:
            box=piece.measure(fonts,style)
            commands.extend(box.translated(x,line["baseline"]));x+=box.width
    return tuple(commands)


def script_gap(node,value=None,*,offsets=None):
    """Set the extra separation of a single semantic script atom."""
    count=0
    def visit(part):
        nonlocal count
        if isinstance(part,SourceScript):
            count+=1
            changes={"gap":value} if value is not None else {}
            if offsets is not None:
                if set(offsets)-{"sub_x","sup_x","sub_y","sup_y"}:raise ValueError("Unknown source script offset")
                changes.update({("superscript_" if key.startswith("sup_") else "subscript_")+key[-1]:x
                                for key,x in offsets.items()})
            return replace(part,**changes)
        if isinstance(part,Row):return Row(*(visit(child) for child in part.items),gap=part.gap)
        if isinstance(part,(SourceFont,SourceShear)):return replace(part,node=visit(part.node))
        return part
    result=visit(node)
    if count!=1:raise ValueError("A source script gap must identify exactly one Script atom")
    return result


def _split_nodes(node,counts):
    """Split authored atoms at explicit source line boundaries; scripts stay whole."""
    def atoms_for(value):
        if isinstance(value,Row):
            return [atom for child in value.items for atom in atoms_for(child)]
        return [value]
    atoms=atoms_for(node)
    groups=[]
    for wanted in counts:
        used=0
        group=[]
        while used<wanted and atoms:
            atom=atoms.pop(0)
            count=len("".join(_flatten_text(atom).split()))
            if used+count<=wanted:
                group.append(atom);used+=count
            elif isinstance(atom,(Literal,SourceLiteral,StyledSourceLiteral)):
                needed=wanted-used
                index=0
                for index,char in enumerate(atom.text,1):
                    needed-=not char.isspace()
                    if needed==0:break
                if isinstance(atom,StyledSourceLiteral):
                    before=tuple({k:v for k,v in run.items() if k!="x"} for run in atom.runs)
                    after=tuple({**run,"start":run["start"]-(wanted-used),"stop":run["stop"]-(wanted-used)} for run in before)
                    group.append(StyledSourceLiteral(atom.text[:index],before))
                    atoms.insert(0,StyledSourceLiteral(atom.text[index:],after))
                else:
                    group.append(SourceLiteral(atom.text[:index]))
                    atoms.insert(0,SourceLiteral(atom.text[index:]))
                used=wanted
            elif isinstance(atom,SourceFont):
                needed=wanted-used
                before,after=_split_nodes(atom.node,(needed,count-needed))
                group.append(SourceFont(before,atom.font))
                atoms.insert(0,SourceFont(after,atom.font))
                used=wanted
            else:
                raise ValueError("Source equation line boundary cuts an indivisible math atom")
        if used!=wanted:raise ValueError("Source equation line text is inconsistent with semantic RHS")
        groups.append(Row(*group,gap=0))
    if atoms and any(_flatten_text(atom).strip() for atom in atoms):
        raise ValueError("Source equation lines omit semantic RHS content")
    return groups


def placed_equations(group,geometry,context,width):
    records=geometry.get("equations",[])
    if len(records)!=len(group.equations):
        raise ValueError(f"{group.block_id}: source equation count differs")
    commands=[]
    left=min([geometry["x"],*(r["lhs_marker"]["x"] for r in records if "lhs_marker" in r)])
    top=min(record["baseline"] for record in records)-20
    metadata=[]
    for equation,record in zip(group.equations,records):
        style=equation.style or group.style or context.style.body
        baseline=record["baseline"]
        def put(node,x,y=baseline):
            box=node.measure(context.fonts,style)
            commands.extend(box.translated(x-left,y-top))
            return box
        def put_role(node,role,x,y=baseline):
            if record.get(role+"_semantic_runs"):
                line={"start_x":x,"baseline":y,"semantic_runs":record[role+"_semantic_runs"]}
                commands.extend(c.translated(-left,-top) for c in anchored_commands(node,line,context.fonts,style))
            else:
                put(node,x,y)
        lhs=equation.lhs
        if "lhs_marker" in record:
            marker=record["lhs_marker"]
            put(SourceLiteral(marker["text"]),marker["x"],marker["baseline"])
            if isinstance(lhs,Row) and _flatten_text(lhs.items[0])==marker["text"]:
                lhs=Row(*lhs.items[1:],gap=0)
            elif isinstance(lhs,(Literal,SourceLiteral)) and lhs.text.startswith(marker["text"]):
                lhs=SourceLiteral(lhs.text[len(marker["text"]):].lstrip())
            else:raise ValueError("Source marker is not the authored LHS prefix")
        if record.get("lhs_text_with_spaces") is not None:
            lhs=source_whitespace(lhs,record["lhs_text_with_spaces"])
        if _flatten_text(lhs).strip():put_role(lhs,"lhs",record.get("lhs_start",left))
        if "first_equal" in record:
            relation=Literal(equation.relation.strip()).measure(context.fonts,style)
            natural=context.fonts.measure(equation.relation.strip()[0],replace(style,tracking=0)).width
            if record.get("relation_semantic_runs"):
                put_role(SourceLiteral(equation.relation.strip()),"relation",record["first_equal"]-natural/2)
            else:
                commands.extend(relation.translated(record["first_equal"]-natural/2-left,baseline-top))
        rhs_lines=record.get("rhs_lines",[])
        if rhs_lines and len(rhs_lines)>1 and all("text" in line for line in rhs_lines):
            counts=[len("".join(line["text"].split())) for line in rhs_lines]
            nodes=_split_nodes(equation.rhs,counts)
            for node,line in zip(nodes,rhs_lines):
                commands.extend(c.translated(-left,-top) for c in anchored_commands(node,line,context.fonts,style))
        elif _flatten_text(equation.rhs).strip():
            line=rhs_lines[0] if rhs_lines else {"start_x":record["rhs_start"],"baseline":baseline}
            commands.extend(c.translated(-left,-top) for c in anchored_commands(equation.rhs,line,context.fonts,style))
        if equation.result is not None:
            result_baseline=record.get("result_baseline",baseline)
            if "second_equal" in record:
                relation=Literal(equation.result_relation.strip()).measure(context.fonts,style)
                natural=context.fonts.measure(equation.result_relation.strip()[0],replace(style,tracking=0)).width
                if record.get("result_relation_semantic_runs"):
                    put_role(SourceLiteral(equation.result_relation.strip()),"result_relation",record["second_equal"]-natural/2,result_baseline)
                else:
                    commands.extend(relation.translated(record["second_equal"]-natural/2-left,result_baseline-top))
            result_node=equation.result
            if record.get("result_text_with_spaces") is not None:
                result_node=source_whitespace(result_node,record["result_text_with_spaces"])
            result=result_node.measure(context.fonts,style)
            put_role(result_node,"result",record["result_right"]-result.width,result_baseline)
            if equation.unit is not None:
                unit=source_whitespace(equation.unit,record["unit_text_with_spaces"]) if record.get("unit_text_with_spaces") is not None else equation.unit
                put_role(unit,"unit",record["unit_start"],record.get("unit_baseline",result_baseline))
        if equation.label:
            put(SourceLiteral(equation.label),record.get("label_start",left))
        metadata.append({"equation_index":len(metadata),"anchors_pt":{name:record[name]-left for name in ("first_equal","second_equal","result_right","unit_start") if name in record},"rhs_start_pt":record.get("rhs_start",left)-left})
    bounds=[command_bounds(c,context.fonts) for c in commands]
    if min((b.x for b in bounds),default=0)<-1e-7 or max((b.right for b in bounds),default=0)>width+1e-7:
        raise LayoutOverflowError(f"{group.block_id}: source equation horizontal overflow",block_id=group.block_id)
    shift=min((b.y for b in bounds),default=0)
    commands=[c.translated(0,-shift) for c in commands]
    top+=shift
    height=max((b.bottom-shift for b in bounds),default=1)
    tight_width=max((b.right for b in bounds),default=width)
    measured=MeasuredBlock(tight_width,PITCH,(LayoutPart(math.ceil(height/PITCH),tuple(commands),{"equations":metadata}),),block_id=group.block_id)
    return measured,left,top


def continuous_table_rules(commands):
    """Join Table part seam insets, retaining native lines and intentional gaps."""
    groups={}
    others=[]
    for command in commands:
        if not isinstance(command,Line) or (command.x1!=command.x2 and command.y1!=command.y2):
            others.append(command)
            continue
        vertical=command.x1==command.x2
        position=command.x1 if vertical else command.y1
        start,stop=sorted((command.y1,command.y2) if vertical else (command.x1,command.x2))
        key=(vertical,position,command.width,command.color)
        groups.setdefault(key,[]).append((start,stop,command))
    for (vertical,position,width,color),segments in groups.items():
        merged=[]
        for start,stop,command in sorted(segments,key=lambda segment:segment[0]):
            if merged and start-merged[-1][1]<=width+1e-7:
                merged[-1]=(merged[-1][0],max(merged[-1][1],stop),merged[-1][2])
            else:
                merged.append((start,stop,command))
        for start,stop,command in merged:
            others.append(replace(command,y1=start,y2=stop) if vertical else replace(command,x1=start,x2=stop))
    return tuple(others)


@dataclass(frozen=True)
class PageFrame:
    source_page: int
    placements: tuple
    declared_ids: tuple

    @property
    def block_id(self):return f"p{self.source_page:02}-content"

    @property
    def children(self):return tuple(block for block,_ in self.placements)

    def measure(self,context,available_width):
        origin=context.profile.grid
        local=local_context(context)
        commands=[]
        children=[]
        actual_ids=set()
        parent_frames={}
        for block,geometry in self.placements:
            width=geometry.get("width",available_width)
            kind=geometry["kind"]
            if kind=="equations":
                measured,x,y=placed_equations(block,geometry,local,width)
            elif kind in ("paragraph","math"):
                measured,x,y=_placed_lines(block,geometry,local,width)
            else:
                measuring=replace(local,fonts=SourceTableInkFonts(context.fonts)) if kind=="table" else local
                measured=measure_block(block,measuring,width)
                x,y=geometry["x"],geometry["y"]
            dx,dy=x-origin.origin_x,y-origin.origin_y
            native=measured.translated(dx,dy)
            commands.extend(continuous_table_rules(native) if kind=="table" else native)
            children.append(child_trace(measured,dx,dy))
            for parent in geometry.get("parents",[]):
                parent_frames.setdefault(parent,[]).append((dx,dy,dx+measured.width,dy+measured.height))
            actual_ids.add(block.block_id)
            def find_ids(value):
                if hasattr(value,"items"):
                    if isinstance(value.get("block_id"),str):actual_ids.add(value["block_id"])
                    for child in value.values():find_ids(child)
                elif isinstance(value,(list,tuple)):
                    for child in value:find_ids(child)
            find_ids(children[-1])
        # Empty spacers and structural containers are still declared explicitly.
        for identifier in self.declared_ids:
            if identifier not in actual_ids:
                frames=parent_frames.get(identifier,[])
                x=min((f[0] for f in frames),default=0)
                y=min((f[1] for f in frames),default=0)
                right=max((f[2] for f in frames),default=available_width)
                bottom=max((f[3] for f in frames),default=0)
                children.append({"block_id":identifier,"x_pt":x,"y_pt":y,"width":right-x,"rows":math.ceil((bottom-y)/PITCH),"row_pitch":PITCH,"prefix":[],"parts":[]})
        return MeasuredBlock(available_width,origin.pitch_y,(LayoutPart(context.profile.body_end_row-context.profile.body_start_row,tuple(commands),{"children":children,"source_page":self.source_page}),),keep_together=True,block_id=self.block_id)
