"""DAG operations for the brainstorm engine design space.

All functions take a session_path (Path to the crew worktree, e.g.
.aitask-crews/crew-brainstorm-419/) and operate on br_nodes/, br_proposals/,
br_plans/, and br_graph_state.yaml within it.

Reuses YAML I/O from agentcrew_utils to avoid duplication.
"""

from __future__ import annotations

import os
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

# Allow importing agentcrew_utils from sibling package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentcrew.agentcrew_utils import read_yaml, write_yaml  # noqa: E402

NODES_DIR = "br_nodes"
PROPOSALS_DIR = "br_proposals"
PLANS_DIR = "br_plans"
GRAPH_STATE_FILE = "br_graph_state.yaml"


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------


def create_node(
    session_path: Path,
    node_id: str,
    parents: list[str],
    description: str,
    dimensions: dict,
    proposal_content: str,
    group_name: str = "",
    reference_files: list[str] | None = None,
) -> Path:
    """Create a node YAML in br_nodes/ and proposal MD in br_proposals/.

    Returns the path to the created node YAML file.
    """
    nodes_dir = session_path / NODES_DIR
    proposals_dir = session_path / PROPOSALS_DIR

    proposal_file = f"{PROPOSALS_DIR}/{node_id}.md"

    node_data: dict = {
        "node_id": node_id,
        "parents": parents,
        "description": description,
        "proposal_file": proposal_file,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "created_by_group": group_name,
    }

    if reference_files is not None:
        node_data["reference_files"] = reference_files

    # Merge dimension fields
    node_data.update(dimensions)

    node_path = nodes_dir / f"{node_id}.yaml"
    write_yaml(str(node_path), node_data)

    proposal_path = proposals_dir / f"{node_id}.md"
    proposal_path.write_text(proposal_content, encoding="utf-8")

    return node_path


def read_node(session_path: Path, node_id: str) -> dict:
    """Read and return node YAML as dict."""
    node_path = session_path / NODES_DIR / f"{node_id}.yaml"
    return read_yaml(str(node_path))


def update_node(session_path: Path, node_id: str, updates: dict) -> None:
    """Update specific fields in node YAML (merge with existing data)."""
    node_path = session_path / NODES_DIR / f"{node_id}.yaml"
    data = read_yaml(str(node_path))
    data.update(updates)
    write_yaml(str(node_path), data)


def list_nodes(session_path: Path) -> list[str]:
    """Return all node IDs sorted by filename (creation order)."""
    nodes_dir = session_path / NODES_DIR
    if not nodes_dir.is_dir():
        return []
    return sorted(
        p.stem for p in nodes_dir.iterdir()
        if p.suffix == ".yaml" and not p.name.startswith("_")
    )


# ---------------------------------------------------------------------------
# Graph state operations
# ---------------------------------------------------------------------------


def _read_graph_state(session_path: Path) -> dict:
    """Read br_graph_state.yaml."""
    return read_yaml(str(session_path / GRAPH_STATE_FILE))


def _write_graph_state(session_path: Path, data: dict) -> None:
    """Write br_graph_state.yaml."""
    write_yaml(str(session_path / GRAPH_STATE_FILE), data)


def get_head(session_path: Path) -> str | None:
    """Read br_graph_state.yaml and return current HEAD node ID (or None)."""
    gs = _read_graph_state(session_path)
    head = gs.get("current_head")
    # YAML null / empty string → None
    if not head:
        return None
    return str(head)


def set_head(session_path: Path, node_id: str) -> None:
    """Update HEAD in br_graph_state.yaml and append to history."""
    gs = _read_graph_state(session_path)
    gs["current_head"] = node_id
    history = gs.get("history", [])
    history.append(node_id)
    gs["history"] = history
    _write_graph_state(session_path, gs)


def next_node_id(session_path: Path) -> int:
    """Read, increment, and return next_node_id from br_graph_state.yaml.

    Returns the current value and increments the stored counter.
    """
    gs = _read_graph_state(session_path)
    current = gs.get("next_node_id", 0)
    gs["next_node_id"] = current + 1
    _write_graph_state(session_path, gs)
    return current


# ---------------------------------------------------------------------------
# DAG traversal
# ---------------------------------------------------------------------------


def get_parents(session_path: Path, node_id: str) -> list[str]:
    """Return parent node IDs from node YAML."""
    data = read_node(session_path, node_id)
    return data.get("parents", [])


def get_children(session_path: Path, node_id: str) -> list[str]:
    """Find all nodes that list this node as a parent."""
    children = []
    for nid in list_nodes(session_path):
        data = read_node(session_path, nid)
        if node_id in data.get("parents", []):
            children.append(nid)
    return children


def get_node_lineage(session_path: Path, node_id: str) -> list[str]:
    """Trace ancestry back to root node. Returns list from root to node_id.

    Uses BFS backwards through parents. If the node has multiple parents
    (hybridization), follows the first parent at each step.
    """
    lineage = [node_id]
    visited = {node_id}
    current = node_id

    while True:
        parents = get_parents(session_path, current)
        if not parents:
            break
        # Follow first parent for linear lineage
        parent = parents[0]
        if parent in visited:
            break
        visited.add(parent)
        lineage.append(parent)
        current = parent

    lineage.reverse()
    return lineage


# ---------------------------------------------------------------------------
# Content readers
# ---------------------------------------------------------------------------


def read_proposal(session_path: Path, node_id: str) -> str:
    """Read the proposal markdown file for a node."""
    path = session_path / PROPOSALS_DIR / f"{node_id}.md"
    return path.read_text(encoding="utf-8")


def read_plan(session_path: Path, node_id: str) -> str | None:
    """Read the plan markdown file for a node (None if doesn't exist)."""
    path = session_path / PLANS_DIR / f"{node_id}_plan.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Dimension helpers
# ---------------------------------------------------------------------------


def get_dimension_fields(node_data: dict) -> dict:
    """Extract all dimension fields from node data.

    Dimension fields are those starting with: requirements_, assumption_,
    component_, tradeoff_.
    """
    from .brainstorm_schemas import is_dimension_field
    return {k: v for k, v in node_data.items() if is_dimension_field(k)}
