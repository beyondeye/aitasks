---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-06-14 11:06
updated_at: 2026-06-15 11:02
completed_at: 2026-06-15 11:02
---

## Origin

Spawned from t822_6 (extract monitor_core) during Step 8b review.

## Upstream defect

- `aidocs/benchmarks/bench_monitor_refresh.py:94` — monkeypatches
  `_tm._run_tmux_async` (`from monitor import tmux_monitor as _tm`), a
  `TmuxMonitor` method that was **deleted in t952_3** when the tmux exec-strategy
  dispatcher moved to `lib/tmux_exec.py` (`TmuxClient.run_async_via_control`).
  The benchmark has been broken since t952_3, independent of any later refactor.

## Diagnostic context

Surfaced while mapping consumers of the monitor modules for the t822_6
headless-core extraction. The benchmark still imports successfully
(`from monitor import tmux_monitor` resolves via the new t822_6 re-export shim),
but the attribute access `_tm._run_tmux_async` raises `AttributeError` at runtime
— the symbol exists in neither `tmux_monitor` (now a shim) nor `monitor_core`.
t822_6 neither introduced nor worsened this; it only confirmed the symbol is gone.

## Suggested fix

Re-point the benchmark's instrumentation at the current delegation seam — count
calls by patching `TmuxClient.run_async_via_control` (in `lib/tmux_exec.py`) or
`TmuxMonitor._tmux_async` (now in `monitor_core.py`) instead of the removed
`_run_tmux_async`. Alternatively, retire the benchmark if it is no longer used.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T08:00:52Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-15T08:00:52Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-15T08:00:52Z status=pass attempt=1 type=human
