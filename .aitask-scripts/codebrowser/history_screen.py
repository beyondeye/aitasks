"""History screen composing left pane + detail pane for browsing completed tasks."""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from agent_command_screen import AgentCommandScreen
from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command, resolve_agent_string, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, LoadingIndicator
from textual import work

from history_list import HistoryLeftPane, HistoryTaskList, HistoryTaskItem, TaskSelected
from history_detail import HistoryDetailPane, NavigateToFile, HistoryBrowseEvent
from history_data import load_task_index, load_task_index_progressive, detect_platform_info, CompletedTask, PlatformInfo


class HistoryScreen(Screen):
    """Full-screen view for browsing completed task history."""

    BINDINGS = [
        Binding("h", "dismiss_screen", "Back to browser"),
        Binding("escape", "dismiss_screen", "Back to browser"),
        Binding("q", "quit", "Quit"),
        Binding("tab", "toggle_focus", "Toggle Focus", priority=True),
        Binding("left", "focus_left", "Focus list"),
        Binding("right", "focus_right", "Focus detail"),
        Binding("v", "toggle_view", "Toggle task/plan"),
        Binding("l", "label_filter", "Label filter"),
        Binding("a", "launch_qa", "Launch QA"),
        # Override codebrowser app bindings to hide them from footer
        Binding("r", "noop", show=False),
        Binding("t", "noop", show=False),
        Binding("g", "noop", show=False),
        Binding("e", "noop", show=False),
        Binding("d", "noop", show=False),
        Binding("D", "noop", show=False),
        Binding("H", "noop", show=False),
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
        restore_labels: Optional[set] = None,
        navigate_to_task_id: Optional[str] = None,
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
        self._restore_labels = restore_labels
        self._navigate_to_task_id = navigate_to_task_id

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
        # Restore label filter before loading chunks
        if self._restore_labels:
            left.apply_label_filter(self._restore_labels)
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
        # Navigate to specific task if requested (takes priority over restore)
        if self._navigate_to_task_id:
            detail.show_task(self._navigate_to_task_id, is_explicit_browse=True)
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
        platform = detect_platform_info(self._project_root)
        for index_chunk in load_task_index_progressive(self._project_root):
            self.app.call_from_thread(self._on_index_chunk, index_chunk, platform)

    def _on_index_chunk(self, index, platform) -> None:
        # Always cache on app (even if screen dismissed, so re-open is fast)
        self.app._history_index = index
        self.app._history_platform = platform
        # Guard: skip UI updates if screen was dismissed while worker ran
        if not self.is_mounted:
            return
        if self._task_index is None:
            # First chunk: mount the UI
            self._task_index = index
            self._platform_info = platform
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
            # Navigate to specific task if requested
            if self._navigate_to_task_id:
                detail.show_task(self._navigate_to_task_id, is_explicit_browse=True)
        else:
            # Subsequent chunks: update existing UI progressively
            self._task_index = index
            try:
                left = self.query_one("#history_left", HistoryLeftPane)
                left.update_index(index)
                detail = self.query_one("#history_detail", HistoryDetailPane)
                detail._task_index = index
            except Exception:
                pass

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
            # Save label filter state
            self.app._history_active_labels = set(task_list._active_labels)
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

    def action_label_filter(self) -> None:
        """Open the label filter modal dialog."""
        if self._task_index is None:
            return
        from history_label_filter import LabelFilterModal, load_labels, compute_label_counts
        labels_list = load_labels(self._project_root)
        label_counts = compute_label_counts(self._task_index)
        try:
            left = self.query_one("#history_left", HistoryLeftPane)
            task_list = left.query_one("#history_list", HistoryTaskList)
            current = set(task_list._active_labels)
        except Exception:
            current = set()
        modal = LabelFilterModal(
            all_labels=labels_list,
            label_counts=label_counts,
            currently_selected=current,
            task_index=self._task_index,
        )
        self.app.push_screen(modal, callback=self._on_label_filter_result)

    def _on_label_filter_result(self, result: set | None) -> None:
        """Handle label filter modal result."""
        if result is None:
            return  # Cancel — keep existing filter
        try:
            left = self.query_one("#history_left", HistoryLeftPane)
            left.apply_label_filter(result)
        except Exception:
            pass

    def action_launch_qa(self) -> None:
        """Launch QA agent for the currently viewed task."""
        try:
            detail = self.query_one("#history_detail", HistoryDetailPane)
        except Exception:
            return
        if not detail._nav_stack:
            self.notify("No task selected", severity="warning")
            return
        task_id = detail._nav_stack[-1]

        from agent_utils import resolve_agent_binary

        agent_name, binary, error_msg = resolve_agent_binary(self._project_root, "qa")
        if not binary:
            self.notify(error_msg or "Could not resolve QA agent configuration", severity="error")
            return
        if not shutil.which(binary):
            self.notify(f"{agent_name} CLI ({binary}) not found in PATH", severity="error")
            return

        full_cmd = resolve_dry_run_command(self._project_root, "qa", task_id)
        if full_cmd:
            prompt_str = f"/aitask-qa {task_id}"
            agent_string = resolve_agent_string(self._project_root, "qa")
            screen = AgentCommandScreen(
                f"QA for t{task_id}", full_cmd, prompt_str,
                default_window_name=f"agent-qa-{task_id}",
                project_root=self._project_root,
                operation="qa",
                operation_args=[task_id],
                default_agent_string=agent_string,
            )
            def on_result(result):
                if result == "run":
                    self._run_qa_command(task_id)
                elif isinstance(result, TmuxLaunchConfig):
                    _, err = launch_in_tmux(screen.full_command, result)
                    if err:
                        self.app.notify(err, severity="error")
                    elif result.new_window:
                        maybe_spawn_minimonitor(result.session, result.window)
            self.app.push_screen(screen, on_result)
        else:
            self._run_qa_command(task_id)

    @work(exclusive=True)
    async def _run_qa_command(self, task_id: str) -> None:
        """Launch QA agent in a terminal or inline."""
        wrapper = str(self._project_root / ".aitask-scripts" / "aitask_codeagent.sh")
        terminal = _find_terminal()
        if terminal:
            subprocess.Popen(
                [terminal, "--", wrapper, "invoke", "qa", task_id],
                cwd=str(self._project_root),
            )
        else:
            with self.app.suspend():
                subprocess.call(
                    [wrapper, "invoke", "qa", task_id],
                    cwd=str(self._project_root),
                )

    def action_toggle_focus(self) -> None:
        """Cycle focus: history_list → recent_list → detail → history_list."""
        try:
            left = self.query_one("#history_left", HistoryLeftPane)
            detail = self.query_one("#history_detail", HistoryDetailPane)
        except Exception:
            return
        try:
            task_list = left.query_one("#history_list", HistoryTaskList)
            recent_list = left.query_one("#recent_list")
        except Exception:
            return

        if task_list.has_focus_within:
            self._focus_in_list(recent_list)
            return

        if recent_list.has_focus_within:
            if not detail._focus_first_field():
                detail.focus()
            return

        if detail.has_focus_within:
            self._focus_in_list(task_list)
            return

        # Fallback: focus the task list
        self._focus_in_list(task_list)

    def action_focus_right(self) -> None:
        """Move focus to first focusable field in the detail pane."""
        try:
            detail = self.query_one("#history_detail", HistoryDetailPane)
        except Exception:
            return
        if detail.has_focus_within:
            return
        for child in detail.children:
            if child.can_focus and child.display and child.styles.display != "none":
                child.focus()
                child.scroll_visible()
                return

    def action_focus_left(self) -> None:
        """Move focus leftward: detail->task list->recent list, cycling."""
        try:
            left = self.query_one("#history_left", HistoryLeftPane)
            detail = self.query_one("#history_detail", HistoryDetailPane)
        except Exception:
            return
        task_list = left.query_one("#history_list", HistoryTaskList)
        recent_list = left.query_one("#recent_list")

        if detail.has_focus_within:
            # Detail pane -> focus current task in either list
            current_task_id = detail._nav_stack[-1] if detail._nav_stack else None
            if self._focus_in_list(task_list, current_task_id):
                return
            if self._focus_in_list(recent_list, current_task_id):
                return
            # Fallback: first visible in task list
            if not self._focus_in_list(task_list):
                self._focus_in_list(recent_list)
            return

        if task_list.has_focus_within:
            # Remember focused task before switching to recent list
            focused = self.app.focused
            if isinstance(focused, HistoryTaskItem):
                self._last_task_list_focus_id = focused.completed_task.task_id
            # Full task list -> recent tasks list
            self._focus_in_list(recent_list)
            return

        if recent_list.has_focus_within:
            # Recent tasks list -> full task list (restore last focused if possible)
            last_id = getattr(self, "_last_task_list_focus_id", None)
            if last_id and self._focus_in_list(task_list, last_id):
                return
            self._focus_in_list(task_list)
            return

        # No focus anywhere -> full task list, then recent list
        if not self._focus_in_list(task_list):
            self._focus_in_list(recent_list)

    def _focus_in_list(self, container, target_task_id: str | None = None) -> bool:
        """Focus a task item in the given container. Returns True if focused."""
        items = list(container.query(HistoryTaskItem))
        if target_task_id:
            for item in items:
                if item.completed_task.task_id == target_task_id:
                    item.focus()
                    item.scroll_visible()
                    return True
        # Find the first item visible in the scroll viewport
        try:
            scroll_y = container.scroll_y
            viewport_h = container.size.height
            for item in items:
                if not item.display or item.styles.display == "none":
                    continue
                item_y = item.virtual_region.y
                if item_y + item.virtual_region.height > scroll_y and item_y < scroll_y + viewport_h:
                    item.focus()
                    return True
        except Exception:
            pass
        # Fallback: first visible item
        for item in items:
            if item.display and item.styles.display != "none":
                item.focus()
                item.scroll_visible()
                return True
        return False
