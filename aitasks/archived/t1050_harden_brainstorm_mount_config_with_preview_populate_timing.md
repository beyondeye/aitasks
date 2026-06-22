---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [brainstorm]
assigned_to: dario-e@beyond-eye.com
anchor: 1047
implemented_with: claudecode/opus4_8
created_at: 2026-06-22 11:21
updated_at: 2026-06-22 17:04
completed_at: 2026-06-22 17:04
---

Surfaced during t1047 testing.

`.aitask-scripts/brainstorm/brainstorm_app.py::ActionsWizardScreen._mount_config_with_preview`
mounts the proposal preview split and schedules `_fill` via
`self.call_after_refresh(_fill)`, where `_fill` calls `pane.populate(...)`. The
populate path does `ProposalPreviewPane._content()` →
`query_one("#preview_proposal_content")`. The screen's idle can fire `_fill`
**before** the dynamically-mounted `ProposalPreviewPane` finishes composing its
children on its own message pump, so `query_one` raises a transient `NoMatches`.

- **Impact:** Benign in production (the real app's extra layout refreshes win the
  race), but fatal under headless `run_test` — t1047's pilot tests had to
  neutralize it with a tolerant `populate` patch
  (`tests/test_brainstorm_wizard_nav_consolidation.py`, `setUp`).
- **Likely fix:** make populate timing robust — e.g. `await` the split mount
  before populate, populate from the pane's own `on_mount`, or have `_content()`
  defer until the content widget exists. Then remove the test's `populate` patch.

## Acceptance criteria
- `_mount_config_with_preview` no longer races: populate cannot run before the
  pane's content widget exists (no transient `NoMatches`).
- The `populate` monkeypatch in `tests/test_brainstorm_wizard_nav_consolidation.py`
  is removed and the tests still pass.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-22T14:00:03Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-22T14:00:04Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-22T14:03:06Z status=pass attempt=1 type=human
