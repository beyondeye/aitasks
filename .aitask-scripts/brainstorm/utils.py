"""Brainstorm TUI: pure helper functions and the NodeSelection model."""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import re
from difflib import SequenceMatcher
from pathlib import Path
from rich.text import Text
from diffviewer.diff_display import (
    word_diff_texts,
    TAG_STYLES,
)
from brainstorm.brainstorm_dag import _node_module
from brainstorm.brainstorm_session import GROUPS_FILE
from launch_modes import DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES

from brainstorm.constants import (
    RUNNER_STATE_DISPLAY,
    _MODULE_OPS,
    _MULTI_NODE_OPS,
    _MULTI_NODE_REASON,
    _ROOT_DELETE_REASON,
    _SINGLE_NODE_OPS,
    _SINGLE_NODE_REASON,
    _WIZARD_OP_TO_AGENT_TYPE,
    _WIZARD_STEPS,
)

def derive_runner_state(status: str, stale: bool) -> tuple[str, str]:
    """Pure: map a runner (status, stale) pair to (label, color).

    Mirrors the precedence used by the Running tab: an explicit ``none`` /
    ``stopped`` status wins, then ``stale``, else the runner is ``active``.
    """
    if status == "none":
        key = "none"
    elif status == "stopped":
        key = "stopped"
    elif stale:
        key = "stale"
    else:
        key = "active"
    return RUNNER_STATE_DISPLAY[key]


def format_status_strip(status: str, stale: bool, running_count: int) -> str:
    """Pure: render the always-on runtime strip markup (t983_9).

    ``[<color>]●[/] <label>   ▶ N running`` (or ``idle`` when nothing runs).
    """
    label, color = derive_runner_state(status, stale)
    run = f"▶ {running_count} running" if running_count else "idle"
    return f"[{color}]●[/{color}] {label}   {run}"


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


_STALE_CREW_BRANCH_RE = re.compile(
    r"Branch '(crew-brainstorm-[\w\-]+)' already exists"
)


def detect_stale_crew_branch(error_text: str) -> str | None:
    """Return the stale `crew-brainstorm-<N>` branch name if the error names one."""
    m = _STALE_CREW_BRANCH_RE.search(error_text)
    return m.group(1) if m else None


def _open_node_detail_visible(active_tab: str, focused_is_node_row: bool) -> bool:
    """check_action helper: Enter Open-detail is shown only when the Browse tab
    is active AND a NodeRow is currently focused (list view — a NodeRow is only
    focusable there)."""
    return active_tab == "tab_browse" and focused_is_node_row


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
    """kind is 'proposal'."""
    return f"brainstorm_t{task_num}_{node_id}_{kind}.md"


def _write_node_exports(
    target_dir: Path,
    task_num: str,
    node_id: str,
    proposal_text: str,
    do_proposal: bool,
) -> list[str]:
    """Write requested files to target_dir. Returns list of written paths.

    Raises OSError on write failure (caller surfaces via notify).
    """
    written: list[str] = []
    if do_proposal:
        p = target_dir / _export_filename(task_num, node_id, "proposal")
        p.write_text(proposal_text, encoding="utf-8")
        written.append(str(p))
    return written


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


def compare_matrix_rows(
    node_dims: dict[str, dict], node_ids: list[str]
) -> "list[tuple[str, list]] | None":
    """Compute the dimension-comparison matrix rows (pure, no I/O, no App, t983_7).

    Takes already-extracted per-node dimension dicts (``node_dims[node_id] ->
    {dim: value}``) and the column order ``node_ids``; returns the rows as
    ``[(row_key, cells), ...]`` where ``cells`` is the Dimension-column value
    followed by one cell per node id (rich ``Text`` / str), or ``None`` when no
    node has any dimension field. ``CompareMatrixModal.on_mount`` assembles the
    ``DataTable`` from these rows — ``DataTable.add_column`` needs an active App,
    so the *assembly* lives in the modal while this *logic* stays unit-testable
    without a running App. Logic lifted verbatim from the former
    ``_build_compare_matrix`` / ``_add_similarity_row``."""
    # Collect all dimension keys (preserving first-seen order)
    all_keys: list[str] = []
    seen: set[str] = set()
    for nid in node_ids:
        for k in node_dims.get(nid, {}):
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    if not all_keys:
        return None

    n = len(node_ids)
    rows: list[tuple[str, list]] = []

    # Dimension rows with color-coded values
    for key in all_keys:
        raw_values = [str(node_dims.get(nid, {}).get(key, "—")) for nid in node_ids]
        unique = set(raw_values)

        if len(unique) == 1:
            # Equal values: collapse to a single visible value (DataTable
            # cannot span cells, so use a "← same" marker for n == 2).
            if n == 2:
                node_cells = [
                    Text(raw_values[0], style="green"),
                    Text("← same", style="dim green"),
                ]
            else:
                node_cells = [Text(v, style="green") for v in raw_values]
        elif n == 2:
            # Differing values, two nodes: inline word-diff.
            v1, v2 = raw_values
            node_cells = list(word_diff_texts(
                v1, v2,
                TAG_STYLES["replace"], TAG_STYLES["replace"],
                TAG_STYLES["replace_dim"], TAG_STYLES["replace_dim"],
            ))
        else:
            # Differing values, 3-4 nodes: color by max pairwise similarity.
            max_sim = 0.0
            for i, x in enumerate(raw_values):
                for y in raw_values[i + 1:]:
                    sim = SequenceMatcher(None, x, y).ratio()
                    if sim > max_sim:
                        max_sim = sim
            color = "yellow" if max_sim > 0.6 else "red"
            node_cells = [Text(v, style=color) for v in raw_values]
        rows.append((key, [key, *node_cells]))

    # Average-similarity summary row
    from itertools import combinations

    pair_avgs: list[float] = []
    for n1, n2 in combinations(node_ids, 2):
        scores = []
        for key in all_keys:
            v1 = str(node_dims.get(n1, {}).get(key, ""))
            v2 = str(node_dims.get(n2, {}).get(key, ""))
            scores.append(SequenceMatcher(None, v1, v2).ratio())
        pair_avgs.append(sum(scores) / len(scores) if scores else 0.0)

    avg = sum(pair_avgs) / len(pair_avgs) if pair_avgs else 0.0
    sim_cells = [
        Text("— Avg Similarity —", style="bold"),
        Text(f"{avg:.0%}", style="bold cyan"),
    ] + [Text("")] * (n - 1)
    rows.append(("sim_score", sim_cells))

    return rows


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


class NodeSelection:
    """Selection state for the Browse UI: a ``primary`` cursor + a ``marked`` set.

    The target IA replaces single-node selection with ``space``-marking (single
    OR multi); the Operations dialog (t983_4) greys ops by selection
    *cardinality*. This model fixes the primary-vs-marked semantics:

      * ``primary`` is the cursor / focused node. SINGLE-node operations act on
        ``primary``. The cursor moves independently of marking (arrows move it;
        ``space`` marks the node under it).
      * ``marked`` is the explicitly space-marked set. MULTI-node operations act
        on ``marked``. Marking is what promotes a selection from single to multi.
      * :attr:`cardinality` is the EFFECTIVE selection size the dialog greys ops
        by: ``len(marked)`` when anything is marked, else ``1`` when a ``primary``
        cursor exists, else ``0``.
      * :meth:`effective` is the concrete target set an operation runs on — the
        runnable form of the cardinality rule.
    """

    def __init__(self, primary: str | None = None, marked: set[str] | None = None):
        self.primary = primary
        self.marked: set[str] = set(marked) if marked else set()

    def set_primary(self, node_id: str | None) -> None:
        """Move the cursor to ``node_id`` (or clear it with ``None``)."""
        self.primary = node_id

    def mark(self, node_id: str) -> None:
        """Add ``node_id`` to the marked set (idempotent)."""
        self.marked.add(node_id)

    def unmark(self, node_id: str) -> None:
        """Remove ``node_id`` from the marked set (no-op if absent)."""
        self.marked.discard(node_id)

    def toggle(self, node_id: str) -> None:
        """Flip ``node_id``'s marked state."""
        if node_id in self.marked:
            self.marked.discard(node_id)
        else:
            self.marked.add(node_id)

    def clear(self) -> None:
        """Clear the marked set only — the cursor (``primary``) persists."""
        self.marked.clear()

    def remove(self, node_id: str) -> None:
        """Drop ``node_id`` from the selection entirely (e.g. when it is deleted
        from the graph): unmark it AND clear it as ``primary`` if it was the
        cursor. Single-call cleanup so consumers don't have to remember a
        two-step purge. No-op if ``node_id`` is in neither."""
        self.marked.discard(node_id)
        if self.primary == node_id:
            self.primary = None

    @property
    def cardinality(self) -> int:
        """Effective selection size: marked count if any, else 1 for a lone
        cursor, else 0."""
        if self.marked:
            return len(self.marked)
        return 1 if self.primary is not None else 0

    def effective(self) -> set[str]:
        """Node ids an operation targets: the marked set if any are marked, else
        the primary as a singleton, else empty."""
        if self.marked:
            return set(self.marked)
        return {self.primary} if self.primary is not None else set()


def browse_toggle_view(current: str) -> str:
    """Return the other Browse view (graph⇄list).

    Any unrecognized ``current`` flips relative to the default, so a corrupt
    persisted value still toggles deterministically.
    """
    return "list" if current == "graph" else "graph"


def op_states_for_selection(node_ctx: dict, cardinality: int) -> dict:
    """Return ``{op_key: (disabled, reason)}`` for the Operations dialog, greyed
    by selection *cardinality* (t983_4).

    Pure / headless — no Textual, no session I/O. ``node_ctx`` carries the
    per-(primary-)node facts the delete/module-op preconditions need —
    ``is_root`` / ``is_umbrella`` / ``has_ancestor`` / ``has_linked_task`` —
    gathered by the App wrapper :meth:`BrainstormApp._node_action_op_states`.
    ``cardinality`` is :attr:`NodeSelection.cardinality` (marked count, else 1
    for a lone cursor, else 0).

    Greying rules:
      * single-node ops (explore / fast_track / delete) and module ops are
        disabled when ``cardinality > 1`` (reason "select a single node");
      * delete is disabled for the canonical root node;
      * module ops are *also* disabled when their own precondition is unmet
        (umbrella subgraph / no ancestor subgraph / no linked task) — the
        cardinality reason takes precedence when both apply;
      * multi-node ops (compare / synthesize) are disabled when
        ``cardinality < 2`` (reason "mark 2+ nodes").
    """
    multi = cardinality > 1
    states: dict[str, tuple[bool, str]] = {}

    for op in _SINGLE_NODE_OPS:
        states[op] = (True, _SINGLE_NODE_REASON) if multi else (False, "")

    is_umbrella = bool(node_ctx.get("is_umbrella"))
    is_root = bool(node_ctx.get("is_root"))
    has_ancestor = bool(node_ctx.get("has_ancestor"))
    has_linked_task = bool(node_ctx.get("has_linked_task"))

    if not multi and is_root:
        states["delete"] = (True, _ROOT_DELETE_REASON)

    # Per-module-op (disabled, reason) from the primary node's preconditions,
    # used only when the selection is a single node (cardinality == 1).
    module_precond = {
        "module_decompose": (is_umbrella, "no module on the root design"),
        "module_merge": (
            is_umbrella or not has_ancestor,
            "no module on the root design" if is_umbrella
            else "no ancestor subgraph",
        ),
        "module_sync": (
            is_umbrella or not has_linked_task,
            "no module on the root design" if is_umbrella
            else "module has no linked task",
        ),
    }
    for op in _MODULE_OPS:
        states[op] = (True, _SINGLE_NODE_REASON) if multi else module_precond[op]

    for op in _MULTI_NODE_OPS:
        states[op] = (False, "") if multi else (True, _MULTI_NODE_REASON)

    return states


def format_node_id_summary(ids, prefix: str, cap: int = 5) -> str:
    """Compact, overflow-capped one-line render of a node-id list (t983_4).

    Shared by the Operations dialog header (``Targets``) and the Browse
    marked-node summary (``Marked``) so the cap logic lives in one place. Shows
    the first ``cap`` ids and a ``(+K more)`` suffix for the rest, keeping the
    label bounded regardless of selection size — e.g.
    ``Targets (12): n001, n002, n003, n004, n005 (+7 more)``.
    """
    ids = list(ids)
    n = len(ids)
    shown = ", ".join(ids[:cap])
    suffix = f" (+{n - cap} more)" if n > cap else ""
    return f"{prefix} ({n}): {shown}{suffix}"


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

