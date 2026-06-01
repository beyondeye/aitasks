---
Task: t756_2_phase_b1_module_aware_wizard_infra.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_3_phase_b2_decompose_merge_ops.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_5_phase_d1_status_views.md, aitasks/t756/t756_6_phase_d2_fast_track_preset.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md (after 756_1 lands)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t756_2 — Phase B1: module-aware wizard infrastructure

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.5 existing-ops-become-module-aware; §7 Phase A subgraph-selector note).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`. **TUI rules:**
`aidocs/tui_conventions.md`. **Depends on:** t756_1 (data model).

## Goal
Make the *existing* brainstorm ops subgraph-scoped and add the shared subgraph-selector
wizard step that the new ops (B2, t756_3) build on. **No new ops here.** Split out of
the original Phase B because §4.5 calls this "the chunk of work that touches the most
existing code"; it also resolves the A/B boundary ambiguity flagged in t756_1's plan.

## Scope
- `brainstorm_app.py`:
  - Insert a **subgraph-selector** wizard step before node-select. Default =
    most-recently-touched subgraph; fallback `_umbrella`. Auto-select / invisible when
    only `_umbrella` exists (existing flows unchanged).
  - `_NODE_SELECT_OPS` step 2 filters node candidates by
    `module_label == <selected subgraph>`.
  - Record the chosen `subgraph` in the op's `br_groups.yaml` group entry.
- `brainstorm_schemas.py`: optional `subgraph` field on group entries (default
  `_umbrella` for back-compat).
- `brainstorm_crew.py` + existing templates (explorer/comparator/synthesizer/detailer/
  patcher): add "subgraph context: <module_label>" front-matter; thread module context
  through `register_*()` input assembly.

## Reference patterns
- `brainstorm_app.py` wizard step machine (op-picker → node-select → optional
  section-select → config → confirm) and `_execute_design_op`.
- t756_1's `get_head(module=...)` / `set_head(module=...)` and `current_heads` map.

## Implementation steps
1. Add the optional `subgraph` group field (default `_umbrella`).
2. Insert the subgraph-selector wizard step (auto-skip when only `_umbrella`).
3. Filter node-select candidates by `module_label`.
4. Record `subgraph` in group entries; add "subgraph context" template front-matter.

## Verification
- With a single subgraph (`_umbrella` only), all existing ops behave exactly as before
  (selector auto-selects, no visible change).
- On a constructed multi-module state (Phase A fixture), the selector lists subgraphs
  and node-select filters candidates by `module_label`.
- Group entries record `subgraph`; legacy groups without it default to `_umbrella`.
- Existing brainstorm tests still pass; follow `aidocs/tui_conventions.md`.

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_2)`), consolidate this
plan with Final Implementation Notes (note the subgraph-selector contract so 756_3 can
reuse it), archive via `./.aitask-scripts/aitask_archive.sh 756_2`.
