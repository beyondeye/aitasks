---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t983_1]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 11:38
updated_at: 2026-06-15 11:48
---

## Context
Child of t983 (brainstorm TUI IA redesign). The target IA replaces single-node
selection with `space`-marking (single OR multi), and the new Operations dialog
greys ops by selection **cardinality**. Today selection is single-only:
`self._current_focused_node_id` (`.aitask-scripts/brainstorm/brainstorm_app.py:3453`),
read at ~10 sites. This child lands the **pure, headless selection model first**
(testability-first: no Textual dependency, exhaustively unit-tested), ahead of its
UI consumer. It is purely additive — the old `_current_focused_node_id` keeps
working until t983_3 wires the model into the Browse UI.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` (or a small new module imported
  by it) — add a plain `NodeSelection` class with NO Textual/I/O dependency.
- `tests/test_brainstorm_node_selection.py` — NEW (fully headless).

## Reference Files for Patterns
- The wizard's pure, headless model is the template: `_WIZARD_STEPS` +
  `active_step_ids`/`next_step_id` (:1822-1887), unit-tested with zero Textual in
  `tests/test_brainstorm_wizard_steps.py`. Mirror that style exactly.

## Implementation Plan
1. `class NodeSelection`: `marked: set[str]`, `primary: str | None` (cursor),
   methods `mark`/`unmark`/`toggle(node_id)`, `clear()`, `set_primary(node_id)`,
   property `cardinality` (len of effective selection — primary alone counts as 1
   when nothing is marked). Decide and document the primary-vs-marked semantics
   (single-node ops act on primary/cursor; multi-node ops act on the marked set).
2. Keep it import-light and side-effect-free (no reads of session files).
3. Do NOT yet wire it into the UI (that is t983_3) — land it + its tests only.

## Verification
- Pure unit: `tests/test_brainstorm_node_selection.py` — exhaustive over
  mark/unmark/toggle/clear/set_primary and `cardinality` transitions (empty,
  primary-only, single-marked, multi-marked).
- Suite: `tests/test_brainstorm*.py` green (this child is additive).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T08:48:36Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-15T08:48:38Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-15T09:09:47Z status=pass attempt=1 type=human
