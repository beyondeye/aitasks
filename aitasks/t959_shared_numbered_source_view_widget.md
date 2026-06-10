---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [ait_brainstorm]
created_at: 2026-06-10 10:04
updated_at: 2026-06-10 10:04
---

Extract a shared "reflow-stable, syntax-highlighted, line-numbered source view" base widget and adopt it in both the codebrowser `CodeViewer` and the brainstorm Actions-tab numbered proposal view (`_NumberedProposal`, added in t954).

## Context

t954 added `_NumberedProposal` (in `.aitask-scripts/brainstorm/brainstorm_app.py`) — a Rich-`Table` gutter view (right-justified `no_wrap` line-number column + wrapping content column, one source line per row so numbers survive reflow) with markdown syntax highlighting via `Syntax(text, "markdown", theme="monokai").highlight(text).split("\n")`. This reimplements the same idiom already in `.aitask-scripts/codebrowser/code_viewer.py` (`CodeViewer.load_file` + `_rebuild_display`).

Verbatim-identical surface today is ~10-12 lines, but the coherent shared *base widget* is ~40-60 lines: highlight+per-line split+cache, width calc (`available - LINE_NUM_WIDTH - pad`), boxless table skeleton, the number→row loop, `Static.update`, and `on_resize`→rebuild. Decision (with user) is to extract the full base and adopt in both.

## Goal

Add a shared base widget (suggested `NumberedSourceView`) in `.aitask-scripts/lib/` that both TUIs sit on. `lib/` is already on `sys.path`, so both codebrowser (PyPy) and brainstorm (CPython) can import it.

## Required extension hooks (codebrowser needs these; the preview does not)

The base must expose clean override/parameter points so `CodeViewer` keeps its current behavior:
1. **Lexer selection** — fixed lexer (preview: `markdown`) vs `Syntax.guess_lexer(path, code)` (codebrowser).
2. **Per-row styling hook** — cursor line + multi-line selection row styles (codebrowser).
3. **Optional extra column** — the annotation gutter (codebrowser's 3rd column).
4. **Render-range hook** — viewport windowing for 2000+ line files (codebrowser), plus the "N lines above/below" indicator rows.
5. **Wrap-vs-truncate switch** — codebrowser toggles `no_wrap` + `MAX_LINE_WIDTH` truncation; the preview is always-wrap.

Keep the base minimal; these are the only divergence points found between the two.

## Key files
- NEW: `.aitask-scripts/lib/<numbered_source_view>.py` — the base widget.
- `.aitask-scripts/codebrowser/code_viewer.py` — refactor `CodeViewer` (618 lines) onto the base; keep annotations/viewport/selection/cursor/truncate behavior intact.
- `.aitask-scripts/brainstorm/brainstorm_app.py` — make `_NumberedProposal` a thin subclass/user of the base (must remain a `Static`/`VerticalScroll`-only widget — no `TextArea`/`CycleField`/`RadioSet` — to preserve the `_actions_collect_config` single-match collector contract).

## Reference points
- `code_viewer.py:153-194` (`load_file`: read/sanitize/highlight) and `:283-367` (`_rebuild_display`: width calc, columns, viewport indicators, row loop, resize).
- `brainstorm_app.py` `_NumberedProposal` (set_text caches `_lines`; `_rebuild` builds the 2-col table).

## Constraints / risks
- `CodeViewer` is load-bearing and routed through PyPy; its existing tests must stay green. Highest-blast-radius part of this task.
- Do NOT regress the t954 numbered-view behavior: numbers track source lines across reflow, markdown highlighting, toggle/focus-ring integration.

## Verification
- `python tests/test_brainstorm_proposal_preview.py` — all green (incl. one-row-per-source-line, reflow-survival, syntax-highlight tests).
- Run the codebrowser test suite (find via `ls tests/ | grep -i codebrowser`) — all green.
- Manual: `ait codebrowser` renders highlighted code with line numbers, annotations, viewport, selection, wrap toggle as before; `ait brainstorm` Actions tab Ctrl+Shift+L numbered view unchanged.

Follow Step 9 (Post-Implementation) of the task-workflow for archival.
