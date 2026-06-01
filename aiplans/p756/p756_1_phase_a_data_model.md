---
Task: t756_1_phase_a_data_model.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_2_phase_b1_module_aware_wizard_infra.md, aitasks/t756/t756_3_phase_b2_decompose_merge_ops.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_5_phase_d1_status_views.md, aitasks/t756/t756_6_phase_d2_fast_track_preset.md
Archived Sibling Plans: (none yet — this is the first child)
Worktree: (none — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 17:59
---

# t756_1 — Phase A: Module Data Model (foundation)

## Context

`ait brainstorm` today models **one session = one task = one DAG = one HEAD**.
`br_graph_state.yaml` tracks a single `current_head`; every op targets it. The
module-decomposition feature (parent t756) requires **per-subgraph HEADs**,
explicit subgraph membership on nodes, optional per-module task linkage, and a
per-module sync timestamp. This child lays that **additive, back-compatible**
schema/DAG groundwork only — **no new ops** are added here; existing ops keep
operating on the `_umbrella` subgraph. Phases B/C/D consume this foundation.

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.1 subgraph data model, §5 "data-model layer" + "merge guard", §7 Phase A).
**Binding cross-cutting decisions:** `aiplans/p756_brainstorm_modules.md`
(`module_` op-prefix convention; "dimensions stay session-wide"; t873
re-verification record).

### Plan verification (2026-06-01, verify path)

Re-verified the existing plan against live source before re-confirming it:
- `brainstorm_schemas.py`: `GRAPH_STATE_REQUIRED` at **line 35**;
  `NODE_OPTIONAL_FIELDS = ["plan_file", "reference_files"]` at **line 17**
  (plan previously said "~line 13" — minor drift, corrected below);
  `validate_graph_state` at **line 101** (currently requires `history` to be a
  `list` at line 108 and `active_dimensions` to be a `list` at line 114);
  t873 helpers `extract_dimensions` (145), `group_dimensions_by_prefix` (150).
- `brainstorm_dag.py`: single-head `get_head` (122), `set_head` (132),
  `get_node_lineage` (175, first-parent walk), `next_node_id` (142);
  `get_active_dimensions` (116).
- `brainstorm_session.py::init_session`: graph-state dict written at lines
  **110–116** (`current_head: None, history: [], next_node_id: 0,
  active_dimensions: []`); `set_head(wt, "n000_init")` at 152.
- Confirmed: `active_dimensions` is still a **flat session-wide list** (do NOT
  convert to a per-module map); no `module_*` fields exist yet — additive fields
  collide with nothing. Relevant tests exist: `test_brainstorm_schemas.py`,
  `test_brainstorm_dag.py`, `test_brainstorm_session.py`.

**Outcome: the plan HOLDS.** Only the `NODE_OPTIONAL_FIELDS` line reference was
stale (17, not ~13); approach and all other anchors are valid.

## Goal

Lay the additive, back-compatible data-model groundwork that Phases B/C/D
consume. **No new ops** here — existing ops keep targeting the `_umbrella`
subgraph.

## Scope

### `.aitask-scripts/brainstorm/brainstorm_schemas.py`
- `NODE_OPTIONAL_FIELDS` (line 17): add `module_label` →
  `["plan_file", "reference_files", "module_label"]`.
- Graph-state schema (line 35): the new model adds `current_heads` (map
  `<module>:<node_id>`), repurposes `history` as either the legacy list OR a
  per-module map, and adds optional `module_tasks` / `last_synced_at` maps.
  **Back-compat is load-bearing:** legacy sessions on disk have only
  `current_head` + list-`history`. Do **NOT** add `current_heads` to
  `GRAPH_STATE_REQUIRED` (that would fail every legacy session). Instead require
  "a head is present" via either `current_head` (legacy) or `current_heads`
  (new) — keep `current_head` as a legacy alias of `current_heads["_umbrella"]`.
- `validate_graph_state` (line 101): accept `current_heads` as a map (str→str)
  when present; accept `history` as **either** a list (legacy `_umbrella`
  history) **or** a map (`<module>` → list); validate `module_tasks` and
  `last_synced_at` as maps when present. **Leave `active_dimensions` validated
  as a flat `list`** (re-verified unchanged against t873).

### `.aitask-scripts/brainstorm/brainstorm_dag.py`
- Thread a `module: str = "_umbrella"` parameter (default = back-compat) through
  `get_head` (122), `set_head` (132), `get_node_lineage` (175),
  `next_node_id` (142). Back-compat reader/writer behavior:
  - `get_head(module=...)`: read `current_heads[module]` if the map exists; else
    fall back to legacy `current_head` when `module == "_umbrella"`.
  - `set_head(module=...)`: write `current_heads[module]`; when
    `module == "_umbrella"` also keep legacy `current_head` in sync; append to
    `history[module]` (per-module map), repurposing the legacy list as
    `history["_umbrella"]` on first write to a session that still has a list.
- New helper `is_ancestor_subgraph(source, destination)` — walks the
  parent-of-root chain (reusing `get_parents`); returns True iff `destination`'s
  subgraph is an ancestor of `source`'s. Consumed by Phase B's merge "only up"
  guard. Ancestor → True; sibling/descendant → False.

### `.aitask-scripts/brainstorm/brainstorm_session.py::init_session`
- Seed the new maps alongside the legacy fields in the graph-state dict
  (lines 110–116): `current_heads = {}` initially, then after the root node is
  created `set_head(wt, "n000_init")` populates `current_heads["_umbrella"]`;
  add `module_tasks = {}` and `last_synced_at = {}`. Keep `current_head`,
  `history`, `next_node_id`, `active_dimensions` exactly as today for back-compat.

### Wizard subgraph-selector scaffolding (`brainstorm_app.py`)
- Lands here **only if cheap**; otherwise it belongs to Phase B1 (t756_2).
  **Document the chosen boundary** in Final Implementation Notes so 756_2 knows
  where the line was drawn. Default expectation: defer to B1 (the selector
  touches the most wizard code), unless a trivial no-op scaffold is warranted.

## Reference patterns (reuse, don't fork)
- `brainstorm_schemas.py`: current `GRAPH_STATE_REQUIRED`, `validate_graph_state`,
  `NODE_OPTIONAL_FIELDS`; t873 helpers `extract_dimensions`,
  `group_dimensions_by_prefix`.
- `brainstorm_dag.py`: current single-head `get_head`/`set_head`/
  `get_node_lineage`/`next_node_id`; `get_parents` (for the ancestor walk);
  `get_active_dimensions`.
- `brainstorm_session.py::init_session` current graph-state init.

## Implementation steps
1. Schema: add `module_label` to `NODE_OPTIONAL_FIELDS`; extend
   `validate_graph_state` with back-compat readers for `current_heads`/`history`
   map-or-list, `module_tasks`, `last_synced_at`; keep `active_dimensions` a list.
2. DAG: thread `module="_umbrella"` through the four head/lineage helpers with
   legacy fallbacks; add `is_ancestor_subgraph`.
3. Session init: seed `current_heads`/`module_tasks`/`last_synced_at` maps.
4. Decide + document the wizard-scaffold boundary (here vs Phase B1).

## Verification
- Legacy single-head sessions still load and pass `validate_graph_state`.
- New map fields round-trip (write → read → validate) for a multi-module state.
- `current_head` legacy alias resolves to `current_heads["_umbrella"]` both ways.
- `is_ancestor_subgraph` correctness on a constructed DAG (ancestor → True;
  sibling/descendant → False).
- Existing brainstorm tests still pass:
  `bash tests/test_brainstorm_schemas.py`, `tests/test_brainstorm_dag.py`,
  `tests/test_brainstorm_session.py` (and the broader brainstorm suite as needed).

## Step 9 (Post-Implementation)
On completion follow task-workflow Step 9: review, commit (`feature: … (t756_1)`),
consolidate this plan with Final Implementation Notes (incl. the wizard-scaffold
boundary decision + any notes for sibling tasks), then archive via
`./.aitask-scripts/aitask_archive.sh 756_1`.
