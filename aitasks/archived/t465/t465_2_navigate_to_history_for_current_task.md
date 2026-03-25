---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-25 12:57
updated_at: 2026-03-25 15:02
completed_at: 2026-03-25 15:02
---

## Context

The codebrowser TUI has bidirectional navigation between its main screen and history screen, but only in one direction: from history you can open a file in the main screen (via affected files). The reverse is missing — from the main screen, when viewing an annotated line with a task in the detail pane, there is no way to jump to that task in the history screen.

This task adds that reverse navigation via the `H` (capital H) keyboard shortcut.

## Key Files to Modify

- `.aitask-scripts/codebrowser/codebrowser_app.py` — Add `Binding("H", "history_for_task", "History for task")` to BINDINGS (after line 132), add `action_history_for_task()` method
- `.aitask-scripts/codebrowser/history_screen.py` — Add `navigate_to_task_id` parameter to `__init__()` (line 44), handle in `_populate_and_restore()` and `_on_index_chunk()`, add `Binding("H", "noop", show=False)` to noop overrides

## Reference Files for Patterns

- `codebrowser_app.py` lines 549-564: `action_toggle_history()` — shows how HistoryScreen is created and pushed, with cached state. The new method follows the same pattern but passes `navigate_to_task_id` instead of `restore_task_id`
- `codebrowser_app.py` line 60: `detail_pane.py` — `DetailPane._current_task_id` holds the task ID shown from annotations
- `history_screen.py` lines 85-110: `_populate_and_restore()` — existing restore logic; `navigate_to_task_id` handling goes after `detail.set_context()`
- `history_screen.py` lines 127-162: `_on_index_chunk()` — first-chunk path where `navigate_to_task_id` must also be handled

## Implementation Plan

1. Add `navigate_to_task_id: Optional[str] = None` parameter to `HistoryScreen.__init__()`, store as `self._navigate_to_task_id`
2. In `_populate_and_restore()`: after `detail.set_context(...)` call and existing restore logic, add: if `self._navigate_to_task_id` is set, call `detail.show_task(self._navigate_to_task_id, is_explicit_browse=True)`. This takes priority over `restore_task_id`.
3. In `_on_index_chunk()` (first chunk path, after `detail.set_context()`): same logic — if `self._navigate_to_task_id` is set, show the task in detail pane
4. Add `Binding("H", "noop", show=False)` to HistoryScreen.BINDINGS to suppress the shortcut while in history
5. Add `Binding("H", "history_for_task", "History for task")` to CodeBrowserApp.BINDINGS
6. Add `action_history_for_task()` method to CodeBrowserApp:
   - Check `self._project_root` is not None
   - Get `detail._current_task_id` from DetailPane
   - If no task_id, show notification "No task selected in detail pane" and return
   - Create HistoryScreen with `navigate_to_task_id=task_id`, passing cached_index and cached_platform
   - Push screen with `_on_history_dismiss` callback

## Edge Cases
- If task_id from annotations is not in the completed task index (active task), history detail shows "Task tXXX not found in index" — acceptable behavior
- If detail pane is hidden or no annotation is on cursor, show notification

## Verification Steps

- Open a file with annotations, enable detail pane (`d`), move cursor to annotated line, press `H` — history should open showing that task
- Press `H` with no task selected — should show "No task selected" notification
- Press `H` while history screen is open — should be a noop (suppressed)
