---
Task: t509_brainstorm_tmux_dedup.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

When launching brainstorm from the board TUI via tmux, pressing `b` always opens a new tmux window — even if a brainstorm session for that task is already running. This creates duplicate windows. The fix: detect existing `brainstorm-{num}` windows and switch to them instead.

## Plan

### 1. Add `find_window_by_name()` to `agent_launch_utils.py`

**File:** `.aitask-scripts/lib/agent_launch_utils.py` (after `get_tmux_windows()`, ~line 108)

Scans all tmux sessions for a window matching the given name. Returns `(session, window_index)` or `None`.

### 2. Add `_launch_brainstorm()` helper to `KanbanApp` in `aitask_board.py`

Extract shared brainstorm launch logic into a helper that both code paths call. Add dedup check at the top: if window exists, switch to it via `tmux select-window`; otherwise show the AgentCommandScreen dialog.

### 3. Update both call sites to use the helper

- Detail screen callback (~line 3343)
- `action_brainstorm_task()` (~line 3453)

### 4. Update import

Add `find_window_by_name` to the existing import from `agent_launch_utils`.

### 5. Disable brainstorm for locked tasks

- Detail screen: button `disabled=self.read_only or is_locked`
- Board shortcut: check `manager.lock_map` and show warning

## Files Modified

- `.aitask-scripts/lib/agent_launch_utils.py` — add `find_window_by_name()`
- `.aitask-scripts/board/aitask_board.py` — add import, add `_launch_brainstorm()` helper, simplify both call sites, disable brainstorm for locked tasks

## Final Implementation Notes
- **Actual work done:** Implemented all planned changes plus an additional fix: disabled brainstorm button/shortcut for locked tasks
- **Deviations from plan:** Added lock guard — brainstorm button in detail screen is disabled when `is_locked`, and the board-level `b` shortcut checks `manager.lock_map` and shows a warning notification
- **Issues encountered:** None
- **Key decisions:** Used `find_window_by_name()` scanning all sessions (not just the default) for robustness
