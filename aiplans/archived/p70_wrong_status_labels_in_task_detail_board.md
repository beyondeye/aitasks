---
Task: t70_wrong_status_labels_in_task_detail_board.md
Worktree: (working on current branch)
Branch: main
Base branch: main
---

## Context

The task detail screen in `aitask_board.py` shows incorrect status options when cycling with left/right arrows. It currently has `["Ready", "In Progress", "Done"]`, but `"In Progress"` is not a valid status. The valid statuses from `aitask_update.sh` are: `Ready`, `Editing`, `Implementing`, `Postponed`, `Done`.

Additionally, `Editing` and `Postponed` are missing entirely from the cycle options.

## Fix

**File:** `aitask_board/aitask_board.py` (line 818)

Change:
```python
yield CycleField("Status", ["Ready", "In Progress", "Done"],
```
To:
```python
yield CycleField("Status", ["Ready", "Editing", "Implementing", "Postponed", "Done"],
```

This aligns the UI with the actual valid statuses used by `aitask_update.sh`.

## Verification

- The `aitask_update.sh` script's help text, interactive mode, and batch validation all agree on the same 5 statuses — no discrepancy there.
- After the fix, run the board (`python aitask_board/aitask_board.py`), select a task, and verify that left/right arrows on the Status field cycle through: Ready → Editing → Implementing → Postponed → Done.

## Final Implementation Notes
- **Actual work done:** Replaced the 3-element status list `["Ready", "In Progress", "Done"]` with the full 5-element list `["Ready", "Editing", "Implementing", "Postponed", "Done"]` matching `aitask_update.sh`.
- **Deviations from plan:** None — straightforward single-line fix.
- **Issues encountered:** None.
- **Key decisions:** Used the exact same status values and order as defined in `aitask_update.sh` (help text, interactive mode, and batch validation all agree).
