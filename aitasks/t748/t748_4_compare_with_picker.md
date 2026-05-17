---
priority: medium
effort: medium
depends: [t748_3]
issue_type: enhancement
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-17 10:13
updated_at: 2026-05-17 14:34
---

## Context

Part of t748 (parent: `aitasks/t748_browsable_node_graph.md`, plan: `aiplans/p748_browsable_node_graph.md`). This child adds a `x` (Compare) keybinding to the brainstorm Graph tab that enters an interactive "pick second node" mode: the focused node becomes the anchor (highlighted in a third color), the user moves with arrows/`j`/`k`, `Enter` confirms the pick and jumps to the Compare tab with the two nodes, `Esc` cancels.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — add binding, action, message, pick-mode state, and anchor rendering.
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add `@on(DAGDisplay.CompareRequested)` handler that calls `_build_compare_matrix` and switches the tab.

## Reference Files for Patterns

- `DAGDisplay.OperationOpened` + `action_open_operation` (`brainstorm_dag_display.py:429-434, 565-578`) — message + action pattern (mirror for `CompareRequested`).
- `_build_compare_matrix(selected_nodes)` in `brainstorm_app.py` — the existing Compare-tab rendering pipeline; call with `[anchor_id, picked_id]`.
- `_render_node_box(...)` in `brainstorm_dag_display.py` — currently accepts `operation`; extend to accept `is_anchor=False`.
- HEAD-green and focused-bg-purple styles in `brainstorm_dag_display.py` — the precedent for per-node style differentiation.

## Implementation Plan

1. **Add binding to `DAGDisplay.BINDINGS`:**
   ```python
   Binding("x", "compare_with", "Compare", show=True),
   ```
2. **Add pick-mode state to `DAGDisplay.__init__`:**
   ```python
   self._compare_anchor_id: str | None = None
   self._compare_pick_mode: bool = False
   ```
3. **Add `DAGDisplay.CompareRequested` message:**
   ```python
   class CompareRequested(Message):
       def __init__(self, anchor_id: str, picked_id: str) -> None:
           super().__init__()
           self.anchor_id = anchor_id
           self.picked_id = picked_id
   ```
4. **Add `action_compare_with`:**
   - If `_compare_pick_mode` is already True, treat as no-op (or notify "already in compare mode").
   - Otherwise: store `_compare_anchor_id = focused_id`, set `_compare_pick_mode = True`, re-render, notify: `"Select node to compare with {anchor_id} — Enter=confirm, Esc=cancel"`.
5. **Override behavior in compare-pick mode:**
   - Existing nav actions (arrows, `j`/`k`) continue to update `_focused_idx` and re-render — anchor stays styled.
   - `action_open_node` (Enter): if `_compare_pick_mode` is True, then:
     - If `focused_id == _compare_anchor_id`: notify "Pick a different node" and stay in mode.
     - Otherwise: `post_message(CompareRequested(_compare_anchor_id, focused_id))`, clear pick-mode state, re-render. Do NOT post `NodeSelected` in this path.
     - If `_compare_pick_mode` is False: post `NodeSelected` as today.
   - Add `Binding("escape", "cancel_compare", show=False)`: if `_compare_pick_mode` is True, clear state, re-render, notify "Compare cancelled". If False, do nothing.
6. **Extend `_render_node_box(...)` signature** to accept `is_anchor: bool = False`. When `True`, use `ANCHOR_BORDER_STYLE` (yellow + bold) instead of the default border. Confirm `NODE_ROWS=5` (with the t749_3 op-badge row) is unaffected.
7. **Update `_render_dag` / `_render_layer`** to pass `is_anchor=(nid == self._compare_anchor_id)` when calling `_render_node_box`.
8. **Add app-level `@on(DAGDisplay.CompareRequested)` handler** in `brainstorm_app.py`:
   ```python
   @on(DAGDisplay.CompareRequested)
   def on_dag_display_compare_requested(self, event: DAGDisplay.CompareRequested) -> None:
       self._build_compare_matrix([event.anchor_id, event.picked_id])
       self.query_one(TabbedContent).active = "tab_compare"
   ```

## Verification Steps

1. Launch `ait brainstorm`, switch to (G)raph.
2. Focus a node and press `x` — toast appears: "Select node to compare with <id> — Enter=confirm, Esc=cancel". Anchor node renders with a yellow border (distinct from HEAD-green and focus-purple).
3. Move with arrows/`j`/`k` — focus moves, anchor remains visually distinct.
4. Press `Enter` on a different node — Compare tab activates, showing the diff matrix for the two nodes.
5. Repeat steps 2-3, then press `Esc` — toast "Compare cancelled", anchor styling clears, Graph tab remains.
6. Repeat step 2, then press `Enter` on the anchor itself — toast "Pick a different node", still in pick mode.
7. Regression: press `Enter` on a focused node OUTSIDE pick mode — `NodeDetailModal` opens as before.

## Notes for Sibling Tasks

- `_compare_anchor_id` and `_compare_pick_mode` are pick-mode session state; they're cleared on confirm/cancel. They live on the DAGDisplay instance (not in app state) because they're entirely a navigation concern within the Graph tab.
- The yellow `ANCHOR_BORDER_STYLE` complements existing focus-purple and HEAD-green; pick a distinctive shade that doesn't clash with `OP_BADGE_STYLES` colors.
- Whenever a focus-change action runs (`action_next_node`, arrow actions, etc.), pick-mode does NOT clear — the user is mid-selection.
