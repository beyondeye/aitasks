"""Brainstorm TUI: interactive design space exploration with Textual."""

from __future__ import annotations

import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

# Allow importing sibling packages (brainstorm, agentcrew)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from tui_switcher import TuiSwitcherMixin  # noqa: E402

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Label,
    Markdown,
    Static,
    Tabs,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual import on, work
from textual.message import Message
from textual.reactive import reactive

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
from brainstorm.brainstorm_sections import parse_sections
from brainstorm.brainstorm_dag_display import DAGDisplay
from brainstorm.brainstorm_session import (
    archive_session,
    crew_worktree,
    finalize_session,
    GROUPS_FILE,
    load_session,
    save_session,
    session_exists,
)
from brainstorm.brainstorm_crew import (
    register_comparator,
    register_detailer,
    register_explorer,
    register_patcher,
    register_synthesizer,
)
from agent_launch_utils import is_tmux_available
from launch_modes import DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES
from agentcrew.agentcrew_utils import list_agent_files, format_elapsed, read_yaml
from agentcrew.agentcrew_log_utils import (
    list_agent_logs,
    read_log_tail,
    read_log_full,
    format_log_size,
)
from agentcrew.agentcrew_runner_control import (
    get_runner_info,
    hard_kill_agent,
    send_agent_command,
    start_runner,
    stop_runner,
)
from agentcrew.agentcrew_process_stats import (
    get_all_agent_processes,
    get_runner_process_info,
    sync_stale_processes,
)
from agentcrew.agentcrew_utils import update_yaml_field

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

AGENT_STATUS_COLORS = {
    "Completed": "green",
    "Running": "yellow",
    "Waiting": "#BD93F9",
    "Ready": "cyan",
    "Error": "red",
    "Aborted": "red",
    "Paused": "#FFB86C",
}

_NODE_SELECT_OPS = {"explore", "detail", "patch"}

_WIZARD_OP_TO_AGENT_TYPE = {
    "explore": "explorer",
    "compare": "comparator",
    "hybridize": "synthesizer",
    "detail": "detailer",
    "patch": "patcher",
}


def _brainstorm_launch_mode_default(wizard_op: str) -> str:
    from pathlib import Path
    from brainstorm.brainstorm_crew import get_agent_types
    agent_type = _WIZARD_OP_TO_AGENT_TYPE.get(wizard_op, "")
    return get_agent_types(config_root=Path(".")).get(
        agent_type, {}
    ).get("launch_mode", DEFAULT_LAUNCH_MODE)


def _sections_intersection(node_sections: dict[str, list[str]]) -> list[str]:
    """Return sorted section names present in every node in the mapping.

    Used by the compare wizard step to derive sections comparable across the
    currently-checked nodes. Empty mapping or any empty per-node list returns [].
    """
    if not node_sections:
        return []
    sets = [set(names) for names in node_sections.values()]
    return sorted(set.intersection(*sets))


def _parse_section_label(label: str) -> str:
    """Extract a section name from a checkbox label (may include '[dims]' suffix)."""
    return label.split(" ", 1)[0]

_DESIGN_OPS = [
    ("explore", "Explore", "Create new design variants from a base node"),
    ("compare", "Compare", "Run agent comparison across nodes"),
    ("hybridize", "Hybridize", "Merge multiple nodes into a synthesis"),
    ("detail", "Detail", "Generate implementation plan for a node"),
    ("patch", "Patch", "Tweak an existing plan"),
]

_SESSION_OPS = [
    ("pause", "Pause", "Pause the active session"),
    ("resume", "Resume", "Resume a paused session"),
    ("finalize", "Finalize", "Copy HEAD plan to aiplans/ and mark completed"),
    ("archive", "Archive", "Mark completed session as archived"),
    ("delete", "Delete", "Permanently delete session, worktree, and branch"),
]


# ---------------------------------------------------------------------------
# Modal Screens
# ---------------------------------------------------------------------------


class _MarkdownOnlyDirectoryTree(DirectoryTree):
    """DirectoryTree that only lists directories and markdown files."""

    def filter_paths(self, paths):
        return [
            p for p in paths
            if p.is_dir() or p.suffix.lower() in (".md", ".markdown")
        ]


class ImportProposalFilePicker(ModalScreen):
    """Markdown-only file picker for the initial proposal import flow."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Container(id="import_picker_dialog"):
            yield Label(
                "Select a markdown file for the initial proposal",
                id="import_picker_title",
            )
            yield _MarkdownOnlyDirectoryTree(".", id="import_picker_tree")
            yield Label("↵ select  esc cancel", id="import_picker_footer")

    def on_directory_tree_file_selected(self, event) -> None:
        self.dismiss(str(Path(event.path).resolve()))

    def action_cancel(self) -> None:
        self.dismiss(None)


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
            yield Label("How would you like to initialize the session?")
            with Horizontal(id="init_buttons"):
                yield Button(
                    "Initialize Blank", variant="default", id="btn_init_blank"
                )
                yield Button(
                    "Import Proposal…", variant="primary", id="btn_init_import"
                )
                yield Button("Cancel", variant="default", id="btn_cancel")

    @on(Button.Pressed, "#btn_init_blank")
    def on_blank(self) -> None:
        self.dismiss("blank")

    @on(Button.Pressed, "#btn_init_import")
    def on_import(self) -> None:
        self.app.push_screen(
            ImportProposalFilePicker(),
            callback=self._on_picker_result,
        )

    def _on_picker_result(self, path: str | None) -> None:
        if path:
            self.dismiss(f"import:{path}")

    @on(Button.Pressed, "#btn_cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


_STALE_CREW_BRANCH_RE = re.compile(
    r"Branch '(crew-brainstorm-[\w\-]+)' already exists"
)


def detect_stale_crew_branch(error_text: str) -> str | None:
    """Return the stale `crew-brainstorm-<N>` branch name if the error names one."""
    m = _STALE_CREW_BRANCH_RE.search(error_text)
    return m.group(1) if m else None


class InitFailureModal(ModalScreen):
    """Modal shown when ``ait brainstorm init`` fails or its runner crashes.

    Replaces the previous fire-and-forget `notify(...)` + `app.exit()` pattern
    that swallowed the error message. Lets the user read the captured
    stderr/stdout and choose to retry the init flow or quit.

    When the captured error names a stale `crew-brainstorm-<N>` branch (the
    common failure mode after a prior aborted init), an extra button offers
    to delete the branch and re-run the init flow in one step.
    """

    BINDINGS = [Binding("escape", "quit", "Quit", show=False)]

    def __init__(self, error_text: str):
        super().__init__()
        self.error_text = error_text
        self.stale_branch = detect_stale_crew_branch(error_text)

    def compose(self) -> ComposeResult:
        with Container(id="init_failure_dialog"):
            yield Label("Brainstorm init failed", id="init_failure_title")
            if self.stale_branch:
                hint = (
                    f"A stale `{self.stale_branch}` branch is blocking init "
                    f"(likely left over from an aborted previous attempt). "
                    f"Use 'Delete branch & retry' to clean it up and rerun."
                )
            else:
                hint = (
                    "The init subprocess failed. Captured output below — "
                    "fix the underlying issue and Retry."
                )
            yield Label(hint, id="init_failure_hint")
            ta = TextArea(self.error_text, id="init_failure_output", read_only=True)
            ta.show_line_numbers = False
            yield ta
            with Horizontal(id="init_failure_buttons"):
                if self.stale_branch:
                    yield Button(
                        "Delete branch & retry",
                        variant="warning",
                        id="btn_init_failure_clean",
                    )
                yield Button("Retry", variant="primary", id="btn_init_failure_retry")
                yield Button("Quit", variant="default", id="btn_init_failure_quit")

    @on(Button.Pressed, "#btn_init_failure_clean")
    def on_clean(self) -> None:
        self.dismiss("clean_and_retry")

    @on(Button.Pressed, "#btn_init_failure_retry")
    def on_retry(self) -> None:
        self.dismiss("retry")

    @on(Button.Pressed, "#btn_init_failure_quit")
    def on_quit(self) -> None:
        self.dismiss("quit")

    def action_quit(self) -> None:
        self.dismiss("quit")


class DeleteSessionModal(ModalScreen):
    """Double-confirmation modal for deleting a brainstorm session."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, task_num: str):
        super().__init__()
        self.task_num = task_num
        self._confirmed_once = False

    def compose(self) -> ComposeResult:
        with Container(id="delete_dialog"):
            yield Label(
                f"Delete brainstorm session for t{self.task_num}?",
                id="delete_title",
            )
            yield Label(
                "This will permanently destroy:\n"
                "  \u2022 All session data (nodes, proposals, plans)\n"
                "  \u2022 The crew worktree directory\n"
                "  \u2022 The git branch (local and remote)",
                id="delete_details",
            )
            with Horizontal(id="delete_buttons"):
                yield Button("Delete", variant="error", id="btn_delete")
                yield Button("Cancel", variant="default", id="btn_delete_cancel")

    @on(Button.Pressed, "#btn_delete")
    def on_delete(self) -> None:
        if not self._confirmed_once:
            self._confirmed_once = True
            self.query_one("#delete_title", Label).update(
                "Are you sure? This cannot be undone."
            )
            self.query_one("#delete_details", Label).update(
                f"All brainstorm data for t{self.task_num} will be permanently lost."
            )
            self.query_one("#btn_delete", Button).label = "Yes, delete permanently"
        else:
            self.dismiss(True)

    @on(Button.Pressed, "#btn_delete_cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class NodeDetailModal(ModalScreen):
    """Modal for viewing node details with tabbed content (Metadata, Proposal, Plan)."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("tab", "focus_minimap", "Minimap"),
        Binding("V", "fullscreen_plan", "Fullscreen plan"),
    ]

    def __init__(self, node_id: str, session_path: Path):
        super().__init__()
        self.node_id = node_id
        self.session_path = session_path
        self._proposal_parsed = None
        self._proposal_text = ""
        self._plan_parsed = None
        self._plan_text = ""

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
        self._proposal_text = proposal
        parsed_proposal = parse_sections(proposal)
        if parsed_proposal.sections:
            self._proposal_parsed = parsed_proposal
            from section_viewer import SectionMinimap
            prop_scroll = self.query_one("#proposal_scroll", VerticalScroll)
            prop_minimap = SectionMinimap(id="proposal_minimap")
            prop_scroll.mount(prop_minimap, before="#proposal_content")
            prop_minimap.populate(parsed_proposal)

        # --- Plan tab ---
        plan = read_plan(self.session_path, self.node_id)
        if plan is None:
            plan = "*No plan generated.*"
        self.query_one("#plan_content", Markdown).update(plan)
        self._plan_text = plan
        parsed_plan = parse_sections(plan)
        if parsed_plan.sections:
            self._plan_parsed = parsed_plan
            from section_viewer import SectionMinimap
            plan_scroll = self.query_one("#plan_scroll", VerticalScroll)
            plan_minimap = SectionMinimap(id="plan_minimap")
            plan_scroll.mount(plan_minimap, before="#plan_content")
            plan_minimap.populate(parsed_plan)

    def on_section_minimap_section_selected(self, event) -> None:
        """Scroll the active tab's Markdown to the selected section."""
        from section_viewer import estimate_section_y
        minimap_id = event.control.id
        if minimap_id == "proposal_minimap":
            parsed, text, scroll_id = (
                self._proposal_parsed,
                self._proposal_text,
                "#proposal_scroll",
            )
        elif minimap_id == "plan_minimap":
            parsed, text, scroll_id = (
                self._plan_parsed,
                self._plan_text,
                "#plan_scroll",
            )
        else:
            return
        if parsed is None:
            return
        scroll = self.query_one(scroll_id, VerticalScroll)
        total = text.count("\n") + 1
        y = estimate_section_y(
            parsed, event.section_name, total, scroll.virtual_size.height
        )
        if y is not None:
            scroll.scroll_to(y=y, animate=False)
        event.stop()

    def on_section_minimap_toggle_focus(self, event) -> None:
        """Minimap Tab → focus the matching tab's Markdown."""
        if event.control.id == "proposal_minimap":
            self.query_one("#proposal_content", Markdown).focus()
        elif event.control.id == "plan_minimap":
            self.query_one("#plan_content", Markdown).focus()
        event.stop()

    def action_focus_minimap(self) -> None:
        """Tab from Markdown → focus the active tab's minimap. SkipAction falls through to default Tab-nav."""
        from textual.actions import SkipAction
        tabbed = self.query_one(TabbedContent)
        focused = self.screen.focused
        if tabbed.active == "tab_proposal":
            md_sel, mm_sel = "#proposal_content", "#proposal_minimap"
        elif tabbed.active == "tab_plan":
            md_sel, mm_sel = "#plan_content", "#plan_minimap"
        else:
            raise SkipAction()
        try:
            md = self.query_one(md_sel, Markdown)
        except Exception:
            raise SkipAction()
        if focused is not md:
            raise SkipAction()
        minimaps = self.query(mm_sel)
        if not minimaps:
            raise SkipAction()
        minimaps.first().focus_first_row()

    def action_fullscreen_plan(self) -> None:
        """V → push SectionViewerScreen for the active tab's content."""
        tabbed = self.query_one(TabbedContent)
        if tabbed.active == "tab_proposal":
            content = self._proposal_text
            title = f"Proposal: {self.node_id}"
        elif tabbed.active == "tab_plan":
            content = self._plan_text
            title = f"Plan: {self.node_id}"
        else:
            self.notify(
                "Fullscreen viewer only works on Proposal or Plan tab",
                severity="warning",
            )
            return
        if not content:
            self.notify("No content on this tab", severity="warning")
            return
        from section_viewer import SectionViewerScreen
        self.app.push_screen(SectionViewerScreen(content, title=title))

    @on(Button.Pressed, "#btn_close_detail")
    def close_detail(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class AgentModeEditModal(ModalScreen):
    """Modal to pick an agent's launch_mode from VALID_LAUNCH_MODES."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        agent_name: str,
        agent_status: str,
        current_mode: str,
    ):
        super().__init__()
        self.agent_name = agent_name
        self.agent_status = agent_status
        self.current_mode = current_mode

    def compose(self) -> ComposeResult:
        with Container(id="mode_modal_dialog"):
            yield Label(
                f"Launch mode: {self.agent_name}",
                id="mode_modal_title",
            )
            yield Static(
                f"Current: [bold]{self.current_mode}[/bold]  "
                f"Status: {self.agent_status}",
                id="mode_modal_current",
            )
            if self.agent_status != "Waiting":
                yield Static(
                    "[dim]launch_mode can only be changed on Waiting agents. "
                    "Close this dialog and reset the agent first if needed.[/]",
                    id="mode_modal_note",
                )
                with Horizontal(id="mode_modal_buttons"):
                    yield Button("Close", variant="default", id="btn_mode_close")
            else:
                with Horizontal(id="mode_modal_buttons"):
                    for mode in sorted(VALID_LAUNCH_MODES):
                        yield Button(
                            mode.replace("_", " ").title(),
                            variant=(
                                "primary"
                                if self.current_mode == mode
                                else "default"
                            ),
                            id=f"btn_mode_{mode}",
                        )
                    yield Button("Cancel", variant="default", id="btn_mode_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid in ("btn_mode_cancel", "btn_mode_close"):
            self.dismiss(None)
            return
        if bid.startswith("btn_mode_"):
            mode = bid[len("btn_mode_"):]
            if mode in VALID_LAUNCH_MODES:
                self.dismiss(mode)
                return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class LogDetailModal(ModalScreen):
    """Modal for viewing agent log file content with Tail/Full tabs."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("r", "refresh", "Refresh"),
        Binding("t", "show_tail", "Tail"),
        Binding("f", "show_full", "Full"),
    ]

    def __init__(self, log_path: str, agent_name: str):
        super().__init__()
        self.log_path = log_path
        self.agent_name = agent_name

    def compose(self) -> ComposeResult:
        import os

        size = format_log_size(os.path.getsize(self.log_path)) if os.path.isfile(self.log_path) else "0 B"
        with Container(id="log_modal_container"):
            yield Label(
                f"Log: {self.agent_name}  ({size})", id="log_modal_title"
            )
            with TabbedContent(id="log_modal_tabs"):
                with TabPane("Tail", id="tab_log_tail"):
                    yield VerticalScroll(
                        Static(id="log_tail_content"),
                        id="log_tail_scroll",
                    )
                with TabPane("Full", id="tab_log_full"):
                    yield VerticalScroll(
                        Static(id="log_full_content"),
                        id="log_full_scroll",
                    )
            with Horizontal(id="log_modal_buttons"):
                yield Button(
                    "Close", variant="default", id="btn_close_log"
                )

    def on_mount(self) -> None:
        self._load_tail()
        self._load_full()

    def _load_tail(self) -> None:
        content = read_log_tail(self.log_path) or "(empty)"
        self.query_one("#log_tail_content", Static).update(content)

    def _load_full(self) -> None:
        content = read_log_full(self.log_path) or "(empty)"
        self.query_one("#log_full_content", Static).update(content)

    def _update_header(self) -> None:
        import os

        size = format_log_size(os.path.getsize(self.log_path)) if os.path.isfile(self.log_path) else "0 B"
        self.query_one("#log_modal_title", Label).update(
            f"Log: {self.agent_name}  ({size})"
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def action_refresh(self) -> None:
        self._update_header()
        self._load_tail()
        self._load_full()
        self.notify("Refreshed")

    def action_show_tail(self) -> None:
        self.query_one("#log_modal_tabs", TabbedContent).active = "tab_log_tail"

    def action_show_full(self) -> None:
        self.query_one("#log_modal_tabs", TabbedContent).active = "tab_log_full"

    @on(Button.Pressed, "#btn_close_log")
    def close_log(self) -> None:
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


class OperationRow(Static):
    """Focusable row representing an operation in the Actions wizard."""

    selected = reactive(False)

    class Activated(Message):
        """Emitted when an OperationRow is clicked (mouse activation)."""

        def __init__(self, row: OperationRow) -> None:
            super().__init__()
            self.row = row

    def __init__(self, op_key: str, label: str, description: str, disabled: bool = False):
        super().__init__()
        self.op_key = op_key
        self.op_label = label
        self.op_description = description
        self.op_disabled = disabled
        self.can_focus = not disabled

    def render(self) -> str:
        if self.op_disabled:
            return f"[dim strikethrough]{self.op_label}[/]  [dim]{self.op_description}[/]"
        marker = "[bold cyan]> [/]" if self.selected else "  "
        return f"{marker}[bold]{self.op_label}[/]  {self.op_description}"

    def on_click(self) -> None:
        """Focus and activate this row when clicked."""
        if not self.op_disabled:
            self.focus()
            self.post_message(self.Activated(self))


class CycleField(Static):
    """Minimal cycle widget for numeric option selection (left/right keys)."""

    def __init__(self, label: str, options: list[str], initial: str = "", *, id: str | None = None):
        super().__init__(id=id)
        self.label = label
        self.options = options
        self.current_index = options.index(initial) if initial in options else 0
        self.can_focus = True

    @property
    def current_value(self) -> str:
        return self.options[self.current_index]

    def render(self) -> str:
        parts = []
        for i, opt in enumerate(self.options):
            if i == self.current_index:
                parts.append(f"[bold reverse] {opt} [/]")
            else:
                parts.append(f" {opt} ")
        return f"  {self.label}:  [dim]\u25c0[/] {'|'.join(parts)} [dim]\u25b6[/]"

    def on_key(self, event) -> None:
        if event.key == "left":
            self.current_index = (self.current_index - 1) % len(self.options)
            self.refresh()
            event.prevent_default()
            event.stop()
        elif event.key == "right":
            self.current_index = (self.current_index + 1) % len(self.options)
            self.refresh()
            event.prevent_default()
            event.stop()


class GroupRow(Static, can_focus=True):
    """Expandable group row in the Status tab."""

    def __init__(self, name: str, info: dict, expanded: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.group_name = name
        self.group_info = info
        self.expanded = expanded

    def render(self) -> str:
        arrow = "\u25bc" if self.expanded else "\u25b6"
        op = self.group_info.get("operation", "?")
        status = self.group_info.get("status", "?")
        color = AGENT_STATUS_COLORS.get(status, "#888888")
        agents = self.group_info.get("agents", [])
        created = self.group_info.get("created_at", "")
        return (
            f"{arrow} [bold]{self.group_name}[/bold]  {op}  "
            f"[{color}]{status}[/{color}]  agents: {len(agents)}  {created}"
        )

    def on_click(self) -> None:
        self.focus()


class StatusLogRow(Static, can_focus=True):
    """Focusable row displaying an agent log file entry in the Status tab."""

    def __init__(self, log_info: dict, **kwargs):
        super().__init__(**kwargs)
        self.log_info = log_info

    def render(self) -> str:
        name = self.log_info["name"]
        size = format_log_size(self.log_info["size"])
        mtime = self.log_info["mtime_str"]
        return f"  {name}  [{size}]  Last updated: {mtime}"

    def on_click(self) -> None:
        self.focus()


class AgentStatusRow(Static, can_focus=True):
    """Focusable agent status row in the Status tab. Supports reset via 'w' key."""

    def __init__(self, name: str, status: str, display_line: str, crew_id: str, **kwargs):
        super().__init__(**kwargs)
        self.agent_name = name
        self.agent_status = status
        self.crew_id = crew_id
        self._display_line = display_line

    def render(self) -> str:
        line = self._display_line
        if self.has_focus:
            hints = []
            if self.agent_status == "Error":
                hints.append("w: reset")
            elif self.agent_status == "Waiting":
                hints.append("e: edit mode")
            log_path = Path(crew_worktree(self.crew_id)) / f"{self.agent_name}_log.txt"
            if log_path.exists():
                hints.append("L: log")
            if hints:
                line += "  [dim](" + " | ".join(hints) + ")[/dim]"
        return line

    def on_click(self) -> None:
        self.focus()

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()


class ProcessRow(Static, can_focus=True):
    """Focusable process row in the Status tab. Supports p/k/K actions."""

    def __init__(self, proc_data: dict, crew_id: str, **kwargs):
        super().__init__(**kwargs)
        self.proc_data = proc_data
        self.crew_id = crew_id
        self.agent_name = proc_data["agent_name"]

    def render(self) -> str:
        d = self.proc_data
        alive = d.get("process_alive", False)
        status = d.get("status", "")

        if alive and status == "Running":
            dot = "[green]\u25cf[/]"
        elif status == "Paused":
            dot = "[yellow]\u25cf[/]"
        elif not alive:
            dot = "[red]\u25cf[/]"
        else:
            dot = "[dim]\u25cf[/]"

        pid_str = str(d.get("pid", "?"))
        wall = format_elapsed(d["wall_time"]) if d.get("wall_time") is not None else "?"
        cpu = f'{d["cpu_time"]:.1f}s' if d.get("cpu_time") is not None else "?"
        rss = f'{d["memory_rss_mb"]:.0f}MB' if d.get("memory_rss_mb") is not None else "?"
        hb = d.get("heartbeat_age", "?")

        line = f"{dot} {d['agent_name']}  PID:{pid_str}  Wall:{wall}  CPU:{cpu}  RSS:{rss}  HB:{hb}"
        if not alive:
            line += "  [red]DEAD[/]"
        if self.has_focus:
            line += "  [dim](p:pause  k:kill  K:hard kill)[/dim]"
        return line

    def on_click(self) -> None:
        self.focus()

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


class BrainstormApp(TuiSwitcherMixin, App):
    """Textual app for interactive brainstorm session orchestration."""

    TITLE = "ait brainstorm"

    CSS = """
    Screen {
        align: center middle;
    }

    .initializer-banner {
        display: none;
        background: $error;
        color: $text;
        padding: 0 1;
        height: 1;
    }

    .initializer-banner.visible {
        display: block;
    }

    #brainstorm_tabs {
        height: 1fr;
    }

    VerticalScroll {
        padding: 1 2;
    }

    /* Status tab */
    GroupRow {
        height: auto;
        padding: 0 1;
    }

    GroupRow:focus {
        background: $accent;
        color: $text;
    }

    GroupRow:hover {
        background: $surface-lighten-1;
    }

    .status_section_title {
        text-style: bold;
        margin-top: 1;
    }

    .status_agent_detail {
        padding: 0 3;
        height: auto;
    }

    AgentStatusRow {
        padding: 0 3;
        height: auto;
    }

    AgentStatusRow:focus {
        background: $accent;
        color: $text;
    }

    AgentStatusRow:hover {
        background: $surface-lighten-1;
    }

    ProcessRow {
        height: auto;
        padding: 0 3;
    }

    ProcessRow:focus {
        background: $accent;
        color: $text;
    }

    ProcessRow:hover {
        background: $surface-lighten-1;
    }

    ProcessRow.-dead {
        opacity: 0.6;
    }

    .status_output_preview {
        padding: 0 5;
        color: $text-muted;
        height: auto;
    }

    .status_empty {
        width: 100%;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
        height: 100%;
    }

    /* Actions wizard */
    .actions_step_indicator {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: $accent;
    }

    .actions_section_title {
        text-style: bold;
        margin-top: 1;
    }

    OperationRow {
        padding: 0 1;
        height: 1;
    }

    OperationRow:focus {
        background: $accent;
        color: $text;
    }

    OperationRow:hover {
        background: $surface-lighten-1;
    }

    CycleField {
        height: 1;
        padding: 0 1;
    }

    CycleField:focus {
        background: $accent;
    }

    .actions_summary {
        padding: 1 2;
    }

    .actions_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
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

    /* Delete session modal */
    #delete_dialog {
        width: 60;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }

    #delete_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #delete_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
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

    /* Init failure modal */
    #init_failure_dialog {
        width: 90%;
        height: 80%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }

    #init_failure_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: $error;
    }

    #init_failure_hint {
        width: 100%;
        margin-bottom: 1;
    }

    #init_failure_output {
        height: 1fr;
        margin-bottom: 1;
    }

    #init_failure_buttons {
        height: 3;
        align: center middle;
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

    /* Agent launch-mode edit modal */
    #mode_modal_dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #mode_modal_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }

    #mode_modal_current {
        padding-bottom: 1;
    }

    #mode_modal_note {
        padding-bottom: 1;
    }

    #mode_modal_buttons {
        height: 3;
        align: center middle;
    }

    /* Log browsing widgets (t439_4) */
    StatusLogRow { height: 1; padding: 0 1; }
    StatusLogRow:focus { background: $accent 20%; }

    #log_modal_container {
        width: 90%;
        height: 85%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    #log_modal_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #log_modal_tabs { height: 1fr; }

    #log_tail_scroll, #log_full_scroll {
        height: 1fr;
        padding: 1 2;
    }

    #log_modal_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    .runner_bar { height: auto; padding: 0 1; margin-bottom: 1; }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        Binding("q", "quit", "Quit"),
        Binding("d", "tab_dashboard", "Dashboard"),
        Binding("g", "tab_graph", "Graph"),
        Binding("c", "tab_compare", "Compare"),
        Binding("a", "tab_actions", "Actions"),
        Binding("s", "tab_status", "Status"),
        Binding("ctrl+r", "retry_initializer_apply", "Retry initializer apply"),
    ]

    def __init__(self, task_num: str):
        super().__init__()
        self.current_tui_name = f"brainstorm-{task_num}"
        self.task_num = task_num
        self.session_path = crew_worktree(task_num)
        self.session_data: dict = {}
        self.read_only: bool = False
        self._wizard_step: int = 0
        self._wizard_total_steps: int = 3
        self._wizard_op: str = ""
        self._wizard_config: dict = {}
        self._wizard_has_sections: bool = False
        self._cmp_section_checks: dict[str, bool] = {}
        self._expanded_groups: set[str] = set()
        self._status_refresh_timer = None
        self._processes_synced: bool = False
        self._initializer_agent: str | None = None
        self._initializer_done: bool = False
        self._initializer_timer = None
        self._initializer_apply_error: str | None = None
        self._applying_initializer: bool = False
        self._update_title_from_task()

    def _resolve_task_file_path(self) -> Path | None:
        """Return the task file path for self.task_num, or None if not found."""
        tf = self.session_data.get("task_file") if self.session_data else None
        if tf:
            p = Path(tf)
            if p.exists():
                return p
        matches = sorted(Path("aitasks").glob(f"t{self.task_num}_*.md"))
        return matches[0] if matches else None

    def _update_title_from_task(self) -> None:
        """Set sub_title to include task id and full task name."""
        path = self._resolve_task_file_path()
        if path is not None:
            stem = path.stem
            prefix = f"t{self.task_num}_"
            name_part = stem[len(prefix):] if stem.startswith(prefix) else stem
            self.sub_title = f"t{self.task_num} — {name_part}"
        else:
            self.sub_title = f"t{self.task_num}"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="initializer_apply_banner", classes="initializer-banner")
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
            with TabPane("Graph", id="tab_dag"):
                yield DAGDisplay(id="dag_content")
            with TabPane("Compare", id="tab_compare"):
                yield VerticalScroll(
                    Label(
                        "Press 'c' to select nodes for comparison, 'D' to diff",
                        id="compare_hint",
                    ),
                    id="compare_content",
                )
            with TabPane("Actions", id="tab_actions"):
                yield VerticalScroll(id="actions_content")
            with TabPane("Status", id="tab_status"):
                yield VerticalScroll(id="status_content")
        yield Footer()

    def on_key(self, event) -> None:
        """Handle Enter on NodeRow, compare keys, wizard nav, and arrow navigation."""
        if isinstance(self.screen, ModalScreen):
            return
        tabbed = self.query_one(TabbedContent)

        # Down from tab bar: focus first row in active tab
        if event.key == "down":
            tabs_widget = tabbed.query_one(Tabs)
            if self.focused is tabs_widget:
                tab_to_container = {
                    "tab_dashboard": ("node_list_pane", (NodeRow,)),
                    "tab_actions": ("actions_content", (OperationRow,)),
                    "tab_status": ("status_content", (GroupRow, AgentStatusRow, StatusLogRow)),
                }
                mapping = tab_to_container.get(tabbed.active)
                if mapping:
                    if self._navigate_rows(1, mapping[0], mapping[1]):
                        event.prevent_default()
                        event.stop()
                        return

        # Up/down: navigate NodeRow items in Dashboard
        if event.key in ("up", "down") and tabbed.active == "tab_dashboard":
            direction = 1 if event.key == "down" else -1
            if self._navigate_rows(direction, "node_list_pane", (NodeRow,)):
                event.prevent_default()
                event.stop()
                return

        # Up on Graph/Compare tab: focus tab bar directly
        if event.key == "up" and tabbed.active in ("tab_dag", "tab_compare"):
            tabs_widget = tabbed.query_one(Tabs)
            tabs_widget.focus()
            event.prevent_default()
            event.stop()
            return

        # Actions tab wizard navigation
        if tabbed.active == "tab_actions" and self._wizard_step > 0:
            # Esc: go back to previous wizard step
            if event.key == "escape" and self._wizard_step > 1:
                step = self._wizard_step
                total = self._wizard_total_steps
                if step == total:
                    # From confirm step
                    if self._wizard_op == "detail":
                        if self._wizard_has_sections:
                            self._actions_show_section_select()
                        else:
                            self._actions_show_node_select()
                    elif self._wizard_op in ("explore", "patch", "compare", "hybridize"):
                        self._actions_show_config()
                    else:
                        self._actions_show_config()
                elif (
                    step == total - 1
                    and self._wizard_op in ("explore", "patch")
                ):
                    # From config step
                    if self._wizard_has_sections:
                        self._actions_show_section_select()
                    else:
                        self._actions_show_node_select()
                elif step == 3 and self._wizard_has_sections:
                    # From section-select step
                    self._actions_show_node_select()
                elif step == 2:
                    self._actions_show_step1()
                event.prevent_default()
                event.stop()
                return
            # Enter on step 1: select operation
            if event.key == "enter" and self._wizard_step == 1:
                focused = self.focused
                if isinstance(focused, OperationRow) and not focused.op_disabled:
                    self._wizard_op = focused.op_key
                    self._set_total_steps()
                    if self._wizard_op == "delete":
                        self.push_screen(
                            DeleteSessionModal(self.task_num),
                            self._on_delete_result,
                        )
                    elif self._wizard_op in ("pause", "resume", "finalize", "archive"):
                        self._wizard_config = {"confirmed": True}
                        self._actions_show_confirm()
                    else:
                        self._actions_show_step2()
                    event.prevent_default()
                    event.stop()
                    return
            # Enter on step 2 node select: select node and advance
            if event.key == "enter" and self._wizard_step == 2:
                focused = self.focused
                if isinstance(focused, OperationRow) and not focused.op_disabled:
                    if self._wizard_op in _NODE_SELECT_OPS:
                        self._wizard_config["_selected_node"] = focused.op_key
                        if self._wizard_op == "detail":
                            self._wizard_config["node"] = focused.op_key
                            self._actions_show_confirm()
                        else:
                            self._actions_show_config()
                        event.prevent_default()
                        event.stop()
                        return
            # Up/down: navigate OperationRow widgets in wizard steps 1-2
            if event.key in ("up", "down") and self._wizard_step in (1, 2):
                direction = 1 if event.key == "down" else -1
                if self._navigate_rows(direction, "actions_content", (OperationRow,)):
                    event.prevent_default()
                    event.stop()
                    return
            # Up/down: cycle focus among focusable widgets on the confirm step
            if (
                event.key in ("up", "down")
                and self._wizard_step == self._wizard_total_steps
            ):
                if self._cycle_confirm_focus(1 if event.key == "down" else -1):
                    event.prevent_default()
                    event.stop()
                    return

        # Enter key handlers for various focusable rows
        if event.key == "enter":
            focused = self.focused
            if isinstance(focused, GroupRow):
                name = focused.group_name
                if name in self._expanded_groups:
                    self._expanded_groups.discard(name)
                else:
                    self._expanded_groups.add(name)
                self._refresh_status_tab()
                event.prevent_default()
                event.stop()
                return
            if isinstance(focused, StatusLogRow):
                self.push_screen(LogDetailModal(focused.log_info["path"], focused.log_info["name"]))
                event.prevent_default()
                event.stop()
                return
            if isinstance(focused, NodeRow):
                self.push_screen(NodeDetailModal(focused.node_id, self.session_path))
                event.prevent_default()
                event.stop()
                return

        # Shift+D: diff proposals on Compare tab (was 'd', now 'D' to avoid Dashboard shortcut conflict)
        if event.key == "D":
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

        # b: show task brief
        if event.key == "b":
            spec = getattr(self, "session_data", {}).get("initial_spec", "")
            if spec:
                self._show_brief_in_detail(spec)
            else:
                self.notify("No task brief available", severity="warning")
            event.prevent_default()
            event.stop()
            return

        # w: reset agent in Error state
        if event.key == "w":
            focused = self.focused
            if isinstance(focused, AgentStatusRow):
                if focused.agent_status != "Error":
                    self.notify(
                        f"Can only reset agents in Error state (current: {focused.agent_status})",
                        severity="warning",
                    )
                else:
                    self._reset_agent(focused)
                event.prevent_default()
                event.stop()
                return

        # e: edit launch_mode on a Waiting agent
        if event.key == "e":
            focused = self.focused
            if isinstance(focused, AgentStatusRow):
                if focused.agent_status != "Waiting":
                    self.notify(
                        f"Can only edit launch_mode on Waiting agents "
                        f"(current: {focused.agent_status})",
                        severity="warning",
                    )
                else:
                    self._edit_agent_mode(focused)
                event.prevent_default()
                event.stop()
                return

        # L: open log viewer for focused agent row
        if event.key == "L":
            focused = self.focused
            if isinstance(focused, AgentStatusRow):
                crew_dir = crew_worktree(focused.crew_id)
                log_path = Path(crew_dir) / f"{focused.agent_name}_log.txt"
                if not log_path.exists():
                    self.notify(
                        f"No log yet for {focused.agent_name}",
                        severity="warning",
                    )
                else:
                    try:
                        subprocess.Popen(
                            ["./ait", "crew", "logview", "--path", str(log_path)],
                        )
                        self.notify(f"Opening log for {focused.agent_name}")
                    except OSError as exc:
                        self.notify(
                            f"Failed to open log viewer: {exc}",
                            severity="error",
                        )
                event.prevent_default()
                event.stop()
                return

        # Process actions on focused ProcessRow
        if isinstance(self.focused, ProcessRow):
            proc_row = self.focused
            if event.key == "p":
                status = proc_row.proc_data.get("status", "")
                cmd = "resume" if status == "Paused" else "pause"
                ok = send_agent_command(proc_row.crew_id, proc_row.agent_name, cmd)
                self.notify(
                    f"{'Resumed' if cmd == 'resume' else 'Paused'} {proc_row.agent_name}"
                    if ok else f"Failed to {cmd} {proc_row.agent_name}",
                    severity="information" if ok else "error",
                )
                self.set_timer(2.0, self._refresh_status_tab)
                event.prevent_default()
                event.stop()
                return
            elif event.key == "k":
                ok = send_agent_command(proc_row.crew_id, proc_row.agent_name, "kill")
                self.notify(
                    f"Kill sent to {proc_row.agent_name}" if ok
                    else f"Failed to send kill to {proc_row.agent_name}",
                    severity="information" if ok else "error",
                )
                self.set_timer(2.0, self._refresh_status_tab)
                event.prevent_default()
                event.stop()
                return
            elif event.key == "K":
                result = hard_kill_agent(proc_row.crew_id, proc_row.agent_name)
                self.notify(
                    result["message"],
                    severity="information" if result["success"] else "error",
                )
                if result["success"]:
                    self.set_timer(2.0, self._refresh_status_tab)
                event.prevent_default()
                event.stop()
                return

        # Up/down: navigate focusable rows in Status tab
        if event.key in ("up", "down") and tabbed.active == "tab_status":
            direction = 1 if event.key == "down" else -1
            if self._navigate_rows(direction, "status_content", (GroupRow, AgentStatusRow, ProcessRow, StatusLogRow)):
                event.prevent_default()
                event.stop()
                return

    # ------------------------------------------------------------------
    # Tab switching actions (shown in Footer via BINDINGS)
    # ------------------------------------------------------------------

    def action_tab_dashboard(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.query_one(TabbedContent).active = "tab_dashboard"

    def action_tab_graph(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.query_one(TabbedContent).active = "tab_dag"

    def action_tab_compare(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        tabbed = self.query_one(TabbedContent)
        if tabbed.active == "tab_compare":
            # Already on compare — trigger compare node select
            nodes = list_nodes(self.session_path)
            if len(nodes) < 2:
                self.notify("Need at least 2 nodes to compare", severity="warning")
            else:
                self.push_screen(
                    CompareNodeSelectModal(nodes),
                    callback=self._on_compare_selected,
                )
            return
        tabbed.active = "tab_compare"

    def action_tab_actions(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.query_one(TabbedContent).active = "tab_actions"

    def action_tab_status(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.query_one(TabbedContent).active = "tab_status"

    # ------------------------------------------------------------------
    # Keyboard navigation helper
    # ------------------------------------------------------------------

    def _navigate_rows(self, direction: int, container_id: str, row_types: tuple) -> bool:
        """Navigate up/down among focusable rows in a container.

        Returns True if the event was handled.
        direction: -1 for up, +1 for down.
        """
        try:
            container = self.query_one(f"#{container_id}", VerticalScroll)
        except Exception:
            return False

        focusable = [w for w in container.children if isinstance(w, row_types) and w.can_focus]
        if not focusable:
            return False

        focused = self.focused
        tabbed = self.query_one(TabbedContent)
        tabs_widget = tabbed.query_one(Tabs)

        # If focus is on the Tabs bar and direction is down, focus first row
        if focused is tabs_widget:
            if direction == 1:
                focusable[0].focus()
                focusable[0].scroll_visible()
                return True
            return False

        # If no row is focused, focus the first (down) or last (up) row
        if not isinstance(focused, row_types):
            target = focusable[0] if direction == 1 else focusable[-1]
            target.focus()
            target.scroll_visible()
            return True

        # Find current index
        try:
            idx = focusable.index(focused)
        except ValueError:
            focusable[0].focus()
            focusable[0].scroll_visible()
            return True

        new_idx = idx + direction

        # At boundary: up past top → focus tabs; down past bottom → stop
        if new_idx < 0:
            tabs_widget.focus()
            return True
        if new_idx >= len(focusable):
            return True  # Stop at bottom, don't wrap

        focusable[new_idx].focus()
        focusable[new_idx].scroll_visible()
        return True

    def _cycle_confirm_focus(self, direction: int) -> bool:
        """Cycle focus among focusable descendants of the confirm step container.

        direction: +1 down, -1 up. Returns True if focus moved.
        """
        try:
            container = self.query_one("#actions_content", VerticalScroll)
        except Exception:
            return False

        focusable = [
            w for w in container.query("*")
            if getattr(w, "can_focus", False) and not getattr(w, "disabled", False)
        ]
        if not focusable:
            return False

        current = self.focused
        if current in focusable:
            idx = focusable.index(current)
            new_idx = (idx + direction) % len(focusable)
        else:
            new_idx = 0 if direction == 1 else len(focusable) - 1

        focusable[new_idx].focus()
        try:
            focusable[new_idx].scroll_visible()
        except Exception:
            pass
        return True

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
        self._update_title_from_task()
        status = self.session_data.get("status", "")
        if status in ("completed", "archived"):
            self.read_only = True
        self._update_session_status()
        self._populate_node_list()
        self.query_one(DAGDisplay).load_dag(self.session_path)
        self._actions_show_step1()
        self._status_refresh_timer = self.set_interval(30, self._refresh_status_tab)
        self._try_apply_initializer_if_needed()

    def _try_apply_initializer_if_needed(self, force: bool = False) -> None:
        """Re-attempt apply_initializer_output if n000_init is still placeholder.

        Called on session load, on initializer poll completion, and via the
        ctrl+r manual-retry binding. Surfaces failures via a persistent
        banner widget rather than a fading toast.
        """
        if self._applying_initializer:
            return
        from brainstorm.brainstorm_session import (
            n000_needs_apply,
            apply_initializer_output,
        )
        if not force and not n000_needs_apply(self.task_num):
            return
        self._applying_initializer = True
        try:
            apply_initializer_output(self.task_num)
        except Exception as exc:
            self._initializer_apply_error = str(exc)
            self._set_apply_banner(
                f"Initializer apply failed: {exc} — "
                f"run `ait brainstorm apply-initializer {self.task_num}` to retry"
            )
        else:
            self._initializer_apply_error = None
            self._clear_apply_banner()
            self.notify("Initial proposal imported.")
            self._load_existing_session()
        finally:
            self._applying_initializer = False

    def _set_apply_banner(self, msg: str) -> None:
        try:
            widget = self.query_one("#initializer_apply_banner", Static)
            widget.update(msg)
            widget.add_class("visible")
        except Exception:
            pass

    def _clear_apply_banner(self) -> None:
        try:
            widget = self.query_one("#initializer_apply_banner", Static)
            widget.update("")
            widget.remove_class("visible")
        except Exception:
            pass

    def action_retry_initializer_apply(self) -> None:
        """ctrl+r: force-retry the initializer apply, even if not flagged."""
        self._try_apply_initializer_if_needed(force=True)

    def on_tabbed_content_tab_activated(self, event) -> None:
        """Refresh Status tab when it becomes active."""
        if event.pane.id == "tab_status":
            self._refresh_status_tab()

    def _refresh_status_tab(self) -> None:
        """Populate the Status tab with operation groups and agent statuses."""
        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab_status":
            return

        import os

        wt_path = str(self.session_path)
        container = self.query_one("#status_content", VerticalScroll)
        container.remove_children()

        if not os.path.isdir(wt_path):
            container.mount(Label("Crew worktree not found", classes="status_empty"))
            return

        # Runner status section
        crew_id = self.session_data.get("crew_id", "")
        if crew_id:
            runner = get_runner_info(crew_id)
            status = runner["status"]
            stale = runner["stale"]

            if status == "none":
                status_text = "No runner"
                color = "#888888"
            elif status == "stopped":
                status_text = "Runner stopped"
                color = "#888888"
            elif stale:
                status_text = "Runner stale"
                color = "#FF5555"
            else:
                status_text = "Runner active"
                color = "#50FA7B"

            info_parts = [f"[{color}]{status_text}[/{color}]"]
            if runner.get("hostname"):
                info_parts.append(f"Host: {runner['hostname']}")
            hb_age = runner.get("heartbeat_age", "never")
            if hb_age != "never":
                info_parts.append(f"Heartbeat: {hb_age}")

            # Augment with OS-level stats
            runner_proc = get_runner_process_info(crew_id)
            if runner_proc and runner_proc.get("pid") and not runner_proc.get("remote"):
                extra = []
                extra.append(f"PID: {runner_proc['pid']}")
                if runner_proc.get("cpu_time") is not None:
                    extra.append(f"CPU: {runner_proc['cpu_time']:.1f}s")
                if runner_proc.get("memory_rss_mb") is not None:
                    extra.append(f"RSS: {runner_proc['memory_rss_mb']:.0f}MB")
                if extra:
                    info_parts.extend(extra)

            container.mount(
                Label("[bold]Runner[/bold]", classes="status_section_title")
            )
            container.mount(Label("  ".join(info_parts)))

            runner_active = status not in ("none", "stopped") and not stale
            bar = Horizontal(classes="runner_bar")
            container.mount(bar)
            if not runner_active:
                bar.mount(Button("Start Runner", classes="btn_runner_start"))
            else:
                bar.mount(Button("Stop Runner", classes="btn_runner_stop"))

        # --- Running Processes section ---
        if crew_id:
            if not self._processes_synced:
                corrected = sync_stale_processes(crew_id)
                if corrected:
                    self.notify(f"Auto-corrected {len(corrected)} stale agent(s)")
                self._processes_synced = True

            processes = get_all_agent_processes(crew_id)
            container.mount(
                Label("[bold]Running Processes[/bold]", classes="status_section_title")
            )
            if not processes:
                container.mount(Label("  [dim]No running processes[/dim]"))
            else:
                for proc in processes:
                    container.mount(ProcessRow(proc, crew_id))

        # Read groups from br_groups.yaml
        groups_path = self.session_path / GROUPS_FILE
        groups: dict = {}
        if groups_path.is_file():
            try:
                gdata = read_yaml(str(groups_path))
                groups = gdata.get("groups", {}) if gdata else {}
            except Exception:
                pass

        # Check for agent files even without groups
        agent_files = list_agent_files(wt_path, "_status.yaml")

        if not groups and not agent_files:
            container.mount(Label("No operations yet", classes="status_empty"))
            return

        # Groups section
        if groups:
            container.mount(
                Label("[bold]Operation Groups[/bold]", classes="status_section_title")
            )
            # Sort by created_at descending (newest first)
            sorted_groups = sorted(
                groups.items(),
                key=lambda kv: kv[1].get("created_at", "") if isinstance(kv[1], dict) else "",
                reverse=True,
            )
            for gname, ginfo in sorted_groups:
                if not isinstance(ginfo, dict):
                    continue
                expanded = gname in self._expanded_groups
                container.mount(
                    GroupRow(gname, ginfo, expanded=expanded, classes="status_group_row")
                )
                if expanded:
                    self._mount_group_agents(container, wt_path, ginfo)

        # Ungrouped agents section
        grouped_agents: set[str] = set()
        for ginfo in groups.values():
            if isinstance(ginfo, dict):
                for a in ginfo.get("agents", []):
                    grouped_agents.add(a)

        ungrouped = []
        for sf in agent_files:
            data = read_yaml(sf)
            name = data.get("agent_name", "")
            if name and name not in grouped_agents:
                ungrouped.append((name, data))

        if ungrouped:
            container.mount(Label(""))
            container.mount(
                Label("[bold]Ungrouped Agents[/bold]", classes="status_section_title")
            )
            for name, data in ungrouped:
                self._mount_agent_row(container, wt_path, name, data)

        # Log files section (t439_4)
        logs = list_agent_logs(wt_path)
        if logs:
            container.mount(Label(""))
            container.mount(
                Label(
                    "[bold]Agent Logs[/bold]  (Enter to view)",
                    classes="status_section_title",
                )
            )
            for log_info in logs:
                container.mount(StatusLogRow(log_info))

    def _reset_agent(self, row: "AgentStatusRow") -> None:
        """Reset an agent from Error to Waiting by updating the status file directly."""
        import os

        name = row.agent_name
        wt_path = str(self.session_path)
        sf = os.path.join(wt_path, f"{name}_status.yaml")
        if os.path.isfile(sf):
            update_yaml_field(sf, "status", "Waiting")
            update_yaml_field(sf, "error_message", "")
            update_yaml_field(sf, "completed_at", "")
            self.notify(f"Agent {name} reset to Waiting")
            self._delayed_refresh_status()
        else:
            self.notify(f"Status file not found for {name}", severity="error")

    def _edit_agent_mode(self, row: "AgentStatusRow") -> None:
        """Open the launch_mode edit modal for a Waiting agent row."""
        import os

        name = row.agent_name
        sf = os.path.join(str(self.session_path), f"{name}_status.yaml")
        if not os.path.isfile(sf):
            self.notify(
                f"Status file not found for {name}",
                severity="error",
            )
            return
        data = read_yaml(sf) or {}
        current_mode = data.get("launch_mode", DEFAULT_LAUNCH_MODE)
        status = data.get("status", row.agent_status)
        self.push_screen(
            AgentModeEditModal(
                agent_name=name,
                agent_status=status,
                current_mode=current_mode,
            ),
            lambda result, _name=name, _current=current_mode:
                self._on_mode_edit_result(_name, _current, result),
        )

    def _on_mode_edit_result(
        self, agent_name: str, current_mode: str, new_mode
    ) -> None:
        """Callback after AgentModeEditModal closes."""
        if new_mode is None or new_mode == current_mode:
            return
        crew_id = self.session_data.get("crew_id", "")
        if not crew_id:
            self.notify("No crew_id in session", severity="error")
            return
        try:
            result = subprocess.run(
                [
                    AIT_PATH, "crew", "setmode",
                    "--crew", crew_id,
                    "--name", agent_name,
                    "--mode", new_mode,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as e:
            self.notify(f"setmode failed to launch: {e}", severity="error")
            return
        if result.returncode == 0 and f"UPDATED:{agent_name}:{new_mode}" in result.stdout:
            self.notify(f"Launch mode → {new_mode} for {agent_name}")
            self._delayed_refresh_status()
        else:
            err = (result.stderr or result.stdout).strip() or "unknown error"
            self.notify(f"setmode failed: {err}", severity="error")

    def _delayed_refresh_status(self) -> None:
        """Show a loading notification then refresh the status tab after 2 seconds."""
        self.notify("Refreshing status...", timeout=2)
        self.set_timer(2.0, self._refresh_status_tab)

    def _mount_group_agents(
        self, container: VerticalScroll, wt_path: str, ginfo: dict
    ) -> None:
        """Mount agent detail rows for an expanded group."""
        import os

        agent_names = ginfo.get("agents", [])
        if not agent_names:
            container.mount(Label("  (no agents)", classes="status_agent_detail"))
            return

        for name in agent_names:
            sf = os.path.join(wt_path, f"{name}_status.yaml")
            if os.path.isfile(sf):
                data = read_yaml(sf)
            else:
                data = {"agent_name": name, "status": "Unknown"}
            self._mount_agent_row(container, wt_path, name, data)

    def _mount_agent_row(
        self, container: VerticalScroll, wt_path: str, name: str, data: dict
    ) -> None:
        """Mount a single agent status row with optional output preview."""
        import os
        from datetime import datetime, timezone

        status = data.get("status", "Unknown")
        color = AGENT_STATUS_COLORS.get(status, "#888888")
        atype = data.get("agent_type", "")
        type_label = f" ({atype})" if atype else ""

        # Heartbeat info
        alive_path = os.path.join(wt_path, f"{name}_alive.yaml")
        hb_str = ""
        msg_str = ""
        if os.path.isfile(alive_path):
            alive = read_yaml(alive_path)
            hb = alive.get("last_heartbeat", "")
            if hb:
                try:
                    ts = datetime.fromisoformat(str(hb).replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - ts).total_seconds()
                    hb_str = f"  \u2665 {format_elapsed(elapsed)} ago"
                except (ValueError, TypeError):
                    pass
            msg = alive.get("last_message", "")
            if msg:
                msg_str = f"  {msg}"

        line = (
            f"  [{color}]\u25cf[/{color}] {name}{type_label}  "
            f"[{color}]{status}[/{color}]{hb_str}{msg_str}"
        )
        crew_id = self.session_data.get("crew_id", "")
        container.mount(AgentStatusRow(name, status, line, crew_id))

        # Output preview (last 10 lines)
        output_path = os.path.join(wt_path, f"{name}_output.md")
        if os.path.isfile(output_path):
            try:
                with open(output_path) as f:
                    lines = f.readlines()
                if lines:
                    tail = lines[-10:]
                    preview = "".join(tail).rstrip()
                    if preview:
                        container.mount(
                            Label(
                                f"[dim]{preview}[/dim]",
                                classes="status_output_preview",
                            )
                        )
            except Exception:
                pass

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

        spec = sd.get("initial_spec", "")
        if spec:
            preview_lines = [ln for ln in spec.splitlines() if ln.strip() and not ln.startswith("---")][:2]
            preview = " | ".join(preview_lines)
            if len(preview) > 100:
                preview = preview[:97] + "…"
            info_lines.append(f"Brief: {preview}  [press b for full text]")

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

    def _show_brief_in_detail(self, spec: str) -> None:
        """Show the full initial_spec in the detail pane (press b to toggle)."""
        self.query_one("#dash_node_title", Label).update("Task Brief")
        # Truncate for the Label widget; full text is in n000_init proposal
        lines = spec.splitlines()
        if len(lines) > 30:
            preview = "\n".join(lines[:30]) + "\n\n… (truncated — see n000_init proposal for full text)"
        else:
            preview = spec
        self.query_one("#dash_node_info", Label).update(preview)

    def on_descendant_focus(self, event) -> None:
        """When a NodeRow gets focus, update the detail pane. Track wizard node selection."""
        if isinstance(event.widget, NodeRow):
            self._show_node_detail(event.widget.node_id)
        if isinstance(event.widget, OperationRow):
            tabbed = self.query_one(TabbedContent)
            if tabbed.active == "tab_actions" and self._wizard_step == 2:
                if self._wizard_op in _NODE_SELECT_OPS:
                    self._wizard_config["_selected_node"] = event.widget.op_key
                    # Visual feedback: mark selected node
                    container = self.query_one("#actions_content", VerticalScroll)
                    for row in container.query(OperationRow):
                        row.selected = (row.op_key == event.widget.op_key)
                    # Enable Next button
                    try:
                        self.query_one(".btn_actions_next", Button).disabled = False
                    except Exception:
                        pass

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

    # ------------------------------------------------------------------
    # Actions wizard
    # ------------------------------------------------------------------

    def _actions_show_step1(self) -> None:
        """Render Step 1: operation selection list."""
        self._wizard_step = 1
        self._wizard_op = ""
        self._wizard_config = {}
        self._wizard_has_sections = False
        self._cmp_section_checks = {}

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()

        if self.read_only:
            container.mount(Label("[italic]Session is read-only. No operations available.[/]"))
            return

        container.mount(Label("Step 1 \u2014 Select Operation  (\u2191\u2193 Navigate  Enter Select)", classes="actions_step_indicator"))

        status = self.session_data.get("status", "")
        head = get_head(self.session_path)

        # Design operations
        container.mount(Label("Design Operations", classes="actions_section_title"))
        design_disabled = status not in ("init", "active")
        for op_key, label, desc in _DESIGN_OPS:
            container.mount(OperationRow(op_key, label, desc, disabled=design_disabled))

        # Session lifecycle operations
        container.mount(Label("Session Lifecycle", classes="actions_section_title"))
        for op_key, label, desc in _SESSION_OPS:
            disabled = self._is_session_op_disabled(op_key, status, head)
            container.mount(OperationRow(op_key, label, desc, disabled=disabled))

        # Recent operations history
        self._mount_recent_ops(container)

        # Focus first enabled operation after widgets are rendered
        self.call_after_refresh(self._focus_first_operation)

    def _focus_first_operation(self) -> None:
        """Focus the first enabled OperationRow in the actions tab."""
        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab_actions":
            return
        try:
            rows = self.query("OperationRow")
            for row in rows:
                if not row.op_disabled:
                    row.focus()
                    break
        except Exception:
            pass

    def _is_session_op_disabled(self, op_key: str, status: str, head: str | None) -> bool:
        """Determine if a session operation should be disabled."""
        if op_key == "pause":
            return status != "active"
        if op_key == "resume":
            return status != "paused"
        if op_key == "finalize":
            return status != "active" or head is None
        if op_key == "archive":
            return status != "completed"
        if op_key == "delete":
            return False
        return False

    def _mount_recent_ops(self, container: VerticalScroll) -> None:
        """Append recent operation history from br_groups.yaml."""
        groups_path = self.session_path / GROUPS_FILE
        if not groups_path.is_file():
            return
        try:
            groups_data = read_yaml(str(groups_path))
        except Exception:
            return
        groups = groups_data.get("groups", {}) if groups_data else {}
        if not groups:
            return
        container.mount(Label("Recent Operations", classes="actions_section_title"))
        for name in list(groups.keys())[-5:]:
            info = groups[name] if isinstance(groups[name], dict) else {}
            op = info.get("operation", "?")
            gstatus = info.get("status", "?")
            created = info.get("created_at", "")
            container.mount(Label(f"  [dim]{name}[/]  {op}  [{gstatus}]  {created}"))

    def _set_total_steps(self) -> None:
        """Set _wizard_total_steps based on operation type."""
        if self._wizard_op in ("explore", "patch"):
            self._wizard_total_steps = 4
        else:
            self._wizard_total_steps = 3
        self._wizard_has_sections = False
        self._cmp_section_checks = {}

    def _actions_show_step2(self) -> None:
        """Route to node selection or config based on operation type."""
        if self._wizard_op in _NODE_SELECT_OPS:
            self._actions_show_node_select()
        else:
            self._actions_show_config()

    def _actions_show_node_select(self) -> None:
        """Step 2: dedicated node selection for explore/detail/patch."""
        self._wizard_step = 2
        self._wizard_config = {}

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()

        total = self._wizard_total_steps
        desc_map = {
            "explore": "Select Base Node",
            "detail": "Select Node for Detailing",
            "patch": "Select Node to Patch",
        }
        desc = desc_map.get(self._wizard_op, "Select Node")
        container.mount(
            Label(
                f"Step 2 of {total} \u2014 {desc}  (Esc: Back)",
                classes="actions_step_indicator",
            )
        )
        container.mount(
            Label("[dim]  \u2191\u2193 Navigate  Enter Select  |  Click node + Next[/dim]")
        )

        nodes = list_nodes(self.session_path)
        head = get_head(self.session_path)

        if not nodes:
            container.mount(
                Label("[bold yellow]No nodes available.[/] Initialize the session first.")
            )
            return

        for nid in nodes:
            node_data = read_node(self.session_path, nid)
            desc = node_data.get("description", "")
            lbl = f"{nid} [green]HEAD[/]" if nid == head else nid
            container.mount(OperationRow(nid, lbl, desc))

        container.mount(
            Button("Next \u25b6", variant="primary", classes="btn_actions_next", disabled=True)
        )
        self.call_after_refresh(self._focus_first_operation)

    def _actions_show_section_select(self) -> None:
        """Optional step 3: pick sections to target for the selected node."""
        node = self._wizard_config.get("_selected_node", "")
        secs = self._node_sections(node)

        self._wizard_has_sections = True
        if self._wizard_op in ("explore", "patch"):
            self._wizard_total_steps = 5
        elif self._wizard_op == "detail":
            self._wizard_total_steps = 4
        self._wizard_step = 3

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()

        total = self._wizard_total_steps
        container.mount(
            Label(
                f"Step 3 of {total} \u2014 Select Sections for {node}  (Esc: Back)",
                classes="actions_step_indicator",
            )
        )
        container.mount(
            Label("[dim]Leave all unchecked to target the whole document.[/]")
        )
        for s in secs:
            dims = f" [dim][{', '.join(s.dimensions)}][/]" if s.dimensions else ""
            container.mount(Checkbox(f"{s.name}{dims}", classes="chk_section"))
        container.mount(
            Button("Next \u25b6", variant="primary", classes="btn_actions_next")
        )

    def _actions_show_config(self) -> None:
        """Render config step: operation-specific configuration form."""
        op = self._wizard_op
        if op in ("explore", "patch"):
            self._wizard_step = self._wizard_total_steps - 1
        else:
            self._wizard_step = 2

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()

        total = self._wizard_total_steps
        step = self._wizard_step
        container.mount(
            Label(
                f"Step {step} of {total} \u2014 Configure: {op.title()}  (Esc: Back)",
                classes="actions_step_indicator",
            )
        )

        if op == "explore":
            self._config_explore_no_node(container)
        elif op == "compare":
            self._config_compare(container)
        elif op == "hybridize":
            self._config_hybridize(container)
        elif op == "patch":
            self._config_patch_no_node(container)

    def _config_explore_no_node(self, container: VerticalScroll) -> None:
        """Explore config (node already selected): mandate, parallel count."""
        node_id = self._wizard_config.get("_selected_node", "?")
        container.mount(Label(f"[bold]Base Node:[/] {node_id}"))
        container.mount(Label("[bold]Exploration Mandate[/]"))
        container.mount(TextArea(""))
        container.mount(CycleField("Parallel explorers", ["1", "2", "3", "4"], initial="2"))
        container.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))

    def _config_compare(self, container: VerticalScroll) -> None:
        """Compare config: multi-node checkboxes + dimension checkboxes + sections."""
        nodes = list_nodes(self.session_path)

        container.mount(Label("[bold]Select Nodes to Compare (2+)[/]"))
        for nid in nodes:
            container.mount(Checkbox(nid, classes="chk_node"))

        container.mount(Label("[bold]Dimensions[/]"))
        all_dims = self._get_all_dimension_keys()
        if all_dims:
            for dim in all_dims:
                container.mount(Checkbox(dim, value=True, classes="chk_dim"))
        else:
            container.mount(Label("[dim]No dimensions found[/]"))

        container.mount(Label("[bold]Target Sections (optional)[/]", id="cmp_sections_label"))
        container.mount(Container(id="cmp_sections_box"))

        container.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))

        self._cmp_section_checks = {}
        self.call_after_refresh(self._refresh_compare_sections)

    def _refresh_compare_sections(self) -> None:
        """(Re)mount compare section checkboxes based on currently checked nodes."""
        try:
            box = self.query_one("#cmp_sections_box", Container)
        except Exception:
            return

        for cb in box.query("Checkbox.chk_section"):
            self._cmp_section_checks[_parse_section_label(str(cb.label))] = bool(cb.value)
        box.remove_children()

        checked: list[str] = []
        for cb in self.query("Checkbox.chk_node"):
            if cb.value:
                checked.append(str(cb.label))

        if len(checked) < 1:
            box.mount(Label("[dim]Select nodes to see comparable sections.[/]"))
            return

        per_node: dict[str, list[str]] = {
            nid: [s.name for s in self._node_sections(nid)] for nid in checked
        }
        inter = _sections_intersection(per_node)

        if not inter:
            box.mount(Label("[dim]No sections are present in all selected nodes.[/]"))
            return

        for name in inter:
            value = self._cmp_section_checks.get(name, False)
            box.mount(Checkbox(name, value=value, classes="chk_section"))

    def _config_hybridize(self, container: VerticalScroll) -> None:
        """Hybridize config: multi-node checkboxes + merge rules."""
        nodes = list_nodes(self.session_path)

        container.mount(Label("[bold]Select Source Nodes (2+)[/]"))
        for nid in nodes:
            container.mount(Checkbox(nid, classes="chk_node"))

        container.mount(Label("[bold]Merge Rules[/]"))
        container.mount(TextArea(""))
        container.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))

    def _config_patch_no_node(self, container: VerticalScroll) -> None:
        """Patch config (node already selected): patch request."""
        node_id = self._wizard_config.get("_selected_node", "?")
        container.mount(Label(f"[bold]Node:[/] {node_id}"))
        container.mount(Label("[bold]Patch Request[/]"))
        container.mount(TextArea(""))
        container.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))

    def _config_session_op(self, container: VerticalScroll) -> None:
        """Session operation config: confirmation only."""
        labels = {
            "pause": "Pause the session. Agents will not be dispatched.",
            "resume": "Resume the paused session.",
            "finalize": "Copy the HEAD node's plan to aiplans/ and mark session completed.",
            "archive": "Mark the session as archived.",
        }
        container.mount(Label(f"[bold]{labels.get(self._wizard_op, self._wizard_op)}[/]"))
        container.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))

    def _get_all_dimension_keys(self) -> list[str]:
        """Get all dimension keys from all nodes (preserving order)."""
        all_dims: list[str] = []
        seen: set[str] = set()
        for nid in list_nodes(self.session_path):
            data = read_node(self.session_path, nid)
            for k in extract_dimensions(data):
                if k not in seen:
                    all_dims.append(k)
                    seen.add(k)
        return all_dims

    def _node_sections(self, node_id: str) -> list:
        """Return the list of ContentSection for a node (plan preferred, else proposal)."""
        try:
            plan = read_plan(self.session_path, node_id)
        except FileNotFoundError:
            plan = None
        if plan:
            secs = parse_sections(plan).sections
            if secs:
                return secs
        try:
            proposal = read_proposal(self.session_path, node_id)
        except FileNotFoundError:
            proposal = None
        if proposal:
            return parse_sections(proposal).sections
        return []

    def _node_has_sections(self, node_id: str) -> bool:
        """True when the node's plan or proposal has structured sections."""
        return bool(self._node_sections(node_id))

    def _actions_collect_config(self) -> bool:
        """Collect and validate config from config step widgets. Returns True if valid."""
        op = self._wizard_op
        # Preserve _selected_node from node selection step
        selected_node = self._wizard_config.get("_selected_node")
        # Preserve target_sections already chosen in the section-select step
        prior_target_sections = self._wizard_config.get("target_sections")
        config: dict = {}
        if selected_node:
            config["_selected_node"] = selected_node
        if prior_target_sections is not None:
            config["target_sections"] = prior_target_sections
        container = self.query_one("#actions_content", VerticalScroll)

        if op == "explore":
            config["base_node"] = selected_node or ""
            if not config["base_node"]:
                self.notify("Select a base node first", severity="warning")
                return False
            config["mandate"] = container.query_one(TextArea).text.strip()
            if not config["mandate"]:
                self.notify("Mandate cannot be empty", severity="warning")
                return False
            config["parallel"] = int(container.query_one(CycleField).current_value)

        elif op == "compare":
            node_cbs = container.query("Checkbox.chk_node")
            selected = [cb.label for cb in node_cbs if cb.value]
            if len(selected) < 2:
                self.notify("Select at least 2 nodes", severity="warning")
                return False
            config["nodes"] = [str(lbl) for lbl in selected]
            dim_cbs = container.query("Checkbox.chk_dim")
            config["dimensions"] = [str(cb.label) for cb in dim_cbs if cb.value]
            try:
                box = self.query_one("#cmp_sections_box", Container)
                sec_cbs = box.query("Checkbox.chk_section")
                sel_secs = [str(cb.label) for cb in sec_cbs if cb.value]
                config["target_sections"] = sel_secs or None
            except Exception:
                config["target_sections"] = None

        elif op == "hybridize":
            node_cbs = container.query("Checkbox.chk_node")
            selected = [cb.label for cb in node_cbs if cb.value]
            if len(selected) < 2:
                self.notify("Select at least 2 source nodes", severity="warning")
                return False
            config["nodes"] = [str(lbl) for lbl in selected]
            config["merge_rules"] = container.query_one(TextArea).text.strip()
            if not config["merge_rules"]:
                self.notify("Merge rules cannot be empty", severity="warning")
                return False

        elif op == "patch":
            config["node"] = selected_node or ""
            if not config["node"]:
                self.notify("Select a node first", severity="warning")
                return False
            config["patch_request"] = container.query_one(TextArea).text.strip()
            if not config["patch_request"]:
                self.notify("Patch request cannot be empty", severity="warning")
                return False

        elif op in ("pause", "resume", "finalize", "archive"):
            config["confirmed"] = True

        self._wizard_config = config
        return True

    def _collect_target_sections(self) -> None:
        """Collect checked section names from the section-select step into wizard config."""
        container = self.query_one("#actions_content", VerticalScroll)
        names: list[str] = []
        for cb in container.query("Checkbox.chk_section"):
            if cb.value:
                names.append(_parse_section_label(str(cb.label)))
        self._wizard_config["target_sections"] = names or None

    def _actions_show_confirm(self) -> None:
        """Render final confirm step: summary + launch/confirm button."""
        total = self._wizard_total_steps
        self._wizard_step = total

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()
        container.mount(Label(f"Step {total} of {total} \u2014 Confirm  (Esc: Back)", classes="actions_step_indicator"))

        summary_lines = self._build_summary()
        container.mount(Static("\n".join(summary_lines), classes="actions_summary"))

        is_session_op = self._wizard_op in ("pause", "resume", "finalize", "archive")
        if not is_session_op:
            default_mode = _brainstorm_launch_mode_default(self._wizard_op)
            container.mount(
                CycleField(
                    "Launch mode",
                    sorted(VALID_LAUNCH_MODES),
                    initial=default_mode,
                    id="launch-mode-field",
                )
            )
            if not is_tmux_available():
                container.mount(
                    Static(
                        "[dim]tmux not installed — interactive will fall back "
                        "to a standalone terminal (no monitor integration)[/]",
                        classes="actions_hint",
                    )
                )

        btn_label = "Confirm" if is_session_op else "Launch"
        container.mount(
            Horizontal(
                Button(btn_label, variant="primary", classes="btn_actions_launch"),
                Button("Back", variant="default", classes="btn_actions_back"),
                classes="actions_buttons",
            )
        )
        self.call_after_refresh(self._focus_confirm_start)

    def _focus_confirm_start(self) -> None:
        """Move focus to the first focusable widget on the confirm screen."""
        try:
            container = self.query_one("#actions_content", VerticalScroll)
        except Exception:
            return
        for w in container.query("*"):
            if getattr(w, "can_focus", False) and not getattr(w, "disabled", False):
                w.focus()
                return

    def _build_summary(self) -> list[str]:
        """Build summary lines for step 3 display."""
        op = self._wizard_op
        cfg = self._wizard_config
        lines = [f"[bold]Operation:[/] {op.title()}", ""]

        if op == "explore":
            lines.append(f"[bold]Base Node:[/] {cfg['base_node']}")
            lines.append(f"[bold]Parallel Explorers:[/] {cfg['parallel']}")
            lines.append("[bold]Mandate:[/]")
            lines.append(cfg["mandate"])
        elif op == "compare":
            lines.append(f"[bold]Nodes:[/] {', '.join(cfg['nodes'])}")
            dims_str = ", ".join(cfg["dimensions"]) if cfg["dimensions"] else "(all)"
            lines.append(f"[bold]Dimensions:[/] {dims_str}")
        elif op == "hybridize":
            lines.append(f"[bold]Source Nodes:[/] {', '.join(cfg['nodes'])}")
            lines.append("[bold]Merge Rules:[/]")
            lines.append(cfg["merge_rules"])
        elif op == "detail":
            lines.append(f"[bold]Node:[/] {cfg['node']}")
        elif op == "patch":
            lines.append(f"[bold]Node:[/] {cfg['node']}")
            lines.append("[bold]Patch Request:[/]")
            lines.append(cfg["patch_request"])
        elif op == "pause":
            lines.append("Session will be paused.")
        elif op == "resume":
            lines.append("Session will be resumed.")
        elif op == "finalize":
            head = get_head(self.session_path)
            lines.append(f"HEAD node [bold]{head}[/] plan will be copied to aiplans/.")
        elif op == "archive":
            lines.append("Session will be archived.")

        ts = cfg.get("target_sections")
        if ts:
            lines.append(f"[bold]Sections:[/] {', '.join(ts)}")

        if op not in ("pause", "resume", "finalize", "archive"):
            default_mode = _brainstorm_launch_mode_default(op)
            lines.append(f"[bold]Launch mode:[/] {default_mode} (editable below)")

        return lines

    @on(Checkbox.Changed, ".chk_node")
    def _on_cmp_node_changed(self, event: Checkbox.Changed) -> None:
        """Re-render compare section checkboxes when node selection changes."""
        if self._wizard_op != "compare":
            return
        self._refresh_compare_sections()

    @on(Button.Pressed, ".btn_actions_launch")
    def _on_actions_launch(self) -> None:
        """Handle Launch/Confirm button press in step 3."""
        if self._wizard_op in ("pause", "resume", "finalize", "archive"):
            self._execute_session_op()
        else:
            self._execute_design_op()

    @on(Button.Pressed, ".btn_actions_back")
    def _on_actions_back(self) -> None:
        """Handle Back button in confirm step."""
        if self._wizard_op == "detail":
            if self._wizard_has_sections:
                self._actions_show_section_select()
            else:
                self._actions_show_node_select()
        elif self._wizard_op in ("explore", "patch", "compare", "hybridize"):
            self._actions_show_config()
        else:
            self._actions_show_config()

    @on(Button.Pressed, ".btn_actions_next")
    def _on_actions_next(self) -> None:
        """Handle Next button in wizard steps."""
        if self._wizard_step == 2:
            if self._wizard_op in _NODE_SELECT_OPS:
                # Step 2 is node select; advance
                node = self._wizard_config.get("_selected_node")
                if not node:
                    self.notify("Select a node first", severity="warning")
                    return
                if self._node_has_sections(node):
                    self._actions_show_section_select()
                    return
                if self._wizard_op == "detail":
                    self._wizard_config["node"] = node
                    self._actions_show_confirm()
                else:
                    self._actions_show_config()
            elif self._actions_collect_config():
                self._actions_show_confirm()
        elif (
            self._wizard_step == 3
            and self._wizard_has_sections
            and self._wizard_op in _NODE_SELECT_OPS
        ):
            # Section-select step: collect sections, then go to config (explore/patch) or confirm (detail)
            self._collect_target_sections()
            if self._wizard_op == "detail":
                self._wizard_config["node"] = self._wizard_config.get("_selected_node", "")
                self._actions_show_confirm()
            else:
                self._actions_show_config()
        elif self._wizard_step == self._wizard_total_steps - 1 and self._wizard_op in ("explore", "patch"):
            # Config step for 4- or 5-step ops
            if self._actions_collect_config():
                self._actions_show_confirm()

    @on(Button.Pressed, ".btn_runner_start")
    def _on_runner_start(self, event: Button.Pressed) -> None:
        """Start the crew runner process."""
        event.button.disabled = True
        crew_id = self.session_data.get("crew_id", "")
        if crew_id and start_runner(crew_id):
            self.notify("Runner started")
            self._delayed_refresh_status()
        else:
            self.notify("Failed to start runner", severity="error")

    @on(Button.Pressed, ".btn_runner_stop")
    def _on_runner_stop(self, event: Button.Pressed) -> None:
        """Request the crew runner to stop."""
        event.button.disabled = True
        crew_id = self.session_data.get("crew_id", "")
        if crew_id and stop_runner(crew_id):
            self.notify("Runner stop requested")
            self._delayed_refresh_status()
        else:
            self.notify("Failed to stop runner", severity="error")

    def on_operation_row_activated(self, event: OperationRow.Activated) -> None:
        """Handle mouse click activation on an OperationRow."""
        row = event.row
        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab_actions":
            return
        if self._wizard_step == 1:
            self._wizard_op = row.op_key
            self._set_total_steps()
            if self._wizard_op == "delete":
                self.push_screen(
                    DeleteSessionModal(self.task_num),
                    self._on_delete_result,
                )
            elif self._wizard_op in ("pause", "resume", "finalize", "archive"):
                self._wizard_config = {"confirmed": True}
                self._actions_show_confirm()
            else:
                self._actions_show_step2()
        elif self._wizard_step == 2 and self._wizard_op in _NODE_SELECT_OPS:
            self._wizard_config["_selected_node"] = row.op_key
            # Visual feedback: mark selected node
            container = self.query_one("#actions_content", VerticalScroll)
            for op_row in container.query(OperationRow):
                op_row.selected = (op_row.op_key == row.op_key)
            # Enable Next button
            try:
                self.query_one(".btn_actions_next", Button).disabled = False
            except Exception:
                pass

    def _execute_session_op(self) -> None:
        """Execute a session lifecycle operation."""
        op = self._wizard_op
        try:
            if op == "pause":
                save_session(self.task_num, {"status": "paused"})
                self.notify("Session paused")
            elif op == "resume":
                save_session(self.task_num, {"status": "active"})
                self.notify("Session resumed")
            elif op == "finalize":
                dest = finalize_session(self.task_num)
                self.notify(f"Plan finalized to {dest}")
            elif op == "archive":
                archive_session(self.task_num)
                self.notify("Session archived")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            return

        self._load_existing_session()

    def _execute_design_op(self) -> None:
        """Dispatch design operation to background thread."""
        status = self.session_data.get("status", "")
        if status == "init":
            save_session(self.task_num, {"status": "active"})
            self.session_data["status"] = "active"
        try:
            field = self.query_one("#launch-mode-field", CycleField)
            self._wizard_config["launch_mode"] = field.current_value
        except Exception:
            self._wizard_config["launch_mode"] = DEFAULT_LAUNCH_MODE
        self._run_design_op()

    @work(thread=True)
    def _run_design_op(self) -> None:
        """Register agents for the design operation in a background thread."""
        op = self._wizard_op
        cfg = self._wizard_config
        crew_id = self.session_data.get("crew_id", f"brainstorm-{self.task_num}")
        group_name = self._next_group_name(op)
        launch_mode = cfg.get("launch_mode", DEFAULT_LAUNCH_MODE)
        target_sections = cfg.get("target_sections")

        try:
            if op == "explore":
                agents = []
                count = cfg["parallel"]
                suffixes = "abcdefgh"
                for i in range(count):
                    suffix = suffixes[i] if count > 1 else ""
                    agent = register_explorer(
                        self.session_path, crew_id, cfg["mandate"],
                        cfg["base_node"], group_name, agent_suffix=suffix,
                        launch_mode=launch_mode,
                        target_sections=target_sections,
                    )
                    agents.append(agent)
                msg = f"Registered {len(agents)} explorer(s): {', '.join(agents)}"
            elif op == "compare":
                agent = register_comparator(
                    self.session_path, crew_id, cfg["nodes"],
                    cfg["dimensions"], group_name,
                    launch_mode=launch_mode,
                    target_sections=target_sections,
                )
                msg = f"Registered comparator: {agent}"
            elif op == "hybridize":
                agent = register_synthesizer(
                    self.session_path, crew_id, cfg["nodes"],
                    cfg["merge_rules"], group_name,
                    launch_mode=launch_mode,
                )
                msg = f"Registered synthesizer: {agent}"
            elif op == "detail":
                agent = register_detailer(
                    self.session_path, crew_id, cfg["node"],
                    ["."], group_name,
                    launch_mode=launch_mode,
                    target_sections=target_sections,
                )
                msg = f"Registered detailer: {agent}"
            elif op == "patch":
                agent = register_patcher(
                    self.session_path, crew_id, cfg["node"],
                    cfg["patch_request"], group_name,
                    launch_mode=launch_mode,
                    target_sections=target_sections,
                )
                msg = f"Registered patcher: {agent}"
            else:
                msg = f"Unknown operation: {op}"

            self.call_from_thread(self.notify, msg)
            self.call_from_thread(self._actions_show_step1)

        except Exception as e:
            self.call_from_thread(
                self.notify, f"Operation failed: {e}", severity="error",
            )
            self.call_from_thread(self._actions_show_step1)

    def _next_group_name(self, op: str) -> str:
        """Generate next group name (e.g., explore_001, compare_002)."""
        groups_path = self.session_path / GROUPS_FILE
        groups: dict = {}
        if groups_path.is_file():
            try:
                data = read_yaml(str(groups_path))
                groups = (data or {}).get("groups", {})
            except Exception:
                pass
        existing = [k for k in groups if k.startswith(f"{op}_")]
        seq = len(existing) + 1
        return f"{op}_{seq:03d}"

    def _on_delete_result(self, confirmed: bool | None) -> None:
        """Handle DeleteSessionModal result."""
        if confirmed:
            self._run_delete_session()
        else:
            self._actions_show_step1()

    @work(thread=True)
    def _run_delete_session(self) -> None:
        """Run ait brainstorm delete in a background thread, then exit."""
        result = subprocess.run(
            [AIT_PATH, "brainstorm", "delete", self.task_num, "--yes"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.call_from_thread(self.exit)
        else:
            self.call_from_thread(
                self.notify,
                f"Delete failed: {result.stderr.strip()}",
                severity="error",
            )
            self.call_from_thread(self._actions_show_step1)

    def _on_init_result(self, result: str | None) -> None:
        """Handle InitSessionModal result."""
        if result is None:
            self.exit()
        elif result == "blank":
            self._run_init()
        elif isinstance(result, str) and result.startswith("import:"):
            path = result[len("import:"):]
            self._run_init_with_proposal(path)
        else:
            self.notify(f"Unknown init result: {result!r}", severity="error")
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

    @work(thread=True)
    def _run_init_with_proposal(self, path: str) -> None:
        """Shell to `ait brainstorm init <N> --proposal-file <path>`, then poll."""
        result = subprocess.run(
            [
                AIT_PATH, "brainstorm", "init", self.task_num,
                "--proposal-file", path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            error_text = self._format_init_error(
                f"`ait brainstorm init {self.task_num}` exited "
                f"with code {result.returncode}.",
                result.stdout,
                result.stderr,
                include_runner_log=False,
            )
            self.call_from_thread(self._show_init_failure, error_text)
            return

        agent_name = "initializer_bootstrap"
        for line in result.stdout.splitlines():
            if line.startswith("INITIALIZER_AGENT:"):
                agent_name = line.split(":", 1)[1].strip()
                break

        if "RUNNER_START_FAILED:" in result.stderr:
            error_text = self._format_init_error(
                "The initializer agent was registered, but its runner "
                f"crashed within {1.5}s of launch.\n"
                f"To retry the runner manually:\n"
                f"    ait crew runner --crew brainstorm-{self.task_num}",
                result.stdout,
                result.stderr,
                include_runner_log=True,
            )
            self.call_from_thread(self._show_init_failure, error_text)
            return

        self.call_from_thread(self._start_initializer_wait, agent_name)

    def _format_init_error(
        self,
        summary: str,
        stdout: str,
        stderr: str,
        include_runner_log: bool,
    ) -> str:
        """Build the multi-line error body shown in InitFailureModal."""
        parts = [summary, "", "STDERR:", stderr.rstrip() or "(empty)", "",
                 "STDOUT:", stdout.rstrip() or "(empty)"]
        if include_runner_log:
            log_path = crew_worktree(self.task_num) / "_runner_launch.log"
            if log_path.is_file():
                try:
                    log_text = log_path.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    log_text = f"(failed to read {log_path}: {e})"
                parts.extend(["", f"_runner_launch.log ({log_path}):", log_text.rstrip()])
        return "\n".join(parts)

    def _show_init_failure(self, error_text: str) -> None:
        """Push InitFailureModal from the main thread."""
        self.push_screen(
            InitFailureModal(error_text),
            callback=self._on_init_failure_result,
        )

    def _on_init_failure_result(self, result: str | None) -> None:
        """Modal-result handler.

        - ``retry``: re-open InitSessionModal.
        - ``clean_and_retry``: delete the stale crew branch in a worker, then
          either re-open InitSessionModal on success or re-show the failure
          modal with the cleanup error appended on failure.
        - any other value (``quit``/``None``/Escape): exit the app.
        """
        if result == "retry":
            self.push_screen(
                InitSessionModal(self.task_num),
                callback=self._on_init_result,
            )
        elif result == "clean_and_retry":
            self._cleanup_stale_crew_branch_and_retry()
        else:
            self.exit()

    @work(thread=True)
    def _cleanup_stale_crew_branch_and_retry(self) -> None:
        """Delete the stale `crew-brainstorm-<N>` branch, then reopen Init modal.

        Runs `git worktree prune` first so a stale worktree registration
        does not pin the branch as "checked out elsewhere", then deletes the
        local branch (and best-effort the remote tracking ref). On failure,
        re-shows the InitFailureModal with the cleanup output appended.
        """
        crew_branch = f"crew-brainstorm-{self.task_num}"
        cmds = [
            ["git", "worktree", "prune"],
            ["git", "branch", "-D", crew_branch],
        ]
        outputs: list[str] = []
        success = True
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True)
            outputs.append(
                f"$ {' '.join(cmd)}\nexit={r.returncode}\n"
                f"{r.stdout}{r.stderr}".rstrip()
            )
            if r.returncode != 0 and cmd[1] == "branch":
                success = False
        # Best-effort remote prune; never fails the cleanup
        r = subprocess.run(
            ["git", "push", "origin", "--delete", crew_branch],
            capture_output=True, text=True,
        )
        outputs.append(
            f"$ git push origin --delete {crew_branch}\nexit={r.returncode}\n"
            f"{r.stdout}{r.stderr}".rstrip()
        )

        if success:
            self.call_from_thread(
                self.notify,
                f"Deleted stale {crew_branch}; reopening init…",
                severity="information",
            )
            self.call_from_thread(
                self.push_screen,
                InitSessionModal(self.task_num),
                callback=self._on_init_result,
            )
        else:
            error_text = (
                f"Failed to delete stale {crew_branch}.\n\n"
                + "\n\n".join(outputs)
            )
            self.call_from_thread(self._show_init_failure, error_text)

    def _start_initializer_wait(self, agent_name: str) -> None:
        """Main-thread setup: show placeholder DAG + start polling timer."""
        self._initializer_agent = agent_name
        self._initializer_done = False
        self.session_data = load_session(self.task_num)
        self._update_title_from_task()
        self._load_existing_session()
        self.notify(f"Waiting for {agent_name} to complete…")
        self._try_apply_initializer_if_needed()
        self._initializer_timer = self.set_interval(2, self._poll_initializer)

    def _poll_initializer(self) -> None:
        """Timer tick: check status file, apply initializer output on Completed."""
        if self._initializer_done or self._initializer_agent is None:
            return
        status_path = (
            self.session_path / f"{self._initializer_agent}_status.yaml"
        )
        if not status_path.is_file():
            return
        try:
            data = read_yaml(str(status_path))
        except Exception:
            return
        status = (data or {}).get("status", "")
        if status == "Completed":
            self._initializer_done = True
            if self._initializer_timer is not None:
                self._initializer_timer.stop()
            try:
                from brainstorm.brainstorm_session import apply_initializer_output
                apply_initializer_output(self.task_num)
                self.notify("Initial proposal imported.")
            except Exception as e:
                self.notify(
                    f"Failed to apply initializer output: {e}",
                    severity="error",
                )
            self._load_existing_session()
        elif status in ("Error", "Aborted"):
            # Don't permanently stop — the agent may still write _output.md
            # later. Stop the fast 2 s timer; install a slower 30 s watcher
            # so a late-arriving output is still applied.
            if self._initializer_timer is not None:
                self._initializer_timer.stop()
            self._initializer_timer = self.set_interval(30, self._poll_initializer)
            self.notify(
                f"Initializer agent {status.lower()}. "
                f"Watching for output; press ctrl+r or run "
                f"`ait brainstorm apply-initializer {self.task_num}` to retry.",
                severity="error",
            )
            self._load_existing_session()
            self._try_apply_initializer_if_needed()


if __name__ == "__main__":
    task_num = sys.argv[1] if len(sys.argv) > 1 else "0"
    app = BrainstormApp(task_num)
    app.run()
