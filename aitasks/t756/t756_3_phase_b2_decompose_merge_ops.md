---
priority: high
effort: high
depends: [t756_2]
issue_type: feature
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 17:29
updated_at: 2026-06-02 10:20
---

Phase B2 of the `ait brainstorm` **module decomposition** feature (parent t756).
Adds the two **paired** ops `module_decompose` (divergent) and `module_merge`
(convergent, up-only). Paired because they share the ancestry-guard validator (built
in Phase A) and the subgraph-selector wizard machinery (built in Phase B1, t756_2).
Now thin because B1 already made the wizard module-aware. Depends on Phase B1 (t756_2).

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.2 decompose, §4.4 merge, §4.8 fast-track, §4.10 templates, §5 op-recipe).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`.

## Context
B1 (t756_2) made the wizard subgraph-aware (selector step + existing ops filtered by
`module_label`). B2 adds the two new lifecycle ops on top of that infra:
`module_decompose` forks the DAG into per-module subgraph roots (UC-1); with one
module + `--link-to-task` it is the UC-3 fast-track (§4.8). `module_merge` folds a
refined module subgraph back up into its parent (2-parent output node), guarded
"only up" by `is_ancestor_subgraph` (Phase A).

## IMPORTANT — `module_` prefix everywhere (binding)
Design doc uses bare `decompose`/`merge`; implemented identifiers take `module_`:
| Layer | Names |
|-------|-------|
| op-key (`GROUP_OPERATIONS`, persisted `operation:`) | `module_decompose` · `module_merge` |
| wizard label (`_DESIGN_OPS`) | "Module Decompose" · "Module Merge" |
| agent type (`BRAINSTORM_AGENT_TYPES`, `_WIZARD_OP_TO_AGENT_TYPE`) | `module_decomposer` · `module_merger` |
| template | `templates/module_decomposer.md` · `templates/module_merger.md` |
| register fn | `register_module_decomposer()` · `register_module_merger()` |
| input section (`_OP_INPUT_SECTION`) | "Decomposition Plan" · "Merge-Up Rules" |
("Merge-Up Rules" is distinct from synthesize's existing "Merge Rules".)

## Key Files to Modify
- New templates `templates/module_decomposer.md`, `templates/module_merger.md`.
- `brainstorm_crew.py`: add agent types; `register_module_decomposer()` (multi-output:
  one subgraph-root node per module; `--from-sections` slice path vs agent-driven;
  optional `--link-to-task` fast-track via `aitask_create.sh --batch --parent
  <umbrella>` + `module_tasks[M]` write); `register_module_merger()` (2-parent
  destination node; ancestry guard at launch via `is_ancestor_subgraph`). Model after
  `register_explorer()`.
- `brainstorm_schemas.py`: add the two op-keys to `GROUP_OPERATIONS`.
- `brainstorm_op_refs.py`: `_OP_INPUT_SECTION` entries.
- `brainstorm_app.py`: `_DESIGN_OPS`, `_WIZARD_OP_TO_AGENT_TYPE`, `_NODE_SELECT_OPS`,
  `_OPERATION_HELP`, `_execute_design_op` branches for the two ops. **Reuses** the
  subgraph-selector step from B1 — do not re-add it.
- UC-3 fast-track functional path = `module_decompose --modules=one + --link-to-task`
  (the polished preset UI is Phase D2, t756_6).

## Reuse t873 section↔dimension helpers (do NOT reinvent)
`module_decomposer` uses `<!-- section: … -->` markers + `component_*` dimensions as
**boundary hints only**. t873_1 shipped glob expansion + validation in
`brainstorm_sections.py`:
- `dimension_matches_tag(dim_key, tag)` (~233) — exact-or-glob match.
- `get_sections_for_dimension` / `best_section_for_dimension` (~247, ~263).
- `validate_sections(parsed, node_keys=...)` (~164) — flag invented section tags.
Each module root's proposal slice carries the **subset** of dimensions relevant to it;
inherit-never-drop operates within the subgraph; the axis vocabulary stays
session-wide so cross-module compare/`module_merge` stay coherent.

## Reference Files for Patterns
- `brainstorm_crew.py::register_explorer` — multi-step node-creating register fn.
- B1's subgraph-selector wizard step and `subgraph` group field.
- Phase A's `is_ancestor_subgraph` (merge guard) and `set_head(module=...)`.

## Implementation Plan
1. Add op-keys, agent types, op-input sections, wizard tuples (all `module_`-prefixed).
2. Write the two templates.
3. `register_module_decomposer()` (incl. `--from-sections`, `--link-to-task`).
4. `register_module_merger()` (incl. ancestry guard at launch).
5. Wire `_execute_design_op` branches, reusing B1's subgraph selector.

## Verification Steps
- `module_decompose` on the `_umbrella` HEAD spawns per-module roots with correct
  `module_label` / `parents` / `current_heads`.
- `module_merge` produces a 2-parent destination node and **refuses** a non-ancestor
  destination (ancestry guard fires before agent input is assembled).
- An existing op targeted at a module changes only that subgraph (regression on B1).
- `--link-to-task` creates a child aitask and writes `module_tasks[M]`.
- `--from-sections` slices deterministically when the parent proposal has clean
  section markers.
- Existing brainstorm tests still pass.
