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

## Final Implementation Notes

- **Actual work done:** Created `history_screen.py` with HistoryScreen composing left pane + detail pane, integrated into CodeBrowserApp with `h` keybinding. Also fixed a pre-existing bug in `history_detail.py` (DuplicateIds crash) and added comprehensive state preservation for re-opening.
- **Deviations from plan:**
  - **No cached screen instance:** Textual cannot reliably re-push a dismissed Screen instance. Instead, a new HistoryScreen is created each time, with loaded data (task index, platform info) cached on the CodeBrowserApp. Re-opens are instant because cached data is passed to the new screen's constructor.
  - **State preservation:** Added `restore_task_id`, `restore_chunks`, `restore_showing_plan`, `restore_scroll_y` parameters so that the detail pane shows the same task, the list scroll position is maintained, and the plan/task toggle state persists across opens.
  - **Screen-level bindings:** Added `v` binding at screen level (delegating to detail pane) to ensure plan/task toggle works regardless of focus. Also added no-op overrides for codebrowser bindings (`r`, `t`, `g`, `e`, `d`, `D`) to hide them from the footer in the history screen.
  - **`call_from_thread`:** Must be `self.app.call_from_thread()` not `self.call_from_thread()` — Screen doesn't have this method; only App does.
- **Issues encountered:**
  - `call_from_thread` AttributeError on Screen — fixed by using `self.app.call_from_thread()`.
  - Textual cannot re-push the same dismissed Screen instance — redesigned to create fresh instances with cached data.
  - DuplicateIds crash in `history_detail.py` — `child.remove()` loop is async, old `body_markdown` ID still present when new one mounts. Fixed by switching to `remove_children()` and using class (`body-markdown`) instead of ID.
  - `show_task()` resets `_showing_plan = False` — fixed by setting the restored plan state AFTER calling `show_task()`, since the render is deferred.
  - Scroll restoration needs deferred execution — used `set_timer(0.1)` to restore after layout completes.
- **Key decisions:** Caching loaded data on the App instance (`_history_index`, `_history_platform`, `_history_last_task_id`, etc.) enables both fast re-opens and state preservation while avoiding the re-push problem. The deferred scroll restore uses 100ms timer which is simple and reliable.
- **Notes for sibling tasks:**
  - `_open_file_by_path()` on CodeBrowserApp is a stub — t448_5 should implement it to open files in the codebrowser view after navigating from history.
  - Plan files inside old.tar.gz archives return "No plan file found" when toggling with `v` — this is a data retrieval issue in `history_data.py` that should be investigated separately (not a UI bug).
  - The `action_toggle_history` uses lazy import (`from history_screen import HistoryScreen`) to avoid circular imports and speed up app startup.

## Step 9: Post-Implementation

Archive child task, update plan, push.
