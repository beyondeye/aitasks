---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 16:44
updated_at: 2026-06-01 18:08
---

Phase A of the `ait brainstorm` **module decomposition** feature (parent t756).
Builds the additive, back-compatible **data-model foundation** that Phases B/C/D
depend on. **No new ops** are added here — existing ops keep operating on the
`_umbrella` subgraph.

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.1 subgraph data model, §5 "data-model layer" + "merge guard", §7 Phase A).
**Cross-cutting decisions (binding):** `aiplans/p756_brainstorm_modules.md` — the
`module_` op-prefix convention, the "dimensions stay session-wide" decision, and
the t873 re-verification record.

## Context
Today `ait brainstorm` models **one session = one task = one DAG = one HEAD**.
`br_graph_state.yaml` tracks a single `current_head`; every op targets it. Modules
require **per-subgraph HEADs**, explicit subgraph membership on nodes, optional
per-module task linkage, and a per-module sync timestamp — all additive so legacy
single-head sessions keep loading. This child lays that schema/DAG groundwork only;
the ops that consume it land in Phase B (t756_2) and Phase C (t756_3).

**Re-verified against t873 (2026-06-01):** `active_dimensions` is unchanged — a
**flat session-wide list of strings**. Do NOT convert it to a per-module map.
`module_label` is an independent optional node field, orthogonal to dimension
fields. (See parent plan "Re-verification" section.)

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_schemas.py`
  - `GRAPH_STATE_REQUIRED` (line ~35): extend/validate for `current_heads` (map
    `<module>:<node_id>`). Keep `current_head` as a **legacy alias** of
    `current_heads["_umbrella"]`. Handle `history` as either the legacy list OR
    the new per-module map without breaking existing sessions.
  - `NODE_OPTIONAL_FIELDS` (line ~13): add `module_label`.
  - `validate_graph_state`: validate `current_heads`/`history` map shapes,
    `module_tasks` map, `last_synced_at` map. Keep `active_dimensions` validated
    as a flat `list` (do NOT change).
- `.aitask-scripts/brainstorm/brainstorm_dag.py`
  - Add a `module="_umbrella"` parameter (default = back-compat) to `set_head`,
    `get_head`, `get_node_lineage`, `next_node_id`.
  - New helper `is_ancestor_subgraph(source, destination)` — walks the
    parent-of-root chain; used by Phase B's merge "only up" guard.
- `.aitask-scripts/brainstorm/brainstorm_session.py::init_session`
  - Initialize `current_heads = {_umbrella: <root>}`, `module_tasks = {}`, and the
    `last_synced_at = {}` map alongside the legacy fields.
- Wizard subgraph-selector scaffolding (`brainstorm_app.py`) lands here **only if
  cheap**; otherwise it belongs in Phase B — note the boundary explicitly in the
  plan/Final Implementation Notes so 756_2 knows where the line was drawn.

## Reference Files for Patterns
- `brainstorm_schemas.py` current `GRAPH_STATE_REQUIRED`,
  `validate_graph_state`, `NODE_OPTIONAL_FIELDS`, `extract_dimensions`,
  `group_dimensions_by_prefix` (the last two added by t873 — reuse, don't fork).
- `brainstorm_dag.py` current `get_head`/`set_head`/`get_node_lineage`/
  `next_node_id` (single-head versions) and `get_active_dimensions` (t873, line ~116).
- `brainstorm_session.py::init_session` current graph-state initialization.

## Implementation Plan
1. Schema: add the three new map fields with back-compat readers; keep
   `current_head`/`history` legacy aliases working both ways.
2. DAG: thread the `module` parameter through the four head/lineage helpers,
   defaulting to `_umbrella`; add `is_ancestor_subgraph`.
3. Session init: seed the new maps.
4. Decide the wizard-scaffold boundary (here vs Phase B) and document it.

## Verification Steps
- Legacy single-head sessions still load and pass `validate_graph_state`.
- New map fields round-trip (write → read → validate).
- `is_ancestor_subgraph` correctness on a small constructed DAG (ancestor → True,
  sibling/descendant → False).
- Existing brainstorm tests still pass: `bash tests/test_*brainstorm*.sh` (run the
  relevant suite).
