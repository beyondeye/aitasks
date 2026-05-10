---
Task: t761_fix_codebrowser_history_screen_crash_at_open.md
Base branch: main
plan_verified: []
---

## Context

The codebrowser history screen crashes when opened for the first time (no cached index). The traceback is:

```
NoMatches: No nodes match '#history_list' on HistoryLeftPane(id='history_left')
textual.worker.WorkerFailed: Worker raised exception: NoMatches(...)
```

Reproduced headlessly: launch `CodeBrowserApp` and press `h`.

## Root Cause

`.aitask-scripts/codebrowser/history_screen.py:176-214`, in `_on_index_chunk()`'s first-chunk branch (no cached index):

```python
container = Horizontal()
left = HistoryLeftPane(self._project_root, id="history_left")
detail = HistoryDetailPane(project_root=self._project_root, id="history_detail")
self.mount(container, before=self.query_one(Footer))   # AwaitMount, not awaited
container.mount(left)                                   # AwaitMount, not awaited
container.mount(detail)                                 # AwaitMount, not awaited
left.set_data(index)                                    # crash — left's compose hasn't run
detail.set_context(self._project_root, index, platform)
if self._navigate_to_task_id:
    detail.show_task(self._navigate_to_task_id, is_explicit_browse=True)
```

`Container.mount()` is async — it returns an `AwaitMount` and is not awaited here. The child `HistoryTaskList(id="history_list")` (yielded by `HistoryLeftPane.compose()` at `history_list.py:380`) hasn't been composed yet when `left.set_data(index)` calls `query_one("#history_list", HistoryTaskList)` (`history_list.py:386`) → `NoMatches`.

`_on_index_chunk` runs on the main loop via `app.call_from_thread()` from the `@work(thread=True)` worker `_load_data` (line 162-166), so it is currently a regular sync method.

The cached-index path (`_populate_and_restore`, line 117-151) is unaffected because compose at line 104-115 yields the panes inline so the children are mounted before `on_mount` fires. `_on_reload_chunk` (line 216) is also unaffected — it queries existing left/detail widgets that are already mounted.

## Fix

Convert `_on_index_chunk` to `async` and `await` the mounts before populating data. Textual's `App.call_from_thread()` supports coroutine callables. This is a one-method change.

**File:** `.aitask-scripts/codebrowser/history_screen.py`

Change `_on_index_chunk` (line 176) from sync to async, and await each mount:

```python
async def _on_index_chunk(self, index, platform) -> None:
    # Always cache on app (even if screen dismissed, so re-open is fast)
    self.app._history_index = index
    self.app._history_platform = platform
    # Guard: skip UI updates if screen was dismissed while worker ran
    if not self.is_mounted:
        return
    if self._task_index is None:
        # First chunk: mount the UI
        self._task_index = index
        self._platform_info = platform
        # Remove loading indicator
        try:
            self.query_one("#history_loading").remove()
        except Exception:
            pass
        # Mount the actual content
        container = Horizontal()
        left = HistoryLeftPane(self._project_root, id="history_left")
        detail = HistoryDetailPane(project_root=self._project_root, id="history_detail")
        await self.mount(container, before=self.query_one(Footer))
        await container.mount(left)
        await container.mount(detail)
        # Populate with data — safe now that compose() of left/detail has run
        left.set_data(index)
        detail.set_context(self._project_root, index, platform)
        # Navigate to specific task if requested
        if self._navigate_to_task_id:
            detail.show_task(self._navigate_to_task_id, is_explicit_browse=True)
    else:
        # Subsequent chunks: update existing UI progressively (unchanged)
        self._task_index = index
        try:
            left = self.query_one("#history_left", HistoryLeftPane)
            left.update_index(index)
            detail = self.query_one("#history_detail", HistoryDetailPane)
            detail._task_index = index
        except Exception:
            pass
```

The caller (`_load_data`, line 162-166) uses `self.app.call_from_thread(self._on_index_chunk, index_chunk, platform)` — `call_from_thread` already handles coroutine targets by scheduling them on the main loop, so no change is needed there.

`_on_reload_chunk` (line 216) does not mount new widgets and works against existing left/detail. Leave unchanged.

## Verification

1. **Headless reproduction (regression check):**
   ```bash
   python3 -c "
   import os, sys, asyncio
   from pathlib import Path
   os.environ['TERM']='xterm-256color'
   sys.path.insert(0, '.aitask-scripts/codebrowser')
   sys.path.insert(0, '.aitask-scripts/lib')
   from codebrowser_app import CodeBrowserApp
   async def run():
       app = CodeBrowserApp()
       async with app.run_test(headless=True, size=(150, 50)) as pilot:
           await pilot.pause(1.0)
           await pilot.press('h')
           await pilot.pause(3.0)
           # Should now have HistoryScreen on stack with no exception raised
           assert any(type(s).__name__ == 'HistoryScreen' for s in app.screen_stack)
           print('OK: history screen opened without crash')
   asyncio.run(run())
   "
   ```

2. **Interactive verification (user runs):**
   - `ait codebrowser` → press `h` → history screen opens, lists archived tasks. Press `escape` to return.
   - Press `h` again (cached path) → should still open instantly.
   - Inside history, press `r` (refresh) → should reload without crash.
   - In codebrowser main view, press `H` (open history navigated to task at cursor) — should open and select the right task.

## Step 9 — Post-Implementation

Standard archival via `aitask_archive.sh 761`. No worktree, no migration concerns, no cross-script touchpoints (single Python file).
