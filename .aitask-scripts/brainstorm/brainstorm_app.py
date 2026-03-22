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
    Static,
    TabbedContent,
    TabPane,
)
from textual import on, work

from brainstorm.brainstorm_dag import (
    get_dimension_fields,
    get_head,
    list_nodes,
    read_node,
    set_head,
)
from brainstorm.brainstorm_dag_display import DAGDisplay
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
# Dashboard Widgets
# ---------------------------------------------------------------------------


class NodeRow(Static):
    """Focusable row representing a brainstorm node in the dashboard list."""

    def __init__(self, node_id: str, description: str, is_head: bool = False):
        super().__init__()
        self.node_id = node_id
        self.node_description = description
        self.is_head = is_head
        self.can_focus = True

    def render(self) -> str:
        head_marker = " [bold green]HEAD[/]" if self.is_head else ""
        return f"[bold]{self.node_id}[/]{head_marker}  {self.node_description}"


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
    #compare_placeholder,
    #actions_placeholder, #status_placeholder {
        width: 100%;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
        height: 100%;
    }

    /* DAG visualization */
    DAGDisplay {
        height: 1fr;
        padding: 1 2;
    }

    /* Dashboard split pane */
    #dashboard_split {
        height: 1fr;
    }

    #node_list_pane {
        width: 40%;
        border-right: solid $primary;
        padding: 1 1;
    }

    #detail_pane {
        width: 60%;
        padding: 1 2;
    }

    #session_status_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #session_status_info {
        color: $text-muted;
        margin-bottom: 2;
    }

    #dash_node_title {
        text-style: bold;
        margin-bottom: 1;
    }

    NodeRow {
        padding: 0 1;
        height: 1;
    }

    NodeRow:focus {
        background: $accent;
        color: $text;
    }

    NodeRow:hover {
        background: $surface-lighten-1;
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
                with Horizontal(id="dashboard_split"):
                    yield VerticalScroll(id="node_list_pane")
                    yield VerticalScroll(
                        Label("Session Status", id="session_status_title"),
                        Label("Loading...", id="session_status_info"),
                        Label("", id="dash_node_title"),
                        Label("", id="dash_node_info"),
                        id="detail_pane",
                    )
            with TabPane("DAG", id="tab_dag"):
                yield DAGDisplay(id="dag_content")
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
        """Handle Enter on NodeRow and numeric tab shortcuts (1-5)."""
        if isinstance(self.screen, ModalScreen):
            return
        if event.key == "enter":
            focused = self.focused
            if isinstance(focused, NodeRow):
                self.push_screen(NodeDetailModal(focused.node_id))
                event.prevent_default()
                event.stop()
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
        self._update_session_status()
        self._populate_node_list()
        self.query_one(DAGDisplay).load_dag(self.session_path)

    def _update_session_status(self) -> None:
        """Show session metadata in the right pane status area."""
        sd = self.session_data
        status = sd.get("status", "unknown")
        created = sd.get("created_at", "")
        updated = sd.get("updated_at", "")
        created_by = sd.get("created_by", "")
        node_count = len(list_nodes(self.session_path))
        head = get_head(self.session_path)

        info_lines = [
            f"Status: {status}" + (" [READ ONLY]" if self.read_only else ""),
            f"Nodes: {node_count}  HEAD: {head or 'none'}",
            f"Created: {created}  by {created_by}",
            f"Updated: {updated}",
            f"Path: {self.session_path}",
        ]
        self.query_one("#session_status_info", Label).update("\n".join(info_lines))

    def _populate_node_list(self) -> None:
        """Clear and repopulate the left pane with NodeRow widgets."""
        pane = self.query_one("#node_list_pane", VerticalScroll)
        pane.remove_children()

        nodes = list_nodes(self.session_path)
        head = get_head(self.session_path)

        if not nodes:
            pane.mount(Label("No nodes yet"))
            return

        for nid in nodes:
            node_data = read_node(self.session_path, nid)
            desc = node_data.get("description", "")
            row = NodeRow(nid, desc, is_head=(nid == head))
            pane.mount(row)

    def _show_node_detail(self, node_id: str) -> None:
        """Update the right pane with detail for the focused node."""
        try:
            node_data = read_node(self.session_path, node_id)
        except Exception:
            return

        desc = node_data.get("description", "")
        parents = node_data.get("parents", [])
        created = node_data.get("created_at", "")
        group = node_data.get("created_by_group", "")

        self.query_one("#dash_node_title", Label).update(f"Node: {node_id}")

        detail_lines = [
            f"Description: {desc}",
            f"Parents: {', '.join(parents) if parents else 'root'}",
            f"Created: {created}",
        ]
        if group:
            detail_lines.append(f"Group: {group}")

        dims = get_dimension_fields(node_data)
        if dims:
            detail_lines.append("")
            detail_lines.append("Dimensions:")
            for k, v in dims.items():
                detail_lines.append(f"  {k}: {v}")

        self.query_one("#dash_node_info", Label).update("\n".join(detail_lines))

    def on_descendant_focus(self, event) -> None:
        """When a NodeRow gets focus, update the detail pane."""
        if isinstance(event.widget, NodeRow):
            self._show_node_detail(event.widget.node_id)

    def on_dag_display_node_selected(self, event: DAGDisplay.NodeSelected) -> None:
        """Open node detail modal from DAG view."""
        self.push_screen(NodeDetailModal(event.node_id))

    def on_dag_display_head_changed(self, event: DAGDisplay.HeadChanged) -> None:
        """Update HEAD from DAG view."""
        if not self.read_only:
            set_head(self.session_path, event.node_id)
            self._populate_node_list()
            self._update_session_status()
            self.query_one(DAGDisplay).load_dag(self.session_path)

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
