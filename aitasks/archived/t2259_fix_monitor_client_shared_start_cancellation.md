---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [monitor, applink]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-09 15:18
updated_at: 2026-11-10 08:07
completed_at: 2026-11-10 08:07
---

## Origin

Spawned from t2037_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/status_client.py:387-405` — `MonitorClient.start()` awaits its startup task unshielded. Cancelling the first caller therefore cancels the shared startup, and the client is left in `connecting`: no fallback and no reconnect task, with `_started` true, so every later `start()` returns at once. This was worked around for applink with `start_detached()`. The monitor apps own their client, so they are unaffected today, but any future shared caller would hit it.

## Diagnostic context

From t2037_4's plan review (archived plan `aiplans/archived/p2037/p2037_4_applink_subscribe_status_server.md`):

- **How it shows.** applink shares one `MonitorClient` across every phone's push loop. If phone A's loop is the first reader, phone B joins, and A disconnects mid-startup, then `PushScheduler.stop()` cancels A's loop. That cancels `_start_task` through the unshielded `await`. `_start_body`'s `finally` sets `_ready` without `_enter_fallback` or a reconnect, so B is stuck reading a `connecting` client.
- **The reviewer's repro.** Two `start()` callers and a held connection attempt. After the first caller is cancelled, later `start()` calls return with `mode=connecting`, `started=True` and no reconnect task.
- **Controls.** `tests/test_monitor_status_client.py::SharedClientTests` shows it: making the first waiter own the start leaves the mode `CONNECTING`. A `start_detached()` start reaches `SERVER` / `FALLBACK`.

## Suggested fix

- **Option 1.** Make `start()` itself cancellation-safe: `await asyncio.shield(self._start_task)` for every caller, keeping `close()` as the only canceller. Then check whether any caller relies on "cancelling the caller aborts the attempt":
  - `test_cancelled_start_closes_the_socket` does;
  - the monitor apps' unmount path already calls `close()`.
- **Option 2.** Have every multi-caller user use `start_detached()`, and document `start()` as single-owner only.

Either way, pin the behaviour with a two-caller test, plus its positive control.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-09T20:25:11Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-09T21:13:56Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-10T06:07:48Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:c30241012c6f2e61

> **✅ gate:risk_evaluated** run=2026-11-10T06:07:48Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2259/risk_evaluated_2026-11-10T06:07:48Z-risk_evaluated-a1.log`
