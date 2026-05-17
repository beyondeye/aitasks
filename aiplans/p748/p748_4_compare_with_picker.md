---
Task: t748_4_compare_with_picker.md
Parent Task: aitasks/t748_browsable_node_graph.md
Sibling Tasks: aitasks/t748/t748_1_2d_arrow_navigation.md, aitasks/t748/t748_2_inline_detail_pane.md, aitasks/t748/t748_3_view_proposal_plan_keys.md
Archived Sibling Plans: (none yet)
Base branch: main
---

# t748_4 — Compare-with (`x`) — interactive second-node selection

## Context

Part of t748 — adds a `x` keybinding to the Graph tab that enters an
interactive "pick second node" mode. The currently-focused node becomes
the anchor (rendered with a third visual style, distinct from
HEAD-green and focus-purple). The user moves with arrows/`j`/`k`,
`Enter` confirms the pick and jumps to the Compare tab with the two
nodes loaded, `Esc` cancels.

Parent plan: `aiplans/p748_browsable_node_graph.md`.

## Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — binding,
  pick-mode state, action, message class, anchor rendering.
- `.aitask-scripts/brainstorm/brainstorm_app.py` —
  `@on(DAGDisplay.CompareRequested)` handler.

## Reused infrastructure

- `DAGDisplay.OperationOpened` + `action_open_operation`
  (`brainstorm_dag_display.py:429-434, 565-578`) — message + action
  pattern (mirror for `CompareRequested`).
- `_build_compare_matrix(selected_nodes)` in `brainstorm_app.py` —
  existing Compare-tab rendering pipeline; call with
  `[anchor_id, picked_id]`.
- `_render_node_box(...)` in `brainstorm_dag_display.py` — currently
  accepts `operation`; extend with `is_anchor=False`.
- HEAD-green and focused-bg-purple node styles in
  `brainstorm_dag_display.py` — precedent for per-node styling.

## Implementation Plan

### Step 1 — Add binding

Append to `DAGDisplay.BINDINGS`:

```python
Binding("x", "compare_with", "Compare", show=True),
Binding("escape", "cancel_compare", show=False),
```

### Step 2 — Add pick-mode state to `__init__`

```python
self._compare_anchor_id: str | None = None
self._compare_pick_mode: bool = False
```

### Step 3 — Add message class

```python
class CompareRequested(Message):
    def __init__(self, anchor_id: str, picked_id: str) -> None:
        super().__init__()
        self.anchor_id = anchor_id
        self.picked_id = picked_id
```

### Step 4 — Define anchor border style

Near `OP_BADGE_STYLES`:

```python
ANCHOR_BORDER_STYLE = Style(color="yellow", bold=True)
```

### Step 5 — Action methods

```python
def action_compare_with(self) -> None:
    if self._compare_pick_mode:
        self.notify("Already in compare mode — Enter to confirm, Esc to cancel")
        return
    if not self._node_order:
        return
    focused_id = self._node_order[self._focused_idx]
    self._compare_anchor_id = focused_id
    self._compare_pick_mode = True
    self._render_dag()
    self.notify(
        f"Select node to compare with {focused_id} — "
        "Enter=confirm, Esc=cancel"
    )

def action_cancel_compare(self) -> None:
    if not self._compare_pick_mode:
        return
    self._compare_anchor_id = None
    self._compare_pick_mode = False
    self._render_dag()
    self.notify("Compare cancelled")
```

### Step 6 — Override `action_open_node` (Enter handling)

Replace the current implementation so it branches on pick mode:

```python
def action_open_node(self) -> None:
    if not self._node_order:
        return
    focused_id = self._node_order[self._focused_idx]
    if self._compare_pick_mode:
        if focused_id == self._compare_anchor_id:
            self.notify("Pick a different node")
            return
        anchor = self._compare_anchor_id
        self._compare_anchor_id = None
        self._compare_pick_mode = False
        self._render_dag()
        self.post_message(self.CompareRequested(anchor, focused_id))
        return
    self.post_message(self.NodeSelected(focused_id))
```

### Step 7 — Render anchor with distinct border

Extend `_render_node_box` to accept `is_anchor: bool = False`. When
`True`, apply `ANCHOR_BORDER_STYLE` to the box border characters
instead of the default style. Confirm `NODE_ROWS = 5` is unchanged.

Update `_render_layer` (or wherever `_render_node_box` is called) to
pass `is_anchor=(nid == self._compare_anchor_id)`.

### Step 8 — App-level handler

In `brainstorm_app.py`, alongside other `@on(DAGDisplay.*)` handlers:

```python
@on(DAGDisplay.CompareRequested)
def on_dag_display_compare_requested(
    self, event: DAGDisplay.CompareRequested
) -> None:
    self._build_compare_matrix([event.anchor_id, event.picked_id])
    self.query_one(TabbedContent).active = "tab_compare"
```

## Verification

1. Launch `ait brainstorm`, switch to (G)raph.
2. Focus a node and press `x` — toast: "Select node to compare with
   <id> — Enter=confirm, Esc=cancel". Anchor renders with a yellow
   border distinct from HEAD-green and focus-purple.
3. Move with arrows/`j`/`k` — focus moves; anchor stays visually
   distinct.
4. Press `Enter` on a different node — Compare tab activates with
   the diff matrix for the two nodes.
5. Repeat step 2, then press `Esc` — toast "Compare cancelled",
   anchor styling clears, Graph tab remains.
6. Repeat step 2, press `Enter` on the anchor itself — toast
   "Pick a different node", still in pick mode.
7. Regression: outside pick mode, `Enter` on a focused node opens
   `NodeDetailModal` as before.
8. Pick mode persists across focus changes (does NOT auto-cancel when
   moving).

## Step 9 (cleanup, archival, merge)

See parent plan. Archive via
`./.aitask-scripts/aitask_archive.sh 748_4`.
