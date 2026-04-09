---
priority: medium
effort: medium
depends: [t496_1]
issue_type: feature
status: Implementing
labels: [aitask_monitor, aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 09:07
updated_at: 2026-04-09 10:41
---

## Context

This is the core implementation of the mini monitor TUI for t496. It depends on t496_1 (shared module extraction). The mini monitor is a compact Textual TUI designed to run as a narrow side-column split pane alongside code agent windows in tmux. Unlike the full monitor, it has no preview zone — just a compact agent list with idle status.

**UI layout:** A narrow side column (~40 columns wide) showing a compact list of all code agents across the tmux session. Users can quit it with `q` if they don't want it.

## Key Files to Create

- `.aitask-scripts/monitor/minimonitor_app.py` — **NEW** compact TUI app (~350 LOC)
- `.aitask-scripts/aitask_minimonitor.sh` — **NEW** shell launcher

## Key Files to Modify

- `ait` — add `minimonitor` command dispatch
- `aitasks/metadata/project_config.yaml` — add `minimonitor` to `tui_window_names`

## Reference Files for Patterns

- `.aitask-scripts/monitor/monitor_app.py` — full monitor TUI pattern (layout, refresh, actions)
- `.aitask-scripts/monitor/monitor_shared.py` — shared widgets (TaskInfoCache, TaskDetailDialog, KillConfirmDialog) — created by t496_1
- `.aitask-scripts/monitor/tmux_monitor.py` — TmuxMonitor core library, discover_window_panes() — updated by t496_1
- `.aitask-scripts/lib/tui_switcher.py` — TuiSwitcherMixin pattern
- `.aitask-scripts/aitask_monitor.sh` — shell launcher pattern

## Implementation Plan

### 1. Create `minimonitor_app.py`

Path: `.aitask-scripts/monitor/minimonitor_app.py`

**Layout (designed for ~40 column width, no Header/Footer — too bulky):**
```
┌──────────────────────────────────────┐
│ aitasks  3 agents  1 idle            │ ← 1-line session bar (dock: top)
│ ● agent-pick-42              ok      │ ← MiniPaneCard (focusable)
│   Fix login validation               │    (optional task title line)
│ ● agent-pick-99         IDLE 12s     │
│   Add user settings                  │
│ ● agent-qa-47_1             ok       │
│   Auth middleware tests              │
│                                      │
│ j:jump s:switch i:info k:kill q:quit │ ← 1-line key hints (dock: bottom)
└──────────────────────────────────────┘
```

**Key classes:**
- `MiniPaneCard(Static, can_focus=True)` — compact card with `pane_id` attribute
- `MiniMonitorApp(TuiSwitcherMixin, App)` — main app

**MiniMonitorApp design:**
- `current_tui_name = "minimonitor"` (for switcher mixin)
- No zone model (single zone — just the pane list)
- **CRITICAL: Do NOT call `tmux rename-window`** — the minimonitor runs inside an agent's window, renaming would break agent classification
- Auto-close: on each refresh, call `discover_window_panes(own_window_id)`. If no other panes remain (excluding self via `TMUX_PANE`), call `self.exit()`. Add 5-second grace period after mount to avoid startup race.
- Window ID detection on mount: `tmux display-message -p -t $TMUX_PANE '#{window_id}'`

**CSS (narrow-friendly):**
```python
CSS = """
#mini-session-bar {
    dock: top; height: 1;
    background: $primary; color: $text;
    padding: 0 1; text-style: bold;
}
#mini-pane-list { height: 1fr; }
MiniPaneCard { height: auto; padding: 0 1; }
MiniPaneCard:focus { background: $accent; color: $text; }
#mini-key-hints {
    dock: bottom; height: 1;
    background: $surface; color: $text-muted;
    padding: 0 1;
}
"""
```

**Bindings:**
- `j` — TUI switcher (via mixin, show=False)
- `s` — switch to focused pane
- `i` — show task info dialog
- `k` — kill pane (with confirmation)
- `q` — quit minimonitor
- `r` — force refresh
- Up/Down — navigate pane list (handled in `on_key`)

**Constructor:** Same params as MonitorApp minus preview-related ones. Uses TmuxMonitor with session-wide discovery.

**Refresh cycle:** Single-tier (no fast preview timer). Every `refresh_seconds` (default 3s from config):
1. `capture_all()` — session-wide snapshots
2. Auto-close check
3. Rebuild session bar (count agents, idle count)
4. Rebuild pane list (AGENT panes only, sorted by window_index)
5. Restore focus

**Session bar format:** `"{session}  {N} agents{idle_str}"` where idle_str is ` {M} idle` in yellow if M > 0

**Pane list format per agent:**
```
{dot} {window_name}  {status}
  {task_title}
```
- dot: green `●` if active, yellow `●` if idle
- status: `ok` (green) if active, `{N}s` (yellow) if idle
- Task title: optional 2nd line, dim, truncated to ~30 chars

**Actions:** Same logic as full monitor but without preview zone complexity.

**Entrypoint `main()`:**
- CLI args: `--session`, `--interval`
- Config loading: same pattern as monitor_app.py (project_config.yaml)
- Session resolution: CLI > detected > configured > default "aitasks"

### 2. Create `aitask_minimonitor.sh`

Path: `.aitask-scripts/aitask_minimonitor.sh` (make executable)

Exact same pattern as `aitask_monitor.sh`:
- Check python (venv > system), check textual+yaml, check tmux
- `ait_warn_if_incapable_terminal`
- `exec "$PYTHON" "$SCRIPT_DIR/monitor/minimonitor_app.py" "$@"`

### 3. Update `ait` dispatcher

Path: `ait`

- Line ~27 (TUI section help): add `  minimonitor    Compact monitor for tmux agent panes`
- Line ~149 (skip list): add `minimonitor` to the pipe-separated list
- After line ~163 (monitor dispatch): add `minimonitor)  shift; exec "$SCRIPTS_DIR/aitask_minimonitor.sh" "$@" ;;`

### 4. Update project config

Path: `aitasks/metadata/project_config.yaml`

Add `minimonitor` to `tui_window_names` list (after `monitor`).

## Verification Steps

1. `ait minimonitor --help` — shows help without error
2. Inside tmux: `ait minimonitor` — launches compact TUI showing agents
3. Press `q` — minimonitor exits cleanly
4. Press `j` — TUI switcher opens
5. Navigate with up/down, press `i` on an agent — task info dialog shows
6. Press `k` on an agent — kill confirmation shows
7. Narrow terminal (40 cols) — layout renders correctly
