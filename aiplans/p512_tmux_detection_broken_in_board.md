---
Task: t512_tmux_detection_broken_in_board.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix tmux detection in board TUI dialogs

## Context

When running `ait board` inside a tmux session, the task create and task pick dialogs always show the "Direct" tab selected by default instead of the "Tmux" tab. The root cause is that `AgentCommandScreen.on_mount()` only checks the `prefer_tmux` config setting (which is `false`) — it never checks the `TMUX` environment variable to detect if already running inside tmux.

## Fix

**File:** `.aitask-scripts/lib/agent_command_screen.py`

### Step 1: Add `os` import (line 29)

Add `import os` alongside the existing `import sys`.

### Step 2: Update tmux tab pre-selection logic (lines 244-249)

Change the condition from:
```python
if self._tmux_defaults.get("prefer_tmux"):
```
to:
```python
if self._tmux_defaults.get("prefer_tmux") or os.environ.get("TMUX"):
```

This pre-selects the tmux tab when either:
- `prefer_tmux: true` is set in config, **OR**
- The board is running inside an active tmux session (`TMUX` env var is set)

This matches the pattern used elsewhere in the codebase (e.g., `tui_switcher.py:462`, `agent_launch_utils.py:149`).

## Verification

1. Run `ait board` inside a tmux session → open task create or task pick dialog → tmux tab should be selected by default
2. Run `ait board` outside tmux → direct tab should remain default
3. With `prefer_tmux: true` in config → tmux tab selected regardless of environment

## Final Implementation Notes
- **Actual work done:** Added `os` import and extended the tmux tab pre-selection condition in `AgentCommandScreen.on_mount()` to also check the `TMUX` environment variable
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** None
- **Key decisions:** Used `or os.environ.get("TMUX")` to match the existing pattern used in `tui_switcher.py` and `agent_launch_utils.py`
