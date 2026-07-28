---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: refactor
status: Done
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/opus5
created_at: 2026-07-26 11:47
updated_at: 2026-07-28 17:48
completed_at: 2026-07-28 17:48
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
  than a literal. **Scope decision at implementation time (user-confirmed):**
  this splits in two and is met by two different mechanisms.
  - *"reads the shared constant"* — met by test. `tests/test_tui_narrow_breakpoint.py`
    monkeypatches `tui_layout`'s module global and drives the real widget/app;
    a re-inlined literal ignores the patch and the assertion fails (proven by
    running both negative controls at implementation time).
  - *"a future edit cannot silently reintroduce a local number"* — met by
    documentation, **not** by a source-scanning test. An AST guard over the two
    migrated files was designed and then deliberately dropped: it would police
    only files already covered behaviourally, while the real drift risk is a
    *new* TUI written later, which such a scan would not see either. The
    `aidocs/framework/tui_conventions.md` section (reached via the existing
    `CLAUDE.md` pointer) is the mechanism instead.
- Run isolated and in the full suite — `t1179` records that
  `tests/run_all_python_tests.sh` is order-dependent.
- Manual: resize `ait board` and `ait codebrowser` across the breakpoints and
  confirm behavior is identical to before the refactor.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-28T12:31:05Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-28T14:39:00Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-28T14:48:14Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:efe1912354e6989b

> **✅ gate:risk_evaluated** run=2026-07-28T14:48:14Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1251/risk_evaluated_2026-07-28T14:48:14Z-risk_evaluated-a1.log`
