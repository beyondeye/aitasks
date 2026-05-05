---
priority: high
effort: low
depends: [t749_5]
issue_type: enhancement
status: Ready
labels: [ait_brainstorm]
created_at: 2026-05-05 10:43
updated_at: 2026-05-05 10:43
---

## Context

Wire up the 'o' keybinding in two surfaces (DAG view + dashboard
NodeRow list) to push the `OperationDetailScreen` for the focused
node's generating group. Also flips the existing `show=False`
bindings in `DAGDisplay` to footer-visible, per the recent
"TUI footer must surface keys (existing + new)" feedback memory.

Depends on t749_5 (`OperationDetailScreen` exists).

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — add
  `Binding("o", "open_operation", "Operation", show=True)` to
  `DAGDisplay`. Add a new `OperationOpened(Message)`. Convert the
  existing `j` / `k` from `show=False` to `show=True`. Convert the
  `on_key` `Enter` and `h` handlers to formal `Binding` entries with
  `show=True`.
- `.aitask-scripts/brainstorm/brainstorm_app.py` —
  - Add `on_dag_display_operation_opened` handler that pushes
    `OperationDetailScreen(group_name, session_path)`.
  - Add an `o` binding to `NodeRow` (the dashboard left-pane row
    widget). New `NodeRow.OperationOpened(Message)`.
    Add `on_node_row_operation_opened` handler in the App.

## Reference Files for Patterns

- `brainstorm_dag_display.py:354-367` — `HeadChanged` `Message` +
  `on_key` `h` handler. Mirror exactly for `OperationOpened` / `o`.
- `brainstorm_app.py:3007-3013` — `on_dag_display_head_changed`
  handler. Mirror for `on_dag_display_operation_opened`.
- `NodeRow` definition in `brainstorm_app.py` (search for
  `class NodeRow`) — contains the existing focused-row keybindings.

## Implementation Plan

1. In `brainstorm_dag_display.py`, replace the `BINDINGS` list:
   ```python
   BINDINGS = [
       Binding("j", "next_node", "Next", show=True),
       Binding("k", "prev_node", "Prev", show=True),
       Binding("enter", "open_node", "Open", show=True),
       Binding("h", "head_node", "Set HEAD", show=True),
       Binding("o", "open_operation", "Operation", show=True),
   ]
   ```

2. Add a new message class:
   ```python
   class OperationOpened(Message):
       def __init__(self, group_name: str) -> None:
           super().__init__()
           self.group_name = group_name
   ```

3. Replace the `on_key` body so it ONLY guards Enter/h fall-throughs
   when needed (or remove it entirely now that those are formal
   bindings). Add three actions:
   ```python
   def action_open_node(self) -> None:
       if not self._node_order:
           return
       focused_id = self._node_order[self._focused_idx]
       self.post_message(self.NodeSelected(focused_id))

   def action_head_node(self) -> None:
       if not self._node_order:
           return
       focused_id = self._node_order[self._focused_idx]
       self.post_message(self.HeadChanged(focused_id))

   def action_open_operation(self) -> None:
       if not self._node_order:
           return
       focused_id = self._node_order[self._focused_idx]
       data = read_node(self._session_path, focused_id)
       group = data.get("created_by_group", "")
       if not group:
           self.app.notify(
               "No group recorded for this node",
               severity="warning",
           )
           return
       self.post_message(self.OperationOpened(group))
   ```

4. In `brainstorm_app.py`, add the handler near the existing
   `on_dag_display_head_changed`:
   ```python
   def on_dag_display_operation_opened(
       self, event: DAGDisplay.OperationOpened
   ) -> None:
       self.push_screen(
           OperationDetailScreen(event.group_name, self.session_path)
       )
   ```

5. In `NodeRow` (dashboard left-pane row widget), add a
   `Binding("o", "open_operation", "Operation", show=True)` entry,
   and an `OperationOpened(Message)` inner class. Implement
   `action_open_operation` that reads the row's node id, opens the
   yaml, and posts the message. Add the App-side handler
   `on_node_row_operation_opened` that does the same `push_screen`.

6. If `NodeRow` already has `BINDINGS`, append the `o` entry without
   modifying others. If it currently relies on `on_key` for Enter,
   leave Enter alone — only flip what we touch in this child.

## Verification Steps

1. Add `tests/test_brainstorm_dag_op_keybinding.py` (Pilot) that:
   - Mounts a `DAGDisplay` over a fixture session with one node
     whose `created_by_group="explore_001"` and a recorded
     explore_001 group.
   - Focuses the node, simulates `o` key, asserts an
     `OperationOpened` message was posted with `group_name ==
     "explore_001"`.
   - Repeats with a node whose `created_by_group=""` and asserts a
     warning notification (no message posted).

2. Manually verify the DAG view footer reads
   `j Next  k Prev  enter Open  h Set HEAD  o Operation` (or close).

3. In the dashboard left pane, press `o` on a focused NodeRow and
   verify the OperationDetailScreen opens.

## Notes for Sibling Tasks

- The `app.notify(...)` warning path (no group recorded) is a 1st-
  class UX state; the OperationDetailScreen also has a placeholder
  for unknown groups (see t749_5). Both paths must agree on tone:
  dim, non-blocking.
- Keep `NodeDetailModal` untouched — the user explicitly rejected
  surfacing operation details inside that modal during plan review.
