---
Task: t350_bug_in_child_sorting_in_board.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Plan

1. Update child sorting in `TaskManager.get_child_tasks_for_parent()` to use
   numeric ordering by child index instead of plain filename sorting.
2. Keep sorting robust for unexpected filename patterns by falling back to
   filename-based ordering.
3. Verify behavior by checking that expanded parent tasks list children as
   `1,2,3,...,10,11` for two-digit child IDs.
4. Complete Step 9 after implementation: archive task with `aitask_archive.sh`
   and push task-data updates.

## Final Implementation Notes

- **Actual work done:** Replaced lexicographic child-task sorting with numeric child-index sorting in `TaskManager.get_child_tasks_for_parent()`.
- **Deviations from plan:** No major deviations; implementation stayed scoped to a single function.
- **Issues encountered:** None during implementation; verification used `python -m py_compile` as a fast syntax check.
- **Key decisions:** Added a safe fallback path that keeps filename ordering for unexpected child filename formats.
