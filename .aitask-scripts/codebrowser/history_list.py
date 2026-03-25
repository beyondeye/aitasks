"""History left pane widgets: task list with chunked loading and recently opened list."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from history_data import CompletedTask, load_completed_tasks_chunk
from history_label_filter import filter_index_by_labels

# Issue type → Dracula palette color (matching board's PALETTE_COLORS)
_TYPE_COLORS = {
    "bug": "#FF5555",
    "feature": "#50FA7B",
    "refactor": "#8BE9FD",
    "chore": "#6272A4",
    "test": "#FFB86C",
    "documentation": "#F1FA8C",
    "performance": "#FF79C6",
    "style": "#BD93F9",
}
_DEFAULT_TYPE_COLOR = "#6272A4"

HISTORY_FILE = ".aitask-history/recently_opened.json"
MAX_RECENT = 10


def _type_color(issue_type: str) -> str:
    return _TYPE_COLORS.get(issue_type, _DEFAULT_TYPE_COLOR)


def _format_labels(labels: list, max_show: int = 3) -> str:
    if not labels:
        return ""
    shown = labels[:max_show]
    parts = ", ".join(shown)
    if len(labels) > max_show:
        parts += f", +{len(labels) - max_show}"
    return f"[dim]{parts}[/]"


def _compute_child_counts(task_index: list[CompletedTask]) -> dict[str, int]:
    """Build dict of parent_id -> child count from the index."""
    counts: dict[str, int] = {}
    for t in task_index:
        if "_" in t.task_id:
            parent = t.task_id.split("_")[0]
            counts[parent] = counts.get(parent, 0) + 1
    return counts


class TaskSelected(Message):
    """Posted when a task item is selected (Enter or click)."""

    def __init__(self, task: CompletedTask) -> None:
        super().__init__()
        self.task = task


def _focus_neighbor(widget, direction: int) -> None:
    """Move focus to the next (+1) or previous (-1) visible focusable sibling."""
    parent = widget.parent
    if parent is None:
        return
    # Collect all visible focusable children in DOM order
    focusable = [
        w for w in parent.children
        if w.can_focus and w.display and w.styles.display != "none"
    ]
    try:
        idx = focusable.index(widget)
    except ValueError:
        return
    target = idx + direction
    if 0 <= target < len(focusable):
        focusable[target].focus()
        focusable[target].scroll_visible()


class HistoryTaskItem(Static):
    """Focusable row representing one completed task."""

    can_focus = True

    DEFAULT_CSS = """
    HistoryTaskItem {
        height: 2;
        padding: 0 1;
    }
    HistoryTaskItem:focus {
        background: $accent 20%;
    }
    HistoryTaskItem:hover {
        background: $accent 10%;
    }
    """

    def __init__(self, task: CompletedTask, child_count: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.completed_task = task
        self.child_count = child_count

    def render(self) -> str:
        t = self.completed_task
        task_num = f"[bold #7aa2f7]t{t.task_id}[/]"
        # Truncate name to prevent wrapping into line 2
        # Prefix uses ~8 chars (2 indent + tNNN + 2 spaces), leave room for children suffix
        id_len = len(f"t{t.task_id}")
        prefix_len = 2 + id_len + 2  # indent + id + spaces
        children_len = len(f" [+{self.child_count} children]") if self.child_count > 0 else 0
        try:
            avail = self.size.width - prefix_len - children_len - 2  # 2 for padding
        except Exception:
            avail = 30
        avail = max(avail, 10)
        name = t.name.replace("_", " ")
        if len(name) > avail:
            name = name[: avail - 1] + "\u2026"
        children = f" [dim]\\[+{self.child_count} children][/]" if self.child_count > 0 else ""
        color = _type_color(t.issue_type)
        type_badge = f"[{color}]\\[{t.issue_type}][/]" if t.issue_type else ""
        date = f"[dim]{t.commit_date[:10]}[/]" if t.commit_date else ""
        labels = _format_labels(t.labels)
        line1 = f"  {task_num}  {name}{children}"
        line2 = f"      {type_badge}  {date}  {labels}"
        return f"{line1}\n{line2}"

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(TaskSelected(self.completed_task))
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()

    def on_click(self) -> None:
        self.post_message(TaskSelected(self.completed_task))


class _LoadMoreIndicator(Static):
    """Clickable indicator at the bottom of the task list to load the next chunk."""

    can_focus = True

    DEFAULT_CSS = """
    _LoadMoreIndicator {
        display: none;
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface-lighten-1;
        color: $text-muted;
        text-style: italic;
        text-align: center;
    }
    _LoadMoreIndicator:focus {
        background: $accent 20%;
    }
    _LoadMoreIndicator:hover {
        background: $accent 10%;
    }
    """

    class Clicked(Message):
        """Posted when the load more indicator is activated."""

    def on_click(self) -> None:
        self.post_message(self.Clicked())

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Clicked())
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()


class HistoryTaskList(VerticalScroll):
    """Scrollable list of completed tasks with chunked loading."""

    DEFAULT_CSS = """
    HistoryTaskList {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._full_index: list[CompletedTask] = []
        self._index: list[CompletedTask] = []
        self._child_counts: dict[str, int] = {}
        self._offset = 0
        self._chunk_size = 20
        self._has_more = False
        self._active_labels: set[str] = set()

    def compose(self):
        yield _LoadMoreIndicator("", id="load_more_ind")

    def set_index(self, index: list[CompletedTask], child_counts: dict[str, int]) -> None:
        self._full_index = index
        self._child_counts = child_counts
        self._index = filter_index_by_labels(self._full_index, self._active_labels)
        self._offset = 0
        # Remove any previously loaded items
        for item in self.query(HistoryTaskItem):
            item.remove()
        self._load_chunk()

    def apply_label_filter(self, labels: set[str]) -> None:
        """Apply label filter: recompute index, reset display, reload first chunk."""
        self._active_labels = labels
        self._index = filter_index_by_labels(self._full_index, self._active_labels)
        self._offset = 0
        for item in self.query(HistoryTaskItem):
            item.remove()
        self._load_chunk()

    def update_index(self, new_index: list[CompletedTask]) -> None:
        """Progressive update: replace full index and refresh filtered view."""
        self._full_index = new_index
        self._child_counts = _compute_child_counts(new_index)
        new_filtered = filter_index_by_labels(self._full_index, self._active_labels)
        # Only update load-more indicator (items already displayed stay)
        self._index = new_filtered
        if self._has_more or self._offset < len(self._index):
            self._has_more = self._offset < len(self._index)
            ind = self.query_one("#load_more_ind", _LoadMoreIndicator)
            if self._has_more:
                remaining = len(self._index) - self._offset
                ind.update(f"\u25bc Load more ({remaining} remaining) \u25bc")
                ind.display = True
            else:
                ind.display = False

    def _load_chunk(self) -> None:
        chunk, has_more = load_completed_tasks_chunk(self._index, self._offset, self._chunk_size)
        self._has_more = has_more
        ind = self.query_one("#load_more_ind", _LoadMoreIndicator)
        for task in chunk:
            cc = self._child_counts.get(task.task_id, 0)
            item = HistoryTaskItem(task, child_count=cc)
            self.mount(item, before=ind)
        self._offset += len(chunk)
        if has_more:
            remaining = len(self._index) - self._offset
            ind.update(f"▼ Load more ({remaining} remaining) ▼")
            ind.display = True
        else:
            ind.display = False

    def on__load_more_indicator_clicked(self) -> None:
        self._load_chunk()


class RecentlyOpenedList(VerticalScroll):
    """Persistent list of recently browsed tasks."""

    DEFAULT_CSS = """
    RecentlyOpenedList {
        max-height: 12;
    }
    """

    def __init__(self, project_root: Path, task_index: list[CompletedTask], **kwargs) -> None:
        super().__init__(**kwargs)
        self._project_root = project_root
        self._task_index = task_index
        self._index_map: dict[str, CompletedTask] = {}
        self._history: list[dict] = []

    def on_mount(self) -> None:
        self._rebuild_index_map()
        self._history = self._load_history()
        self._refresh_display()

    def set_task_index(self, task_index: list[CompletedTask]) -> None:
        self._task_index = task_index
        self._rebuild_index_map()
        self._history = self._load_history()
        self._refresh_display()

    def _rebuild_index_map(self) -> None:
        self._index_map = {t.task_id: t for t in self._task_index}

    def _load_history(self) -> list[dict]:
        path = self._project_root / HISTORY_FILE
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return data[:MAX_RECENT] if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save_history(self) -> None:
        path = self._project_root / HISTORY_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._history, indent=2), encoding="utf-8")

    def add_to_history(self, task_id: str) -> None:
        """Add a task to the recently opened list (move to top if present)."""
        self._history = [h for h in self._history if h.get("task_id") != task_id]
        self._history.insert(0, {"task_id": task_id, "timestamp": datetime.now().isoformat()})
        self._history = self._history[:MAX_RECENT]
        self._save_history()
        self._refresh_display()

    def _refresh_display(self) -> None:
        for item in self.query(HistoryTaskItem):
            item.remove()
        for entry in self._history:
            tid = entry.get("task_id", "")
            task = self._index_map.get(tid)
            if task is not None:
                self.mount(HistoryTaskItem(task))


class HistoryLeftPane(Container):
    """Left pane combining recently opened and full task list."""

    DEFAULT_CSS = """
    HistoryLeftPane {
        width: 45;
        border-right: thick $primary;
        background: $surface;
    }
    HistoryLeftPane .section-header {
        height: 1;
        background: $surface-lighten-1;
        padding: 0 1;
        text-style: bold;
    }
    HistoryLeftPane #history_header {
        margin-top: 2;
    }
    HistoryLeftPane #label_filter_status {
        height: auto;
        padding: 0 1;
        color: #FFB86C;
        display: none;
    }
    HistoryLeftPane #no_match_msg {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-style: italic;
        display: none;
    }
    """

    def __init__(self, project_root: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._project_root = project_root
        self._task_index: list[CompletedTask] = []

    def compose(self):
        yield Static("Recently Opened (0)", id="recent_header", classes="section-header")
        yield RecentlyOpenedList(self._project_root, [], id="recent_list")
        yield Static("Completed Tasks (0)", id="history_header", classes="section-header")
        yield Static("", id="label_filter_status")
        yield Static("No tasks match selected labels", id="no_match_msg")
        yield HistoryTaskList(id="history_list")

    def set_data(self, task_index: list[CompletedTask]) -> None:
        """Populate both lists after data loading completes."""
        self._task_index = task_index
        child_counts = _compute_child_counts(task_index)
        self.query_one("#history_list", HistoryTaskList).set_index(task_index, child_counts)
        self.query_one("#recent_list", RecentlyOpenedList).set_task_index(task_index)
        self._update_headers()

    def apply_label_filter(self, labels: set[str]) -> None:
        """Apply label filter and update display."""
        task_list = self.query_one("#history_list", HistoryTaskList)
        task_list.apply_label_filter(labels)
        self._update_filter_status(labels)
        self._update_headers()
        # Show/hide no-match message
        no_match = self.query_one("#no_match_msg", Static)
        no_match.display = len(task_list._index) == 0 and bool(labels)

    def update_index(self, new_index: list[CompletedTask]) -> None:
        """Progressive update from chunked loading."""
        self._task_index = new_index
        task_list = self.query_one("#history_list", HistoryTaskList)
        task_list.update_index(new_index)
        self.query_one("#recent_list", RecentlyOpenedList).set_task_index(new_index)
        self._update_headers()

    def _update_filter_status(self, labels: set[str]) -> None:
        status = self.query_one("#label_filter_status", Static)
        if labels:
            labels_str = ", ".join(sorted(labels))
            status.update(f"Filtered: {labels_str}")
            status.display = True
        else:
            status.update("")
            status.display = False

    def _update_headers(self) -> None:
        task_list = self.query_one("#history_list", HistoryTaskList)
        total = len(task_list._full_index)
        filtered = len(task_list._index)
        if task_list._active_labels:
            self.query_one("#history_header", Static).update(
                f"Completed Tasks ({filtered} of {total} total)"
            )
        else:
            self.query_one("#history_header", Static).update(
                f"Completed Tasks ({total} total)"
            )
        recent = self.query_one("#recent_list", RecentlyOpenedList)
        valid_count = sum(
            1 for h in recent._history if h.get("task_id") in recent._index_map
        )
        self.query_one("#recent_header", Static).update(
            f"Recently Opened ({valid_count})"
        )

    def get_recently_opened_list(self) -> RecentlyOpenedList:
        return self.query_one("#recent_list", RecentlyOpenedList)
