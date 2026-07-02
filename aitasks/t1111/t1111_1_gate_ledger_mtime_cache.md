---
priority: high
effort: low
depends: []
issue_type: performance
status: Implementing
labels: [monitor, tui, performance]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus4_8
created_at: 2026-07-02 14:43
updated_at: 2026-07-02 15:00
---

Gate-ledger **mtime cache** for the monitor — stop re-reading every visible
gated task's ledger from disk on every 3s refresh tick.

## Context
Part of t1111 (`ait monitor` UI-thread offload). `_refresh_data` calls
`self._gate_cache.clear()` every tick (`monitor_app.py:702`), so
`GateSummaryCache.summary_for` re-reads each visible gated task's ledger from disk
every 3s (`monitor_core.py:1631-1633` → `gate_ledger.read_task_gate_state`). This
is per-agent disk I/O on the UI thread, scaling with agent count. Replace the
blanket per-tick clear with mtime-based invalidation. Lowest-risk child; land first.

## Key files to modify
- `.aitask-scripts/monitor/monitor_core.py` — `GateSummaryCache` (1599-1637).
- `.aitask-scripts/monitor/monitor_app.py:702` — remove the per-tick
  `self._gate_cache.clear()` call inside `_refresh_data`.

## Implementation plan
1. `GateSummaryCache._cache`: `dict[str, str]` → `dict[str, tuple[tuple[int, int], str]]`
   where the validity key is `(st_mtime_ns, st_size)` and the value is the summary.
2. In `summary_for(info)`: after `key = info.task_file_abs`, `st = os.stat(key)`
   guarded by `try/except OSError` (missing/unreadable → treat as miss, fail closed
   to `""`, do not raise). Identity = `(st.st_mtime_ns, st.st_size)`.
   **Use `st_mtime_ns`, NOT float `st_mtime`** — float-second granularity misses two
   ledger edits within the same wall-clock second; ns + size closes that cheaply.
3. Hit with unchanged identity → return cached summary. Otherwise re-read via the
   existing `has_gate_markers(info.body)` prefilter →
   `read_task_gate_state(info.task_file_abs)` → `compact_gate_summary(state)`, store
   `((mtime_ns, size), summary)`, return.
4. Keep the `clear()` method (minimonitor still calls it; leaving that call is
   correct — just no within-tick benefit there until the deferred minimonitor
   follow-up).
5. Remove `self._gate_cache.clear()` from `_refresh_data` (`monitor_app.py:702`).
6. `grep` `monitor_app.py` for any other `_gate_cache.clear()` caller that relies on
   blanket clearing (there should be none besides 702).

## Reference patterns
- Board's gate cache (`aitask_board.TaskManager.gate_state_for`) — the model this
  cache mirrors (see the `GateSummaryCache` docstring).
- `os` is already imported in `monitor_core.py`.

## Verification
- New `tests/test_monitor_gate_cache.py` (Python, self-contained): construct a
  `GateSummaryCache`; monkeypatch `gate_ledger.read_task_gate_state` with a
  call-counting spy; point a temp task file (with gate markers) at it.
  - Two `summary_for` calls → exactly 1 disk read.
  - Bump the file mtime → next call re-reads (2 reads total).
  - **Same-second content change of different length** → re-reads (proves ns/size
    identity, not float seconds).
  - Missing file → returns `""` with no raise.
- Manually: run `ait monitor`, confirm gate columns still update live as a ledger
  grows (mtime changes on each ledger append).

## Risk
code-health low, goal low. No threading. No AC deviation expected.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-02T12:00:55Z status=pass attempt=1 type=human
