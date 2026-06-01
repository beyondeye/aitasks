---
priority: medium
effort: high
depends: [t756_4]
issue_type: feature
status: Ready
labels: [ait_brainstorm, brainstom_modules, tui]
created_at: 2026-06-01 17:30
updated_at: 2026-06-01 17:30
---

Phase D1 of the `ait brainstorm` **module decomposition** feature (parent t756).
The **status-visualization** half of the original Phase D: the §4.7 derived status
view + per-module badges + subgraph-tree dashboard + deferred marker. The "Fast-track
this module" wizard preset is split out to Phase D2 (t756_6). Depends on Phase C
(t756_4) — needs sync state, merge ('merged' status), and the full data model.

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.7 fluid status as a derived view, §7 Phase D). **Binding conventions:**
`aiplans/p756_brainstorm_modules.md`. **TUI rules:** read `aidocs/tui_conventions.md`.

## Context
UC-2 (fluid status) is a **derived render, not a new op** — all inputs already exist
after A/B/C. This child surfaces module state: a per-module status badge, a
subgraph-tree dashboard, and the deferred-module marker.

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
- **Dashboard** showing the subgraph tree with per-module sync/merge state.
- **Deferred-module marker** — TUI binding to set `status.deferred=true` (persisted).

## Reuse t873 TUI/dimension helpers (do NOT reinvent)
- `FuzzyCheckList.set_grouped_items(groups)` — `brainstorm_app.py:~1654` — reusable
  grouped/filterable checklist for the dashboard.
- `group_dimensions_by_prefix(dims)` + `extract_dimensions(data)` —
  `brainstorm_schemas.py:~150,~145` — grouped status/dimension views.
- `get_active_dimensions(session_path)` — `brainstorm_dag.py:~116` — scope defaults.

## Reference Files for Patterns
- `aidocs/tui_conventions.md` (mandatory).
- Existing `brainstorm_app.py` badge/detail-pane rendering and the t873 glob-aware
  dimension badge-count loop as a model for the status-badge computation.
- `brainstorm_dag_display.py` for the existing DAG/tree render.

## Implementation Plan
1. Implement the §4.7 status computation as a pure derived function over existing data.
2. Render the per-module badge in the dashboard/tree.
3. Build the subgraph-tree dashboard (reuse `FuzzyCheckList.set_grouped_items`).
4. Add the deferred-module toggle binding (persist `status.deferred`).

## Verification Steps
- Per-module status badges reflect mixed states correctly
  (`unstarted`/`in_design`/`in_implementation`/`implemented`/`merged`/`deferred`).
- Deferred toggle persists across a TUI reload.
- Dashboard renders the subgraph tree with per-module sync/merge state.
- Existing brainstorm tests still pass; follow `aidocs/tui_conventions.md`.
- (Human-observable behavior is covered by the aggregate manual-verification sibling.)
