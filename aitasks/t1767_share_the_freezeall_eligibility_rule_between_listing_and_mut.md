---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [monitor, frozen]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: review_finding
implemented_with: claudecode/opus5
created_at: 2026-09-09 15:31
updated_at: 2026-09-17 13:06
---

`agent_freeze.freeze_all_eligible()` documents itself as THE eligibility rule,
read by both the `--dry-run` listing and the mutation — "so a UI that shows a
confirmation count cannot drift from what confirming actually does".

`freeze_all()` does not call it. It duplicates the discovery loop and the two
filters (`category == AGENT`, `not pane.frozen_record`) inline. A spy confirmed
zero calls to the helper during a fake-backed batch.

The rules match today, so this is maintainability debt rather than an observed
wrong target — but the confirmation count `Z` shows in both monitor TUIs is
derived from the helper while the freeze it authorizes is driven by the copy,
so any future edit to one silently invalidates the other. That is precisely the
drift the helper's docstring says it exists to prevent.

Constraint on the fix: `freeze_all()` reports a session that vanished mid-scan
(the caller asked for a mutation and is owed the news), while
`freeze_all_eligible()` skips it (it is a listing). Share the SELECTION without
flattening that difference — e.g. have the mutation iterate the shared
enumeration while keeping its own per-session error reporting.

Found by review of t1705_7. Disposition there: follow-up, not blocking.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T10:06:05Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-17T11:48:05Z status=pass attempt=1 type=human
