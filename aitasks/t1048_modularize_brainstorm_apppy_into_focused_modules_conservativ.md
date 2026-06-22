---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [1047]
issue_type: refactor
status: Implementing
labels: [brainstorm, tech-debt]
risk_mitigation_tasks: [1052]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-22 09:52
updated_at: 2026-06-22 12:19
---

`.aitask-scripts/brainstorm/brainstorm_app.py` has grown to ~9,224 lines
(~362KB) and is too large to navigate or edit safely. Split it into focused
modules under `.aitask-scripts/brainstorm/`. This is a **conservative
extraction**: pull out the clean, low-risk modules and leave the `BrainstormApp`
core and `ActionsWizardScreen` largely intact (a deeper decomposition — splitting
the app into Browse/Session/Running tab modules and extracting the wizard with
dependency injection — is explicitly out of scope here and can be a follow-up).

## Depends on t1047
The three wizard/preview UX bug fixes (t1047) should land first; this refactor
then moves the already-fixed code into modules. Sequencing this after t1047
avoids reworking the fixes mid-split.

## Current size profile
- `BrainstormApp` (App): ~4,350 lines (47%) — left mostly in place this pass.
- `ActionsWizardScreen` (ModalScreen): ~1,568 lines — left in place this pass.
- One monolithic CSS block: ~1,200 lines.
- `_OPERATION_HELP` constant: ~230 lines.
- Numerous modals, row/list widgets, and pure helper functions.

## Proposed conservative extraction
Extract the low-risk, low-coupling pieces; keep `brainstorm_app.py` as the entry
point importing from the new modules:
- `constants.py` — STATUS_COLORS, AGENT_STATUS_COLORS, RUNNER_STATE_DISPLAY,
  op/label dicts, `_OPERATION_HELP`, `_WIZARD_STEPS` etc. (pure data).
- `utils.py` — pure functions: `derive_runner_state`, `format_status_strip`,
  `_sections_intersection`, `op_states_for_selection`, wizard step helpers
  (`active_step_ids`/`step_position`/`next_step_id`/`prev_step_id`),
  `compare_matrix_rows`, label/section parsers, etc.
- `styles.py` (or per-widget DEFAULT_CSS) — the large CSS block, organized.
- `widgets/` — `ProposalPreviewPane` + `_PreviewMinimap` + `_NumberedProposal`;
  Browse widgets (`NodeRow`, `NodeDetailPanel`, `NodeSelection`);
  list widgets (`FuzzyCheckList`, `DimensionRow`); status/row widgets
  (`GroupRow`, `AgentStatusRow`, `ProcessRow`, `StatusLogRow`);
  op widgets (`OperationRow`, `CycleField`).
- `modals/` — the self-contained modals (init/import, node detail/hub/export,
  compare matrix, operation/log/help, action-select/module-preview).

Final module boundaries to be settled in the implementation plan; the above is
the candidate split from exploration.

## Constraints / conventions
- **Preserve the entry point.** Only `aitask_brainstorm_tui.sh` runs the file as
  a script (`exec "$PYTHON" .../brainstorm/brainstorm_app.py "$@"`); no other
  module imports it. Keep `brainstorm_app.py` runnable as-is (or update the
  launcher if renamed).
- Follow `aidocs/framework/tui_conventions.md`: modals reused/pushed need their
  own DEFAULT_CSS if separated from a central CSS block; preserve the brainstorm
  shortcut scope registration (`_shortcuts_scope = "brainstorm"`,
  `lib/shortcut_scopes.py` / `KNOWN_BINDING_SOURCES`) when moving
  `ActionsWizardScreen`/`BrainstormApp` bindings.
- Watch `self.app`-reaching coupling: many modals/widgets read
  `self.app.session_path`, `self.app._selection`, `self.app.notify()`. This pass
  may keep that coupling (move the class, keep `self.app` access) rather than
  introduce dependency injection — note any place where a clean move is blocked.
- Mechanical, behaviour-preserving: no UX changes. Run the brainstorm TUI test
  suite (and any goldens) before/after.

## Acceptance criteria
- `brainstorm_app.py` is materially smaller; clean modules extracted as above.
- `ait brainstorm` launches and behaves identically (Browse/Session/Running
  tabs, node-op wizard, proposal preview, minimap, polling) — manual smoke +
  existing tests pass.
- No new external import surface required; launcher still works.
- TUI conventions respected (DEFAULT_CSS, shortcut scope registration).
- Out of scope (note as potential follow-up): splitting `BrainstormApp` into
  per-tab modules and extracting `ActionsWizardScreen` with injected
  dependencies.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-22T08:57:13Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-22T08:57:15Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-22T09:18:34Z status=pass attempt=1 type=human
