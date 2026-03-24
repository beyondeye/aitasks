---
Task: t448_2_history_left_pane_task_list_and_recently_opened.md
Parent Task: aitasks/t448_archived_tasks_in_board.md
Sibling Tasks: aitasks/t448/t448_1_*.md, aitasks/t448/t448_3_*.md
Archived Sibling Plans: aiplans/archived/p448/p448_*_*.md
Worktree: (none)
Branch: main
Base branch: main
---

# Plan: History left pane — task list + recently opened

## Step 1: Create `history_list.py`

File: `.aitask-scripts/codebrowser/history_list.py`

### HistoryTaskItem(Static)

A focusable static widget representing one task in the list.

```python
class HistoryTaskItem(Static):
    can_focus = True

    def __init__(self, task: CompletedTask, **kwargs):
        super().__init__(**kwargs)
        self.task = task

    def render(self):
        # Format: t219  rename_aitask...  [refactor]  2026-02-23  ui, backend, +1
        task_num = f"[bold #7aa2f7]t{self.task.task_id}[/]"
        name = self.task.name[:25]  # truncate
        type_badge = f"[{_type_color(self.task.issue_type)}][{self.task.issue_type}][/]"
        date = self.task.commit_date[:10]  # just date part
        labels = _format_labels(self.task.labels, max_show=3)
        children = _format_children(self.task) if _is_parent(self.task) else ""
        return f"  {task_num}  {name} {children} {type_badge}  [dim]{date}[/]  {labels}"
```

Helper functions:
- `_type_color(issue_type)` — return Rich color for each type (reuse board's color scheme)
- `_format_labels(labels, max_show=3)` — show first 3, append `+N` if more
- `_is_parent(task)` / `_format_children(task)` — check if task has children in the index, show `[+N]`

### HistoryTaskList(VerticalScroll)

The main scrollable list with chunked loading.

```python
class TaskSelected(Message):
    def __init__(self, task: CompletedTask):
        super().__init__()
        self.task = task

class HistoryTaskList(VerticalScroll):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._index = []
        self._offset = 0
        self._chunk_size = 10

    def set_index(self, index: list):
        self._index = index
        self._offset = 0
        self._load_chunk()
        self._update_header()

    def _load_chunk(self):
        chunk, has_more = load_completed_tasks_chunk(self._index, self._offset, self._chunk_size)
        for task in chunk:
            item = HistoryTaskItem(task)
            self.mount(item, before=self._load_more_btn if has_more else None)
        self._offset += len(chunk)
        # Update or remove load more button
        if has_more:
            remaining = len(self._index) - self._offset
            self._load_more_btn.update(f"Load more ({remaining} remaining)")
        else:
            self._load_more_btn.remove()
```

### RecentlyOpenedList(VerticalScroll)

Persistent list of recently browsed tasks.

```python
HISTORY_FILE = ".aitask-history/recently_opened.json"
MAX_RECENT = 10

class RecentlyOpenedList(VerticalScroll):
    def __init__(self, project_root: Path, task_index: list, **kwargs):
        super().__init__(**kwargs)
        self._project_root = project_root
        self._task_index = task_index
        self._history = self._load_history()

    def _load_history(self) -> list:
        path = self._project_root / HISTORY_FILE
        if path.exists():
            return json.loads(path.read_text())[:MAX_RECENT]
        return []

    def _save_history(self):
        path = self._project_root / HISTORY_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._history, indent=2))

    def add_to_history(self, task_id: str):
        # Remove if already present (move to top)
        self._history = [h for h in self._history if h["task_id"] != task_id]
        self._history.insert(0, {"task_id": task_id, "timestamp": datetime.now().isoformat()})
        self._history = self._history[:MAX_RECENT]
        self._save_history()
        self._refresh_display()
```

### HistoryLeftPane(Container)

Combines both sections:

```python
class HistoryLeftPane(Container):
    def compose(self):
        yield Static("Recently Opened", id="recent_header", classes="section-header")
        yield RecentlyOpenedList(self._project_root, self._task_index, id="recent_list")
        yield Static("Completed Tasks", id="history_header", classes="section-header")
        yield HistoryTaskList(id="history_list")
```

## Step 2: Add `.aitask-history/` to `.gitignore`

Ensure `.aitask-history/` is in the project's `.gitignore` (it's user-local state).

## Verification

1. Import module and verify no syntax errors
2. Mock task data, verify rendering format
3. Verify chunked loading: 10 items initially, "Load more" works
4. Verify recently opened: add items, save, reload, verify persistence
5. Verify keyboard navigation between items

## Step 9: Post-Implementation

Archive child task, update plan, push.
