---
Task: t1111_3_kill_sync_tmux_in_refresh.md
Parent Task: aitasks/t1111_monitor_ui_thread_offload_perf.md
Sibling Tasks: aitasks/t1111/t1111_*.md
Worktree: aiwork/t1111_3_kill_sync_tmux_in_refresh
Branch: aitask/t1111_3_kill_sync_tmux_in_refresh
Base branch: main
---

Kill **synchronous tmux calls** on the UI thread inside `_refresh_data`.

## Context
Part of t1111 (`ait monitor` UI-thread offload). Several sync tmux round-trips run
on the Textual event-loop thread inside the 3s refresh. `tmux_run` blocks the
caller until the bg control loop completes the round-trip (`monitor_core.py:884-887`),
so each is a UI-thread stall per tick.

## Key files to modify
- `.aitask-scripts/monitor/monitor_app.py` (focus-request + session-bar paths).
- Possibly a small `monitor_core.py` helper (surgical) — `tmux_run_async` already
  exists at `monitor_core.py:891-901`, reuse it.

## Problem — four sync paths
1. `_consume_focus_request` (784-787, `show-environment` via `tmux_run`).
2. `_clear_focus_request` (798-805, `set-environment -u` via `tmux_run`) — called
   from `_refresh_data:732` after a successful focus match. **Easy to miss.**
3. `_read_attached_session` (958-965, `display-message` via `tmux_run`,
   multi-session only, called from `_rebuild_session_bar`:932).
4. `_get_desync_summary(cwd)` (915) — already has a 30s in-proc TTL cache
   (`desync_summary.py:33-37`), so mostly mitigated; lowest priority.

## Implementation plan
Convert the *uncached* sync round-trips to async via the existing `tmux_run_async`:
1. Make `_consume_focus_request` async (or add `_consume_focus_request_async`); await
   it in `_refresh_data` before the focus-match loop.
2. **Make `_clear_focus_request` async too**; await it at the `_refresh_data`
   focus-match site (732). Do NOT leave a sync `set-environment` on the loop.
3. Fetch the attached session asynchronously (`_read_attached_session_async`) and
   pass the value into `_rebuild_session_bar` instead of it calling `tmux_run`
   inline; await before building the bar.
4. Leave `_get_desync_summary` as-is (TTL-cached); note its cache-miss subprocess is
   picked up by the t1111_4 offload work if needed.

## Reference patterns
- `tmux_run_async` (`monitor_core.py:891-901`) and `capture_pane_async`
  (`1249-1258`) show the async dispatch through the bg control loop.
- Follow `aidocs/framework/tmux_gateway.md` — the sanctioned tmux call sites.

## Verification
- New `tests/test_monitor_refresh_no_sync_tmux.py`: run `_refresh_data` once against
  a fake `TmuxMonitor` whose sync `tmux_run` is a spy that records/raises; assert
  `tmux_run` is **never** called during a refresh — **including the focus-match
  branch that calls `_clear_focus_request`** (drive a refresh where the focus-request
  env var is set and matched, so the clear path is exercised). All tmux must go via
  `*_async`. Without exercising the match branch, the guarantee is silently weakened.
- Manually: `ait monitor`, trigger a minimonitor focus request, confirm focus
  follows and no stall.

## Risk
code-health low, goal low–medium (session-bar value must be threaded through
`_rebuild_session_bar` correctly). No new threading (async only).

## Final Implementation Notes
- **Actual work done:** Removed the uncached synchronous tmux round-trips from
  `MonitorApp._refresh_data`. Focus-request consume/clear and attached-session
  reads now use `tmux_run_async`; `_refresh_data` awaits the session-to-project
  mapping through a new async `TmuxMonitor` cache path; and multi-session pane
  discovery now uses async session discovery on cold cache / cache invalidation.
  Added `discover_aitasks_sessions_async()` in `agent_launch_utils.py` and
  factored shared non-I/O assembly so sync and async discovery preserve pane-cwd
  detection, registry fallback, project-group resolution, registered/stale row
  synthesis, dedupe, and sorting. Added regression coverage in
  `tests/test_discover_async_parity.py` and
  `tests/test_monitor_refresh_no_sync_tmux.py`.
- **Deviations from plan:** Expanded beyond the three direct `monitor_app.py`
  `tmux_run` calls after review found hidden refresh-path sync tmux through
  multi-session session discovery. Kept `_rebuild_session_bar()` callable from
  synchronous actions by making the attached-session argument optional and using
  `self._session` as the deliberate fallback until the next refresh.
- **Issues encountered:** Textual's `Static` test object exposes updated content
  via `.content`, not `.renderable`; the session-bar fallback test was adjusted
  accordingly. No production issue found during implementation.
- **Key decisions:** Shared discovery assembly rather than duplicating the sync
  helper's business rules in the async helper. The async discovery path remains
  sequential per session, matching sync ordering and behavior while yielding the
  event loop during each tmux round-trip.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** The refresh path still performs local registry /
  config file reads and the TTL-cached `_get_desync_summary(Path.cwd())` call on
  the UI thread; those are intentionally left for the broader t1111 refresh
  offload work. Minimonitor still has its own sync tmux calls and is out of
  scope for this child.
