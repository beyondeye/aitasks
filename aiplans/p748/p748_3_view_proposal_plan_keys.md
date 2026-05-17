---
Task: t748_3_view_proposal_plan_keys.md
Parent Task: aitasks/t748_browsable_node_graph.md
Sibling Tasks: aitasks/t748/t748_4_compare_with_picker.md, aitasks/t748/t748_5_manual_verification_browsable_node_graph.md
Archived Sibling Plans: aiplans/archived/p748/p748_1_2d_arrow_navigation.md, aiplans/archived/p748/p748_2_inline_detail_pane.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-17 14:23
---

# t748_3 — Context-aware operations: view proposal / view plan

## Context

Adds two new keybindings to the brainstorm Graph tab's `DAGDisplay`:
- `p` — view proposal of focused node (push `SectionViewerScreen`)
- `l` — view plan of focused node (push `SectionViewerScreen`, with notify when no plan)

This is the third implementation child of t748 (browsable node graph). t748_1 (2D arrow nav) and t748_2 (inline detail pane + `FocusChanged` message) are already merged. The Graph tab's existing bindings (`j/k/Enter/h/o` + arrows) are all already declared `show=True` with `action_*` handlers after t749_6's binding-refactor sweep.

The two new bindings follow the **Message → @on(...)** routing pattern: `DAGDisplay` posts a message; `BrainstormApp` reads session data and pushes the screen.

## Verification of existing plan (Phase 1)

The existing plan at `aiplans/p748/p748_3_view_proposal_plan_keys.md` was verified against the current codebase. All claims hold; concrete line numbers in the current code:

- `SectionViewerScreen` — `.aitask-scripts/lib/section_viewer.py:292` (class) / `:335-340` (constructor `(content, title="Plan Viewer", section_filter=None)`)
- `read_proposal` / `read_plan` — `.aitask-scripts/brainstorm/brainstorm_dag.py:200-211`. `read_plan` returns `None` when the file doesn't exist.
- Both already imported in `brainstorm_app.py:44-52`.
- `DAGDisplay.BINDINGS` — `brainstorm_dag_display.py:407-415` (no `p`/`l`/`x` declared)
- `DAGDisplay.OperationOpened` message — `:431-436`; `action_open_operation` — `:657-671`
- `DAGDisplay.FocusChanged` (t748_2) — `:438-443`
- `_node_order` / `_focused_idx` — initialized at `:445-456`, populated in `load_dag()` at `:461-499`
- App-level `@on(DAGDisplay.OperationOpened)` — `brainstorm_app.py:3966-3973`
- No `on_key` override in `DAGDisplay`; no binding for `p`/`l`/`x` in `DAGDisplay`, `BrainstormApp`, or `TuiSwitcherMixin` (the `x` in `TuiSwitcherOverlay:337` is on a modal overlay and won't intercept Graph-tab keystrokes).
- `BrainstormApp = TuiSwitcherMixin, App` at `brainstorm_app.py:1830` — `self.notify` / `self.push_screen` available.

## Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — add 2 bindings, 2 message classes, 2 action methods
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add 2 `@on(...)` handlers

## Implementation

### 1. `brainstorm_dag_display.py` — bindings, messages, actions

Append to `BINDINGS` (after the existing `Binding("o", "open_operation", "Operation", show=True)`):

```python
Binding("p", "view_proposal", "Proposal", show=True),
Binding("l", "view_plan", "Plan", show=True),
```

Add two `Message` subclasses next to `OperationOpened`:

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

Add two `action_*` methods (mirroring the guard pattern of `action_open_operation`, but session-IO-free since only `node_id` is needed):

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

(Design note: `action_open_operation` does direct session-IO because it needs `created_by_group` to populate the event. For proposal/plan, only the `node_id` is needed — the App reads the file and pushes the modal.)

### 2. `brainstorm_app.py` — `@on` handlers

Right after the existing `@on(DAGDisplay.OperationOpened)` handler at `:3966-3973`, add:

```python
@on(DAGDisplay.ProposalRequested)
def on_dag_display_proposal_requested(
    self, event: DAGDisplay.ProposalRequested
) -> None:
    """Open SectionViewerScreen with the focused node's proposal ('p' key)."""
    try:
        proposal = read_proposal(self.session_path, event.node_id)
    except Exception:
        self.notify(
            f"No proposal for {event.node_id}", severity="warning"
        )
        return
    self.push_screen(
        SectionViewerScreen(proposal, title=f"Proposal: {event.node_id}")
    )

@on(DAGDisplay.PlanRequested)
def on_dag_display_plan_requested(
    self, event: DAGDisplay.PlanRequested
) -> None:
    """Open SectionViewerScreen with the focused node's plan ('l' key)."""
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

No new imports — `read_proposal`, `read_plan`, and `SectionViewerScreen` are already imported at the top of `brainstorm_app.py`.

## Verification

1. Launch `ait brainstorm`, switch to (G)raph tab.
2. Focus a node and press `p` — `SectionViewerScreen` opens titled `Proposal: <node_id>` showing the proposal body.
3. Focus a node with a plan and press `l` — `SectionViewerScreen` opens titled `Plan: <node_id>`.
4. Focus a node WITHOUT a plan (e.g., a non-`detail` operation node) and press `l` — warning toast "No plan generated for …"; no screen pushed.
5. Footer surfaces `p Proposal` and `l Plan` adjacent to the existing entries (`j Next`, `k Prev`, `Enter Open`, `h Set HEAD`, `o Operation`, plus arrow nav from t748_1).
6. Regression: `Enter` still opens `NodeDetailModal`; `Esc` from `SectionViewerScreen` returns to Graph tab with focus preserved.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9. Archive via `./.aitask-scripts/aitask_archive.sh 748_3`.
