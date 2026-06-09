"""Brainstorm TUI: interactive design space exploration with Textual."""

from __future__ import annotations

import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, NamedTuple

# Allow importing sibling packages (brainstorm, agentcrew)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402
from keybinding_registry import resolve_key  # noqa: E402

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
    Input,
    Label,
    LoadingIndicator,
    Markdown,
    RadioButton,
    RadioSet,
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

from diffviewer.diff_display import word_diff_texts, TAG_STYLES

from brainstorm.brainstorm_dag import (
    UMBRELLA_SUBGRAPH,
    _node_module,
    _read_graph_state,
    delete_node_cascade,
    get_active_dimensions,
    get_dimension_fields,
    get_head,
    is_ancestor_subgraph,
    list_nodes,
    list_subgraphs,
    node_descendants_closure,
    read_node,
    read_plan,
    read_proposal,
    set_head,
)
from brainstorm.brainstorm_schemas import extract_dimensions, group_dimensions_by_prefix
from brainstorm.brainstorm_sections import (
    best_section_for_dimension,
    dimension_matches_tag,
    get_sections_for_dimension,
    parse_sections,
)
from brainstorm.brainstorm_dag_display import (
    DAGDisplay,
    MODULE_STATUS_STYLES,
    OP_BADGE_STYLES,
    UNKNOWN_OP_STYLE,
    UNKNOWN_STATUS_STYLE,
)
from brainstorm.brainstorm_status import module_status_rows
from brainstorm.brainstorm_op_refs import (
    OpDataRef,
    list_op_inputs,
    resolve_ref,
)
from brainstorm.polling_indicator import PollingIndicator
from brainstorm.brainstorm_session import (
    _module_deferred_map,
    _write_module_deferred,
    archive_session,
    crew_worktree,
    finalize_session,
    GROUPS_FILE,
    load_session,
    record_operation,
    resolve_node_group,
    save_session,
    session_exists,
)
from brainstorm.brainstorm_crew import (
    register_comparator,
    register_detailer,
    register_explorer,
    register_module_decomposer,
    register_module_merger,
    register_module_syncer,
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
# Ops that get a source-node-select step. module_decompose picks a source node
# too, but — unlike the ops above — must NOT trigger the section_select step
# (which stays gated on the narrower _NODE_SELECT_OPS).
_NODE_SELECT_STEP_OPS = _NODE_SELECT_OPS | {"module_decompose"}
_SUBGRAPH_SELECT_OPS = _NODE_SELECT_OPS | {
    "module_decompose", "module_merge", "module_sync",
}

_WIZARD_OP_TO_AGENT_TYPE = {
    "explore": "explorer",
    "compare": "comparator",
    "synthesize": "synthesizer",
    "detail": "detailer",
    "patch": "patcher",
    "module_decompose": "module_decomposer",
    "module_merge": "module_merger",
    "module_sync": "module_syncer",
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


def _parse_dimension_label(label: str) -> str:
    """Recover the raw dimension key from a 'key — value' checkbox label.

    Safe because dimension keys never contain spaces and the label separator is
    ``" — "``, so the key is always the first space-delimited token (even after
    the descriptive value is truncated).
    """
    return label.split(" ", 1)[0]


def _read_groups(session_path: Path) -> dict:
    """Return the inner ``groups`` dict from br_groups.yaml (or {})."""
    from brainstorm.brainstorm_session import _read_groups_file
    data = _read_groups_file(str(session_path / GROUPS_FILE))
    return data.get("groups", {}) or {}

_DESIGN_OPS = [
    ("explore", "Explore", "Create new design variants from a base node"),
    ("compare", "Compare", "Run agent comparison across nodes"),
    ("synthesize", "Synthesize", "Merge multiple nodes into a synthesis"),
    ("detail", "Detail", "Generate implementation plan for a node"),
    ("patch", "Patch", "Tweak an existing plan"),
    ("module_decompose", "Module Decompose", "Fork module subgraph roots"),
    ("module_merge", "Module Merge", "Merge a module up into an ancestor"),
    ("module_sync", "Module Sync", "Pull a linked module's as-implemented design back in"),
]

_SESSION_OPS = [
    ("pause", "Pause", "Pause the active session"),
    ("resume", "Resume", "Resume a paused session"),
    ("finalize", "Finalize", "Copy HEAD plan to aiplans/ and mark completed"),
    ("archive", "Archive", "Mark completed session as archived"),
    ("delete", "Delete", "Permanently delete session, worktree, and branch"),
]

# Flat op_key -> (label, brief description) map built from both op lists.
# Used by _mount_op_context_header to remind the user which operation the
# wizard is configuring on Step 2 onwards.
_OP_LABELS: dict[str, tuple[str, str]] = {
    op_key: (label, desc) for op_key, label, desc in (_DESIGN_OPS + _SESSION_OPS)
}


# Help text condensed from the agent prompt templates in
# .aitask-scripts/brainstorm/templates/*.md (one prompt per design op) and
# from the session lifecycle status machine in brainstorm_session.py.
# When those sources change, update the per-entry source comments below
# AND the corresponding "summary"/"reads_from_parent"/"produces" fields.
# Surfaced inline on Step 2+ (one-line header via _mount_op_context_header)
# and via the op-help shortcut on every wizard step (OperationHelpModal).
_OPERATION_HELP: dict[str, dict] = {
    # Source: .aitask-scripts/brainstorm/templates/explorer.md
    # I/O contract derived from "## Input" (reads parent YAML metadata,
    # proposal markdown, plan markdown if one exists, reference files) and
    # "## Output" (produces a new node: YAML metadata + proposal markdown;
    # no plan).
    "explore": {
        "title": "Explore — Architecture Explorer",
        "summary": (
            "Generate a new architectural proposal as a child of an existing "
            "base node, given an exploration mandate. The new node inherits "
            "the base node's dimension space and may modify, add, or replace "
            "values, but never silently drops a dimension."
        ),
        "reads_from_parent": [
            "YAML metadata of the base node (all dimensions: requirements_*, "
            "assumption_*, component_*, tradeoff_*).",
            "Proposal markdown of the base node (full architectural narrative).",
            "Plan markdown of the base node (if one exists).",
            "Reference files cited by the base node.",
        ],
        "produces": [
            "A new node with `parents = [base_node]`.",
            "A new YAML metadata file (description, dimensions, "
            "reference_files, created_by_group).",
            "A new proposal markdown.",
            "No plan — use Detail later to derive a plan from this proposal.",
        ],
        "use_cases": [
            "Branch off a parent node to try an alternate architecture under "
            "specific constraints (e.g., swap a component, relax an "
            "assumption).",
            "Iterate on a proposal by exploring a different component or "
            "assumption space.",
            "Run several explorers in parallel to fan out a design space.",
        ],
    },
    # Source: .aitask-scripts/brainstorm/templates/comparator.md
    # I/O from "## Input" — explicitly metadata-only ("You only need the
    # YAML metadata — do not read proposals, plans, or codebase files") —
    # and "## Output" (comparison matrix + delta summary; no new node, no
    # edits to existing nodes).
    "compare": {
        "title": "Compare — Tradeoff Analyst",
        "summary": (
            "Compare two or more nodes side-by-side across their YAML "
            "dimensions and produce a tradeoff matrix plus a delta summary. "
            "Does not read proposals, plans, or codebase files — comparisons "
            "are kept fast and dimension-focused."
        ),
        "reads_from_parent": [
            "YAML metadata only — across every selected node.",
            "Does NOT read proposals, plans, or codebase/reference files.",
        ],
        "produces": [
            "A comparison matrix (markdown table) — rows are dimensions, "
            "columns are nodes plus a Key Tradeoff column.",
            "A delta summary highlighting critical assumption differences "
            "and hidden risks.",
            "Optional winner declaration only when the user supplies a "
            "scoring metric.",
            "Does NOT create a new node, modify existing proposals/plans, "
            "or change YAML metadata.",
        ],
        "use_cases": [
            "Quickly spot dimension differences across sibling design "
            "variants before picking one.",
            "Score variants against an explicit metric supplied by the user.",
            "Surface infrastructure / integration risks that are easy to "
            "miss when reading proposals individually.",
        ],
    },
    # Source: .aitask-scripts/brainstorm/templates/synthesizer.md
    # I/O from "## Input" (reads source nodes' YAML metadata + proposal
    # markdown per the user's merge rules) and "## Output" (new node:
    # YAML + merged proposal; parents = [all source nodes]; includes a
    # Conflict Resolutions section).
    "synthesize": {
        "title": "Synthesize — Architecture Synthesizer",
        "summary": (
            "Merge components from multiple source nodes into a single "
            "synthesized node according to user-supplied merge rules. The "
            "synthesized node lists every source as a parent and documents "
            "how conflicts between sources were resolved."
        ),
        "reads_from_parent": [
            "YAML metadata from all selected source nodes.",
            "Proposal markdown from all selected source nodes.",
            "Reference files merged & deduplicated from all sources.",
        ],
        "produces": [
            "A new node with `parents = [all source nodes]`.",
            "A new merged YAML metadata file.",
            "A new merged proposal markdown including a Conflict "
            "Resolutions section.",
            "No plan — use Detail later to derive a plan.",
        ],
        "use_cases": [
            "Combine the data layer from one variant with the API layer "
            "from another into a unified design.",
            "Resolve component-level tradeoffs across siblings into a "
            "single proposal.",
        ],
    },
    # Source: .aitask-scripts/brainstorm/templates/detailer.md
    # I/O from "## Input" (reads node YAML metadata + proposal markdown +
    # reference files + project context like CLAUDE.md) and "## Output"
    # (single plan markdown attached to the same node; does NOT modify
    # the proposal or YAML metadata).
    "detail": {
        "title": "Detail — Implementation Planner",
        "summary": (
            "Translate a finalized proposal into a concrete, step-by-step "
            "implementation plan with file paths, code snippets, and "
            "verification steps. Steps are ordered by dependency."
        ),
        "reads_from_parent": [
            "YAML metadata of the selected node.",
            "Proposal markdown of the selected node.",
            "Reference files (local paths and cached URLs).",
            "Additional project context (e.g., CLAUDE.md, directory listings).",
        ],
        "produces": [
            "A single implementation plan markdown attached to the same "
            "node (Prerequisites + Step-by-Step Changes + per-component "
            "sub-sections).",
            "Does NOT modify the node's proposal or YAML metadata.",
        ],
        "use_cases": [
            "Convert the leading proposal into something a developer can "
            "implement directly.",
            "Re-detail a node after material proposal changes.",
        ],
    },
    # Source: .aitask-scripts/brainstorm/templates/patcher.md
    # I/O from "## Input" — plan is the edit target; proposal is read-only
    # and used only for impact analysis — and "## Output" (patched plan +
    # impact verdict NO_IMPACT/IMPACT_FLAG; optional updated metadata when
    # the patch flags an architectural change).
    "patch": {
        "title": "Patch — Plan Patcher",
        "summary": (
            "Apply a surgical, targeted modification to an existing "
            "implementation plan and assess whether the change has any "
            "architectural impact. Only the user-requested change is "
            "applied; unaffected steps remain byte-for-byte identical."
        ),
        "reads_from_parent": [
            "YAML metadata of the selected node.",
            "Plan markdown of the selected node — the edit target.",
            "Proposal markdown of the selected node — read-only, used only "
            "for impact analysis.",
        ],
        "produces": [
            "A patched plan markdown (only requested changes applied).",
            "An impact verdict: NO_IMPACT (purely local change) or "
            "IMPACT_FLAG (architectural implications listed).",
            "Optionally an updated YAML metadata file when the patch flags "
            "an architectural change (e.g., swapping a component).",
        ],
        "use_cases": [
            "Tweak a step in an approved plan without redoing the whole "
            "Detail pass.",
            "Swap one library for another and surface whether the change "
            "has architectural implications.",
        ],
    },
    "module_decompose": {
        "title": "Module Decompose — Module Fork",
        "summary": (
            "Fork the selected subgraph HEAD into one root node per named "
            "module so each module can evolve independently."
        ),
        "reads_from_parent": [
            "YAML metadata and proposal markdown of the selected subgraph HEAD.",
            "Existing section markers and component dimensions as boundary hints.",
        ],
        "produces": [
            "One new root node per module.",
            "Per-module HEAD/history entries in graph state.",
            "Optional linked child aitasks recorded in module_tasks.",
        ],
        "use_cases": [
            "Split a broad umbrella proposal into module-specific subgraphs.",
            "Fast-track one module into a linked implementation task.",
        ],
    },
    "module_merge": {
        "title": "Module Merge — Merge Up",
        "summary": (
            "Merge a refined source module into an ancestor destination "
            "subgraph, producing a 2-parent destination node."
        ),
        "reads_from_parent": [
            "Source module HEAD proposal.",
            "Destination subgraph HEAD proposal.",
            "User-supplied merge-up rules.",
        ],
        "produces": [
            "A new destination-subgraph node with parents "
            "[destination_head, source_head].",
            "The destination HEAD advances; the source HEAD is unchanged.",
        ],
        "use_cases": [
            "Absorb a refined module back into the umbrella proposal.",
            "Record explicit merge provenance across subgraphs.",
        ],
    },
    "module_sync": {
        "title": "Module Sync — Reconcile As-Implemented",
        "summary": (
            "Pull a fast-tracked module's as-implemented design back into its "
            "subgraph (new HEAD) so a later merge absorbs current reality, not a "
            "stale design. Read-only on the linked aitask."
        ),
        "reads_from_parent": [
            "Linked task plan (esp. Final Implementation Notes / Post-Review Changes).",
            "Scoped git diff of the linked task's commits since the last sync.",
            "aitask_explain_context historical scan of the touched files.",
        ],
        "produces": [
            "A new single-parent node that becomes the module's HEAD.",
            "An advanced last_synced_at[module] scan horizon.",
        ],
        "use_cases": [
            "Refresh a module's design after its linked task landed code.",
            "De-stale a module before merging it back up.",
        ],
    },
    # Source: BrainstormApp._is_session_op_disabled (this file) +
    # session status machine in brainstorm_session.py (init / active /
    # paused / completed / archived).
    "pause": {
        "title": "Pause — Session Lifecycle",
        "summary": (
            "Pause an `active` session. While paused, no new operations "
            "can be launched until the session is resumed. Existing "
            "in-flight agent runs are not interrupted."
        ),
        "use_cases": [
            "Step away from a session without it accepting new ops.",
            "Freeze the design space while reviewing a proposal externally.",
        ],
    },
    # Source: brainstorm_session.py — sets status back to `active` on a
    # paused session.
    "resume": {
        "title": "Resume — Session Lifecycle",
        "summary": (
            "Resume a `paused` session, returning it to `active` so design "
            "operations can be launched again."
        ),
        "use_cases": [
            "Continue work on a session that was paused earlier.",
        ],
    },
    # Source: brainstorm_session.finalize_session — copies the HEAD node's
    # plan into aiplans/ and marks the session `completed`. Requires HEAD
    # to be set and status to be `active`.
    "finalize": {
        "title": "Finalize — Session Lifecycle",
        "summary": (
            "Copy the HEAD node's implementation plan into aiplans/ and "
            "mark the session `completed`. Requires the session to be "
            "`active` and HEAD to point at a node that has a plan."
        ),
        "use_cases": [
            "Promote the chosen design's plan to the project's canonical "
            "aiplans/ directory once the brainstorm has converged.",
        ],
    },
    # Source: brainstorm_session.archive_session — flips a `completed`
    # session to `archived`.
    "archive": {
        "title": "Archive — Session Lifecycle",
        "summary": (
            "Mark a `completed` session as `archived`. The session and "
            "its data remain on disk but are surfaced as historical."
        ),
        "use_cases": [
            "Tidy up the active session list after finalization.",
        ],
    },
    # Source: brainstorm_session.delete_session — permanently removes the
    # session, its worktree directory, and its crew branch.
    "delete": {
        "title": "Delete — Session Lifecycle",
        "summary": (
            "Permanently delete the session, its worktree directory, and "
            "its crew git branch. NOT reversible — confirmation required."
        ),
        "use_cases": [
            "Discard an aborted exploration or a session whose history is "
            "no longer wanted.",
        ],
    },
}


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


class _InlineSectionMinimap:
    """Lazily-imported SectionMinimap subclass with no Tab binding.

    Used inside `NodeDetailModal` only, where Tab is owned by the dialog (it
    focuses the minimap). The fullscreen `SectionViewerScreen` continues to
    use the stock `SectionMinimap` and its built-in Tab toggle.

    Implemented as a function returning the subclass class, so the import of
    `SectionMinimap` stays lazy (matches the existing pattern at the call
    sites).
    """

    _cache = None

    @classmethod
    def cls(cls):
        if cls._cache is None:
            from section_viewer import SectionMinimap as _Base

            class _NoTabMinimap(_Base):
                BINDINGS: list = []

            cls._cache = _NoTabMinimap
        return cls._cache


class _PreviewMinimap:
    """Lazily-built SectionMinimap subclass for the config-step preview pane.

    Rebinds Tab / Shift+Tab to step the app-level preview focus ring
    (``BrainstormApp._cycle_preview_focus``: inputs → minimap → proposal
    markdown → wrap). SectionMinimap's stock ``tab → toggle_focus`` *priority*
    binding cannot simply be cleared (Textual merges BINDINGS across the MRO, so
    a ``BINDINGS = []`` subclass still inherits it), so we override it here with
    our own priority binding. Doing the focus move from a synchronous binding
    *action* (rather than a posted ToggleFocus message) is what makes the new
    focus stick.
    """

    _cache = None

    @classmethod
    def cls(cls):
        if cls._cache is None:
            from section_viewer import SectionMinimap as _Base

            class _PreviewMM(_Base):
                BINDINGS = [
                    Binding("tab", "preview_focus_advance", "Next", priority=True),
                    Binding(
                        "shift+tab", "preview_focus_retreat", "Prev", priority=True
                    ),
                ]

                def action_preview_focus_advance(self) -> None:
                    app = self.app
                    if hasattr(app, "_cycle_preview_focus"):
                        app._cycle_preview_focus(forward=True)

                def action_preview_focus_retreat(self) -> None:
                    app = self.app
                    if hasattr(app, "_cycle_preview_focus"):
                        app._cycle_preview_focus(forward=False)

            cls._cache = _PreviewMM
        return cls._cache


class ProposalPreviewPane(Horizontal):
    """Reusable side-by-side proposal viewer: a fixed minimap pane beside a
    scrollable Markdown.

    Adopts ``SectionViewerScreen``'s layout (minimap left, content right) so the
    minimap stays visible while the proposal scrolls, and delegates
    section-navigation to ``SectionAwareMarkdown.request_scroll_to_section`` —
    which scrolls to the section's actual rendered heading (exact, no overshoot)
    rather than a line-ratio estimate. Built for the explore / module-decompose
    wizard config steps (t945), mounted via
    ``BrainstormApp._mount_config_with_preview``.

    The minimap (``_PreviewMinimap``) rebinds Tab / Shift+Tab to drive the
    app-level focus ring (``_cycle_preview_focus``), cycling inputs → minimap →
    proposal markdown. Inputs and the markdown pane are routed by the app's
    ``on_key``; the minimap's own priority Tab binding hands back to the same
    ring so focus never sticks on the minimap.

    IMPORTANT: the pane mounts only a minimap + a ``SectionAwareMarkdown`` —
    never a ``TextArea`` / ``CycleField`` / ``RadioSet``. The config-step
    collectors in ``_actions_collect_config`` query ``#actions_content``
    recursively with single-match ``query_one(TextArea)`` /
    ``query_one(CycleField)``; adding any such widget here would make those
    queries ambiguous.
    """

    DEFAULT_CSS = """
    ProposalPreviewPane {
        height: 1fr;
        border-left: solid $primary;
    }
    ProposalPreviewPane > .preview_proposal_minimap {
        width: 28;
        max-width: 28;
        height: 1fr;
        max-height: 100%;
    }
    ProposalPreviewPane > #preview_proposal_content {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._parsed = None
        self._text = ""

    def compose(self) -> ComposeResult:
        from section_viewer import SectionAwareMarkdown
        yield _PreviewMinimap.cls()(classes="preview_proposal_minimap")
        yield SectionAwareMarkdown(id="preview_proposal_content")

    def _content(self):
        from section_viewer import SectionAwareMarkdown
        return self.query_one("#preview_proposal_content", SectionAwareMarkdown)

    def _minimap(self):
        return self.query_one(".preview_proposal_minimap")

    def populate(self, proposal_text: str) -> None:
        """Render *proposal_text* and (re)build the section minimap."""
        text = proposal_text if proposal_text else "*No proposal found.*"
        self._text = text
        parsed = parse_sections(text)
        self._content().update_content(text, parsed)
        minimap = self._minimap()
        # populate() clears any stale rows and adds one per section (none when
        # there are no sections), so this also resets the minimap on re-populate.
        minimap.populate(parsed)
        if parsed.sections:
            self._parsed = parsed
            minimap.display = True
        else:
            self._parsed = None
            # No sections → hide the (now-empty) minimap so the proposal takes
            # the full pane width.
            minimap.display = False

    def scroll_to_section(self, section_name: str) -> None:
        """Scroll the proposal so *section_name*'s heading sits at the top.

        Delegates to ``SectionAwareMarkdown.request_scroll_to_section``, which
        targets the section's actual rendered heading (exact, no overshoot)
        and defers until the markdown has finished its async render.
        """
        if self._parsed is None:
            return
        self._content().request_scroll_to_section(section_name)

    def on_ratio_change(self) -> None:
        """Keep the currently-top source line at the top across a width reflow.

        Operates on the inner ``SectionAwareMarkdown`` scroll (the markdown is
        what scrolls now that the minimap is a fixed sibling). Capture the top
        line *before* the width class swaps — ``scroll_offset.y`` still reflects
        the pre-reflow geometry — then re-apply after re-layout
        (``call_after_refresh``).
        """
        content = self._content()
        total = self._text.count("\n") + 1
        max_scroll = float(getattr(content, "max_scroll_y", 0) or 0)
        if total <= 0 or max_scroll <= 0:
            return
        top_line = round(content.scroll_offset.y / max_scroll * total)

        def _restore() -> None:
            new_max = float(getattr(content, "max_scroll_y", 0) or 0)
            if new_max <= 0:
                return
            content.scroll_to(y=(top_line / total) * new_max, animate=False)

        content.call_after_refresh(_restore)


class NodeDetailModal(ModalScreen):
    """Modal for viewing node details with tabbed content (Metadata, Proposal, Plan)."""

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
            yield Footer()

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
            prop_scroll = self.query_one("#proposal_scroll", VerticalScroll)
            prop_minimap = _InlineSectionMinimap.cls()(id="proposal_minimap")
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
            plan_scroll = self.query_one("#plan_scroll", VerticalScroll)
            plan_minimap = _InlineSectionMinimap.cls()(id="plan_minimap")
            plan_scroll.mount(plan_minimap, before="#plan_content")
            plan_minimap.populate(parsed_plan)

    def on_section_minimap_section_selected(self, event) -> None:
        """Scroll the active tab's Markdown to the selected section."""
        from section_viewer import estimate_section_y
        minimap_id = event.control.id
        if minimap_id == "proposal_minimap":
            parsed, text, scroll_id, md_id = (
                self._proposal_parsed,
                self._proposal_text,
                "#proposal_scroll",
                "#proposal_content",
            )
        elif minimap_id == "plan_minimap":
            parsed, text, scroll_id, md_id = (
                self._plan_parsed,
                self._plan_text,
                "#plan_scroll",
                "#plan_content",
            )
        else:
            return
        if parsed is None:
            return
        scroll = self.query_one(scroll_id, VerticalScroll)
        md = self.query_one(md_id, Markdown)
        # Same correction as SectionAwareMarkdown.scroll_to_section: map the
        # section's line ratio to the *scrollable* range below the minimap
        # (scroll.max_scroll_y minus the minimap's outer height), not the
        # markdown's full virtual height. Multiplying by virtual height
        # over-shoots by ~one viewport because the bottom viewport-worth of
        # content does not need to scroll past the visible area.
        total = text.count("\n") + 1
        minimap_height = float(event.control.outer_size.height)
        max_scroll = float(getattr(scroll, "max_scroll_y", 0) or 0)
        body_scroll_range = max(0.0, max_scroll - minimap_height)
        y_in_body = estimate_section_y(
            parsed, event.section_name, total, body_scroll_range
        )
        if y_in_body is not None:
            scroll.scroll_to(
                y=minimap_height + y_in_body, animate=False
            )
            # Markdown.can_focus is False, so we focus the parent
            # VerticalScroll — that's what consumes up/down for scrolling.
            scroll.focus()
        event.stop()

    def action_focus_minimap(self) -> None:
        """Tab on Proposal/Plan tab → focus the inline minimap.

        No-op when focus is already inside the minimap, so Tab presses while
        the user is navigating minimap rows do not jump back to row 0.
        """
        from textual.actions import SkipAction
        tabbed = self.query_one(TabbedContent)
        if tabbed.active == "tab_proposal":
            mm_sel = "#proposal_minimap"
        elif tabbed.active == "tab_plan":
            mm_sel = "#plan_minimap"
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

    def action_export(self) -> None:
        """E → open ExportNodeDetailModal for the active node's content."""
        tabbed = self.query_one(TabbedContent)
        active_tab = tabbed.active or ""
        # Pre-check the active tab; user can adjust in the modal. Metadata
        # tab pre-checks both so the user can export either or both without
        # having to flip checkboxes.
        default_proposal = active_tab in ("tab_proposal", "tab_metadata")
        default_plan = active_tab in ("tab_plan", "tab_metadata")
        last_dir = getattr(self.app, "_last_export_dir", None) or str(Path.cwd())
        self.app.push_screen(
            ExportNodeDetailModal(
                node_id=self.node_id,
                task_num=self.app.task_num,
                proposal_text=self._proposal_text,
                plan_text=self._plan_text,
                default_proposal=default_proposal,
                default_plan=default_plan,
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


def _open_node_detail_visible(active_tab: str, focused_is_node_row: bool) -> bool:
    """check_action helper: Enter Open-detail is shown only when the
    Dashboard tab is active AND a NodeRow is currently focused."""
    return active_tab == "tab_dashboard" and focused_is_node_row


def _validate_export_dir(dir_str: str):
    """Resolve and ensure the export directory exists.

    Returns (path, None) on success, (None, error_message) on failure.
    """
    s = (dir_str or "").strip()
    if not s:
        return None, "Output directory is required"
    target = Path(s).expanduser()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, f"Cannot create directory: {exc}"
    if not target.is_dir():
        return None, f"Not a directory: {target}"
    return target, None


def _export_filename(task_num: str, node_id: str, kind: str) -> str:
    """kind is 'proposal' or 'plan'."""
    return f"brainstorm_t{task_num}_{node_id}_{kind}.md"


def _write_node_exports(
    target_dir: Path,
    task_num: str,
    node_id: str,
    proposal_text: str,
    plan_text: str,
    do_proposal: bool,
    do_plan: bool,
) -> list[str]:
    """Write requested files to target_dir. Returns list of written paths.

    Raises OSError on write failure (caller surfaces via notify).
    """
    written: list[str] = []
    if do_proposal:
        p = target_dir / _export_filename(task_num, node_id, "proposal")
        p.write_text(proposal_text, encoding="utf-8")
        written.append(str(p))
    if do_plan:
        p = target_dir / _export_filename(task_num, node_id, "plan")
        p.write_text(plan_text, encoding="utf-8")
        written.append(str(p))
    return written


class ExportNodeDetailModal(ModalScreen):
    """Modal: pick what to export (proposal/plan) and the output directory."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        node_id: str,
        task_num: str,
        proposal_text: str,
        plan_text: str,
        default_proposal: bool,
        default_plan: bool,
        default_dir: str,
    ):
        super().__init__()
        self.node_id = node_id
        self.task_num = task_num
        self._proposal_text = proposal_text
        self._plan_text = plan_text
        self._default_proposal = default_proposal and bool(proposal_text)
        self._default_plan = default_plan and bool(plan_text)
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
            yield Checkbox(
                f"Plan{'' if self._plan_text else ' (empty)'}",
                value=self._default_plan,
                id="export_modal_chk_plan",
                disabled=not self._plan_text,
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
        do_plan = self.query_one("#export_modal_chk_plan", Checkbox).value
        if not (do_proposal or do_plan):
            self.notify("Select at least one of Proposal / Plan", severity="warning")
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
                self._plan_text,
                do_proposal,
                do_plan,
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
        # silent-dismiss crashes, cf. _build_compare_matrix).
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


def _next_checkbox_index(current: int | None, total: int, direction: int) -> int | None:
    """Compute next focus index for arrow navigation in a checkbox list.

    Returns the new index, or None if focus should not move (no checkboxes,
    or already at the boundary). Stops at boundaries (no wrap), consistent
    with `_navigate_rows`.
    """
    if total <= 0:
        return None
    if current is None:
        return 0 if direction == 1 else total - 1
    new_idx = current + direction
    if new_idx < 0 or new_idx >= total:
        return None
    return new_idx


def _filter_labels(query: str, labels: list[str]) -> list[str]:
    """Case-insensitive substring filter for wizard fuzzy-search boxes.

    Blank query keeps everything; otherwise keeps labels containing the
    query as a substring. Order-preserving — matches the substring behaviour
    of the settings `FuzzySelect` picker.
    """
    q = query.strip().lower()
    if not q:
        return list(labels)
    return [lbl for lbl in labels if q in lbl.lower()]


def _nodes_for_subgraph(
    session_path, nodes: list[str], subgraph: str
) -> list[str]:
    """Keep only the nodes belonging to ``subgraph`` (by ``module_label``).

    Order-preserving. Unlabeled / legacy nodes resolve to ``_umbrella`` via
    ``_node_module``, so a single-subgraph session keeps every node. Pure
    (no App state) — unit-tested alongside ``_filter_labels``.
    """
    return [nid for nid in nodes if _node_module(session_path, nid) == subgraph]


# ---------------------------------------------------------------------------
# Wizard step model (pure, App-independent — see tests/test_brainstorm_wizard_steps.py)
#
# The Actions-tab wizard is an ordered table of steps; which steps are *active*
# for a given flow is decided by per-step predicates over a small context dict
# (`{"op": <op>, "node_has_sections": <bool>}`). Back/Next/Esc navigation and
# the "Step X of Y" indicator are derived from the active list, so adding an
# optional step is "add one row + predicate" — no integer renumbering. A future
# module subgraph-selector slots in as one more row (see commented entry).
# ---------------------------------------------------------------------------


class _WizardStep(NamedTuple):
    id: str
    active: Callable[[dict], bool]  # reads ONLY ctx keys; never does I/O
    rows: bool                      # True => renders an OperationRow list (nav target)


_WIZARD_STEPS: list[_WizardStep] = [
    _WizardStep("op_select", lambda c: True, True),
    # Module subgraph-selector (t756_2) — active only for node-select ops in a
    # session with 2+ subgraphs; single-subgraph sessions skip it entirely.
    _WizardStep(
        "subgraph_select",
        lambda c: c.get("op") in _SUBGRAPH_SELECT_OPS
        and c.get("subgraph_count", 1) >= 2,
        True,
    ),
    _WizardStep("node_select", lambda c: c.get("op") in _NODE_SELECT_STEP_OPS, True),
    _WizardStep(
        "section_select",
        lambda c: c.get("op") in _NODE_SELECT_OPS and bool(c.get("node_has_sections")),
        False,
    ),
    _WizardStep(
        "config",
        lambda c: c.get("op") in (
            "explore",
            "patch",
            "compare",
            "synthesize",
            "module_decompose",
            "module_merge",
            "module_sync",
        ),
        False,
    ),
    _WizardStep("confirm", lambda c: c.get("op") not in ("", "delete"), False),
]

_WIZARD_STEPS_BY_ID = {s.id: s for s in _WIZARD_STEPS}


def active_step_ids(ctx: dict) -> list[str]:
    """Ordered ids of the wizard steps active for ``ctx``."""
    return [s.id for s in _WIZARD_STEPS if s.active(ctx)]


def step_position(ctx: dict, step_id: str) -> tuple[int, int]:
    """Return ``(index, total)`` (1-based) of ``step_id`` within the active list.

    ``index`` is 0 when ``step_id`` is not active for ``ctx`` (caller is between
    flows); ``total`` is always the active-step count.
    """
    ids = active_step_ids(ctx)
    total = len(ids)
    index = ids.index(step_id) + 1 if step_id in ids else 0
    return index, total


def next_step_id(ctx: dict, step_id: str) -> str | None:
    """Id of the step after ``step_id`` in the active list, or None if last."""
    ids = active_step_ids(ctx)
    if step_id not in ids:
        return None
    i = ids.index(step_id)
    return ids[i + 1] if i + 1 < len(ids) else None


def prev_step_id(ctx: dict, step_id: str) -> str | None:
    """Id of the step before ``step_id`` in the active list, or None if first."""
    ids = active_step_ids(ctx)
    if step_id not in ids:
        return None
    i = ids.index(step_id)
    return ids[i - 1] if i > 0 else None


class CompareNodeSelectModal(ShortcutsMixin, ModalScreen):
    """Modal for selecting 2-4 nodes to compare in the dimension matrix."""

    _shortcuts_scope = "brainstorm.compare_select"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("c", "confirm", "Compare"),
    ]

    def __init__(self, node_ids: list[str]):
        super().__init__()
        self.node_ids = node_ids

    def compose(self) -> ComposeResult:
        with Container(id="compare_select_dialog"):
            yield Label("Select 2\u20134 nodes to compare", id="compare_select_title")
            yield Label(
                "[dim]\u2191\u2193 Navigate  Space/Enter Toggle  c Compare[/dim]",
                id="compare_select_hint",
            )
            with VerticalScroll(id="compare_checkbox_list"):
                for nid in self.node_ids:
                    yield Checkbox(nid, id=f"chk_cmp_{nid}")
            with Horizontal(id="compare_select_buttons"):
                yield Button(self.label("confirm", "Compare"), variant="primary", id="btn_compare")
                yield Button("Cancel", variant="default", id="btn_compare_cancel")

    def on_mount(self) -> None:
        self._update_compare_button()

    def _get_selected(self) -> list[str]:
        return [
            nid
            for nid in self.node_ids
            if self.query_one(f"#chk_cmp_{nid}", Checkbox).value
        ]

    def _update_compare_button(self) -> None:
        try:
            btn = self.query_one("#btn_compare", Button)
        except Exception:
            return
        count = len(self._get_selected())
        btn.disabled = not (2 <= count <= 4)

    @on(Checkbox.Changed)
    def _on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._update_compare_button()

    def on_key(self, event) -> None:
        if event.key in ("up", "down"):
            direction = 1 if event.key == "down" else -1
            if self._navigate_checkboxes(direction):
                event.prevent_default()
                event.stop()

    def _navigate_checkboxes(self, direction: int) -> bool:
        try:
            container = self.query_one("#compare_checkbox_list", VerticalScroll)
        except Exception:
            return False
        checkboxes = [
            w for w in container.children
            if isinstance(w, Checkbox) and w.can_focus
        ]
        if not checkboxes:
            return False
        focused = self.focused
        current = checkboxes.index(focused) if focused in checkboxes else None
        new_idx = _next_checkbox_index(current, len(checkboxes), direction)
        if new_idx is None:
            return False
        checkboxes[new_idx].focus()
        checkboxes[new_idx].scroll_visible()
        return True

    @on(Button.Pressed, "#btn_compare")
    def _on_compare_pressed(self) -> None:
        self.action_confirm()

    def action_confirm(self) -> None:
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


class FuzzyCheckList(Container):
    """Filter box + scrolling multi-select checkbox list.

    A self-contained wizard control group: an `Input` fuzzy-filter box on top
    and a `VerticalScroll` of native `Checkbox` rows. Rows keep the
    caller-supplied CSS class, so existing `query("Checkbox.<class>")`-based
    collection code finds them unchanged.

    Filtering toggles `display` only. A checked row always stays visible —
    even when it does not match the current filter — so the active selection
    is never hidden; `.value` is preserved regardless. `↑`/`↓` move focus
    within this group (the filter box + visible rows); `Tab` group-switching
    is handled by the parent app.
    """

    def __init__(self, items, *, item_class: str, default_checked: bool = False,
                 placeholder: str = "Type to filter…", id: str | None = None):
        super().__init__(id=id)
        self._items = [str(it) for it in items]
        self._item_class = item_class
        self._default_checked = default_checked
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self._placeholder, classes="fcl_filter")
        with VerticalScroll(classes="fcl_list"):
            for label in self._items:
                yield Checkbox(label, value=self._default_checked,
                               classes=f"{self._item_class} fcl_item")

    def on_input_changed(self, event: Input.Changed) -> None:
        matched = set(_filter_labels(event.value, self._items))
        for cb in self.query(Checkbox):
            # A checked row stays visible even when it does not match the
            # filter, so the current selection is never hidden from view.
            cb.display = str(cb.label) in matched or bool(cb.value)
        focused = self.app.focused
        if isinstance(focused, Checkbox) and not focused.display:
            self.query_one(Input).focus()

    def on_key(self, event) -> None:
        if event.key in ("up", "down"):
            if self._navigate(1 if event.key == "down" else -1):
                event.prevent_default()
                event.stop()

    def _navigate(self, direction: int) -> bool:
        chain = [self.query_one(Input)]
        chain += [cb for cb in self.query(Checkbox) if cb.display]
        focused = self.app.focused
        current = chain.index(focused) if focused in chain else None
        new_idx = _next_checkbox_index(current, len(chain), direction)
        if new_idx is None:
            return True  # boundary: consume, no move
        chain[new_idx].focus()
        chain[new_idx].scroll_visible()
        return True

    def set_grouped_items(self, groups) -> None:
        """Replace rows with grouped, subheadered items.

        ``groups``: list of ``(subheader_text, [(label, checked), ...])``.
        Re-mounts the inner ``.fcl_list`` scroll with a non-focusable ``Static``
        subheader per group followed by its ``Checkbox`` rows, and resyncs
        ``self._items`` so the fuzzy filter stays correct. Safe to call
        repeatedly (e.g. on node-selection change), mirroring
        ``_refresh_compare_sections``'s remount. Subheaders are ``Static`` (not
        ``Checkbox``), so ``_navigate`` skips them and the filter leaves them
        visible.
        """
        try:
            listview = self.query_one(".fcl_list", VerticalScroll)
        except Exception:
            return
        listview.remove_children()
        items: list[str] = []
        for subheader, rows in groups:
            listview.mount(Static(
                f"[bold $accent]{subheader}[/]", classes="fcl_subheader"))
            for label, checked in rows:
                listview.mount(Checkbox(
                    label, value=checked,
                    classes=f"{self._item_class} fcl_item"))
                items.append(label)
        self._items = items


# ---------------------------------------------------------------------------
# Dashboard Widgets
# ---------------------------------------------------------------------------


class NodeRow(Static):
    """Focusable row representing a brainstorm node in the dashboard list."""

    BINDINGS = [
        Binding("o", "open_operation", "Operation", show=True),
    ]

    class OperationOpened(Message):
        """Emitted when 'o' is pressed on a focused NodeRow."""

        def __init__(self, group_name: str) -> None:
            super().__init__()
            self.group_name = group_name

    def __init__(self, node_id: str, description: str, is_head: bool = False,
                 has_plan: bool = False):
        super().__init__()
        self.node_id = node_id
        self.node_description = description
        self.is_head = is_head
        self.has_plan = has_plan
        self.can_focus = True

    def render(self) -> str:
        head_marker = " [bold green]HEAD[/]" if self.is_head else ""
        plan_marker = (
            " [bold green]● has plan[/]" if self.has_plan
            else " [dim]○ no plan[/]"
        )
        return f"[bold]{self.node_id}[/]{head_marker}{plan_marker}  {self.node_description}"

    def action_open_operation(self) -> None:
        """Post OperationOpened for this row's generating group (o key)."""
        session_path = getattr(self.app, "session_path", None)
        if session_path is None:
            return
        data = read_node(session_path, self.node_id)
        group = data.get("created_by_group", "")
        if not group:
            self.app.notify(
                "No group recorded for this node",
                severity="warning",
            )
            return
        # Apply the same defensive resolution used by the graph-tab
        # detail pane so the operation modal can open even when the
        # stored ``created_by_group`` is a pre-t792 drifted value
        # (e.g. ``op_explore_001``).
        groups = _read_groups(session_path)
        resolved_group, _ginfo = resolve_node_group(
            self.node_id, group, groups
        )
        self.post_message(self.OperationOpened(resolved_group))


class DimensionRow(Static):
    """Focusable row showing a stripped dimension suffix + value.

    Mounted by the dashboard right pane under the appropriate dimension-type
    subheader. Pressing Enter posts an :class:`Activated` message carrying the
    full prefixed dimension key (e.g. ``requirements_perf``) so the host can
    look up matching proposal sections via
    :func:`brainstorm.brainstorm_sections.get_sections_for_dimension`.
    """

    can_focus = True

    DEFAULT_CSS = """
    DimensionRow {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    DimensionRow:focus {
        background: $accent;
        color: $text;
    }
    DimensionRow:hover {
        background: $surface-lighten-1;
    }
    """

    class Activated(Message):
        def __init__(self, dim_key: str) -> None:
            super().__init__()
            self.dim_key = dim_key

    def __init__(
        self, suffix: str, value: str, dim_key: str,
        section_count: int = 0, **kwargs,
    ):
        super().__init__(**kwargs)
        self.suffix = suffix
        self.value = value
        self.dim_key = dim_key
        self.section_count = section_count
        # When collapsed (default) the row is clipped to a single line by the
        # ``height: 1`` CSS; ``space`` toggles it to ``height: auto`` so the
        # full (often paragraph-length) value wraps and becomes readable.
        self.expanded = False

    def render(self) -> str:
        if self.section_count == 0:
            badge = "[dim][0 §][/]"
        else:
            badge = f"[bold cyan][{self.section_count} §][/]"
        caret = "[dim]▾[/]" if self.expanded else "[dim]▸[/]"
        return f"  {caret} {badge} [bold]{self.suffix}:[/] {self.value}"

    def on_click(self) -> None:
        self.focus()
        self.post_message(self.Activated(self.dim_key))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Activated(self.dim_key))
            event.stop()
        elif event.key == "space":
            # Toggle full-text expansion in place. The value is always present
            # in render(); only the row height gates how much is visible.
            self.expanded = not self.expanded
            self.styles.height = "auto" if self.expanded else 1
            self.refresh(layout=True)
            event.stop()


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


class NodeActionSelectModal(ModalScreen):
    """Modal to pick an operation for a focused DAG node.

    Surfaced via the `A` keybinding on the Graph and Dashboard tabs. Offers
    every operation that can run from a focused node — the single-node ops
    (explore, detail, patch), the fast-track preset, the module ops
    (module_decompose / module_merge / module_sync, seeded from the node's
    subgraph), and delete. Each op is shown disabled with a reason when it does
    not apply to this node (per the ``op_states`` map passed by the caller).
    Returns the chosen op_key string via dismiss(), or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    # Operation keys offered, in display order. Labels/descriptions are
    # pulled from _OP_LABELS so the picker stays in sync with the wizard.
    # ``fast_track`` (UC-3 preset, t756_6) and ``delete`` are NOT wizard ops in
    # _OP_LABELS — fast_track seeds a single-module module_decompose, delete is
    # handled inline via DeleteNodeModal — so their labels live in _LOCAL_LABELS.
    _OPS = [
        "explore", "detail", "patch", "fast_track",
        "module_decompose", "module_merge", "module_sync", "delete",
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

    def __init__(self, node_id: str, has_plan: bool, op_states: dict | None = None):
        super().__init__()
        self.node_id = node_id
        self.has_plan = has_plan
        # op_states[op_key] = (disabled: bool, reason: str). Computed by the
        # caller (action_node_action) so the modal stays session-free/testable.
        self.op_states = op_states or {}

    def compose(self) -> ComposeResult:
        with Container(id="node_action_dialog"):
            yield Label(
                f"Operate on node [bold]{self.node_id}[/]",
                id="node_action_title",
            )
            yield Label(
                "[dim]↑↓ Navigate  Enter Select  Esc Cancel[/dim]",
                id="node_action_hint",
            )
            with VerticalScroll(id="node_action_list"):
                for op_key in self._OPS:
                    label, desc = self._LOCAL_LABELS.get(
                        op_key, _OP_LABELS.get(op_key, (op_key, ""))
                    )
                    # op_states (computed by the caller) is authoritative; patch
                    # falls back to has_plan when no map was supplied; all other
                    # ops default to enabled.
                    if op_key in self.op_states:
                        disabled, reason = self.op_states[op_key]
                    elif op_key == "patch":
                        disabled, reason = (not self.has_plan, "node has no plan")
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


def _format_progress_bar(progress: int) -> str:
    """Render a 10-block progress bar plus percent label, e.g. ``\u2588\u2588\u2588\u2591\u2591\u2591\u2591\u2591\u2591\u2591 30%``.

    Returns an empty string when ``progress`` is not strictly positive,
    matching the convention used by per-agent rows. Input is clipped to
    [0, 100].
    """
    try:
        p = int(progress)
    except (TypeError, ValueError):
        return ""
    p = max(0, min(100, p))
    if p <= 0:
        return ""
    filled = int(10 * p / 100)
    bar = "\u2588" * filled + "\u2591" * (10 - filled)
    return f"{bar} {p}%"


class GroupRow(Static, can_focus=True):
    """Expandable group row in the Status tab."""

    def __init__(
        self,
        name: str,
        info: dict,
        expanded: bool = False,
        aggregate_progress: int | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.group_name = name
        self.group_info = info
        self.expanded = expanded
        self.aggregate_progress = aggregate_progress

    def render(self) -> str:
        arrow = "\u25bc" if self.expanded else "\u25b6"
        op = self.group_info.get("operation", "?")
        status = self.group_info.get("status", "?")
        color = AGENT_STATUS_COLORS.get(status, "#888888")
        agents = self.group_info.get("agents", [])
        created = self.group_info.get("created_at", "")
        progress_str = ""
        # Hide the bar for already-Completed groups (would always read 100%)
        # and when no agent has progress > 0 yet.
        if status != "Completed" and self.aggregate_progress:
            bar = _format_progress_bar(self.aggregate_progress)
            if bar:
                progress_str = f"  {bar}"
        return (
            f"{arrow} [bold]{self.group_name}[/bold]  {op}  "
            f"[{color}]{status}[/{color}]  agents: {len(agents)}"
            f"{progress_str}  {created}"
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


class CompareDataTable(DataTable):
    """DataTable for the Compare tab.

    When the cursor is at row 0 and Up is pressed, focus returns to the
    tab bar (matching the Dashboard's NodeRow escape behavior). Otherwise
    Up moves the row cursor as normal.
    """

    def action_cursor_up(self) -> None:
        if self.cursor_row == 0:
            try:
                tabbed = self.app.query_one(TabbedContent)
                tabbed.query_one(Tabs).focus()
                return
            except Exception:
                pass
        super().action_cursor_up()


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


class BrainstormApp(TuiSwitcherMixin, ShortcutsMixin, App):
    """Textual app for interactive brainstorm session orchestration."""

    _shortcuts_scope = "brainstorm"

    TITLE = "ait brainstorm"

    CSS = """
    Screen {
        align: center middle;
    }

    #initializer_row {
        height: 1;
    }

    .initializer-banner {
        width: 1fr;
        height: 1;
        padding: 0 1;
        background: transparent;
        color: $text;
    }

    .initializer-banner.visible {
        background: $error;
    }

    .status-header {
        height: 1;
        padding: 0 1;
    }

    .status_pane_title {
        width: 1fr;
        text-style: bold;
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
    FuzzyCheckList {
        height: auto;
        margin-bottom: 1;
    }

    FuzzyCheckList .fcl_filter {
        margin: 0 1;
    }

    FuzzyCheckList .fcl_list {
        height: auto;
        max-height: 10;
        padding: 0 1;
    }

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

    #compare_select_hint {
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

    /* Node action selection modal */
    #node_action_dialog {
        width: 64;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #node_action_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #node_action_hint {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #node_action_list {
        height: auto;
        max-height: 24;
        padding: 0 1;
    }

    /* Picker rows wrap (height: auto overrides the global single-line
       OperationRow) so long descriptions and the disabled-op "(reason)"
       suffix are fully visible instead of truncating. */
    #node_action_list OperationRow {
        height: auto;
    }

    #node_action_buttons {
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

    /* Config-step side-by-side preview (t945): input left, proposal right.
       The ratio-cycle action (ctrl+shift+b) toggles three width splits by adding a
       ratio_* class to BOTH panes; compound selectors give each its width. */
    .config_preview_split {
        height: 1fr;
    }

    .config_preview_left {
        width: 50%;
        height: 1fr;
        padding: 0 1;
    }

    .config_preview_pane {
        width: 50%;
    }

    .config_preview_left.ratio_input_wide { width: 70%; }
    .config_preview_pane.ratio_input_wide { width: 30%; }
    .config_preview_left.ratio_proposal_wide { width: 30%; }
    .config_preview_pane.ratio_proposal_wide { width: 70%; }

    #session_status_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #session_status_info {
        color: $text-muted;
        margin-bottom: 2;
    }

    #module_status_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #module_status_info {
        height: auto;
        margin-bottom: 2;
    }

    #dash_node_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #dash_node_info {
        height: auto;
        padding: 0;
    }

    /* Graph tab split pane */
    #dag_split {
        height: 1fr;
    }

    #dag_content {
        width: 60%;
    }

    #dag_detail_pane {
        width: 40%;
        padding: 0 1;
    }

    #dag_node_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #dag_node_info {
        height: auto;
        padding: 0;
    }

    .meta_field {
        padding: 0;
    }

    .dim_subheader {
        padding: 0 1;
        margin-top: 1;
    }

    .fcl_subheader {
        padding: 0 1;
        margin-top: 1;
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

    /* Operation detail modal (t749_5) */
    #op_detail_dialog {
        width: 80%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #op_detail_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #op_detail_content {
        height: 1fr;
    }

    #op_detail_loading {
        height: 1fr;
        width: 100%;
    }

    #op_detail_tabs {
        height: 1fr;
    }

    .op_tab_scroll {
        height: 1fr;
        padding: 1 2;
    }

    #op_detail_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    #op_detail_missing {
        padding: 2;
        text-align: center;
        color: $text-muted;
    }

    .op_agent_log {
        padding: 1;
    }

    /* Export node-detail modal */
    #export_modal_dialog {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #export_modal_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }

    #export_modal_buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
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

    /* Operation help modal */
    #op_help_dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #op_help_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #op_help_scroll {
        height: 1fr;
        padding: 0 1;
    }

    #op_help_footer {
        dock: bottom;
        width: 100%;
        text-align: center;
        padding: 0 1;
    }

    .runner_bar { height: auto; padding: 0 1; margin-bottom: 1; }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("q", "quit", "Quit"),
        Binding("d", "tab_dashboard", "Dashboard", show=False),
        Binding("g", "tab_graph", "Graph", show=False),
        Binding("c", "tab_compare", "Compare", show=False),
        Binding("a", "tab_actions", "Actions", show=False),
        Binding("s", "tab_status", "Status", show=False),
        Binding("enter", "open_node_detail", "Open detail"),
        Binding("r", "compare_regenerate", "Regenerate"),
        Binding("D", "compare_diff", "Diff"),
        Binding("A", "node_action", "Node action"),
        Binding("f", "toggle_deferred", "Defer module"),
        Binding("H", "op_help", "Op help"),
        Binding("ctrl+shift+b", "cycle_preview_ratio", "Preview width"),
        Binding("ctrl+r", "retry_initializer_apply", "Retry initializer apply"),
        Binding("ctrl+shift+r", "retry_patcher_apply",
                "Retry patcher apply", show=False),
        Binding("ctrl+shift+x", "retry_explorer_apply",
                "Retry explorer apply", show=False),
        Binding("ctrl+shift+y", "retry_synthesizer_apply",
                "Retry synthesizer apply", show=False),
        Binding("ctrl+shift+d", "retry_detailer_apply",
                "Retry detailer apply", show=False),
    ]

    # Maps action_name -> required tab id. check_action() hides the binding
    # from the footer when the active tab does not match.
    _TAB_SCOPED_ACTIONS: dict[str, str] = {
        "compare_regenerate": "tab_compare",
        "compare_diff": "tab_compare",
        "open_node_detail": "tab_dashboard",
    }

    def __init__(self, task_num: str):
        super().__init__()
        self.current_tui_name = f"brainstorm-{task_num}"
        self.task_num = task_num
        self.session_path = crew_worktree(task_num)
        self.session_data: dict = {}
        self.read_only: bool = False
        # _wizard_step / _wizard_total_steps are DERIVED ints (from step_position)
        # kept for the "Step X of Y" label and the "wizard active" sentinel guards
        # (_wizard_step > 0). _wizard_step_id is the source of truth for dispatch.
        self._wizard_step: int = 0
        self._wizard_total_steps: int = 3
        self._wizard_step_id: str = ""
        self._wizard_op: str = ""
        self._wizard_config: dict = {}
        self._wizard_has_sections: bool = False
        # Cached subgraph count for the I/O-free _wizard_ctx (set when op-select
        # renders); gates the optional subgraph-selector step (>= 2 subgraphs).
        self._wizard_subgraph_count: int = 1
        # The subgraph chosen in the selector (or _umbrella default). Held in a
        # dedicated field, NOT _wizard_config, because node-select resets that
        # dict after the selector runs.
        self._wizard_subgraph: str = UMBRELLA_SUBGRAPH
        # Transient "Fast-track this module" preset flag (UC-3, t756_6). When
        # set, the module_decompose config step pre-arms link-to-task. Reset by
        # _set_total_steps (the op-select funnel) so it never leaks across ops.
        self._wizard_fast_track: bool = False
        self._cmp_section_checks: dict[str, bool] = {}
        self._expanded_groups: set[str] = set()
        self._status_refresh_timer = None
        self._processes_synced: bool = False
        self._initializer_agent: str | None = None
        self._initializer_done: bool = False
        self._initializer_timer = None
        self._initializer_apply_error: str | None = None
        self._applying_initializer: bool = False
        # Patcher auto-apply state. Maps agent_name -> source_node_id for
        # patchers we should poll until applied. Populated at register
        # time and refreshed at session-load by parsing existing
        # patcher_*_input.md files.
        self._patcher_sources: dict[str, str] = {}
        self._applying_patcher: set[str] = set()
        self._patcher_apply_errors: dict[str, str] = {}
        self._patcher_poll_timer = None
        # Explorer auto-apply state. Tracked agent names produce a single
        # node each via apply_explorer_output; the poll timer fires until
        # every tracked agent has either applied or been dropped.
        self._explorer_agents: set[str] = set()
        self._applying_explorer: set[str] = set()
        self._explorer_apply_errors: dict[str, str] = {}
        self._explorer_poll_timer = None
        # Synthesizer auto-apply state. Tracked agent names produce a
        # single synthesized node each via apply_synthesizer_output; the poll
        # timer fires until every tracked agent has either applied or
        # been dropped.
        self._synthesizer_agents: set[str] = set()
        self._applying_synthesizer: set[str] = set()
        self._synthesizer_apply_errors: dict[str, str] = {}
        self._synthesizer_poll_timer = None
        # Detailer auto-apply state. Maps agent_name -> target_node_id for
        # detailers we should poll until applied. The detailer enriches an
        # existing node (writes its plan, sets plan_file) rather than creating
        # a node — so this mirrors the patcher's keyed-on-a-node pattern.
        self._detailer_targets: dict[str, str] = {}
        self._applying_detailer: set[str] = set()
        self._detailer_apply_errors: dict[str, str] = {}
        self._detailer_poll_timer = None
        self._module_agents: set[str] = set()
        self._applying_module_agent: set[str] = set()
        self._module_apply_errors: dict[str, str] = {}
        self._module_poll_timer = None
        # Review gate (t929_1): decomposer agents whose proposal is awaiting the
        # operator's preview decision, and those already accepted (so the poller
        # applies them on the next tick without re-prompting). ``_module_steer``
        # carries the ordered Re-run revision notes forward, keyed by group name.
        self._module_review_pending: set[str] = set()
        self._module_review_accepted: set[str] = set()
        self._module_steer: dict[str, list[str]] = {}
        self._current_focused_node_id: str | None = None
        # Remembered for the lifetime of the app; pre-fills the export modal's
        # directory input so repeated exports default to the previous choice.
        self._last_export_dir: str | None = None
        self._update_title_from_task()

    def check_action(self, action: str, parameters) -> bool | None:
        # Hide app-level bindings from the footer when a non-modal screen
        # (e.g., pushed DiffViewerScreen) is active — the screen owns the
        # footer. Returning None hides the binding from the footer but
        # keeps it live, so app shortcuts like `q` still work.
        if (
            len(self.screen_stack) > 1
            and not isinstance(self.screen, ModalScreen)
        ):
            return None
        if action == "op_help":
            try:
                tabbed = self.query_one(TabbedContent)
            except Exception:
                return None
            if tabbed.active != "tab_actions" or self._wizard_step < 1:
                return None
            return True
        if action in ("node_action", "toggle_deferred"):
            try:
                tabbed = self.query_one(TabbedContent)
            except Exception:
                return None
            if tabbed.active not in ("tab_dashboard", "tab_dag"):
                return None
            if not self._current_focused_node_id:
                return None
            return True
        if action == "cycle_preview_ratio":
            try:
                tabbed = self.query_one(TabbedContent)
            except Exception:
                return None
            if tabbed.active != "tab_actions" or not self.query(
                ProposalPreviewPane
            ):
                return None
            return True
        required_tab = self._TAB_SCOPED_ACTIONS.get(action)
        if required_tab is None:
            return True
        try:
            tabbed = self.query_one(TabbedContent)
        except Exception:
            return None
        if tabbed.active != required_tab:
            return None
        if action == "open_node_detail":
            if not _open_node_detail_visible(
                tabbed.active or "", isinstance(self.focused, NodeRow)
            ):
                return None
        return True

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
        with Horizontal(id="initializer_row", classes="initializer-row"):
            yield Static("", id="initializer_apply_banner", classes="initializer-banner")
            yield PollingIndicator(id="initializer_polling_indicator")
        yield Static(
            "", id="patcher_impact_banner", classes="initializer-banner"
        )
        with TabbedContent(id="brainstorm_tabs"):
            with TabPane("(D)ashboard", id="tab_dashboard"):
                with Horizontal(id="dashboard_split"):
                    yield VerticalScroll(id="node_list_pane")
                    yield VerticalScroll(
                        Label("Session Status", id="session_status_title"),
                        Label("Loading...", id="session_status_info"),
                        Label("Modules", id="module_status_title"),
                        Label("", id="module_status_info"),
                        Label("", id="dash_node_title"),
                        Container(id="dash_node_info"),
                        id="detail_pane",
                    )
            with TabPane("(G)raph", id="tab_dag"):
                with Horizontal(id="dag_split"):
                    yield DAGDisplay(id="dag_content")
                    yield VerticalScroll(
                        Label("", id="dag_node_title"),
                        Container(id="dag_node_info"),
                        id="dag_detail_pane",
                    )
            with TabPane("(C)ompare", id="tab_compare"):
                yield VerticalScroll(
                    Label(
                        "Press 'r' to (re)select nodes, 'D' to open full diff",
                        id="compare_hint",
                    ),
                    id="compare_content",
                )
            with TabPane("(A)ctions", id="tab_actions"):
                yield VerticalScroll(id="actions_content")
            with TabPane("(S)tatus", id="tab_status"):
                with Horizontal(id="status_header", classes="status-header"):
                    yield Label("Status", classes="status_pane_title")
                    yield PollingIndicator(id="status_polling_indicator")
                yield VerticalScroll(id="status_content")
        yield Footer()

    def on_key(self, event) -> None:
        """Handle Enter on NodeRow, compare keys, wizard nav, and arrow navigation."""
        if isinstance(self.screen, ModalScreen):
            return
        tabbed = self.query_one(TabbedContent)

        # Tab / Shift+Tab on the Actions tab → cycle the side-by-side preview
        # focus ring (t945): inputs → minimap → proposal markdown → wrap. No-op
        # (falls through to default Tab) when no preview pane is mounted.
        if event.key in ("tab", "shift+tab") and tabbed.active == "tab_actions":
            if self._cycle_preview_focus(forward=event.key == "tab"):
                event.prevent_default()
                event.stop()
                return

        # Down from tab bar: focus first row in active tab
        if event.key == "down":
            tabs_widget = tabbed.query_one(Tabs)
            if self.focused is tabs_widget:
                # Compare tab: single DataTable, focus it directly so its
                # built-in up/down cursor bindings drive section navigation.
                if tabbed.active == "tab_compare":
                    try:
                        table = self.query_one("#compare_table", DataTable)
                    except Exception:
                        table = None
                    if table is not None:
                        table.focus()
                        event.prevent_default()
                        event.stop()
                        return
                # Graph tab: focus the DAGDisplay directly. It manages its
                # own layer/column navigation via internal bindings.
                if tabbed.active == "tab_dag":
                    try:
                        dag = self.query_one(DAGDisplay)
                    except Exception:
                        dag = None
                    if dag is not None:
                        dag.focus()
                        event.prevent_default()
                        event.stop()
                        return
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

        # Up/down: navigate NodeRow items in Dashboard, or DimensionRow items
        # in the detail pane once focus has moved into it.
        if event.key in ("up", "down") and tabbed.active == "tab_dashboard":
            direction = 1 if event.key == "down" else -1
            if isinstance(self.focused, DimensionRow):
                if self._navigate_rows(direction, "dash_node_info", (DimensionRow,)):
                    event.prevent_default()
                    event.stop()
                    return
            elif self._navigate_rows(direction, "node_list_pane", (NodeRow,)):
                event.prevent_default()
                event.stop()
                return

        # Up/down on Graph tab when a DimensionRow in the right pane is
        # focused: navigate among DimensionRow widgets in #dag_node_info.
        # When DAGDisplay itself is focused, its own up/down bindings handle
        # layer navigation (so we don't intercept here).
        if (
            event.key in ("up", "down")
            and tabbed.active == "tab_dag"
            and isinstance(self.focused, DimensionRow)
        ):
            direction = 1 if event.key == "down" else -1
            if self._navigate_rows(direction, "dag_node_info", (DimensionRow,)):
                event.prevent_default()
                event.stop()
                return

        # Tab / Shift+Tab on Dashboard: toggle focus between the node list (left)
        # and the dimension list (right). Only fires when there is at least one
        # DimensionRow in the detail pane (i.e., a node with dimensions is
        # currently displayed).
        if event.key in ("tab", "shift+tab") and tabbed.active == "tab_dashboard":
            if self._dashboard_toggle_pane_focus():
                event.prevent_default()
                event.stop()
                return

        # Tab / Shift+Tab on Graph: toggle focus between DAGDisplay (left)
        # and the detail pane DimensionRows (right). Only fires when there
        # is at least one DimensionRow in #dag_node_info, mirroring the
        # Dashboard behavior.
        if event.key in ("tab", "shift+tab") and tabbed.active == "tab_dag":
            if self._graph_toggle_pane_focus():
                event.prevent_default()
                event.stop()
                return

        # Actions tab wizard navigation
        if tabbed.active == "tab_actions" and self._wizard_step > 0:
            # Esc: go back to the previous active wizard step (resolver-driven)
            if event.key == "escape" and self._wizard_step > 1:
                prev = prev_step_id(self._wizard_ctx(), self._wizard_step_id)
                if prev is not None:
                    self._render_wizard_step(prev)
                event.prevent_default()
                event.stop()
                return
            # Enter on op-select: choose operation
            if event.key == "enter" and self._wizard_step_id == "op_select":
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
            # Enter on subgraph-select: choose subgraph and advance
            if event.key == "enter" and self._wizard_step_id == "subgraph_select":
                focused = self.focused
                if isinstance(focused, OperationRow) and not focused.op_disabled:
                    self._wizard_subgraph = focused.op_key
                    nxt = next_step_id(self._wizard_ctx(), "subgraph_select")
                    if nxt is not None:
                        self._render_wizard_step(nxt)
                    event.prevent_default()
                    event.stop()
                    return
            # Enter on node-select: select node and advance
            if event.key == "enter" and self._wizard_step_id == "node_select":
                focused = self.focused
                if isinstance(focused, OperationRow) and not focused.op_disabled:
                    if self._wizard_op in _NODE_SELECT_STEP_OPS:
                        self._wizard_config["_selected_node"] = focused.op_key
                        self._actions_advance_from_node_select(focused.op_key)
                        event.prevent_default()
                        event.stop()
                        return
            # Compare/Synthesize config step: Tab cycles whole control groups
            if (
                event.key in ("tab", "shift+tab")
                and self._wizard_step_id == "config"
                and self._wizard_op in ("compare", "synthesize")
            ):
                if self._cycle_wizard_groups(-1 if event.key == "shift+tab" else 1):
                    event.prevent_default()
                    event.stop()
                    return
            # Compare config step: up/down within the section-checkbox group
            if (
                event.key in ("up", "down")
                and self._wizard_step_id == "config"
                and self._wizard_op == "compare"
                and isinstance(self.focused, Checkbox)
                and "chk_section" in self.focused.classes
            ):
                if self._navigate_rows(
                    1 if event.key == "down" else -1,
                    "cmp_sections_box", (Checkbox,),
                ):
                    event.prevent_default()
                    event.stop()
                    return
            # Up/down: navigate OperationRow widgets in the row-select steps
            if event.key in ("up", "down") and self._wizard_step_id in (
                "op_select", "subgraph_select", "node_select",
            ):
                direction = 1 if event.key == "down" else -1
                if self._navigate_rows(direction, "actions_content", (OperationRow,)):
                    event.prevent_default()
                    event.stop()
                    return
            # Up/down: cycle focus among focusable widgets on the confirm step
            if event.key in ("up", "down") and self._wizard_step_id == "confirm":
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
            # NodeRow Enter is handled by action_open_node_detail (binding) so
            # the footer hint is surfaced. Falls through here when focus is
            # something else.

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

    def action_open_node_detail(self) -> None:
        """Enter on a focused NodeRow → open NodeDetailModal.

        Falls through (SkipAction) when focus is anything else, so the
        existing on_key handlers for GroupRow/StatusLogRow keep working.
        """
        from textual.actions import SkipAction
        if isinstance(self.screen, ModalScreen):
            raise SkipAction()
        focused = self.focused
        if isinstance(focused, NodeRow):
            self.push_screen(NodeDetailModal(focused.node_id, self.session_path))
            return
        raise SkipAction()

    def action_tab_dashboard(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.query_one(TabbedContent).active = "tab_dashboard"

    def action_tab_graph(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.query_one(TabbedContent).active = "tab_dag"

    def _node_action_op_states(self, node_id: str) -> dict:
        """Compute the disabled/reason map for the node-action picker.

        Returns ``{op_key: (disabled, reason)}`` for the relevance-filtered ops
        offered by ``NodeActionSelectModal``. Module ops are seeded from the
        node's subgraph (like the fast_track preset), so they are disabled on
        the ``_umbrella`` root and when their per-op precondition is unmet
        (merge needs an ancestor subgraph; sync needs a linked task). Ops not
        in the map default to enabled in the modal.
        """
        module = _node_module(self.session_path, node_id)
        is_umbrella = module == UMBRELLA_SUBGRAPH
        gs = _read_graph_state(self.session_path)
        tasks = gs.get("module_tasks")
        has_linked_task = bool(isinstance(tasks, dict) and tasks.get(module))
        # _ancestor_subgraphs takes a subgraph NAME (matches _config_module_merge,
        # which passes self._wizard_subgraph). The _umbrella root has none.
        ancestors = [] if is_umbrella else self._ancestor_subgraphs(module)
        return {
            "patch": (not self._node_has_plan(node_id), "node has no plan"),
            "module_decompose": (is_umbrella, "no module on the root design"),
            "module_merge": (
                is_umbrella or not ancestors,
                "no module on the root design" if is_umbrella
                else "no ancestor subgraph",
            ),
            "module_sync": (
                is_umbrella or not has_linked_task,
                "no module on the root design" if is_umbrella
                else "module has no linked task",
            ),
        }

    def action_node_action(self) -> None:
        """Open the node-action operation picker for the focused node.

        Bound to `A` on the Dashboard and Graph tabs. On pick, the dismiss
        callback seeds the operation wizard and switches to the Actions tab
        (or, for delete, opens the cascade-delete confirmation modal).
        """
        if isinstance(self.screen, ModalScreen):
            return
        tabbed = self.query_one(TabbedContent)
        if tabbed.active not in ("tab_dashboard", "tab_dag"):
            return
        node_id = self._current_focused_node_id
        if not node_id:
            self.notify("Focus a node first", severity="warning")
            return
        if self.read_only:
            self.notify(
                "Session is read-only — no operations available.",
                severity="warning",
            )
            return
        status = self.session_data.get("status", "")
        if status not in ("init", "active"):
            self.notify(
                f"Design operations are unavailable while the session is "
                f"'{status or 'unknown'}'.",
                severity="warning",
            )
            return
        if node_id not in list_nodes(self.session_path):
            # Node was deleted between focus and keypress.
            self._current_focused_node_id = None
            self.notify(
                f"Node '{node_id}' no longer exists.", severity="error"
            )
            return
        has_plan = self._node_has_plan(node_id)
        op_states = self._node_action_op_states(node_id)
        self.push_screen(
            NodeActionSelectModal(node_id, has_plan, op_states),
            lambda result, nid=node_id: self._on_node_action_result(
                nid, result
            ),
        )

    def action_toggle_deferred(self) -> None:
        """Toggle the focused node's module ``deferred`` marker (§4.7, t756_5).

        Bound to `f` on the Dashboard / Graph tabs. The target module is the
        subgraph of the currently-focused node; the `_umbrella` root has no
        module to defer. Persists ``module_deferred[module]`` so the marker
        survives a TUI reload, then refreshes the status view. ``deferred`` is
        orthogonal to the computed base status (a module can be both).
        """
        if isinstance(self.screen, ModalScreen):
            return
        tabbed = self.query_one(TabbedContent)
        if tabbed.active not in ("tab_dashboard", "tab_dag"):
            return
        node_id = self._current_focused_node_id
        if not node_id:
            self.notify("Focus a node first", severity="warning")
            return
        if self.read_only:
            self.notify(
                "Session is read-only — cannot change deferral.",
                severity="warning",
            )
            return
        module = _node_module(self.session_path, node_id)
        if module == UMBRELLA_SUBGRAPH:
            self.notify(
                "The root design has no module to defer.", severity="warning"
            )
            return
        current = bool(_module_deferred_map(self.session_path).get(module, False))
        _write_module_deferred(self.session_path, module, not current)
        self.notify(
            f"Module '{module}' marked {'deferred' if not current else 'active'}."
        )
        self._update_module_status()

    def _on_node_action_result(self, node_id: str, op_key) -> None:
        """Callback from NodeActionSelectModal: enter the Actions wizard.

        `op_key` is the chosen operation string, or None if cancelled. On
        cancel nothing happens — no tab was switched, so the user stays on
        the originating Graph/Dashboard tab.
        """
        if not op_key:
            return
        # The DAG can mutate (background poll timers) while the modal is open.
        if node_id not in list_nodes(self.session_path):
            self.notify(
                f"Node '{node_id}' no longer exists.", severity="error"
            )
            return
        if op_key == "fast_track":
            # UC-3 preset (t756_6): seed a single-module module_decompose with
            # link-to-task pre-armed, sourced from the focused node's subgraph.
            # This reuses the module_decompose config/confirm/execute path
            # verbatim — it is NOT a new op. module_decompose has no node-select
            # step and the subgraph is already known, so we render config
            # directly. _set_total_steps clears _wizard_fast_track, so re-arm
            # the flag after calling it.
            self._wizard_op = "module_decompose"
            self._set_total_steps()
            self._wizard_fast_track = True
            self._wizard_subgraph = _node_module(self.session_path, node_id)
            self._wizard_config = {}
            self._actions_show_config()
            self.call_after_refresh(self._enter_actions_tab)
            return
        if op_key == "delete":
            # Cascade-delete this node and its descendants. Handled inline via a
            # dedicated confirmation modal (like the session-level delete op) —
            # synchronous, no agent dispatch, no wizard tab switch.
            self._open_delete_node_modal(node_id)
            return
        if op_key in ("module_decompose", "module_merge", "module_sync"):
            # Seed the module op from the focused node's subgraph, mirroring the
            # fast_track preset but WITHOUT arming _wizard_fast_track. Module ops
            # have no node-select step, so render config directly. Set
            # _wizard_subgraph after _set_total_steps (which resets it).
            self._wizard_op = op_key
            self._set_total_steps()
            self._wizard_subgraph = _node_module(self.session_path, node_id)
            self._wizard_config = {}
            self._actions_show_config()
            self.call_after_refresh(self._enter_actions_tab)
            return
        # Seed wizard state as if Step 1 (operation select) had completed.
        self._wizard_op = op_key
        self._set_total_steps()
        # Render Step 2 (node select) so #actions_content is in a consistent
        # state, then seed the selected node — _actions_show_node_select
        # clears _wizard_config, so the seed must happen after it.
        self._actions_show_node_select()
        self._wizard_config["_selected_node"] = node_id
        try:
            container = self.query_one("#actions_content", VerticalScroll)
            for row in container.query(OperationRow):
                row.selected = (row.op_key == node_id)
            self.query_one(".btn_actions_next", Button).disabled = False
        except Exception:
            pass
        # Advance past node-select into the config / section / confirm step.
        self._actions_advance_from_node_select(node_id)
        # Switch to the Actions tab only once the picker modal has fully
        # closed. `Screen.dismiss` runs this callback *before* `pop_screen`,
        # and the pop's `ScreenResume` restores focus to the source widget
        # (DAGDisplay / NodeRow) — switching synchronously here would be
        # reverted by that restore. The deferred handler runs after the pop
        # has settled; it focuses a widget inside #actions_content, so
        # TabbedContent reveals the Actions tab and (being the last focus
        # change) it sticks.
        self.call_after_refresh(self._enter_actions_tab)

    def _delete_agent_casualties(self, closure: set) -> list:
        """Return running/waiting agents operating on an affected node.

        Reads the crew worktree's ``_status.yaml`` files; for each agent whose
        status is Running or Waiting, recovers its source/target node from
        ``<agent>_input.md`` (``_recover_node_id_from_input``) and flags it when
        that node is in ``closure``. Agents whose node cannot be recovered
        (compare / synthesize / module ops operate at subgraph/HEAD scope, not a
        single node) are treated as non-blocking. Returns a list of
        ``(node_id, agent_name, status)`` tuples.
        """
        casualties = []
        try:
            status_files = list_agent_files(str(self.session_path), "_status.yaml")
        except Exception:
            return casualties
        for sf in status_files:
            try:
                data = read_yaml(sf)
            except Exception:
                continue
            status = data.get("status", "")
            name = data.get("agent_name", "")
            if status not in ("Running", "Waiting") or not name:
                continue
            node = self._recover_node_id_from_input(name)
            if node and node in closure:
                casualties.append((node, name, status))
        return casualties

    def _open_delete_node_modal(self, node_id: str) -> None:
        """Build and push the cascade-delete confirmation modal for ``node_id``.

        Computes the deletion closure, the affected linked-task modules (warn),
        and the blocking running-agent casualties, then pushes DeleteNodeModal.
        """
        closure_list = node_descendants_closure(self.session_path, node_id)
        closure = set(closure_list)
        # Affected modules with a linked aitask — warn-only.
        gs = _read_graph_state(self.session_path)
        tasks = gs.get("module_tasks")
        tasks = tasks if isinstance(tasks, dict) else {}
        affected_modules = {
            _node_module(self.session_path, nid) for nid in closure_list
        }
        linked_modules = [
            (m, tasks[m]) for m in sorted(affected_modules) if tasks.get(m)
        ]
        casualties = self._delete_agent_casualties(closure)
        self.push_screen(
            DeleteNodeModal(node_id, closure_list, linked_modules, casualties),
            lambda confirmed, nid=node_id: self._on_delete_node_result(
                nid, confirmed
            ),
        )

    def _on_delete_node_result(self, node_id: str, confirmed) -> None:
        """Callback from DeleteNodeModal: run the cascade delete on confirm."""
        if not confirmed:
            return
        # Re-check the node still exists and the agent guard still holds — the
        # DAG / agents may have changed while the modal was open.
        if node_id not in list_nodes(self.session_path):
            self.notify(
                f"Node '{node_id}' no longer exists.", severity="error"
            )
            return
        closure = set(node_descendants_closure(self.session_path, node_id))
        if self._delete_agent_casualties(closure):
            self.notify(
                "Delete blocked — a running agent now operates on an affected "
                "node.",
                severity="error",
            )
            return
        report = delete_node_cascade(self.session_path, node_id)
        if report.get("missing_root"):
            self.notify(
                f"Node '{node_id}' no longer exists.", severity="error"
            )
            return
        deleted = report.get("deleted", [])
        if self._current_focused_node_id in deleted:
            self._current_focused_node_id = None
        self.notify(f"Deleted {len(deleted)} node(s).")
        self._load_existing_session()

    def _enter_actions_tab(self) -> None:
        """Activate the Actions tab and focus its wizard content.

        Deferred entry point for the node-action picker — see
        `_on_node_action_result`. Focusing a widget inside #actions_content
        makes TabbedContent reveal the Actions tab; the explicit `active`
        assignment covers the case where no content widget is focusable.
        """
        try:
            tabbed = self.query_one(TabbedContent)
            container = self.query_one("#actions_content", VerticalScroll)
        except Exception:
            return
        tabbed.active = "tab_actions"
        for w in container.query("*"):
            if getattr(w, "can_focus", False) and w.display:
                w.focus()
                return

    def _open_compare_select_modal(self) -> None:
        nodes = list_nodes(self.session_path)
        if len(nodes) < 2:
            self.notify("Need at least 2 nodes to compare", severity="warning")
            return
        self.push_screen(
            CompareNodeSelectModal(nodes),
            callback=self._on_compare_selected,
        )

    def action_tab_compare(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        tabbed = self.query_one(TabbedContent)
        if tabbed.active == "tab_compare":
            self._open_compare_select_modal()
            return
        tabbed.active = "tab_compare"

    def action_compare_regenerate(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self._open_compare_select_modal()

    def action_compare_diff(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        nodes = getattr(self, "_compare_nodes", None)
        if not nodes or len(nodes) < 2:
            self.notify(
                "Pick nodes to compare first (press 'r')",
                severity="warning",
            )
            return
        n1, n2 = nodes[:2]
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
        self.push_screen(
            DiffViewerScreen(str(p1), [str(p2)], mode="classical")
        )

    def action_tab_actions(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.query_one(TabbedContent).active = "tab_actions"

    def action_tab_status(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.query_one(TabbedContent).active = "tab_status"

    def action_op_help(self) -> None:
        from textual.actions import SkipAction
        if isinstance(self.screen, ModalScreen):
            raise SkipAction
        try:
            tabbed = self.query_one(TabbedContent)
        except Exception:
            raise SkipAction
        if tabbed.active != "tab_actions" or self._wizard_step < 1:
            raise SkipAction
        if self._wizard_step_id == "op_select":
            focused = self.focused
            if not isinstance(focused, OperationRow):
                raise SkipAction
            op_key = focused.op_key
        else:
            op_key = self._wizard_op
        if not op_key or op_key not in _OPERATION_HELP:
            raise SkipAction
        self.push_screen(OperationHelpModal(op_key))

    # ------------------------------------------------------------------
    # Keyboard navigation helper
    # ------------------------------------------------------------------

    def _dashboard_toggle_pane_focus(self) -> bool:
        """Tab toggle between the Dashboard's node list and dimension list.

        Returns True if focus was moved (caller should stop the event).
        Returns False (so default Tab traversal still applies) when the
        target pane has no focusable rows — e.g. dimension list is empty.
        """
        focused = self.focused
        # Right → left: dimension row → corresponding (or first) node row.
        if isinstance(focused, DimensionRow):
            try:
                list_pane = self.query_one("#node_list_pane", VerticalScroll)
            except Exception:
                return False
            node_rows = [
                w for w in list_pane.children
                if isinstance(w, NodeRow) and w.can_focus
            ]
            if not node_rows:
                return False
            target = node_rows[0]
            if self._current_focused_node_id:
                for r in node_rows:
                    if r.node_id == self._current_focused_node_id:
                        target = r
                        break
            target.focus()
            target.scroll_visible()
            return True
        # Left → right: node row → first dimension row (only if any exist).
        if isinstance(focused, NodeRow):
            try:
                container = self.query_one("#dash_node_info")
            except Exception:
                return False
            dim_rows = [
                w for w in container.children
                if isinstance(w, DimensionRow) and w.can_focus
            ]
            if not dim_rows:
                return False
            dim_rows[0].focus()
            dim_rows[0].scroll_visible()
            return True
        return False

    def _graph_toggle_pane_focus(self) -> bool:
        """Tab toggle between the Graph tab's DAG (left) and detail pane (right).

        Mirrors `_dashboard_toggle_pane_focus`: returns True if focus was
        moved (caller should stop the event), False otherwise so default
        Tab traversal still applies.
        """
        focused = self.focused
        try:
            dag = self.query_one(DAGDisplay)
        except Exception:
            return False
        # Right → left: dimension row → DAGDisplay.
        if isinstance(focused, DimensionRow):
            dag.focus()
            return True
        # Left → right: DAGDisplay → first dimension row (only if any exist).
        if focused is dag:
            try:
                container = self.query_one("#dag_node_info")
            except Exception:
                return False
            dim_rows = [
                w for w in container.children
                if isinstance(w, DimensionRow) and w.can_focus
            ]
            if not dim_rows:
                return False
            dim_rows[0].focus()
            dim_rows[0].scroll_visible()
            return True
        return False

    def _navigate_rows(self, direction: int, container_id: str, row_types: tuple) -> bool:
        """Navigate up/down among focusable rows in a container.

        Returns True if the event was handled.
        direction: -1 for up, +1 for down.
        """
        try:
            container = self.query_one(f"#{container_id}")
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

    def _focus_within(self, container) -> bool:
        """True if the currently focused widget is `container` or a descendant."""
        node = self.focused
        while node is not None:
            if node is container:
                return True
            node = node.parent
        return False

    def _cycle_wizard_groups(self, direction: int) -> bool:
        """Tab/Shift+Tab cycle focus between whole control groups on the
        Compare/Synthesize config step.

        Each group exposes one "entry widget" (the filter box of a
        FuzzyCheckList, the first section checkbox, the merge-rules TextArea,
        or the Next button) plus a "membership" widget used to detect which
        group currently holds focus. Returns True if handled.
        """
        try:
            container = self.query_one("#actions_content", VerticalScroll)
        except Exception:
            return False

        def _fcl_group(fcl_id):
            try:
                fcl = container.query_one(f"#{fcl_id}", FuzzyCheckList)
                return (fcl.query_one(Input), fcl)
            except Exception:
                return None

        # (entry_widget, membership_widget) pairs, in Tab order.
        groups: list[tuple] = []
        if self._wizard_op == "synthesize":
            node_grp = _fcl_group("syn_nodes")
            if node_grp:
                groups.append(node_grp)
            try:
                ta = container.query_one(TextArea)
                groups.append((ta, ta))
            except Exception:
                pass
        elif self._wizard_op == "compare":
            node_grp = _fcl_group("cmp_nodes")
            if node_grp:
                groups.append(node_grp)
            dim_grp = _fcl_group("cmp_dims")
            if dim_grp:
                groups.append(dim_grp)
            try:
                box = container.query_one("#cmp_sections_box", Container)
                secs = list(box.query("Checkbox.chk_section"))
                if secs:
                    groups.append((secs[0], box))
            except Exception:
                pass
        try:
            btn = container.query_one(".btn_actions_next", Button)
            groups.append((btn, btn))
        except Exception:
            pass

        if not groups:
            return False

        current = None
        for i, (_entry, member) in enumerate(groups):
            if self._focus_within(member):
                current = i
                break

        if current is None:
            new_idx = 0 if direction == 1 else len(groups) - 1
        else:
            new_idx = (current + direction) % len(groups)

        entry = groups[new_idx][0]
        entry.focus()
        try:
            entry.scroll_visible()
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
        self._update_module_status()
        self._populate_node_list()
        self.query_one(DAGDisplay).load_dag(self.session_path)
        self._actions_show_step1()
        try:
            self.query_one("#status_polling_indicator", PollingIndicator).start()
        except Exception:
            pass
        self._status_refresh_timer = self.set_interval(30, self._refresh_status_tab)
        self._try_apply_initializer_if_needed()
        self._scan_existing_patchers()
        self._scan_existing_explorers()
        self._scan_existing_synthesizers()
        self._scan_existing_detailers()
        self._scan_existing_module_agents()

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

    # ------------------------------------------------------------------
    # Patcher auto-apply (mirrors initializer pattern)
    # ------------------------------------------------------------------

    _PATCHER_INPUT_META_RE = re.compile(
        r"-\s*Metadata:\s*\S+/br_nodes/([A-Za-z0-9_]+)\.yaml"
    )

    def _register_patcher_source(self, agent_name: str,
                                 source_node_id: str) -> None:
        """Main-thread: track a freshly-registered patcher and ensure the
        poll timer is running."""
        self._patcher_sources[agent_name] = source_node_id
        self._ensure_patcher_poll_timer()

    def _ensure_patcher_poll_timer(self) -> None:
        if self._patcher_poll_timer is not None:
            return
        if not self._patcher_sources:
            return
        self._patcher_poll_timer = self.set_interval(5, self._poll_patchers)

    def _stop_patcher_poll_timer(self) -> None:
        if self._patcher_poll_timer is not None:
            try:
                self._patcher_poll_timer.stop()
            except Exception:
                pass
            self._patcher_poll_timer = None

    def _scan_existing_patchers(self) -> None:
        """Scan the worktree for patcher agents that are in-flight or
        completed-but-unapplied, so the poll timer keeps watching them.
        Recovers the source_node_id by parsing the agent's _input.md
        (written by ``_assemble_input_patcher``).

        Idempotent — safe to call from ``_load_existing_session``.
        """
        wt = self.session_path
        if not wt or not Path(wt).is_dir():
            return
        try:
            from brainstorm.brainstorm_session import (
                _agent_apply_scan_should_track,
                _patcher_needs_apply,
            )
        except Exception:
            return
        for status_path in sorted(Path(wt).glob("patcher_*_status.yaml")):
            agent = status_path.stem[:-len("_status")]
            if agent in self._patcher_sources:
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            input_path = Path(wt) / f"{agent}_input.md"
            if not input_path.is_file():
                continue
            try:
                input_text = input_path.read_text(encoding="utf-8")
            except Exception:
                continue
            m = self._PATCHER_INPUT_META_RE.search(input_text)
            if not m:
                continue
            needs_apply = (
                _patcher_needs_apply(self.task_num, agent)
                if status == "Completed" else False
            )
            if not _agent_apply_scan_should_track(status, needs_apply):
                continue
            self._patcher_sources[agent] = m.group(1)
        self._ensure_patcher_poll_timer()

    def _poll_patchers(self) -> None:
        """Timer tick: for each tracked patcher, apply its output if it's
        Completed. Drops entries whose output has already been applied
        (idempotent across restarts). Stops the timer when empty.
        """
        if not self._patcher_sources:
            self._stop_patcher_poll_timer()
            return
        try:
            from brainstorm.brainstorm_session import (
                _AGENT_FAILED_STATUSES,
                _patcher_needs_apply,
            )
        except Exception:
            return
        for agent, source in list(self._patcher_sources.items()):
            if agent in self._applying_patcher:
                continue
            status_path = self.session_path / f"{agent}_status.yaml"
            if not status_path.is_file():
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            if status in _AGENT_FAILED_STATUSES:
                self._patcher_sources.pop(agent, None)
                continue
            if status != "Completed":
                continue
            if not _patcher_needs_apply(self.task_num, agent):
                # Already applied (e.g., by CLI fallback). Drop and move on.
                self._patcher_sources.pop(agent, None)
                continue
            self._try_apply_patcher_if_needed(agent, source)
        if not self._patcher_sources:
            self._stop_patcher_poll_timer()

    def _try_apply_patcher_if_needed(self, agent_name: str,
                                     source_node_id: str,
                                     force: bool = False) -> None:
        """Single-shot apply attempt for one patcher agent. Failures
        surface via the IMPACT/error banner; success refreshes the DAG.
        """
        if agent_name in self._applying_patcher:
            return
        from brainstorm.brainstorm_session import (
            _patcher_needs_apply,
            apply_patcher_output,
        )
        if not force and not _patcher_needs_apply(self.task_num, agent_name):
            return
        self._applying_patcher.add(agent_name)
        try:
            try:
                new_id, impact, details = apply_patcher_output(
                    self.task_num, agent_name, source_node_id,
                )
            except Exception as exc:
                self._patcher_apply_errors[agent_name] = str(exc)
                self._set_impact_banner(
                    f"Patcher {agent_name} apply failed: {exc} — "
                    f"run `ait brainstorm apply-patcher {self.task_num} "
                    f"{agent_name} {source_node_id}` to retry"
                )
                return
            self._patcher_apply_errors.pop(agent_name, None)
            self._patcher_sources.pop(agent_name, None)
            if impact == "IMPACT_FLAG":
                self._set_impact_banner(
                    f"Patcher {agent_name} → {new_id}: IMPACT_FLAG — "
                    f"Explorer regeneration recommended.\n{details}"
                )
            else:
                self._clear_impact_banner()
                self.notify(f"Patched plan applied → {new_id}.")
            self._load_existing_session()
        finally:
            self._applying_patcher.discard(agent_name)

    def _set_impact_banner(self, msg: str) -> None:
        try:
            widget = self.query_one("#patcher_impact_banner", Static)
            widget.update(msg)
            widget.add_class("visible")
        except Exception:
            pass

    def _clear_impact_banner(self) -> None:
        try:
            widget = self.query_one("#patcher_impact_banner", Static)
            widget.update("")
            widget.remove_class("visible")
        except Exception:
            pass

    def action_retry_patcher_apply(self) -> None:
        """ctrl+shift+r: force-retry a patcher apply.

        Walks the worktree (rather than ``self._patcher_sources``) so the
        retry works after auto-apply has already drained the tracking
        dict — the previously-applied-then-corrupted case mirroring t787
        item #3 / t837. Recovers ``source_node_id`` from
        ``self._patcher_sources`` if present, else by re-parsing the
        agent's ``_input.md``.
        """
        agent = self._pick_completed_agent_for_retry("patcher")
        if agent is None:
            self.notify("No completed patcher agents to retry.")
            return
        source = self._patcher_sources.get(agent)
        if source is None:
            source = self._recover_node_id_from_input(agent)
        if source is None:
            self.notify(
                f"Cannot retry {agent}: source_node_id not recoverable."
            )
            return
        self._try_apply_patcher_if_needed(agent, source, force=True)

    # ------------------------------------------------------------------
    # Explorer auto-apply (mirrors patcher pattern; no source_node_id —
    # the explorer NODE_YAML carries its own parents list)
    # ------------------------------------------------------------------

    def _register_explorer_agent(self, agent_name: str) -> None:
        """Main-thread: track a freshly-registered explorer and ensure the
        poll timer is running."""
        self._explorer_agents.add(agent_name)
        self._ensure_explorer_poll_timer()

    def _ensure_explorer_poll_timer(self) -> None:
        if self._explorer_poll_timer is not None:
            return
        if not self._explorer_agents:
            return
        self._explorer_poll_timer = self.set_interval(5, self._poll_explorers)

    def _stop_explorer_poll_timer(self) -> None:
        if self._explorer_poll_timer is not None:
            try:
                self._explorer_poll_timer.stop()
            except Exception:
                pass
            self._explorer_poll_timer = None

    def _scan_existing_explorers(self) -> None:
        """Scan the worktree for explorer agents that are in-flight or
        completed-but-unapplied, so the poll timer keeps watching them.
        Idempotent — safe to call from ``_load_existing_session``.
        """
        wt = self.session_path
        if not wt or not Path(wt).is_dir():
            return
        try:
            from brainstorm.brainstorm_session import (
                _agent_apply_scan_should_track,
                _explorer_needs_apply,
            )
        except Exception:
            return
        for status_path in sorted(Path(wt).glob("explorer_*_status.yaml")):
            agent = status_path.stem[:-len("_status")]
            if agent in self._explorer_agents:
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            needs_apply = (
                _explorer_needs_apply(self.task_num, agent)
                if status == "Completed" else False
            )
            if not _agent_apply_scan_should_track(status, needs_apply):
                continue
            self._explorer_agents.add(agent)
        self._ensure_explorer_poll_timer()

    def _poll_explorers(self) -> None:
        """Timer tick: for each tracked explorer, apply its output if it's
        Completed. Drops entries whose output has already been applied
        (idempotent across restarts). Stops the timer when empty.
        """
        if not self._explorer_agents:
            self._stop_explorer_poll_timer()
            return
        try:
            from brainstorm.brainstorm_session import (
                _AGENT_FAILED_STATUSES,
                _explorer_needs_apply,
            )
        except Exception:
            return
        for agent in list(self._explorer_agents):
            if agent in self._applying_explorer:
                continue
            status_path = self.session_path / f"{agent}_status.yaml"
            if not status_path.is_file():
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            if status in _AGENT_FAILED_STATUSES:
                self._explorer_agents.discard(agent)
                continue
            if status != "Completed":
                continue
            if not _explorer_needs_apply(self.task_num, agent):
                # Already applied (e.g., by CLI fallback). Drop and move on.
                self._explorer_agents.discard(agent)
                continue
            self._try_apply_explorer_if_needed(agent)
        if not self._explorer_agents:
            self._stop_explorer_poll_timer()

    def _try_apply_explorer_if_needed(
        self, agent_name: str, force: bool = False,
    ) -> None:
        """Single-shot apply attempt for one explorer agent. Failures
        surface via the initializer apply banner; success refreshes the
        DAG.
        """
        if agent_name in self._applying_explorer:
            return
        from brainstorm.brainstorm_session import (
            _explorer_needs_apply,
            apply_explorer_output,
        )
        if not force and not _explorer_needs_apply(self.task_num, agent_name):
            return
        self._applying_explorer.add(agent_name)
        try:
            try:
                new_id = apply_explorer_output(self.task_num, agent_name)
            except Exception as exc:
                self._explorer_apply_errors[agent_name] = str(exc)
                self._set_apply_banner(
                    f"Explorer {agent_name} apply failed: {exc} — "
                    f"run `ait brainstorm apply-explorer {self.task_num} "
                    f"{agent_name}` to retry"
                )
                return
            self._explorer_apply_errors.pop(agent_name, None)
            self._explorer_agents.discard(agent_name)
            self._clear_apply_banner()
            self.notify(f"Explorer {agent_name} applied → {new_id}.")
            self._load_existing_session()
        finally:
            self._applying_explorer.discard(agent_name)

    # ------------------------------------------------------------------
    # Module op auto-apply
    # ------------------------------------------------------------------

    def _register_module_agent(self, agent_name: str) -> None:
        self._module_agents.add(agent_name)
        self._ensure_module_poll_timer()

    def _ensure_module_poll_timer(self) -> None:
        if self._module_poll_timer is not None:
            return
        if not self._module_agents:
            return
        self._module_poll_timer = self.set_interval(5, self._poll_module_agents)

    def _stop_module_poll_timer(self) -> None:
        if self._module_poll_timer is not None:
            try:
                self._module_poll_timer.stop()
            except Exception:
                pass
            self._module_poll_timer = None

    def _scan_existing_module_agents(self) -> None:
        wt = self.session_path
        if not wt or not Path(wt).is_dir():
            return
        try:
            from brainstorm.brainstorm_session import (
                _agent_apply_scan_should_track,
                _module_decomposer_needs_apply,
                _module_merger_needs_apply,
                _module_syncer_needs_apply,
            )
        except Exception:
            return
        for pattern, needs_fn in (
            ("module_decomposer_*_status.yaml", _module_decomposer_needs_apply),
            ("module_merger_*_status.yaml", _module_merger_needs_apply),
            ("module_syncer_*_status.yaml", _module_syncer_needs_apply),
        ):
            for status_path in sorted(Path(wt).glob(pattern)):
                agent = status_path.stem[:-len("_status")]
                if agent in self._module_agents:
                    continue
                try:
                    data = read_yaml(str(status_path))
                except Exception:
                    continue
                status = (data or {}).get("status", "")
                needs_apply = (
                    needs_fn(self.task_num, agent) if status == "Completed" else False
                )
                if _agent_apply_scan_should_track(status, needs_apply):
                    self._module_agents.add(agent)
        self._ensure_module_poll_timer()

    def _poll_module_agents(self) -> None:
        if not self._module_agents:
            self._stop_module_poll_timer()
            return
        try:
            from brainstorm.brainstorm_session import _AGENT_FAILED_STATUSES
        except Exception:
            return
        for agent in list(self._module_agents):
            if agent in self._applying_module_agent:
                continue
            status_path = self.session_path / f"{agent}_status.yaml"
            if not status_path.is_file():
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            if status in _AGENT_FAILED_STATUSES:
                self._module_agents.discard(agent)
                continue
            if status != "Completed":
                continue
            self._try_apply_module_agent_if_needed(agent)
        if not self._module_agents:
            self._stop_module_poll_timer()

    def _module_agent_needs_apply(self, agent_name: str) -> bool:
        from brainstorm.brainstorm_session import (
            _module_decomposer_needs_apply,
            _module_merger_needs_apply,
            _module_syncer_needs_apply,
        )
        if agent_name.startswith("module_decomposer_"):
            return _module_decomposer_needs_apply(self.task_num, agent_name)
        if agent_name.startswith("module_merger_"):
            return _module_merger_needs_apply(self.task_num, agent_name)
        if agent_name.startswith("module_syncer_"):
            return _module_syncer_needs_apply(self.task_num, agent_name)
        return False

    def _try_apply_module_agent_if_needed(
        self, agent_name: str, force: bool = False,
    ) -> None:
        if agent_name in self._applying_module_agent:
            return
        if not force and not self._module_agent_needs_apply(agent_name):
            self._module_agents.discard(agent_name)
            return
        # Review gate (t929_1): for module_decompose, pause before applying so
        # the operator can preview / steer / accept. Only decomposer ops gate;
        # merge and sync auto-apply as before. ``force`` and an already-accepted
        # proposal bypass the gate.
        if (
            not force
            and agent_name.startswith("module_decomposer_")
            and agent_name not in self._module_review_accepted
            and self._module_review_enabled(agent_name)
        ):
            if agent_name not in self._module_review_pending:
                self._module_review_pending.add(agent_name)
                self._open_module_preview(agent_name)
            return
        from brainstorm.brainstorm_session import (
            apply_module_decomposer_output,
            apply_module_merger_output,
            apply_module_syncer_output,
        )
        self._applying_module_agent.add(agent_name)
        try:
            try:
                if agent_name.startswith("module_decomposer_"):
                    new_ids = apply_module_decomposer_output(self.task_num, agent_name)
                    result = ", ".join(new_ids)
                elif agent_name.startswith("module_syncer_"):
                    result = apply_module_syncer_output(self.task_num, agent_name)
                else:
                    result = apply_module_merger_output(self.task_num, agent_name)
            except Exception as exc:
                self._module_apply_errors[agent_name] = str(exc)
                self._set_apply_banner(
                    f"Module agent {agent_name} apply failed: {exc}"
                )
                return
            self._module_apply_errors.pop(agent_name, None)
            self._module_agents.discard(agent_name)
            self._module_review_pending.discard(agent_name)
            self._module_review_accepted.discard(agent_name)
            self._clear_apply_banner()
            self.notify(f"Module agent {agent_name} applied → {result}.")
            self._load_existing_session()
        finally:
            self._applying_module_agent.discard(agent_name)

    # ------------------------------------------------------------------
    # Module decompose review gate (t929_1: iterate-before-apply)
    # ------------------------------------------------------------------

    def _module_review_enabled(self, agent_name: str) -> bool:
        from brainstorm.brainstorm_session import module_decomposer_review_enabled
        try:
            return module_decomposer_review_enabled(self.task_num, agent_name)
        except Exception:
            return False

    def _open_module_preview(self, agent_name: str) -> None:
        """Parse the decomposer output and push the preview modal.

        On a parse failure, fall through to the apply path (which records the
        same error and banners it) instead of blocking on a broken preview.
        """
        from brainstorm.brainstorm_session import (
            assign_inferred_module_node_ids,
            parse_module_decomposer_output,
        )
        # Assign deferred IDs for infer-mode output so the preview shows the
        # proposed names + their node ids (t929_2). No-op for names-given output.
        assign_inferred_module_node_ids(self.task_num, agent_name)
        out_path = Path(self.session_path) / f"{agent_name}_output.md"
        try:
            blocks = parse_module_decomposer_output(
                out_path.read_text(encoding="utf-8")
            )
        except Exception:
            self._module_review_pending.discard(agent_name)
            self._module_review_accepted.add(agent_name)
            self._try_apply_module_agent_if_needed(agent_name)
            return
        self.push_screen(
            ModulePreviewScreen(agent_name, blocks),
            lambda result, a=agent_name: self._on_module_preview_result(a, result),
        )

    def _on_module_preview_result(self, agent_name: str, result) -> None:
        """Handle the operator's Accept / Re-run / Cancel choice."""
        self._module_review_pending.discard(agent_name)
        action = result.get("action") if isinstance(result, dict) else None
        if action == "accept":
            self._module_review_accepted.add(agent_name)
            self._try_apply_module_agent_if_needed(agent_name)
        elif action == "rerun":
            steer = result.get("steer", "") if isinstance(result, dict) else ""
            self._module_rerun_decomposer(agent_name, steer)
        else:
            # Cancel or escape-dismiss: discard the proposal, graph untouched.
            self._module_cancel_decomposer(agent_name)

    def _module_cancel_decomposer(self, agent_name: str) -> None:
        from brainstorm.brainstorm_session import discard_module_decomposer_output
        discard_module_decomposer_output(
            self.task_num, agent_name, suffix="cancelled"
        )
        self._module_agents.discard(agent_name)
        self._module_review_accepted.discard(agent_name)
        self._module_review_pending.discard(agent_name)
        self.notify(
            f"Discarded module decomposition {agent_name}; graph unchanged."
        )

    @work(thread=True)
    def _module_rerun_decomposer(self, agent_name: str, steer_text: str) -> None:
        """Re-dispatch a decomposer with accumulated steering (t929_1).

        Neutralizes the reviewed proposal (graph untouched), then registers a
        fresh decomposer in a new group carrying the ordered revision notes. The
        composition rule (Steering overrides the Decomposition Plan on conflict;
        later revisions win) lives in ``_assemble_input_module_decomposer``.
        """
        from brainstorm.brainstorm_session import (
            _agent_to_group_name,
            _read_groups_file,
            discard_module_decomposer_output,
            record_operation,
        )
        wt = Path(self.session_path)
        old_group = _agent_to_group_name(agent_name)
        groups = _read_groups_file(str(wt / GROUPS_FILE)).get("groups", {})
        info = groups.get(old_group, {}) if isinstance(groups, dict) else {}
        modules = info.get("modules") or []
        subgraph = (
            info.get("source_subgraph")
            or info.get("subgraph")
            or UMBRELLA_SUBGRAPH
        )
        source_node = info.get("head_at_creation") or get_head(
            self.session_path, module=subgraph
        )
        if not modules or not source_node:
            self.call_from_thread(
                self.notify,
                "Cannot re-run: module configuration is missing.",
                severity="error",
            )
            return
        from_sections = bool(info.get("from_sections"))
        link_to_task = bool(info.get("link_to_task"))
        instructions = info.get("instructions", "") or ""
        launch_mode = info.get("launch_mode") or DEFAULT_LAUNCH_MODE

        # Neutralize the reviewed proposal (durable; graph untouched).
        discard_module_decomposer_output(
            self.task_num, agent_name, suffix="superseded"
        )
        self._module_agents.discard(agent_name)
        self._module_review_accepted.discard(agent_name)

        # Accumulate revisions, carried forward to the new group.
        revisions = list(self._module_steer.get(old_group, []))
        if steer_text and steer_text.strip():
            revisions.append(steer_text.strip())

        crew_id = self.session_data.get(
            "crew_id", f"brainstorm-{self.task_num}"
        )
        new_group = self._next_group_name("module_decompose")
        self._module_steer[new_group] = revisions
        try:
            new_agent = register_module_decomposer(
                self.session_path,
                crew_id,
                source_node,
                modules,
                new_group,
                from_sections=from_sections,
                link_to_task=link_to_task,
                instructions=instructions,
                steer=revisions,
                launch_mode=launch_mode,
            )
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"Re-run failed: {exc}", severity="error",
            )
            return
        record_operation(
            self.task_num,
            group_name=new_group,
            operation="module_decompose",
            agents=[new_agent],
            head_at_creation=source_node,
            subgraph=subgraph,
            modules=modules,
            from_sections=from_sections,
            link_to_task=link_to_task,
            source_subgraph=subgraph,
            review_before_apply=True,
            instructions=instructions,
            launch_mode=launch_mode,
        )
        self.call_from_thread(self._register_module_agent, new_agent)
        self.call_from_thread(
            self.notify,
            f"Re-running module decomposer (revision {len(revisions)}): {new_agent}",
        )

    def _pick_completed_agent_for_retry(self, role: str) -> str | None:
        """Walk the session worktree and return the agent name with the
        most recent ``_status.yaml`` mtime whose status is ``Completed``,
        for the given role prefix (``explorer``, ``patcher``,
        ``synthesizer``, ``detailer``). Returns ``None`` if the worktree
        is missing or no Completed agent is found. Shared by the four
        ``action_retry_*_apply`` methods so the retry path keeps working
        after auto-apply has drained the in-memory tracking container.
        """
        wt = self.session_path
        if not wt or not Path(wt).is_dir():
            return None
        candidates: list[tuple[str, float]] = []
        for status_path in Path(wt).glob(f"{role}_*_status.yaml"):
            agent = status_path.stem[: -len("_status")]
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            if (data or {}).get("status", "") != "Completed":
                continue
            try:
                mtime = status_path.stat().st_mtime
            except Exception:
                mtime = 0.0
            candidates.append((agent, mtime))
        if not candidates:
            return None
        return max(candidates, key=lambda p: p[1])[0]

    def _recover_node_id_from_input(self, agent: str) -> str | None:
        """Re-parse ``<agent>_input.md`` for the node-id captured by
        ``_PATCHER_INPUT_META_RE``. Used by the patcher / detailer retry
        actions to recover ``source_node_id`` / ``target_node_id`` when
        the in-memory tracking entry has been drained by auto-apply.
        """
        wt = self.session_path
        if not wt or not Path(wt).is_dir():
            return None
        input_path = Path(wt) / f"{agent}_input.md"
        if not input_path.is_file():
            return None
        try:
            text = input_path.read_text(encoding="utf-8")
        except Exception:
            return None
        m = self._PATCHER_INPUT_META_RE.search(text)
        return m.group(1) if m else None

    def action_retry_explorer_apply(self) -> None:
        """ctrl+shift+x: force-retry an explorer apply.

        After a successful auto-apply the agent is dropped from
        ``self._explorer_agents`` and is not re-tracked by
        ``_scan_existing_explorers`` (its node already exists, so
        ``_explorer_needs_apply`` returns False). Walk the worktree
        instead so the manual retry path also covers the
        already-applied-then-corrupted case exercised by t787 item #3.
        """
        agent = self._pick_completed_agent_for_retry("explorer")
        if agent is None:
            self.notify("No completed explorer agents to retry.")
            return
        self._try_apply_explorer_if_needed(agent, force=True)

    def _register_synthesizer_agent(self, agent_name: str) -> None:
        """Main-thread: track a freshly-registered synthesizer and ensure
        the poll timer is running."""
        self._synthesizer_agents.add(agent_name)
        self._ensure_synthesizer_poll_timer()

    def _ensure_synthesizer_poll_timer(self) -> None:
        if self._synthesizer_poll_timer is not None:
            return
        if not self._synthesizer_agents:
            return
        self._synthesizer_poll_timer = self.set_interval(
            5, self._poll_synthesizers,
        )

    def _stop_synthesizer_poll_timer(self) -> None:
        if self._synthesizer_poll_timer is not None:
            try:
                self._synthesizer_poll_timer.stop()
            except Exception:
                pass
            self._synthesizer_poll_timer = None

    def _scan_existing_synthesizers(self) -> None:
        """Scan the worktree for synthesizer agents that are in-flight or
        completed-but-unapplied, so the poll timer keeps watching them.
        Idempotent — safe to call from ``_load_existing_session``.
        """
        wt = self.session_path
        if not wt or not Path(wt).is_dir():
            return
        try:
            from brainstorm.brainstorm_session import (
                _agent_apply_scan_should_track,
                _synthesizer_needs_apply,
            )
        except Exception:
            return
        for status_path in sorted(Path(wt).glob("synthesizer_*_status.yaml")):
            agent = status_path.stem[:-len("_status")]
            if agent in self._synthesizer_agents:
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            needs_apply = (
                _synthesizer_needs_apply(self.task_num, agent)
                if status == "Completed" else False
            )
            if not _agent_apply_scan_should_track(status, needs_apply):
                continue
            self._synthesizer_agents.add(agent)
        self._ensure_synthesizer_poll_timer()

    def _poll_synthesizers(self) -> None:
        """Timer tick: for each tracked synthesizer, apply its output if
        it's Completed. Drops entries whose output has already been
        applied (idempotent across restarts). Stops the timer when empty.
        """
        if not self._synthesizer_agents:
            self._stop_synthesizer_poll_timer()
            return
        try:
            from brainstorm.brainstorm_session import (
                _AGENT_FAILED_STATUSES,
                _synthesizer_needs_apply,
            )
        except Exception:
            return
        for agent in list(self._synthesizer_agents):
            if agent in self._applying_synthesizer:
                continue
            status_path = self.session_path / f"{agent}_status.yaml"
            if not status_path.is_file():
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            if status in _AGENT_FAILED_STATUSES:
                self._synthesizer_agents.discard(agent)
                continue
            if status != "Completed":
                continue
            if not _synthesizer_needs_apply(self.task_num, agent):
                # Already applied (e.g., by CLI fallback).
                self._synthesizer_agents.discard(agent)
                continue
            self._try_apply_synthesizer_if_needed(agent)
        if not self._synthesizer_agents:
            self._stop_synthesizer_poll_timer()

    def _try_apply_synthesizer_if_needed(
        self, agent_name: str, force: bool = False,
    ) -> None:
        """Single-shot apply attempt for one synthesizer agent. Failures
        surface via the initializer apply banner; success refreshes the
        DAG.
        """
        if agent_name in self._applying_synthesizer:
            return
        from brainstorm.brainstorm_session import (
            _synthesizer_needs_apply,
            apply_synthesizer_output,
        )
        if not force and not _synthesizer_needs_apply(
            self.task_num, agent_name,
        ):
            return
        self._applying_synthesizer.add(agent_name)
        try:
            try:
                new_id = apply_synthesizer_output(
                    self.task_num, agent_name,
                )
            except Exception as exc:
                self._synthesizer_apply_errors[agent_name] = str(exc)
                self._set_apply_banner(
                    f"Synthesizer {agent_name} apply failed: {exc} — "
                    f"run `ait brainstorm apply-synthesizer "
                    f"{self.task_num} {agent_name}` to retry"
                )
                return
            self._synthesizer_apply_errors.pop(agent_name, None)
            self._synthesizer_agents.discard(agent_name)
            self._clear_apply_banner()
            self.notify(f"Synthesizer {agent_name} applied → {new_id}.")
            self._load_existing_session()
        finally:
            self._applying_synthesizer.discard(agent_name)

    def action_retry_synthesizer_apply(self) -> None:
        """ctrl+shift+y: force-retry a synthesizer apply.

        Walks the worktree (rather than ``self._synthesizer_agents``) so
        the retry works after auto-apply has already drained the tracking
        set — mirrors the t837 fix for explorer.
        """
        agent = self._pick_completed_agent_for_retry("synthesizer")
        if agent is None:
            self.notify("No completed synthesizer agents to retry.")
            return
        self._try_apply_synthesizer_if_needed(agent, force=True)

    # ------------------------------------------------------------------
    # Detailer auto-apply (mirrors patcher pattern — keyed on the target
    # node id; the detailer enriches an existing node, writing its plan)
    # ------------------------------------------------------------------

    def _register_detailer_target(self, agent_name: str,
                                  target_node_id: str) -> None:
        """Main-thread: track a freshly-registered detailer and ensure the
        poll timer is running."""
        self._detailer_targets[agent_name] = target_node_id
        self._ensure_detailer_poll_timer()

    def _ensure_detailer_poll_timer(self) -> None:
        if self._detailer_poll_timer is not None:
            return
        if not self._detailer_targets:
            return
        self._detailer_poll_timer = self.set_interval(5, self._poll_detailers)

    def _stop_detailer_poll_timer(self) -> None:
        if self._detailer_poll_timer is not None:
            try:
                self._detailer_poll_timer.stop()
            except Exception:
                pass
            self._detailer_poll_timer = None

    def _scan_existing_detailers(self) -> None:
        """Scan the worktree for detailer agents that are in-flight or
        completed-but-unapplied, so the poll timer keeps watching them.
        Recovers the target_node_id by parsing the agent's _input.md (the
        ``## Target Node`` Metadata line written by
        ``_assemble_input_detailer``).

        Idempotent — safe to call from ``_load_existing_session``.
        """
        wt = self.session_path
        if not wt or not Path(wt).is_dir():
            return
        try:
            from brainstorm.brainstorm_session import (
                _agent_apply_scan_should_track,
                _detailer_needs_apply,
            )
        except Exception:
            return
        for status_path in sorted(Path(wt).glob("detailer_*_status.yaml")):
            agent = status_path.stem[:-len("_status")]
            if agent in self._detailer_targets:
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            input_path = Path(wt) / f"{agent}_input.md"
            if not input_path.is_file():
                continue
            try:
                input_text = input_path.read_text(encoding="utf-8")
            except Exception:
                continue
            m = self._PATCHER_INPUT_META_RE.search(input_text)
            if not m:
                continue
            target_node_id = m.group(1)
            needs_apply = (
                _detailer_needs_apply(self.task_num, agent, target_node_id)
                if status == "Completed" else False
            )
            if not _agent_apply_scan_should_track(status, needs_apply):
                continue
            self._detailer_targets[agent] = target_node_id
        self._ensure_detailer_poll_timer()

    def _poll_detailers(self) -> None:
        """Timer tick: for each tracked detailer, apply its output if it's
        Completed. Drops entries whose output has already been applied
        (idempotent across restarts). Stops the timer when empty.
        """
        if not self._detailer_targets:
            self._stop_detailer_poll_timer()
            return
        try:
            from brainstorm.brainstorm_session import (
                _AGENT_FAILED_STATUSES,
                _detailer_needs_apply,
            )
        except Exception:
            return
        for agent, target in list(self._detailer_targets.items()):
            if agent in self._applying_detailer:
                continue
            status_path = self.session_path / f"{agent}_status.yaml"
            if not status_path.is_file():
                continue
            try:
                data = read_yaml(str(status_path))
            except Exception:
                continue
            status = (data or {}).get("status", "")
            if status in _AGENT_FAILED_STATUSES:
                self._detailer_targets.pop(agent, None)
                continue
            if status != "Completed":
                continue
            if not _detailer_needs_apply(self.task_num, agent, target):
                # Already applied (e.g., by CLI fallback). Drop and move on.
                self._detailer_targets.pop(agent, None)
                continue
            self._try_apply_detailer_if_needed(agent, target)
        if not self._detailer_targets:
            self._stop_detailer_poll_timer()

    def _try_apply_detailer_if_needed(self, agent_name: str,
                                      target_node_id: str,
                                      force: bool = False) -> None:
        """Single-shot apply attempt for one detailer agent. Failures
        surface via the initializer apply banner; success refreshes the DAG.
        """
        if agent_name in self._applying_detailer:
            return
        from brainstorm.brainstorm_session import (
            _detailer_needs_apply,
            apply_detailer_output,
        )
        if not force and not _detailer_needs_apply(
            self.task_num, agent_name, target_node_id,
        ):
            return
        self._applying_detailer.add(agent_name)
        try:
            try:
                apply_detailer_output(
                    self.task_num, agent_name, target_node_id,
                )
            except Exception as exc:
                self._detailer_apply_errors[agent_name] = str(exc)
                self._set_apply_banner(
                    f"Detailer {agent_name} apply failed: {exc} — "
                    f"run `ait brainstorm apply-detailer {self.task_num} "
                    f"{agent_name} {target_node_id}` to retry"
                )
                return
            self._detailer_apply_errors.pop(agent_name, None)
            self._detailer_targets.pop(agent_name, None)
            self._clear_apply_banner()
            self.notify(
                f"Detailer {agent_name} applied → {target_node_id} plan."
            )
            self._load_existing_session()
        finally:
            self._applying_detailer.discard(agent_name)

    def action_retry_detailer_apply(self) -> None:
        """ctrl+shift+d: force-retry a detailer apply.

        Walks the worktree (rather than ``self._detailer_targets``) so
        the retry works after auto-apply has already drained the tracking
        dict — mirrors the t837 fix for explorer. Recovers
        ``target_node_id`` from ``self._detailer_targets`` if present,
        else by re-parsing the agent's ``_input.md``.
        """
        agent = self._pick_completed_agent_for_retry("detailer")
        if agent is None:
            self.notify("No completed detailer agents to retry.")
            return
        target = self._detailer_targets.get(agent)
        if target is None:
            target = self._recover_node_id_from_input(agent)
        if target is None:
            self.notify(
                f"Cannot retry {agent}: target_node_id not recoverable."
            )
            return
        self._try_apply_detailer_if_needed(agent, target, force=True)

    def on_tabbed_content_tab_activated(self, event) -> None:
        """Refresh Status tab when it becomes active."""
        if event.pane.id == "tab_status":
            self._refresh_status_tab()

    def _refresh_status_tab(self) -> None:
        """Populate the Status tab with operation groups and agent statuses."""
        try:
            self.query_one("#status_polling_indicator", PollingIndicator).flash()
        except Exception:
            pass
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
                aggregate = self._compute_group_progress(wt_path, ginfo)
                container.mount(
                    GroupRow(
                        gname, ginfo, expanded=expanded,
                        aggregate_progress=aggregate,
                        classes="status_group_row",
                    )
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

    def _compute_group_progress(
        self, wt_path: str, ginfo: dict
    ) -> int | None:
        """Return the mean per-agent progress for a group, rounded to int.

        Reads each agent's ``<name>_status.yaml::progress`` value. Returns
        ``None`` when the group has no agents on disk so the GroupRow
        suppresses the bar. Used by Status-tab refresh to give parallel
        ops (e.g. multi-explorer ``explore_<seq>``) a single aggregate
        indicator at the group level (t792).
        """
        import os

        agent_names = ginfo.get("agents") or []
        if not agent_names:
            return None
        progresses: list[int] = []
        for name in agent_names:
            sf = os.path.join(wt_path, f"{name}_status.yaml")
            if not os.path.isfile(sf):
                continue
            try:
                data = read_yaml(sf)
            except Exception:
                continue
            try:
                p = int(data.get("progress", 0) or 0)
            except (TypeError, ValueError):
                p = 0
            progresses.append(max(0, min(100, p)))
        if not progresses:
            return None
        return int(round(sum(progresses) / len(progresses)))

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

        bar = _format_progress_bar(data.get("progress", 0))
        progress_str = f"  {bar}" if bar else ""

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
            f"[{color}]{status}[/{color}]{progress_str}{hb_str}{msg_str}"
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

    def _update_module_status(self) -> None:
        """Render the per-module fluid-status view (§4.7, UC-2, t756_5).

        A read-only subgraph tree: one line per subgraph with its computed
        status badge, the orthogonal ``deferred`` overlay, and sync/link
        context. Sessions with only the ``_umbrella`` root show a placeholder so
        the common single-subgraph case stays uncluttered.
        """
        try:
            label = self.query_one("#module_status_info", Label)
        except Exception:
            return
        rows = module_status_rows(self.session_path)
        if not any(not r["is_umbrella"] for r in rows):
            label.update("[dim]— no modules —[/]")
            return
        lines: list[str] = []
        for r in rows:
            status = r["status"]
            style = MODULE_STATUS_STYLES.get(status, UNKNOWN_STATUS_STYLE)
            color = style.color
            hex_c = color.name if color else "#888888"
            name = "root" if r["is_umbrella"] else r["module"]
            extra: list[str] = []
            if r["deferred"]:
                extra.append("[#FF5555 italic]deferred[/]")
            if r["task_id"]:
                extra.append(f"[dim]t{r['task_id']}[/]")
            if r["last_synced"]:
                extra.append(f"[dim]synced {r['last_synced']}[/]")
            suffix = ("  " + "  ".join(extra)) if extra else ""
            lines.append(
                f"[{hex_c} bold]{status}[/]  {name} "
                f"[dim]({r['node_count']})[/]{suffix}"
            )
        label.update("\n".join(lines))

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
            has_plan = bool(node_data.get("plan_file"))
            row = NodeRow(nid, desc, is_head=(nid == head), has_plan=has_plan)
            pane.mount(row)

    def _render_node_detail_widgets(self, node_id: str) -> tuple[str, list]:
        """Return (title_text, widgets) for the inline node-detail pane.

        Shared by Dashboard's _show_node_detail and Graph's
        _show_dag_node_detail. Widgets are unmounted instances ready
        for mount() into the caller's container.
        """
        try:
            node_data = read_node(self.session_path, node_id)
        except Exception:
            return (f"Node: {node_id}", [Static("(node not readable)")])

        desc = node_data.get("description", "")
        parents = node_data.get("parents", [])
        created = node_data.get("created_at", "")
        group = node_data.get("created_by_group", "")

        widgets: list = []
        widgets.append(Static(
            f"[bold $accent]Description:[/] {desc}", classes="meta_field"))
        widgets.append(Static(
            f"[bold $accent]Parents:[/] "
            f"{', '.join(parents) if parents else 'root'}",
            classes="meta_field"))
        widgets.append(Static(
            f"[bold $accent]Created:[/] {created}", classes="meta_field"))
        if group:
            groups = _read_groups(self.session_path)
            group, ginfo = resolve_node_group(node_id, group, groups)
            op = ginfo.get("operation", "?")
            agents = ginfo.get("agents") or []
            when = ginfo.get("created_at", "")

            op_style = OP_BADGE_STYLES.get(op, UNKNOWN_OP_STYLE)
            op_color = op_style.color
            color_hex = op_color.name if op_color else "#888"

            widgets.append(Static(
                f"[bold $accent]Generated by:[/] [{color_hex} bold]{op}[/]"
                f"  [dim](group {group})[/]",
                classes="meta_field"))
            if agents:
                widgets.append(Static(
                    f"[bold $accent]Agents:[/] {', '.join(agents)}",
                    classes="meta_field"))
            if when:
                widgets.append(Static(
                    f"[bold $accent]When:[/] {when}",
                    classes="meta_field"))
            widgets.append(Static(
                "[dim]Press 'o' for operation details[/]",
                classes="meta_field"))

        dims = get_dimension_fields(node_data)
        grouped = group_dimensions_by_prefix(dims)
        if grouped:
            section_counts: dict[str, int] = {}
            try:
                proposal = read_proposal(self.session_path, node_id)
                parsed_proposal = parse_sections(proposal)
                for sec in parsed_proposal.sections:
                    # Expand each tag (exact or glob) against the node's real
                    # dimension keys, counting each section once per real key.
                    linked = {
                        k
                        for k in dims
                        for t in sec.dimensions
                        if dimension_matches_tag(k, t)
                    }
                    for k in linked:
                        section_counts[k] = section_counts.get(k, 0) + 1
            except Exception:
                pass

            widgets.append(Static(""))
            widgets.append(Static("[bold $accent]Dimensions:[/]"))
            widgets.append(Static(
                "[dim]space: expand/collapse · enter: jump to proposal[/]",
                classes="meta_field"))
            for _prefix, label, entries in grouped:
                widgets.append(Static(
                    f"[bold $accent]{label}[/]", classes="dim_subheader"))
                for suffix, value, full_key in entries:
                    widgets.append(DimensionRow(
                        suffix, str(value), full_key,
                        section_count=section_counts.get(full_key, 0),
                    ))

        return (f"Node: {node_id}", widgets)

    def _show_node_detail(self, node_id: str) -> None:
        """Update the Dashboard right pane with detail for the focused node."""
        self._current_focused_node_id = node_id
        title_text, widgets = self._render_node_detail_widgets(node_id)
        self.query_one("#dash_node_title", Label).update(title_text)
        container = self.query_one("#dash_node_info", Container)
        container.remove_children()
        for w in widgets:
            container.mount(w)

    def _show_dag_node_detail(self, node_id: str) -> None:
        """Update the Graph tab's inline detail pane for the focused DAG node."""
        self._current_focused_node_id = node_id
        title_text, widgets = self._render_node_detail_widgets(node_id)
        self.query_one("#dag_node_title", Label).update(title_text)
        container = self.query_one("#dag_node_info", Container)
        container.remove_children()
        for w in widgets:
            container.mount(w)

    def _show_brief_in_detail(self, spec: str) -> None:
        """Show the full initial_spec in the detail pane (press b to toggle)."""
        self.query_one("#dash_node_title", Label).update("Task Brief")
        self._current_focused_node_id = None
        container = self.query_one("#dash_node_info", Container)
        container.remove_children()
        # Truncate for the Static widget; full text is in n000_init proposal
        lines = spec.splitlines()
        if len(lines) > 30:
            preview = "\n".join(lines[:30]) + "\n\n… (truncated — see n000_init proposal for full text)"
        else:
            preview = spec
        container.mount(Static(preview))

    def on_dimension_row_activated(self, event: DimensionRow.Activated) -> None:
        """Enter on a DimensionRow → push SectionViewerScreen filtered to matching sections."""
        node_id = self._current_focused_node_id
        if not node_id:
            return
        try:
            proposal = read_proposal(self.session_path, node_id)
        except Exception:
            self.notify(
                "Could not read proposal for this node", severity="warning"
            )
            return
        parsed = parse_sections(proposal)
        matching = get_sections_for_dimension(parsed, event.dim_key)
        if not matching:
            self.notify(
                f"No proposal sections tagged with `{event.dim_key}`",
                severity="warning",
            )
            return
        # Land on the most-specific section (a nested subsection when present,
        # else the wrapper); keep the wrapper + leaf both in the minimap filter.
        best = best_section_for_dimension(parsed, event.dim_key)
        from section_viewer import SectionViewerScreen
        self.push_screen(SectionViewerScreen(
            proposal,
            title=f"Proposal: {node_id} — {event.dim_key}",
            section_filter=[s.name for s in matching],
            scroll_target=best.name if best else None,
        ))

    def on_descendant_focus(self, event) -> None:
        """When a NodeRow gets focus, update the detail pane. Track wizard node selection."""
        if isinstance(event.widget, NodeRow):
            self._show_node_detail(event.widget.node_id)
        if isinstance(event.widget, OperationRow):
            tabbed = self.query_one(TabbedContent)
            if tabbed.active == "tab_actions" and self._wizard_step_id == "node_select":
                if self._wizard_op in _NODE_SELECT_STEP_OPS:
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

    @on(DAGDisplay.NodeSelected)
    def on_dag_display_node_selected(self, event: DAGDisplay.NodeSelected) -> None:
        """Open node detail modal from DAG view."""
        self.push_screen(NodeDetailModal(event.node_id, self.session_path))

    @on(DAGDisplay.HeadChanged)
    def on_dag_display_head_changed(self, event: DAGDisplay.HeadChanged) -> None:
        """Update HEAD from DAG view."""
        if not self.read_only:
            set_head(self.session_path, event.node_id)
            self._populate_node_list()
            self._update_session_status()
            self._update_module_status()
            self.query_one(DAGDisplay).load_dag(self.session_path)

    @on(DAGDisplay.OperationOpened)
    def on_dag_display_operation_opened(
        self, event: DAGDisplay.OperationOpened
    ) -> None:
        """Open OperationDetailScreen from DAG view ('o' key)."""
        self.push_screen(
            OperationDetailScreen(event.group_name, self.session_path)
        )

    @on(DAGDisplay.ProposalRequested)
    def on_dag_display_proposal_requested(
        self, event: DAGDisplay.ProposalRequested
    ) -> None:
        """Open SectionViewerScreen with the focused node's proposal ('p' key)."""
        from section_viewer import SectionViewerScreen
        try:
            proposal = read_proposal(self.session_path, event.node_id)
        except Exception:
            self.notify(
                f"No proposal for {event.node_id}", severity="warning"
            )
            return
        self.push_screen(
            SectionViewerScreen(proposal, title=f"Proposal: {event.node_id}")
        )

    @on(DAGDisplay.PlanRequested)
    def on_dag_display_plan_requested(
        self, event: DAGDisplay.PlanRequested
    ) -> None:
        """Open SectionViewerScreen with the focused node's plan ('l' key)."""
        from section_viewer import SectionViewerScreen
        try:
            plan = read_plan(self.session_path, event.node_id)
        except Exception:
            plan = None
        if not plan or not plan.strip():
            self.notify(
                f"No plan generated for {event.node_id}", severity="warning"
            )
            return
        self.push_screen(
            SectionViewerScreen(plan, title=f"Plan: {event.node_id}")
        )

    @on(DAGDisplay.CompareRequested)
    async def on_dag_display_compare_requested(
        self, event: DAGDisplay.CompareRequested
    ) -> None:
        """Render Compare-tab matrix for [anchor, picked] and switch tabs."""
        # Shift focus off DAGDisplay first: DAGDisplay lives in tab_dag,
        # so if it remains focused while we activate tab_compare, Textual
        # auto-reverts the active tab to keep the focused widget visible
        # (manifests as "Compare flashes, then Graph comes back").
        tabbed = self.query_one(TabbedContent)
        try:
            tabbed.query_one(Tabs).focus()
        except Exception:
            pass
        tabbed.active = "tab_compare"
        # Pre-flush #compare_content so a previously-mounted #compare_table
        # is fully gone before _build_compare_matrix re-mounts. Otherwise
        # the second consecutive compare attempt fails with "id already
        # mounted" (remove_children is async; mount in the same sync tick
        # races the removal).
        container = self.query_one("#compare_content", VerticalScroll)
        await container.remove_children()
        try:
            self._build_compare_matrix(
                [event.anchor_id, event.picked_id]
            )
        except Exception as e:
            self.notify(
                f"Compare build failed: {e!s}",
                severity="error",
            )

    @on(DAGDisplay.FocusChanged)
    def on_dag_display_focus_changed(
        self, event: DAGDisplay.FocusChanged
    ) -> None:
        """Refresh the Graph tab's inline detail pane on focus change."""
        self._show_dag_node_detail(event.node_id)

    @on(DAGDisplay.TopBoundaryHit)
    def on_dag_display_top_boundary_hit(
        self, event: DAGDisplay.TopBoundaryHit
    ) -> None:
        """Refocus the tab row when Up is pressed at the top of the DAG."""
        try:
            tabs_widget = self.query_one(TabbedContent).query_one(Tabs)
        except Exception:
            return
        tabs_widget.focus()
        event.stop()

    @on(NodeRow.OperationOpened)
    def on_node_row_operation_opened(
        self, event: NodeRow.OperationOpened
    ) -> None:
        """Open OperationDetailScreen from dashboard NodeRow ('o' key)."""
        self.push_screen(
            OperationDetailScreen(event.group_name, self.session_path)
        )

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

        table = CompareDataTable(id="compare_table", cursor_type="row")
        table.add_column("Dimension", key="dim")
        for nid in selected_nodes:
            table.add_column(nid, key=nid)

        # Add dimension rows with color-coded values
        for key in all_keys:
            raw_values = [str(node_dims[nid].get(key, "\u2014")) for nid in selected_nodes]
            unique = set(raw_values)
            n = len(selected_nodes)

            if len(unique) == 1:
                # Equal values: collapse to a single visible value (DataTable
                # cannot span cells, so use a "\u2190 same" marker for n == 2).
                if n == 2:
                    styled = [
                        Text(raw_values[0], style="green"),
                        Text("\u2190 same", style="dim green"),
                    ]
                else:
                    styled = [Text(v, style="green") for v in raw_values]
                table.add_row(key, *styled, key=key)
                continue

            # Differing values
            if n == 2:
                v1, v2 = raw_values
                t1, t2 = word_diff_texts(
                    v1, v2,
                    TAG_STYLES["replace"], TAG_STYLES["replace"],
                    TAG_STYLES["replace_dim"], TAG_STYLES["replace_dim"],
                )
                table.add_row(key, t1, t2, key=key)
            else:
                max_sim = 0.0
                for i, x in enumerate(raw_values):
                    for y in raw_values[i + 1:]:
                        sim = SequenceMatcher(None, x, y).ratio()
                        if sim > max_sim:
                            max_sim = sim
                color = "yellow" if max_sim > 0.6 else "red"
                styled = [Text(v, style=color) for v in raw_values]
                table.add_row(key, *styled, key=key)

        # Add similarity score summary row
        self._add_similarity_row(table, selected_nodes, node_dims, all_keys)

        container.mount(table)
        self._compare_nodes = selected_nodes
        self.call_after_refresh(table.focus)

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
        self._wizard_op = ""
        self._wizard_config = {}
        self._wizard_has_sections = False
        self._cmp_section_checks = {}
        # Refresh the cached subgraph count for the selector predicate (one
        # disk read per wizard entry; _wizard_ctx then stays I/O-free).
        self._wizard_subgraph_count = len(list_subgraphs(self.session_path))
        self._wizard_subgraph = UMBRELLA_SUBGRAPH
        self._enter_wizard_step("op_select")

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()

        if self.read_only:
            container.mount(Label("[italic]Session is read-only. No operations available.[/]"))
            return

        container.mount(Label("Step 1 \u2014 Select Operation  (\u2191\u2193 Navigate  Enter Select  ? Help)", classes="actions_step_indicator"))

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

    def _focus_operation_row(self, op_key: str) -> None:
        """Focus the OperationRow matching ``op_key`` (fallback: first enabled).

        Used to pre-highlight a default choice (e.g. HEAD on the decompose
        source-node step); focusing the row drives ``on_descendant_focus`` to
        seed ``_selected_node`` and enable Next.
        """
        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab_actions":
            return
        try:
            rows = list(self.query("OperationRow"))
            for row in rows:
                if row.op_key == op_key and not row.op_disabled:
                    row.focus()
                    return
            for row in rows:
                if not row.op_disabled:
                    row.focus()
                    return
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

    def _mount_op_context_header(self, container: VerticalScroll) -> None:
        """Mount a one-line dim header showing op name + brief desc.

        Called from step 2 onwards so the user remembers which operation
        they're configuring. Full description stays in OperationHelpModal,
        reachable via the op-help shortcut.
        """
        info = _OP_LABELS.get(self._wizard_op)
        if not info:
            return
        label_text, desc = info
        help_key = resolve_key(self._shortcuts_scope, "op_help", "H") or "H"
        container.mount(
            Label(
                f"[dim]{label_text} — {desc}  ({help_key} for details)[/dim]",
                classes="actions_op_context",
            )
        )

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
        """Reset per-op wizard flags when an operation is chosen.

        The step count is now derived from the active step set (see
        ``step_position``), so this only resets the section cache that the
        predicates read. Kept as a named hook because op-select call-sites
        invoke it right after setting ``_wizard_op``.
        """
        self._wizard_has_sections = False
        self._cmp_section_checks = {}
        self._wizard_subgraph = UMBRELLA_SUBGRAPH
        # Clear the fast-track preset arm whenever a new op is selected; the
        # fast-track branch re-arms it after calling this. Keeps the preset's
        # link-to-task pre-check from bleeding into a later normal decompose.
        self._wizard_fast_track = False

    def _wizard_ctx(self) -> dict:
        """Context dict consumed by the pure step resolver (no I/O)."""
        return {
            "op": self._wizard_op,
            "node_has_sections": self._wizard_has_sections,
            "subgraph_count": self._wizard_subgraph_count,
        }

    def _enter_wizard_step(self, step_id: str) -> None:
        """Mark the current wizard step and derive its 'Step X of Y' numbers."""
        self._wizard_step_id = step_id
        self._wizard_step, self._wizard_total_steps = step_position(
            self._wizard_ctx(), step_id
        )

    def _render_wizard_step(self, step_id: str) -> None:
        """Render the wizard step with id ``step_id`` (back/next dispatch target)."""
        renderers = {
            "op_select": self._actions_show_step1,
            "subgraph_select": self._actions_show_subgraph_select,
            "node_select": self._actions_show_node_select,
            "section_select": self._actions_show_section_select,
            "config": self._actions_show_config,
            "confirm": self._actions_show_confirm,
        }
        renderer = renderers.get(step_id)
        if renderer is not None:
            renderer()

    def _actions_show_step2(self) -> None:
        """Render the step after op-select (resolver-driven).

        Routes to subgraph-select (multi-subgraph node-select ops), node-select
        (single-subgraph node-select ops), or config (compare/synthesize),
        whichever the active step set says comes next after op_select.
        """
        nxt = next_step_id(self._wizard_ctx(), "op_select")
        if nxt is not None:
            self._render_wizard_step(nxt)

    def _actions_show_subgraph_select(self) -> None:
        """Optional step: choose which module subgraph the op runs inside.

        Only rendered for subgraph-scoped ops in a 2+ subgraph session (see the
        ``subgraph_select`` predicate). Defaults the highlighted choice to the
        most-recently-touched subgraph. Mirrors op-select: Enter/click advances
        immediately (no Next button).
        """
        self._enter_wizard_step("subgraph_select")

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()

        container.mount(
            Label(
                f"Step {self._wizard_step} of {self._wizard_total_steps} "
                "— Select Subgraph  (↑↓ Navigate  Enter Select  Esc: Back)",
                classes="actions_step_indicator",
            )
        )
        self._mount_op_context_header(container)

        subgraphs = list_subgraphs(self.session_path)
        # Default selection = most-recently-touched subgraph (first in the list).
        if self._wizard_op == "module_merge":
            self._wizard_subgraph = next(
                (m for m in subgraphs if m != UMBRELLA_SUBGRAPH),
                UMBRELLA_SUBGRAPH,
            )
        else:
            self._wizard_subgraph = subgraphs[0] if subgraphs else UMBRELLA_SUBGRAPH
        for module in subgraphs:
            head = get_head(self.session_path, module=module)
            head_str = head or "(empty)"
            disabled = self._wizard_op == "module_merge" and module == UMBRELLA_SUBGRAPH
            container.mount(
                OperationRow(module, module, f"HEAD: {head_str}", disabled=disabled)
            )
        self.call_after_refresh(self._focus_first_operation)

    def _actions_show_node_select(self) -> None:
        """Step 2: dedicated node selection for explore/detail/patch."""
        self._wizard_config = {}
        self._enter_wizard_step("node_select")

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()

        total = self._wizard_total_steps
        desc_map = {
            "explore": "Select Base Node",
            "detail": "Select Node for Detailing",
            "patch": "Select Node to Patch",
            "module_decompose": "Select Source Node",
        }
        desc = desc_map.get(self._wizard_op, "Select Node")
        container.mount(
            Label(
                f"Step {self._wizard_step} of {total} \u2014 {desc}  (Esc: Back)",
                classes="actions_step_indicator",
            )
        )
        self._mount_op_context_header(container)
        container.mount(
            Label("[dim]  \u2191\u2193 Navigate  Enter Select  |  Click node + Next[/dim]")
        )

        # Scope candidates + HEAD to the selected subgraph (default _umbrella
        # \u2192 every node, identical to pre-module behaviour).
        subgraph = self._wizard_subgraph
        nodes = _nodes_for_subgraph(
            self.session_path, list_nodes(self.session_path), subgraph
        )
        head = get_head(self.session_path, module=subgraph)

        if not nodes:
            container.mount(
                Label("[bold yellow]No nodes available.[/] Initialize the session first.")
            )
            return

        for nid in nodes:
            node_data = read_node(self.session_path, nid)
            desc = node_data.get("description", "")
            has_plan = bool(node_data.get("plan_file"))

            lbl_parts = [nid]
            if nid == head:
                lbl_parts.append("[green]HEAD[/]")
            if has_plan:
                lbl_parts.append("[bold green]● has plan[/]")
            else:
                lbl_parts.append("[dim]○ no plan[/]")
            lbl = " ".join(lbl_parts)

            disabled = (self._wizard_op == "patch" and not has_plan)
            if disabled:
                desc = f"{desc}  [italic](patch unavailable)[/]"

            container.mount(OperationRow(nid, lbl, desc, disabled=disabled))

        container.mount(
            Button("Next \u25b6", variant="primary", classes="btn_actions_next", disabled=True)
        )
        # module_decompose defaults its source node to HEAD so the user can
        # advance immediately; explore/detail/patch require an explicit pick.
        # Focusing the HEAD row makes on_descendant_focus seed _selected_node
        # and enable Next (the same path explore uses for its first row).
        if self._wizard_op == "module_decompose" and head in nodes:
            self.call_after_refresh(lambda: self._focus_operation_row(head))
        else:
            self.call_after_refresh(self._focus_first_operation)

    def _actions_advance_from_node_select(self, node: str) -> bool:
        """Advance the wizard out of the node-select step for ``node``.

        Canonical logic shared by the Next button, keyboard Enter, and the
        NodeActionSelectModal callback. Returns False (after notifying) when
        the operation cannot proceed; True once the next step is rendered.
        """
        if not node:
            self.notify("Select a node first", severity="warning")
            return False
        if self._wizard_op == "patch" and not self._node_has_plan(node):
            self.notify(
                f"Node '{node}' has no plan — patch is only valid on "
                f"nodes that already have an implementation plan.",
                severity="error",
                timeout=6,
            )
            return False
        # Cache section presence into the ctx source BEFORE transitioning so the
        # step resolver sees it (else section_select would be skipped). This disk
        # read happens once here, never inside a per-render predicate. Only the
        # node-select ops have a section_select step; module_decompose reuses the
        # node-select UI but skips straight to config.
        if self._wizard_op in _NODE_SELECT_OPS:
            self._wizard_has_sections = self._node_has_sections(node)
            if self._wizard_has_sections:
                self._actions_show_section_select()
                return True
        if self._wizard_op == "detail":
            self._wizard_config["node"] = node
            self._actions_show_confirm()
        else:
            self._actions_show_config()
        return True

    def _actions_show_section_select(self) -> None:
        """Optional step (post node-select): pick sections to target."""
        node = self._wizard_config.get("_selected_node", "")
        secs = self._node_sections(node)

        # Mark sections present so the resolver counts this step, then derive
        # the indicator numbers from the active set.
        self._wizard_has_sections = True
        self._enter_wizard_step("section_select")

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()

        total = self._wizard_total_steps
        container.mount(
            Label(
                f"Step {self._wizard_step} of {total} \u2014 Select Sections for {node}  (Esc: Back)",
                classes="actions_step_indicator",
            )
        )
        self._mount_op_context_header(container)
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
        self._enter_wizard_step("config")

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
        self._mount_op_context_header(container)

        if op in ("compare", "synthesize"):
            container.mount(Label(
                "[dim]  ↑↓ Navigate  Space Toggle  "
                "Tab Switch group  Type to filter[/]"))

        if op == "explore":
            self._config_explore_no_node(container)
        elif op == "compare":
            self._config_compare(container)
        elif op == "synthesize":
            self._config_synthesize(container)
        elif op == "patch":
            self._config_patch_no_node(container)
        elif op == "module_decompose":
            self._config_module_decompose(container)
        elif op == "module_merge":
            self._config_module_merge(container)
        elif op == "module_sync":
            self._config_module_sync(container)

    def _focus_fcl_filter(self, fcl_id: str) -> None:
        """Focus the filter Input of a FuzzyCheckList by widget id."""
        try:
            fcl = self.query_one(f"#{fcl_id}", FuzzyCheckList)
            fcl.query_one(Input).focus()
        except Exception:
            pass

    # --- Side-by-side proposal preview (t945) ---------------------------------

    def _mount_config_with_preview(self, container, left_builder, proposal_text):
        """Lay out a config step as input-left / proposal-preview-right.

        *left_builder* receives the left ``VerticalScroll`` and mounts the op's
        own widgets into it verbatim, so the existing ``_actions_collect_config``
        collectors keep resolving them via the recursive ``#actions_content``
        query. The right :class:`ProposalPreviewPane` shows *proposal_text* with
        a navigable minimap. The pane adds no input widgets, so explore's
        single-match ``query_one(TextArea)`` / ``query_one(CycleField)`` stay
        unambiguous.
        """
        left = VerticalScroll(classes="config_preview_left")
        pane = ProposalPreviewPane(classes="config_preview_pane")
        split = Horizontal(left, pane, classes="config_preview_split")
        container.mount(split)
        self._preview_ratio = 0

        def _fill() -> None:
            left_builder(left)
            pane.populate(proposal_text)

        # Defer nested mounts until the split has settled (mirrors the
        # call_after_refresh pattern used by the compare/synthesize configs).
        self.call_after_refresh(_fill)

    def _apply_preview_ratio(self, left, pane, ratio: int) -> None:
        """Set the width split by swapping the ratio_* class on both panes.

        ratio 0 = balanced (50/50, no class), 1 = proposal-wide, 2 = input-wide.
        """
        ratio_classes = {1: "ratio_proposal_wide", 2: "ratio_input_wide"}
        for w in (left, pane):
            w.remove_class("ratio_proposal_wide")
            w.remove_class("ratio_input_wide")
        cls = ratio_classes.get(ratio)
        if cls:
            left.add_class(cls)
            pane.add_class(cls)

    def action_cycle_preview_ratio(self) -> None:
        """Cycle the config-step preview split: balanced → proposal → input."""
        from textual.actions import SkipAction
        panes = self.query(ProposalPreviewPane)
        splits = self.query(".config_preview_split")
        if not panes or not splits:
            raise SkipAction()
        pane = panes.first()
        lefts = splits.first().query(".config_preview_left")
        if not lefts:
            raise SkipAction()
        left = lefts.first()
        # Capture the current top line BEFORE the width reflow, then restore it.
        pane.on_ratio_change()
        self._preview_ratio = (getattr(self, "_preview_ratio", 0) + 1) % 3
        self._apply_preview_ratio(left, pane, self._preview_ratio)

    def on_section_minimap_section_selected(self, event) -> None:
        """Route an Actions-tab preview minimap selection to its pane.

        NodeDetailModal handles its own minimap (it is a separate ModalScreen);
        only the config-step preview pane's minimap bubbles up to the App. The
        ``preview_proposal_minimap`` class guards against any other source.
        """
        ctrl = getattr(event, "control", None)
        if ctrl is None or not ctrl.has_class("preview_proposal_minimap"):
            return
        panes = self.query(ProposalPreviewPane)
        if not panes:
            return
        panes.first().scroll_to_section(event.section_name)
        event.stop()

    def _preview_focus_ring(self) -> list:
        """Ordered Tab focus ring for the config-with-preview step.

        Left input widgets (each editbox/control in DOM order), then the section
        minimap (only when it is shown), then the scrollable proposal markdown
        pane. Returns ``[]`` when no preview pane is mounted (other Actions-tab
        steps fall back to their own / default Tab handling).
        """
        panes = self.query(ProposalPreviewPane)
        splits = self.query(".config_preview_split")
        if not panes or not splits:
            return []
        pane = panes.first()
        ring: list = []

        def _ancestor_in_ring(w) -> bool:
            p = w.parent
            while p is not None:
                if p in ring:
                    return True
                p = p.parent
            return False

        lefts = splits.first().query(".config_preview_left")
        if lefts:
            # Outermost focusable per control group (e.g. the RadioSet, not its
            # individual RadioButtons), in DOM order.
            for w in lefts.first().query("*"):
                if not (w.can_focus and w.display and not w.disabled):
                    continue
                if _ancestor_in_ring(w):
                    continue
                ring.append(w)
        minimaps = list(pane.query(".preview_proposal_minimap"))
        if minimaps and minimaps[0].display:
            ring.append(minimaps[0])
        contents = list(pane.query("#preview_proposal_content"))
        if contents:
            ring.append(contents[0])
        return ring

    def _cycle_preview_focus(self, forward: bool = True) -> bool:
        """Tab / Shift+Tab on the config-with-preview step → step the focus ring.

        Cycles editboxes → minimap → proposal pane → wrap, so the proposal
        markdown is reachable (and scrollable) by Tab alongside the inputs and
        the minimap. Returns True when focus was moved (caller stops the event);
        False when there is no preview pane (default Tab traversal runs).
        """
        ring = self._preview_focus_ring()
        if not ring:
            return False
        focused = self.screen.focused
        cur = -1
        for i, member in enumerate(ring):
            if focused is member or (
                focused is not None and focused in member.walk_children()
            ):
                cur = i
                break
        if cur == -1:
            target = ring[0]
        else:
            target = ring[(cur + (1 if forward else -1)) % len(ring)]
        minimaps = list(self.query(".preview_proposal_minimap"))
        if minimaps and target is minimaps[0]:
            target.focus_first_row()
        else:
            target.focus()
        return True

    def _config_explore_no_node(self, container: VerticalScroll) -> None:
        """Explore config (node already selected): mandate, parallel count.

        Lays out input-left / proposal-preview-right via the shared
        :meth:`_mount_config_with_preview` helper (t945_1) so the selected base
        node's proposal is visible beside the Exploration Mandate input.
        """
        node_id = self._wizard_config.get("_selected_node", "?")
        try:
            proposal = read_proposal(self.session_path, node_id)
        except Exception:
            proposal = "*No proposal found.*"

        def left_builder(left: VerticalScroll) -> None:
            left.mount(Label(f"[bold]Base Node:[/] {node_id}"))
            left.mount(Label("[bold]Exploration Mandate[/]"))
            left.mount(TextArea(""))
            left.mount(CycleField("Parallel explorers", ["1", "2", "3", "4"], initial="2"))
            left.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))

        self._mount_config_with_preview(container, left_builder, proposal)

    def _config_compare(self, container: VerticalScroll) -> None:
        """Compare config: multi-node checkboxes + dimension checkboxes + sections."""
        nodes = list_nodes(self.session_path)

        container.mount(Label("[bold]Select Nodes to Compare (2+)[/]"))
        container.mount(FuzzyCheckList(
            nodes, item_class="chk_node",
            placeholder="Type to filter nodes\u2026", id="cmp_nodes"))

        container.mount(Label("[bold]Dimensions[/]"))
        # Mounted empty; _refresh_compare_dimensions populates it scoped to the
        # checked nodes (grouped, descriptive, active-default) once nodes are
        # selected. Keeping the FuzzyCheckList present preserves its filter
        # Input + the cmp_dims Tab-nav group even before any node is checked.
        container.mount(FuzzyCheckList(
            [], item_class="chk_dim",
            placeholder="Type to filter dimensions\u2026", id="cmp_dims"))

        container.mount(Label("[bold]Target Sections (optional)[/]", id="cmp_sections_label"))
        container.mount(Container(id="cmp_sections_box"))

        container.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))

        self._cmp_section_checks = {}
        self._cmp_dim_checks = {}
        self.call_after_refresh(self._refresh_compare_sections)
        self.call_after_refresh(self._refresh_compare_dimensions)
        self.call_after_refresh(lambda: self._focus_fcl_filter("cmp_nodes"))

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

    def _refresh_compare_dimensions(self) -> None:
        """(Re)mount compare dimension checkboxes scoped to the checked nodes.

        Mirrors ``_refresh_compare_sections``: preserves prior toggles across
        node-selection changes, scopes the dimension list to the union of the
        checked nodes' dimensions (grouped by prefix under subheaders),
        default-checks the session's ``active_dimensions`` (falling back to
        all-checked when none), and labels each row ``"<full_key> — <value>"``
        so the dimension's meaning is visible.
        """
        try:
            fcl = self.query_one("#cmp_dims", FuzzyCheckList)
        except Exception:
            return

        # Preserve current toggles across node-selection changes.
        for cb in fcl.query("Checkbox.chk_dim"):
            self._cmp_dim_checks[_parse_dimension_label(str(cb.label))] = bool(cb.value)

        checked_nodes = [
            str(cb.label) for cb in self.query("Checkbox.chk_node") if cb.value
        ]
        if not checked_nodes:
            fcl.set_grouped_items([])
            return

        grouped = self._dimension_entries_for_nodes(checked_nodes)
        active = set(get_active_dimensions(self.session_path))
        groups: list[tuple[str, list[tuple[str, bool]]]] = []
        for _prefix, label, entries in grouped:
            rows: list[tuple[str, bool]] = []
            for _suffix, value, full_key in entries:
                v = str(value)
                trunc = v if len(v) <= 60 else v[:57] + "…"
                if full_key in self._cmp_dim_checks:
                    checked = self._cmp_dim_checks[full_key]
                elif active:
                    checked = full_key in active
                else:
                    checked = True  # fallback = old default_checked=True
                rows.append((f"{full_key} — {trunc}", checked))
            groups.append((label, rows))
        fcl.set_grouped_items(groups)

    def _config_synthesize(self, container: VerticalScroll) -> None:
        """Synthesize config: multi-node checkboxes + merge rules."""
        nodes = list_nodes(self.session_path)

        container.mount(Label("[bold]Select Source Nodes (2+)[/]"))
        container.mount(FuzzyCheckList(
            nodes, item_class="chk_node",
            placeholder="Type to filter nodes\u2026", id="syn_nodes"))

        container.mount(Label("[bold]Merge Rules[/]"))
        container.mount(TextArea(""))
        container.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))
        self.call_after_refresh(lambda: self._focus_fcl_filter("syn_nodes"))

    def _config_patch_no_node(self, container: VerticalScroll) -> None:
        """Patch config (node already selected): patch request."""
        node_id = self._wizard_config.get("_selected_node", "?")
        container.mount(Label(f"[bold]Node:[/] {node_id}"))
        container.mount(
            Label("[bold]Patch Request[/] \u2014 describe the change to apply to this node")
        )
        container.mount(
            Label("[dim]Type your patch request in the text area below.[/]")
        )
        container.mount(TextArea("", classes="ta_patch_request"))
        container.mount(
            Button(
                "Next \u25b6",
                variant="primary",
                classes="btn_actions_next",
                disabled=True,
            )
        )

    def _config_module_decompose(self, container: VerticalScroll) -> None:
        """Module decompose config: module list + extraction options.

        When entered via the "Fast-track this module" preset
        (``_wizard_fast_track``, t756_6 UC-3), the link-to-task checkbox is
        pre-armed so naming one module + confirm creates the subgraph root and
        the linked aitask in a single pass. The op, config-collection, confirm,
        and execute paths are otherwise identical to the multi-module flow.

        Lays out input-left / proposal-preview-right via the shared
        :meth:`_mount_config_with_preview` helper (t945_1) so the chosen source
        node's proposal is visible beside the Decomposition Plan input.
        """
        fast_track = getattr(self, "_wizard_fast_track", False)
        # Source node: the user's pick on the source-node step, else subgraph
        # HEAD (express entry paths skip node-select).
        node_id = self._wizard_config.get("_selected_node") or get_head(
            self.session_path, module=self._wizard_subgraph
        )
        try:
            proposal = (
                read_proposal(self.session_path, node_id)
                if node_id else "*No proposal found.*"
            )
        except Exception:
            proposal = "*No proposal found.*"

        def left_builder(left: VerticalScroll) -> None:
            if fast_track:
                left.mount(Label(
                    "[dim]Fast-track: name one module — a linked aitask is "
                    "created in one pass.[/]"
                ))
            left.mount(Label(f"[bold]Source Subgraph:[/] {self._wizard_subgraph}"))
            left.mount(Label(f"[bold]Source Node:[/] {node_id or '(none)'}"))
            left.mount(Label("[bold]Decompose mode[/]"))
            left.mount(RadioSet(
                RadioButton("Manual — I type the names", value=True),
                RadioButton("Agent-proposed — infer from the Plan"),
                RadioButton("From section markers"),
                classes="rs_decompose_mode",
            ))
            left.mount(Label("[bold]Modules (used by Manual / From-sections)[/]"))
            left.mount(TextArea("", classes="ta_module_decompose_modules"))
            link_chk = Checkbox("Create linked child tasks", classes="chk_link_to_task")
            link_chk.value = bool(fast_track)
            left.mount(link_chk)
            left.mount(Label("[bold]Decomposition Plan (optional)[/]"))
            left.mount(TextArea("", classes="ta_module_decompose_plan"))
            review_chk = Checkbox(
                "Review before apply", classes="chk_review_before_apply"
            )
            review_chk.value = True
            left.mount(review_chk)
            left.mount(Button("Next \u25b6", variant="primary", classes="btn_actions_next"))

        self._mount_config_with_preview(container, left_builder, proposal)

    def _ancestor_subgraphs(self, source: str) -> list[str]:
        return [
            module for module in list_subgraphs(self.session_path)
            if module != source
            and is_ancestor_subgraph(self.session_path, source, module)
        ]

    def _config_module_merge(self, container: VerticalScroll) -> None:
        """Module merge config: ancestor destination + merge-up rules."""
        source = self._wizard_subgraph
        ancestors = self._ancestor_subgraphs(source)
        source_head = get_head(self.session_path, module=source)
        container.mount(Label(f"[bold]Source Subgraph:[/] {source}"))
        container.mount(Label(f"[bold]Source HEAD:[/] {source_head or '(none)'}"))
        if not ancestors:
            container.mount(
                Label("[bold yellow]No ancestor destination is available for this source.[/]")
            )
        else:
            container.mount(
                CycleField(
                    "Destination subgraph",
                    ancestors,
                    initial=ancestors[0],
                    id="cf_module_merge_destination",
                )
            )
        container.mount(Label("[bold]Merge-Up Rules[/]"))
        container.mount(TextArea("", classes="ta_module_merge_rules"))
        container.mount(
            Button(
                "Next \u25b6",
                variant="primary",
                classes="btn_actions_next",
                disabled=not bool(ancestors),
            )
        )

    def _config_module_sync(self, container: VerticalScroll) -> None:
        """Module sync config: requires a linked task; surface scan horizon."""
        module = self._wizard_subgraph
        gs = _read_graph_state(self.session_path)
        tasks = gs.get("module_tasks")
        tasks = tasks if isinstance(tasks, dict) else {}
        linked = tasks.get(module)
        synced = gs.get("last_synced_at")
        synced = synced if isinstance(synced, dict) else {}
        last = synced.get(module) or "(never)"
        source_head = get_head(self.session_path, module=module)
        container.mount(Label(f"[bold]Module Subgraph:[/] {module}"))
        container.mount(Label(f"[bold]Source HEAD:[/] {source_head or '(none)'}"))
        if not linked:
            container.mount(
                Label(
                    "[bold yellow]This module has no linked task (module_tasks). "
                    "Sync requires one \u2014 use Patch for free-form context.[/]"
                )
            )
        else:
            container.mount(Label(f"[bold]Linked Task:[/] t{linked}"))
            container.mount(Label(f"[bold]Last Synced:[/] {last}"))
            container.mount(Label("[bold]Sync Instructions (optional)[/]"))
            container.mount(TextArea("", classes="ta_module_sync_instructions"))
        container.mount(
            Button(
                "Next \u25b6",
                variant="primary",
                classes="btn_actions_next",
                disabled=not bool(linked) or not bool(source_head),
            )
        )

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

    def _dimension_entries_for_nodes(self, node_ids):
        """Union of the given nodes' dimensions, grouped by prefix.

        Returns ``group_dimensions_by_prefix`` output:
        ``[(prefix, label, [(suffix, value, full_key)])]``. **Union, not
        intersection** — a dimension present on only one selected node is still
        a valid comparison axis, and intersection risks an empty list when
        nodes carry divergent dimension sets. Scoped to the *selected* nodes,
        it still shrinks far below the whole-graph key set.
        """
        merged: dict[str, str] = {}
        for nid in node_ids:
            try:
                data = read_node(self.session_path, nid)
            except Exception:
                continue
            for k, v in extract_dimensions(data).items():
                merged.setdefault(k, str(v))
        return group_dimensions_by_prefix(merged)

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

    def _node_has_plan(self, node_id: str) -> bool:
        """Return True if the node has a plan_file set in its YAML."""
        try:
            data = read_node(self.session_path, node_id)
        except Exception:
            return False
        return bool(data.get("plan_file"))

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
            config["dimensions"] = [
                _parse_dimension_label(str(cb.label))
                for cb in dim_cbs if cb.value
            ]
            try:
                box = self.query_one("#cmp_sections_box", Container)
                sec_cbs = box.query("Checkbox.chk_section")
                sel_secs = [str(cb.label) for cb in sec_cbs if cb.value]
                config["target_sections"] = sel_secs or None
            except Exception:
                config["target_sections"] = None

        elif op == "synthesize":
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

        elif op == "module_decompose":
            config["subgraph"] = self._wizard_subgraph
            # Use the node chosen on the source-node step, falling back to the
            # subgraph HEAD (express entry paths skip node-select).
            config["source_node"] = selected_node or get_head(
                self.session_path, module=self._wizard_subgraph
            )
            if not config["source_node"]:
                self.notify("Selected subgraph has no HEAD", severity="warning")
                return False
            # Decompose mode: 0=Manual, 1=Agent-proposed (infer), 2=From sections.
            mode = container.query_one(
                ".rs_decompose_mode", RadioSet
            ).pressed_index
            module_text = container.query_one(
                ".ta_module_decompose_modules", TextArea
            ).text
            modules = [
                m.strip()
                for m in re.split(r"[,\n]+", module_text)
                if m.strip()
            ]
            instructions = container.query_one(
                ".ta_module_decompose_plan", TextArea
            ).text.strip()
            if mode == 1:
                # Infer: the agent proposes the module set; names field is
                # ignored, but a Decomposition Plan is required to infer from.
                if not instructions:
                    self.notify(
                        "Agent-proposed mode needs a Decomposition Plan "
                        "to infer from",
                        severity="warning",
                    )
                    return False
                modules = []
            else:
                if not modules:
                    self.notify("Enter at least one module name", severity="warning")
                    return False
                if len(set(modules)) != len(modules):
                    self.notify("Module names must be unique", severity="warning")
                    return False
            config["modules"] = modules
            config["from_sections"] = (mode == 2)
            config["link_to_task"] = bool(
                container.query_one(".chk_link_to_task", Checkbox).value
            )
            config["instructions"] = instructions
            try:
                config["review_before_apply"] = bool(
                    container.query_one(".chk_review_before_apply", Checkbox).value
                )
            except Exception:
                config["review_before_apply"] = True

        elif op == "module_merge":
            config["source_subgraph"] = self._wizard_subgraph
            try:
                dest = container.query_one(
                    "#cf_module_merge_destination", CycleField
                ).current_value
            except Exception:
                dest = ""
            if not dest:
                self.notify("No ancestor destination available", severity="warning")
                return False
            if not is_ancestor_subgraph(self.session_path, self._wizard_subgraph, dest):
                self.notify("Destination is not an ancestor", severity="warning")
                return False
            config["destination_subgraph"] = dest
            config["merge_rules"] = container.query_one(
                ".ta_module_merge_rules", TextArea
            ).text.strip()
            if not config["merge_rules"]:
                self.notify("Merge-up rules cannot be empty", severity="warning")
                return False

        elif op == "module_sync":
            module = self._wizard_subgraph
            config["subgraph"] = module
            gs = _read_graph_state(self.session_path)
            tasks = gs.get("module_tasks")
            tasks = tasks if isinstance(tasks, dict) else {}
            if not tasks.get(module):
                self.notify(
                    "Module has no linked task — sync requires one",
                    severity="warning",
                )
                return False
            try:
                config["instructions"] = container.query_one(
                    ".ta_module_sync_instructions", TextArea
                ).text.strip()
            except Exception:
                config["instructions"] = ""

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
        self._enter_wizard_step("confirm")
        total = self._wizard_total_steps
        step = self._wizard_step

        container = self.query_one("#actions_content", VerticalScroll)
        container.remove_children()
        container.mount(Label(f"Step {step} of {total} \u2014 Confirm  (Esc: Back)", classes="actions_step_indicator"))
        self._mount_op_context_header(container)

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
        elif op == "synthesize":
            lines.append(f"[bold]Source Nodes:[/] {', '.join(cfg['nodes'])}")
            lines.append("[bold]Merge Rules:[/]")
            lines.append(cfg["merge_rules"])
        elif op == "detail":
            lines.append(f"[bold]Node:[/] {cfg['node']}")
        elif op == "patch":
            lines.append(f"[bold]Node:[/] {cfg['node']}")
            lines.append("[bold]Patch Request:[/]")
            lines.append(cfg["patch_request"])
        elif op == "module_decompose":
            lines.append(f"[bold]Source Subgraph:[/] {cfg['subgraph']}")
            lines.append(f"[bold]Source HEAD:[/] {cfg['source_node']}")
            lines.append(f"[bold]Modules:[/] {', '.join(cfg['modules'])}")
            lines.append(
                f"[bold]From Sections:[/] {str(cfg['from_sections']).lower()}"
            )
            lines.append(
                f"[bold]Link To Task:[/] {str(cfg['link_to_task']).lower()}"
            )
            if cfg.get("instructions"):
                lines.append("[bold]Decomposition Plan:[/]")
                lines.append(cfg["instructions"])
        elif op == "module_merge":
            lines.append(f"[bold]Source Subgraph:[/] {cfg['source_subgraph']}")
            lines.append(
                f"[bold]Destination Subgraph:[/] {cfg['destination_subgraph']}"
            )
            lines.append("[bold]Merge-Up Rules:[/]")
            lines.append(cfg["merge_rules"])
        elif op == "module_sync":
            module = cfg["subgraph"]
            gs = _read_graph_state(self.session_path)
            tasks = gs.get("module_tasks")
            tasks = tasks if isinstance(tasks, dict) else {}
            synced = gs.get("last_synced_at")
            synced = synced if isinstance(synced, dict) else {}
            lines.append(f"[bold]Module Subgraph:[/] {module}")
            lines.append(f"[bold]Linked Task:[/] t{tasks.get(module, '?')}")
            lines.append(f"[bold]Last Synced:[/] {synced.get(module) or '(never)'}")
            if cfg.get("instructions"):
                lines.append("[bold]Sync Instructions:[/]")
                lines.append(cfg["instructions"])
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
        """Re-render compare section + dimension checkboxes on node-selection change."""
        if self._wizard_op != "compare":
            return
        self._refresh_compare_sections()
        self._refresh_compare_dimensions()

    @on(Button.Pressed, ".btn_actions_launch")
    def _on_actions_launch(self) -> None:
        """Handle Launch/Confirm button press in step 3."""
        if self._wizard_op in ("pause", "resume", "finalize", "archive"):
            self._execute_session_op()
        else:
            self._execute_design_op()

    @on(Button.Pressed, ".btn_actions_back")
    def _on_actions_back(self) -> None:
        """Handle Back button (confirm step) — go to the previous active step."""
        prev = prev_step_id(self._wizard_ctx(), self._wizard_step_id)
        if prev is not None:
            self._render_wizard_step(prev)

    @on(Button.Pressed, ".btn_actions_next")
    def _on_actions_next(self) -> None:
        """Handle Next button — dispatch by the current step id."""
        if self._wizard_step_id == "node_select":
            # Guarded advance (patch-no-plan guard, section/config/confirm routing).
            self._actions_advance_from_node_select(
                self._wizard_config.get("_selected_node", "")
            )
        elif self._wizard_step_id == "section_select":
            # Collect sections, then go to config (explore/patch) or confirm (detail).
            self._collect_target_sections()
            if self._wizard_op == "detail":
                self._wizard_config["node"] = self._wizard_config.get("_selected_node", "")
                self._actions_show_confirm()
            else:
                self._actions_show_config()
        elif self._wizard_step_id == "config":
            if self._actions_collect_config():
                self._actions_show_confirm()

    @on(TextArea.Changed, ".ta_patch_request")
    def _on_patch_request_changed(self, event: TextArea.Changed) -> None:
        """Enable Next button only when the patch request TextArea is non-empty."""
        has_text = bool(event.text_area.text.strip())
        try:
            self.query_one(".btn_actions_next", Button).disabled = not has_text
        except Exception:
            pass

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
        if self._wizard_step_id == "op_select":
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
        elif self._wizard_step_id == "subgraph_select":
            # Mirror op-select: clicking a subgraph chooses it and advances.
            self._wizard_subgraph = row.op_key
            nxt = next_step_id(self._wizard_ctx(), "subgraph_select")
            if nxt is not None:
                self._render_wizard_step(nxt)
        elif self._wizard_step_id == "node_select" and self._wizard_op in _NODE_SELECT_STEP_OPS:
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
        # Scope the op to a subgraph: node-select ops use the selector's choice;
        # compare/synthesize (no selector) derive it from their first input node.
        if op == "module_merge":
            subgraph = cfg.get("destination_subgraph", UMBRELLA_SUBGRAPH)
            head_at_creation = get_head(
                self.session_path,
                module=cfg.get("source_subgraph", UMBRELLA_SUBGRAPH),
            )
        elif op in _SUBGRAPH_SELECT_OPS:
            subgraph = self._wizard_subgraph
            head_at_creation = get_head(self.session_path, module=subgraph)
        else:
            input_nodes = cfg.get("nodes") or []
            subgraph = (
                _node_module(self.session_path, input_nodes[0])
                if input_nodes else UMBRELLA_SUBGRAPH
            )
            head_at_creation = get_head(self.session_path, module=subgraph)
        agents_list: list[str] = []
        operation_extra: dict = {}

        try:
            if op == "explore":
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
                    agents_list.append(agent)
                    # Track each explorer so the auto-apply poller will
                    # ingest its output when the agent completes.
                    self.call_from_thread(
                        self._register_explorer_agent, agent,
                    )
                msg = f"Registered {len(agents_list)} explorer(s): {', '.join(agents_list)}"
            elif op == "compare":
                agent = register_comparator(
                    self.session_path, crew_id, cfg["nodes"],
                    cfg["dimensions"], group_name,
                    launch_mode=launch_mode,
                    target_sections=target_sections,
                )
                agents_list.append(agent)
                msg = f"Registered comparator: {agent}"
            elif op == "synthesize":
                agent = register_synthesizer(
                    self.session_path, crew_id, cfg["nodes"],
                    cfg["merge_rules"], group_name,
                    launch_mode=launch_mode,
                )
                agents_list.append(agent)
                # Track the synthesizer so the auto-apply poller will
                # ingest its output when the agent completes.
                self.call_from_thread(
                    self._register_synthesizer_agent, agent,
                )
                msg = f"Registered synthesizer: {agent}"
            elif op == "detail":
                agent = register_detailer(
                    self.session_path, crew_id, cfg["node"],
                    ["."], group_name,
                    launch_mode=launch_mode,
                    target_sections=target_sections,
                )
                agents_list.append(agent)
                # Track the target node so the auto-apply poller can pass it
                # to apply_detailer_output when the agent completes.
                self.call_from_thread(
                    self._register_detailer_target, agent, cfg["node"],
                )
                msg = f"Registered detailer: {agent}"
            elif op == "patch":
                agent = register_patcher(
                    self.session_path, crew_id, cfg["node"],
                    cfg["patch_request"], group_name,
                    launch_mode=launch_mode,
                    target_sections=target_sections,
                )
                agents_list.append(agent)
                # Track source node so the auto-apply poller can pass it
                # to apply_patcher_output when the agent completes.
                self.call_from_thread(
                    self._register_patcher_source, agent, cfg["node"],
                )
                msg = f"Registered patcher: {agent}"
            elif op == "module_decompose":
                operation_extra = {
                    "modules": cfg["modules"],
                    "from_sections": cfg["from_sections"],
                    "link_to_task": cfg["link_to_task"],
                    "source_subgraph": cfg["subgraph"],
                    # Persisted so the review gate / re-run (t929_1) survive a
                    # TUI reload — the poller reads review_before_apply, and the
                    # Re-run path replays modules/instructions/launch_mode.
                    "review_before_apply": cfg.get("review_before_apply", True),
                    "instructions": cfg.get("instructions", ""),
                    "launch_mode": launch_mode,
                }
                if cfg["from_sections"]:
                    from brainstorm.brainstorm_session import (
                        apply_module_decompose_from_sections,
                    )
                    record_operation(
                        self.task_num,
                        group_name=group_name,
                        operation=op,
                        agents=[],
                        head_at_creation=head_at_creation,
                        subgraph=subgraph,
                        **operation_extra,
                    )
                    created = apply_module_decompose_from_sections(
                        self.task_num, group_name
                    )
                    msg = "Created module roots from sections: " + ", ".join(created)
                else:
                    agent = register_module_decomposer(
                        self.session_path,
                        crew_id,
                        cfg["source_node"],
                        cfg["modules"],
                        group_name,
                        from_sections=cfg["from_sections"],
                        link_to_task=cfg["link_to_task"],
                        instructions=cfg.get("instructions", ""),
                        launch_mode=launch_mode,
                    )
                    agents_list.append(agent)
                    self.call_from_thread(self._register_module_agent, agent)
                    msg = f"Registered module decomposer: {agent}"
            elif op == "module_merge":
                agent = register_module_merger(
                    self.session_path,
                    crew_id,
                    cfg["source_subgraph"],
                    cfg["destination_subgraph"],
                    cfg["merge_rules"],
                    group_name,
                    launch_mode=launch_mode,
                )
                agents_list.append(agent)
                self.call_from_thread(self._register_module_agent, agent)
                operation_extra = {
                    "source_subgraph": cfg["source_subgraph"],
                    "destination_subgraph": cfg["destination_subgraph"],
                }
                msg = f"Registered module merger: {agent}"
            elif op == "module_sync":
                agent = register_module_syncer(
                    self.session_path,
                    crew_id,
                    cfg["subgraph"],
                    group_name,
                    instructions=cfg.get("instructions", ""),
                    launch_mode=launch_mode,
                )
                agents_list.append(agent)
                self.call_from_thread(self._register_module_agent, agent)
                msg = f"Registered module syncer: {agent}"
            else:
                msg = f"Unknown operation: {op}"
                agents_list = []

            if agents_list:
                record_operation(
                    self.task_num,
                    group_name=group_name,
                    operation=op,
                    agents=agents_list,
                    head_at_creation=head_at_creation,
                    subgraph=subgraph,
                    **operation_extra,
                )

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
        try:
            self.query_one("#initializer_polling_indicator", PollingIndicator).start()
        except Exception:
            pass
        self._initializer_timer = self.set_interval(2, self._poll_initializer)

    def _poll_initializer(self) -> None:
        """Timer tick: check status file, apply initializer output on Completed."""
        if self._initializer_done or self._initializer_agent is None:
            return
        try:
            self.query_one("#initializer_polling_indicator", PollingIndicator).flash()
        except Exception:
            pass
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
                self.query_one("#initializer_polling_indicator", PollingIndicator).stop()
            except Exception:
                pass
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
