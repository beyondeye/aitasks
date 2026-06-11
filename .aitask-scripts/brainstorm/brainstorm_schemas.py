"""Schema definitions and validation for brainstorm engine data files.

Covers: node YAML (br_nodes/), graph state (br_graph_state.yaml),
session (br_session.yaml), and operation groups (br_groups.yaml).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Node schema (br_nodes/nXXX_name.yaml)
# ---------------------------------------------------------------------------

NODE_REQUIRED_FIELDS = [
    "node_id", "parents", "description", "proposal_file",
    "created_at", "created_by_group",
]
# ``module_label`` (optional) records the node's subgraph membership for the
# module-decomposition feature (t756). Absent / empty means the default
# ``_umbrella`` subgraph, so legacy single-head sessions need no migration.
NODE_OPTIONAL_FIELDS = ["plan_file", "reference_files", "module_label"]

# Dimension fields use these prefixes — extensible, any key starting with
# one of these is treated as a dimension field.
DIMENSION_PREFIXES = ("requirements_", "assumption_", "component_", "tradeoff_")

# Human-readable plural label per dimension prefix.
PREFIX_TO_LABEL = {
    "requirements_": "Requirements",
    "assumption_":   "Assumptions",
    "component_":    "Components",
    "tradeoff_":     "Tradeoffs",
}

# ---------------------------------------------------------------------------
# Graph state schema (br_graph_state.yaml)
# ---------------------------------------------------------------------------

GRAPH_STATE_REQUIRED = ["current_head", "history", "next_node_id", "active_dimensions"]

# Additive, optional fields for module decomposition (t756). They are NOT in
# GRAPH_STATE_REQUIRED so legacy single-head sessions keep validating:
#   current_heads   — map <module>:<node_id>; current_head stays as the legacy
#                     alias of current_heads["_umbrella"].
#   module_tasks    — map <module>:<task_id> (optional fast-track linkage).
#   last_synced_at  — map <module>:<timestamp> (sync scan horizon).
#   module_deferred — map <module>:<bool> (UC-2 fluid-status "deferred" marker,
#                     t756_5); orthogonal to the computed base status. Absent /
#                     falsy means the module is active.
# ``history`` is repurposed from the legacy linear list into a per-module map
# (<module> -> [node_id, ...]); validate_graph_state accepts either shape.
GRAPH_STATE_MODULE_MAPS = [
    "current_heads", "module_tasks", "last_synced_at", "module_deferred",
]

# ---------------------------------------------------------------------------
# Session schema (br_session.yaml)
# ---------------------------------------------------------------------------

SESSION_REQUIRED = [
    "task_id", "task_file", "status", "crew_id",
    "created_at", "updated_at", "created_by", "initial_spec",
]
SESSION_OPTIONAL = ["url_cache", "url_cache_bypass"]
SESSION_STATUSES = ["init", "active", "paused", "completed", "archived"]

# ---------------------------------------------------------------------------
# Operation group schema (br_groups.yaml entries)
# ---------------------------------------------------------------------------

GROUP_REQUIRED = [
    "operation", "agents", "status", "created_at",
    "head_at_creation", "nodes_created",
]
# Canonical optional group fields. Documentation-only (no validator consumes
# it today, symmetric with GROUP_REQUIRED): ``subgraph`` records which module
# subgraph an op ran inside; absent entries default to ``_umbrella``.
GROUP_OPTIONAL = ["subgraph"]
GROUP_OPERATIONS = [
    "explore",
    "compare",
    "synthesize",
    "module_decompose",
    "module_merge",
    "module_sync",
]

# Legacy operation names kept readable for in-flight sessions on disk.
# t807 renamed the DAG op "hybridize" -> "synthesize" (agent stays
# "synthesizer"). Old br_groups.yaml entries / created_by_group values
# still carry "hybridize"; canonical_op() normalizes them at read time.
_LEGACY_OP_ALIASES = {"hybridize": "synthesize"}


def canonical_op(op: str) -> str:
    """Normalize a persisted operation name to its current canonical form.

    Legacy in-flight brainstorm sessions persist ``operation: hybridize``;
    this maps it to ``synthesize``. Current / unknown values pass through.
    """
    return _LEGACY_OP_ALIASES.get(op, op)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_node(data: dict) -> list[str]:
    """Validate a node YAML dict. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    for field in NODE_REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "parents" in data and not isinstance(data["parents"], list):
        errors.append("Field 'parents' must be a list")

    if "reference_files" in data and not isinstance(data["reference_files"], list):
        errors.append("Field 'reference_files' must be a list")

    if "node_id" in data and "proposal_file" in data:
        node_id = data["node_id"]
        proposal = data["proposal_file"]
        if node_id and proposal and node_id not in proposal:
            errors.append(f"proposal_file '{proposal}' does not contain node_id '{node_id}'")

    return errors


def validate_graph_state(data: dict) -> list[str]:
    """Validate a graph state YAML dict. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    for field in GRAPH_STATE_REQUIRED:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # history is either the legacy linear list (single-head sessions) or the
    # new per-module map <module> -> [node_id, ...] (module decomposition, t756).
    if "history" in data:
        history = data["history"]
        if isinstance(history, dict):
            for module, entries in history.items():
                if not isinstance(entries, list):
                    errors.append(
                        f"Field 'history[{module}]' must be a list of node IDs"
                    )
        elif not isinstance(history, list):
            errors.append("Field 'history' must be a list or a per-module map")

    if "next_node_id" in data and not isinstance(data["next_node_id"], int):
        errors.append("Field 'next_node_id' must be an integer")

    # active_dimensions stays a flat, session-wide list — modules do NOT fork
    # the dimension axis (re-verified against t873). Do not convert to a map.
    if "active_dimensions" in data and not isinstance(data["active_dimensions"], list):
        errors.append("Field 'active_dimensions' must be a list")

    # Additive module-decomposition maps (all optional, all <module>-keyed).
    for field in GRAPH_STATE_MODULE_MAPS:
        if field in data and not isinstance(data[field], dict):
            errors.append(f"Field '{field}' must be a map keyed by module name")

    return errors


def validate_session(data: dict) -> list[str]:
    """Validate a session YAML dict. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    for field in SESSION_REQUIRED:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    status = data.get("status")
    if status is not None and status not in SESSION_STATUSES:
        errors.append(f"Invalid status '{status}', must be one of: {', '.join(SESSION_STATUSES)}")

    if "url_cache" in data and data["url_cache"] not in ("enabled", "disabled"):
        errors.append("Field 'url_cache' must be 'enabled' or 'disabled'")

    if "url_cache_bypass" in data and not isinstance(data["url_cache_bypass"], list):
        errors.append("Field 'url_cache_bypass' must be a list")

    return errors


def is_dimension_field(key: str) -> bool:
    """Check if a key is a dimension field based on its prefix."""
    return any(key.startswith(p) for p in DIMENSION_PREFIXES)


def extract_dimensions(data: dict) -> dict:
    """Extract all dimension fields from a node data dict."""
    return {k: v for k, v in data.items() if is_dimension_field(k)}


def group_dimensions_by_prefix(
    dims: dict,
) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """Group dimension fields by their type prefix, in DIMENSION_PREFIXES order.

    Returns a list of (prefix, human_label, entries). Each entry is
    (suffix, value, full_key). Empty prefixes are omitted entirely.
    Items not matching any known prefix are silently dropped (callers are
    expected to pass already-validated dimension dicts via
    ``extract_dimensions`` / ``get_dimension_fields``).
    """
    groups: list[tuple[str, str, list[tuple[str, str, str]]]] = []
    for prefix in DIMENSION_PREFIXES:
        entries = [
            (k[len(prefix):], v, k)
            for k, v in dims.items()
            if k.startswith(prefix)
        ]
        if entries:
            groups.append((prefix, PREFIX_TO_LABEL[prefix], entries))
    return groups
