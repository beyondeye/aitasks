---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [minimonitor, tmux, tui]
gates: [risk_evaluated]
anchor: 1446
created_at: 2026-08-07 12:13
updated_at: 2026-08-07 12:13
---

## Origin

Risk-mitigation ("after") follow-up for t1446, created at Step 8d after implementation landed.

## Risk addressed

code-health — the sync `tmux_run` on the async refresh tick still blocks the
event loop for up to 5 s during a stall.

From t1446's plan `## Risk` section:

> The fix removes the *fatal* consequence of a tmux stall but leaves
> `discover_window_panes` on the **sync** `tmux_run` path, called from the async
> `_refresh_data` tick — so the same 5 s timeout still blocks Textual's event
> loop during a stall. This contradicts the t1111_3 invariant that
> `tests/test_monitor_refresh_no_sync_tmux.py` encodes (that suite does not
> reach this call). · severity: medium

Re-verified at t1446's post-implementation review: the call is still
`self.tmux_run([...])` at `monitor_core.py:1779` with no `timeout=` argument
(the 5.0 s default), reached from the async `_refresh_data` through the sync
`self._check_auto_close()` at `minimonitor_app.py:499`. So a stalled tmux can
still freeze the minimonitor UI for up to 5 s per tick — it just can no longer
*close* it, which is what t1446 required.

Historical note: `aiplans/archived/p719/p719_2_hot_path_integration.md:130`
deliberately left `discover_window_panes` on the sync path, classified as
"user-action triggered, not per-tick". That classification is wrong today — it
IS per-tick, via `_check_auto_close`.

## Goal

Move `discover_window_panes` onto the async gateway and keep the refresh loop
free of sync tmux round-trips:

1. Add an async variant of `TmuxMonitor.discover_window_panes` built on
   `tmux_run_async` / `_tmux_async`, preserving t1446's `(observed, panes)`
   contract exactly — `observed` is `True` only when tmux answered AND every
   non-blank record parsed. Extract the parse loop so both variants share it
   rather than duplicating the completeness logic.
2. Make `MiniMonitorApp._check_auto_close` async and `await` it from
   `_refresh_data` (`minimonitor_app.py:499`).
3. Extend `tests/test_monitor_refresh_no_sync_tmux.py` so the invariant covers
   the **minimonitor** refresh path — today that suite targets
   `MonitorApp`/`TmuxMonitor` and its `_FakeRefreshMonitor` never exposes
   `discover_window_panes`, which is why this violation went unnoticed.
4. Keep `tests/test_minimonitor_auto_close_guard.py` green; its layer 2/3
   fixtures script `tmux_run`, so they will need the async seam too.

## Out of scope

The auto-close *decision* logic (t1446) is settled — do not revisit the
`(observed, panes)` contract, the self-sighting rule, or
`AUTO_CLOSE_CONFIRMATIONS`. This task is purely about where the tmux round-trip
runs.
