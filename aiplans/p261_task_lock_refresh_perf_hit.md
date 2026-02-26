---
Task: t261_task_lock_refresh_perf_hit.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix Board Refresh Performance + Move-to-Top/Bottom Shortcuts

## Context

After introducing lock status checking in the board TUI, every `refresh_board()` call invokes `refresh_lock_map()` which runs `./aiscripts/aitask_lock.sh --list`. This performs a `git fetch origin aitask-locks` network round-trip on **every** refresh. Since `refresh_board()` is called from 20 different code paths (task movement, close detail, create task, column reorder, etc.), the board feels sluggish for basic operations that have nothing to do with locks.

**Root cause:** Lock refresh is coupled to board refresh. Most board operations don't change lock state and don't need to re-fetch locks.

## Approach

### Part 1: Decouple lock refresh from board refresh

Add a `refresh_locks` parameter to `refresh_board()` (default `False`). Only fetch lock status when explicitly requested.

**File:** `aiscripts/board/aitask_board.py`

#### Step 1: Modify `refresh_board()` signature

```python
def refresh_board(self, refocus_filename: str = "", refresh_locks: bool = False):
    self.manager.refresh_git_status()
    if refresh_locks:
        self.manager.refresh_lock_map()
    # ... rest unchanged
```

#### Step 2: Update call sites that NEED lock refresh

These are the only call sites that should pass `refresh_locks=True`:

| Line | Location | Why needs locks |
|------|----------|-----------------|
| 2255 | `on_mount()` | Initial board load — show current lock state |
| 2298 | `action_refresh_board()` | Manual "r" key — user expects fresh data |
| 2541 | `_run_sync()` | After sync fetches remote data, good time to update locks |
| 2563 | `_run_interactive_sync()` | Same as sync |
| 2464 | `check_edit()` callback | After lock/unlock dismiss from detail screen |

For `check_edit()` (line 2448), add special handling for lock/unlock results:
```python
def check_edit(result):
    if result == "edit":
        self.run_editor(focused.task_data.filepath)
    elif result == "pick":
        self.run_aitask_pick(focused.task_data.filename)
    elif result == "delete":
        # ... existing delete logic
        return
    # Refresh board — include lock refresh for lock/unlock operations
    needs_locks = result in ("locked", "unlocked")
    self.refresh_board(refocus_filename=focused.task_data.filename, refresh_locks=needs_locks)
```

#### Step 3: All other call sites stay with default `refresh_locks=False`

The remaining ~15 call sites (task movement, column reorder, editor return, task creation, settings, etc.) keep using the default `False` — they show cached lock data which is fine.

### Part 2: Add Ctrl+Up / Ctrl+Down for move-to-top/bottom

**File:** `aiscripts/board/aitask_board.py`

#### Step 4: Add key bindings

Add to `BINDINGS` list (after existing shift+up/down):
```python
Binding("ctrl+up", "move_task_top", "Task Top"),
Binding("ctrl+down", "move_task_bottom", "Task Btm"),
```

#### Step 5: Add action methods

```python
def action_move_task_top(self):
    self._move_task_to_extreme(-1)

def action_move_task_bottom(self):
    self._move_task_to_extreme(1)

def _move_task_to_extreme(self, direction):
    """Move focused task to top (direction=-1) or bottom (direction=1) of its column."""
    focused = self._focused_card()
    if not focused or focused.is_child:
        return
    filename = focused.task_data.filename
    col_id = focused.task_data.board_col
    tasks = self.manager.get_column_tasks(col_id)
    if len(tasks) <= 1:
        return
    try:
        current_idx = next(i for i, t in enumerate(tasks) if t.filename == filename)
    except StopIteration:
        return
    # Already at extreme?
    if direction == -1 and current_idx == 0:
        return
    if direction == 1 and current_idx == len(tasks) - 1:
        return
    # Set boardidx to be before first or after last task
    if direction == -1:
        focused.task_data.board_idx = tasks[0].board_idx - 10
    else:
        focused.task_data.board_idx = tasks[-1].board_idx + 10
    focused.task_data.reload_and_save_board_fields()
    self.manager.normalize_indices(col_id)
    self.refresh_board(refocus_filename=filename)
```

#### Step 6: Update `check_action()` to hide for child cards

Add the new actions to the existing child-card check:
```python
elif action in ("move_task_right", "move_task_left", "move_task_up", "move_task_down",
                "move_task_top", "move_task_bottom"):
```

### Part 3: Update board documentation

#### Step 7: Update `website/content/docs/board/reference.md`

Add the new shortcuts to the "Task Operations" table (after `Shift+Down` row):

```markdown
| `Ctrl+Up` | Move task to top of column | Board (parent cards only) |
| `Ctrl+Down` | Move task to bottom of column | Board (parent cards only) |
```

#### Step 8: Update `website/content/docs/board/how-to.md`

In the task reordering how-to section (around line 20), add a note about the new shortcuts after the existing Shift+Up/Down instructions:

```markdown
3. Press **Ctrl+Up** to jump the task to the top of the column, or **Ctrl+Down** to jump it to the bottom
```

## Verification

1. Run `python -c "import aiscripts.board.aitask_board"` or launch the board to check for syntax errors
2. Test board operations: move task between columns (shift+left/right), move up/down (shift+up/down) — should feel instant (no network delay)
3. Press "r" to manually refresh — lock indicators should update
4. Test Ctrl+Up: moves selected task to top of column
5. Test Ctrl+Down: moves selected task to bottom of column
6. Verify lock indicators still show on task cards (from cached data)
7. Open detail screen, lock a task, close — lock indicator should appear immediately

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned — decoupled lock refresh from board refresh by adding `refresh_locks` parameter (default False), and added Ctrl+Up/Ctrl+Down shortcuts for move-to-top/bottom of column. Updated board documentation.
- **Deviations from plan:** None. All 8 steps executed as designed.
- **Issues encountered:** None. Python syntax check passed on first try.
- **Key decisions:** Made Ctrl+Up/Down bindings `show=False` to keep the footer bar uncluttered (advanced users will discover them via docs or command palette). Only 5 out of 20 `refresh_board()` call sites need lock refresh (mount, manual refresh, sync×2, lock/unlock dismiss).
