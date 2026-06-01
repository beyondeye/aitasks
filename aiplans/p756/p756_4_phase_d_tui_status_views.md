---
Task: t756_4_phase_d_tui_status_views.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_2_phase_b_decompose_merge_ops.md, aitasks/t756/t756_3_phase_c_sync_op.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md, aiplans/archived/p756/p756_2_*.md, aiplans/archived/p756/p756_3_*.md (after they land)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t756_4 — Phase D: TUI surfaces & status views

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.7 fluid status as derived view, §4.8 fast-track preset, §7 Phase D).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`.
**TUI rules:** read `aidocs/tui_conventions.md` before any Textual change.
**Depends on:** t756_3 (and the whole A/B/C stack).

## Goal
Surface module state and ergonomics in the brainstorm TUI. UC-2 (fluid status) is a
**derived render, not a new op** — all inputs already exist after A/B/C. Built last
so it does not chase in-flight schema/op changes.

## Scope (`brainstorm_app.py`, plus `brainstorm_dag_display.py` if the tree lives there)
- **Per-module status badge** computed per §4.7 table — a render, not an op:
  | Status | Computed from |
  |--------|---------------|
  | `unstarted` | only the subgraph root exists |
  | `in_design` | nodes beyond root; no `linked_task` or it is `Ready` |
  | `in_implementation` | `linked_task` is `Implementing` |
  | `implemented` | `linked_task` is `Done` (archived) |
  | `merged` | source HEAD appears in `parents` of some destination-subgraph node |
  | `deferred` | explicit user marker (orthogonal to the rest) |
  Inputs: per-subgraph history counts, `linked_task` frontmatter, `parents` walk,
  new `deferred` marker.
- **"Fast-track this module" wizard preset** — one-pass UI over
  `module_decompose --modules=one + --link-to-task` (functional path landed in 756_2).
- **Dashboard** showing the subgraph tree with per-module sync/merge state.
- **Deferred-module marker** — TUI binding to set `status.deferred=true` (persisted).

## Reuse t873 TUI/dimension helpers (do NOT reinvent)
- `FuzzyCheckList.set_grouped_items(groups)` — `brainstorm_app.py:~1654` — reusable
  grouped/filterable checklist for subgraph selector & dashboard.
- `group_dimensions_by_prefix(dims)` + `extract_dimensions(data)` —
  `brainstorm_schemas.py:~150,~145` — grouped status/dimension views.
- `get_active_dimensions(session_path)` — `brainstorm_dag.py:~116` — scope defaults.

## Reference patterns
- `aidocs/tui_conventions.md` (mandatory).
- Existing `brainstorm_app.py` badge/detail-pane rendering and the t873 glob-aware
  dimension badge-count loop as a model for the status-badge computation.
- `brainstorm_dag_display.py` for the existing DAG/tree render.

## Implementation steps
1. Implement the §4.7 status computation as a pure derived function over existing data.
2. Render the per-module badge in the dashboard/tree.
3. Build the subgraph-tree dashboard (reuse `FuzzyCheckList.set_grouped_items`).
4. Add the "Fast-track this module" preset and the deferred-module toggle binding.

## Verification
- Badges reflect mixed module states (`unstarted`/`in_design`/`in_implementation`/
  `implemented`/`merged`/`deferred`) correctly.
- "Fast-track this module" preset creates a subgraph + linked task in one pass.
- Deferred toggle persists across reload.
- Dashboard renders the subgraph tree with per-module sync/merge state.
- Existing brainstorm tests still pass; follow `aidocs/tui_conventions.md`.
- (Most of the above is human-observable — covered by the aggregate
  manual-verification sibling created alongside these children.)

## Step 9 (Post-Implementation)
On completion follow task-workflow Step 9: review, commit (`feature: … (t756_4)`),
consolidate this plan with Final Implementation Notes, then archive via
`./.aitask-scripts/aitask_archive.sh 756_4` — this is the last child, so parent t756
auto-archives when 756_4 completes.
