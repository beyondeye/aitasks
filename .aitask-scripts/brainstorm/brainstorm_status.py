"""Derived per-module fluid status (UC-2) for the brainstorm module feature.

Status is a *render*, not a stored op (design doc §4.7): every input already
exists after Phases A–C. ``compute_module_status`` folds four already-persisted
signals into one of the base states:

    unstarted | in_design | in_implementation | implemented | merged

The ``deferred`` marker (``module_deferred`` map, t756_5) is **orthogonal** — it
overlays on top of the base state, so it is returned separately (see
``module_status_rows``) rather than collapsed into the base status.

Inputs (all already on disk):
  * per-subgraph node counts        — ``list_nodes`` + ``_node_module``
  * linked-task state               — ``module_tasks`` map → task-file frontmatter
  * cross-subgraph merge edge        — ``parents`` walk for the source HEAD
  * deferred marker                  — ``module_deferred`` map

No new ops are introduced; this module is pure (read-only over a session_path).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from brainstorm.brainstorm_dag import (
    UMBRELLA_SUBGRAPH,
    _node_module,
    _read_graph_state,
    get_head,
    get_parents,
    list_nodes,
    list_subgraphs,
)
from brainstorm.brainstorm_session import _module_deferred_map

# §4.7 fluid-status vocabulary (base states + the orthogonal overlay).
STATUS_UNSTARTED = "unstarted"
STATUS_IN_DESIGN = "in_design"
STATUS_IN_IMPLEMENTATION = "in_implementation"
STATUS_IMPLEMENTED = "implemented"
STATUS_MERGED = "merged"
STATUS_DEFERRED = "deferred"

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Linked-task state resolution
# ---------------------------------------------------------------------------


def _resolve_task_state(task_id: str) -> tuple[str | None, bool]:
    """Resolve a linked task id to ``(frontmatter_status, is_archived)``.

    Modelled on ``brainstorm_crew._resolve_linked_plan_path`` but over
    ``aitasks/`` (task files, not plans). ``task_id`` may be a child id
    (``756_5`` → ``aitasks/t756/t756_5_*.md``) or a parent id
    (``905`` → ``aitasks/t905_*.md``). Live location is preferred; an
    archived-only hit reports ``is_archived=True`` (the §4.7 "implemented"
    signal). Returns ``(None, False)`` when no task file exists (graceful: the
    caller treats an unresolved task as still in design).
    """
    tid = str(task_id)
    if "_" in tid:
        parent = tid.split("_", 1)[0]
        live_dir = Path("aitasks") / f"t{parent}"
        arch_dir = Path("aitasks/archived") / f"t{parent}"
    else:
        live_dir = Path("aitasks")
        arch_dir = Path("aitasks/archived")
    pattern = f"t{tid}_*.md"

    for d, archived in ((live_dir, False), (arch_dir, True)):
        if d.is_dir():
            matches = sorted(d.glob(pattern))
            if matches:
                return (_read_frontmatter_status(matches[0]), archived)
    return (None, False)


def _read_frontmatter_status(path: Path) -> str | None:
    """Return the ``status`` field from a task file's YAML frontmatter (or None)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None
    status = meta.get("status")
    return str(status) if status else None


# ---------------------------------------------------------------------------
# Merge detection
# ---------------------------------------------------------------------------


def is_module_merged(session_path: Path, module: str) -> bool:
    """True iff ``module``'s HEAD was merged into another subgraph (§4.7).

    The merge edge is created by ``module_merge``: a node in the *destination*
    subgraph lists the source subgraph's HEAD among its ``parents``. So the
    module is "merged" when its current HEAD appears in the ``parents`` of any
    node belonging to a different subgraph.
    """
    source_head = get_head(session_path, module=module)
    if not source_head:
        return False
    for nid in list_nodes(session_path):
        if _node_module(session_path, nid) == module:
            continue
        if source_head in get_parents(session_path, nid):
            return True
    return False


# ---------------------------------------------------------------------------
# Base status computation
# ---------------------------------------------------------------------------


def compute_module_status(session_path: Path, module: str) -> str:
    """Compute a module's §4.7 **base** status (deferred is handled separately).

    Precedence: ``merged`` is terminal (the design was absorbed upstream) and
    wins over every other base state. Otherwise the state derives from the
    subgraph's node count and the linked task's lifecycle:

        only root node                              → unstarted
        nodes beyond root, no/Ready linked task     → in_design
        linked task Implementing                    → in_implementation
        linked task Done / archived                 → implemented

    The ``deferred`` overlay is **not** folded in here — call
    ``_module_deferred_map`` (or use ``module_status_rows``) for that, so a
    module can be both deferred and any base state.
    """
    if is_module_merged(session_path, module):
        return STATUS_MERGED

    subgraph_nodes = [
        nid for nid in list_nodes(session_path)
        if _node_module(session_path, nid) == module
    ]
    if len(subgraph_nodes) <= 1:
        return STATUS_UNSTARTED

    task_id = _read_graph_state(session_path).get("module_tasks", {})
    task_id = task_id.get(module) if isinstance(task_id, dict) else None
    if not task_id:
        return STATUS_IN_DESIGN

    status, is_archived = _resolve_task_state(task_id)
    if is_archived or status == "Done":
        return STATUS_IMPLEMENTED
    if status == "Implementing":
        return STATUS_IN_IMPLEMENTATION
    return STATUS_IN_DESIGN


# ---------------------------------------------------------------------------
# Render helper (subgraph-tree dashboard data)
# ---------------------------------------------------------------------------


def module_status_rows(session_path: Path) -> list[dict]:
    """Per-subgraph status rows for the dashboard, most-recent subgraph first.

    Each row: ``{module, status, deferred, task_id, last_synced, node_count,
    is_umbrella}``. ``status`` is the base state; ``deferred`` is the orthogonal
    overlay flag. Single source of truth for the dashboard render and its tests.
    """
    gs = _read_graph_state(session_path)
    module_tasks = gs.get("module_tasks") if isinstance(gs.get("module_tasks"), dict) else {}
    last_synced = gs.get("last_synced_at") if isinstance(gs.get("last_synced_at"), dict) else {}
    deferred_map = _module_deferred_map(session_path)

    counts: dict[str, int] = {}
    for nid in list_nodes(session_path):
        m = _node_module(session_path, nid)
        counts[m] = counts.get(m, 0) + 1

    rows: list[dict] = []
    for module in list_subgraphs(session_path):
        rows.append({
            "module": module,
            "status": compute_module_status(session_path, module),
            "deferred": bool(deferred_map.get(module, False)),
            "task_id": module_tasks.get(module),
            "last_synced": last_synced.get(module),
            "node_count": counts.get(module, 0),
            "is_umbrella": module == UMBRELLA_SUBGRAPH,
        })
    return rows
