---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [minimonitor, monitor, frozen_agents]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2049
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 15:32
updated_at: 2026-10-20 10:39
completed_at: 2026-10-20 10:39
---

## Origin

Spawned from t2057 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:3197` — `_on_own_kill_confirmed` passes a pane to `kill_agent_pane_smart` without re-checking frozen state; an agent frozen while the `k` confirm dialog is open gets the unleased kill-then-drop that deletes its capture (guard with `_kill_target_state`)
- `.aitask-scripts/monitor/monitor_app.py:3674` — `_on_kill_confirmed`: same frozen-while-confirm-open race into `kill_agent_pane_smart`
- `.aitask-scripts/monitor/monitor_app.py:3881` — `_on_restart_confirmed`: same race (frozen guard only at action entry, kill runs in the dialog callback)
- `.aitask-scripts/applink/router.py:541` — remote kill reaches `kill_agent_pane_smart` with no frozen check at all

(Line numbers are as of commit 1ac0b0883; re-locate by function name.)

## Diagnostic context

`kill_agent_pane_smart` (`monitor_core.py`) kills a pane FIRST and then runs
`aitask_agent_sessions.sh drop` for a frozen record. The kill takes no lease, so
it can tear down a stand-in whose record a restore coordinator owns. The drop
also deletes the capture, which is the only copy of the agent's output, without
the warning `k` shows. The leased, preflighted path is `_drop_frozen`
(`aitask_frozen.sh drop`).

t2057 closed this for the pick flows (minimonitor `n`/`p`, full monitor `n`)
with a kill-time re-check, `MonitorSharedMixin._kill_target_state(pane_id)` in
`monitor_shared.py`. It reads the current snapshot and then the live
`@aitask_frozen` pane option through `TmuxMonitor.get_pane_option_sync`, and
returns `live|frozen|unverified`. Only `live` may reach the kill; anything else
fails closed.

The `k` and `r` confirm callbacks check frozen state only when the action
starts (`action_kill_*` routes a frozen snapshot to `_confirm_drop_frozen`). If
the agent is frozen by another monitor while the confirm dialog is open, the
callback still reaches the unleased frozen path. The applink router kill has no
frozen awareness at all.

## Suggested fix

At each call site, call `_kill_target_state(pane_id)` immediately before
`kill_agent_pane_smart`. Kill only on `"live"`. On `"frozen"`, say so and point
at `k` (the leased drop); on `"unverified"`, decline with a warning. Any toast
that names a window keeps `markup=False`, and new toast sites go in
`tests/test_monitor_markup_literal_sinks.py`'s `TOAST_SITES`.

For applink, decide whether a remote kill of a frozen pane should be refused or
routed to the leased drop.

Add regressions with a snapshot that flips to frozen between the action and the
confirm callback, plus a live control. See
`tests/test_minimonitor_pick_by_number.py::KillTimeFrozenRecheckTests`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T05:52:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-20T07:32:40Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-20T07:39:53Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:712e9d6706ae8dbd

> **✅ gate:risk_evaluated** run=2026-10-20T07:39:53Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2065/risk_evaluated_2026-10-20T07:39:53Z-risk_evaluated-a1.log`
