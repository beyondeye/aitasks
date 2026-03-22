"""Brainstorm TUI: interactive design space exploration with Textual."""

from __future__ import annotations

import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

# Allow importing sibling packages (brainstorm, agentcrew)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)
from textual import on, work

from rich.text import Text

from brainstorm.brainstorm_dag import (
    get_dimension_fields,
    get_head,
    list_nodes,
    read_node,
    read_plan,
    read_proposal,
    set_head,
)
from brainstorm.brainstorm_schemas import extract_dimensions
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
    """Modal for viewing node details with tabbed content (Metadata, Proposal, Plan)."""

    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    def __init__(self, node_id: str, session_path: Path):
        super().__init__()
        self.node_id = node_id
        self.session_path = session_path

    def compose(self) -> ComposeResult:
        with Container(id="node_detail_dialog"):
            yield Label(
                f"Node Detail: {self.node_id}", id="node_detail_title"
            )
            with TabbedContent(id="node_detail_tabs"):
                with TabPane("Metadata", id="tab_metadata"):
                    yield VerticalScroll(
                        Static(id="metadata_content"),
                        id="metadata_scroll",
                    )
                with TabPane("Proposal", id="tab_proposal"):
                    yield VerticalScroll(
                        Markdown(id="proposal_content"),
                        id="proposal_scroll",
                    )
                with TabPane("Plan", id="tab_plan"):
                    yield VerticalScroll(
                        Markdown(id="plan_content"),
                        id="plan_scroll",
                    )
            with Horizontal(id="node_detail_buttons"):
                yield Button(
                    "Close", variant="default", id="btn_close_detail"
                )

    def on_mount(self) -> None:
        """Load node data into all three tabs."""
        try:
            node_data = read_node(self.session_path, self.node_id)
        except Exception:
            node_data = {}

        # --- Metadata tab ---
        parents = node_data.get("parents", [])
        desc = node_data.get("description", "")
        created = node_data.get("created_at", "")
        group = node_data.get("created_by_group", "")

        lines = [
            f"[bold]Node ID:[/bold] {self.node_id}",
            f"[bold]Parents:[/bold] {', '.join(parents) if parents else 'root'}",
            f"[bold]Description:[/bold] {desc}",
            f"[bold]Created:[/bold] {created}",
        ]
        if group:
            lines.append(f"[bold]Group:[/bold] {group}")

        dims = get_dimension_fields(node_data)
        if dims:
            lines.append("")
            lines.append("[bold]Dimensions:[/bold]")
            for k, v in dims.items():
                lines.append(f"  {k}: {v}")

        self.query_one("#metadata_content", Static).update("\n".join(lines))

        # --- Proposal tab ---
        try:
            proposal = read_proposal(self.session_path, self.node_id)
        except Exception:
            proposal = "*No proposal found.*"
        self.query_one("#proposal_content", Markdown).update(proposal)

        # --- Plan tab ---
        plan = read_plan(self.session_path, self.node_id)
        if plan is None:
            plan = "*No plan generated.*"
        self.query_one("#plan_content", Markdown).update(plan)

    @on(Button.Pressed, "#btn_close_detail")
    def close_detail(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class CompareNodeSelectModal(ModalScreen):
    """Modal for selecting 2-4 nodes to compare in the dimension matrix."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, node_ids: list[str]):
        super().__init__()
        self.node_ids = node_ids

    def compose(self) -> ComposeResult:
        with Container(id="compare_select_dialog"):
            yield Label("Select 2\u20134 nodes to compare", id="compare_select_title")
            with VerticalScroll(id="compare_checkbox_list"):
                for nid in self.node_ids:
                    yield Checkbox(nid, id=f"chk_cmp_{nid}")
            with Horizontal(id="compare_select_buttons"):
                yield Button("Compare", variant="primary", id="btn_compare")
                yield Button("Cancel", variant="default", id="btn_compare_cancel")

    def _get_selected(self) -> list[str]:
        return [
            nid
            for nid in self.node_ids
            if self.query_one(f"#chk_cmp_{nid}", Checkbox).value
        ]

    @on(Button.Pressed, "#btn_compare")
    def confirm(self) -> None:
        selected = self._get_selected()
        if len(selected) < 2:
            self.notify("Select at least 2 nodes", severity="warning")
            return
        if len(selected) > 4:
            self.notify("Select at most 4 nodes", severity="warning")
            return
        self.dismiss(selected)

    @on(Button.Pressed, "#btn_compare_cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
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
    #actions_placeholder, #status_placeholder {
        width: 100%;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
        height: 100%;
    }

    /* Compare tab */
    #compare_hint {
        width: 100%;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
        height: 100%;
    }

    #compare_table {
        height: 1fr;
    }

    /* Compare node selection modal */
    #compare_select_dialog {
        width: 60;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #compare_select_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #compare_checkbox_list {
        max-height: 20;
        padding: 0 1;
    }

    #compare_select_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
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
        height: 90%;
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

    #node_detail_tabs {
        height: 1fr;
    }

    #metadata_scroll, #proposal_scroll, #plan_scroll {
        height: 1fr;
        padding: 1 2;
    }

    #node_detail_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
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
                        "Press 'c' to select nodes for comparison",
                        id="compare_hint",
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
        """Handle Enter on NodeRow, compare keys, and numeric tab shortcuts."""
        if isinstance(self.screen, ModalScreen):
            return
        if event.key == "enter":
            focused = self.focused
            if isinstance(focused, NodeRow):
                self.push_screen(NodeDetailModal(focused.node_id, self.session_path))
                event.prevent_default()
                event.stop()
                return
        if event.key == "c":
            tabbed = self.query_one(TabbedContent)
            if tabbed.active == "tab_compare":
                nodes = list_nodes(self.session_path)
                if len(nodes) < 2:
                    self.notify("Need at least 2 nodes to compare", severity="warning")
                else:
                    self.push_screen(
                        CompareNodeSelectModal(nodes),
                        callback=self._on_compare_selected,
                    )
                event.prevent_default()
                event.stop()
                return
        if event.key == "d":
            tabbed = self.query_one(TabbedContent)
            if (
                tabbed.active == "tab_compare"
                and hasattr(self, "_compare_nodes")
                and len(self._compare_nodes) >= 2
            ):
                n1, n2 = self._compare_nodes[:2]
                p1 = self.session_path / "br_proposals" / f"{n1}.md"
                p2 = self.session_path / "br_proposals" / f"{n2}.md"
                if p1.is_file() and p2.is_file():
                    subprocess.Popen(["diff", "--color=always", str(p1), str(p2)])
                    self.notify(f"Diff launched: {n1} vs {n2}")
                else:
                    self.notify("Proposal files not found", severity="warning")
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
        self.push_screen(NodeDetailModal(event.node_id, self.session_path))

    def on_dag_display_head_changed(self, event: DAGDisplay.HeadChanged) -> None:
        """Update HEAD from DAG view."""
        if not self.read_only:
            set_head(self.session_path, event.node_id)
            self._populate_node_list()
            self._update_session_status()
            self.query_one(DAGDisplay).load_dag(self.session_path)

    def _on_compare_selected(self, selected: list[str] | None) -> None:
        """Handle CompareNodeSelectModal result."""
        if selected:
            self._build_compare_matrix(selected)

    def _build_compare_matrix(self, selected_nodes: list[str]) -> None:
        """Build dimension comparison matrix DataTable."""
        container = self.query_one("#compare_content", VerticalScroll)
        container.remove_children()

        # Extract dimensions for each node
        node_dims: dict[str, dict] = {}
        for nid in selected_nodes:
            data = read_node(self.session_path, nid)
            node_dims[nid] = extract_dimensions(data)

        # Collect all dimension keys (preserving first-seen order)
        all_keys: list[str] = []
        seen: set[str] = set()
        for dims in node_dims.values():
            for k in dims:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)

        if not all_keys:
            container.mount(Label("No dimension fields found in selected nodes"))
            return

        table = DataTable(id="compare_table")
        table.add_column("Dimension", key="dim")
        for nid in selected_nodes:
            table.add_column(nid, key=nid)

        # Add dimension rows with color-coded values
        for key in all_keys:
            raw_values = [str(node_dims[nid].get(key, "\u2014")) for nid in selected_nodes]

            # Determine color based on similarity
            unique = set(raw_values)
            if len(unique) == 1:
                color = "green"
            else:
                max_sim = 0.0
                for i, v1 in enumerate(raw_values):
                    for v2 in raw_values[i + 1 :]:
                        sim = SequenceMatcher(None, v1, v2).ratio()
                        if sim > max_sim:
                            max_sim = sim
                color = "yellow" if max_sim > 0.6 else "red"

            styled = [Text(v, style=color) for v in raw_values]
            table.add_row(key, *styled, key=key)

        # Add similarity score summary row
        self._add_similarity_row(table, selected_nodes, node_dims, all_keys)

        container.mount(table)
        self._compare_nodes = selected_nodes

    def _add_similarity_row(
        self,
        table: DataTable,
        nodes: list[str],
        node_dims: dict[str, dict],
        all_keys: list[str],
    ) -> None:
        """Add an average similarity score row to the compare table."""
        from itertools import combinations

        pair_avgs: list[float] = []
        for n1, n2 in combinations(nodes, 2):
            scores = []
            for key in all_keys:
                v1 = str(node_dims[n1].get(key, ""))
                v2 = str(node_dims[n2].get(key, ""))
                scores.append(SequenceMatcher(None, v1, v2).ratio())
            pair_avgs.append(sum(scores) / len(scores) if scores else 0.0)

        avg = sum(pair_avgs) / len(pair_avgs) if pair_avgs else 0.0
        label = Text("\u2014 Avg Similarity \u2014", style="bold")
        score = Text(f"{avg:.0%}", style="bold cyan")
        cells = [label, score] + [Text("")] * (len(nodes) - 1)
        table.add_row(*cells, key="sim_score")

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
