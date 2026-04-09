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

New function after `launch_in_tmux()` (~line 160):

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
- In `on_pick_result` at lines 3237 and 3303: after `launch_in_tmux` succeeds with `new_window=True`:
  ```python
  elif pick_result.new_window:
      maybe_spawn_minimonitor(pick_result.session, pick_result.window)
  ```

### 3. Hook into codebrowser

**`history_screen.py` (line 11, 289):** Add import, call after launch_in_tmux succeeds with `new_window=True`.

**`codebrowser_app.py` (line 13, 698):** Same pattern.

### 4. Hook into TUI switcher (`tui_switcher.py`)

- Add `("minimonitor", "Mini Monitor", "ait minimonitor")` to `KNOWN_TUIS` (after monitor)
- In `action_shortcut_explore()`: after spawning agent window, call `maybe_spawn_minimonitor(self._session, window_name)` via deferred import

### 5. Config support

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

## Step 9: Post-Implementation
Archive task, push changes, collect feedback.
