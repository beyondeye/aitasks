---
Task: t68_commit_changes_labels.md
Worktree: N/A (current branch)
Branch: main
Base branch: main
---

## Context

When `aitask_create.sh` creates a task with a new label not in `labels.txt`, it adds the label to `aitasks/metadata/labels.txt` but the git commit only includes the new task file. The `labels.txt` update is lost until someone manually commits it.

## Plan

### Fix: Include labels.txt in git commits

Always `git add "$LABELS_FILE"` alongside the task file in each commit location. If labels.txt is unchanged, `git add` is a no-op and the commit is unaffected.

### Changes in `aiscripts/aitask_create.sh`

Added `git add "$LABELS_FILE" 2>/dev/null || true` in all 5 commit locations:

1. **`finalize_draft()` — child task (line ~478):** Draft finalization for child tasks
2. **`finalize_draft()` — parent task (line ~536):** Draft finalization for parent tasks
3. **`commit_task()` — interactive mode (line ~1091):** Interactive mode commit
4. **`run_batch_mode()` — child task (line ~1201):** Batch mode child task
5. **`run_batch_mode()` — parent task (line ~1228):** Batch mode parent task

## Final Implementation Notes

- **Actual work done:** Added `git add "$LABELS_FILE" 2>/dev/null || true` before every `git commit` in the script
- **Deviations from plan:** Initially identified only 3 commit locations (interactive + 2 batch). During testing, discovered 2 more in the `finalize_draft()` function (the draft→finalize workflow used by interactive mode). Total: 5 locations.
- **Issues encountered:** User tested with a new task (t222) which used the draft finalization path, revealing the missing locations
- **Key decisions:** Used unconditional `git add` with error suppression — if labels.txt is unchanged, `git add` is a no-op; if it doesn't exist, the `2>/dev/null || true` guard silently skips it
