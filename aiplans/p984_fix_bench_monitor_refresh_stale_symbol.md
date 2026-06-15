---
Task: t984_fix_bench_monitor_refresh_stale_symbol.md
Worktree: .
Branch: main
Base branch: main
---

# Fix `bench_monitor_refresh.py` Stale Tmux Symbol

## Summary

Repair `aidocs/benchmarks/bench_monitor_refresh.py` so it no longer
monkey-patches the deleted `monitor.tmux_monitor._run_tmux_async` symbol. Keep
the benchmark's `forks=` metric meaningful by counting actual async subprocess
fallback calls through `TmuxClient.run_async`.

## Implementation Plan

1. In `aidocs/benchmarks/bench_monitor_refresh.py`, replace the stale
   `_tm._run_tmux_async` import and monkey-patch with a class-level patch of
   `.aitask-scripts/lib/tmux_exec.py::TmuxClient.run_async`.
2. Preserve the benchmark counter semantics by incrementing the counter only
   when the gateway reaches the async subprocess primitive, not when it routes
   successfully through the persistent control backend.
3. Restore `TmuxClient.run_async` in the existing `finally` block.
4. Set `AITASKS_TMUX_SOCKET=""` in the isolated fixture setup so direct fixture
   `tmux` commands and gateway-backed monitor calls use the same isolated
   no-flag tmux socket under `TMUX_TMPDIR`.
5. Update nearby comments to describe the current gateway-based instrumentation
   seam.
6. Complete Step 9 post-implementation archival after code and plan commits.

## Verification

- `python3 -m py_compile aidocs/benchmarks/bench_monitor_refresh.py`
- `python3 aidocs/benchmarks/bench_monitor_refresh.py --panes 1 --iterations 1 --warmup 0`
- `python3 -m unittest tests.test_tmux_exec.TestRunViaControl`

## Risk

### Code-health risk: low
- The change is isolated to one benchmark script and uses the existing tmux
  gateway abstraction. · severity: low · -> mitigation: None

### Goal-achievement risk: low
- The plan addresses both discovered breakages: the deleted symbol and the
  benchmark fixture's socket mismatch. · severity: low · -> mitigation: None

## Final Implementation Notes

- **Actual work done:** Updated the benchmark to patch `TmuxClient.run_async`
  instead of the removed `_run_tmux_async` symbol, and aligned the fixture socket
  environment with the gateway-backed monitor.
- **Deviations from plan:** None.
- **Issues encountered:** The original smoke test failed with
  `AttributeError: module 'monitor.tmux_monitor' has no attribute
  '_run_tmux_async'`. During planning, the fixture socket mismatch was also
  identified as a necessary companion fix because `TmuxClient` now defaults to
  the dedicated `-L ait` socket.
- **Key decisions:** Count `TmuxClient.run_async` calls rather than
  `run_async_via_control` calls so `forks=` continues to mean subprocess
  fallback invocations.
- **Upstream defects identified:** None
