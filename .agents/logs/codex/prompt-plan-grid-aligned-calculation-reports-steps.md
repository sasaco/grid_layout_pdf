# Objective

Decompose a custom Python PDF calculation-report library into an ordered, independently testable implementation plan. Read the local evidence and provide design advice only. Do NOT edit files, install anything, start recursive consultations or invoke other agents. The root agent will author the plan.

# Confirmed requirements

- User deliberately chose a custom reusable OOP library, with grid-adjusted layout as its differentiator. Initial authoring interface is Python, not a GUI designer.
- A grid cell is a placement unit for paragraphs/equations/tables, NOT a full-width character cell. Preserve configured font size and glyph proportions; do not shrink automatically to fit.
- Add blocks top-to-bottom with automatic height reservation/pagination and explicit positioning when needed.
- Acceptance is equivalent expression/readability on the supplied grid, NOT exact reference PDF coordinates, byte equality, or identical page breaks.
- Equations are structured Python components (fraction, root, scripts, relation, chain/group), not a TeX parser. Computation of structural engineering results is outside this library.
- Long equations wrap at semantically valid structural boundaries with manual break hints, preserve fraction/root atomicity and equality alignment; fail clearly on unbreakable overflow.
- First release supports A4 portrait default, A3/landscape, and mixed page settings within one PDF. Existing external PDF pages are evidence for mixed sizes, not authorization to implement PDF importing.

# Current state and evidence

- New repository: no product code, manifest or executable product tests. Only shared skills/bootstrap, design documents, references. Do not invent existing product paths or frame this as an in-place P7 migration.
- Read `CONTEXT.md`, `.agents/docs/DESIGN.md` (FR001-011), `.agents/rules/project.md` and `.agents/rules/project-scope.md`.
- Read `.agents/docs/research/grid-reference-findings.md` and `.agents/docs/research/sample-report-findings.md`.
- A4 grid: MediaBox595x842 pt, 30 columns x47 rows, origin(50.88,54.598) from top-left at line centers, pitch(16.08,15.48)pt, line thickness0.96pt. No text/font instructions in grid.
- A3 grid has just been measured: same origin/pitch/47 rows, 67 columns, landscape. Full evidence may be appended while you read; do not guess any not-yet-recorded MediaBox number.
- Ten sample PDFs/251 pages structurally inspected,14 representative pages visually inspected. Body glyph advances10.08pt/5.04pt and e.g. baseline delta14.88pt do NOT match grid pitch; preserve grid-based normalized appearance, do not reproduce old coordinates.
- Representative proof cases: `tests/output/08_線路.pdf` p2 two equality columns, result-right and unit-left alignment; `13_片持ち梁照査.pdf` p54 stacked fractions, scripts, roots/brackets, derivations; `12_フーチング.pdf` p1 merged cells/multirow headers/dense table; `07_荷重計算.pdf` p1 heading+table+diagram+wrapped equations. A3 mixed-size evidence in10/11.
- Source PDFs must remain unchanged; generated fixtures/output live elsewhere.

# Design direction to assess (proposals, not user-approved details)

- Custom layout engine over a narrow PDF drawing backend; ReportLab Canvas is a likely backend because of existing P7 usage and font/vector support. Own grid/measure/place/wrap/pagination and semantic components, not PDF file serialization. Use PyMuPDF only for development extraction/visual QA initially.
- Immutable GridSpec/PageProfile/Style + semantic document/block/math trees -> deterministic measurement -> page placement with progress guarantees -> scene/drawing commands -> backend. One top-left coordinate convention and explicit conversion at renderer boundary.
- Text glyph advance/font metrics are distinct from block/grid geometry. Block start/occupied rows follow grid; fractions/scripts have locally measured sub-row positions. Intentional script style sizes are not overflow shrinking. Baseline conventions and anchor-left/center semantics must be explicit.
- Named equation alignment groups scope anchors locally; calculate shared columns against widest left side then snap, allow explicit anchors, multiple relation columns, result and unit slots. Account for all wrapped continuation lines before placing subsequent blocks. Unbreakable overflow must diagnose source block/path/size.
- Mixed page templates are explicit at first; no automatic switch to larger paper to hide overflow. A3 is wider at the same pitch, not scaled A4. Ordinary figure scaling allowed as explicit/aspect-preserving placement, independent of font policy.
- Keep interfaces/dependencies small; avoid speculative plugin ecosystems. No GUI, TeX parser, symbolic calculator, Excel export, full P7 migration, arbitrary PDF import in first release.

# Constraints

- Put uncertainty-heavy typography/math/anchor proof cases early before a large API/framework build.
- Identify concrete NEW module and test paths. Ordered steps must form an achievable staged thin slice, then additive capabilities. No product implementation in this task.
- Separate mechanical unit tests, independent PDF geometry checks, visual acceptance, and source-preservation hashes. Avoid circular tests that merely compare implementation outputs to themselves.
- Must address mixed Japanese/Latin, Greek glyph coverage, intentional scripts, CJK wrapping, baseline/ink boxes, multiple equals, long labels/results/units, rowspans across page breaks, impossible blocks, explicit placement collisions, repeated page styles and total page numbers.
- Recommendations can decide routine technical defaults. Report genuinely user-facing blockers rather than fabricate approvals. Do not request needless further user questions.

# Output

## Implementation Steps (ordered by dependency)
## Verification per Step
## Risks and Mitigations
## Open Questions

English, concise but actionable. Cite source file:line or PDF page where relevant.
