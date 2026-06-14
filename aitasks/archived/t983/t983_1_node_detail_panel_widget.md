---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 11:38
updated_at: 2026-06-14 12:57
completed_at: 2026-06-14 12:57
---

## Context
Foundation child of t983 (brainstorm TUI IA redesign). The target IA hosts ONE
shared node-detail panel in the new Browse tab. Today the two inline detail panes
are **already deduplicated** via `_render_node_detail_widgets`
(`.aitask-scripts/brainstorm/brainstorm_app.py:5768`), shared by
`_show_node_detail` (Dashboard, :5858) and `_show_dag_node_detail` (Graph, :5868).
The remaining duplication is `NodeDetailModal` (:1047), which keeps its own
text-metadata path (:1095-1117) plus a proposal-markdown + `SectionMinimap` view
the inline panes lack. This child extracts a reusable widget so Browse (t983_3)
can host a single instance, and reconciles the modal's metadata path.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add `NodeDetailPanel(Widget)`
  wrapping `_render_node_detail_widgets` + its title; repoint `_show_node_detail`
  / `_show_dag_node_detail` to drive a `NodeDetailPanel` instance; fold
  `NodeDetailModal.on_mount` metadata path onto the shared renderer.
- `tests/test_brainstorm_node_detail_panel.py` — NEW.

## Reference Files for Patterns
- `_render_node_detail_widgets` (:5768) — the shared renderer to wrap.
- `NodeDetailModal` (:1047) — metadata path (:1095-1117) + proposal/minimap.
- `tests/test_brainstorm_node_detail_minimap.py`, `tests/test_brainstorm_node_export.py`
  — must stay green.

## Implementation Plan
1. Define `NodeDetailPanel(Widget)` owning a title `Label` + a content
   `Container`; `update(node_id)` calls `_render_node_detail_widgets` and mounts.
2. Replace the ad-hoc `#dash_node_*` / `#dag_node_*` mount logic in
   `_show_node_detail` / `_show_dag_node_detail` with the panel's `update`.
3. Reconcile `NodeDetailModal`'s metadata extraction to call the same renderer
   (keep the modal's proposal-markdown + minimap tab unchanged).
4. No behavior change for the user — pure extraction.

## Verification
- Pure/widget: `tests/test_brainstorm_node_detail_panel.py` — `run_test` pilot
  asserts the panel renders the expected fields/dimension rows for a fixture node.
- Regression: `test_brainstorm_node_detail_minimap.py`, `node_export` green.
- Manual: `ait brainstorm <session>` → focus a node, detail renders as before.
