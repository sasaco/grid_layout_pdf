No files were changed and no agents or recursive consultations were invoked.

Recommended architecture: immutable semantic components → deterministic measurement → page layout/pagination → backend-neutral scene commands → a narrow ReportLab Canvas adapter. Internally, all coordinates use a top-left origin; only the renderer converts to PDF’s bottom-left coordinates.

## Implementation Steps (ordered by dependency)

1. **Bootstrap the package and protect reference evidence**

   Create:

   - `pyproject.toml`, `uv.lock`
   - `src/gridlayoutpdf/__init__.py`
   - `src/gridlayoutpdf/errors.py`
   - `tests/fixtures/reference_manifest.json`
   - `tests/unit/test_reference_integrity.py`

   Use ReportLab as the provisional runtime backend, pytest for tests, and PyMuPDF only as a development/integration-test dependency. Record SHA-256 values for A4, A3, and every `tests/output/*.pdf`; generated PDFs must go under `build/test-output/`, never beside the references. The repository currently has no product package, manifest, or executable product tests, so every product path above is new ([sample-report-findings.md:16](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:16)). Reference hashes are evidence-preservation checks, not generated-output golden hashes ([sample-report-findings.md:104](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:104)).

2. **Prove geometry, font metrics, and the PDF adapter before designing the public API**

   Create:

   - `src/gridlayoutpdf/geometry.py`
   - `src/gridlayoutpdf/profiles.py`
   - `src/gridlayoutpdf/fonts.py`
   - `src/gridlayoutpdf/scene.py`
   - `src/gridlayoutpdf/rendering/base.py`
   - `src/gridlayoutpdf/rendering/reportlab.py`
   - `tests/unit/test_geometry.py`
   - `tests/integration/test_reportlab_typography.py`

   Implement immutable `Point`, `Box`, `GridSpec`, `PageProfile`, `FontFace`, `FontMetrics`, and scene commands such as `TextRun`, `Line`, `Rect`, `Path`, and `Image`. Add the measured profiles:

   - A4 portrait: 595×842 pt, 30×47, origin `(50.88, 54.598)`, pitch `(16.08, 15.48)` ([grid-reference-findings.md:22](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/grid-reference-findings.md:22)).
   - A3 landscape: 1191×842 pt, 67×47 with the same origin and pitch ([grid-reference-findings.md:95](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/grid-reference-findings.md:95)).

   The backend must return advance width, ascent, descent, baseline, and glyph bounding boxes. Render a proof sheet containing Japanese, Latin, digits, Greek, half/full-width equals, and intentional script sizes. If glyph coverage, baseline recovery, or output/extracted coordinates cannot be made deterministic, stop here and reassess the backend or font—not the semantic model.

3. **Implement text measurement and deterministic mixed-language wrapping**

   Create:

   - `src/gridlayoutpdf/styles.py`
   - `src/gridlayoutpdf/text.py`
   - `src/gridlayoutpdf/linebreak.py`
   - `src/gridlayoutpdf/diagnostics.py`
   - `tests/unit/test_text.py`
   - `tests/integration/test_text_pdf_geometry.py`

   Keep font size, natural glyph metrics, optional tracking, block-grid position, and line baseline as separate concepts. Default to natural advance; allow explicit tracking or target advance without horizontally scaling glyphs. Add documented CJK break opportunities and Japanese line-start/line-end punctuation rules, while Latin breaks at whitespace or explicit hints.

   The reference text uses 10.08 pt full-width and 5.04 pt half-width advances, neither of which equals the grid pitch ([sample-report-findings.md:43](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:43), [sample-report-findings.md:47](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:47)). Therefore, grid cells remain placement units rather than character cells, as required by [CONTEXT.md:19](C:/Users/sasai/Documents/GridLayoutPdf/CONTEXT.md:19).

4. **Build the structured mathematical box model**

   Create:

   - `src/gridlayoutpdf/math/nodes.py`
   - `src/gridlayoutpdf/math/measure.py`
   - `src/gridlayoutpdf/math/layout.py`
   - `tests/unit/test_math_layout.py`

   Provide immutable semantic nodes such as `Text`, `Identifier`, `Number`, `Operator`, `Relation`, `Sequence`, `Group`, `Fraction`, `Root`, `Script`, and `BreakHint`. Every measured `MathBox` must expose width, ascent, descent, mathematical axis, child positions, and named anchors.

   Fractions, roots, and scripts use local sub-row geometry; only the containing block’s start and occupied extent snap to document rows. Script font sizes are intentional styles, never an overflow-shrinking mechanism. The risk proof should reproduce the structural features of `tests/output/13_片持ち梁照査.pdf` p.54: stacked fractions, roots, brackets, Greek characters, and scripts ([sample-report-findings.md:77](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:77)).

5. **Add equation alignment groups and semantic wrapping**

   Create:

   - `src/gridlayoutpdf/equations.py`
   - `src/gridlayoutpdf/math/wrap.py`
   - `tests/unit/test_equation_alignment.py`
   - `tests/unit/test_equation_wrap.py`

   Implement locally scoped `AlignmentGroup`s with named slots such as label, definition relation, substitution, result relation, result, and unit. Resolve shared columns from the widest measured member, while permitting explicit grid anchors. Align relation glyphs by the center of their advance box so half/full-width equals do not align by unrelated left edges.

   Support:

   - Multiple relation columns.
   - Right-aligned results and left-aligned units.
   - Long labels, results, and units with explicit wrap/atomic policies.
   - Automatic breaks at relations, low-precedence operators, and manual hints.
   - Atomic fractions and roots.
   - Continuation-line alignment.
   - An `UnbreakableOverflowError` containing the semantic path, available width, measured width, font/style, and candidate breakpoints.

   The primary cases are `08_線路.pdf` p.2, where two equation columns, result-right, and unit-left alignment coexist ([sample-report-findings.md:57](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:57)), and `07_荷重計算.pdf` p.1, where a substitution wraps without losing its result column ([sample-report-findings.md:62](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:62)).

6. **Create the first usable vertical slice: blocks, flow, and pagination**

   Create:

   - `src/gridlayoutpdf/blocks.py`
   - `src/gridlayoutpdf/pagination.py`
   - `src/gridlayoutpdf/document.py`
   - `tests/unit/test_flow.py`
   - `tests/unit/test_pagination.py`
   - `tests/integration/test_basic_document.py`

   Define a strict block contract: `measure()`, `place()`, and—only where legal—`split()`. Start with paragraph, equation, spacer, and explicit page-break blocks. Measurement must happen before placement; wrapped continuation lines must be included before positioning the following block.

   Pagination must guarantee progress: every iteration either consumes content, creates a page once, or raises a diagnostic error. Implement `keep_with_next`, `keep_together`, exact-bottom fit, forced break, orphan-heading prevention, and impossible-block detection. A block taller than an empty page must fail instead of being moved to new pages indefinitely, matching the documented recommendation ([sample-report-findings.md:92](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:92)).

7. **Add merged-cell tables and a defined cross-page rowspan policy**

   Create:

   - `src/gridlayoutpdf/tables.py`
   - `tests/unit/test_tables.py`
   - `tests/integration/test_table_pagination.py`

   Support fixed, grid-column, and measured column widths; horizontal/vertical merges; multirow headers; cell padding; alignment; and paragraph/equation cell content. Split tables only between legal row groups and repeat headers.

   First-release policy: a rowspan group is indivisible across a page boundary. Move the complete group to the next page; if it cannot fit on an empty page, raise a measured `UnbreakableTableRegionError`. Do not silently duplicate or truncate a spanning cell. Validate against the structure of `12_フーチング.pdf` p.1 ([sample-report-findings.md:81](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/sample-report-findings.md:81)).

8. **Support mixed page profiles, templates, and total page counts**

   Create:

   - `src/gridlayoutpdf/templates.py`
   - `tests/unit/test_profiles.py`
   - `tests/integration/test_mixed_pages.py`
   - `tests/integration/test_page_templates.py`

   Make page-template changes explicit in the document tree; never switch to a larger sheet merely to hide overflow. Ship the measured A4 portrait and A3 landscape profiles. Derived A4 landscape or A3 portrait profiles should retain the physical pitch and top-left origin, use only complete rows/columns, and be marked `derived`, not `reference_exact`.

   Complete layout for every page before rendering so `{page_number}` and `{page_count}` can be resolved without mutating an already-rendered PDF. Header/footer reservations are part of usable-grid calculation. Verify A4 → A3 landscape → A4, repeated template selection, page-number formats, unchanged font sizes, and unchanged pitch. The A3 reference is wider rather than scaled A4 ([grid-reference-findings.md:109](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/grid-reference-findings.md:109)).

9. **Add figures and collision-safe explicit placement**

   Create:

   - `src/gridlayoutpdf/figures.py`
   - `src/gridlayoutpdf/placement.py`
   - `tests/unit/test_placement.py`
   - `tests/integration/test_figures.py`

   Provide aspect-preserving raster-image placement and backend-neutral vector figure commands. Explicitly positioned blocks must reserve page rectangles and participate in collision detection; overlap is an error unless a future API adds an explicit overlay mode. Flow placement must account for reservations before choosing the next row.

   External PDF page import remains out of scope: mixed-size reference pages justify page profiles, not PDF composition ([DESIGN.md:13](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/DESIGN.md:13)).

10. **Stabilize the narrow public API and diagnostic trace**

   Create:

   - `src/gridlayoutpdf/api.py`
   - `examples/basic_report.py`
   - `tests/unit/test_public_api.py`
   - `tests/integration/test_layout_trace.py`

   Export only stable semantic concepts: `Document`, page/template selection, styles, paragraphs, equations, tables, figures, and page breaks. Keep backend and layout internals private. Engineering calculations enter as already-computed values and labels; they never become a responsibility of this library.

   Emit an optional layout trace containing page/profile, block path, grid row/column, occupied rows, baseline, glyph boxes, math anchors, splits, and scene bounds. This is essential because image comparison alone cannot prove baselines and anchors ([grid-reference-findings.md:72](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/research/grid-reference-findings.md:72)).

11. **Run the acceptance suite and freeze release behavior**

   Add the representative fixtures and acceptance tooling:

   - `tests/fixtures/layout_cases/`
   - `tests/integration/test_pdf_geometry.py`
   - `tests/visual/`
   - `tools/render_visual_cases.py`

   Cover:

   - `08_線路.pdf` p.2: equation/result/unit columns.
   - `13_片持ち梁照査.pdf` p.54: complex mathematical boxes.
   - `12_フーチング.pdf` p.1: merged and multirow table.
   - `07_荷重計算.pdf` p.1: heading, table, figure, and wrapped equations.
   - A4 → A3 landscape → A4 profile changes.

   Acceptance means comparable expression and readability on the new grid—not original coordinates, page breaks, bytes, or pixels ([DESIGN.md:26](C:/Users/sasai/Documents/GridLayoutPdf/.agents/docs/DESIGN.md:26)).

## Verification per Step

| Step | Required verification |
|---|---|
| 1 | `uv run pytest tests/unit/test_reference_integrity.py -q`; lockfile resolves from a clean environment; all source hashes match. |
| 2 | `uv run pytest tests/unit/test_geometry.py tests/integration/test_reportlab_typography.py -q`; independently inspect MediaBox, text origins, and font sizes with PyMuPDF. |
| 3 | `uv run pytest tests/unit/test_text.py tests/integration/test_text_pdf_geometry.py -q`; check CJK punctuation, mixed scripts, baseline positions, natural/tracked advances, and no glyph scaling. |
| 4 | `uv run pytest tests/unit/test_math_layout.py -q`; compare box dimensions and child coordinates against hand-calculated fixtures. |
| 5 | `uv run pytest tests/unit/test_equation_alignment.py tests/unit/test_equation_wrap.py -q`; assert anchor equality, non-overlap, atomicity, and exact diagnostic fields. |
| 6 | `uv run pytest tests/unit/test_flow.py tests/unit/test_pagination.py tests/integration/test_basic_document.py -q`; include a watchdog/property test proving pagination makes progress. |
| 7 | `uv run pytest tests/unit/test_tables.py tests/integration/test_table_pagination.py -q`; verify repeated headers, legal split rows, preserved spans, and impossible-span failure. |
| 8 | `uv run pytest tests/unit/test_profiles.py tests/integration/test_mixed_pages.py tests/integration/test_page_templates.py -q`; independently extract all MediaBoxes and page labels. |
| 9 | `uv run pytest tests/unit/test_placement.py tests/integration/test_figures.py -q`; assert aspect ratio, reservation behavior, and collision errors. |
| 10 | `uv run pytest tests/unit/test_public_api.py tests/integration/test_layout_trace.py -q`; generate `examples/basic_report.py` using only documented imports. |
| 11 | Run `uv run pytest -q`, then `uv run python tools/render_visual_cases.py --out build/visual-review`; inspect rendered pages and layout traces manually. Finally run `& .agents/check.ps1`, noting that this repository gate does not replace product tests ([project.md:20](C:/Users/sasai/Documents/GridLayoutPdf/.agents/rules/project.md:20)). |

## Risks and Mitigations

- **Japanese font licensing or host-font substitution:** require explicit font registration, use one redistributable fixed test font, embed/subset where permitted, and fail on missing glyphs rather than silently substituting.
- **ReportLab measurement differs from emitted PDF geometry:** keep a narrow backend protocol and compare emitted coordinates independently with PyMuPDF before committing to the adapter.
- **CJK wrapping becomes an incomplete homemade Unicode engine:** document the supported first-release rules and isolate them in `linebreak.py`; expand through fixtures rather than hidden renderer behavior.
- **Math alignment becomes circular when group widths affect wrapping:** measure semantic segments first, solve group columns second, then wrap against the resolved regions; reject unsatisfiable groups.
- **Pagination loops on unsplittable content:** enforce a monotonic content cursor and distinguish “retry on fresh page once” from “impossible on an empty page.”
- **Rowspans cross page boundaries ambiguously:** keep the entire rowspan group together in the first release and report impossible groups explicitly.
- **Mixed orientations accidentally scale content:** page profiles change usable geometry only; font sizes, pitch, and figure scaling policies remain independent.
- **Golden-image tests become environment-sensitive:** use numeric geometry checks as the mechanical gate and visual images as controlled-environment approval evidence, never PDF byte equality.
- **Public API hardens too early:** defer top-level exports until typography, math, wrapping, pagination, and tables have passed their risk proofs.
- **Reference PDFs are accidentally modified:** validate their hashes before and after the complete suite and write all generated output outside reference directories.

## Open Questions

1. **Release-blocking font policy:** which Japanese font may be distributed with the library? If none, the public contract must require callers to register a font family, while tests use a separately licensed fixture font.
2. **Visual acceptance:** the generated typography proof must establish the default body font, baseline offset, tracking policy, and visual center for relation operators. These cannot be derived from the grid-only PDFs.
3. **Cross-page rowspans:** the recommended first-release behavior is “move the complete span group or fail.” Supporting a visually continuous rowspan split across pages would be a separate, materially larger feature.
4. **Non-blocking defaults:** proceed with Python 3.12+, ReportLab Canvas, PyMuPDF as development-only tooling, natural text advances by default, and origin-locked derived profiles unless a known consumer requires different compatibility or margin rules.
