---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t983_6, t983_8]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-16 16:33
updated_at: 2026-06-17 12:38
---

## Context
Split out of **t983_6** (see its plan/AC). t983_6 delivered the *seeding* half
of the wizard re-host (seed-aware `node_select` predicate + contextual seeding of
explore/module_decompose and pre-checking of compare/synthesize `FuzzyCheckList`),
but kept the wizard physically hosted inside the `tab_actions` `TabPane`. This
task does the **physical re-host**: move the wizard off `#actions_content`'s
`TabPane` into a dedicated host so the Actions tab can be removed, coordinated
with **t983_8** (Session tab split) and **t983_9** (Running rename + footer/
keybinding deconflict) which restructure the same tab area.

This was deferred because verify-mode analysis (t983_6) showed the re-host is far
larger and riskier than the original t983_6 plan assumed — see findings below.

## Verify-mode findings (the reason this is its own task)
- **`App.query_one` does NOT traverse a pushed screen.** Empirically confirmed
  on textual 8.2.7: `app.query_one("#actions_content")` searches only the
  *default* screen and raises `NoMatches` when the widget lives in a pushed
  `ModalScreen`; only `app.screen.query_one(...)` (top of stack) finds it. So the
  premise "keep the id and the query sites work unchanged" is **false**.
- **~28 wizard-internal query sites** must be retargeted to the host screen
  (`grep -nE 'self\.query(_one)?\(.*(actions_content|OperationRow|btn_actions|cmp_|syn_|chk_section|fcl_|merge_rules|confirm_)'`).
- **Key-nav must relocate.** A `ModalScreen` consumes key events, so the wizard
  navigation block currently in `BrainstormApp.on_key` (the
  `tabbed.active == "tab_actions" and self._wizard_step > 0` block) never fires
  once the wizard is a modal — move it into the host screen's own `on_key`
  (delegating to the App's `_render_wizard_step`/`_actions_advance_*`/`_navigate_rows`/
  `_cycle_*` helpers via `self.app`).
- **Background-thread refreshes need guarding.** `call_from_thread(self._actions_show_step1)`
  fires after an op completes (3 sites, ~lines 8076/8082/8121). Today the Actions
  tab always exists; after re-host the host screen is transient, so these must
  no-op (or push/refresh-only-if-open) when the wizard host isn't mounted.
- **15 `tab_actions` guard sites** to sweep onto an `isinstance(self.screen, <Host>)`
  (or equivalent) check.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — introduce the host (a
  dedicated `Screen`/`ModalScreen` owning `VerticalScroll(id="actions_content")`),
  retarget the ~28 wizard-internal queries, move the key-nav block, guard the bg
  refreshes, sweep the `tab_actions` guards, replace `_enter_actions_tab`'s
  tab-switch with a `push_screen` of the host, and remove the `(A)ctions`
  `TabPane` (coordinate ordering with t983_8/t983_9).
- `tests/test_brainstorm_wizard_filter.py` / `_sections.py` / `_subgraph.py` —
  update for the new host (these construct/drive the wizard).

## Reference Files for Patterns
- `NodeDetailModal` / `NodeHub` (`brainstorm_app.py`) — existing `ModalScreen`
  subclasses with hook-driven compose; mirror their structure.
- t983_5 plan `aiplans/archived/p983/p983_5_node_hub_overlay.md` — the
  hook/typed-result pattern for screens.
- The seeding contract t983_6 established: `_wizard_ctx()` exposes
  `pre_seeded_node`; the `node_select` step is seed-aware (kept, not deleted).

## Architecture decision to make (carried over from t983_6 verify mode)
Three approaches were identified — pick one in planning, document trade-offs:
1. **ModalScreen + retarget queries** (matches task-as-written; high churn).
2. **In-screen overlay** (move `#actions_content` out of `TabbedContent` but keep
   it in the default screen → all `self.query_one` keep working; must hand-roll
   focus-trap/escape/key routing).
3. **Move wizard methods onto the host Screen class** (cleanest end-state; breaks
   many tests that call `app._actions_*`).

## Verification
- All `tests/test_brainstorm_wizard_*.py` green after host migration.
- `bash tests/run_all_python_tests.sh` (`tests/test_brainstorm*.py`) green.
- Manual: launch every op from the Operations dialog (`A`) and Node Hub (Enter)
  → wizard host opens, runs to completion, closes cleanly; Esc/back nav works;
  an op completing in the background does not crash when the host is closed.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_11`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-17T09:38:25Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-17T09:38:26Z status=pass attempt=1 type=machine
