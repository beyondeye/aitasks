"""DAG operations for the brainstorm engine design space.

All functions take a session_path (Path to the crew worktree, e.g.
.aitask-crews/crew-brainstorm-419/) and operate on br_nodes/, br_proposals/,
and br_graph_state.yaml within it.

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
GRAPH_STATE_FILE = "br_graph_state.yaml"

# Default subgraph for the module-decomposition feature (t756). Every legacy
# single-head session is an implicit ``_umbrella`` subgraph; head/lineage
# helpers default to it so existing call-sites are unchanged.
UMBRELLA_SUBGRAPH = "_umbrella"


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
    module_label: str | None = None,
) -> Path:
    """Create a node YAML in br_nodes/ and proposal MD in br_proposals/.

    Returns the path to the created node YAML file.

    ``module_label`` records the node's subgraph membership. It is written
    only for non-``_umbrella`` subgraphs so legacy / umbrella nodes stay
    byte-identical (``_node_module`` defaults an absent label to _umbrella).
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

    if module_label and module_label != UMBRELLA_SUBGRAPH:
        node_data["module_label"] = module_label

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


def get_active_dimensions(session_path: Path) -> list[str]:
    """Return the session's active dimension keys (or [] if none)."""
    gs = _read_graph_state(session_path)
    return [str(d) for d in (gs.get("active_dimensions") or [])]


def get_head(session_path: Path, module: str = UMBRELLA_SUBGRAPH) -> str | None:
    """Return the HEAD node ID for a subgraph (or None).

    Reads ``current_heads[module]`` when the per-module map exists; for the
    ``_umbrella`` subgraph it falls back to the legacy ``current_head`` field
    so single-head sessions written before module support still resolve.
    """
    gs = _read_graph_state(session_path)
    head = None
    heads = gs.get("current_heads")
    if isinstance(heads, dict) and module in heads:
        head = heads.get(module)
    elif module == UMBRELLA_SUBGRAPH:
        head = gs.get("current_head")
    # YAML null / empty string → None
    if not head:
        return None
    return str(head)


def set_head(session_path: Path, node_id: str, module: str = UMBRELLA_SUBGRAPH) -> None:
    """Update a subgraph HEAD in br_graph_state.yaml and append to its history.

    Writes ``current_heads[module]`` and, for the ``_umbrella`` subgraph, keeps
    the legacy ``current_head`` field in sync as an alias. ``history`` is a
    per-module map (<module> -> [node_id, ...]); a legacy linear list is
    migrated in place to ``history["_umbrella"]`` on first write.
    """
    gs = _read_graph_state(session_path)

    heads = gs.get("current_heads")
    if not isinstance(heads, dict):
        heads = {}
    heads[module] = node_id
    gs["current_heads"] = heads

    # Legacy alias: the _umbrella HEAD is mirrored to current_head.
    if module == UMBRELLA_SUBGRAPH:
        gs["current_head"] = node_id

    history = gs.get("history")
    if isinstance(history, list):
        # Legacy linear list — repurpose as the _umbrella subgraph history.
        history = {UMBRELLA_SUBGRAPH: history}
    elif not isinstance(history, dict):
        history = {}
    module_history = list(history.get(module, []))
    module_history.append(node_id)
    history[module] = module_history
    gs["history"] = history

    _write_graph_state(session_path, gs)


def next_node_id(session_path: Path, module: str = UMBRELLA_SUBGRAPH) -> int:
    """Read, increment, and return next_node_id from br_graph_state.yaml.

    Returns the current value and increments the stored counter. The node-id
    counter is session-wide (shared across all subgraphs); the ``module``
    parameter is accepted for signature symmetry with the other head helpers
    and is currently unused.
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


def node_descendants_closure(session_path: Path, node_id: str) -> list[str]:
    """Return ``node_id`` plus all its transitive descendants (child-closure).

    Breadth-first over ``get_children`` (which finds any node listing the
    current id among its ``parents``), starting from ``node_id`` (always first
    in the result). The closure is **child-transitive**: a multi-parent
    ``synthesize`` / ``module_merge`` node that lists an affected node among its
    parents is pulled in, so the closure never leaves a dangling parent ref
    behind. Shared by the delete-confirm modal (casualty list + agent guard) and
    ``delete_node_cascade``.
    """
    closure: list[str] = []
    seen: set[str] = set()
    queue: deque[str] = deque([node_id])
    while queue:
        nid = queue.popleft()
        if nid in seen:
            continue
        seen.add(nid)
        closure.append(nid)
        for child in get_children(session_path, nid):
            if child not in seen:
                queue.append(child)
    return closure


def _first_surviving_parent(
    session_path: Path, node_id: str, closure: set[str]
) -> str | None:
    """Return the nearest ancestor of ``node_id`` not in ``closure`` (or None).

    Climbs the ``parents`` graph breadth-first, skipping members of ``closure``
    (the to-be-deleted set), and returns the first surviving ancestor found.
    Used to re-point a subgraph HEAD when the HEAD node is being deleted; yields
    ``None`` when the deleted subtree root has no surviving ancestor.
    """
    seen: set[str] = set()
    queue: deque[str] = deque(get_parents(session_path, node_id))
    while queue:
        pid = queue.popleft()
        if pid in seen:
            continue
        seen.add(pid)
        if pid not in closure:
            return pid
        queue.extend(get_parents(session_path, pid))
    return None


def delete_node_cascade(session_path: Path, node_id: str) -> dict:
    """Delete ``node_id`` and all its descendants, repointing affected HEADs.

    Cascade-deletes the child-transitive closure of ``node_id`` (see
    ``node_descendants_closure``): removes each node's ``br_nodes/<id>.yaml``,
    ``br_proposals/<id>.md``, and plan file, and rewrites
    ``br_graph_state.yaml``:

    - Any subgraph HEAD (``current_heads[module]`` or the legacy
      ``current_head`` alias) in the closure is re-pointed to the nearest
      surviving ancestor of ``node_id`` (or cleared when none survives).
    - Closure ids are pruned from every per-module ``history`` list.
    - ``module_tasks``, ``last_synced_at``, and ``module_deferred`` are left
      untouched — a linked aitask is never deleted by this operation.

    Returns a report dict::

        {"deleted": [...], "head_repoints": {module: new_head_or_None},
         "history_pruned": {module: [removed_id, ...]}, "missing_root": bool}
    """
    if node_id not in list_nodes(session_path):
        return {
            "deleted": [],
            "head_repoints": {},
            "history_pruned": {},
            "missing_root": True,
        }

    closure_list = node_descendants_closure(session_path, node_id)
    closure = set(closure_list)

    gs = _read_graph_state(session_path)

    # --- HEAD repoints ---
    head_repoints: dict[str, str | None] = {}
    repoint_target = _first_surviving_parent(session_path, node_id, closure)

    heads = gs.get("current_heads")
    if isinstance(heads, dict):
        for module, head in list(heads.items()):
            if head in closure:
                head_repoints[module] = repoint_target
                if repoint_target is None:
                    heads.pop(module, None)
                else:
                    heads[module] = repoint_target

    # Legacy alias: keep current_head in sync with the _umbrella HEAD.
    legacy_head = gs.get("current_head")
    if legacy_head and legacy_head in closure:
        head_repoints.setdefault(UMBRELLA_SUBGRAPH, repoint_target)
        gs["current_head"] = repoint_target

    # --- History prune ---
    history = gs.get("history")
    if isinstance(history, list):
        # Legacy linear list — treat as the _umbrella subgraph history.
        history = {UMBRELLA_SUBGRAPH: history}
    history_pruned: dict[str, list[str]] = {}
    if isinstance(history, dict):
        for module, ids in list(history.items()):
            if not isinstance(ids, list):
                continue
            removed = [i for i in ids if i in closure]
            if removed:
                history[module] = [i for i in ids if i not in closure]
                history_pruned[module] = removed
        gs["history"] = history

    _write_graph_state(session_path, gs)

    # --- Delete files (best-effort) ---
    for nid in closure_list:
        (session_path / NODES_DIR / f"{nid}.yaml").unlink(missing_ok=True)
        (session_path / PROPOSALS_DIR / f"{nid}.md").unlink(missing_ok=True)

    return {
        "deleted": closure_list,
        "head_repoints": head_repoints,
        "history_pruned": history_pruned,
        "missing_root": False,
    }


def _node_module(session_path: Path, node_id: str) -> str:
    """Return a node's subgraph membership (``module_label``, default _umbrella).

    Absent / empty ``module_label`` means the node belongs to the default
    ``_umbrella`` subgraph, so legacy nodes need no migration.
    """
    data = read_node(session_path, node_id)
    label = data.get("module_label")
    return str(label) if label else UMBRELLA_SUBGRAPH


def _node_id_ordinal(node_id: str) -> int:
    """Return the numeric ordinal of a node id (``n012_explorer`` -> 12).

    Node ids are minted as ``f"n{num:03d}_{agent}"`` with a session-wide
    counter, so the ordinal is a stable global recency key. Returns -1 for an
    id that does not match the pattern (sorts such ids last).
    """
    if not node_id.startswith("n"):
        return -1
    digits = node_id[1:].split("_", 1)[0]
    return int(digits) if digits.isdigit() else -1


def list_subgraphs(session_path: Path) -> list[str]:
    """Return the session's subgraph names, most-recently-touched first.

    Recency is the ordinal of each subgraph's current HEAD node id (the
    node-id counter is session-wide, so a higher ordinal means more recently
    extended). ``_umbrella`` is always present; an absent / empty
    ``current_heads`` map yields ``["_umbrella"]``. Single source of truth for
    the wizard subgraph-selector and its tests — callers must not re-walk
    graph state.
    """
    gs = _read_graph_state(session_path)
    heads = gs.get("current_heads")
    if not isinstance(heads, dict) or not heads:
        return [UMBRELLA_SUBGRAPH]
    names = list(heads.keys())
    if UMBRELLA_SUBGRAPH not in names:
        names.append(UMBRELLA_SUBGRAPH)
    names.sort(key=lambda m: _node_id_ordinal(str(heads.get(m) or "")), reverse=True)
    return names


def get_node_lineage(
    session_path: Path, node_id: str, module: str = UMBRELLA_SUBGRAPH
) -> list[str]:
    """Trace ancestry back to the subgraph root. Returns list from root to node_id.

    Uses a backwards first-parent walk (multi-parent ``synthesize`` / ``merge``
    nodes follow their first parent). The walk stays within the ``module``
    subgraph: it stops as soon as the next first-parent belongs to a different
    subgraph — e.g. a subgraph root whose first parent lives in the ancestor
    subgraph. For legacy single-head sessions every node is ``_umbrella``, so
    the walk reaches the real root exactly as before.
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
        if _node_module(session_path, parent) != module:
            # Crossed a subgraph boundary — stop at this subgraph's root.
            break
        visited.add(parent)
        lineage.append(parent)
        current = parent

    lineage.reverse()
    return lineage


def _subgraph_root(session_path: Path, module: str) -> str | None:
    """Return the root node of a subgraph.

    The root is the earliest node tagged with ``module`` whose first-parent
    lies outside ``module`` (the ``decompose`` boundary), or a parentless node
    (the ``_umbrella`` root). Returns None if the subgraph has no nodes.
    """
    candidates = [
        nid for nid in list_nodes(session_path)
        if _node_module(session_path, nid) == module
    ]
    for nid in candidates:
        parents = get_parents(session_path, nid)
        if not parents:
            return nid
        if _node_module(session_path, parents[0]) != module:
            return nid
    # Fallback: earliest candidate by creation order.
    return candidates[0] if candidates else None


def is_ancestor_subgraph(
    session_path: Path, source: str, destination: str
) -> bool:
    """Return True iff ``destination`` is an ancestor subgraph of ``source``.

    Enforces the ``merge`` op's "up only" rule: a module subgraph may merge
    only into a subgraph that lies on the chain of ``parents`` above the
    source subgraph's root node. Sibling and descendant destinations return
    False, as does ``source == destination`` (a subgraph is not its own
    ancestor). Walks the first-parent chain from the source root upward.
    """
    if source == destination:
        return False

    root = _subgraph_root(session_path, source)
    if root is None:
        return False

    visited = {root}
    current = root
    while True:
        parents = get_parents(session_path, current)
        if not parents:
            break
        parent = parents[0]
        if parent in visited:
            break
        visited.add(parent)
        if _node_module(session_path, parent) == destination:
            return True
        current = parent

    return False


# ---------------------------------------------------------------------------
# Content readers
# ---------------------------------------------------------------------------


def read_proposal(session_path: Path, node_id: str) -> str:
    """Read the proposal markdown file for a node."""
    path = session_path / PROPOSALS_DIR / f"{node_id}.md"
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
