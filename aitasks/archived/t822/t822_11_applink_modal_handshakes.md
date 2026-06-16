---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t822_7]
issue_type: feature
status: Done
labels: [ait_bridge]
risk_mitigation_tasks: [1011]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 10:42
updated_at: 2026-06-16 16:57
completed_at: 2026-06-16 16:57
---

Implement the applink modal-dialog handshake plumbing: the pull-model confirm/prompt/choose round-trips that replace the desktop Textual modals for mobile-issued verbs.

## Context

Sixth §"Deferred follow-up tasks" bullet of `aidocs/applink/monitor_port_design.md`. t822_7 ships the listener with stubbed confirmations; this task completes the §Modal-dialog handshakes table. Pull model (already decided): the client re-sends the gated verb with `confirmed:true` / a chosen ID after a `confirm_required` response — the server never blocks on a dialog reply and destructive actions stay client-initiated and idempotent.

## Handshakes to implement (design doc §Modal-dialog handshakes)

- **kill confirm** (`kill_pane`, `kill_window`): `confirmed:false` → `res {confirm_required:true, target:{pane_id, window_name, task?}}` → re-send with `confirmed:true` executes via `kill_agent_pane_smart` semantics.
- **restart confirm** (`restart_task`): `res` detail includes `{task_id, title, status, idle_seconds}`; server rejects non-idle panes with `err BAD_PAYLOAD detail:{reason:"not_idle"}`. NOTE: actual execution (kill + relaunch pick agent) may remain deferred per the design doc — implement the handshake + idle gate; if launch orchestration is still unavailable, return a `deferred` error after confirmation and document it.
- **sibling pick** (`pick_next_sibling`): no `sibling_id` → `res {suggested, current, parent_id, ready_siblings:[...]}` (via `TaskInfoCache.find_next_sibling`/`find_ready_siblings`); re-send with chosen `sibling_id` executes (same deferral caveat as restart).
- **rename_session**: `{session_id}` → `res {current}`; with `name` executes. Desktop-only in v1 per the design doc — implement only if trivial, else record as out-of-scope.

Correlation is by envelope `id`; gating applies to the underlying verb tier.

## Reference Files

- `aidocs/applink/monitor_port_design.md` — §Modal-dialog handshakes, verb-table notes on deferred workflow verbs
- `aidocs/applink/protocol.md` — envelope, error frame schema
- `monitor_core` `TaskInfoCache` sibling helpers

## Implementation Plan

1. Add a confirm-token-less two-phase dispatch helper in the listener (first call returns details, `confirmed:true` executes) shared by kill/restart.
2. Implement the sibling-pick suggest/choose round-trip from TaskInfoCache.
3. Tests with a scripted WS client covering: confirm-then-execute, decline (never re-send), non-idle restart rejection, permission denial under `monitor_control`.

## Verification Steps

- Scripted client kills a scratch pane only after the second (confirmed) request; the first request alone never kills.
- `restart_task` on a busy pane returns `not_idle`.
- `pick_next_sibling` returns a coherent suggestion + ready list for a task family with pending children.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T13:56:01Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T13:56:03Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-16T13:56:05Z status=pass attempt=1 type=human
