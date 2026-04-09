---
Task: t496_3_autospawn_integration.md
Parent Task: aitasks/t496_minimonitor.md
Sibling Tasks: aitasks/t496/t496_1_extract_monitor_shared.md, aitasks/t496/t496_2_core_minimonitor_tui.md
Archived Sibling Plans: aiplans/archived/p496/p496_1_*.md, aiplans/archived/p496/p496_2_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Auto-Spawn Integration (t496_3)

## Overview

Hook minimonitor auto-spawn into all agent launch points (board, codebrowser, TUI switcher). When a code agent is spawned in a new tmux window, a minimonitor automatically splits alongside it as a ~40-column right pane.

## Steps

### 1. Add `maybe_spawn_minimonitor()` to `agent_launch_utils.py`

**File:** `.aitask-scripts/lib/agent_launch_utils.py`

New function after `launch_in_tmux()` (~line 172):

```python
def maybe_spawn_minimonitor(session: str, window_name: str) -> bool:
```

Logic:
1. Guard: skip if `window_name` doesn't start with `"agent-"`
2. Config check: read `tmux.minimonitor.auto_spawn` from `project_config.yaml`. Default `true`. If `false`, return.
3. Config width: read `tmux.minimonitor.width` from config. Default `40`.
4. Find window index via `tmux list-windows -t {session}`
5. Check existing panes via `tmux list-panes -t {session}:{index} -F "#{pane_current_command}"`. Skip if any contains "minimonitor" or "monitor_app"
6. `tmux split-window -h -l {width} -t {session}:{index} ait minimonitor`
7. `tmux select-pane -t {session}:{index}.0` (refocus agent)
8. Return True

### 2. Hook into board (`aitask_board.py`)

- Add `maybe_spawn_minimonitor` to import (line 16)
- In `on_pick_result` at lines 3336 and 3416: after `launch_in_tmux` succeeds with `new_window=True`:
  ```python
  elif pick_result.new_window:
      maybe_spawn_minimonitor(pick_result.session, pick_result.window)
  ```

### 3. Hook into codebrowser

**`history_screen.py` (lines 11, 289):** Add `maybe_spawn_minimonitor` to import, call after launch_in_tmux succeeds with `new_window=True`.

**`codebrowser_app.py` (lines 13, 698):** Same pattern.

### 4. Hook into TUI switcher (`tui_switcher.py`)

- ~~Add `("minimonitor", "Mini Monitor", "ait minimonitor")` to `KNOWN_TUIS`~~ — **already done by t496_2** (line 65)
- In `action_shortcut_explore()` (line 328): after spawning agent window, call `maybe_spawn_minimonitor(self._session, window_name)` via deferred import

### 5. Single-instance guard in `aitask_minimonitor.sh`

Before `exec`, check if another minimonitor or monitor is already running in the same tmux window. If inside tmux (`$TMUX` set):
1. Get current window panes: `tmux list-panes -F "#{pane_pid}:#{pane_current_command}"`
2. Exclude own PID (`$$`)
3. If any remaining pane's command contains "minimonitor" or "monitor_app", print message and exit 0

This prevents manual `ait minimonitor` from spawning a second instance.

### 6. Config support

Add to `project_config.yaml` (or just document as optional):
```yaml
tmux:
  minimonitor:
    auto_spawn: true
    width: 40
```

## Verification

1. Board pick via tmux → minimonitor auto-spawns as right split
2. Focus stays on agent pane (left)
3. Switcher explore (`x`) → minimonitor auto-spawns
4. Codebrowser QA/explain launch → minimonitor auto-spawns
5. Agent finishes → minimonitor auto-closes
6. `auto_spawn: false` → no auto-spawn
7. Minimonitor in KNOWN_TUIS list in switcher
8. Double-spawn prevention: manually run `ait minimonitor` then trigger auto-spawn → second one skipped

## Post-Review Changes

### Change Request 1 (2026-04-09)
- **Requested by user:** (1) Minimonitor should not appear in TUI switcher — it's a companion pane, not a standalone TUI. (2) Full monitor shows minimonitor pane as duplicate agent in agent list.
- **Changes made:** Removed minimonitor from `KNOWN_TUIS` in tui_switcher.py. Added `_is_companion_process()` helper in `tmux_monitor.py` that checks `/proc/<pid>/cmdline` (with `ps` fallback for macOS) to detect minimonitor/monitor panes — these are now filtered out of `discover_panes()` when they appear in agent windows.
- **Files affected:** `.aitask-scripts/lib/tui_switcher.py`, `.aitask-scripts/monitor/tmux_monitor.py`

## Final Implementation Notes
- **Actual work done:** Created `maybe_spawn_minimonitor()` in agent_launch_utils.py with agent-prefix guard, config reading, duplicate detection, and tmux split-window spawning. Hooked it into board (2 pick callback sites), codebrowser (QA + explain), and TUI switcher (explore shortcut). Added single-instance guard in aitask_minimonitor.sh. Added companion pane filtering in tmux_monitor.py to prevent full monitor from showing minimonitor as duplicate agent. Removed minimonitor from KNOWN_TUIS in tui_switcher.py.
- **Deviations from plan:** (1) KNOWN_TUIS already had minimonitor from t496_2 — removed it instead since minimonitor is a companion pane, not a standalone TUI. (2) Added `_is_companion_process()` to tmux_monitor.py to filter minimonitor panes from agent discovery — not in original plan but needed to prevent the full monitor from showing them as duplicate agents.
- **Issues encountered:** Full monitor classified minimonitor pane as AGENT because it shares the agent window name. Fixed by checking process cmdline via `/proc/<pid>/cmdline`.
- **Key decisions:** Used `/proc/<pid>/cmdline` with `ps` fallback for portability. Companion pane filtering only applies to session-wide `discover_panes()`, not window-specific `discover_window_panes()` (used by minimonitor for auto-close).
- **Notes for sibling tasks:** This is the final child task. The minimonitor is fully integrated: auto-spawns alongside agents, auto-closes when agents exit, single-instance enforced both in auto-spawn and manual launch paths, and properly hidden from both TUI switcher and full monitor agent list.

## Step 9: Post-Implementation
Archive task, push changes, collect feedback.
