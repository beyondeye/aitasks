---
Task: t748_3_view_proposal_plan_keys.md
Parent Task: aitasks/t748_browsable_node_graph.md
Sibling Tasks: aitasks/t748/t748_1_2d_arrow_navigation.md, aitasks/t748/t748_2_inline_detail_pane.md, aitasks/t748/t748_4_compare_with_picker.md
Archived Sibling Plans: (none yet)
Base branch: main
---

# t748_3 — Context-aware operations: view proposal / view plan

## Context

Part of t748 — adds two new keybindings (`p` view proposal, `l` view
plan) on the Graph tab's `DAGDisplay`. Both push the existing
`SectionViewerScreen` modal.

**Important post-t749 reconciliation:** the original parent plan
included a "footer-visibility pass" for existing bindings
(`j`/`k`/`Enter`/`h`) that is **already done** by t749_6 — those four
bindings are already `Binding(..., show=True)` with proper `action_*`
handlers (`brainstorm_dag_display.py:407-412, 537-578`), and `on_key`
no longer consumes them. `o` is also already `show=True`. So this
child's scope is limited to the two new bindings.

Parent plan: `aiplans/p748_browsable_node_graph.md`.

## Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — bindings,
  action methods, new message classes.
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `@on` handlers that
  read session data and push `SectionViewerScreen`.

## Reused infrastructure

- `DAGDisplay.OperationOpened` + `action_open_operation` pattern
  (`brainstorm_dag_display.py:429-434, 565-578`) — mirror for
  `ProposalRequested` / `PlanRequested`.
- `@on(DAGDisplay.OperationOpened)` handler at
  `brainstorm_app.py:3863-3879` — place to add the two new `@on`
  handlers.
- `SectionViewerScreen` at `lib/section_viewer.py:292` — modal
  constructor `(content, title, section_filter=None)`.
- `read_proposal`, `read_plan` in `.aitask-scripts/brainstorm/
  brainstorm_dag` — readers used by the app-level handlers.

## Implementation Plan

### Step 1 — Add bindings

Append to `DAGDisplay.BINDINGS`:

```python
Binding("p", "view_proposal", "Proposal", show=True),
Binding("l", "view_plan", "Plan", show=True),
```

### Step 2 — Add message classes

In `DAGDisplay`:

```python
class ProposalRequested(Message):
    def __init__(self, node_id: str) -> None:
        super().__init__()
        self.node_id = node_id

class PlanRequested(Message):
    def __init__(self, node_id: str) -> None:
        super().__init__()
        self.node_id = node_id
```

### Step 3 — Add action methods

```python
def action_view_proposal(self) -> None:
    if not self._node_order:
        return
    focused_id = self._node_order[self._focused_idx]
    self.post_message(self.ProposalRequested(focused_id))

def action_view_plan(self) -> None:
    if not self._node_order:
        return
    focused_id = self._node_order[self._focused_idx]
    self.post_message(self.PlanRequested(focused_id))
```

DAGDisplay does NOT read session data directly — the App handles IO.

### Step 4 — App-level `@on(DAGDisplay.ProposalRequested)` handler

In `brainstorm_app.py`, alongside the existing
`@on(DAGDisplay.OperationOpened)` handler:

```python
@on(DAGDisplay.ProposalRequested)
def on_dag_display_proposal_requested(
    self, event: DAGDisplay.ProposalRequested
) -> None:
    try:
        proposal = read_proposal(self.session_path, event.node_id)
    except Exception:
        self.notify(
            f"No proposal for {event.node_id}", severity="warning"
        )
        return
    self.push_screen(
        SectionViewerScreen(
            proposal, title=f"Proposal: {event.node_id}"
        )
    )
```

### Step 5 — App-level `@on(DAGDisplay.PlanRequested)` handler

```python
@on(DAGDisplay.PlanRequested)
def on_dag_display_plan_requested(
    self, event: DAGDisplay.PlanRequested
) -> None:
    try:
        plan = read_plan(self.session_path, event.node_id)
    except Exception:
        plan = None
    if not plan or not plan.strip():
        self.notify(
            f"No plan generated for {event.node_id}", severity="warning"
        )
        return
    self.push_screen(
        SectionViewerScreen(plan, title=f"Plan: {event.node_id}")
    )
```

### Step 6 — Import `read_proposal`, `read_plan` in `brainstorm_app.py`

Confirm they are imported from `brainstorm.brainstorm_dag` at the top of
`brainstorm_app.py`. Add if missing.

## Verification

1. Launch `ait brainstorm`, switch to (G)raph.
2. Focus a node and press `p` — `SectionViewerScreen` opens titled
   `Proposal: <node_id>` with the proposal content.
3. Focus a node with a plan and press `l` — `SectionViewerScreen`
   opens titled `Plan: <node_id>`.
4. Focus a node without a plan (e.g., a non-`detail` operation node)
   and press `l` — warning toast appears, no screen pushed.
5. Footer shows: `j Next | k Prev | Enter Open | h Set HEAD | o Operation
   | p Proposal | l Plan | x Compare | ↑/↓/←/→ nav` (the last set
   depends on t748_1 / t748_4 merge status).
6. Press `Enter` — `NodeDetailModal` still opens with tabs (regression).
7. Press `Esc` from `SectionViewerScreen` — returns to Graph tab,
   focus preserved.

## Step 9 (cleanup, archival, merge)

See parent plan. Archive via
`./.aitask-scripts/aitask_archive.sh 748_3`.
