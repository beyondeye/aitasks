---
Task: t455_fix_load_more_indicator_race_in_history_screen.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

In the codebrowser TUI history screen, the "load more" pseudo item at the bottom of the task list is missing on first entry but appears on subsequent entries. This is caused by a race condition between `HistoryTaskList.on_mount()` and `_load_chunk()` in the dynamic mount path.

**First-time entry:** `_on_data_loaded()` dynamically mounts `HistoryLeftPane`, then immediately calls `set_data()` → `_load_chunk()` → sets `ind.display = True`. But Textual defers `on_mount()`, so `HistoryTaskList.on_mount()` fires **after** and resets `ind.display = False`.

**Second-time entry:** Widgets are yielded in `compose()`, so `on_mount()` fires **before** `set_data()` → correct order.

## Plan

### File: `.aitask-scripts/codebrowser/history_list.py`

**Change 1:** Add `display: none;` to `_LoadMoreIndicator`'s `DEFAULT_CSS` (line ~153-168)

**Change 2:** Remove `on_mount()` from `HistoryTaskList` (lines 210-211)

`_load_chunk()` already correctly manages display state on every call (`True` when more items, `False` when none), making `on_mount()` redundant and the source of the race.

## Step 9: Post-Implementation

Archive task t455, push changes.

## Verification

1. Run codebrowser and press `h` — verify "load more" indicator appears on first entry
2. Press `h` to go back, then `h` again — verify indicator still works on re-entry
3. Click/Enter on "load more" — verify it loads more tasks

## Final Implementation Notes
- **Actual work done:** Exactly as planned — added `display: none;` to `_LoadMoreIndicator` DEFAULT_CSS and removed `HistoryTaskList.on_mount()`.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Using CSS `display: none` rather than an alternative approach (e.g., deferring `set_data`) because `_load_chunk()` already manages visibility correctly on every call.
