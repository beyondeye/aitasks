from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.widgets import Header, Footer, Static


class CodeBrowserApp(App):
    CSS = """
    #file_tree_pane {
        width: 35;
        border-right: thick $primary;
        background: $surface;
        padding: 1;
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
            with Container(id="file_tree_pane"):
                yield Static("File tree will appear here")
            with Container(id="code_pane"):
                yield Static("Select a file to view")
        yield Footer()

    def action_toggle_focus(self) -> None:
        tree_pane = self.query_one("#file_tree_pane")
        code_pane = self.query_one("#code_pane")
        if tree_pane.has_focus_within:
            code_pane.focus()
        else:
            tree_pane.focus()


if __name__ == "__main__":
    app = CodeBrowserApp()
    app.run()
