"""Brainstorm TUI: ModalScreen dialogs."""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container,
    Horizontal,
    VerticalScroll,
)
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    DirectoryTree,
    Footer,
    Input,
    Label,
    LoadingIndicator,
    Markdown,
    Static,
    Tabs,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual import (
    on,
    work,
)
from brainstorm.brainstorm_dag import (
    read_node,
    read_proposal,
)
from brainstorm.brainstorm_schemas import extract_dimensions
from brainstorm.brainstorm_sections import parse_sections
from brainstorm.brainstorm_dag_display import (
    OP_BADGE_STYLES,
    UNKNOWN_OP_STYLE,
)
from brainstorm.brainstorm_op_refs import (
    OpDataRef,
    list_op_inputs,
    resolve_ref,
)
from launch_modes import DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES
from agentcrew.agentcrew_utils import read_yaml
from agentcrew.agentcrew_log_utils import (
    read_log_tail,
    read_log_full,
    format_log_size,
)

from brainstorm.constants import (
    AGENT_STATUS_COLORS,
    NODE_HUB_COMPARE,
    NODE_HUB_OPERATIONS,
    NodeHubResult,
    _OPERATION_HELP,
    _OP_LABELS,
)
from brainstorm.utils import (
    _read_groups,
    _validate_export_dir,
    _write_node_exports,
    compare_matrix_rows,
    detect_stale_crew_branch,
    format_node_id_summary,
)
from brainstorm.widgets import (
    NodeDetailPanel,
    OperationRow,
)

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


class DeleteNodeModal(ModalScreen):
    """Double-confirmation modal for cascade-deleting a DAG node + descendants.

    Lists every node in the deletion closure, warns (does not block) when an
    affected module has a linked aitask, and blocks the delete entirely when a
    running/waiting agent operates on an affected node. Returns True (confirmed)
    or False (cancelled) via dismiss(). Carries its own DEFAULT_CSS so it is
    self-contained (per tui_conventions).
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    DeleteNodeModal {
        align: center middle;
    }
    #delete_node_dialog {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }
    #delete_node_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }
    /* Direct-child labels span the full dialog so prose wraps instead of
       truncating (closure-list rows live inside #delete_node_closure and are
       short ids, so they keep their auto width). */
    #delete_node_dialog > Label {
        width: 100%;
    }
    #delete_node_closure {
        height: auto;
        max-height: 12;
        margin-bottom: 1;
    }
    #delete_node_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    """

    def __init__(self, node_id, closure, linked_modules, agent_casualties):
        super().__init__()
        self.node_id = node_id
        self.closure = closure  # list[str], includes node_id (root first)
        self.linked_modules = linked_modules  # list[(module, task_id)]
        self.agent_casualties = agent_casualties  # list[(node, agent, status)]
        self._confirmed_once = False

    def compose(self) -> ComposeResult:
        n_desc = max(0, len(self.closure) - 1)
        with Container(id="delete_node_dialog"):
            yield Label(
                f"Delete node [bold]{self.node_id}[/] and "
                f"{n_desc} descendant(s)?",
                id="delete_node_title",
            )
            yield Label(
                "[dim]These nodes (and their proposals/plans) will be "
                "permanently removed:[/dim]",
            )
            with VerticalScroll(id="delete_node_closure"):
                for nid in self.closure:
                    marker = "  ▸ " if nid == self.node_id else "  • "
                    yield Label(f"{marker}{nid}")
            if self.linked_modules:
                lines = "\n".join(
                    f"  • module '{m}' → linked aitask t{t}"
                    for m, t in self.linked_modules
                )
                yield Label(
                    "[bold yellow]Warning — affected module(s) have a linked "
                    "aitask:[/]\n" + lines +
                    "\n[yellow]The linked aitask itself is left untouched.[/]",
                )
            if self.agent_casualties:
                lines = "\n".join(
                    f"  • {nid} — {agent} ({status})"
                    for nid, agent, status in self.agent_casualties
                )
                yield Label(
                    "[bold red]Blocked — running agent(s) operate on affected "
                    "node(s):[/]\n" + lines +
                    "\n[red]Stop these agents before deleting.[/]",
                )
            yield Label(
                "[dim]Enter/Delete to confirm  Esc to cancel[/dim]",
            )
            with Horizontal(id="delete_node_buttons"):
                yield Button(
                    "Delete", variant="error", id="btn_delete_node",
                    disabled=bool(self.agent_casualties),
                )
                yield Button(
                    "Cancel", variant="default", id="btn_delete_node_cancel"
                )

    @on(Button.Pressed, "#btn_delete_node")
    def on_delete(self) -> None:
        if self.agent_casualties:
            return
        if not self._confirmed_once:
            self._confirmed_once = True
            self.query_one("#delete_node_title", Label).update(
                "Are you sure? This cannot be undone."
            )
            self.query_one("#btn_delete_node", Button).label = (
                "Yes, delete permanently"
            )
        else:
            self.dismiss(True)

    @on(Button.Pressed, "#btn_delete_node_cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class CleanupAgentModal(ModalScreen):
    """Confirm removal of a finished/failed agent's status artifacts (t983_9 /
    t535). Returns True (confirmed) or False (cancelled) via dismiss(). Carries
    its own DEFAULT_CSS so it is self-contained (per tui_conventions).
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    CleanupAgentModal {
        align: center middle;
    }
    #cleanup_agent_dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    #cleanup_agent_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }
    #cleanup_agent_dialog > Label {
        width: 100%;
    }
    #cleanup_agent_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        agent_name: str,
        *,
        title: str | None = None,
        body: str | None = None,
    ):
        super().__init__()
        self.agent_name = agent_name
        # t1018_2: optional overrides so the same modal confirms a group-level
        # cleanup (re-run-fresh path) as well as a single-agent cleanup.
        self._title = title or f"Clean up agent [bold]{agent_name}[/]?"
        self._body = body or (
            "[dim]Removes its status / alive / output / log files from the "
            "crew worktree. This cannot be undone.[/dim]"
        )

    def compose(self) -> ComposeResult:
        with Container(id="cleanup_agent_dialog"):
            yield Label(self._title, id="cleanup_agent_title")
            yield Label(self._body)
            yield Label("[dim]Enter to confirm  Esc to cancel[/dim]")
            with Horizontal(id="cleanup_agent_buttons"):
                yield Button(
                    "Clean up", variant="warning", id="btn_cleanup_agent"
                )
                yield Button(
                    "Cancel", variant="default", id="btn_cleanup_agent_cancel"
                )

    @on(Button.Pressed, "#btn_cleanup_agent")
    def on_cleanup(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cleanup_agent_cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class NodeDetailModal(ModalScreen):
    """Modal for viewing node details with tabbed content (Metadata, Proposal)."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("tab", "focus_minimap", "Minimap", priority=True),
        Binding("v", "fullscreen_view", "Fullscreen view"),
        Binding("e", "export", "Export..."),
    ]

    def __init__(self, node_id: str, session_path: Path):
        super().__init__()
        self.node_id = node_id
        self.session_path = session_path
        self._proposal_parsed = None
        self._proposal_text = ""

    def compose(self) -> ComposeResult:
        from section_viewer import SectionAwareMarkdown, SectionMinimap
        with Container(id="node_detail_dialog"):
            yield Label(self._dialog_title_text(), id="node_detail_title")
            with TabbedContent(id="node_detail_tabs"):
                with TabPane("Metadata", id="tab_metadata"):
                    yield VerticalScroll(
                        NodeDetailPanel(
                            self.session_path,
                            title_id="modal_node_title",
                            info_id="modal_node_info",
                            id="modal_node_panel",
                        ),
                        id="metadata_scroll",
                    )
                with TabPane("Proposal", id="tab_proposal"):
                    with Horizontal(id="proposal_pane"):
                        yield SectionMinimap(
                            id="proposal_minimap", classes="node_detail_minimap"
                        )
                        yield SectionAwareMarkdown(id="proposal_content")
            with Horizontal(id="node_detail_buttons"):
                yield from self._dialog_buttons()
            yield Footer()

    def _dialog_title_text(self) -> str:
        """Dialog title text. Overridden by NodeHub to read "Node Hub: …"."""
        return f"Node Detail: {self.node_id}"

    def _dialog_buttons(self):
        """Yield the dialog's footer buttons. NodeHub overrides this to prepend
        an Operations button. The Close button id (``#btn_close_detail``) is
        load-bearing — ``close_detail`` and the CSS target it."""
        yield Button("Close", variant="default", id="btn_close_detail")

    def on_mount(self) -> None:
        """Load node data into both tabs."""
        # --- Metadata tab (shared NodeDetailPanel renderer) ---
        self.query_one(
            "#modal_node_panel", NodeDetailPanel).update(self.node_id)

        from section_viewer import SectionAwareMarkdown

        # --- Proposal tab ---
        try:
            proposal = read_proposal(self.session_path, self.node_id)
        except Exception:
            proposal = "*No proposal found.*"
        self._proposal_text = proposal
        parsed_proposal = parse_sections(proposal)
        prop_content = self.query_one("#proposal_content", SectionAwareMarkdown)
        prop_content.update_content(proposal, parsed_proposal)
        prop_minimap = self.query_one("#proposal_minimap")
        # populate() clears stale rows and adds one per section (none when
        # there are no sections), so it also resets the minimap state.
        prop_minimap.populate(parsed_proposal)
        if parsed_proposal.sections:
            self._proposal_parsed = parsed_proposal
            prop_minimap.display = True
        else:
            self._proposal_parsed = None
            # No sections → hide the empty minimap so the proposal takes the
            # full pane width.
            prop_minimap.display = False

    def on_section_minimap_section_selected(self, event) -> None:
        """Scroll the selected tab's content to the chosen section's heading.

        Delegates to ``SectionAwareMarkdown.request_scroll_to_section``, which
        targets the section's actual rendered heading (exact, no overshoot)
        rather than a line-ratio estimate, and defers until the markdown's
        async render completes.
        """
        from section_viewer import SectionAwareMarkdown
        minimap_id = event.control.id
        if minimap_id == "proposal_minimap":
            parsed, content_id = self._proposal_parsed, "#proposal_content"
        else:
            return
        if parsed is None:
            return
        content = self.query_one(content_id, SectionAwareMarkdown)
        content.request_scroll_to_section(event.section_name)
        # SectionAwareMarkdown is a VerticalScroll → focusing it lets up/down
        # scroll the content after a section is selected.
        content.focus()
        event.stop()

    def action_focus_minimap(self) -> None:
        """Tab on the Proposal tab → focus the inline minimap.

        No-op when focus is already inside the minimap, so Tab presses while
        the user is navigating minimap rows do not jump back to row 0.
        """
        from textual.actions import SkipAction
        tabbed = self.query_one(TabbedContent)
        if tabbed.active == "tab_proposal":
            mm_sel = "#proposal_minimap"
        else:
            raise SkipAction()
        minimaps = self.query(mm_sel)
        if not minimaps:
            raise SkipAction()
        minimap = minimaps.first()
        focused = self.screen.focused
        if focused is not None:
            walker = focused
            while walker is not None:
                if walker is minimap:
                    return  # Already on minimap (or one of its rows): no-op.
                walker = walker.parent
        minimap.focus_first_row()

    def action_fullscreen_view(self) -> None:
        """V → push SectionViewerScreen for the active tab's content."""
        tabbed = self.query_one(TabbedContent)
        if tabbed.active == "tab_proposal":
            content = self._proposal_text
            title = f"Proposal: {self.node_id}"
        else:
            self.notify(
                "Fullscreen viewer only works on the Proposal tab",
                severity="warning",
            )
            return
        if not content:
            self.notify("No content on this tab", severity="warning")
            return
        from section_viewer import SectionViewerScreen
        self.app.push_screen(SectionViewerScreen(content, title=title))

    def action_export(self) -> None:
        """E → open ExportNodeDetailModal for the active node's content."""
        tabbed = self.query_one(TabbedContent)
        active_tab = tabbed.active or ""
        # Pre-check the proposal on the Proposal/Metadata tabs; the user can
        # still adjust in the modal.
        default_proposal = active_tab in ("tab_proposal", "tab_metadata")
        last_dir = getattr(self.app, "_last_export_dir", None) or str(Path.cwd())
        self.app.push_screen(
            ExportNodeDetailModal(
                node_id=self.node_id,
                task_num=self.app.task_num,
                proposal_text=self._proposal_text,
                default_proposal=default_proposal,
                default_dir=last_dir,
            ),
            callback=self._on_export_done,
        )

    def _on_export_done(self, result) -> None:
        if not result:
            return
        self.app._last_export_dir = result["dir"]
        paths = result["written"]
        if paths:
            self.notify("Exported:\n" + "\n".join(paths), timeout=6)

    @on(Button.Pressed, "#btn_close_detail")
    def close_detail(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class NodeHub(NodeDetailModal):
    """Node Hub overlay (Enter, t983_5): the shared Detail surface (Metadata
    ``NodeDetailPanel`` + Proposal/minimap, inherited from ``NodeDetailModal``)
    plus an **Operations** entry that launches the contextual Operations dialog
    (t983_4) seeded from the current selection. Unifies the node-detail entry
    points and is the second launch surface (besides ``A``) that t983_6/t983_7
    plug into."""

    BINDINGS = [
        Binding("a", "operations", "Operations"),
        Binding("c", "compare", "Compare"),
    ]

    def _dialog_title_text(self) -> str:
        return f"Node Hub: {self.node_id}"

    def _dialog_buttons(self):
        yield Button("Operations", variant="primary", id="btn_node_hub_ops")
        yield Button("Compare", variant="default", id="btn_node_hub_compare")
        yield Button("Close", variant="default", id="btn_close_detail")

    def action_operations(self) -> None:
        """`a` → dismiss with the Operations launch verb (the app callback
        opens the Operations dialog once the Hub is closed)."""
        self.dismiss(NodeHubResult(NODE_HUB_OPERATIONS, self.node_id))

    @on(Button.Pressed, "#btn_node_hub_ops")
    def _open_operations(self) -> None:
        self.dismiss(NodeHubResult(NODE_HUB_OPERATIONS, self.node_id))

    def action_compare(self) -> None:
        """`c` → dismiss with the Compare launch verb (t983_7); the app callback
        opens the matrix overlay on this node unioned with the marked set."""
        self.dismiss(NodeHubResult(NODE_HUB_COMPARE, self.node_id))

    @on(Button.Pressed, "#btn_node_hub_compare")
    def _open_compare(self) -> None:
        self.dismiss(NodeHubResult(NODE_HUB_COMPARE, self.node_id))


class CompareMatrixModal(ModalScreen):
    """Dimension-comparison matrix overlay (t983_7).

    Re-homes the former Compare-tab matrix as a modal opened from the marked set
    (Browse ``c``), the Node Hub (``c`` / Compare button), or the graph
    ``x``/Enter picker. Builds the matrix from 2-4 node ids via the pure
    ``compare_matrix_rows`` and offers an in-modal ``D`` to diff the first two
    proposals (pushed *over* this modal, returning to the matrix on dismiss —
    the same ``self.app.push_screen`` pattern ``NodeDetailModal`` uses for its
    fullscreen view)."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("D", "diff", "Diff"),
    ]

    def __init__(self, session_path: Path, node_ids: list[str]):
        super().__init__()
        self.session_path = session_path
        self.node_ids = node_ids

    def compose(self) -> ComposeResult:
        with Container(id="compare_matrix_dialog"):
            yield Label(
                f"Compare: {', '.join(self.node_ids)}",
                id="compare_matrix_title",
            )
            yield VerticalScroll(id="compare_matrix_content")
            yield Footer()

    def on_mount(self) -> None:
        node_dims = {
            nid: extract_dimensions(read_node(self.session_path, nid))
            for nid in self.node_ids
        }
        container = self.query_one("#compare_matrix_content", VerticalScroll)
        rows = compare_matrix_rows(node_dims, self.node_ids)
        if rows is None:
            container.mount(Label("No dimension fields found in selected nodes"))
            return
        # DataTable assembly needs an active App (add_column measures widths),
        # so it lives here, not in the pure compare_matrix_rows.
        table = DataTable(id="compare_table", cursor_type="row")
        table.add_column("Dimension", key="dim")
        for nid in self.node_ids:
            table.add_column(nid, key=nid)
        for row_key, cells in rows:
            table.add_row(*cells, key=row_key)
        container.mount(table)
        self.call_after_refresh(table.focus)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_diff(self) -> None:
        """`D` → open the proposal diff of the first two compared nodes, stacked
        over this modal (re-homed from the old app-level ``action_compare_diff``;
        body otherwise verbatim)."""
        if len(self.node_ids) < 2:
            return
        n1, n2 = self.node_ids[:2]
        p1 = self.session_path / "br_proposals" / f"{n1}.md"
        p2 = self.session_path / "br_proposals" / f"{n2}.md"
        missing = [p for p in (p1, p2) if not p.is_file()]
        if missing:
            self.notify(
                f"Proposal file missing: {missing[0].name}",
                severity="warning",
            )
            return
        from diffviewer.diff_viewer_screen import DiffViewerScreen
        self.app.push_screen(
            DiffViewerScreen(str(p1), [str(p2)], mode="classical")
        )


class ExportNodeDetailModal(ModalScreen):
    """Modal: pick what to export (proposal) and the output directory."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        node_id: str,
        task_num: str,
        proposal_text: str,
        default_proposal: bool,
        default_dir: str,
    ):
        super().__init__()
        self.node_id = node_id
        self.task_num = task_num
        self._proposal_text = proposal_text
        self._default_proposal = default_proposal and bool(proposal_text)
        self._default_dir = default_dir

    def compose(self) -> ComposeResult:
        with Container(id="export_modal_dialog"):
            yield Label(
                f"Export node detail: {self.node_id}",
                id="export_modal_title",
            )
            yield Label("Output directory:")
            yield Input(
                value=self._default_dir,
                placeholder="/path/to/dir",
                id="export_modal_dir",
            )
            yield Checkbox(
                f"Proposal{'' if self._proposal_text else ' (empty)'}",
                value=self._default_proposal,
                id="export_modal_chk_proposal",
                disabled=not self._proposal_text,
            )
            with Horizontal(id="export_modal_buttons"):
                yield Button("Export", variant="primary", id="btn_export_ok")
                yield Button("Cancel", variant="default", id="btn_export_cancel")

    @on(Button.Pressed, "#btn_export_cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn_export_ok")
    def _confirm(self) -> None:
        dir_str = self.query_one("#export_modal_dir", Input).value
        do_proposal = self.query_one("#export_modal_chk_proposal", Checkbox).value
        if not do_proposal:
            self.notify("Select Proposal to export", severity="warning")
            return
        target, err = _validate_export_dir(dir_str)
        if err is not None:
            self.notify(err, severity="error")
            return
        try:
            written = _write_node_exports(
                target,
                self.task_num,
                self.node_id,
                self._proposal_text,
                do_proposal,
            )
        except OSError as exc:
            self.notify(f"Write failed: {exc}", severity="error")
            return
        self.dismiss({"dir": str(target), "written": written})


class OperationDetailScreen(ModalScreen):
    """Modal showing everything about the operation that generated a node.

    Pushed by the 'o' keybinding (wired in t749_6) from the brainstorm
    dashboard. Reads ``br_groups.yaml`` and the agent input/output/log
    files in the session worktree to render an Overview tab + one
    per-agent tab.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close", show=False),
    ]

    def __init__(self, group_name: str, session_path: Path) -> None:
        super().__init__()
        self.group_name = group_name
        self.session_path = session_path
        self.group_info: dict = {}

    def compose(self) -> ComposeResult:
        # Render a lightweight skeleton synchronously so the modal
        # appears immediately on `o`. The heavy file reads that
        # populate the tabs run in on_mount via an async worker,
        # giving the user instant visual feedback (LoadingIndicator).
        with Container(id="op_detail_dialog"):
            yield Label(
                f"Operation: {self.group_name}",
                id="op_detail_title",
            )
            with Container(id="op_detail_content"):
                yield LoadingIndicator(id="op_detail_loading")
            with Horizontal(id="op_detail_buttons"):
                yield Button(
                    "Close", variant="default", id="btn_close_op_detail"
                )
            yield Footer()

    def on_mount(self) -> None:
        # Schedule heavy reads via a worker so the LoadingIndicator
        # paints first. The worker is async so we can await each
        # mount/remove (Textual's mount/remove return AwaitMount /
        # AwaitRemove — racing them produces "id already mounted" or
        # silent-dismiss crashes).
        self._populate_content_worker()

    @work
    async def _populate_content_worker(self) -> None:
        try:
            self.group_info = _read_groups(self.session_path).get(
                self.group_name, {}
            )
            loading = self.query_one("#op_detail_loading", LoadingIndicator)
            content = self.query_one("#op_detail_content", Container)

            if not self.group_info:
                await content.mount(
                    Label(
                        f"(no group entry recorded for `{self.group_name}`)",
                        id="op_detail_missing",
                    )
                )
                await loading.remove()
                return

            self.query_one("#op_detail_title", Label).update(
                self._build_title()
            )

            tabbed = TabbedContent(id="op_detail_tabs")
            await content.mount(tabbed)
            await tabbed.add_pane(
                TabPane(
                    "Overview",
                    VerticalScroll(
                        *self._build_overview_widgets(),
                        classes="op_tab_scroll",
                    ),
                    id="op_overview",
                )
            )
            for agent in self.group_info.get("agents") or []:
                await tabbed.add_pane(
                    TabPane(
                        agent,
                        VerticalScroll(
                            *self._build_agent_widgets(agent),
                            classes="op_tab_scroll",
                        ),
                        id=f"tab_agent_{agent}",
                    )
                )
            await loading.remove()
            # Focus the tab row so arrow-key navigation works
            # immediately (otherwise focus lands on the Close button
            # after LoadingIndicator removal).
            try:
                tabbed.query_one(Tabs).focus()
            except Exception:
                pass
        except Exception as exc:
            self.notify(
                f"Failed to load operation details: {exc}",
                severity="error",
            )

    def _build_title(self) -> str:
        op = self.group_info.get("operation", "?")
        status = self.group_info.get("status", "Unknown")
        op_style = OP_BADGE_STYLES.get(op, UNKNOWN_OP_STYLE)
        color_hex = op_style.color.name if op_style.color else "#888"
        return (
            f"[bold {color_hex}]Operation: {op}[/]  "
            f"[dim]({self.group_name})[/]  "
            f"\\[{status}]"
        )

    def _build_overview_widgets(self) -> list:
        created_at = self.group_info.get("created_at", "")
        head = self.group_info.get("head_at_creation") or "(none)"
        nodes_created = self.group_info.get("nodes_created") or []
        widgets: list = [
            Static(f"[bold]Created at:[/] {created_at}"),
            Static(f"[bold]HEAD at creation:[/] {head}"),
            Static(
                f"[bold]Nodes created:[/] "
                f"{', '.join(nodes_created) if nodes_created else '(none yet)'}"
            ),
            Static(""),
        ]

        refs = list_op_inputs(self.group_info)
        if not refs:
            widgets.append(
                Label("[dim](no agents registered yet — input pending)[/]")
            )
        else:
            ref = refs[0]
            content = resolve_ref(self.session_path, ref)
            title_suffix = ref.section or "(whole file)"
            widgets.append(Static(f"[bold]Input — {title_suffix}[/]"))
            if not content:
                widgets.append(Label("[dim](no input found)[/]"))
            else:
                widgets.append(Markdown(content))

        agents = self.group_info.get("agents") or []
        if agents:
            widgets.append(Static(""))
            widgets.append(Static("[bold]Agent statuses[/]"))
            for name in agents:
                widgets.append(Static(self._agent_status_line(name)))
        return widgets

    def _agent_status_line(self, name: str) -> str:
        status_path = self.session_path / f"{name}_status.yaml"
        status = "Unknown"
        atype = ""
        if status_path.is_file():
            try:
                data = read_yaml(str(status_path)) or {}
                status = data.get("status", "Unknown")
                atype = data.get("agent_type", "")
            except Exception:
                pass
        color = AGENT_STATUS_COLORS.get(status, "#888888")
        type_label = f" ({atype})" if atype else ""
        return (
            f"  [{color}]●[/{color}] {name}{type_label}  "
            f"[{color}]{status}[/{color}]"
        )

    def _build_agent_widgets(self, name: str) -> list:
        input_content = resolve_ref(
            self.session_path, OpDataRef("agent_input", name)
        )
        output_content = resolve_ref(
            self.session_path, OpDataRef("agent_output", name)
        )
        log_path = self.session_path / f"{name}_log.txt"
        log_content = read_log_tail(str(log_path), lines=200)

        return [
            Static("[bold]Input[/]"),
            Markdown(input_content or "*(no input file)*"),
            Static(""),
            Static("[bold]Output[/]"),
            Markdown(output_content or "*(agent has not produced output yet)*"),
            Static(""),
            Static("[bold]Log (last 200 lines)[/]"),
            Static(log_content or "*(no log)*", classes="op_agent_log"),
        ]

    def action_close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn_close_op_detail")
    def _on_close_button(self) -> None:
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


class OperationHelpModal(ModalScreen):
    """Modal showing summary, I/O contract, and use cases for an operation.

    Triggered by the op-help shortcut from any Actions wizard step. On Step 1
    the op_key comes from the focused `OperationRow`; on Step 2+ it comes
    from `BrainstormApp._wizard_op`. Content is sourced from
    `_OPERATION_HELP` (see the source-trace comments above each entry).
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
    ]

    def __init__(self, op_key: str):
        super().__init__()
        self.op_key = op_key

    def compose(self) -> ComposeResult:
        info = _OPERATION_HELP.get(self.op_key)
        title = info["title"] if info else self.op_key
        with Container(id="op_help_dialog"):
            yield Label(f"Operation: {title}", id="op_help_title")
            yield VerticalScroll(
                Markdown(self._render_markdown(info), id="op_help_content"),
                id="op_help_scroll",
            )
            yield Label("[dim]Esc close[/]", id="op_help_footer")

    def _render_markdown(self, info: dict | None) -> str:
        if not info:
            return f"*No help available for `{self.op_key}`.*"
        parts: list[str] = [info["summary"], ""]
        if info.get("reads_from_parent"):
            parts.append("## Reads from base/parent node(s)")
            parts.extend(f"- {x}" for x in info["reads_from_parent"])
            parts.append("")
        if info.get("produces"):
            parts.append("## Produces")
            parts.extend(f"- {x}" for x in info["produces"])
            parts.append("")
        if info.get("use_cases"):
            parts.append("## Use cases")
            parts.extend(f"- {x}" for x in info["use_cases"])
        return "\n".join(parts)

    def action_close(self) -> None:
        self.dismiss(None)


class NodeActionSelectModal(ModalScreen):
    """The contextual **Operations** dialog for the current Browse selection.

    Surfaced via the `A` keybinding on the Browse tab. Offers every operation
    that can run from the selection — the single-node ops (explore, the
    fast-track preset, delete), the module ops (module_decompose / module_merge
    / module_sync, seeded from the node's subgraph), and the multi-node ops
    (compare / synthesize). Each op is shown disabled with a reason when it does
    not apply to the current selection — single-node ops grey when 2+ nodes are
    marked, multi-node ops grey when fewer than 2 are — per the ``op_states``
    map (computed by the caller via :func:`op_states_for_selection`). ``H`` on a
    focused row opens its :class:`OperationHelpModal`. Returns the chosen op_key
    string via dismiss(), or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("H", "op_help", "Help", show=False),
    ]

    # Operation keys offered, in contextual display order (parent t983 design:
    # explore · compare · synthesize · module_* · fast_track · delete).
    # Labels/descriptions are pulled from _OP_LABELS so the picker stays in sync
    # with the wizard. ``fast_track`` (UC-3 preset, t756_6) and ``delete`` are
    # NOT wizard ops in _OP_LABELS — fast_track seeds a single-module
    # module_decompose, delete is handled inline via DeleteNodeModal — so their
    # labels live in _LOCAL_LABELS.
    _OPS = [
        "explore", "compare", "synthesize",
        "module_decompose", "module_merge", "module_sync",
        "fast_track", "delete",
    ]

    _LOCAL_LABELS = {
        "fast_track": (
            "Fast-track this module",
            "Extract one module into a linked aitask in a single pass",
        ),
        "delete": (
            "Delete this node",
            "Remove this node and all its descendants",
        ),
    }

    def __init__(self, node_id, op_states=None, targets=None):
        super().__init__()
        self.node_id = node_id
        # op_states[op_key] = (disabled: bool, reason: str). Computed by the
        # caller (action_node_action) so the modal stays session-free/testable.
        self.op_states = op_states or {}
        # Effective target node ids the chosen op acts on
        # (NodeSelection.effective()); defaults to the lone primary node so the
        # dialog still works when opened with no marked set (t983_4).
        self.targets = list(targets) if targets else [node_id]

    def _targets_summary(self) -> str:
        """One-line render of the effective target set for the dialog header,
        capped via :func:`format_node_id_summary` so a large marked set cannot
        overflow the height-bounded modal (t983_4)."""
        return f"[dim]{format_node_id_summary(self.targets, 'Targets')}[/]"

    def compose(self) -> ComposeResult:
        with Container(id="node_action_dialog"):
            yield Label("Operations", id="node_action_title")
            yield Label(self._targets_summary(), id="node_action_targets")
            yield Label(
                "[dim]↑↓ Navigate  Enter Select  H Help  Esc Cancel[/dim]",
                id="node_action_hint",
            )
            with VerticalScroll(id="node_action_list"):
                for op_key in self._OPS:
                    label, desc = self._LOCAL_LABELS.get(
                        op_key, _OP_LABELS.get(op_key, (op_key, ""))
                    )
                    # op_states (computed by the caller) is authoritative; all
                    # ops default to enabled when no map was supplied.
                    if op_key in self.op_states:
                        disabled, reason = self.op_states[op_key]
                    else:
                        disabled, reason = (False, "")
                    if disabled and reason:
                        desc = f"{desc}  [italic]({reason})[/]"
                    yield OperationRow(op_key, label, desc, disabled=disabled)
            with Horizontal(id="node_action_buttons"):
                yield Button(
                    "Cancel", variant="default", id="btn_node_action_cancel"
                )

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_first_enabled)

    def _focus_first_enabled(self) -> None:
        for row in self.query(OperationRow):
            if not row.op_disabled:
                row.selected = True
                row.focus()
                break

    def _rows(self) -> list:
        return [r for r in self.query(OperationRow) if r.can_focus]

    def on_key(self, event) -> None:
        if event.key in ("up", "down"):
            if self._navigate(1 if event.key == "down" else -1):
                event.prevent_default()
                event.stop()
            return
        if event.key == "enter":
            focused = self.focused
            if isinstance(focused, OperationRow) and not focused.op_disabled:
                event.prevent_default()
                event.stop()
                self.dismiss(focused.op_key)

    def _navigate(self, direction: int) -> bool:
        rows = self._rows()
        if not rows:
            return False
        focused = self.focused
        current = rows.index(focused) if focused in rows else None
        if current is None:
            new_idx = 0
        else:
            new_idx = (current + direction) % len(rows)
        for r in rows:
            r.selected = False
        rows[new_idx].selected = True
        rows[new_idx].focus()
        rows[new_idx].scroll_visible()
        return True

    @on(OperationRow.Activated)
    def _on_row_activated(self, event: OperationRow.Activated) -> None:
        # Mouse click on an enabled row selects immediately. stop() keeps
        # the message off the app-level on_operation_row_activated handler.
        event.stop()
        if not event.row.op_disabled:
            self.dismiss(event.row.op_key)

    @on(Button.Pressed, "#btn_node_action_cancel")
    def _on_cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_op_help(self) -> None:
        """`H`: open the OperationHelpModal for the focused op row (t983_4).

        Preserves the `_OPERATION_HELP` discoverability the Actions-tab wizard
        offers, now from the Operations dialog. fast_track / delete have no
        help entry — surface an explicit notice rather than a silent no-op so
        `H` always gives feedback.
        """
        focused = self.focused
        if not isinstance(focused, OperationRow):
            return
        op_key = focused.op_key
        if op_key in _OPERATION_HELP:
            self.app.push_screen(OperationHelpModal(op_key))
        else:
            self.app.notify(
                "No help available for this operation.",
                severity="information",
            )


class ModulePreviewScreen(ModalScreen):
    """Review gate for ``module_decompose`` (t929_1: iterate-before-apply).

    Shows the module roots a decomposer proposed and lets the operator:
      - **Accept** — apply the proposal to the graph.
      - **Re-run** — discard this attempt and dispatch a revised one, steered by
        free-text instructions that OVERRIDE the original Decomposition Plan.
      - **Cancel** — discard the proposal; the graph is left untouched.

    Returns ``{"action": "accept"|"rerun"|"cancel", "steer": <str>}`` via
    ``dismiss``; escape dismisses as cancel. The screen is session-free (it
    receives already-parsed blocks) so it stays testable.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, agent_name: str, blocks: list[dict]):
        super().__init__()
        self.agent_name = agent_name
        self.blocks = blocks

    def compose(self) -> ComposeResult:
        with Container(id="module_preview_dialog"):
            yield Label(
                f"Review module decomposition "
                f"([bold]{len(self.blocks)}[/] module(s))",
                id="module_preview_title",
            )
            yield Label(
                "[dim]Review the proposed modules before they are applied to "
                "the graph.[/dim]",
                id="module_preview_hint",
            )
            with VerticalScroll(id="module_preview_list"):
                for blk in self.blocks:
                    yield Label(
                        f"[bold]{blk.get('module_name', '?')}[/]  "
                        f"[dim]{blk.get('node_id', '')}[/]"
                    )
                    yield Static(
                        blk.get("proposal_excerpt", ""),
                        classes="module_preview_excerpt",
                    )
            yield Label("Steering for Re-run (overrides the plan on conflict):")
            yield TextArea("", id="ta_module_preview_steer")
            with Horizontal(id="module_preview_buttons"):
                yield Button(
                    "Accept", variant="success", id="btn_module_preview_accept"
                )
                yield Button(
                    "Re-run", variant="primary", id="btn_module_preview_rerun"
                )
                yield Button(
                    "Cancel", variant="default", id="btn_module_preview_cancel"
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_module_preview_accept":
            self.dismiss({"action": "accept", "steer": ""})
        elif bid == "btn_module_preview_rerun":
            steer = self.query_one("#ta_module_preview_steer", TextArea).text.strip()
            if not steer:
                self.notify(
                    "Enter steering text to re-run, or choose Accept / Cancel.",
                    severity="warning",
                )
                return
            self.dismiss({"action": "rerun", "steer": steer})
        else:
            self.dismiss({"action": "cancel", "steer": ""})

    def action_cancel(self) -> None:
        self.dismiss({"action": "cancel", "steer": ""})

