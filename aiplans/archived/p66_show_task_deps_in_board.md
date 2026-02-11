---
Task: t66_show_task_deps_in_board.md
Branch: main (no worktree)
---

## Context

Task t66 requests showing task dependency IDs on the main board screen alongside the existing status line in each task box. Currently, the `depends` field is loaded from task metadata but only displayed in the detail screen — not on the board's task cards.

## Implementation Plan

**File to modify:** `aitask_board/aitask_board.py`

### Change: Add dependency display to `TaskCard.compose()` (lines 327-331)

After the existing status line rendering, add a new line showing unresolved dependency task IDs.

**Logic:**
1. Read `depends` from `self.task_data.metadata`
2. Filter to only show **unresolved** dependencies (tasks that still exist in `task_datas` or `child_task_datas` and are NOT status "Done"). Dependencies that are not found (already archived/completed) are considered resolved and should not be shown.
3. If there are unresolved dependencies, yield a new `Label` with format: `🔗 t47, t12`

**Location:** Insert after line 331 (after the status_parts block), before the child_count block (line 333).

```python
if self.manager:
    deps = meta.get('depends', [])
    if deps:
        unresolved = []
        for d in deps:
            d_str = str(d)
            dep_id = d_str if d_str.startswith('t') else f"t{d_str}"
            dep_task = self.manager.find_task_by_id(dep_id)
            if dep_task and dep_task.metadata.get('status') != 'Done':
                unresolved.append(dep_id)
        if unresolved:
            yield Label(f"🔗 {', '.join(unresolved)}", classes="task-info")
```

This reuses the existing `find_task_by_id()` method (line 182) and the `task-info` CSS class already used by other metadata lines.

### Why filter to unresolved only

- Archived/done tasks should not clutter the board display
- If `find_task_by_id` returns None (task archived and removed from loaded tasks), it's resolved
- If found but status is "Done", it's also resolved

## Post-Review Changes

### Change Request 1 (2026-02-10)
- **Requested by user:** When a task has unresolved dependencies, show "blocked" instead of "Ready" status — since dependencies mean the task cannot be implemented yet
- **Changes made:** Restructured `TaskCard.compose()` to compute unresolved deps first, then use that to override status: show "🚫 blocked" instead of "📋 Ready" when there are unresolved dependencies. The dependency list (🔗 line) is shown below the status line.
- **Files affected:** `aitask_board/aitask_board.py`

## Verification

1. Run the board: `python aitask_board/aitask_board.py`
2. Find a task with `depends` set (e.g., check for tasks with non-empty depends)
3. Verify the dependency line appears below the status line
4. Verify resolved (Done/archived) dependencies are excluded
5. Verify tasks with no dependencies or all-resolved dependencies don't show the line

## Final Implementation Notes
- **Actual work done:** Modified `TaskCard.compose()` in `aitask_board.py` to compute unresolved dependencies before rendering the status line. Tasks with unresolved deps show "🚫 blocked" instead of "📋 Ready", followed by a "🔗 t47, t12" line listing the blocking task IDs.
- **Deviations from plan:** Initial plan only added a dependency list line. After user feedback, the status display was also changed to show "blocked" for tasks with unresolved deps, since those tasks can't be worked on.
- **Issues encountered:** None
- **Key decisions:** Dependencies are considered "resolved" if the task is not found (archived) or has status "Done". Only unresolved dependencies affect the display.
