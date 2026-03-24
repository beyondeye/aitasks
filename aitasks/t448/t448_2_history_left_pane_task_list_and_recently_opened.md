---
priority: medium
effort: medium
depends: [t448_1]
issue_type: feature
status: Implementing
labels: [aitask_board, task-archive]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-24 08:59
updated_at: 2026-03-24 10:24
---

## Context

This is child task 2 of t448 (Completed Tasks History View in Codebrowser). It creates the left pane of the history screen with two sections: a persistent "recently opened" list and the main chronological task list with chunked loading.

Depends on t448_1 which provides the data layer (`history_data.py` with `CompletedTask` dataclass, `load_task_index()`, and `load_completed_tasks_chunk()`).

## Key Files to Create
- `.aitask-scripts/codebrowser/history_list.py`

## Reference Files
- `.aitask-scripts/board/aitask_board.py` — `TaskCard` (lines 562-712) for rendering patterns, color-coded type indicators
- `.aitask-scripts/codebrowser/codebrowser_app.py` — existing Textual app patterns
- `.aitask-scripts/codebrowser/history_data.py` — data layer from t448_1

## Implementation

### Section 1: Recently Opened List (top, collapsible)

Create `RecentlyOpenedList(VerticalScroll)`:
- Shows last 10 tasks the user explicitly browsed, most recent at top
- **Persistent storage**: JSON file at `.aitask-history/recently_opened.json` in the project root
  - Format: `[{"task_id": "t219", "timestamp": "2026-03-24T10:30:00"}, ...]`
  - Load on screen init, save on each update
  - Create `.aitask-history/` dir if it does not exist
- Provides `add_to_history(task_id)` method — adds entry, deduplicates (move to top if already present), trims to 10
- Header: "Recently Opened (N)" with collapse toggle
- Same row format as the main task list (see below)

### Section 2: All Completed Tasks (main list)

Create `HistoryTaskList(VerticalScroll)` with `HistoryTaskItem(Static)` entries:

**Row format for each task:**
```
t219  rename_aitaskpickremote  [refactor]  2026-02-23  ui, backend, +1
```
- Task number (accent color, bold)
- Abbreviated task name (truncated to fit)
- Issue type badge (color-coded — reuse color mapping from board's TaskCard)
- Commit date (muted)
- First 3 labels, with `+N` suffix if more than 3 (e.g., `label1, label2, label3, +2`)
- Parent tasks show `[+N children]` indicator after the name

**Behavior:**
- `can_focus = True` on each `HistoryTaskItem`
- Keyboard: Up/Down to move focus between items, Enter to select
- Mouse: Click to select
- Posts `TaskSelected(CompletedTask)` Textual message on selection
- **This message must be handled by the parent screen to update the "recently opened" list** (the list widget itself provides the `add_to_history` method but does not call it — the screen wires this)

**Chunked loading:**
- On init, call `load_completed_tasks_chunk(index, 0, 10)` to load first 10
- Render a `LoadMoreButton(Button)` at the bottom: "Load more (N remaining)"
- On button press, load next chunk and append items
- Button disappears when `has_more` is False
- Show total count in header: "Completed Tasks (N total)"

### Container Layout

Both sections live in a single `VerticalScroll` container:
```python
with VerticalScroll(id="history_left_pane"):
    yield Static("Recently Opened (N)", id="recent_header")
    yield RecentlyOpenedList(...)
    yield Static("Completed Tasks (N total)", id="history_header")
    yield HistoryTaskList(...)
```

## Verification

1. Create a minimal test Textual app that instantiates the left pane with mock data
2. Verify tasks render in correct format with all metadata
3. Verify chunked loading: initially 10 items, "Load more" loads next 10
4. Verify recently opened persistence: add items, restart TUI, verify list persists
5. Verify keyboard navigation and selection messages
