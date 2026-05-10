---
priority: high
effort: low
depends: []
issue_type: bug
status: Done
labels: [codebrowser, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-10 15:07
updated_at: 2026-05-10 16:45
completed_at: 2026-05-10 16:45
---

## Symptom

Pressing `h` in codebrowser to open the history screen crashes the app with:

```
NoMatches: No nodes match '#history_list' on HistoryLeftPane(id='history_left')
```

The crash bubbles up as `textual.worker.WorkerFailed: Worker raised exception`.

## Reproduction

Headless Textual run:

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
asyncio.run(run())
"
```

## Root Cause

`.aitask-scripts/codebrowser/history_screen.py:192-204`, in `_on_index_chunk()` (the first-chunk branch reached when no cached index exists):

```python
container = Horizontal()
left = HistoryLeftPane(self._project_root, id="history_left")
detail = HistoryDetailPane(project_root=self._project_root, id="history_detail")
self.mount(container, before=self.query_one(Footer))
container.mount(left)
container.mount(detail)
# Populate with data
left.set_data(index)            # <-- crash
detail.set_context(self._project_root, index, platform)
if self._navigate_to_task_id:
    detail.show_task(self._navigate_to_task_id, is_explicit_browse=True)
```

`Container.mount()` returns an `AwaitMount` and is not awaited here. The `HistoryLeftPane`'s `compose()` (which yields `HistoryTaskList(id="history_list")` at `history_list.py:380`) has not run yet, so `left.set_data(index)` → `self.query_one("#history_list", HistoryTaskList)` raises `NoMatches`. Same applies to `detail.set_context(...)` and the `navigate_to_task_id` follow-up.

This is reached only when the app has no cached `_history_index` (typical first open). The cached path (`_populate_and_restore`, `history_screen.py:117-151`) is unaffected because compose at `history_screen.py:104-115` yields the panes inline so children are mounted before `on_mount` fires. `_on_reload_chunk` (history_screen.py:216) is also unaffected — left/detail already exist when refresh is invoked.

`_on_index_chunk` runs on the main loop via `call_from_thread` from the `@work(thread=True)` worker `_load_data` (line 162-166), so it is a regular sync method and cannot `await` the AwaitMount values directly.

## Fix Approach

Defer the populate calls until after the mount completes. Two viable patterns:

1. **`call_after_refresh`** — replace the synchronous calls with:
   ```python
   self.call_after_refresh(left.set_data, index)
   self.call_after_refresh(detail.set_context, self._project_root, index, platform)
   if self._navigate_to_task_id:
       self.call_after_refresh(detail.show_task, self._navigate_to_task_id, True)
   ```

2. **Convert to async** — make `_on_index_chunk` `async` and `await` each `mount(...)`, then call `set_data` / `set_context`. Requires `call_from_thread` to handle coroutine targets (it does in current Textual).

Pattern 1 is the smaller change. Verify `_on_reload_chunk` first-chunk branch (line 228-254) is unaffected (left/detail are queried from already-mounted DOM there).

## Acceptance

- Pressing `h` in codebrowser opens the history screen without crash, both with and without a cached index.
- Subsequent chunks (progressive loading) still update the visible list.
- `r` (refresh) inside the history screen still works.
- `H` (open history navigated to a specific task at cursor) still works on first open and on cached-open.
