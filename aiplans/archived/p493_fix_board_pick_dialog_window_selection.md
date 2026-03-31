---
Task: t493_fix_board_pick_dialog_window_selection.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The board TUI's "pick" dialog (`AgentCommandScreen`) has two bugs when selecting an existing tmux window to launch a code agent:

1. Arrow keys don't work in the window selection dropdown — only mouse works
2. Selecting any existing window (not "New window") silently fails to spawn the agent

## Plan

### Fix 1: Arrow keys in Select dropdown (agent_command_screen.py)

**Root cause:** When the Textual `Select` dropdown overlay opens, focus moves to `SelectOverlay` (an `OptionList` subclass). The `on_key` handler at line 488 checks `isinstance(focused, (Input, Select))` but `SelectOverlay` is not a subclass of `Select`, so the early return doesn't trigger. The method continues and may interfere with key propagation.

**Changes in `.aitask-scripts/lib/agent_command_screen.py`:**

1. Add import at top (after line 37):
   ```python
   from textual.widgets._select import SelectOverlay
   ```

2. Update `on_key` method (line 490) — add `SelectOverlay` to the isinstance check:
   ```python
   if isinstance(focused, (Input, Select, SelectOverlay)):
       return  # Let input/select/overlay handle the key
   ```

### Fix 2: Invalid tmux target for existing windows (agent_command_screen.py + agent_launch_utils.py)

**Root cause:** Window option values are stored as `f"{idx}:{name}"` (e.g., `"0:main"`). When passed to `launch_in_tmux`, the tmux target becomes `session:0:main` — invalid syntax. Tmux expects `session:window_index`.

**Changes in `.aitask-scripts/lib/agent_command_screen.py`:**

1. Line 329 — Change window option value to store only the index:
   ```python
   # Before:
   (f"{idx}: {name}", f"{idx}:{name}") for idx, name in windows
   # After:
   (f"{idx}: {name}", f"{idx}") for idx, name in windows
   ```
   Display label keeps `"0: main"`, value becomes just `"0"`.

2. The "last used" tracking (lines 335-344, 452) will automatically work since it compares option values, which will now be indices.

**Changes in `.aitask-scripts/lib/agent_launch_utils.py`:**

3. Surface tmux errors to the caller. Change `launch_in_tmux` return type to include error info. Update lines 135-139 and 149-153:
   ```python
   # For new-window (line 137-139):
   if proc.returncode != 0:
       stderr = proc.stderr.read().decode() if proc.stderr else ""
       return proc, f"tmux new-window failed: {stderr}"
   return proc, None

   # For split-window (line 151-153):
   if proc.returncode != 0:
       stderr = proc.stderr.read().decode() if proc.stderr else ""
       return proc, f"tmux split-window failed: {stderr}"
   return proc, None
   ```
   Also update the new-session path (line 123-127) to return `(proc, None)`.

**Changes in `.aitask-scripts/board/aitask_board.py`:**

4. Update the two `on_pick_result` callbacks (lines 3235-3236 and 3299-3300) to check for errors:
   ```python
   elif isinstance(pick_result, TmuxLaunchConfig):
       _, err = launch_in_tmux(screen.full_command, pick_result)
       if err:
           self.notify(err, severity="error")
   ```

## Files to Modify

- `.aitask-scripts/lib/agent_command_screen.py` — Import SelectOverlay, fix isinstance check, fix window value format
- `.aitask-scripts/lib/agent_launch_utils.py` — Return error info from `launch_in_tmux`
- `.aitask-scripts/board/aitask_board.py` — Surface tmux errors via notify

## Final Implementation Notes

- **Actual work done:** Fixed all 4 issues: (1) arrow keys in Select dropdown via `check_action` disabling priority bindings when `SelectOverlay` is focused + `on_key` SelectOverlay check, (2) invalid tmux target by storing only window index as value, (3) tmux error surfacing via `app.notify()` at all 5 call sites, (4) always default to "New window", (5) auto-switch to target window after split-window
- **Deviations from plan:** The arrow key fix required changes in `check_action` (in `aitask_board.py`) rather than just `on_key` (in `agent_command_screen.py`), because the App-level priority bindings for up/down were capturing events before child widgets. Two additional fixes were requested during review: always default to "New window" and auto-switch to existing window after split.
- **Issues encountered:** Initial arrow key fix (adding `SelectOverlay` to `on_key` isinstance check) was insufficient because `KanbanApp.BINDINGS` has `priority=True` on up/down, which captures events before any widget handler. The real fix was in `check_action` returning `False` when a `SelectOverlay` is focused, following the existing pattern for `TuiSwitcherOverlay`.
- **Key decisions:** Window option values changed from `"idx:name"` to `"idx"` only — display label unchanged. All 5 callers of `launch_in_tmux` (3 in board, 2 in codebrowser) updated for new return type.
