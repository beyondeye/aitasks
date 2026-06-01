---
priority: high
effort: high
depends: [t756_1]
issue_type: feature
status: Ready
labels: [ait_brainstorm, brainstom_modules]
created_at: 2026-06-01 16:45
updated_at: 2026-06-01 16:45
---

Phase B of the `ait brainstorm` **module decomposition** feature (parent t756).
Adds the two **paired** ops `module_decompose` (divergent) and `module_merge`
(convergent), and makes the existing ops module-aware. Paired in one task because
they share the ancestry-guard validator and the wizard subgraph-selector machinery
(design doc §7 Phase B rationale). Depends on Phase A (t756_1) data model.

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.2 decompose, §4.4 merge, §4.5 existing-ops-become-module-aware, §4.8 fast-track,
§4.10 templates, §5 op-recipe). **Binding conventions:** `aiplans/p756_brainstorm_modules.md`.

## Context
Phase A added per-subgraph HEADs and `module_label`. Phase B adds the ops that
create and reconcile subgraphs. `module_decompose` forks the DAG into per-module
subgraph roots (UC-1); with one module + `--link-to-task` it is the UC-3 fast-track
(§4.8). `module_merge` folds a refined module subgraph back up into its parent
(2-parent output node), guarded "only up". Existing ops gain a subgraph-selector
wizard step so refinement is scoped to one module.

## IMPORTANT — `module_` prefix everywhere (binding, from parent plan)
The design doc uses bare `decompose`/`merge`, but the **implemented** identifiers
take a `module_` prefix to avoid collision with git/syncer/synthesize "merge"/"sync":
- op-key (`GROUP_OPERATIONS`, persisted `operation:`): `module_decompose`, `module_merge`
- wizard label (`_DESIGN_OPS`): "Module Decompose", "Module Merge"
- agent type (`BRAINSTORM_AGENT_TYPES`, `_WIZARD_OP_TO_AGENT_TYPE`):
  `module_decomposer`, `module_merger`
- template file: `templates/module_decomposer.md`, `templates/module_merger.md`
- register fn: `register_module_decomposer()`, `register_module_merger()`
- input section (`_OP_INPUT_SECTION`): "Decomposition Plan", "Merge-Up Rules"
  (distinct from synthesize's existing "Merge Rules").

## Key Files to Modify
- New templates `templates/module_decomposer.md`, `templates/module_merger.md`.
- `brainstorm_crew.py`: add `module_decomposer`/`module_merger` to
  `BRAINSTORM_AGENT_TYPES`; `register_module_decomposer()` (multi-output: one
  subgraph-root node per module; `--from-sections` slice path vs agent-driven;
  optional `--link-to-task` fast-track via
  `aitask_create.sh --batch --parent <umbrella>`), `register_module_merger()`
  (2-parent output node in destination subgraph; ancestry guard at launch).
  Model after `register_explorer()`.
- `brainstorm_schemas.py`: add `module_decompose`, `module_merge` to
  `GROUP_OPERATIONS`; optional `subgraph` field on group entries (default `_umbrella`).
- `brainstorm_op_refs.py`: `_OP_INPUT_SECTION` += `module_decompose:"Decomposition Plan"`,
  `module_merge:"Merge-Up Rules"`.
- `brainstorm_app.py`: `_DESIGN_OPS`, `_WIZARD_OP_TO_AGENT_TYPE`, `_NODE_SELECT_OPS`,
  `_OPERATION_HELP`, `_execute_design_op` branches; insert the **subgraph selector**
  wizard step before node-select; make existing ops module-aware (filter node
  candidates by `module_label`, record `subgraph` in group entry, add prompt
  front-matter "subgraph context: <module_label>").
- UC-3 fast-track = `module_decompose --modules=one + --link-to-task` (functional
  one-step path here; the polished preset UI is Phase D).

## Reuse t873 section↔dimension helpers (do NOT reinvent)
The `module_decomposer` uses `<!-- section: … -->` markers and `component_*`
dimensions as **boundary hints only**. t873_1 already shipped glob/prefix expansion
+ validation — consume these from `brainstorm_sections.py`:
- `dimension_matches_tag(dim_key, tag)` (line ~233) — exact-or-glob match.
- `get_sections_for_dimension(parsed, dim)` / `best_section_for_dimension(parsed, dim)`
  (lines ~247, ~263) — section lookup by dimension.
- `validate_sections(parsed, node_keys=...)` (line ~164) — flag invented section
  tags against a node's real dimension keys.
Each module subgraph root's proposal slice carries the **subset** of dimensions
relevant to that module; the inherit-never-drop rule operates within the subgraph.
The axis vocabulary stays session-wide so cross-module compare/`module_merge` stay
coherent.

## Reference Files for Patterns
- `brainstorm_crew.py::register_explorer` (multi-step register fn; node-creating op).
- `brainstorm_app.py` existing wizard step machine (step1 op-picker → step2
  node-select → optional section-select → config → confirm) and `_execute_design_op`.
- Phase A's `is_ancestor_subgraph` (merge guard) and `set_head(module=...)`.

## Implementation Plan
1. Add op-keys + agent types + op-input sections + wizard tuples (all `module_`-prefixed).
2. Write the two templates.
3. Implement `register_module_decomposer()` (incl. `--from-sections` and
   `--link-to-task`) and `register_module_merger()` (incl. ancestry guard).
4. Insert the subgraph-selector wizard step; make existing ops module-aware.

## Verification Steps
- `module_decompose` on `_umbrella` HEAD spawns per-module roots with correct
  `module_label`/`parents`/`current_heads`.
- `module_merge` produces a 2-parent destination node and **refuses** a non-ancestor
  destination.
- An existing op (e.g. explore) targeted at a module changes only that subgraph.
- `--link-to-task` creates a child aitask and writes `module_tasks[M]`.
- Existing brainstorm tests still pass.
