---
Task: t448_4_history_screen_integration_and_keybinding.md
Parent Task: aitasks/t448_archived_tasks_in_board.md
Sibling Tasks: aitasks/t448/t448_2_*.md, aitasks/t448/t448_3_*.md
Archived Sibling Plans: aiplans/archived/p448/p448_*_*.md
Worktree: (none)
Branch: main
Base branch: main
---

# Plan: History screen integration and keybinding

## Step 1: Create `history_screen.py`

File: `.aitask-scripts/codebrowser/history_screen.py`

```python
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, LoadingIndicator
from textual import work

from history_list import HistoryLeftPane, TaskSelected
from history_detail import HistoryDetailPane, NavigateToFile, HistoryBrowseEvent
from history_data import load_task_index, detect_platform_info


class HistoryScreen(Screen):
    BINDINGS = [
        Binding("h", "dismiss_screen", "Back to browser"),
        Binding("escape", "dismiss_screen", "Back to browser"),
        Binding("q", "quit", "Quit"),
        Binding("tab", "toggle_focus", "Toggle Focus"),
    ]

    CSS = """
    #history_left { width: 40; border-right: thick $primary; background: $surface; }
    #history_detail { width: 1fr; background: $surface; }
    #history_loading { width: 100%; height: 100%; content-align: center middle; }
    """

    def __init__(self, project_root, **kwargs):
        super().__init__(**kwargs)
        self._project_root = project_root
        self._task_index = None
        self._platform_info = None
        self._loaded = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        if not self._loaded:
            yield LoadingIndicator(id="history_loading")
        else:
            with Horizontal():
                yield HistoryLeftPane(
                    self._project_root, self._task_index,
                    id="history_left"
                )
                yield HistoryDetailPane(
                    self._task_index, self._platform_info, self._project_root,
                    id="history_detail"
                )
        yield Footer()

    def on_mount(self):
        if not self._loaded:
            self._load_data()

    @work(exclusive=True)
    async def _load_data(self):
        # Run in worker thread
        index = load_task_index(self._project_root)
        platform = detect_platform_info(self._project_root)
        # Back on main thread
        self._task_index = index
        self._platform_info = platform
        self._loaded = True
        # Remove loading indicator and mount the real layout
        loading = self.query_one("#history_loading", LoadingIndicator)
        loading.remove()
        # Mount the actual content
        # (may need to use recompose() or manual mounting)

    def on_task_selected(self, event: TaskSelected):
        detail = self.query_one("#history_detail", HistoryDetailPane)
        detail.show_task(event.task.task_id, is_explicit_browse=True)

    def on_history_browse_event(self, event: HistoryBrowseEvent):
        left = self.query_one("#history_left", HistoryLeftPane)
        left.add_to_recently_opened(event.task_id)

    def on_navigate_to_file(self, event: NavigateToFile):
        self.dismiss(result=event.file_path)

    def action_dismiss_screen(self):
        self.dismiss(result=None)

    def action_toggle_focus(self):
        # Cycle between history_left and history_detail
        current = self.focused
        left = self.query_one("#history_left")
        detail = self.query_one("#history_detail")
        if current and left.is_ancestor_of(current):
            detail.focus()
        else:
            left.focus()
```

## Step 2: Modify `codebrowser_app.py`

File: `.aitask-scripts/codebrowser/codebrowser_app.py`

### Add binding

In `CodeBrowserApp.BINDINGS`, add:
```python
Binding("h", "toggle_history", "History"),
```

### Add instance variable

In `__init__`:
```python
self._history_screen: HistoryScreen | None = None
```

### Add action

```python
def action_toggle_history(self):
    if self._history_screen is None:
        from history_screen import HistoryScreen
        self._history_screen = HistoryScreen(self._project_root)
    self.push_screen(self._history_screen, callback=self._on_history_dismiss)

def _on_history_dismiss(self, result):
    if result is not None:
        self._open_file_by_path(result)  # implemented in t448_5

def _open_file_by_path(self, file_path: str):
    # Stub for t448_5 — just pass for now
    pass
```

## Verification

1. `ait codebrowser` → press `h` → loading indicator → task list appears
2. Select task → detail pane updates
3. `h` or Escape → back to codebrowser
4. `h` again → same history state (cached instance)
5. Tab cycles focus between panes
6. Footer shows correct bindings

## Step 9: Post-Implementation

Archive child task, update plan, push.
