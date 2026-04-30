---
priority: medium
effort: medium
depends: [t719_2]
issue_type: performance
status: Ready
labels: [performance, monitor, tui]
created_at: 2026-04-30 10:27
updated_at: 2026-04-30 10:27
---

## Context

Phase 2 of t719. Builds on `t719_2` (hot-path integration). Reduces tmux load further when agents are idle by ramping up the refresh interval, then snapping back to base on first change. Independent of the control-client architecture itself — operates on the existing `_last_change_time` deltas already maintained by `TmuxMonitor._finalize_capture`. Sibling auto-dep on `t719_2`.

## Key Files to Modify

- **MODIFY** `.aitask-scripts/monitor/tmux_monitor.py`
  - Track per-tick "anything changed since previous tick?" flag derived from `_last_change_time` deltas inside `_finalize_capture`.
  - Maintain a "consecutive-idle-ticks" counter that increments each tick where nothing changed and resets to zero on any change.
  - Expose `current_poll_interval(base: float) -> float` that returns `base * 2**min(idle_ticks // K, max_doublings)` where `K` and `max_doublings` come from config.
- **MODIFY** `.aitask-scripts/monitor/monitor_app.py`
  - Replace `set_interval(self._refresh_seconds, self._refresh_data)` with a re-arming `set_timer` driven by `self._monitor.current_poll_interval(self._refresh_seconds)`. After each refresh, schedule the next at the freshly-computed interval.
- **MODIFY** `.aitask-scripts/monitor/minimonitor_app.py`
  - Same swap of `set_interval` → re-arming `set_timer`.
- **MODIFY** `aitasks/metadata/project_config.yaml` (and the seed copy)
  - Add `tmux.monitor.adaptive_idle_doublings_max` (default `3` → up to 8× base).
  - Add `tmux.monitor.adaptive_change_resets` (default `true`).
  - Add `tmux.monitor.adaptive_idle_ticks_per_doubling` (default `5`).
- **NEW** `tests/test_adaptive_polling.sh` — unit-style test that drives synthetic snapshots through `_finalize_capture` and asserts interval doublings + resets.

## Reference Files for Patterns

- `.aitask-scripts/monitor/tmux_monitor.py:414-442` — current `_finalize_capture` implementation; the change-detection signal is `prev != compare_value` on line ~424. Hook the per-tick aggregate at the end of `capture_all_async` (line 495), not inside `_finalize_capture` (which is per-pane).
- `.aitask-scripts/monitor/tmux_monitor.py:702-740` — current `load_monitor_config` reads from `aitasks/metadata/project_config.yaml`. Extend it to read the three new keys with sensible defaults.
- `seed/project_config.yaml` — mirror new keys here so fresh installs get them.

## Implementation Plan

### 1. Per-tick change signal

Inside `TmuxMonitor`, add:

```python
self._idle_ticks: int = 0
self._tick_had_change: bool = False
```

Set `self._tick_had_change = True` from `_finalize_capture` whenever `prev != compare_value` (an actual content change). At the end of `capture_all_async` and `capture_all`:

```python
if self._tick_had_change:
    self._idle_ticks = 0
else:
    self._idle_ticks += 1
self._tick_had_change = False
```

### 2. Adaptive interval

```python
def current_poll_interval(self, base: float) -> float:
    if not self._adaptive_change_resets:
        return base
    doublings = min(self._idle_ticks // self._adaptive_idle_ticks_per_doubling,
                    self._adaptive_idle_doublings_max)
    return base * (2 ** doublings)
```

Defaults read in `__init__` from `load_monitor_config`'s extended return.

### 3. Re-arming timer in monitor_app.py

Replace:

```python
self.set_interval(self._refresh_seconds, self._refresh_data)
```

With:

```python
self._reschedule_refresh()

# elsewhere:
def _reschedule_refresh(self) -> None:
    interval = self._monitor.current_poll_interval(self._refresh_seconds) if self._monitor else self._refresh_seconds
    self.set_timer(interval, self._refresh_and_reschedule)

async def _refresh_and_reschedule(self) -> None:
    await self._refresh_data()
    self._reschedule_refresh()
```

### 4. minimonitor_app.py

Same pattern in `_start_monitoring` (line 205 in current file).

### 5. Config plumbing

Extend `load_monitor_config` (line 702) to read:

```yaml
tmux:
  monitor:
    adaptive_idle_doublings_max: 3
    adaptive_change_resets: true
    adaptive_idle_ticks_per_doubling: 5
```

Pass these as kwargs to `TmuxMonitor.__init__`.

### 6. Test (`tests/test_adaptive_polling.sh`)

Driver runs a Python helper that:
- Constructs a `TmuxMonitor` directly (no real tmux required for this logic-level test).
- Manually invokes `_finalize_capture` with synthetic content sequences.
- Asserts `current_poll_interval(3.0)` returns 3.0 initially, 6.0 after K=5 idle ticks, 12.0 after 10, 24.0 after 15, capped at 24.0 (max 3 doublings) thereafter, and snaps back to 3.0 after a change tick.

Skip if `tmux` is unavailable only if the test path also invokes capture (it doesn't in the unit-style test).

## Verification Steps

- `bash tests/test_adaptive_polling.sh` — passes locally on Linux.
- `bash tests/test_tmux_control.sh` (from `t719_1`) — still passes.
- `python3 aidocs/benchmarks/bench_monitor_refresh.py` (from `t719_2`) — still reports the speedup; the benchmark uses fixed N iterations at fixed-interval-equivalent so adaptive logic doesn't affect it.
- Manual smoke: launch `ait monitor` against an idle session; observe interval grow over ~30 seconds (visible via `--debug` log line if added, or by infrequent capture-pane subprocesses in `strace` / `dtruss`); type into an agent → next tick fires at base interval again.
- Deeper manual verification deferred to `t719_5`.
- `git diff --stat` confined to: tmux_monitor.py, monitor_app.py, minimonitor_app.py, project_config.yaml, seed/project_config.yaml, plus one new test.
- **No new whitelisting needed** (no new `.aitask-scripts/aitask_*.sh` helper). Confirm by `grep -rn "test_adaptive_polling" .claude/ seed/` returning nothing.
