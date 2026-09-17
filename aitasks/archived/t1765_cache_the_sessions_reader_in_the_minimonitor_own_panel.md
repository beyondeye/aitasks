---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: performance
status: Done
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
updated_at: 2026-09-17 12:48
completed_at: 2026-09-17 12:48
---

`MiniMonitorApp._own_frozen_at` constructs a fresh `agent_sessions.SessionsView()`
on every frozen own-panel refresh, so the reader's unchanged-store cache never
gets a chance to work: a probe showed two refreshes against an identical store
stamp producing two full `load_safe` calls — a full JSON read and parse each
time.

The panel refreshes on the ordinary monitor tick, and the store is unchanged
between almost all of them, so this is a repeated read of a file whose stamp
already says nothing happened. `SessionsView` exists precisely to make that case
cost a stat.

Fix: hold one `SessionsView` on the app (beside `_marks_view`, which already
follows this pattern) and let `_own_frozen_at` invalidate/read it, so unchanged
frozen state costs a stamp check rather than a re-parse.

Low severity: it costs one small read per tick while the followed agent is
frozen, and nothing is incorrect. Found by review of t1705_7; disposition
there: follow-up, not blocking.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T08:32:47Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-17T09:06:23Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-17T09:48:10Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:8bb7383868e98f2f

> **✅ gate:risk_evaluated** run=2026-09-17T09:48:10Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1765/risk_evaluated_2026-09-17T09:48:10Z-risk_evaluated-a1.log`
