---
Task: t756_2_phase_b_decompose_merge_ops.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_3_phase_c_sync_op.md, aitasks/t756/t756_4_phase_d_tui_status_views.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md (after 756_1 lands)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t756_2 — Phase B: `module_decompose` + `module_merge` ops (paired)

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.2 decompose, §4.4 merge, §4.5 module-aware existing ops, §4.8 fast-track,
§4.10 templates, §5 op-recipe). **Binding conventions:**
`aiplans/p756_brainstorm_modules.md`. **Depends on:** t756_1 (data model).

## Goal
Add the two paired ops that create (`module_decompose`, divergent) and reconcile
(`module_merge`, convergent, up-only) subgraphs, and make existing ops module-aware.
Paired because they share the ancestry-guard validator and the wizard
subgraph-selector machinery.

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

## Scope
- New templates `templates/module_decomposer.md`, `templates/module_merger.md`.
- `brainstorm_crew.py`: add agent types; `register_module_decomposer()`
  (multi-output: one subgraph-root node per module; `--from-sections` slice path vs
  agent-driven; optional `--link-to-task` fast-track via
  `aitask_create.sh --batch --parent <umbrella>` + `module_tasks[M]` write);
  `register_module_merger()` (2-parent destination node; ancestry guard at launch).
  Model after `register_explorer()`.
- `brainstorm_schemas.py`: add the two op-keys to `GROUP_OPERATIONS`; optional
  `subgraph` field on group entries (default `_umbrella`).
- `brainstorm_op_refs.py`: `_OP_INPUT_SECTION` entries.
- `brainstorm_app.py`: `_DESIGN_OPS`, `_WIZARD_OP_TO_AGENT_TYPE`, `_NODE_SELECT_OPS`,
  `_OPERATION_HELP`, `_execute_design_op` branches; insert the **subgraph selector**
  wizard step before node-select; make existing ops module-aware (filter node
  candidates by `module_label`, record `subgraph` in group entry, add prompt
  front-matter "subgraph context: <module_label>").
- UC-3 fast-track functional path = `module_decompose --modules=one + --link-to-task`
  (the polished preset UI is Phase D).

## Reuse t873 section↔dimension helpers (do NOT reinvent)
`module_decomposer` uses `<!-- section: … -->` markers + `component_*` dimensions as
**boundary hints only**. t873_1 already shipped glob expansion + validation in
`brainstorm_sections.py`:
- `dimension_matches_tag(dim_key, tag)` (~233) — exact-or-glob match.
- `get_sections_for_dimension` / `best_section_for_dimension` (~247, ~263).
- `validate_sections(parsed, node_keys=...)` (~164) — flag invented section tags.
Each module root's proposal slice carries the **subset** of dimensions relevant to
it; inherit-never-drop operates within the subgraph; the axis vocabulary stays
session-wide so cross-module compare/`module_merge` stay coherent.

## Reference patterns
- `brainstorm_crew.py::register_explorer` — multi-step node-creating register fn.
- `brainstorm_app.py` wizard step machine + `_execute_design_op`.
- t756_1's `is_ancestor_subgraph` (merge guard) and `set_head(module=...)`.

## Implementation steps
1. Add op-keys, agent types, op-input sections, wizard tuples (all `module_`-prefixed).
2. Write the two templates.
3. `register_module_decomposer()` (incl. `--from-sections`, `--link-to-task`).
4. `register_module_merger()` (incl. ancestry guard at launch).
5. Insert the subgraph-selector wizard step; make existing ops module-aware.

## Verification
- `module_decompose` on `_umbrella` HEAD spawns per-module roots with correct
  `module_label` / `parents` / `current_heads`.
- `module_merge` produces a 2-parent destination node and **refuses** a non-ancestor
  destination (ancestry guard fires before agent input is assembled).
- An existing op (e.g. explore) targeted at a module changes only that subgraph.
- `--link-to-task` creates a child aitask and writes `module_tasks[M]`.
- `--from-sections` slices deterministically when the parent proposal has clean
  section markers.
- Existing brainstorm tests still pass.

## Step 9 (Post-Implementation)
On completion follow task-workflow Step 9: review, commit (`feature: … (t756_2)`),
consolidate this plan with Final Implementation Notes (record the established
op-wiring pattern + notes for 756_3/756_4), then archive via
`./.aitask-scripts/aitask_archive.sh 756_2`.
