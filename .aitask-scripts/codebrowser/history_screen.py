"""History screen composing left pane + detail pane for browsing completed tasks."""

from pathlib import Path
from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, LoadingIndicator
from textual import work

from history_list import HistoryLeftPane, HistoryTaskList, HistoryTaskItem, TaskSelected
from history_detail import HistoryDetailPane, NavigateToFile, HistoryBrowseEvent
from history_data import load_task_index, detect_platform_info, CompletedTask, PlatformInfo


class HistoryScreen(Screen):
    """Full-screen view for browsing completed task history."""

    BINDINGS = [
        Binding("h", "dismiss_screen", "Back to browser"),
        Binding("escape", "dismiss_screen", "Back to browser"),
        Binding("q", "quit", "Quit"),
        Binding("tab", "toggle_focus", "Toggle Focus"),
        Binding("v", "toggle_view", "Toggle task/plan"),
        # Override codebrowser app bindings to hide them from footer
        Binding("r", "noop", show=False),
        Binding("t", "noop", show=False),
        Binding("g", "noop", show=False),
        Binding("e", "noop", show=False),
        Binding("d", "noop", show=False),
        Binding("D", "noop", show=False),
    ]

    DEFAULT_CSS = """
    HistoryScreen #history_loading { width: 100%; height: 100%; }
    HistoryScreen #history_detail { width: 1fr; }
    """

    def __init__(
        self,
        project_root: Path,
        cached_index: Optional[List[CompletedTask]] = None,
        cached_platform: Optional[PlatformInfo] = None,
        restore_task_id: Optional[str] = None,
        restore_chunks: int = 0,
        restore_showing_plan: bool = False,
        restore_scroll_y: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._project_root = project_root
        self._task_index = cached_index
        self._platform_info = cached_platform
        self._restore_task_id = restore_task_id
        self._restore_chunks = restore_chunks
        self._restore_showing_plan = restore_showing_plan
        self._restore_scroll_y = restore_scroll_y

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        if self._task_index is not None:
            # Data already cached — render content immediately
            with Horizontal():
                yield HistoryLeftPane(self._project_root, id="history_left")
                yield HistoryDetailPane(
                    project_root=self._project_root, id="history_detail"
                )
        else:
            yield LoadingIndicator(id="history_loading")
        yield Footer()

    def on_mount(self) -> None:
        if self._task_index is not None:
            self._populate_and_restore()
        else:
            self._load_data()

    def _populate_and_restore(self) -> None:
        """Populate panes with cached data and restore previous view state."""
        left = self.query_one("#history_left", HistoryLeftPane)
        detail = self.query_one("#history_detail", HistoryDetailPane)
        left.set_data(self._task_index)
        detail.set_context(self._project_root, self._task_index, self._platform_info)
        # Restore additional chunks that were loaded previously
        if self._restore_chunks > 1:
            task_list = left.query_one("#history_list", HistoryTaskList)
            for _ in range(self._restore_chunks - 1):
                if task_list._has_more:
                    task_list._load_chunk()
        # Restore last viewed task in detail pane
        if self._restore_task_id:
            detail.show_task(self._restore_task_id, is_explicit_browse=False)
            # Set plan view state AFTER show_task (which resets it to False).
            # The actual render runs deferred via call_from_thread, so it will
            # read the restored value when it executes on the main thread.
            if self._restore_showing_plan:
                detail._showing_plan = True
        # Defer scroll restoration to after layout completes
        if self._restore_scroll_y > 0:
            self.set_timer(0.1, self._restore_scroll)

    def _restore_scroll(self) -> None:
        """Restore the task list scroll position after layout."""
        try:
            left = self.query_one("#history_left", HistoryLeftPane)
            task_list = left.query_one("#history_list", HistoryTaskList)
            task_list.scroll_y = self._restore_scroll_y
        except Exception:
            pass

    @work(thread=True)
    def _load_data(self) -> None:
        index = load_task_index(self._project_root)
        platform = detect_platform_info(self._project_root)
        self.app.call_from_thread(self._on_data_loaded, index, platform)

    def _on_data_loaded(self, index, platform) -> None:
        self._task_index = index
        self._platform_info = platform
        # Cache on the app for fast re-open next time
        self.app._history_index = index
        self.app._history_platform = platform
        # Remove loading indicator
        try:
            self.query_one("#history_loading").remove()
        except Exception:
            pass
        # Mount the actual content
        container = Horizontal()
        left = HistoryLeftPane(self._project_root, id="history_left")
        detail = HistoryDetailPane(project_root=self._project_root, id="history_detail")
        self.mount(container, before=self.query_one(Footer))
        container.mount(left)
        container.mount(detail)
        # Populate with data
        left.set_data(index)
        detail.set_context(self._project_root, index, platform)

    def _save_state_to_app(self) -> None:
        """Save current view state to the app for restoration on re-open."""
        try:
            detail = self.query_one("#history_detail", HistoryDetailPane)
            if detail._nav_stack:
                self.app._history_last_task_id = detail._nav_stack[-1]
            self.app._history_showing_plan = detail._showing_plan
            left = self.query_one("#history_left", HistoryLeftPane)
            task_list = left.query_one("#history_list", HistoryTaskList)
            # Save scroll position
            self.app._history_scroll_y = int(task_list.scroll_y)
            # Number of chunks loaded = offset / chunk_size (rounded up)
            if task_list._offset > 0:
                chunks = (task_list._offset + task_list._chunk_size - 1) // task_list._chunk_size
                self.app._history_loaded_chunks = chunks
        except Exception:
            pass

    def on_task_selected(self, event: TaskSelected) -> None:
        detail = self.query_one("#history_detail", HistoryDetailPane)
        detail.show_task(event.task.task_id, is_explicit_browse=True)

    def on_history_browse_event(self, event: HistoryBrowseEvent) -> None:
        left = self.query_one("#history_left", HistoryLeftPane)
        left.get_recently_opened_list().add_to_history(event.task_id)

    def on_navigate_to_file(self, event: NavigateToFile) -> None:
        self._save_state_to_app()
        self.dismiss(result=event.file_path)

    def action_dismiss_screen(self) -> None:
        self._save_state_to_app()
        self.dismiss(result=None)

    def action_toggle_view(self) -> None:
        """Delegate plan/task toggle to the detail pane."""
        try:
            detail = self.query_one("#history_detail", HistoryDetailPane)
            detail.action_toggle_view()
        except Exception:
            pass

    def action_noop(self) -> None:
        """No-op action to suppress inherited codebrowser bindings."""
        pass

    def action_toggle_focus(self) -> None:
        try:
            left = self.query_one("#history_left")
            detail = self.query_one("#history_detail")
        except Exception:
            return
        if left.has_focus_within:
            detail.focus()
        else:
            left.focus()
