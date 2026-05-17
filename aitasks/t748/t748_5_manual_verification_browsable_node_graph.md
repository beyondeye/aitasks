---
priority: medium
effort: medium
depends: [t748_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [748_1, 748_2, 748_3, 748_4]
created_at: 2026-05-17 10:16
updated_at: 2026-05-17 10:16
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t748_1] Footer on (G)raph tab shows arrow bindings with show=True: ↑ Layer, ↓ Layer, ← Col, → Col (alongside j Next, k Prev, Enter Open, h Set HEAD, o Operation)
- [ ] [t748_1] left/right moves focus within current layer, clamps at edges (no wrap)
- [ ] [t748_1] up/down moves focus to column in adjacent layer whose center is closest to current column's center
- [ ] [t748_1] j/k still works as a flat top-to-bottom-left-to-right walk, crossing layer boundaries
- [ ] [t748_1] Confirm TuiSwitcherMixin's app-level j binding does not steal Graph-tab j (DAGDisplay's local binding wins when focused)
- [ ] [t748_1] Switching tab away and back to (G)raph preserves focus
- [ ] [t748_2] (G)raph tab is a Horizontal split: DAG ASCII left (~60%), detail pane right (~40%)
- [ ] [t748_2] Right pane updates immediately on every focus change (arrows or j/k)
- [ ] [t748_2] Detail content matches Dashboard for the same node: Description, Parents, Created, Generated-by block, Dimensions
- [ ] [t748_2] Generated-by block renders correctly: operation badge with OP_BADGE_STYLES color, Agents row, When row, "Press 'o' for operation details" hint
- [ ] [t748_2] Pressing o from the Graph tab opens OperationDetailScreen for the focused node's group
- [ ] [t748_2] Focusing a DimensionRow in the right pane and pressing Enter opens filtered SectionViewerScreen for the Graph-focused node
- [ ] [t748_2] Dashboard tab still works correctly (refactor regression check)
- [ ] [t748_2] Initial entry to Graph tab populates the right pane immediately (no need to press a key first)
- [ ] [t748_3] Pressing p on a focused node opens SectionViewerScreen titled "Proposal: <node_id>" with proposal content
- [ ] [t748_3] Pressing l on a node with a plan opens SectionViewerScreen titled "Plan: <node_id>"
- [ ] [t748_3] Pressing l on a node WITHOUT a plan shows a warning toast; no screen pushed
- [ ] [t748_3] Pressing Enter still opens NodeDetailModal with Metadata/Proposal/Plan tabs (regression)
- [ ] [t748_3] Esc from SectionViewerScreen returns to Graph tab with focus preserved
- [ ] [t748_3] Footer shows all Graph-tab operations with show=True: j, k, Enter, h, o, p, l, x, plus arrow nav
- [ ] [t748_4] Pressing x stores focused node as anchor, sets pick mode, renders anchor with yellow border distinct from HEAD-green and focus-purple, shows toast
- [ ] [t748_4] In pick mode, arrows/j/k still move focus; anchor remains visually distinct
- [ ] [t748_4] Enter on a DIFFERENT node activates Compare tab with the diff matrix for [anchor, picked]
- [ ] [t748_4] Esc cancels pick mode: anchor styling clears, toast "Compare cancelled", stays on Graph tab
- [ ] [t748_4] Enter on the anchor itself shows "Pick a different node" toast and stays in pick mode
- [ ] [t748_4] Outside pick mode, Enter still opens NodeDetailModal (regression)
- [ ] [t748_4] Pick mode persists across focus changes (no auto-cancel when moving)
