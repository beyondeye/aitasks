from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.widgets import Header, Footer, Static, DirectoryTree

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
        padding: 1;
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
                yield Static("Select a file to view")
        yield Footer()

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        self.log(f"File selected: {event.path}")

    def action_toggle_focus(self) -> None:
        file_tree = self.query_one("#file_tree")
        code_pane = self.query_one("#code_pane")
        if file_tree.has_focus_within:
            code_pane.focus()
        else:
            file_tree.focus()


if __name__ == "__main__":
    app = CodeBrowserApp()
    app.run()
