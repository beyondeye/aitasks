---
Task: t93_wrong_script_name_refs_for_creating_in_board.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

The aitask board Python script's 'n' keyboard shortcut (which creates a new task by spawning a terminal running `aitask_create.sh`) is broken. After refactoring, the bash scripts were moved into `aiscripts/`, but the board script still references the old path `./aitask_create.sh` instead of `./aiscripts/aitask_create.sh`.

## Fix

**File:** `aiscripts/board/aitask_board.py` — line 1436

Change:
```python
subprocess.Popen([terminal, "--", "./aitask_create.sh"])
```

To:
```python
subprocess.Popen([terminal, "--", "./aiscripts/aitask_create.sh"])
```

This is consistent with the board's assumption that CWD is the project root (evidenced by `TASKS_DIR = Path("aitasks")` on line 23).

## Verification

1. Launch the board: `./aiscripts/aitask_board.sh`
2. Press 'n' — a terminal should open running the task creation script

## Final Implementation Notes
- **Actual work done:** Changed the script path in `action_create_task()` from `./aitask_create.sh` to `./aiscripts/aitask_create.sh` on line 1436 of `aiscripts/board/aitask_board.py`
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** None
- **Key decisions:** Used relative path from project root (consistent with existing `TASKS_DIR = Path("aitasks")` pattern) rather than constructing an absolute path from `__file__`
