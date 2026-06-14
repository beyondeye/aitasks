---
Task: t983_5_node_hub_overlay.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_5_node_hub_overlay
Branch: aitask/t983_5_node_hub_overlay
Base branch: main
---

# p983_5 — Node Hub overlay (Enter)

Child of t983. `Enter` on the cursor node opens a Node Hub: Detail (the shared
`NodeDetailPanel`, t983_1) + an Operations entry opening the t983_4 dialog.
Gives t983_6/_7 a second launch surface besides `A`.

## Goal
Unify the node-detail entry points behind one Hub overlay.

## Steps
1. Build `NodeHub` overlay/screen: a Detail tab hosting `NodeDetailPanel` seeded
   with the cursor node (keep proposal-markdown + minimap), plus an Operations
   entry → opens the Operations dialog contextual to the current selection.
2. Repoint `Enter` (`action_open_node_detail`,
   `.aitask-scripts/brainstorm/brainstorm_app.py:3914`) and the Graph
   `DAGDisplay.NodeSelected → NodeDetailModal` path (:5942) to open the Hub.
3. No auto-open on mere cursor movement (avoid modal-spam). Remove now-redundant
   direct `NodeDetailModal` opens.

## Verification
- Pilot: `tests/test_brainstorm_node_hub.py` — `Enter` opens the Hub; Detail
  renders the cursor node; Operations entry opens the dialog.
- Suite `tests/test_brainstorm*.py` green.
- Manual: `Enter` in both Browse views (list + graph) opens the Hub.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_5`.
