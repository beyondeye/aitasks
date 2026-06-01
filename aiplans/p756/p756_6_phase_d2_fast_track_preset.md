---
Task: t756_6_phase_d2_fast_track_preset.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_2_phase_b1_module_aware_wizard_infra.md, aitasks/t756/t756_3_phase_b2_decompose_merge_ops.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_5_phase_d1_status_views.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md … p756_5_*.md (after they land)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t756_6 — Phase D2: "Fast-track this module" wizard preset

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.8 UC-3 = decompose --modules=one + linked_task; §7 Phase D). **Binding
conventions:** `aiplans/p756_brainstorm_modules.md`. **TUI rules:**
`aidocs/tui_conventions.md`. **Depends on:** t756_5.

## Goal
The ergonomics half of the original Phase D: a polished one-pass "Fast-track this
module" wizard preset over the functional `module_decompose --link-to-task` path that
landed in B2 (t756_3). UC-3 is just `module_decompose` parameterised — this is a
presentation/UX layer, **not** a new op.

## Scope (`brainstorm_app.py`)
- "Fast-track this module" wizard **preset** — a one-step entry driving
  `module_decompose` with a single module name + `--link-to-task` in one pass
  (subgraph root + linked aitask created together).
- Surface it alongside the multi-module decompose path; both route through the same
  `register_module_decomposer()` call (§4.8 — no new op).

## Reuse t873 TUI helpers (do NOT reinvent)
- `FuzzyCheckList.set_grouped_items(groups)` — `brainstorm_app.py:~1654` — for any
  grouped/filterable selection in the preset UI.

## Reference patterns
- `aidocs/tui_conventions.md` (mandatory).
- B2's (t756_3) `register_module_decomposer()` `--link-to-task` path + wizard branch.
- D1's (t756_5) dashboard/badge surfaces this preset sits alongside.

## Implementation steps
1. Add the "Fast-track this module" preset entry to the wizard.
2. Wire it to a single-module `module_decompose --link-to-task` invocation in one pass.
3. Confirm it reuses the B2 functional path (no duplicate op logic).

## Verification
- The preset creates a subgraph + linked task in a single pass (one user invocation).
- The preset routes through the same `register_module_decomposer()` as the
  multi-module path (no forked op logic).
- Existing brainstorm tests still pass; follow `aidocs/tui_conventions.md`.
- (Human-observable behavior covered by the aggregate manual-verification sibling.)

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_6)`), consolidate this
plan with Final Implementation Notes, archive via
`./.aitask-scripts/aitask_archive.sh 756_6`. This is the last *implementation* child;
the manual-verification sibling (t756_7) runs after it.
