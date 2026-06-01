---
Task: t756_5_phase_d1_status_views.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_2_phase_b1_module_aware_wizard_infra.md, aitasks/t756/t756_3_phase_b2_decompose_merge_ops.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_6_phase_d2_fast_track_preset.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md … p756_4_*.md (after they land)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t756_5 — Phase D1: status views (badges + dashboard + deferred marker)

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.7 fluid status as a derived view, §7 Phase D). **Binding conventions:**
`aiplans/p756_brainstorm_modules.md`. **TUI rules:** `aidocs/tui_conventions.md`.
**Depends on:** t756_4 (sync state, merge 'merged' status, full data model).

## Goal
The status-visualization half of the original Phase D. UC-2 (fluid status) is a
**derived render, not a new op** — all inputs already exist after A/B/C. Surface a
per-module status badge, a subgraph-tree dashboard, and the deferred-module marker.
(The fast-track wizard preset is split to D2, t756_6.)

## Scope (`brainstorm_app.py`, plus `brainstorm_dag_display.py` if the tree lives there)
- **Per-module status badge** per §4.7 — a render, not an op:
  | Status | Computed from |
  |--------|---------------|
  | `unstarted` | only the subgraph root exists |
  | `in_design` | nodes beyond root; no `linked_task` or it is `Ready` |
  | `in_implementation` | `linked_task` is `Implementing` |
  | `implemented` | `linked_task` is `Done` (archived) |
  | `merged` | source HEAD appears in `parents` of some destination-subgraph node |
  | `deferred` | explicit user marker (orthogonal) |
  Inputs: per-subgraph history counts, `linked_task` frontmatter, `parents` walk,
  new `deferred` marker.
- **Dashboard** showing the subgraph tree with per-module sync/merge state.
- **Deferred-module marker** — TUI binding to set `status.deferred=true` (persisted).

## Reuse t873 TUI/dimension helpers (do NOT reinvent)
- `FuzzyCheckList.set_grouped_items(groups)` — `brainstorm_app.py:~1654`.
- `group_dimensions_by_prefix` + `extract_dimensions` — `brainstorm_schemas.py:~150,~145`.
- `get_active_dimensions(session_path)` — `brainstorm_dag.py:~116`.

## Reference patterns
- `aidocs/tui_conventions.md` (mandatory).
- Existing `brainstorm_app.py` badge/detail-pane rendering and the t873 glob-aware
  dimension badge-count loop.
- `brainstorm_dag_display.py` for the existing DAG/tree render.

## Implementation steps
1. Implement the §4.7 status computation as a pure derived function over existing data.
2. Render the per-module badge in the dashboard/tree.
3. Build the subgraph-tree dashboard (reuse `FuzzyCheckList.set_grouped_items`).
4. Add the deferred-module toggle binding (persist `status.deferred`).

## Verification
- Per-module status badges reflect mixed states correctly
  (`unstarted`/`in_design`/`in_implementation`/`implemented`/`merged`/`deferred`).
- Deferred toggle persists across a TUI reload.
- Dashboard renders the subgraph tree with per-module sync/merge state.
- Existing brainstorm tests still pass; follow `aidocs/tui_conventions.md`.
- (Human-observable behavior covered by the aggregate manual-verification sibling.)

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_5)`), consolidate this
plan with Final Implementation Notes, archive via
`./.aitask-scripts/aitask_archive.sh 756_5`.
