---
Task: t749_6_o_keybinding_open_screen.md
Parent Task: aitasks/t749_report_operation_that_generated_nod.md
Sibling Tasks: aitasks/t749/t749_1_*.md, aitasks/t749/t749_2_*.md, aitasks/t749/t749_3_*.md, aitasks/t749/t749_4_*.md, aitasks/t749/t749_5_*.md, aitasks/t749/t749_7_*.md
Archived Sibling Plans: aiplans/archived/p749/p749_*_*.md
Worktree: (current branch — no separate worktree)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-14 14:15
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

## Final Implementation Notes

- **Actual work done:** Implemented the plan as written: replaced `DAGDisplay.BINDINGS` with five `show=True` entries (`j`, `k`, `enter`, `h`, `o`); added `OperationOpened` message + `action_open_node` / `action_head_node` / `action_open_operation` methods; deleted the now-redundant `on_key` body. Wired App-side `on_dag_display_operation_opened`. Added `BINDINGS` + `OperationOpened` message + `action_open_operation` to `NodeRow` and the App-side `on_node_row_operation_opened`. Added `tests/test_brainstorm_dag_op_keybinding.py` (2 Pilot cases — group present / group missing); both pass alongside the existing brainstorm test suite.
- **Deviations from plan:** None of substance. The plan's NodeRow step was implemented as a per-widget `BINDINGS` (consistent with `DAGDisplay`), matching the plan's text.
- **Issues encountered:** While running the new Pilot test, discovered that Textual's `camel_to_snake("DAGDisplay")` returns the single token `dagdisplay` (the regex matches only `[a-z][A-Z]` boundaries, and `DAG` has no lowercase-to-uppercase boundary). The auto-resolved handler name for `DAGDisplay.OperationOpened` is therefore `on_dagdisplay_operation_opened`, not `on_dag_display_operation_opened`. The pre-existing `on_dag_display_node_selected` and `on_dag_display_head_changed` handlers in `brainstorm_app.py` were dead — `Enter` and `h` on a focused DAG node silently did nothing in production. Fixed in this task by adding `@on(DAGDisplay.NodeSelected)`, `@on(DAGDisplay.HeadChanged)`, and `@on(DAGDisplay.OperationOpened)` decorators (which match by message class, not by name). The new `NodeRow.OperationOpened` handler name resolves correctly (`on_node_row_operation_opened`, because `NodeRow` has a `w_R` boundary), but I annotated it with `@on(...)` anyway for symmetry and future-proofing.
- **Key decisions:**
  - Used `@on(MessageClass)` decorators on all DAGDisplay/NodeRow message handlers rather than relying on the camel-to-snake naming convention. This eliminates a class of silent bugs whenever a widget class contains adjacent uppercase characters (`DAG`, `URL`, `API`, etc.).
  - Guarded `DAGDisplay.action_open_operation` against `_session_path is None` (in addition to the empty `_node_order` check) so the action is a no-op before `load_dag()` is called.
  - In `NodeRow.action_open_operation`, resolved `session_path` via `getattr(self.app, "session_path", None)` and returned silently when absent — keeps the binding inert in unit tests that mount `NodeRow` outside the brainstorm app context.
- **Upstream defects identified:** `.aitask-scripts/brainstorm/brainstorm_app.py:3849-3858 — pre-existing on_dag_display_node_selected/on_dag_display_head_changed handlers were dead due to Textual auto-dispatch name mismatch (camel_to_snake("DAGDisplay") = "dagdisplay"). Fixed inline in this task by adding @on(...) decorators. Worth a separate follow-up audit pass: grep .aitask-scripts/ for other on_<snake>_<msg> handlers where the widget class name contains adjacent uppercase characters (DAG, UI, URL, API, …) — they may also be dead.`
- **Notes for sibling tasks:**
  - For t749_7 (retrospective): record the Textual auto-handler naming pitfall — prefer `@on(MessageClass)` over relying on `camel_to_snake` for any widget class whose name contains adjacent uppercase characters.
  - For t749_8 (manual verification): items to verify — (1) pressing `o` on a focused DAG node (Graph tab) opens `OperationDetailScreen` for the node's generating group; (2) pressing `o` on a focused `NodeRow` (Dashboard left pane) does the same; (3) nodes whose `created_by_group` is empty show a warning notify and no screen pushed; (4) the DAG view footer now shows `j Next  k Prev  enter Open  h Set HEAD  o Operation`. As a separate manual check (newly working as a side effect of this task): `Enter` on a focused DAG node opens the `NodeDetailModal` and `h` updates HEAD from the DAG view — these were silently broken prior to t749_6.
