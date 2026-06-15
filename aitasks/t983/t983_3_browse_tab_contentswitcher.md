---
priority: medium
risk_code_health: high
risk_goal_achievement: low
effort: high
depends: [t983_2]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 11:39
updated_at: 2026-06-15 18:33
---

## Context
Child of t983. Collapses the two DAG *views* (Dashboard list + Graph) into a
single **Browse** tab with a graph/list toggle, ONE shared `NodeDetailPanel`
(t983_1), and `space`-marking wired to `NodeSelection` (t983_2). This is the
highest-risk structural seam; it is de-risked by landing on the already-tested
panel + selection model, plus a pure view-state helper.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — replace `tab_dashboard` (D)
  and `tab_dag` (G) (compose :3540-3559) with one `tab_browse`; host a
  `ContentSwitcher` over list `#node_list_pane` ⇄ graph `DAGDisplay#dag_content`
  + one persistent `NodeDetailPanel`. Add `v` (`action_browse_toggle_view`) and
  `space` (mark) bindings. Unify the two focus→detail triggers.
- `tests/test_brainstorm_browse_view.py` — NEW.
- `tests/test_brainstorm_node_export.py` — update `tab_dashboard` assertions.

## Reference Files for Patterns
- Plan-agent recommendation: use Textual `ContentSwitcher` (NOT nested
  `TabbedContent` — that re-introduces the "tab switch to change shape" smell).
- Divergent triggers to unify: Dashboard `on_descendant_focus` (:5923) →
  `#dash_node_info`; Graph `DAGDisplay.NodeSelected` (:5942) → opens
  `NodeDetailModal`. Make both feed the shared panel via one
  "selection-changed → render panel" handler.
- Per-session persistence pattern to reuse for the toggle default: the
  deferred-module marker (`_write_module_deferred`).

## Implementation Plan
1. Extract a **pure** view-state helper: given session state, return current view
   (graph default) and a `toggle` that flips + persists. Unit-test it headless.
2. Build `tab_browse` with `ContentSwitcher`; mount the shared `NodeDetailPanel`
   as a persistent sibling so it survives `v` toggles.
3. `v` → flip `ContentSwitcher.current` + persist; `space` → `NodeSelection`
   mark/toggle on the cursor node, reflect marks in both views.
4. Repoint tab-switch action(s); update `check_action`/`_TAB_SCOPED_ACTIONS` for
   the new `tab_browse` id (full deconflict is t983_9, but keep Browse working).
5. Decide where dashboard-only labels (`#session_status_info`,
   `#module_status_info`, :3544-3547) live (Browse column for now; header strip
   is t983_9).

## Verification
- Pure unit: view-state helper in `tests/test_brainstorm_browse_view.py`
  (default=graph, toggle flips + persists across reload).
- Pilot: `run_test` — `v` switches the `ContentSwitcher`, the panel persists
  across toggles, `space` marks reflect in `NodeSelection`.
- Update + green: `test_brainstorm_node_export.py`; full `test_brainstorm*.py`.
- Manual: `ait brainstorm <session>` → `v` toggles, detail shared, `space` marks.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T15:33:05Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-15T15:33:06Z status=pass attempt=1 type=machine
