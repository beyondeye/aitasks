---
priority: high
effort: low
depends: []
issue_type: bug
status: Done
labels: [ui, codebrowser]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-24 21:33
updated_at: 2026-03-24 21:43
completed_at: 2026-03-24 21:43
---

## Problem

In the codebrowser TUI history screen, the "load more" pseudo item at the bottom of the task list is **not shown the first time** the history screen is opened (pressing `h`), but **appears correctly on subsequent entries** (h → back → h again).

## Root Cause

Race condition between `HistoryTaskList.on_mount()` and `_load_chunk()` in the dynamic mount path.

**First-time entry (no cached data):** `_on_data_loaded()` in `history_screen.py` dynamically mounts `HistoryLeftPane`, then immediately calls `left.set_data()` → `HistoryTaskList.set_index()` → `_load_chunk()` which sets `ind.display = True`. However, Textual defers `on_mount()` handlers, so `HistoryTaskList.on_mount()` fires **after** `_load_chunk()` and resets `ind.display = False`.

**Second-time entry (cached data):** Widgets are yielded in `compose()`, so all `on_mount()` handlers fire **before** `_populate_and_restore()` → `set_data()` → `_load_chunk()`. The correct order is preserved: hide first, then show if needed.

## Fix

In `.aitask-scripts/codebrowser/history_list.py`:

1. **Add `display: none;`** to `_LoadMoreIndicator`'s `DEFAULT_CSS` so the indicator starts hidden without relying on `on_mount()`
2. **Remove the `on_mount()` method** from `HistoryTaskList` (lines 210-211) since `_load_chunk()` already correctly manages the indicator's display state on every call

`_load_chunk()` sets `ind.display = True` when there are more items and `ind.display = False` when there are none — this is sufficient to control visibility without `on_mount()`.

## Files

- `.aitask-scripts/codebrowser/history_list.py` — `_LoadMoreIndicator` CSS + `HistoryTaskList.on_mount()`
