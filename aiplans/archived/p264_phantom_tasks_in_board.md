---
Task: t264_phantom_tasks_in_board.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Fix phantom tasks in board TUI (t264)

## Context

Task t261 was archived (moved to `aitasks/archived/`) but still shows on the board as a phantom. The root cause: when `normalize_indices()` ran during t262 setup, it called `reload_and_save_board_fields()` on the archived t261. The `load()` failed (FileNotFoundError), the exception handler stored the error message, then `save()` recreated the file as a stub containing only `boardidx: 20` and the error string.

## Changes

### 1. `Task.load()` returns boolean (`aitask_board.py:114`)

Add `return True` at end of try block, `return False` in exception handler. Backward-compatible — existing callers that ignore the return value are unaffected.

### 2. Guard `reload_and_save_board_fields()` (`aitask_board.py:145`) — PRIMARY FIX

After saving `boardcol`/`boardidx`, call `self.load()` and bail out with early `return` if it returns `False`. This prevents recreating deleted/archived files.

### 3. Filter phantom stubs in `load_tasks()` and `load_child_tasks()` (`aitask_board.py:223, 231`)

After constructing a Task, skip it if metadata contains ONLY board keys (`boardcol`, `boardidx`). Uses existing `BOARD_KEYS` constant from `task_yaml.py`. Defense-in-depth for any pre-existing stubs.

### 4. Guard secondary `load()`-then-`save()` callers

- `_remove_dep_from_task()` (line 826): Early return if `load()` fails
- `save_changes()` (line 1599): Show error notification and return if `load()` fails
- `on_reset_confirmed` callback (line 1689): Show error notification and dismiss if `load()` fails

### 5. Delete phantom stub

Remove `aitasks/t261_task_lock_refresh_perf_hit.md` (the corrupted 102-byte file).

## Files to modify

- `aiscripts/board/aitask_board.py` — All code changes (changes 1-4)
- `aitasks/t261_task_lock_refresh_perf_hit.md` — Delete (change 5)

## Verification

- Delete the t261 stub and confirm the board no longer shows it
- Run the board TUI (`./ait board`) and verify normal operation
- Run existing tests: `bash tests/test_*.sh`

## Final Implementation Notes
- **Actual work done:** Implemented all 5 planned changes exactly as specified. The primary fix guards `reload_and_save_board_fields()` against recreating files that no longer exist on disk. Defense-in-depth filtering in `load_tasks()`/`load_child_tasks()` catches any pre-existing stubs. Three secondary callers also guarded.
- **Deviations from plan:** None — all changes implemented as planned.
- **Issues encountered:** None.
- **Key decisions:** Used `set(task.metadata.keys()) <= set(BOARD_KEYS)` as the phantom detection heuristic rather than checking for specific error content, making it robust against any kind of stub file.
