"""Brainstorm TUI: interactive design space exploration with Textual."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Allow importing sibling packages (brainstorm, agentcrew)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    TabbedContent,
    TabPane,
)
from textual import on, work

from brainstorm.brainstorm_session import crew_worktree, load_session, session_exists

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AIT_PATH = str(Path(__file__).resolve().parent.parent.parent / "ait")

STATUS_COLORS = {
    "active": "#50FA7B",
    "paused": "#FFB86C",
    "completed": "#6272A4",
    "archived": "#888888",
}

_TAB_SHORTCUTS = {
    "1": "tab_dashboard",
    "2": "tab_dag",
    "3": "tab_compare",
    "4": "tab_actions",
    "5": "tab_status",
}


# ---------------------------------------------------------------------------
# Modal Screens
# ---------------------------------------------------------------------------


class InitSessionModal(ModalScreen):
    """Modal shown when no brainstorm session exists yet."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, task_num: str):
        super().__init__()
        self.task_num = task_num

    def compose(self) -> ComposeResult:
        with Container(id="init_dialog"):
            yield Label(
                f"No brainstorm session for t{self.task_num}", id="init_title"
            )
            yield Label("Initialize a new session?")
            with Horizontal(id="init_buttons"):
                yield Button("Initialize", variant="primary", id="btn_init")
                yield Button("Cancel", variant="default", id="btn_cancel")

    @on(Button.Pressed, "#btn_init")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class NodeDetailModal(ModalScreen):
    """Skeleton modal for viewing node details (content in t423_4)."""

    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    def __init__(self, node_id: str = ""):
        super().__init__()
        self.node_id = node_id

    def compose(self) -> ComposeResult:
        with Container(id="node_detail_dialog"):
            yield Label(
                f"Node Detail: {self.node_id}", id="node_detail_title"
            )
            yield Label(
                "Node detail viewer \u2014 coming in follow-up tasks",
                id="node_placeholder",
            )
            with Horizontal(id="node_detail_buttons"):
                yield Button(
                    "Close", variant="default", id="btn_close_detail"
                )

    @on(Button.Pressed, "#btn_close_detail")
    def close_detail(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


class BrainstormApp(App):
    """Textual app for interactive brainstorm session orchestration."""

    TITLE = "ait brainstorm"

    CSS = """
    Screen {
        align: center middle;
    }

    #brainstorm_tabs {
        height: 1fr;
    }

    VerticalScroll {
        padding: 1 2;
    }

    /* Placeholder labels for future tabs */
    #dag_placeholder, #compare_placeholder,
    #actions_placeholder, #status_placeholder {
        width: 100%;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
        height: 100%;
    }

    /* Dashboard */
    #dash_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #dash_status {
        color: $text-muted;
    }

    /* Init modal */
    #init_dialog {
        width: 60;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #init_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #init_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    /* Node detail modal */
    #node_detail_dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #node_detail_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #node_detail_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    #node_placeholder {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, task_num: str):
        super().__init__()
        self.task_num = task_num
        self.session_path = crew_worktree(task_num)
        self.session_data: dict = {}
        self.read_only: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="brainstorm_tabs"):
            with TabPane("Dashboard", id="tab_dashboard"):
                yield VerticalScroll(
                    Label(
                        f"Brainstorm session for task t{self.task_num}",
                        id="dash_title",
                    ),
                    Label("Session details loading...", id="dash_status"),
                    id="dashboard_content",
                )
            with TabPane("DAG", id="tab_dag"):
                yield VerticalScroll(
                    Label(
                        "DAG visualization \u2014 coming in follow-up tasks",
                        id="dag_placeholder",
                    ),
                    id="dag_content",
                )
            with TabPane("Compare", id="tab_compare"):
                yield VerticalScroll(
                    Label(
                        "Compare view \u2014 coming in follow-up tasks",
                        id="compare_placeholder",
                    ),
                    id="compare_content",
                )
            with TabPane("Actions", id="tab_actions"):
                yield VerticalScroll(
                    Label(
                        "Actions \u2014 coming in follow-up tasks",
                        id="actions_placeholder",
                    ),
                    id="actions_content",
                )
            with TabPane("Status", id="tab_status"):
                yield VerticalScroll(
                    Label(
                        "Status \u2014 coming in follow-up tasks",
                        id="status_placeholder",
                    ),
                    id="status_content",
                )
        yield Footer()

    def on_key(self, event) -> None:
        """Handle numeric tab shortcuts (1-5)."""
        if isinstance(self.screen, ModalScreen):
            return
        if event.key in _TAB_SHORTCUTS:
            tabbed = self.query_one(TabbedContent)
            tabbed.active = _TAB_SHORTCUTS[event.key]
            tabbed.query_one("Tabs").focus()
            event.prevent_default()
            event.stop()

    def on_mount(self) -> None:
        """Session lifecycle: load existing or prompt to initialize."""
        if session_exists(self.task_num):
            self._load_existing_session()
        else:
            self.push_screen(
                InitSessionModal(self.task_num),
                callback=self._on_init_result,
            )

    def _load_existing_session(self) -> None:
        """Load session data and update the dashboard."""
        self.session_data = load_session(self.task_num)
        status = self.session_data.get("status", "")
        if status in ("completed", "archived"):
            self.read_only = True
        dash_status = self.query_one("#dash_status", Label)
        dash_status.update(
            f"Status: {status} | Path: {self.session_path}"
            + (" [READ ONLY]" if self.read_only else "")
        )

    def _on_init_result(self, confirmed: bool | None) -> None:
        """Handle InitSessionModal result."""
        if confirmed:
            self._run_init()
        else:
            self.exit()

    @work(thread=True)
    def _run_init(self) -> None:
        """Run ait brainstorm init in a background thread."""
        result = subprocess.run(
            [AIT_PATH, "brainstorm", "init", self.task_num],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.call_from_thread(self._load_existing_session)
        else:
            self.call_from_thread(
                self.notify,
                f"Init failed: {result.stderr.strip()}",
                severity="error",
            )


if __name__ == "__main__":
    task_num = sys.argv[1] if len(sys.argv) > 1 else "0"
    app = BrainstormApp(task_num)
    app.run()
