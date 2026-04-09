---
priority: medium
effort: medium
depends: [t496_2]
issue_type: feature
status: Implementing
labels: [aitask_monitor, aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 09:07
updated_at: 2026-04-09 12:15
---

## Context

This is the final child task of t496 (Mini Monitor TUI). It adds the auto-spawn and auto-close lifecycle management: when a code agent is spawned via tmux (from board, codebrowser, or switcher), a minimonitor automatically co-locates as a side-column split pane. Depends on t496_2 (the core minimonitor TUI exists and is launchable via `ait minimonitor`).

The auto-close logic is already built into minimonitor_app.py (t496_2). This task focuses on the auto-SPAWN side: hooking into all agent launch points.

## Key Files to Modify

- `.aitask-scripts/lib/agent_launch_utils.py` — add `maybe_spawn_minimonitor()` utility function
- `.aitask-scripts/board/aitask_board.py` — hook auto-spawn after agent tmux launches
- `.aitask-scripts/codebrowser/history_screen.py` — hook auto-spawn after QA agent launch
- `.aitask-scripts/codebrowser/codebrowser_app.py` — hook auto-spawn after explain agent launch
- `.aitask-scripts/lib/tui_switcher.py` — add minimonitor to KNOWN_TUIS, hook auto-spawn in explore shortcut

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_launch_utils.py` — `launch_in_tmux()` function (lines 111-159), `TmuxLaunchConfig` dataclass
- `.aitask-scripts/board/aitask_board.py` — `on_pick_result` callbacks at lines 3237 and 3303 where `launch_in_tmux` is called
- `.aitask-scripts/codebrowser/history_screen.py` — `on_result` callback at line 289
- `.aitask-scripts/codebrowser/codebrowser_app.py` — `on_result` callback at line 698
- `.aitask-scripts/lib/tui_switcher.py` — `action_shortcut_explore()` at line 329, `KNOWN_TUIS` at line 59

## Implementation Plan

### 1. Add `maybe_spawn_minimonitor()` to `agent_launch_utils.py`

Add after `launch_in_tmux()` (~line 160):

```python
def maybe_spawn_minimonitor(session: str, window_name: str) -> bool:
    """Spawn a minimonitor split pane if no monitor exists in the target window.
    
    Called after launch_in_tmux() creates a new agent window. Checks if a 
    monitor/minimonitor already runs in that window, and if not, creates a 
    horizontal split with a 40-column minimonitor pane.
    
    Returns True if minimonitor was spawned, False otherwise.
    """
```

Logic:
1. Guard: skip if `window_name` doesn't start with any agent prefix (default: `"agent-"`)
2. Check config: read `tmux.minimonitor.auto_spawn` from `project_config.yaml` — if explicitly `false`, skip. Default is `true`.
3. Find window index: `tmux list-windows -t {session} -F "#{window_index}:#{window_name}"`, find matching window
4. Check existing panes: `tmux list-panes -t {session}:{index} -F "#{pane_current_command}"` — if any pane's command contains "minimonitor" or "monitor_app", skip (monitor already running)
5. Split: `tmux split-window -h -l 40 -t {session}:{index} ait minimonitor`
6. Refocus agent: `tmux select-pane -t {session}:{index}.0` (focus back to the agent pane, not the minimonitor)

**Config integration** — read from `project_config.yaml`:
```yaml
tmux:
  minimonitor:
    auto_spawn: true       # set to false to disable auto-spawn
    width: 40              # column width of the minimonitor pane
```

Use `load_tmux_defaults()` pattern for config loading, or inline YAML read.

### 2. Hook into board agent launches

**File:** `.aitask-scripts/board/aitask_board.py`

**2a.** Update import (line 16):
```python
from agent_launch_utils import find_terminal, resolve_dry_run_command, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor
```

**2b.** In `on_pick_result` at line 3237 (inside `check_edit`, when result == "pick"):
After `launch_in_tmux` succeeds:
```python
elif isinstance(pick_result, TmuxLaunchConfig):
    _, err = launch_in_tmux(screen.full_command, pick_result)
    if err:
        self.notify(err, severity="error")
    elif pick_result.new_window:
        maybe_spawn_minimonitor(pick_result.session, pick_result.window)
```

**2c.** Same pattern in standalone `action_pick_task` at line 3303:
```python
elif isinstance(pick_result, TmuxLaunchConfig):
    _, err = launch_in_tmux(screen.full_command, pick_result)
    if err:
        self.notify(err, severity="error")
    elif pick_result.new_window:
        maybe_spawn_minimonitor(pick_result.session, pick_result.window)
```

### 3. Hook into codebrowser agent launches

**File:** `.aitask-scripts/codebrowser/history_screen.py`

**3a.** Update import (line 11):
```python
from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor
```

**3b.** In `on_result` at line 289:
```python
elif isinstance(result, TmuxLaunchConfig):
    _, err = launch_in_tmux(screen.full_command, result)
    if err:
        self.app.notify(err, severity="error")
    elif result.new_window:
        maybe_spawn_minimonitor(result.session, result.window)
```

**File:** `.aitask-scripts/codebrowser/codebrowser_app.py`

**3c.** Update import (line 13):
```python
from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor
```

**3d.** In `on_result` at line 698:
```python
elif isinstance(result, TmuxLaunchConfig):
    _, err = launch_in_tmux(screen.full_command, result)
    if err:
        self.notify(err, severity="error")
    elif result.new_window:
        maybe_spawn_minimonitor(result.session, result.window)
```

### 4. Hook into TUI switcher + add to KNOWN_TUIS

**File:** `.aitask-scripts/lib/tui_switcher.py`

**4a.** Add to `KNOWN_TUIS` list (after monitor entry, line ~65):
```python
KNOWN_TUIS = [
    ("board", "Task Board", "ait board"),
    ("codebrowser", "Code Browser", "ait codebrowser"),
    ("brainstorm", "Brainstorm", "ait brainstorm"),
    ("settings", "Settings", "ait settings"),
    ("monitor", "tmux Monitor", "ait monitor"),
    ("minimonitor", "Mini Monitor", "ait minimonitor"),
    ("diffviewer", "Diff Viewer", "ait diffviewer"),
]
```

**4b.** In `action_shortcut_explore()` (line ~329), after spawning the agent window:
```python
def action_shortcut_explore(self) -> None:
    n = 1
    while f"agent-explore-{n}" in self._running_names:
        n += 1
    window_name = f"agent-explore-{n}"
    try:
        subprocess.Popen(
            ["tmux", "new-window", "-t", f"{self._session}:",
             "-n", window_name, "ait codeagent invoke explore"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Auto-spawn minimonitor alongside the new agent
        from agent_launch_utils import maybe_spawn_minimonitor
        maybe_spawn_minimonitor(self._session, window_name)
    except (FileNotFoundError, OSError):
        self.app.notify("Failed to launch explore", severity="error")
        return
    self.dismiss(window_name)
```

Note: deferred import to avoid any import ordering issues. `agent_launch_utils` is already imported at the top of `tui_switcher.py` so an alternative is to add `maybe_spawn_minimonitor` to the existing top-level import.

## Verification Steps

1. From `ait board`: pick a task via tmux launch → verify minimonitor auto-spawns as ~40 col right split
2. Verify focus returns to the agent pane (left), not the minimonitor
3. From TUI switcher: press `x` (explore) → verify minimonitor auto-spawns
4. From codebrowser: launch QA or explain agent → verify minimonitor auto-spawns
5. Kill the agent pane → verify minimonitor auto-closes (from t496_2's built-in logic)
6. Set `tmux.minimonitor.auto_spawn: false` in project_config.yaml → verify auto-spawn is disabled
7. In TUI switcher: verify minimonitor appears in the TUIs list
8. Manually split and run `ait minimonitor` in a window that already has one → verify `maybe_spawn_minimonitor` skips
