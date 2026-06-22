"""Brainstorm TUI: shared constants and pure data tables."""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from pathlib import Path
from typing import (
    Callable,
    NamedTuple,
)
from launch_modes import DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES

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


RUNNER_STATE_DISPLAY = {
    "none":    ("No runner",      "#888888"),
    "stopped": ("Runner stopped", "#888888"),
    "stale":   ("Runner stale",   "#FF5555"),
    "active":  ("Runner active",  "#50FA7B"),
}


_TERMINAL_AGENT_STATES = {"Error", "Aborted", "Completed"}


_NODE_SELECT_OPS = {"explore"}


_NODE_SELECT_STEP_OPS = _NODE_SELECT_OPS | {"module_decompose"}


_SUBGRAPH_SELECT_OPS = _NODE_SELECT_OPS | {
    "module_decompose", "module_merge", "module_sync",
}


_WIZARD_OP_TO_AGENT_TYPE = {
    "explore": "explorer",
    "compare": "comparator",
    "synthesize": "synthesizer",
    "module_decompose": "module_decomposer",
    "module_merge": "module_merger",
    "module_sync": "module_syncer",
}


_DESIGN_OPS = [
    ("explore", "Explore", "Create new design variants from a base node"),
    ("compare", "Compare", "Run agent comparison across nodes"),
    ("synthesize", "Synthesize", "Merge multiple nodes into a synthesis"),
    ("module_decompose", "Module Decompose", "Fork module subgraph roots"),
    ("module_merge", "Module Merge", "Merge a module up into an ancestor"),
    ("module_sync", "Module Sync", "Pull a linked module's as-implemented design back in"),
]


_SESSION_OPS = [
    ("pause", "Pause", "Pause the active session"),
    ("resume", "Resume", "Resume a paused session"),
    ("finalize", "Finalize", "Export HEAD proposal to aiplans/ and mark completed"),
    ("archive", "Archive", "Mark completed session as archived"),
    ("delete", "Delete", "Permanently delete session, worktree, and branch"),
]


_OP_LABELS: dict[str, tuple[str, str]] = {
    op_key: (label, desc) for op_key, label, desc in (_DESIGN_OPS + _SESSION_OPS)
}


_OPERATION_HELP: dict[str, dict] = {
    # Source: .aitask-scripts/brainstorm/templates/explorer.md
    # I/O contract derived from "## Input" (reads parent YAML metadata,
    # proposal markdown, reference files) and "## Output" (produces a new
    # node: YAML metadata + proposal markdown).
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
            "Reference files cited by the base node.",
        ],
        "produces": [
            "A new node with `parents = [base_node]`.",
            "A new YAML metadata file (description, dimensions, "
            "reference_files, created_by_group).",
            "A new proposal markdown.",
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
        ],
        "use_cases": [
            "Combine the data layer from one variant with the API layer "
            "from another into a unified design.",
            "Resolve component-level tradeoffs across siblings into a "
            "single proposal.",
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
    # Source: brainstorm_session.finalize_session — exports the HEAD node's
    # proposal into aiplans/ and marks the session `completed`. Requires HEAD
    # to be set; blocks if a fast-tracked module is in implementation but
    # not yet synced.
    "finalize": {
        "title": "Finalize — Session Lifecycle",
        "summary": (
            "Export the HEAD node's proposal into aiplans/ and "
            "mark the session `completed`. Requires the session to be "
            "`active` with a HEAD; blocked while a fast-tracked module is "
            "in implementation but not yet synced."
        ),
        "use_cases": [
            "Promote the chosen design's proposal to the project's canonical "
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


NODE_HUB_OPERATIONS = "operations"


NODE_HUB_COMPARE = "compare"  # t983_7: open the dimension-matrix overlay


class NodeHubResult(NamedTuple):
    """Typed result a :class:`NodeHub` dismisses with: ``action`` is one of the
    ``NODE_HUB_*`` verbs, ``node_id`` is the Hub's node."""

    action: str
    node_id: str


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
    # Skipped when the launch already supplied the node contextually (t983_6):
    # contextual ops (Operations dialog / Node Hub) seed the selection, so the
    # in-wizard node-pick step is redundant. Kept (gated, not deleted) so the
    # non-seeded op-select flow + its unit tests stay valid.
    _WizardStep(
        "node_select",
        lambda c: c.get("op") in _NODE_SELECT_STEP_OPS
        and not c.get("pre_seeded_node"),
        True,
    ),
    _WizardStep(
        "section_select",
        lambda c: c.get("op") in _NODE_SELECT_OPS and bool(c.get("node_has_sections")),
        False,
    ),
    _WizardStep(
        "config",
        lambda c: c.get("op") in (
            "explore",
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


BROWSE_DEFAULT_VIEW = "graph"


BROWSE_VIEWS = ("graph", "list")


BROWSE_VIEW_TO_PANE = {"graph": "dag_content", "list": "node_list_pane"}


BROWSE_PANE_TO_VIEW = {pane: view for view, pane in BROWSE_VIEW_TO_PANE.items()}


_SINGLE_NODE_OPS = ("explore", "fast_track", "delete")


_MODULE_OPS = ("module_decompose", "module_merge", "module_sync")


_MULTI_NODE_OPS = ("compare", "synthesize")


_SINGLE_NODE_REASON = "select a single node"


_MULTI_NODE_REASON = "mark 2+ nodes"


_ROOT_DELETE_REASON = "cannot delete the root design"

