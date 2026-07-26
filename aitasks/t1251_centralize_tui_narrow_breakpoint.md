---
priority: low
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-07-26 11:47
updated_at: 2026-07-26 11:47
---

## Origin

Risk-mitigation ("after") follow-up for t1247, created at Step 8d after
implementation landed.

## Risk addressed

**Goal-achievement — narrow-terminal breakpoint drift.** From t1247's plan
`## Risk` section, verbatim:

> The reflow threshold (`FILTER_SEARCH_MIN_WIDTH = 30`) is a UX judgement, not a
> correctness invariant, and adds a fourth uncentralized narrow-terminal
> breakpoint to the repo · severity: low · → mitigation:
> centralize_tui_narrow_breakpoint

## Goal

Hoist the repo's scattered narrow-terminal breakpoints into one shared constant
(or a small helper) in `.aitask-scripts/lib/`, so "what counts as a narrow
terminal" is defined once rather than rediscovered per TUI.

### Current sites (verified during t1247 planning)

- `.aitask-scripts/codebrowser/codebrowser_app.py` — `on_resize` uses inline
  magic breakpoints `120` / `80` to pick a sidebar width of `35` / `28` / `22`.
  Named constants `DETAIL_DEFAULT_WIDTH = 30` and `CODE_MIN_WIDTH = 80` exist as
  App class attrs, but the breakpoints themselves are literals.
- `.aitask-scripts/codebrowser/code_viewer.py` — `_annotation_col_width()`
  branches on `app_width < 80`.
- `.aitask-scripts/board/aitask_board.py` — `KanbanApp.FILTER_SEARCH_MIN_WIDTH`
  (added by t1247); it is a *floor* rather than a breakpoint, but it feeds the
  filter-row reflow threshold.
- `.aitask-scripts/monitor/monitor_shared.py` — dialogs take a `narrow: bool`
  constructor kwarg and apply a `.narrow` class; callers in
  `minimonitor_app.py` pass it statically. Worth checking whether this should
  consult the same shared notion.

`< 80` is the de-facto repo convention for "narrow" (it appears in two
independent places) but is written nowhere as a shared definition.

### Constraints

- **Do not collapse semantically different numbers into one.** A layout
  *breakpoint* ("is this terminal narrow?") and a component *minimum width*
  ("this widget needs N cells") are different concepts — centralize each on its
  own terms rather than forcing every site onto a single value. If a site's
  number turns out to be genuinely component-specific, leave it and document
  why.
- Preserve current behavior exactly: this is a refactor, not a retune. Any
  intentional threshold change should be a separate task.
- t1247 deliberately did **not** duplicate `FILTER_SEARCH_MIN_WIDTH` as a CSS
  `min-width`; keep that single-source-of-truth property intact.

## Verification

- Existing suites must stay green, in particular
  `tests/test_board_filter_row_layout.py` (filter-row geometry and the derived
  reflow threshold) and the codebrowser tests.
- Add a test asserting each migrated call site reads the shared constant rather
  than a literal, so a future edit cannot silently reintroduce a local number.
- Run isolated and in the full suite — `t1179` records that
  `tests/run_all_python_tests.sh` is order-dependent.
- Manual: resize `ait board` and `ait codebrowser` across the breakpoints and
  confirm behavior is identical to before the refactor.
