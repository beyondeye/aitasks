---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tests, textual]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-10 11:44
updated_at: 2026-11-10 15:17
---

## Origin

Spawned from t2267 during Step 8b review.

## Upstream defect

- `tests/test_frozenagent_app.py:1092-1103 — the 2.0 s budget times ten pilot.press("shift+down") calls plus pilot.pause(); each press carries Textual's wait_for_idle settle (two calls, up to 1 s each), so a busy process can blow the budget whatever the incremental repaint costs (same mechanism as t2267's scratchpad bounds)`

## Diagnostic context

From t2267 (archived plan `aiplans/archived/p2267_fix_monitor_client_start_after_close.md`):

- **How `pilot.press` spends its time.** In Textual 8.2.7, `Pilot.press` calls
  `App._press_keys`. That sends the key, then awaits `wait_for_idle(0)`,
  `animator.wait_until_complete()` and `wait_for_idle(0)` again.
  - Each `wait_for_idle` sleeps in 20 ms windows until the process's CPU time
    advances by less than 1 ms in one window, capped at `max_sleep=1`.
  - So a single press costs at least about 40 ms even on an idle box, and up
    to about 2 s on a busy one, regardless of the app.
- **Measured in t2267.** The scratchpad app exited 1 ms after `ctrl+q`, while
  `pilot.press("ctrl+q")` returned at 2.04 s. That reproduced the reported
  `2.016 not less than 1.0` suite failure.
  - The injection was `textual._wait.SLEEP_IDLE = -1` ("never idle"), which
    drives every press to the cap.
  - t1660 found the same mechanism in
    `tests/test_minimonitor_startup_input_latency.py`.
- **This test.** `test_frozenagent_app.py:1092-1103` times ten
  `pilot.press("shift+down")` calls plus `pilot.pause()` against a 2.0 s
  budget, whose comment reads "Generous: the point is orders of magnitude".
  - Ten presses cost at least about 0.4 s of harness settle when idle, and up
    to about 20 s when busy.
  - The budget therefore mostly measures the harness, not the incremental
    repaint it means to guard. The render-count assertion (`renders["n"] == 0`)
    is timing-free and unaffected.
- Not run under load or under the never-idle injection yet. Confirm with the
  injection first: run the test with `textual._wait.SLEEP_IDLE = -1`.

## Suggested fix

Time the property, not the pilot.
- Send each key with `app._driver.send_message(events.Key(key, None))`, the
  exact call `_press_keys` makes. This is the technique in t1660
  (`_press_and_observe`) and in t2267's `key_latency` helper in
  `tests/test_scratchpad_app.py`.
- Wait on an observable effect: the mark position after ten moves, then the
  search hit.
- Keep a mutation control that still catches the regression the budget guards:
  a full re-render per mark move, timed or counted.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T13:17:18Z status=pass attempt=1 type=human
