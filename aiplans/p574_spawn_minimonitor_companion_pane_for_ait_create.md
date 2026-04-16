---
Task: t574_spawn_minimonitor_companion_pane_for_ait_create.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

When code agents are spawned via `ait pick` (board, monitor, codebrowser), a minimonitor companion pane automatically appears alongside them, showing agent status. But when `ait create` is spawned in tmux (from tui_switcher, board, or codebrowser), no companion minimonitor appears. Users spend significant time writing task descriptions and lose visibility into their running code agents.

The minimonitor companion infrastructure already exists — we just need to extend it to also cover `create-*` windows, including both new-window and existing-window cases.

## Key difference from agent companion spawning

For code agents, companion minimonitor is ONLY spawned when a new window is created (`new_window=True`). For `ait create`, we spawn the companion in both cases:

- **New window**: spawn companion (same as agents)
- **Existing window**: also spawn companion, BUT with smart checks:
  - Skip if window already has minimonitor/monitor
  - Skip if window is a known TUI (board, brainstorm, codebrowser, etc.)
  - Skip if window already has 3+ panes (avoid overcrowding)

This difference exists because `ait create` is primarily about writing task descriptions — the user benefits from agent visibility regardless of which window they're in.

## Plan

### Step 1: Refactor `maybe_spawn_minimonitor` to support both modes

**File:** `.aitask-scripts/lib/agent_launch_utils.py` (lines 213-297)

Current signature: `maybe_spawn_minimonitor(session: str, window_name: str) -> bool`

**New signature:**
```python
def maybe_spawn_minimonitor(
    session: str,
    window_name: str,
    *,
    window_index: str | None = None,
) -> bool:
```

**Changes:**

1. **Configurable prefix list** — Replace the hard-coded `agent-` prefix check (line 222) with a configurable list. Read `tmux.minimonitor.companion_window_prefixes` from `project_config.yaml`, defaulting to `["agent-", "create-"]`. Check: `if not any(window_name.startswith(p) for p in companion_prefixes): return False`.

2. **Support `window_index` parameter** — When `window_index` is provided (existing-window case), skip the name→index lookup (lines 249-264) and use the index directly. The caller passes the window index from `TmuxLaunchConfig.window` plus the window name looked up from tmux.

3. **TUI exclusion check** — Read `tui_window_names` from `tmux.monitor.tui_window_names` config (already available in `project_config.yaml`), defaulting to `DEFAULT_TUI_NAMES`. Add check: if the window name is a known TUI name or starts with `"brainstorm-"`, return False. This is harmless for agent-* windows (never named after TUIs) and essential for the existing-window case where `ait create` might be split into a board/monitor window.

4. **Pane-count guard** — After the existing monitor/minimonitor process check (lines 268-280), count panes. If there are already 3+ panes in the window, return False. This prevents overcrowding when `ait create` is split into a window that already has multiple panes. (For new windows, pane count is 1, so this check passes.)

**Resulting logic flow:**
```
auto_spawn enabled?                    → no: return False
window name matches companion prefix?  → no: return False
window name is a TUI name?             → yes: return False
window index resolved?                 → no: return False
monitor/minimonitor already in window? → yes: return False
3+ panes already?                      → yes: return False
→ spawn minimonitor
```

### Step 2: Add helper to look up window name from index

**File:** `.aitask-scripts/lib/agent_launch_utils.py`

Add a small helper used by callers that have a window index but need the name for the companion call:

```python
def _lookup_window_name(session: str, window_index: str) -> str | None:
    """Look up a tmux window name from its index."""
    try:
        result = subprocess.run(
            ["tmux", "list-windows", "-t", session,
             "-F", "#{window_index}:#{window_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.strip().splitlines():
            if ":" in line:
                idx, name = line.split(":", 1)
                if idx == window_index:
                    return name
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None
```

### Step 3: Add companion spawn in `tui_switcher.py`

**File:** `.aitask-scripts/lib/tui_switcher.py`, `action_shortcut_create()` (lines 413-424)

Mirror the pattern from `action_shortcut_explore()` (lines 394-411). Add after the `tmux new-window` Popen:

```python
from agent_launch_utils import maybe_spawn_minimonitor
maybe_spawn_minimonitor(self._session, "create-task")
```

This is always a new-window case (tui_switcher always creates new windows).

### Step 4: Add companion spawn in board's `action_create_task`

**File:** `.aitask-scripts/board/aitask_board.py`, `on_create_result` callback (lines 3869-3877)

Handle BOTH new-window and existing-window cases:

```python
def on_create_result(create_result):
    if create_result == "run":
        self._run_create_in_terminal()
    elif isinstance(create_result, TmuxLaunchConfig):
        _, err = launch_in_tmux(screen.full_command, create_result)
        if err:
            self.notify(err, severity="error")
        elif create_result.new_window:
            maybe_spawn_minimonitor(create_result.session, create_result.window)
        else:
            # Existing window: look up name, pass index
            from agent_launch_utils import _lookup_window_name
            win_name = _lookup_window_name(create_result.session, create_result.window)
            if win_name:
                maybe_spawn_minimonitor(
                    create_result.session, win_name,
                    window_index=create_result.window,
                )
    self.manager.load_tasks()
    self.refresh_board()
```

`maybe_spawn_minimonitor` is already imported at line 16.

### Step 5: Add companion spawn in codebrowser's `action_create_task`

**File:** `.aitask-scripts/codebrowser/codebrowser_app.py`, `on_result` callback (lines 1230-1237)

**Important:** The codebrowser defaults to splitting `ait create` into the codebrowser's own window (`default_tmux_window=self._tmux_window` at line 1227). Since `codebrowser` is a TUI, the companion should NOT spawn in that default case. The TUI exclusion check in `maybe_spawn_minimonitor` handles this automatically — when the window name is `"codebrowser"`, it matches `tui_window_names` and returns False.

Handle both cases (companion spawns only when the user explicitly chooses a new window or a non-TUI existing window):

```python
def on_result(result):
    if result == "run":
        self._run_create_from_selection(ref_arg)
    elif isinstance(result, TmuxLaunchConfig):
        _, err = launch_in_tmux(screen.full_command, result)
        if err:
            self.notify(err, severity="error")
        elif result.new_window:
            maybe_spawn_minimonitor(result.session, result.window)
        else:
            # Existing window: look up name; TUI exclusion in
            # maybe_spawn_minimonitor prevents companion in
            # codebrowser/board/monitor windows.
            from agent_launch_utils import _lookup_window_name
            win_name = _lookup_window_name(result.session, result.window)
            if win_name:
                maybe_spawn_minimonitor(
                    result.session, win_name,
                    window_index=result.window,
                )
```

`maybe_spawn_minimonitor` is already imported at line 30.

### No changes needed

- **minimonitor_app.py**: `_check_auto_close()` is window-agnostic — when `ait create` exits, minimonitor detects no remaining panes and auto-closes. Works for both new-window and existing-window cases.
- **tmux_monitor.py / classify_pane**: `create-task` should remain classified as OTHER (not TUI, not AGENT). It's a transient process, not a persistent TUI.
- **project_config.yaml**: No changes needed to ship. The defaults (`companion_window_prefixes: ["agent-", "create-"]`) are sensible. Users can customize via `tmux.minimonitor.companion_window_prefixes`.

## Verification

1. **New window from board**: press `n` → create task → verify minimonitor companion appears → exit `ait create` → verify minimonitor auto-closes
2. **New window from tui_switcher**: press `w` then `c` → verify same behavior
3. **New window from codebrowser**: create-task action → verify companion appears with `create-<filename>` window name
4. **Existing window — regular shell**: split `ait create` into a plain shell window → verify companion spawns
5. **Existing window — codebrowser default**: from codebrowser, create task using default split (into codebrowser window) → verify NO companion spawns (codebrowser is a TUI)
6. **Existing window — other TUI**: split `ait create` into board/monitor window → verify NO companion spawns (TUI exclusion)
7. **Existing window — already has monitor**: split `ait create` into agent window with minimonitor → verify NO companion spawns (monitor detection)
8. **Existing window — crowded**: split `ait create` into window with 3+ panes → verify NO companion spawns (pane-count guard)
9. **Auto-despawn**: in all cases where companion spawned, exit `ait create` → verify minimonitor auto-closes

## Step 9 (Post-Implementation)
Archive task, push, handle issues per workflow.
