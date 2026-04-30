---
Task: t719_3_adaptive_polling.md
Parent Task: aitasks/t719_monitor_tmux_control_mode_refactor.md
Sibling Tasks: aitasks/t719/t719_1_control_client_module.md, aitasks/t719/t719_2_hot_path_integration.md, aitasks/t719/t719_4_pipe_pane_push.md
Archived Sibling Plans: aiplans/archived/p719/p719_*_*.md
Worktree: aiwork/t719_3_adaptive_polling
Branch: aitask/t719_3_adaptive_polling
Base branch: main
---

# Plan — t719_3: Adaptive polling (Phase 2)

## Goal

Reduce tmux load further when agents are idle by ramping the refresh
interval up to a cap, snapping back to base on the first content change.
Independent of the control-client architecture; operates on the
`_last_change_time` deltas already maintained by `TmuxMonitor`.

## Files to modify

- `.aitask-scripts/monitor/tmux_monitor.py`
- `.aitask-scripts/monitor/monitor_app.py`
- `.aitask-scripts/monitor/minimonitor_app.py`
- `aitasks/metadata/project_config.yaml` (and `seed/project_config.yaml`)

## Files to add

- `tests/test_adaptive_polling.sh`

## Step 1 — Per-tick change signal in `TmuxMonitor`

Extend `__init__`:

```python
self._idle_ticks: int = 0
self._tick_had_change: bool = False
self._adaptive_change_resets: bool = adaptive_change_resets
self._adaptive_idle_doublings_max: int = adaptive_idle_doublings_max
self._adaptive_idle_ticks_per_doubling: int = adaptive_idle_ticks_per_doubling
```

In `_finalize_capture`, where the existing code detects an actual content
change (`prev is None or compare_value != prev` — line ~424), additionally
set:

```python
if prev is not None and compare_value != prev:
    self._tick_had_change = True
```

(Note: `prev is None` is first-sight, not a *change* in the adaptive
sense — don't reset interval just because the pane appeared.)

At the end of `capture_all_async` and `capture_all`:

```python
def _settle_tick(self) -> None:
    if self._tick_had_change:
        self._idle_ticks = 0
    else:
        self._idle_ticks += 1
    self._tick_had_change = False
```

Call `self._settle_tick()` after the per-pane capture loop.

## Step 2 — `current_poll_interval`

```python
def current_poll_interval(self, base: float) -> float:
    if not self._adaptive_change_resets:
        return base
    doublings = min(
        self._idle_ticks // self._adaptive_idle_ticks_per_doubling,
        self._adaptive_idle_doublings_max,
    )
    return base * (2 ** doublings)
```

## Step 3 — `load_monitor_config` extension

Extend the dict returned by `load_monitor_config` (lines 702–740) with:

```python
defaults["adaptive_idle_doublings_max"] = 3
defaults["adaptive_change_resets"] = True
defaults["adaptive_idle_ticks_per_doubling"] = 5
```

Read overrides from `monitor.adaptive_idle_doublings_max`,
`monitor.adaptive_change_resets`, `monitor.adaptive_idle_ticks_per_doubling`.

## Step 4 — Re-arming timer in `monitor_app.py`

Replace the static `set_interval(self._refresh_seconds, self._refresh_data)`
with:

```python
def _reschedule_refresh(self) -> None:
    interval = (
        self._monitor.current_poll_interval(self._refresh_seconds)
        if self._monitor else self._refresh_seconds
    )
    self.set_timer(interval, self._refresh_and_reschedule)

async def _refresh_and_reschedule(self) -> None:
    await self._refresh_data()
    self._reschedule_refresh()
```

Call `self._reschedule_refresh()` once at the end of `_start_monitoring`.

## Step 5 — Re-arming timer in `minimonitor_app.py`

Same pattern in `_start_monitoring` (line 205 currently uses
`set_interval`).

## Step 6 — Config seed update

In `aitasks/metadata/project_config.yaml` and `seed/project_config.yaml`,
under `tmux.monitor:` add:

```yaml
adaptive_idle_doublings_max: 3
adaptive_change_resets: true
adaptive_idle_ticks_per_doubling: 5
```

## Step 7 — Test (`tests/test_adaptive_polling.sh`)

Logic-level test (no real tmux required):

```bash
#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=.aitask-scripts python3 - <<'PYEOF'
import sys
sys.path.insert(0, ".aitask-scripts")
from monitor.tmux_monitor import TmuxMonitor, TmuxPaneInfo, PaneCategory

mon = TmuxMonitor(
    session="dummy", capture_lines=10, idle_threshold=5.0,
    multi_session=False,
    adaptive_idle_doublings_max=3,
    adaptive_change_resets=True,
    adaptive_idle_ticks_per_doubling=5,
)

p = TmuxPaneInfo(
    window_index="0", window_name="agent-1", pane_index="0",
    pane_id="%1", pane_pid=1, current_command="bash",
    width=80, height=24, category=PaneCategory.AGENT, session_name="dummy",
)
mon._pane_cache[p.pane_id] = p

# First tick: prev is None → no change
mon._finalize_capture(p, "hello\n"); mon._settle_tick()
assert mon.current_poll_interval(3.0) == 3.0, mon.current_poll_interval(3.0)

# 5 idle ticks → 1 doubling → 6.0
for _ in range(5):
    mon._finalize_capture(p, "hello\n"); mon._settle_tick()
assert mon.current_poll_interval(3.0) == 6.0, mon.current_poll_interval(3.0)

# Another 5 idle ticks → 2 doublings → 12.0
for _ in range(5):
    mon._finalize_capture(p, "hello\n"); mon._settle_tick()
assert mon.current_poll_interval(3.0) == 12.0, mon.current_poll_interval(3.0)

# A change → snap back
mon._finalize_capture(p, "world\n"); mon._settle_tick()
assert mon.current_poll_interval(3.0) == 3.0, mon.current_poll_interval(3.0)

print("PASS")
PYEOF

echo "PASS: test_adaptive_polling"
```

## Verification

- `bash tests/test_adaptive_polling.sh` — passes.
- `bash tests/test_tmux_control.sh` (from `t719_1`) — still passes.
- `python3 aidocs/benchmarks/bench_monitor_refresh.py` (from `t719_2`) —
  still reports the speedup (the benchmark uses fixed N iterations not
  driven by the adaptive timer, so this child doesn't affect those numbers).
- Manual smoke: launch `ait monitor` against an idle session; observe
  interval grow over ~30 seconds; type into an agent → next tick fires at
  base interval again.
- `git diff --stat` confined to: tmux_monitor.py, monitor_app.py,
  minimonitor_app.py, project_config.yaml, seed/project_config.yaml,
  plus one new test.
- **No new whitelisting** — no new `.aitask-scripts/aitask_*.sh` helper.
  Confirm: `grep -rn "test_adaptive_polling" .claude/ seed/` returns nothing.

## Step 9 — Post-Implementation

Standard archival per `task-workflow/SKILL.md` Step 9.

## Notes for sibling tasks

- `current_poll_interval` is the public surface other code can read. If
  `t719_4` ships pipe-pane and changes the polling model entirely, this
  helper still applies — pipe-pane only eliminates `capture-pane` calls,
  not the discovery tick where `list-panes` runs.
- `_settle_tick` MUST be called exactly once per tick (after the per-pane
  capture loop). Do not call it from `_finalize_capture` itself.
