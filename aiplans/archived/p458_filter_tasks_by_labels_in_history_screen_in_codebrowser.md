## Context

The history screen in the codebrowser TUI shows all completed tasks in reverse chronological order but has no filtering. With 400+ archived tasks, finding tasks by label requires scrolling. This adds multi-select label filtering with a modal dialog, progressive index loading for scalability, and state persistence.

## Plan

### Architecture Decisions

1. **Data-layer filtering**: Filter the full task index into a filtered index, then chunk from that. Counts, "load more remaining", and pagination all work automatically.

2. **Progressive index loading**: Instead of loading the entire index before showing UI, load in chunks of 200 asynchronously. Each chunk triggers a UI refresh and filtered index rebuild. User can interact immediately with partial data.

### Files Changed

1. **`history_data.py`**: Refactored into `_build_commit_map`, `_merge_chunk`, `load_task_index_progressive` generator (200-task chunks). Original `load_task_index` preserved for backward compat.
2. **`history_label_filter.py`** (new): `load_labels`, `compute_label_counts`, `filter_index_by_labels`, `LabelFilterItem` widget, `LabelFilterModal` (multi-select, fuzzy search, keyboard shortcuts)
3. **`history_list.py`**: `HistoryTaskList` gains `_full_index`, `_active_labels`, `apply_label_filter()`, `update_index()`, chunk size 10→20. `HistoryLeftPane` gains filter status, no-match message.
4. **`history_screen.py`**: Progressive loading via `_on_index_chunk` with `is_mounted` guard. `l` keybinding for label filter. State save/restore.
5. **`codebrowser_app.py`**: `_history_active_labels` state.

## Final Implementation Notes
- **Actual work done:** All planned features implemented. Two bugs found and fixed during testing:
  1. `push_screen` is on App, not Screen — fixed to `self.app.push_screen()`
  2. Rich markup `[` brackets in checkbox render caused MarkupError — fixed with `\[` escaping
- **Deviations from plan:** Added keyboard shortcuts `o` for OK, `r` for Reset (not in original plan). Added keybinding helper text line. Made Up arrow from first label item return focus to search input.
- **Issues encountered:** Input widget captures key events preventing arrow/Enter navigation on label items. Fixed by intercepting Down at modal level when Input is focused, and handling Up on first item to return to Input.
- **Key decisions:** `o`/`r` shortcuts are suppressed when the search Input has focus to avoid interfering with typing.
