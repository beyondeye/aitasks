---
priority: medium
effort: medium
depends: [t983_4]
issue_type: refactor
status: Ready
labels: [brainstorming, tui, ait_brainstorm]
created_at: 2026-06-14 11:39
updated_at: 2026-06-14 11:39
---

## Context
Child of t983. Introduces the **Node Hub** overlay opened by `Enter` on the
cursor node: a Detail tab (the shared `NodeDetailPanel` from t983_1) plus an
**Operations** entry that opens the t983_4 Operations dialog. This unifies the
node-detail entry points and gives the wizard re-host (t983_6) and Compare
overlay (t983_7) a second launch surface besides `A`.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add `NodeHub` overlay/screen;
  repoint `Enter` (`action_open_node_detail`, :3914) and the Graph
  `DAGDisplay.NodeSelected → NodeDetailModal` path (:5942) to open the Hub.
- `tests/test_brainstorm_node_hub.py` — NEW.

## Reference Files for Patterns
- `NodeDetailModal` (:1047) — the existing modal whose Detail content the Hub
  reuses (via `NodeDetailPanel`).
- `NodeActionSelectModal`/Operations dialog (t983_4) — opened from the Hub's
  Operations entry.
- Existing `push_screen`/`ModalScreen` patterns throughout the app.

## Implementation Plan
1. Build `NodeHub` with a Detail tab hosting `NodeDetailPanel` (seeded with the
   cursor node) and an Operations entry → opens the Operations dialog contextual
   to the current selection.
2. `Enter` opens the Hub (no auto-open on mere cursor movement — avoid
   modal-spam). Remove the now-redundant direct `NodeDetailModal` open paths.
3. Keep the proposal-markdown + minimap available within the Hub Detail tab.

## Verification
- Pilot: `tests/test_brainstorm_node_hub.py` — `Enter` opens the Hub, Detail
  renders the cursor node, the Operations entry opens the dialog.
- Suite: `tests/test_brainstorm*.py` green.
- Manual: `Enter` on a node in Browse (both list + graph views) opens the Hub.
