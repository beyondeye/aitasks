---
Task: t487_kill_agent_from_monitor_tui.md
Branch: main
Base branch: main
---

## Implementation Plan

### 1. Add `kill_pane()` to `TmuxMonitor` (`tmux_monitor.py`)

Add method after `switch_to_pane()`. Runs `tmux kill-pane -t <pane_id>`, cleans up internal caches on success. Same subprocess pattern as existing methods.

### 2. Add `KillConfirmDialog(ModalScreen)` to `monitor_app.py`

Confirmation dialog showing:
- Red `$error` border (destructive action visual cue)
- Window name/index, pane index
- Task ID + title + priority/status (if resolved from TaskInfoCache)
- Active/Idle status with duration
- Process command + PID
- Last 15 lines of window content preview
- Kill / Cancel buttons

Follows `SessionRenameDialog` pattern (buttons + `dismiss(bool)`) with rich content like `TaskDetailDialog`.

### 3. Add keybinding and action to `MonitorApp`

- `Binding("k", "kill_pane", "Kill")` in BINDINGS
- `action_kill_pane()` — gets focused pane, resolves task info, opens dialog
- `_on_kill_confirmed()` callback — kills pane, clears focus, triggers refresh

Zone safety handled by existing architecture: preview zone forwards all keys to tmux.

## Final Implementation Notes

- **Actual work done:** Implemented kill agent feature as planned, plus ANSI preview rendering improvements
- **Files changed:** `tmux_monitor.py` (added `kill_pane()` method + `-e` flag for ANSI capture), `monitor_app.py` (added `KillConfirmDialog`, keybinding `k`, action/callback, plus `_ansi_to_rich_text()` helper for proper ANSI rendering in preview)
- **Deviations from plan:** Additional work on ANSI rendering in preview pane — the `-e` flag on `tmux capture-pane` was added (user request) to capture ANSI escape sequences, requiring a helper function to inject dark backgrounds into ANSI codes before Rich parsing
- **Key decisions:**
  - Dark preview background (`#1a1a1a`) is hard-coded because we're rendering actual tmux terminal content (always dark), not themed UI
  - ANSI processing injects dark bg at line starts and after SGR resets to ensure consistent dark background in the preview
  - Kill uses `tmux kill-pane` (not SIGKILL) for clean tmux-level termination
  - Monitor's own pane is excluded via `TMUX_PANE` env var, cannot be self-killed
