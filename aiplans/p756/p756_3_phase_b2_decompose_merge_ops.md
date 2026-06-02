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

## Final Implementation Notes

- **Actual work done:** Implemented `module_decompose` and `module_merge` as
  first-class brainstorm operations with schemas, op refs, TUI flow, crew
  registration, templates, apply paths, DAG badge colors, code-agent defaults,
  and focused tests.
- **Deviations from plan:** Added a direct deterministic
  `apply_module_decompose_from_sections()` path instead of treating
  `from_sections` as only an agent instruction. This better matches the task's
  required slice-without-agent behavior.
- **Issues encountered:** The normal `aitask_create.sh --batch --commit` path
  failed once while creating risk mitigation follow-ups due to task-id claiming
  retry exhaustion. Standalone `aitask_claim_id.sh --claim` then succeeded, so
  reserved IDs `905` and `906` were used for the two mitigation tasks. Main-repo
  `git add` required escalated permissions because the Codex sandbox mounted
  `.git` read-only for regular commands.
- **Key decisions:** Module agent outputs use explicit delimiters:
  decomposer emits repeated `MODULE_NODE` blocks while merger emits the normal
  single-node `NODE_YAML` + `PROPOSAL` format. Group metadata records module
  options and source/destination subgraphs so apply can run from persisted state
  after app restarts.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** The following contracts are now available for
  t756_4/t756_5/t756_6:
- Added the `module_decompose` / `module_merge` op keys, operation refs, DAG badge
  colors, TUI labels/help, and code-agent defaults. New agent types are
  `module_decomposer` and `module_merger`.
- Added `templates/module_decomposer.md` and `templates/module_merger.md`.
  `module_decomposer` emits repeated `MODULE_NODE` blocks; `module_merger` emits
  the normal single-node `NODE_YAML` + `PROPOSAL` blocks.
- Added `register_module_decomposer()` and `register_module_merger()` in
  `brainstorm_crew.py`. The merger registration enforces `is_ancestor_subgraph`
  before launch and reserves a destination node id.
- Added apply paths in `brainstorm_session.py`:
  - `apply_module_decomposer_output()` creates one root per module, tags
    `module_label`, sets each module HEAD/history, records all `nodes_created`,
    and leaves the source subgraph HEAD unchanged.
  - `apply_module_decompose_from_sections()` is the deterministic no-agent
    `from_sections` path. It validates source sections, slices by section name or
    `component_<module>` dimension tag, then creates module roots directly.
  - `apply_module_merger_output()` creates one destination-subgraph node with
    parents `[destination_head, source_head]`; only the destination HEAD advances.
- Added TUI config and launch wiring. `module_decompose` / `module_merge` reuse
  B1's subgraph selector but skip node-select. Module agents are auto-applied via
  a dedicated poller and existing restart scan pattern.
- `--link-to-task` uses `aitask_create.sh --batch --commit --silent --parent ...`
  and writes `module_tasks[module] = <child_id>`. This is intentionally real-child
  creation rather than draft creation so later status/sync tasks have an id to
  resolve.
- Notes for t756_4/t756_5/t756_6: group metadata now carries `modules`,
  `from_sections`, `link_to_task`, `source_subgraph`, and `destination_subgraph`
  where relevant. `module_tasks` is populated only by linked decomposition;
  status/sync should treat absent entries as unlinked.

## Risk

### Code-health risk: high
- The implementation adds new behavior across central brainstorm TUI, crew registration, group persistence, DAG badge rendering, and session apply paths; regressions in existing op launch/apply flows are plausible despite focused tests · severity: high · → mitigation: t906
- The module-agent auto-apply and multi-output parser add a new lifecycle shape that is similar to existing pollers but not yet factored into a shared abstraction, increasing maintenance coupling inside `brainstorm_app.py` and `brainstorm_session.py` · severity: medium · → mitigation: t906

### Goal-achievement risk: medium
- The functional `module_decompose --link-to-task` path shells out to real child-task creation during apply; unit tests cover graph effects but not the full live create/commit/module_tasks workflow · severity: medium · → mitigation: t905
- The module op TUI flow and live agent-launch/apply cycle were not manually exercised in this session, so there is a bounded risk that the implemented wiring does not fully satisfy the intended user workflow even though static/unit checks pass · severity: medium · → mitigation: t905

### Planned mitigations
- timing: after | name: t905 | type: manual_verification | priority: high | effort: medium | addresses: goal-achievement live workflow risks | desc: Manually verify module_decompose/module_merge TUI flows, live agent launch/apply, from_sections behavior, and link-to-task module_tasks persistence.
- timing: after | name: t906 | type: chore | priority: high | effort: medium | addresses: code-health apply and auto-apply risks | desc: Add higher-level integration or contract coverage for module-agent auto-apply, group metadata, multi-output parsing, and linked child-task creation with a stubbed create script.
