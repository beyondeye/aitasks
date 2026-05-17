---
Task: t748_1_2d_arrow_navigation.md
Parent Task: aitasks/t748_browsable_node_graph.md
Sibling Tasks: aitasks/t748/t748_2_inline_detail_pane.md, aitasks/t748/t748_3_view_proposal_plan_keys.md, aitasks/t748/t748_4_compare_with_picker.md
Archived Sibling Plans: (none yet)
Base branch: main
---

# t748_1 — 2D arrow-key navigation in `DAGDisplay`

## Context

Part of t748 — making the brainstorm Graph tab a first-class navigation
surface. Today the DAG is browsed via `j`/`k` only (flat
top-to-bottom-left-to-right). This task adds true 2D arrow-key navigation
matching the visual layout, and surfaces the arrow keys in the Textual
footer (`show=True`).

Parent plan: `aiplans/p748_browsable_node_graph.md`. See its
"Post-t749 reconciliation" section for the current state of DAGDisplay
after t749 landed (op badges, bindings already declared with show=True).

## Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — only file.

## Reused infrastructure

- `DAGDisplay.BINDINGS` at `brainstorm_dag_display.py:407-412` — append
  four new bindings here.
- `_layers: list[list[str]]` populated in `load_dag` (line ~472) — the
  2D structure to derive `(layer_idx, col_idx)`.
- `_node_order` flat list (line 475-477) — keep in sync so `j`/`k` and
  `_focused_idx` remain consistent.
- Existing `action_next_node` / `action_prev_node` (lines 537-547) —
  the pattern for "update `_focused_idx`, call `_render_dag()`".
- Layout constants used by `_render_node_box` / `_render_layer`
  (`COL_STRIDE`, `BOX_WIDTH`) — used to compute column centers for
  snapping.

## Implementation Plan

### Step 1 — Add bindings

Append to `DAGDisplay.BINDINGS`:

```python
Binding("up", "prev_layer", "↑ Layer", show=True),
Binding("down", "next_layer", "↓ Layer", show=True),
Binding("left", "prev_col", "← Col", show=True),
Binding("right", "next_col", "→ Col", show=True),
```

### Step 2 — Derive `(layer_idx, col_idx)` helper

Add a private method to `DAGDisplay`:

```python
def _layer_col_from_focused(self) -> tuple[int, int] | None:
    """Return (layer_idx, col_idx) for the currently focused node, or None."""
    if not self._node_order or not self._layers:
        return None
    focused_id = self._node_order[self._focused_idx]
    for li, layer in enumerate(self._layers):
        if focused_id in layer:
            return (li, layer.index(focused_id))
    return None
```

And the inverse — `_focused_idx_from_layer_col(layer_idx, col_idx)`
that finds the node id in `_layers[layer_idx][col_idx]` and returns its
position in `_node_order`.

### Step 3 — Column-center snapping helper

```python
def _col_center(self, layer: list[str], col_idx: int) -> float:
    """Horizontal center of the given column in the layer (in chars)."""
    # Each box is BOX_WIDTH wide and laid out with COL_STRIDE between centers.
    # Use the same offset math as _render_layer.
    return col_idx * COL_STRIDE + BOX_WIDTH / 2
```

For up/down snapping, find the column in the target layer whose
center minimizes `abs(target_center - source_center)`.

### Step 4 — Action methods

```python
def action_prev_col(self) -> None:
    pos = self._layer_col_from_focused()
    if not pos:
        return
    li, ci = pos
    if ci > 0:
        self._focused_idx = self._focused_idx_from_layer_col(li, ci - 1)
        self._render_dag()

def action_next_col(self) -> None:
    pos = self._layer_col_from_focused()
    if not pos:
        return
    li, ci = pos
    if ci < len(self._layers[li]) - 1:
        self._focused_idx = self._focused_idx_from_layer_col(li, ci + 1)
        self._render_dag()

def action_prev_layer(self) -> None:
    pos = self._layer_col_from_focused()
    if not pos:
        return
    li, ci = pos
    if li == 0:
        return
    src_center = self._col_center(self._layers[li], ci)
    target_layer = self._layers[li - 1]
    best_ci = min(
        range(len(target_layer)),
        key=lambda c: abs(self._col_center(target_layer, c) - src_center),
    )
    self._focused_idx = self._focused_idx_from_layer_col(li - 1, best_ci)
    self._render_dag()

def action_next_layer(self) -> None:
    pos = self._layer_col_from_focused()
    if not pos:
        return
    li, ci = pos
    if li >= len(self._layers) - 1:
        return
    src_center = self._col_center(self._layers[li], ci)
    target_layer = self._layers[li + 1]
    best_ci = min(
        range(len(target_layer)),
        key=lambda c: abs(self._col_center(target_layer, c) - src_center),
    )
    self._focused_idx = self._focused_idx_from_layer_col(li + 1, best_ci)
    self._render_dag()
```

### Step 5 — Sibling coordination (`FocusChanged`)

t748_2 introduces a `DAGDisplay.FocusChanged(node_id)` message that the
inline detail pane subscribes to. If t748_2 has already merged when
this child is picked, add a `self.post_message(self.FocusChanged(...))`
call to all four new action methods (and to `action_next_node` /
`action_prev_node` / `action_open_node` if not already done).

If t748_2 has NOT yet merged, document in Final Implementation Notes
that t748_2 must update these four actions to post `FocusChanged`.

### Step 6 — TuiSwitcherMixin `j` conflict check

The app-wide `TuiSwitcherMixin` binds `j` as a priority key. DAGDisplay's
local `Binding("j", "next_node")` should win because DAGDisplay is the
focused widget when the Graph tab is active. Confirm by launching the
TUI and pressing `j` on the Graph tab. If a conflict appears, follow
the SkipAction guard pattern from CLAUDE.md
("Priority bindings + `App.query_one` gotcha").

## Verification

1. Launch `ait brainstorm` on a session with a multi-layer DAG.
2. Switch to (G)raph tab. Footer shows: `j Next | k Prev | Enter Open |
   h Set HEAD | o Operation | ↑ Layer | ↓ Layer | ← Col | → Col`.
3. Press `right` / `left` — focus moves within the current layer, clamps
   at edges, does not wrap.
4. Press `down` / `up` — focus moves to the column in the adjacent layer
   whose center is closest to the current column's center.
5. Press `j` / `k` — flat walk continues to work, including across
   layer boundaries (verifies `_focused_idx` invariant).
6. Tab away to Dashboard and back to Graph — focus position preserved.
7. (If t748_2 merged) confirm the detail pane updates on every arrow
   press.

## Step 9 (cleanup, archival, merge)

See parent plan `aiplans/p748_browsable_node_graph.md` "Step 9 (parent
archival)". This child is archived via
`./.aitask-scripts/aitask_archive.sh 748_1`.
