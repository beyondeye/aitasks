---
Task: t749_6_o_keybinding_open_screen.md
Parent Task: aitasks/t749_report_operation_that_generated_nod.md
Sibling Tasks: aitasks/t749/t749_1_*.md, aitasks/t749/t749_2_*.md, aitasks/t749/t749_3_*.md, aitasks/t749/t749_4_*.md, aitasks/t749/t749_5_*.md, aitasks/t749/t749_7_*.md
Archived Sibling Plans: aiplans/archived/p749/p749_*_*.md
Worktree: (current branch — no separate worktree)
Branch: main
Base branch: main
---

# Plan: 'o' keybinding to open OperationDetailScreen (t749_6)

## Context

Wires the `o` key on focused nodes (in `DAGDisplay` and the dashboard
`NodeRow` list) to push `OperationDetailScreen`. Also flips
pre-existing `show=False` bindings in `DAGDisplay` to footer-visible
per the recent feedback memory.

Depends on t749_5 (`OperationDetailScreen` class exists).

## Implementation Steps

### Step 1 — `DAGDisplay` BINDINGS

Replace the existing `BINDINGS` list in `brainstorm_dag_display.py`
with:

```python
BINDINGS = [
    Binding("j", "next_node", "Next", show=True),
    Binding("k", "prev_node", "Prev", show=True),
    Binding("enter", "open_node", "Open", show=True),
    Binding("h", "head_node", "Set HEAD", show=True),
    Binding("o", "open_operation", "Operation", show=True),
]
```

### Step 2 — New `OperationOpened` message + actions

Add inside `DAGDisplay`:

```python
class OperationOpened(Message):
    def __init__(self, group_name: str) -> None:
        super().__init__()
        self.group_name = group_name

def action_open_node(self) -> None: ...
def action_head_node(self) -> None: ...
def action_open_operation(self) -> None:
    if not self._node_order:
        return
    focused_id = self._node_order[self._focused_idx]
    data = read_node(self._session_path, focused_id)
    group = data.get("created_by_group", "")
    if not group:
        self.app.notify("No group recorded for this node",
                        severity="warning")
        return
    self.post_message(self.OperationOpened(group))
```

Remove or simplify the existing `on_key` handler — `Enter` and `h` are
now formal bindings.

### Step 3 — App-side handler

In `brainstorm_app.py`, near `on_dag_display_head_changed`:

```python
def on_dag_display_operation_opened(
    self, event: DAGDisplay.OperationOpened
) -> None:
    self.push_screen(
        OperationDetailScreen(event.group_name, self.session_path)
    )
```

### Step 4 — `NodeRow` (dashboard left pane)

Locate the `NodeRow` class definition in `brainstorm_app.py`. Append
to its `BINDINGS` list (or add one if missing):

```python
Binding("o", "open_operation", "Operation", show=True),
```

Add the `OperationOpened` inner Message and the
`action_open_operation` method analogous to step 2 (read the node id
from `self.node_id`, look up `created_by_group`, post the message).

App-side handler `on_node_row_operation_opened` mirrors step 3.

### Step 5 — Tests

`tests/test_brainstorm_dag_op_keybinding.py` (Pilot):

- Mount `DAGDisplay` over a fixture session with one node whose
  `created_by_group="explore_001"` and a recorded explore_001 group.
- Focus the node, simulate `o`, assert `OperationOpened` posted with
  `group_name="explore_001"`.
- Repeat with a node whose `created_by_group=""`; assert no message
  is posted (warning notification is shown but not assertable in
  Pilot — skip).

## Files Modified

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — ~30 LOC
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `on_dag_display_*`
  + `on_node_row_*` handlers, plus NodeRow binding/action (~25 LOC)
- `tests/test_brainstorm_dag_op_keybinding.py` — NEW

## Verification

1. `python -m pytest tests/test_brainstorm_dag_op_keybinding.py -v`.
2. Manually verify the DAG view footer surfaces the new keys.
3. Press `o` on a focused dashboard `NodeRow`; verify the screen
   opens.

## Step 9 (Post-Implementation)

Standard archival flow.

## Verification

(Aggregated under the parent task's manual-verification sibling.)
