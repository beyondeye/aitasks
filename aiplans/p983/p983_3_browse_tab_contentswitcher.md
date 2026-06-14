---
Task: t983_3_browse_tab_contentswitcher.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_3_browse_tab_contentswitcher
Branch: aitask/t983_3_browse_tab_contentswitcher
Base branch: main
---

# p983_3 — Browse tab (Dashboard + Graph → one tab)

Child of t983 — **highest structural seam**, de-risked by landing on the
already-tested `NodeDetailPanel` (t983_1) + `NodeSelection` (t983_2) + a pure
view-state helper.

## Goal
Collapse `tab_dashboard` (D) + `tab_dag` (G) (compose
`.aitask-scripts/brainstorm/brainstorm_app.py:3540-3559`) into one `tab_browse`
with a graph⇄list toggle (`v`, graph default, per-session persist), ONE shared
`NodeDetailPanel`, and `space`-marking via `NodeSelection`.

## Steps
1. **Pure** view-state helper: given session state → current view + `toggle` that
   flips and persists (graph default). Unit-test headless.
2. `tab_browse` hosts a Textual `ContentSwitcher` over list `#node_list_pane` ⇄
   graph `DAGDisplay#dag_content` + a persistent shared `NodeDetailPanel` sibling
   (survives toggles). NOT nested tabs (re-introduces the smell being removed).
3. Unify the two focus→detail triggers — Dashboard `on_descendant_focus` (:5923)
   → pane; Graph `DAGDisplay.NodeSelected` (:5942) → modal — into one
   "selection-changed → render panel" handler.
4. `v` → flip switcher + persist; `space` → `NodeSelection` mark/toggle on the
   cursor node, reflected in both views.
5. Update tab-switch action + `check_action`/`_TAB_SCOPED_ACTIONS` enough for
   Browse to work (full deconflict is t983_9). Decide placement of the
   dashboard-only `#session_status_info`/`#module_status_info` labels
   (:3544-3547) — Browse column for now; header strip lands in t983_9.

## Verification
- Pure unit: `tests/test_brainstorm_browse_view.py` — default=graph; toggle flips
  + persists across reload.
- Pilot: `v` switches the `ContentSwitcher`; panel persists across toggles;
  `space` marking reflected in `NodeSelection`.
- Update + green **in this child**: `test_brainstorm_node_export.py` tab-id
  assertions; full `tests/test_brainstorm*.py`.
- Manual: `ait brainstorm <session>` → `v` toggles, shared detail, `space` marks.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_3`.
