---
priority: medium
effort: low
depends: [t748_2]
issue_type: enhancement
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-17 10:12
updated_at: 2026-05-17 14:32
completed_at: 2026-05-17 14:32
---

## Context

Part of t748 (parent: `aitasks/t748_browsable_node_graph.md`, plan: `aiplans/p748_browsable_node_graph.md`). This child adds two new context-aware operations to the brainstorm Graph tab's focused node: `p` to view the proposal, `l` to view the plan. Both push the existing `SectionViewerScreen` modal.

**Important post-t749 reconciliation:** The originally-planned footer-visibility pass on EXISTING bindings (`j`/`k`/`Enter`/`h`) is **already done** as a side effect of t749_6's binding-refactor sweep. All four are declared as `Binding(..., show=True)` with proper `action_*` methods at `brainstorm_dag_display.py:407-412` and `537-578`; `on_key` no longer consumes them. `o` (operation detail) is also already `show=True`. This child therefore only needs to add the two NEW bindings.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — add bindings, action methods, and new message classes.
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add `@on(...)` handlers to push `SectionViewerScreen`.

## Reference Files for Patterns

- `DAGDisplay.OperationOpened` message + `action_open_operation` (`brainstorm_dag_display.py:429-434, 565-578`) — the pattern for "DAGDisplay posts a message; the App-level handler reads session data and pushes a screen". Mirror this for `ProposalRequested` and `PlanRequested`.
- App-level `@on(DAGDisplay.OperationOpened)` handler at `brainstorm_app.py:3863-3879` — the place to add the two new `@on` handlers.
- `SectionViewerScreen` at `lib/section_viewer.py:292` — constructor: `(content, title, section_filter=None)`.
- `read_proposal`, `read_plan` (in `.aitask-scripts/brainstorm/brainstorm_dag`) — readers for proposal and plan markdown.

## Implementation Plan

1. **Add bindings to `DAGDisplay.BINDINGS`:**
   ```python
   Binding("p", "view_proposal", "Proposal", show=True),
   Binding("l", "view_plan", "Plan", show=True),
   ```
2. **Add two new message classes on `DAGDisplay`:**
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
3. **Add action methods on `DAGDisplay`:**
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
   Routing via messages (instead of pushing screens directly from `DAGDisplay`) matches the OperationOpened pattern and keeps DAGDisplay free of session-IO.
4. **Add app-level `@on(DAGDisplay.ProposalRequested)` handler in `brainstorm_app.py`** that:
   - Reads the proposal: `read_proposal(self.session_path, event.node_id)`
   - Pushes `SectionViewerScreen(proposal_text, title=f"Proposal: {event.node_id}")`
   - On read failure (no file / IO error), `notify("No proposal for {node_id}", severity="warning")`.
5. **Add app-level `@on(DAGDisplay.PlanRequested)` handler** that:
   - Reads the plan: `read_plan(self.session_path, event.node_id)`
   - If the result is `None` or empty/whitespace, `notify("No plan generated for {node_id}", severity="warning")` and return without pushing.
   - Otherwise push `SectionViewerScreen(plan_text, title=f"Plan: {event.node_id}")`.
6. **`Enter` on a focused node continues unchanged** — already wired via `NodeSelected` → app-level handler — full `NodeDetailModal` opens.

## Verification Steps

1. Launch `ait brainstorm`, switch to (G)raph.
2. Focus a node and press `p` — `SectionViewerScreen` opens titled `Proposal: <node_id>` with the proposal content.
3. Focus a node that has a plan and press `l` — `SectionViewerScreen` opens titled `Plan: <node_id>`.
4. Focus a node that has NO plan (e.g., a non-`detail` operation node) and press `l` — a warning toast appears; no screen pushed.
5. Confirm the footer shows: `j Next`, `k Prev`, `Enter Open`, `h Set HEAD`, `o Operation`, `p Proposal`, `l Plan` (plus arrow nav from t748_1 if merged). All `show=True`.
6. Press `Enter` — `NodeDetailModal` still opens with Metadata/Proposal/Plan tabs (regression check).
7. Press `Esc` from `SectionViewerScreen` — returns to Graph tab.

## Notes for Sibling Tasks

- The Message → @on pattern is the canonical way to wire DAGDisplay actions that need session IO. t748_4's `CompareRequested` follows the same shape.
- `read_plan` returns `None` for nodes without a plan (e.g., from operations that don't produce plans). Always check before pushing the screen.
- The footer-visibility pass on existing bindings is intentionally NOT in this child's scope — t749 already did it.
