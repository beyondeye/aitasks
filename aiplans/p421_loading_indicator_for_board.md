---
Task: t421_loading_indicator_for_board.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Add LoadingIndicator for async board operations (t421)

## Context

The `ait board` TUI (`aitask_board.py`, ~3941 lines, Textual 8.1.x) runs several subprocess operations (sync, commit, lock/unlock, archive, delete) with no visual feedback while they execute. Users only see a notification after completion. This task adds a `LoadingIndicator` overlay during these operations.

**Key problem**: Most operations run `subprocess.run()` synchronously on the main thread, blocking the event loop so a loading widget can't animate. Even `_run_sync` (which uses `@work(exclusive=True)`) calls `subprocess.run` inside an `async def` without `thread=True`, blocking the event loop.

**Solution**: Create a reusable `LoadingOverlay` ModalScreen with Textual's built-in `LoadingIndicator` widget, and convert blocking operations to `@work(thread=True)` workers so the overlay can animate.

## File to modify

`.aitask-scripts/board/aitask_board.py`

## Implementation Steps

### Step 1: Add import and LoadingOverlay class

**Import** (line 19): Add `LoadingIndicator` to the textual.widgets import.

**New class** (insert after `SyncConflictScreen` at line 2418, before `ColumnSelectItem`): A simple `LoadingOverlay(ModalScreen)` with no BINDINGS (user can't dismiss it), containing a `Container` with a `Label` (message) and `LoadingIndicator`.

### Step 2: Add CSS rules

Add to `KanbanApp.CSS` (before closing `"""`):
- `#loading_dialog`: 40 wide, 7 tall, centered, themed border
- `#loading_message`: centered text
- `LoadingIndicator`: 3 tall

### Step 3: Convert `_run_sync` (lines 3253-3301)

Two callers: `action_sync_remote` (manual) and `_auto_refresh_tick` (timer). Overlay only for manual sync.

- `action_sync_remote`: Push `LoadingOverlay("Syncing with remote...")`
- `_run_sync`: `@work(exclusive=True, thread=True)`, `def` (not async). Add `show_overlay: bool = False` param.
- Wrap UI calls with `call_from_thread()`. Pop overlay only when `show_overlay=True`.

### Step 4: Convert `_git_commit_tasks` (lines 3912-3937)

Split into wrapper (captures focused card, pushes overlay) + `_do_git_commit_tasks` (`@work(thread=True)`, pops overlay in finally).

### Step 5: Convert lock/unlock in TaskDetailScreen

**Lock** (lines 1988-2011): Extract subprocess into `_do_lock` `@work(thread=True)`. Push overlay in `on_email` callback.

**Unlock** (lines 2014-2069): Extract into `_do_unlock` `@work(thread=True)`. Explicit overlay pop at each branch (before `ResetTaskConfirmScreen` or `self.dismiss`).

### Step 6: Convert archive and delete

**`_execute_archive`** (lines 3835-3853): Split into wrapper + `_do_archive` worker.

**`_execute_delete`** (lines 3855-3910): Split into wrapper + `_do_delete` worker.

## Key Design Decisions

1. **LoadingOverlay as ModalScreen**: Blocks user interaction, configurable message
2. **`@work(thread=True)`**: Frees event loop for animation. `call_from_thread()` for all UI ops
3. **Capture UI state before worker starts**: e.g., focused card in `_git_commit_tasks` wrapper
4. **Explicit overlay pop vs. finally**: `finally` for simple ops; explicit per-branch for unlock

## Out of scope

- Interactive sync / Edit / Pick / Create: suspend the app
- Revert: too fast
- Refresh git status / lock map: background noise
