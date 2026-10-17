# Project scope

- This is a Python library project for grid-aligned PDF calculation reports.
- The user's `.claude/docs/research/A4.pdf` is the grid reference; `tests/output/*.pdf` are appearance references. Preserve these files.
- The user approved implementation of .claude/docs/plans/grid-aligned-calculation-reports.md on 2026-10-16 and explicitly requested tdd and parallel-agent-dev. Implement the approved scope and its verification without asking for the same approval again.
- Distinguish user-confirmed requirements, measured PDF observations, and proposed implementation choices.
- Keep engineering calculations separate from report layout and rendering.
- Use `uv run --no-project python` for existing skill scripts while no project manifest exists. Copied `--project FrameWeb` examples do not describe this repository.
