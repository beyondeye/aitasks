"""Codebrowser TUI entry point.

Supports a programmatic focus mechanism so other tools can ask the
codebrowser to "open this file at these lines":

- ``--focus PATH[:RANGE_SPEC]`` CLI flag for cold launches.
- ``AITASK_CODEBROWSER_FOCUS`` tmux session env var for hot handoffs to
  an already-running instance. Polled once per second; consumed and
  cleared on read.

``RANGE_SPEC`` is ``N``, ``N-M``, or ``N-M^K-L^...`` (matching the
t540_1 ``file_references`` format). Multi-range entries collapse to
the outer span ``min(starts)..max(ends)`` for display, since the code
viewer holds a single contiguous selection.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from agent_command_screen import AgentCommandScreen
from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command, resolve_agent_string, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor
from tui_switcher import TuiSwitcherMixin

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, Header, Footer, Input, Label, Static, DirectoryTree
from textual import on, work

from agent_utils import resolve_agent_binary
from code_viewer import CodeViewer
from detail_pane import DetailPane
from explain_manager import ExplainManager
from file_tree import ProjectFileTree, get_project_root


class GoToLineScreen(ModalScreen):
    """Modal dialog to jump to a specific line number."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, max_line: int):
        super().__init__()
        self.max_line = max_line

    def compose(self):
        with Container(id="goto_dialog"):
            yield Label(f"Go to line (1\u2013{self.max_line}):")
            yield Input(placeholder="Line number", id="goto_input")
            with Horizontal(id="goto_buttons"):
                yield Button("Go", variant="primary", id="btn_goto")
                yield Button("Cancel", variant="default", id="btn_goto_cancel")

    def on_mount(self) -> None:
        self.query_one("#goto_input", Input).focus()

    @on(Button.Pressed, "#btn_goto")
    def do_goto(self) -> None:
        self._submit()

    @on(Button.Pressed, "#btn_goto_cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        raw = self.query_one("#goto_input", Input).value.strip()
        if not raw:
            return
        try:
            line = int(raw)
        except ValueError:
            return
        line = max(1, min(line, self.max_line))
        self.dismiss(line)

    def action_cancel(self) -> None:
        self.dismiss(None)


class CodeBrowserApp(TuiSwitcherMixin, App):
    CSS = """
    #file_tree {
        width: 35;
        border-right: thick $primary;
        background: $surface;
    }
    #code_pane {
        width: 1fr;
        background: $surface;
    }
    #file_info_bar {
        height: 1;
        dock: top;
        background: $surface-lighten-1;
        padding: 0 1;
    }
    #code_viewer {
        height: 1fr;
    }
    #code_display {
        width: auto;
        overflow-x: hidden;
    }
    #detail_pane {
        width: 30;
    }
    #detail_pane.hidden {
        display: none;
    }
    GoToLineScreen {
        align: center middle;
    }
    #goto_dialog {
        width: 40;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }
    #goto_buttons {
        margin-top: 1;
        height: auto;
    }
    #goto_buttons Button {
        margin-right: 1;
    }
    """

    TITLE = "aitasks codebrowser"

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        Binding("escape", "handle_escape_key", "Escape", show=False, priority=True),
        Binding("q", "quit", "Quit"),
        Binding("tab", "toggle_focus", "Toggle Focus"),
        Binding("r", "refresh_explain", "Refresh annotations"),
        Binding("t", "toggle_annotations", "Toggle annotations"),
        Binding("g", "go_to_line", "Go to line"),
        Binding("e", "launch_agent", "Explain"),
        Binding("d", "toggle_detail", "Toggle detail"),
        Binding("D", "expand_detail", "Expand detail"),
        Binding("h", "toggle_history", "History"),
        Binding("H", "history_for_task", "History for task"),
    ]

    DETAIL_DEFAULT_WIDTH = 30
    CODE_MIN_WIDTH = 80

    def __init__(self, *args, initial_focus: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_tui_name = "codebrowser"
        self._project_root: Path | None = None
        self.explain_manager: ExplainManager | None = None
        self._current_explain_data: dict | None = None
        self._current_file_path: Path | None = None
        self._generating: bool = False
        self._gen_start_time: float = 0.0
        self._gen_timer: Timer | None = None
        self._cursor_info: str = ""
        self._annotation_info: str = ""
        self._detail_visible: bool = False
        self._detail_expanded: bool = False
        self._history_index = None       # cached task index
        self._history_platform = None    # cached platform info
        self._history_last_task_id = None  # last viewed task in history
        self._history_loaded_chunks = 0    # number of chunks loaded in list
        self._history_showing_plan = False  # plan/task view toggle state
        self._history_scroll_y = 0         # task list scroll position
        self._history_active_labels: set = set()  # label filter state
        self._initial_focus: str | None = initial_focus
        self._tmux_session: str | None = self._detect_tmux_session()
        # Path whose next FileSelected event should be ignored because the
        # focus mechanism has already loaded the file. Cleared after one
        # event so subsequent user clicks behave normally.
        self._suppress_next_file_selected: Path | None = None

    @staticmethod
    def _detect_tmux_session() -> str | None:
        """Return the current tmux session name, or None if not in tmux."""
        if not os.environ.get("TMUX"):
            return None
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return None

    @staticmethod
    def _parse_focus_value(
        value: str,
    ) -> tuple[str, int | None, int | None] | None:
        """Parse PATH[:RANGE_SPEC] into (path, start, end) or None on error.

        RANGE_SPEC is N, N-M, or N-M^K-L^... — multi-range collapses to
        the outer span min(starts)..max(ends).
        """
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        path, sep, rest = value.partition(":")
        if not path:
            return None
        if not sep:
            return (path, None, None)
        rest = rest.strip()
        if not rest:
            return (path, None, None)
        starts: list[int] = []
        ends: list[int] = []
        for segment in rest.split("^"):
            segment = segment.strip()
            if not segment:
                return None
            if "-" in segment:
                a, _, b = segment.partition("-")
                try:
                    s = int(a)
                    e = int(b)
                except ValueError:
                    return None
                if s < 1 or e < 1 or e < s:
                    return None
                starts.append(s)
                ends.append(e)
            else:
                try:
                    n = int(segment)
                except ValueError:
                    return None
                if n < 1:
                    return None
                starts.append(n)
                ends.append(n)
        if not starts:
            return None
        return (path, min(starts), max(ends))

    def _consume_codebrowser_focus(self) -> str | None:
        """Read AITASK_CODEBROWSER_FOCUS from the tmux session env, or None."""
        if not self._tmux_session:
            return None
        try:
            result = subprocess.run(
                ["tmux", "show-environment", "-t", self._tmux_session,
                 "AITASK_CODEBROWSER_FOCUS"],
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None
        if result.returncode != 0:
            return None
        line = result.stdout.strip()
        if not line or "=" not in line:
            return None
        _, _, val = line.partition("=")
        val = val.strip()
        return val or None

    def _clear_codebrowser_focus(self) -> None:
        """Unset AITASK_CODEBROWSER_FOCUS on the tmux session."""
        if not self._tmux_session:
            return
        try:
            subprocess.run(
                ["tmux", "set-environment", "-t", self._tmux_session, "-u",
                 "AITASK_CODEBROWSER_FOCUS"],
                capture_output=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    def _apply_focus(self, focus_value: str) -> None:
        """Parse a focus value and navigate the viewer to it."""
        parsed = self._parse_focus_value(focus_value)
        if parsed is None:
            self.notify(
                f"Invalid focus value: {focus_value}", severity="warning"
            )
            return
        rel_path, start, end = parsed
        if self._project_root is None:
            return
        candidate = (self._project_root / rel_path).resolve()
        try:
            candidate.relative_to(self._project_root.resolve())
        except ValueError:
            self.notify(
                f"Focus path outside project root: {rel_path}",
                severity="warning",
            )
            return
        if not candidate.is_file():
            self.notify(
                f"Focus path not found: {rel_path}", severity="warning"
            )
            return
        # Mark this path so the FileSelected event from tree.select_path
        # below does NOT clobber the cursor state we are about to set.
        self._suppress_next_file_selected = candidate
        self._open_file_by_path(str(candidate.relative_to(self._project_root)))
        if start is None or end is None:
            return
        # The Static.update() inside load_file is queued for the next
        # render cycle, so the VerticalScroll's virtual_size won't
        # reflect the new content until then. A short timer lets the
        # render pipeline settle before scroll_to() is called.
        self.set_timer(0.15, lambda: self._apply_focus_range(start, end))

    def _apply_focus_range(self, start: int, end: int) -> None:
        """Set cursor + selection on the viewer; called after layout."""
        try:
            code_viewer = self.query_one("#code_viewer", CodeViewer)
        except Exception:
            return
        if code_viewer._total_lines == 0:
            return
        last = code_viewer._total_lines
        clamped_start = max(1, min(start, last))
        clamped_end = max(clamped_start, min(end, last))
        code_viewer._cursor_line = clamped_end - 1
        if clamped_start != clamped_end:
            code_viewer._selection_start = clamped_start - 1
            code_viewer._selection_end = clamped_end - 1
            code_viewer._selection_active = True
        else:
            code_viewer._selection_start = None
            code_viewer._selection_end = None
            code_viewer._selection_active = False
        code_viewer._ensure_viewport_contains_cursor()
        code_viewer._rebuild_display()
        code_viewer._scroll_cursor_visible()
        code_viewer.post_message(
            code_viewer.CursorMoved(clamped_end, code_viewer._total_lines)
        )

    def _consume_and_apply_focus(self) -> None:
        """Poll callback: consume the env var (if any) and apply it."""
        value = self._consume_codebrowser_focus()
        if not value:
            return
        self._clear_codebrowser_focus()
        self._apply_focus(value)

    def on_mount(self) -> None:
        """Apply any pending focus and start the env-var poll."""
        if self._initial_focus:
            pending = self._initial_focus
            self._initial_focus = None
            self.call_after_refresh(self._apply_focus, pending)
        self.call_after_refresh(self._consume_and_apply_focus)
        self.set_interval(1.0, self._consume_and_apply_focus)

    def action_handle_escape_key(self) -> None:
        """Escape: delegate to screen's handle_escape if available, dismiss modals, or no-op."""
        if hasattr(self.screen, "handle_escape"):
            self.screen.handle_escape()
        elif isinstance(self.screen, ModalScreen):
            self.screen.dismiss(None)
        elif hasattr(self.screen, "action_dismiss_screen"):
            self.screen.action_dismiss_screen()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            try:
                self._project_root = get_project_root()
                self.explain_manager = ExplainManager(self._project_root)
                yield ProjectFileTree(self._project_root, id="file_tree")
            except RuntimeError:
                with Container(id="file_tree"):
                    yield Static("Error: not inside a git repository")
            with Container(id="code_pane"):
                yield Static("No file selected", id="file_info_bar")
                yield CodeViewer(id="code_viewer")
            yield DetailPane(id="detail_pane", classes="hidden")
        yield Footer()

    def on_resize(self, event) -> None:
        """Adjust file tree and detail pane widths for terminal size."""
        width = event.size.width
        try:
            file_tree = self.query_one("#file_tree")
        except Exception:
            return
        if width >= 120:
            file_tree.styles.width = 35
        elif width >= 80:
            file_tree.styles.width = 28
        else:
            file_tree.styles.width = 22
        if self._detail_visible:
            self._apply_detail_width()

    def _apply_detail_width(self) -> None:
        """Set detail pane width respecting code-first priority."""
        if not self._detail_visible:
            return
        try:
            detail = self.query_one("#detail_pane", DetailPane)
            file_tree = self.query_one("#file_tree")
        except Exception:
            return

        total_width = self.size.width
        tree_width = 35
        if file_tree.styles.width and file_tree.styles.width.value:
            tree_width = int(file_tree.styles.width.value)
        # Available width after tree and border gaps
        available = total_width - tree_width - 2

        if self._detail_expanded:
            desired_detail = total_width // 2
        else:
            desired_detail = self.DETAIL_DEFAULT_WIDTH

        # Code gets priority: reduce detail if code would be < minimum
        if available - desired_detail < self.CODE_MIN_WIDTH:
            desired_detail = max(0, available - self.CODE_MIN_WIDTH)

        if desired_detail < 15:
            # Too narrow to be useful — hide temporarily
            detail.styles.width = 0
            detail.add_class("hidden")
        else:
            detail.styles.width = desired_detail
            detail.remove_class("hidden")

    def _update_info_bar(self) -> None:
        """Rebuild and display the info bar from current state."""
        if not self._current_file_path:
            return
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        parts = [f" {self._current_file_path.name} — {code_viewer._total_lines} lines"]
        if self._cursor_info:
            parts.append(self._cursor_info)
        if self._annotation_info:
            parts.append(self._annotation_info)
        self.query_one("#file_info_bar", Static).update(" | ".join(parts))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        # If this event was triggered by the focus mechanism's tree.select_path
        # call, the file is already loaded and cursor state has been set —
        # skip the reload to avoid clobbering it.
        if (
            self._suppress_next_file_selected is not None
            and event.path == self._suppress_next_file_selected
        ):
            self._suppress_next_file_selected = None
            return
        self._current_file_path = event.path
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        code_viewer.load_file(event.path)

        self._cursor_info = ""
        self._annotation_info = ""
        self._update_info_bar()

        try:
            self.query_one("#detail_pane", DetailPane).clear()
        except Exception:
            pass

        if self.explain_manager:
            self._load_explain_data(event.path)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Pre-cache explain data when a directory is expanded."""
        if not self.explain_manager:
            return
        if self.explain_manager.request_precache(event.path):
            self._run_precache()

    @work(exclusive=False, group="precache")
    async def _run_precache(self) -> None:
        """Process the pre-cache queue in the background (silent, no info bar updates)."""
        if not self.explain_manager:
            return
        while True:
            directory = self.explain_manager.pop_precache()
            if directory is None:
                break
            if self.explain_manager.is_generating():
                # Another generation is active; re-queue and stop
                self.explain_manager.request_precache(directory)
                break
            try:
                await asyncio.to_thread(
                    self.explain_manager.generate_explain_data, directory
                )
            except Exception:
                pass  # Pre-cache failures are silent

    def on_code_viewer_cursor_moved(self, event: CodeViewer.CursorMoved) -> None:
        """Update info bar and detail pane when cursor moves."""
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        sel = code_viewer.get_selected_range()
        if sel:
            self._cursor_info = f"Line {event.line}/{event.total} | Sel {sel[0]}\u2013{sel[1]}"
        else:
            self._cursor_info = f"Line {event.line}/{event.total}"
        self._update_info_bar()
        if self._detail_visible:
            self._update_detail_pane(event.line, sel)

    def action_go_to_line(self) -> None:
        """Open go-to-line modal."""
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        if code_viewer._total_lines == 0:
            return

        def on_line(line: int | None) -> None:
            if line is not None:
                code_viewer.move_cursor(line - 1)
                code_viewer.focus()

        self.push_screen(GoToLineScreen(code_viewer._total_lines), on_line)

    def _start_gen_timer(self) -> None:
        """Start the generation progress timer."""
        self._gen_start_time = time.monotonic()
        self._stop_gen_timer()
        self._gen_timer = self.set_interval(0.5, self._tick_gen_progress)

    def _stop_gen_timer(self) -> None:
        """Stop the generation progress timer."""
        if self._gen_timer is not None:
            self._gen_timer.stop()
            self._gen_timer = None

    def _tick_gen_progress(self) -> None:
        """Update the info bar with elapsed generation time."""
        if not self._generating:
            self._stop_gen_timer()
            return
        elapsed = time.monotonic() - self._gen_start_time
        self._annotation_info = f"Annotations: Generating... ({elapsed:.1f}s)"
        self._update_info_bar()

    def _format_annotation_info(self, run_info) -> str:
        """Format annotation info with staleness indicator."""
        ts = run_info.timestamp if run_info else "unknown"
        if run_info and run_info.is_stale:
            return f"Annotations: {ts} (outdated - r to refresh)"
        return f"Annotations: {ts}"

    @work(exclusive=True)
    async def _load_explain_data(self, file_path: Path) -> None:
        """Load explain data for a file, generating if not cached."""
        if not self.explain_manager:
            return

        self._generating = True
        self._annotation_info = "Annotations: Generating... (0.0s)"
        self._update_info_bar()
        self._start_gen_timer()

        try:
            cached = await asyncio.to_thread(
                self.explain_manager.get_cached_data, file_path
            )

            if cached is not None:
                self._current_explain_data = {cached.file_path: cached}
                run_info = await asyncio.to_thread(
                    self.explain_manager.get_run_info, file_path
                )
                elapsed = time.monotonic() - self._gen_start_time
                self._annotation_info = self._format_annotation_info(run_info)
                self._update_info_bar()
                self._update_code_annotations()
            else:
                all_data = await asyncio.to_thread(
                    self.explain_manager.generate_explain_data, file_path.parent
                )
                self._current_explain_data = all_data
                run_info = await asyncio.to_thread(
                    self.explain_manager.get_run_info, file_path
                )
                elapsed = time.monotonic() - self._gen_start_time
                # Briefly show generation time
                self._annotation_info = f"Annotations: Generated in {elapsed:.1f}s"
                self._update_info_bar()
                self._update_code_annotations()
                # After 2 seconds, switch to normal timestamp display
                self.set_timer(2.0, lambda: self._show_final_annotation(run_info))
        except Exception as e:
            self._annotation_info = f"Annotations: error ({e})"
            self._update_info_bar()
        finally:
            self._generating = False
            self._stop_gen_timer()

    def _show_final_annotation(self, run_info) -> None:
        """Switch from 'Generated in Xs' to normal timestamp display."""
        if self._generating:
            return  # Don't overwrite if a new generation started
        self._annotation_info = self._format_annotation_info(run_info)
        self._update_info_bar()

    def _update_code_annotations(self) -> None:
        """Pass current explain data annotations to the code viewer."""
        if not self._current_file_path or not self._current_explain_data:
            return
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        rel_path = str(self._current_file_path.relative_to(self._project_root))
        file_data = self._current_explain_data.get(rel_path)
        if file_data and file_data.is_binary:
            code_viewer.set_annotations([])
            code_viewer.show_binary_info(file_data.commit_timeline)
            n = len(file_data.commit_timeline)
            self._annotation_info += f" (binary, {n} commit{'s' if n != 1 else ''})"
            self._update_info_bar()
            return
        code_viewer.set_annotations(file_data.annotations if file_data else [])

    def action_toggle_annotations(self) -> None:
        """Toggle annotation gutter visibility."""
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        code_viewer.toggle_annotations()

    def action_refresh_explain(self) -> None:
        """Refresh explain data for the current file's directory."""
        if self._current_file_path and self.explain_manager:
            self._refresh_explain_data(self._current_file_path)

    @work(exclusive=True)
    async def _refresh_explain_data(self, file_path: Path) -> None:
        """Regenerate explain data for a file's directory."""
        if not self.explain_manager:
            return

        self._generating = True
        self._annotation_info = "Annotations: Refreshing... (0.0s)"
        self._update_info_bar()
        self._start_gen_timer()

        try:
            # Invalidate git cache so staleness re-checks after refresh
            self.explain_manager.invalidate_git_cache()
            all_data = await asyncio.to_thread(
                self.explain_manager.refresh_data, file_path.parent
            )
            self._current_explain_data = all_data
            run_info = await asyncio.to_thread(
                self.explain_manager.get_run_info, file_path
            )
            elapsed = time.monotonic() - self._gen_start_time
            self._annotation_info = f"Annotations: Refreshed in {elapsed:.1f}s"
            self._update_info_bar()
            self._update_code_annotations()
            self.set_timer(2.0, lambda: self._show_final_annotation(run_info))
        except Exception as e:
            self._annotation_info = f"Annotations: error ({e})"
            self._update_info_bar()
        finally:
            self._generating = False
            self._stop_gen_timer()

    def _update_detail_pane(self, cursor_line: int, selection: tuple[int, int] | None) -> None:
        """Look up task IDs for the current line and update the detail pane."""
        try:
            detail = self.query_one("#detail_pane", DetailPane)
        except Exception:
            return

        if not self._current_explain_data or not self._current_file_path:
            detail.clear()
            return

        rel_path = str(self._current_file_path.relative_to(self._project_root))
        file_data = self._current_explain_data.get(rel_path)
        if not file_data or not file_data.annotations:
            detail.clear()
            return

        # Collect task_ids for the cursor line (or selection range)
        if selection:
            line_start, line_end = selection
        else:
            line_start = line_end = cursor_line

        task_ids: list[str] = []
        for ann in file_data.annotations:
            if ann.start_line <= line_end and ann.end_line >= line_start:
                for tid in ann.task_ids:
                    if tid not in task_ids:
                        task_ids.append(tid)

        if not task_ids:
            detail.clear()
            return

        if len(task_ids) > 1:
            detail.show_multiple_tasks(task_ids)
            return

        # Single task — resolve and show content
        if self.explain_manager:
            self._load_task_detail(task_ids[0])

    @work(exclusive=True, group="detail_load")
    async def _load_task_detail(self, task_id: str) -> None:
        """Load task detail content in a worker thread."""
        if not self.explain_manager or not self._current_file_path:
            return
        detail_content = await asyncio.to_thread(
            self.explain_manager.get_task_detail,
            self._current_file_path, task_id,
        )
        try:
            detail = self.query_one("#detail_pane", DetailPane)
        except Exception:
            return
        detail.update_content(detail_content)

    def action_toggle_detail(self) -> None:
        """Toggle detail pane visibility."""
        try:
            detail = self.query_one("#detail_pane", DetailPane)
        except Exception:
            return
        self._detail_visible = not self._detail_visible
        if self._detail_visible:
            detail.remove_class("hidden")
            self._apply_detail_width()
            # Trigger content update for current cursor position
            code_viewer = self.query_one("#code_viewer", CodeViewer)
            sel = code_viewer.get_selected_range()
            self._update_detail_pane(code_viewer._cursor_line + 1, sel)
        else:
            detail.add_class("hidden")
            self._detail_expanded = False

    def action_expand_detail(self) -> None:
        """Toggle detail pane between default width and half screen."""
        if not self._detail_visible:
            return
        self._detail_expanded = not self._detail_expanded
        self._apply_detail_width()

    def action_toggle_focus(self) -> None:
        file_tree = self.query_one("#file_tree")
        code_viewer = self.query_one("#code_viewer")
        if file_tree.has_focus_within:
            code_viewer.focus()
        elif code_viewer.has_focus_within:
            if self._detail_visible:
                try:
                    self.query_one("#detail_pane", DetailPane).focus()
                except Exception:
                    file_tree.focus()
            else:
                file_tree.focus()
        else:
            file_tree.focus()

    def action_toggle_history(self) -> None:
        """Push the history screen to browse completed tasks."""
        if self._project_root is None:
            return
        from history_screen import HistoryScreen
        screen = HistoryScreen(
            self._project_root,
            cached_index=self._history_index,
            cached_platform=self._history_platform,
            restore_task_id=self._history_last_task_id,
            restore_chunks=self._history_loaded_chunks,
            restore_showing_plan=self._history_showing_plan,
            restore_scroll_y=self._history_scroll_y,
            restore_labels=self._history_active_labels,
        )
        self.push_screen(screen, callback=self._on_history_dismiss)

    def _resolve_task_id_at_cursor(self) -> str | None:
        """Get the task ID at the current cursor line from annotations."""
        if not self._current_explain_data or not self._current_file_path:
            return None
        rel_path = str(self._current_file_path.relative_to(self._project_root))
        file_data = self._current_explain_data.get(rel_path)
        if not file_data or not file_data.annotations:
            return None
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        cursor_line = code_viewer._cursor_line + 1
        task_ids: list[str] = []
        for ann in file_data.annotations:
            if ann.start_line <= cursor_line and ann.end_line >= cursor_line:
                for tid in ann.task_ids:
                    if tid not in task_ids:
                        task_ids.append(tid)
        if len(task_ids) == 1:
            return task_ids[0]
        return None

    def action_history_for_task(self) -> None:
        """Open history screen navigated to the current annotation's task."""
        if self._project_root is None:
            return
        # Try detail pane first (if visible and showing a task)
        task_id = None
        if self._detail_visible:
            try:
                detail = self.query_one("#detail_pane", DetailPane)
                task_id = detail._current_task_id
            except Exception:
                pass
        # Fall back to resolving from annotations at cursor
        if not task_id:
            task_id = self._resolve_task_id_at_cursor()
        if not task_id:
            self.notify("No task at cursor line", severity="warning")
            return
        from history_screen import HistoryScreen
        screen = HistoryScreen(
            self._project_root,
            cached_index=self._history_index,
            cached_platform=self._history_platform,
            navigate_to_task_id=task_id,
            restore_chunks=self._history_loaded_chunks,
            restore_labels=self._history_active_labels,
        )
        self.push_screen(screen, callback=self._on_history_dismiss)

    def _on_history_dismiss(self, result) -> None:
        if result is not None:
            self._open_file_by_path(result)

    def _open_file_by_path(self, file_path: str) -> None:
        """Programmatically open a file in the code viewer (from history navigation)."""
        full_path = self._project_root / file_path
        if not full_path.exists():
            self.notify(f"File not found: {file_path}", severity="warning")
            return

        self._current_file_path = full_path
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        code_viewer.load_file(full_path)

        self._cursor_info = ""
        self._annotation_info = ""
        self._update_info_bar()

        try:
            self.query_one("#detail_pane", DetailPane).clear()
        except Exception:
            pass

        if self.explain_manager:
            self._load_explain_data(full_path)

        tree = self.query_one("#file_tree", ProjectFileTree)
        tree.select_path(full_path)

    def action_launch_agent(self) -> None:
        """Launch the configured code agent with the explain skill for the current file."""
        if not self._current_file_path:
            self.notify("No file selected", severity="warning")
            return

        agent_name, binary, error_msg = resolve_agent_binary(self._project_root, "explain")
        if not binary:
            self.notify(error_msg or "Could not resolve code agent configuration", severity="error")
            return
        if not shutil.which(binary):
            self.notify(f"{agent_name} CLI ({binary}) not found in PATH", severity="error")
            return

        rel_path = self._current_file_path.relative_to(self._project_root)
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        selected = code_viewer.get_selected_range()

        if selected:
            arg = f"{rel_path}:{selected[0]}-{selected[1]}"
            title = f"Explain {rel_path} (lines {selected[0]}-{selected[1]})"
        else:
            arg = str(rel_path)
            title = f"Explain {rel_path}"

        full_cmd = resolve_dry_run_command(self._project_root, "explain", arg)
        if full_cmd:
            prompt_str = f"/aitask-explain {arg}"
            agent_string = resolve_agent_string(self._project_root, "explain")
            screen = AgentCommandScreen(
                title, full_cmd, prompt_str,
                default_window_name=f"agent-explain-{rel_path.name}",
                project_root=self._project_root,
                operation="explain",
                operation_args=[arg],
                default_agent_string=agent_string,
            )
            def on_result(result):
                if result == "run":
                    self._run_agent_command("explain", arg)
                elif isinstance(result, TmuxLaunchConfig):
                    _, err = launch_in_tmux(screen.full_command, result)
                    if err:
                        self.notify(err, severity="error")
                    elif result.new_window:
                        maybe_spawn_minimonitor(result.session, result.window)
            self.push_screen(screen, on_result)
        else:
            # Fallback: direct launch without modal
            self._run_agent_command("explain", arg)

    @work(exclusive=True)
    async def _run_agent_command(self, operation: str, arg: str) -> None:
        """Launch code agent in a terminal or inline."""
        wrapper = str(self._project_root / ".aitask-scripts" / "aitask_codeagent.sh")
        terminal = _find_terminal()
        if terminal:
            subprocess.Popen([terminal, "--", wrapper, "invoke", operation, arg],
                             cwd=str(self._project_root))
        else:
            with self.suspend():
                subprocess.call([wrapper, "invoke", operation, arg],
                                cwd=str(self._project_root))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(prog="codebrowser")
    parser.add_argument(
        "--focus",
        metavar="PATH[:RANGE_SPEC]",
        default=None,
        help=(
            "Open the codebrowser focused on PATH at the given line range. "
            "RANGE_SPEC is N, N-M, or N-M^K-L (multi-range collapses to "
            "outer span). Also consumable via the AITASK_CODEBROWSER_FOCUS "
            "tmux session env var."
        ),
    )
    args = parser.parse_args()
    app = CodeBrowserApp(initial_focus=args.focus)
    app.run()


if __name__ == "__main__":
    main()
