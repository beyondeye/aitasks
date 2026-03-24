---
Task: t448_3_history_detail_widget.md
Parent Task: aitasks/t448_archived_tasks_in_board.md
Sibling Tasks: aitasks/t448/t448_1_*.md, aitasks/t448/t448_2_*.md
Archived Sibling Plans: aiplans/archived/p448/p448_*_*.md
Worktree: (none)
Branch: main
Base branch: main
---

# Plan: History detail widget

## Step 1: Create `history_detail.py`

File: `.aitask-scripts/codebrowser/history_detail.py`

### Custom Messages

```python
class NavigateToFile(Message):
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

class HistoryBrowseEvent(Message):
    def __init__(self, task_id: str):
        super().__init__()
        self.task_id = task_id
```

### Field Widgets

Follow `aitask_board.py` patterns (ReadOnlyField at line 858, IssueField at line 1113):

```python
class MetadataField(Static):
    """Read-only metadata field with focus support."""
    can_focus = True
    # Render: "Label: value" with muted label, normal value
    # Focus: accent left border highlight

class CommitLinkField(Static):
    """Clickable commit link that opens browser."""
    can_focus = True
    # Render: "[hash_short] message (date)"
    # Enter: webbrowser.open(platform_commit_url)

class ChildTaskField(Static):
    """Clickable child task link."""
    can_focus = True
    # Render: "t{id} - {name} [{status}]"
    # Enter: post HistoryBrowseEvent, push onto nav stack

class SiblingCountField(Static):
    """Shows sibling count, opens picker on Enter."""
    can_focus = True
    # Render: "N siblings" or "No siblings"
    # Enter or 's': open SiblingPickerModal

class AffectedFileField(Static):
    """Clickable file path that navigates to codebrowser."""
    can_focus = True
    # Render: file path with file icon
    # Enter: post NavigateToFile message
```

### HistoryDetailPane(VerticalScroll)

```python
BINDINGS = [
    Binding("v", "toggle_view", "Toggle task/plan"),
    Binding("s", "open_siblings", "Siblings"),
]

class HistoryDetailPane(VerticalScroll):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._nav_stack: list[str] = []
        self._task_index = []
        self._platform_info = None
        self._showing_plan = False
        self._task_content_cache = {}
        self._plan_content_cache = {}

    def show_task(self, task_id: str, is_explicit_browse: bool = True):
        """Load and display task details. Pushes onto nav stack."""
        self._nav_stack.append(task_id)
        if is_explicit_browse:
            self.post_message(HistoryBrowseEvent(task_id))
        self._showing_plan = False
        self._render_task(task_id)

    def go_back(self):
        """Pop nav stack, show previous task (not an explicit browse)."""
        if len(self._nav_stack) > 1:
            self._nav_stack.pop()
            self._render_task(self._nav_stack[-1])

    def _render_task(self, task_id: str):
        """Clear and rebuild all sections for the given task."""
        self.remove_children()
        # Load data (commits, metadata, content) via @work worker
        # Build sections: back button, metadata, commits, children/siblings, files, body
```

### Section rendering details

**Back button:** Only mount when `len(self._nav_stack) > 1`. Show previous task ID.

**Metadata block:** Mount `MetadataField` for each: priority, effort, issue_type, labels, commit_date.

**Commits:** Call `find_commits_for_task()` in worker, mount `CommitLinkField` for each.

**Children:** If task is a parent (no `_` in task_id), call `find_child_tasks()`, mount `ChildTaskField` for each.

**Siblings:** If task is a child (has `_` in task_id), mount `SiblingCountField` with count from `find_sibling_tasks()`.

**Affected files:** From commit data, mount `AffectedFileField` for each unique file across all commits.

**Body:** Mount Textual `Markdown` widget. Handle `on(Markdown.LinkClicked)` to open URLs in browser.

**Plan toggle (`v`):** Switch between task content and plan content. Load plan lazily via `load_plan_content()`. Cache both.

## Step 2: Create SiblingPickerModal

```python
class SiblingPickerModal(ModalScreen):
    """Modal dialog for browsing sibling tasks with fuzzy search."""

    def __init__(self, siblings: list[CompletedTask]):
        super().__init__()
        self._siblings = siblings
        self._filtered = siblings

    def compose(self):
        with Container(id="sibling_picker_dialog"):
            yield Input(placeholder="Search siblings...", id="sibling_search")
            yield VerticalScroll(id="sibling_list")
            # Populate with SiblingPickerItem for each sibling

    def on_input_changed(self, event):
        # Filter siblings by name (case-insensitive substring)
        query = event.value.lower()
        self._filtered = [s for s in self._siblings if query in s.name.lower()]
        self._refresh_list()

    # Enter on selected item: self.dismiss(selected_task_id)
    # Escape: self.dismiss(None)
```

CSS for the modal:
```css
#sibling_picker_dialog {
    width: 60%;
    max-height: 50%;
    background: $surface;
    border: thick $accent;
    padding: 1 2;
}
```

## Verification

1. Render with mock CompletedTask data — all sections display
2. Commit link opens browser on Enter
3. `v` toggles between task and plan content
4. Navigation: click child → back button appears → click back → returns
5. Sibling picker: Enter on "N siblings" opens modal, search filters, selection works
6. Affected file Enter posts NavigateToFile message

## Step 9: Post-Implementation

Archive child task, update plan, push.
