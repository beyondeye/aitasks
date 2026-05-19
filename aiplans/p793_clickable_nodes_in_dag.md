---
Task: t793_clickable_nodes_in_dag.md
Worktree: (none — working on current branch per fast profile)
Branch: main
Base branch: main
---

# Plan: Click-to-focus brainstorm DAG nodes

## Context

In the brainstorm TUI's Graph tab, the DAG widget (`DAGDisplay`) is currently
keyboard-only — users move focus between proposal nodes with the arrow keys
(`_focused_idx` advanced by `action_prev_layer` / `action_next_layer` /
`action_prev_col` / `action_next_col`). The user wants to additionally focus
any visible node by clicking on it with the mouse.

Scope is narrow: clicking on a node box anywhere in its 5-row × `BOX_WIDTH`-col
footprint should set focus to that node, exactly as if the user had navigated
there with arrows (re-render with highlight, scroll to it, post
`FocusChanged`). It explicitly does NOT trigger Open / HEAD / Operation /
Proposal / Plan / Compare — those remain keyboard-only.

## Approach

The DAG is rendered into a single `Static#dag_display` child inside a
`VerticalScroll` (`DAGDisplay`). The existing code already maintains:

- `self._node_line_map[nid]` — the absolute line index (within the rendered
  content) of each node's **top border**. Every node occupies `NODE_ROWS = 5`
  consecutive lines.
- `self._layers[layer_idx]` — ordered node IDs in each layer. Columns are at
  `col_idx * COL_STRIDE` and span `BOX_WIDTH` characters.

These are sufficient to map a click `(x, y)` (in content coordinates) to a
node. The key Textual fact: when a click hits a `Static` whose content fills
the scroll area, `event.x` / `event.y` on that `Static` are content-relative
(equal to column / line within the rendered text), regardless of scroll
position. So receiving the click on the inner `Static` gives us exactly the
coordinates we need.

### Critical files

- `/.aitask-scripts/brainstorm/brainstorm_dag_display.py` — single file edit.
- `/tests/test_brainstorm_dag_click_focus.py` — new pilot-style test
  (mirrors existing `tests/test_brainstorm_dag_op_keybinding.py`).

### Implementation in `brainstorm_dag_display.py`

1. **Import** `events` from textual (currently only `Binding` and
   `Message` are imported from textual.binding / textual.message):
   ```python
   from textual import events
   ```

2. **Add `_DAGStatic(Static)` subclass** placed just above `DAGDisplay`:
   ```python
   class _DAGStatic(Static):
       """Static that forwards click coordinates to the parent DAGDisplay."""

       def on_click(self, event: events.Click) -> None:
           parent = self.parent
           if isinstance(parent, DAGDisplay):
               parent._handle_click(event.x, event.y)
           event.stop()
   ```
   This narrow subclass exists only to attach an `on_click` handler that
   knows about widget-relative coordinates. The parent `DAGDisplay` already
   has all the geometry state.

3. **Swap the `Static` in `compose()`** (line 506):
   ```python
   yield _DAGStatic("No DAG loaded", id="dag_display")
   ```
   `query_one("#dag_display", Static)` calls elsewhere in the file (lines
   522, 592, 596) continue to work because `_DAGStatic` is a `Static`
   subclass.

4. **Add `_handle_click(self, x, y)` method on `DAGDisplay`** (place near
   the action methods, e.g. just before `action_prev_col`):

   ```python
   def _handle_click(self, x: int, y: int) -> None:
       """Focus the node whose box contains click coords (x, y).

       Coordinates are content-relative (column, line within the rendered
       DAG text). No-op if the click falls outside any node box (edge
       rows, inter-column gaps, or empty space).
       """
       if not self._node_order or not self._layers:
           return

       # Column gate: must land inside a box, not in the COL_GAP.
       col_idx = x // COL_STRIDE
       if x - col_idx * COL_STRIDE >= BOX_WIDTH:
           return

       # Row gate: must land inside one of the NODE_ROWS lines of some
       # node. Layers are rendered top-to-bottom; every node in a layer
       # shares the same top line, so we can scan layer-by-layer.
       for layer in self._layers:
           if not layer:
               continue
           top = self._node_line_map.get(layer[0])
           if top is None:
               continue
           if top <= y < top + NODE_ROWS:
               if col_idx >= len(layer):
                   return
               target_id = layer[col_idx]
               new_idx = self._node_order.index(target_id)
               if new_idx != self._focused_idx:
                   self._focused_idx = new_idx
                   self._render_dag()
                   self.post_message(self.FocusChanged(target_id))
               # Take keyboard focus so subsequent arrow keys work.
               if not self.has_focus:
                   self.focus()
               return
           # If y is past this layer (including its edge rows below), keep
           # scanning. Edge rows between layers are dead zones; no node is
           # selected if the click lands there.
   ```

   - `COL_STRIDE` and `BOX_WIDTH` are module-level constants already in the
     file.
   - The gap check uses `x - col_idx * COL_STRIDE >= BOX_WIDTH` so clicks in
     the `COL_GAP` (4 chars wide) between boxes are ignored.
   - `_render_dag()` is skipped if focus didn't change — avoids a no-op
     re-render on a re-click of the already-focused node — but `focus()` is
     still called so keyboard nav resumes immediately after a click.
   - `post_message(FocusChanged)` mirrors what every arrow-key action does;
     `brainstorm_app.py:4277` (`on_dag_display_focus_changed`) reacts to it.

### Behavior matrix

| Click location                             | Behavior                                |
| ------------------------------------------ | --------------------------------------- |
| Inside a node box (border or interior)     | Focus that node, re-render, scroll      |
| Same node already focused                  | Take widget focus only, no re-render    |
| Inter-column gap (`COL_GAP`)               | No-op                                   |
| Edge rows between layers                   | No-op                                   |
| Below all layers / empty padding           | No-op                                   |
| Compare-pick mode is active                | Same focus update — `x`/Enter still confirm the pick |

Compare-pick mode is unchanged: a click only repositions focus; the user
still presses Enter to confirm the pick or Esc to cancel. This matches the
intent ("focus by clicking", not "select by clicking") and avoids surprise
confirms.

### Test (`tests/test_brainstorm_dag_click_focus.py`)

Mirrors `tests/test_brainstorm_dag_op_keybinding.py`:

1. Seed a temp session with ≥3 nodes spanning at least 2 layers (`n001` root,
   `n002` child of `n001`, `n003` second-layer sibling).
2. Mount a host `App` with a `DAGDisplay`, `load_dag(session_path)`.
3. Compute the expected click target for the bottom-layer node using the
   module's geometry constants: `x = col_idx * COL_STRIDE + BOX_WIDTH // 2`,
   `y = top_line + NODE_ROWS // 2`.
4. Call `dag._handle_click(x, y)` directly (bypasses Textual's pilot mouse
   simulator — pure geometry test, no event plumbing).
5. Assert `dag._node_order[dag._focused_idx]` is the expected node and that
   a `FocusChanged` message was posted with that ID.
6. Add a negative case: click in the `COL_GAP` (e.g. `x = col_idx * COL_STRIDE
   + BOX_WIDTH + 1`) → `_focused_idx` unchanged, no `FocusChanged` posted.
7. Add an edge-row negative case: click at `y` between two layers (in the
   `EDGE_ROWS` zone) → no change.

The pilot-mounted host App is kept (rather than instantiating `DAGDisplay`
standalone) because `_render_dag()` requires the inner `Static` to exist
via `query_one`, which only works once the widget is mounted.

## Out of scope

- Double-click / right-click semantics. Single click = focus only.
- Clicking a node to invoke Open / HEAD / Operation / Proposal / Plan /
  Compare. Those remain keyboard actions.
- Touch / drag selection.

## Verification

1. **Unit test:** `python tests/test_brainstorm_dag_click_focus.py` — passes.
2. **Existing tests still pass:**
   - `python tests/test_brainstorm_dag.py`
   - `python tests/test_brainstorm_dag_op_badge.py`
   - `python tests/test_brainstorm_dag_op_keybinding.py`
3. **Manual TUI smoke (in a real terminal with mouse support):**
   - Start `ait brainstorm` on a session that has at least two layers of
     nodes.
   - Switch to the Graph tab.
   - Click a node in the bottom layer → highlight moves to it, status bar
     reflects the new focused node ID.
   - Click a different node in the top layer → focus jumps there.
   - Click in the gap between two columns → no change.
   - Click in the empty rows between layers → no change.
   - With a node focused via click, press arrows → keyboard nav resumes
     from the clicked node.
   - Press `x` then click another node + Enter → compare opens for the two
     correct nodes (compare-pick semantics preserved).

## Post-Implementation: Step 9

Follow Step 9 of the task-workflow (no separate branch, so just archive on
current branch via `./.aitask-scripts/aitask_archive.sh 793`).
