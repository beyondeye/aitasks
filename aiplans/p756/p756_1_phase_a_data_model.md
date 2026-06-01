---
Task: t756_1_phase_a_data_model.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_2_phase_b_decompose_merge_ops.md, aitasks/t756/t756_3_phase_c_sync_op.md, aitasks/t756/t756_4_phase_d_tui_status_views.md
Archived Sibling Plans: (none yet — this is the first child)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t756_1 — Phase A: Module Data Model (foundation)

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.1, §5 "data-model layer" + "merge guard", §7 Phase A).
**Binding cross-cutting decisions:** `aiplans/p756_brainstorm_modules.md`
(`module_` op-prefix; "dimensions stay session-wide"; t873 re-verification record).

## Goal
Lay the additive, back-compatible data-model groundwork that Phases B/C/D consume.
**No new ops** here — existing ops keep targeting the `_umbrella` subgraph.

## Scope
- `brainstorm_schemas.py`
  - `GRAPH_STATE_REQUIRED` (~line 35): support `current_heads` (map
    `<module>:<node_id>`). Keep `current_head` as a legacy alias of
    `current_heads["_umbrella"]`. Treat `history` as either the legacy list or the
    new per-module map without breaking existing sessions.
  - `NODE_OPTIONAL_FIELDS` (~line 13): add `module_label`.
  - `validate_graph_state`: validate `current_heads` / `history` map shapes,
    `module_tasks` map, `last_synced_at` map. **Leave `active_dimensions` validated
    as a flat `list`** (re-verified unchanged against t873 — do NOT convert to a
    per-module map).
- `brainstorm_dag.py`
  - Add `module="_umbrella"` parameter (default = back-compat) to `set_head`,
    `get_head`, `get_node_lineage`, `next_node_id`.
  - New helper `is_ancestor_subgraph(source, destination)` — walks the
    parent-of-root chain; consumed by Phase B's merge "only up" guard.
- `brainstorm_session.py::init_session`
  - Seed `current_heads = {_umbrella: <root>}`, `module_tasks = {}`,
    `last_synced_at = {}` alongside legacy fields.
- Wizard subgraph-selector scaffolding lands here **only if cheap**; otherwise it
  belongs to Phase B. **Document the chosen boundary** in Final Implementation Notes
  so 756_2 knows where the line was drawn.

## Reference patterns (reuse, don't fork)
- `brainstorm_schemas.py`: current `GRAPH_STATE_REQUIRED`, `validate_graph_state`,
  `NODE_OPTIONAL_FIELDS`; t873 helpers `extract_dimensions` (~145),
  `group_dimensions_by_prefix` (~150).
- `brainstorm_dag.py`: current single-head `get_head`/`set_head`/`get_node_lineage`/
  `next_node_id`; `get_active_dimensions` (~116, t873).
- `brainstorm_session.py::init_session` current graph-state init.

## Implementation steps
1. Schema: add the three new map fields with back-compat readers; keep
   `current_head`/`history` legacy aliases working both directions.
2. DAG: thread `module` through the four head/lineage helpers (default `_umbrella`);
   add `is_ancestor_subgraph`.
3. Session init: seed the new maps.
4. Decide + document the wizard-scaffold boundary (here vs Phase B).

## Verification
- Legacy single-head sessions still load and pass `validate_graph_state`.
- New map fields round-trip (write → read → validate) for a multi-module state.
- `is_ancestor_subgraph` is correct on a constructed DAG (ancestor → True;
  sibling/descendant → False).
- `current_head` legacy alias resolves to `current_heads["_umbrella"]` both ways.
- Existing brainstorm tests still pass (run the brainstorm suite).

## Step 9 (Post-Implementation)
On completion follow task-workflow Step 9: review, commit (`feature: … (t756_1)`),
consolidate this plan with Final Implementation Notes (incl. the wizard-scaffold
boundary decision + any notes for sibling tasks), then archive via
`./.aitask-scripts/aitask_archive.sh 756_1`.
