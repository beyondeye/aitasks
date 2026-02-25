import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.widgets import Header, Footer, Static, DirectoryTree
from textual import work

from code_viewer import CodeViewer
from explain_manager import ExplainManager
from file_tree import ProjectFileTree, get_project_root


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
    }
    """

    TITLE = "aitasks codebrowser"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "toggle_focus", "Toggle Focus"),
        Binding("r", "refresh_explain", "Refresh annotations"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._project_root: Path | None = None
        self.explain_manager: ExplainManager | None = None
        self._current_explain_data: dict | None = None
        self._current_file_path: Path | None = None
        self._generating: bool = False

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

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        self._current_file_path = event.path
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        code_viewer.load_file(event.path)

        info_bar = self.query_one("#file_info_bar", Static)
        info_bar.update(f" {event.path.name} — {code_viewer._total_lines} lines")

        if self.explain_manager:
            self._load_explain_data(event.path)

    @work(exclusive=True)
    async def _load_explain_data(self, file_path: Path) -> None:
        """Load explain data for a file, generating if not cached."""
        if not self.explain_manager:
            return

        self._generating = True
        info_bar = self.query_one("#file_info_bar", Static)
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        line_info = f" {file_path.name} — {code_viewer._total_lines} lines"
        info_bar.update(f"{line_info} | Annotations: (generating...)")

        try:
            # Check cache first
            cached = await asyncio.to_thread(
                self.explain_manager.get_cached_data, file_path
            )

            if cached is not None:
                self._current_explain_data = {cached.file_path: cached}
                run_info = await asyncio.to_thread(
                    self.explain_manager.get_run_info, file_path
                )
                ts = run_info.timestamp if run_info else "unknown"
                info_bar.update(f"{line_info} | Annotations: {ts}")
            else:
                # Generate for the file's directory
                all_data = await asyncio.to_thread(
                    self.explain_manager.generate_explain_data, file_path.parent
                )
                self._current_explain_data = all_data
                run_info = await asyncio.to_thread(
                    self.explain_manager.get_run_info, file_path
                )
                ts = run_info.timestamp if run_info else "unknown"
                info_bar.update(f"{line_info} | Annotations: {ts}")
        except Exception as e:
            info_bar.update(f"{line_info} | Annotations: error ({e})")
        finally:
            self._generating = False

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
        info_bar = self.query_one("#file_info_bar", Static)
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        line_info = f" {file_path.name} — {code_viewer._total_lines} lines"
        info_bar.update(f"{line_info} | Annotations: (refreshing...)")

        try:
            all_data = await asyncio.to_thread(
                self.explain_manager.refresh_data, file_path.parent
            )
            self._current_explain_data = all_data
            run_info = await asyncio.to_thread(
                self.explain_manager.get_run_info, file_path
            )
            ts = run_info.timestamp if run_info else "unknown"
            info_bar.update(f"{line_info} | Annotations: {ts}")
        except Exception as e:
            info_bar.update(f"{line_info} | Annotations: error ({e})")
        finally:
            self._generating = False

    def action_toggle_focus(self) -> None:
        file_tree = self.query_one("#file_tree")
        code_viewer = self.query_one("#code_viewer")
        if file_tree.has_focus_within:
            code_viewer.focus()
        else:
            file_tree.focus()


if __name__ == "__main__":
    app = CodeBrowserApp()
    app.run()
