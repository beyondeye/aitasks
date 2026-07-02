---
Task: t1111_1_gate_ledger_mtime_cache.md
Parent Task: aitasks/t1111_monitor_ui_thread_offload_perf.md
Sibling Tasks: aitasks/t1111/t1111_*.md
Worktree: aiwork/t1111_1_gate_ledger_mtime_cache
Branch: aitask/t1111_1_gate_ledger_mtime_cache
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-02 14:56
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

### Code-health risk: low
- None identified. Narrow blast radius (one class in `monitor_core.py` + one line
  removed in `monitor_app.py`; `minimonitor` keeps its own `clear()` and is
  untouched). Mirrors the established board gate-cache pattern; the cache still
  fails closed to `""` on any IO/parse error. No threading. No AC deviation expected.

### Goal-achievement risk: low
- None identified. Approach is sound — `(st_mtime_ns, st_size)` identity correctly
  avoids the float-second aliasing trap and fully covers the requirement (removes
  the per-tick blanket clear, keeps live-ledger freshness via mtime invalidation).

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned. `GateSummaryCache._cache`
  in `monitor_core.py` changed from `dict[str, str]` to
  `dict[str, tuple[tuple[int, int], str]]`; `summary_for` now does a fail-closed
  `os.stat(key)` (missing/unreadable → `pop` any stale entry and return `""` with
  no raise), computes `identity = (st.st_mtime_ns, st.st_size)`, and returns the
  cached summary when the stored identity matches — otherwise re-reads via the
  existing `has_gate_markers` → `read_task_gate_state` → `compact_gate_summary`
  path and stores `(identity, summary)`. Removed the per-tick
  `self._gate_cache.clear()` from `_refresh_data` (`monitor_app.py`), replacing it
  with a comment explaining the mtime-invalidation contract. Class docstring
  rewritten to describe identity-based invalidation and to note `clear()` is
  retained for minimonitor. Added `tests/test_monitor_gate_cache.py`.
- **Deviations from plan:** None. Also refreshed the `GateSummaryCache` docstring
  (the plan didn't call it out, but it described the old per-tick-clear behavior
  and would have been stale/misleading otherwise).
- **Issues encountered:** None. The pre-existing `test_monitor_gate_summary.py`
  (`test_caches_and_clears`, `test_fail_closed_on_missing_file`) still passes
  unchanged — `clear()` semantics and fail-closed-to-`""` are preserved; the spy
  counts only `read_task_gate_state`, so the extra `os.stat` is invisible to it.
- **Key decisions:** Used `st_mtime_ns` + `st_size` (not float `st_mtime`) per the
  plan — the new `test_same_mtime_different_size_rereads` forces mtime_ns back to
  the original value after a different-length rewrite to prove the size component
  is load-bearing. On an `os.stat` miss the entry is `pop`ed (not just returned
  empty) so a transiently-missing file cannot serve a stale summary later.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** `GateSummaryCache` is defined in
  `monitor_core.py` and re-exported via `monitor_shared.py` (tests import it from
  `monitor.monitor_shared`). `minimonitor_app.py` still calls `_gate_cache.clear()`
  every refresh (line ~440) and does **not** yet benefit from mtime invalidation
  within a tick — that minimonitor follow-up is deliberately deferred (see parent
  t1111 fix #3/#5 and the plan's step 4). The remaining t1111 children
  (t1111_2..t1111_6) target the focus-switch double-render, sync-tmux offload,
  thread-offload of `_refresh_data`, preview-render offload, and manual
  verification respectively.
