---
Task: t506_pick_sibling_directly_from_monitor.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Pick Next Sibling from Monitor TUI (t506)

## Context

When a code agent completes a child task with siblings, the current workflow requires: kill the agent pane in monitor → switch to board TUI → find parent task → pick next sibling. This adds a single `n` keybinding in the monitor TUI that combines all these steps.

## Design

When `n` is pressed on a focused agent pane for a child task:
1. Detect the task ID and check it's a child task with ready siblings
2. Auto-suggest the next sibling (lowest-numbered Ready one)
3. Show a confirmation dialog with 3 options:
   - **"Pick t{parent}_{child}"** — launch agent for the auto-suggested sibling directly
   - **"Choose child"** — launch `aitask-pick {parent}` so the skill handles sibling selection with full dependency/priority info
   - **"Cancel"**
4. If task is Done (or archived — file not found), auto-kill the completed agent pane before launching
5. Launch the new agent in a new tmux window in the same session

## Files Modified

1. **`.aitask-scripts/monitor/monitor_shared.py`** — Added `find_next_sibling()` and `get_parent_id()` to `TaskInfoCache`
2. **`.aitask-scripts/monitor/monitor_app.py`** — Added `NextSiblingDialog`, keybinding `n`, `action_pick_next_sibling`, `_on_next_sibling_result`, import for `agent_launch_utils`, stored `_project_root`

## Final Implementation Notes

- **Actual work done:** Added `n` keybinding to monitor TUI with `NextSiblingDialog` (3 options: pick suggested, choose child via aitask-pick, cancel). Sibling discovery via pure Python filesystem scan in `TaskInfoCache.find_next_sibling()`. Auto-kill of Done/archived agent panes.
- **Deviations from plan:** Added handling for archived child tasks — when a completed child task's file has been moved to `aitasks/archived/`, `get_task_info()` returns None. The action now treats this as "Done" with a fallback title, allowing sibling pick to proceed. In the callback, `not current_info` also triggers auto-kill (archived = done).
- **Issues encountered:** Initial implementation failed for archived tasks because `TaskInfoCache._resolve()` only searches active task directories. Fixed by treating "info not found" as equivalent to "Done" status in both the action method and callback.
- **Key decisions:** "Choose child" option delegates to `aitask-pick {parent}` rather than reimplementing sibling selection logic — the skill handles dependency analysis, priority, and interactive selection better.
