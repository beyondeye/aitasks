from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.widgets import Header, Footer, Static, DirectoryTree

from code_viewer import CodeViewer
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
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            try:
                project_root = get_project_root()
                yield ProjectFileTree(project_root, id="file_tree")
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
        code_viewer = self.query_one("#code_viewer", CodeViewer)
        code_viewer.load_file(event.path)
        info_bar = self.query_one("#file_info_bar", Static)
        info_bar.update(f" {event.path.name} — {code_viewer._total_lines} lines")

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
