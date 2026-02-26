import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Footer, Input, Label, Static, DirectoryTree
from textual import on, work

from code_viewer import CodeViewer
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


class CodeBrowserApp(App):
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
        Binding("q", "quit", "Quit"),
        Binding("tab", "toggle_focus", "Toggle Focus"),
        Binding("r", "refresh_explain", "Refresh annotations"),
        Binding("t", "toggle_annotations", "Toggle annotations"),
        Binding("g", "go_to_line", "Go to line"),
        Binding("e", "launch_claude", "Explain in Claude"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._project_root: Path | None = None
        self.explain_manager: ExplainManager | None = None
        self._current_explain_data: dict | None = None
        self._current_file_path: Path | None = None
        self._generating: bool = False
        self._cursor_info: str = ""
        self._annotation_info: str = ""

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
        yield Footer()

    def on_resize(self, event) -> None:
        """Adjust file tree width for terminal size."""
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
        self._current_file_path = event.path
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        code_viewer.load_file(event.path)

        self._cursor_info = ""
        self._annotation_info = ""
        self._update_info_bar()

        if self.explain_manager:
            self._load_explain_data(event.path)

    def on_code_viewer_cursor_moved(self, event: CodeViewer.CursorMoved) -> None:
        """Update info bar when cursor moves."""
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        sel = code_viewer.get_selected_range()
        if sel:
            self._cursor_info = f"Line {event.line}/{event.total} | Sel {sel[0]}\u2013{sel[1]}"
        else:
            self._cursor_info = f"Line {event.line}/{event.total}"
        self._update_info_bar()

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

    @work(exclusive=True)
    async def _load_explain_data(self, file_path: Path) -> None:
        """Load explain data for a file, generating if not cached."""
        if not self.explain_manager:
            return

        self._generating = True
        self._annotation_info = "Annotations: (generating...)"
        self._update_info_bar()

        try:
            cached = await asyncio.to_thread(
                self.explain_manager.get_cached_data, file_path
            )

            if cached is not None:
                self._current_explain_data = {cached.file_path: cached}
                run_info = await asyncio.to_thread(
                    self.explain_manager.get_run_info, file_path
                )
                ts = run_info.timestamp if run_info else "unknown"
                self._annotation_info = f"Annotations: {ts}"
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
                ts = run_info.timestamp if run_info else "unknown"
                self._annotation_info = f"Annotations: {ts}"
                self._update_info_bar()
                self._update_code_annotations()
        except Exception as e:
            self._annotation_info = f"Annotations: error ({e})"
            self._update_info_bar()
        finally:
            self._generating = False

    def _update_code_annotations(self) -> None:
        """Pass current explain data annotations to the code viewer."""
        if not self._current_file_path or not self._current_explain_data:
            return
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        rel_path = str(self._current_file_path.relative_to(self._project_root))
        file_data = self._current_explain_data.get(rel_path)
        if file_data and file_data.is_binary:
            code_viewer.set_annotations([])
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
        self._annotation_info = "Annotations: (refreshing...)"
        self._update_info_bar()

        try:
            all_data = await asyncio.to_thread(
                self.explain_manager.refresh_data, file_path.parent
            )
            self._current_explain_data = all_data
            run_info = await asyncio.to_thread(
                self.explain_manager.get_run_info, file_path
            )
            ts = run_info.timestamp if run_info else "unknown"
            self._annotation_info = f"Annotations: {ts}"
            self._update_info_bar()
            self._update_code_annotations()
        except Exception as e:
            self._annotation_info = f"Annotations: error ({e})"
            self._update_info_bar()
        finally:
            self._generating = False

    def action_toggle_focus(self) -> None:
        file_tree = self.query_one("#file_tree")
        code_viewer = self.query_one("#code_viewer")
        if file_tree.has_focus_within:
            code_viewer.focus()
        else:
            file_tree.focus()

    def _find_terminal(self) -> str | None:
        """Find an available terminal emulator, or return None."""
        terminal = os.environ.get("TERMINAL")
        if terminal and shutil.which(terminal):
            return terminal
        for term in [
            "alacritty", "kitty", "ghostty", "foot",
            "x-terminal-emulator", "xdg-terminal-exec", "gnome-terminal",
            "konsole", "xfce4-terminal", "lxterminal", "mate-terminal", "xterm",
        ]:
            if shutil.which(term):
                return term
        return None

    @work(exclusive=True)
    async def action_launch_claude(self) -> None:
        """Launch Claude Code with the explain skill for the current file."""
        if not self._current_file_path:
            self.notify("No file selected", severity="warning")
            return
        if not shutil.which("claude"):
            self.notify("Claude CLI not found in PATH", severity="error")
            return

        rel_path = self._current_file_path.relative_to(self._project_root)
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        selected = code_viewer.get_selected_range()

        if selected:
            arg = f"{rel_path}:{selected[0]}-{selected[1]}"
            self.notify(
                f"Launching Claude for {rel_path} (lines {selected[0]}-{selected[1]})..."
            )
        else:
            arg = str(rel_path)
            self.notify(f"Launching Claude for {rel_path}...")

        terminal = self._find_terminal()
        if terminal:
            subprocess.Popen([terminal, "--", "claude", f"/aitask-explain {arg}"])
        else:
            with self.suspend():
                subprocess.call(["claude", f"/aitask-explain {arg}"])


if __name__ == "__main__":
    app = CodeBrowserApp()
    app.run()
