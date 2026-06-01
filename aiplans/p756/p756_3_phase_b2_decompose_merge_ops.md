---
Task: t756_3_phase_b2_decompose_merge_ops.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_2_phase_b1_module_aware_wizard_infra.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_5_phase_d1_status_views.md, aitasks/t756/t756_6_phase_d2_fast_track_preset.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md, aiplans/archived/p756/p756_2_*.md (after they land)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t756_3 — Phase B2: `module_decompose` + `module_merge` ops (paired)

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.2 decompose, §4.4 merge, §4.8 fast-track, §4.10 templates, §5 op-recipe).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`. **Depends on:** t756_2
(module-aware wizard infra) → t756_1 (data model).

## Goal
Add the two paired lifecycle ops on top of B1's module-aware wizard:
`module_decompose` (divergent — forks per-module subgraph roots, UC-1; with one module
+ `--link-to-task` = UC-3 fast-track) and `module_merge` (convergent, up-only —
2-parent node guarded by `is_ancestor_subgraph`). Thin now because B1 already built the
subgraph-selector.

## IMPORTANT — `module_` prefix everywhere (binding)
| Layer | Names |
|-------|-------|
| op-key (`GROUP_OPERATIONS`, persisted `operation:`) | `module_decompose` · `module_merge` |
| wizard label (`_DESIGN_OPS`) | "Module Decompose" · "Module Merge" |
| agent type (`BRAINSTORM_AGENT_TYPES`, `_WIZARD_OP_TO_AGENT_TYPE`) | `module_decomposer` · `module_merger` |
| template | `templates/module_decomposer.md` · `templates/module_merger.md` |
| register fn | `register_module_decomposer()` · `register_module_merger()` |
| input section (`_OP_INPUT_SECTION`) | "Decomposition Plan" · "Merge-Up Rules" |
("Merge-Up Rules" distinct from synthesize's "Merge Rules".)

## Scope
- New templates `templates/module_decomposer.md`, `templates/module_merger.md`.
- `brainstorm_crew.py`: add agent types; `register_module_decomposer()` (multi-output;
  `--from-sections` slice vs agent-driven; optional `--link-to-task` fast-track via
  `aitask_create.sh --batch --parent <umbrella>` + `module_tasks[M]` write);
  `register_module_merger()` (2-parent destination node; ancestry guard at launch).
- `brainstorm_schemas.py`: add the two op-keys to `GROUP_OPERATIONS`.
- `brainstorm_op_refs.py`: `_OP_INPUT_SECTION` entries.
- `brainstorm_app.py`: `_DESIGN_OPS`, `_WIZARD_OP_TO_AGENT_TYPE`, `_NODE_SELECT_OPS`,
  `_OPERATION_HELP`, `_execute_design_op` branches. **Reuse** B1's subgraph selector.
- UC-3 fast-track functional path = `module_decompose --modules=one + --link-to-task`
  (polished preset UI is Phase D2, t756_6).

## Reuse t873 section↔dimension helpers (do NOT reinvent)
`module_decomposer` boundary hints use `<!-- section: … -->` markers + `component_*`
dimensions: `dimension_matches_tag` / `get_sections_for_dimension` /
`best_section_for_dimension` / `validate_sections(parsed, node_keys=...)` (all in
`brainstorm_sections.py`, t873_1). Each module root's slice carries the subset of
dimensions relevant to it; the axis vocabulary stays session-wide.

## Reference patterns
- `brainstorm_crew.py::register_explorer` — multi-step node-creating register fn.
- B1's subgraph-selector wizard step + `subgraph` group field.
- Phase A's `is_ancestor_subgraph` and `set_head(module=...)`.

## Implementation steps
1. Add op-keys, agent types, op-input sections, wizard tuples (`module_`-prefixed).
2. Write the two templates.
3. `register_module_decomposer()` (incl. `--from-sections`, `--link-to-task`).
4. `register_module_merger()` (incl. ancestry guard at launch).
5. Wire `_execute_design_op` branches, reusing B1's subgraph selector.

## Verification
- `module_decompose` on `_umbrella` HEAD spawns per-module roots with correct
  `module_label` / `parents` / `current_heads`.
- `module_merge` produces a 2-parent destination node and refuses a non-ancestor
  destination (guard fires before agent input assembly).
- An existing op targeted at a module changes only that subgraph (B1 regression).
- `--link-to-task` creates a child aitask and writes `module_tasks[M]`.
- `--from-sections` slices deterministically on clean section markers.
- Existing brainstorm tests still pass.

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_3)`), consolidate this
plan with Final Implementation Notes (op-wiring pattern + notes for 756_4/756_6),
archive via `./.aitask-scripts/aitask_archive.sh 756_3`.
