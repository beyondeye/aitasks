---
Task: t465_2_navigate_to_history_for_current_task.md
Parent Task: aitasks/t465_launch_qa_from_codebrowser.md
Sibling Tasks: aitasks/t465/t465_1_*.md, aitasks/t465/t465_3_*.md, aitasks/t465/t465_4_*.md
Archived Sibling Plans: aiplans/archived/p465/p465_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Add "open in history" shortcut from main codebrowser screen

## Step 1: Add navigate_to_task_id parameter to HistoryScreen

File: `.aitask-scripts/codebrowser/history_screen.py`

Add `navigate_to_task_id: Optional[str] = None` parameter to `__init__()` (after `restore_task_id`). Store as `self._navigate_to_task_id`.

## Step 2: Handle navigate_to_task_id in _populate_and_restore()

File: `.aitask-scripts/codebrowser/history_screen.py`, `_populate_and_restore()` method

After the existing restore logic (after `detail.set_context()` and the `restore_task_id` block), add:

```python
# Navigate to specific task if requested (takes priority over restore)
if self._navigate_to_task_id:
    detail.show_task(self._navigate_to_task_id, is_explicit_browse=True)
```

This should go AFTER the `restore_task_id` block so it overrides it.

## Step 3: Handle navigate_to_task_id in _on_index_chunk() (first chunk)

File: `.aitask-scripts/codebrowser/history_screen.py`, `_on_index_chunk()` method

In the first-chunk path (inside `if self._task_index is None:`), after `detail.set_context(self._project_root, index, platform)`, add the same navigate logic:

```python
if self._navigate_to_task_id:
    detail.show_task(self._navigate_to_task_id, is_explicit_browse=True)
```

## Step 4: Add H noop binding to HistoryScreen

File: `.aitask-scripts/codebrowser/history_screen.py`, BINDINGS list

Add to the noop overrides section:
```python
Binding("H", "noop", show=False),
```

## Step 5: Add binding and action to CodeBrowserApp

File: `.aitask-scripts/codebrowser/codebrowser_app.py`

Add to BINDINGS (after the `h` binding):
```python
Binding("H", "history_for_task", "History for task"),
```

Add method:
```python
def action_history_for_task(self) -> None:
    """Open history screen navigated to the current annotation's task."""
    if self._project_root is None:
        return
    try:
        detail = self.query_one("#detail_pane", DetailPane)
    except Exception:
        return
    task_id = detail._current_task_id
    if not task_id:
        self.notify("No task selected in detail pane", severity="warning")
        return
    from history_screen import HistoryScreen
    screen = HistoryScreen(
        self._project_root,
        cached_index=self._history_index,
        cached_platform=self._history_platform,
        navigate_to_task_id=task_id,
        restore_chunks=self._history_loaded_chunks,
        restore_labels=self._history_active_labels,
    )
    self.push_screen(screen, callback=self._on_history_dismiss)
```

## Verification

- Open annotated file, enable detail pane (`d`), navigate to annotated line, press `H` → history opens showing that task
- Press `H` with no task → notification "No task selected in detail pane"
- Press `H` in history screen → noop

## Step 9: Post-Implementation

Follow standard archival workflow.
