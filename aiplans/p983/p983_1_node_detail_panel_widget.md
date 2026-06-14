---
Task: t983_1_node_detail_panel_widget.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_1_node_detail_panel_widget
Branch: aitask/t983_1_node_detail_panel_widget
Base branch: main
---

# p983_1 — Extract `NodeDetailPanel` widget

Foundation child of the t983 brainstorm-TUI IA redesign. See parent decomposition
plan for the full IA. **Testability-first:** land a reusable widget + its pilot
test; pure extraction, no UX change.

## Goal
The new Browse tab (t983_3) hosts ONE shared node-detail panel. Today the inline
panes are already DRY via `_render_node_detail_widgets`
(`.aitask-scripts/brainstorm/brainstorm_app.py:5768`), shared by
`_show_node_detail` (:5858) and `_show_dag_node_detail` (:5868). `NodeDetailModal`
(:1047) keeps a separate text-metadata path (:1095-1117) + proposal/minimap view.
Wrap the shared renderer in a `NodeDetailPanel(Widget)` and reconcile the modal.

## Steps
1. `class NodeDetailPanel(Widget)` owning a title `Label` + content `Container`;
   `update(node_id)` → `_render_node_detail_widgets` then mount widgets.
2. Repoint `_show_node_detail` / `_show_dag_node_detail` to drive a panel instance
   (keep current `#dash_node_*` / `#dag_node_*` behavior identical).
3. Fold `NodeDetailModal.on_mount` metadata extraction onto the shared renderer;
   keep its proposal-markdown + `SectionMinimap` tab unchanged.

## Verification
- New `tests/test_brainstorm_node_detail_panel.py` — `run_test` pilot asserts the
  panel renders the expected fields + dimension rows for a fixture node.
- Keep green: `test_brainstorm_node_detail_minimap.py`, `test_brainstorm_node_export.py`.
- Manual: `ait brainstorm <session>` → focus a node; detail unchanged.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_1`.
