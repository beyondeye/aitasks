---
priority: medium
effort: high
depends: [t756_3]
issue_type: feature
status: Ready
labels: [ait_brainstorm, brainstom_modules, tui]
created_at: 2026-06-01 16:46
updated_at: 2026-06-01 16:46
---

Phase D of the `ait brainstorm` **module decomposition** feature (parent t756).
Adds the TUI surfaces and the derived per-module **status view**. Built last because
it depends on the Phase A/B/C data model + ops being settled. Depends on Phase C
(t756_3).

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.7 fluid status as a derived view, §4.8 fast-track preset, §7 Phase D).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`. **TUI rules:**
read `aidocs/tui_conventions.md` before any Textual change.

## Context
UC-2 (fluid status) is a **derived render, not a new op** — all inputs already exist
after A/B/C. This child surfaces module state and ergonomics in the brainstorm TUI:
a per-module status badge, a subgraph-tree dashboard, the polished "Fast-track this
module" preset on top of `module_decompose --link-to-task`, and a deferred-module marker.

## Key Files to Modify
- `brainstorm_app.py` (and `brainstorm_dag_display.py` if the tree render lives there):
  - **Per-module status badge** computed per §4.7 table:
    `unstarted` (only subgraph root) / `in_design` (nodes beyond root, no/Ready
    `linked_task`) / `in_implementation` (`linked_task` Implementing) / `implemented`
    (`linked_task` Done) / `merged` (source HEAD appears in a destination node's
    `parents`) / `deferred` (explicit marker). Inputs: per-subgraph history counts,
    `linked_task` frontmatter, `parents` walk, new `deferred` marker. **A render, not an op.**
  - **"Fast-track this module" wizard preset** — one-pass UI over
    `module_decompose --modules=one + --link-to-task` (functional path landed in Phase B).
  - **Dashboard** showing the subgraph tree with per-module sync/merge state.
  - **Deferred-module marker** — TUI binding to set `status.deferred=true` (persisted).

## Reuse t873 TUI/dimension helpers (do NOT reinvent)
- `FuzzyCheckList.set_grouped_items(groups)` — `brainstorm_app.py:~1654` — reusable
  grouped/filterable checklist for the subgraph selector & dashboard.
- `group_dimensions_by_prefix(dims)` + `extract_dimensions(data)` —
  `brainstorm_schemas.py:~150,~145` — grouped status/dimension views.
- `get_active_dimensions(session_path)` — `brainstorm_dag.py:~116` — scope defaults.

## Reference Files for Patterns
- `aidocs/tui_conventions.md` (mandatory for Textual edits).
- Existing `brainstorm_app.py` badge/detail-pane rendering and the t873 dimension
  badge-count loop (glob-aware) as a model for the status-badge computation.
- `brainstorm_dag_display.py` for the existing DAG/tree render.

## Implementation Plan
1. Implement the §4.7 status computation as a pure derived function over existing data.
2. Render the per-module badge in the dashboard/tree.
3. Build the subgraph-tree dashboard view (reuse `FuzzyCheckList.set_grouped_items`).
4. Add the "Fast-track this module" preset and the deferred-module toggle binding.

## Verification Steps
- Manual TUI walk-through (covered by the aggregate manual-verification sibling):
  badges reflect mixed module states; fast-track preset creates a subgraph + linked
  task in one pass; deferred toggle persists across reload.
- Existing brainstorm tests still pass; follow `aidocs/tui_conventions.md`.
