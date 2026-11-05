---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [monitor, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-05 08:28
updated_at: 2026-11-05 11:56
---

## Origin

Spawned from t2037_1 during the Step 8b review.

## Upstream defect

- `tests/test_monitor_shadow_zone.py` — `MountedShadowColumnTests` asserts after a single `pilot.pause()` while the app's mount-time refresh worker may still be in flight. `_refresh_data()` then returns early on its re-entrancy guard, so `#shadow-col` is intermittently not shown, or not yet sized.

## Diagnostic context

- The failure shows up as `test_shadow_column_shown_and_sized_from_real_pane_width` failing with `assertTrue(col.display)` → False. Sometimes `test_full_refresh_renders_the_shadow_column_from_the_pane_list` fails instead. It appeared in one full suite run under the xdist lane, and in direct script runs.
- Measured interleaved, script runs of the whole module (t2037_1, 2026-11-04, one host):
  - a detached worktree at HEAD `4c51b9150`: 2 failing runs in 30;
  - the same plus the t2037_1 diff: 6 in 30.

  The difference is not significant, and the test stubs discovery and capture, so none of t2037_1's changed producer paths run.
- In the fixture (`_make_monitor` / `_make_app`), `MonitorApp` starts its own first refresh through `run_worker(self._refresh_data(), name="first_refresh")` when it mounts. While that worker holds `_refresh_inflight`, the test's own `await app._refresh_data()` returns immediately (the t1598 re-entrancy guard), and one `pilot.pause()` is not guaranteed to cover the worker finishing.

## Suggested fix

Before the assertions, wait until the mount-time refresh has finished: wait for `app._refresh_inflight` to be false, or await the `first_refresh` worker, then call `_refresh_data()`. Alternatively, poll the asserted condition with a bounded deadline instead of pausing once. Keep the assertions themselves unchanged.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-05T09:56:47Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-05T12:52:59Z status=pass attempt=1 type=human
