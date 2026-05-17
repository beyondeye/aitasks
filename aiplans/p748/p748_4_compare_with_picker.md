---
Task: t748_4_compare_with_picker.md
Parent Task: aitasks/t748_browsable_node_graph.md
Sibling Tasks: aitasks/t748/t748_5_manual_verification_browsable_node_graph.md
Archived Sibling Plans: aiplans/archived/p748/p748_1_2d_arrow_navigation.md, aiplans/archived/p748/p748_2_inline_detail_pane.md, aiplans/archived/p748/p748_3_view_proposal_plan_keys.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-17 14:53
---

# t748_4 — Compare-with (`x`) — interactive second-node selection

## Context

Part of t748 (parent: `aitasks/t748_browsable_node_graph.md`, parent plan:
`aiplans/p748_browsable_node_graph.md`). Adds a `x` keybinding to the
brainstorm Graph tab that enters an interactive "pick second node" mode:
the currently-focused node becomes the anchor (rendered with a distinct
border color), the user moves with existing arrow / column / layer
navigation, `Enter` confirms the pick and jumps to the Compare tab with
the two nodes loaded into the diff matrix, `Esc` cancels.

The plan was verified against the current codebase on 2026-05-17. The
verification surfaced four refinements vs the originally-archived task
file (see "Verification deltas" at the bottom).

## Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — binding,
  pick-mode state, action methods, message class, anchor rendering.
- `.aitask-scripts/brainstorm/brainstorm_app.py` —
  `@on(DAGDisplay.CompareRequested)` handler.

## Reused infrastructure (verified line numbers)

- `DAGDisplay.OperationOpened` Message class at
  `brainstorm_dag_display.py:433-438` and `action_open_operation` at
  `brainstorm_dag_display.py:673-687` — message + action pattern to
  mirror for `CompareRequested`.
- `DAGDisplay.NodeSelected` at lines 419-424 and `action_open_node` at
  lines 651-660 — the action currently posts BOTH `NodeSelected` and
  `FocusChanged`; the new branch must preserve that behavior in the
  non-pick-mode path.
- `_build_compare_matrix(self, selected_nodes: list[str])` in
  `brainstorm_app.py:4032-4061` — accepts a list of node IDs, builds
  the Compare-tab `DataTable`. Called with `[anchor_id, picked_id]`.
- `TabbedContent` with `id="brainstorm_tabs"` at `brainstorm_app.py:2527`;
  the Compare `TabPane` has `id="tab_compare"` at line 2546. Switching
  via `self.query_one(TabbedContent).active = "tab_compare"`.
- `_render_node_box(...)` at `brainstorm_dag_display.py:192-198` —
  current signature accepts `node_id, description, is_head, is_focused,
  operation=""`. Border style picked via `border_style = HEAD_BORDER_STYLE
  if is_head else BORDER_STYLE` at line 206. Extend to accept
  `is_anchor: bool = False`, with `is_anchor` taking precedence over
  `is_head` for the border color.
- `_render_layer(...)` at `brainstorm_dag_display.py:270-309` — must be
  extended to accept and forward `compare_anchor_id`. Currently called
  once from `_render_dag` at lines 539-542.
- `OP_BADGE_STYLES` dict at lines 53-60; `HEAD_BORDER_STYLE`
  (`#50FA7B` bold) at line 45 and `FOCUSED_BG` (`#44475A`) at line 46
  are the precedent for per-node style differentiation.
- Existing `@on(DAGDisplay.*)` handlers in `brainstorm_app.py` at
  3952/3957/3966/3975/3992 — pattern for `CompareRequested` handler.
- `DAGDisplay.__init__` at lines 461-472 — where new pick-mode state
  attributes are added.

## Implementation Plan

### Step 1 — Add bindings

Append to `DAGDisplay.BINDINGS` (currently `brainstorm_dag_display.py:407-417`):

```python
Binding("x", "compare_with", "Compare", show=True),
Binding("escape", "cancel_compare", show=False),
```

### Step 2 — Define anchor border style

Below `FOCUSED_BG` (around line 47, alongside `HEAD_BORDER_STYLE`):

```python
ANCHOR_BORDER_STYLE = Style(color="#FFB86C", bold=True)  # Dracula orange
```

Chosen because Dracula yellow (`#F1FA8C`) is already used by the
`compare` op badge; orange is unused in `OP_BADGE_STYLES` and reads
cleanly as "attention/selected".

### Step 3 — Add pick-mode state to `DAGDisplay.__init__`

Inside `__init__` (lines 461-472), after `self._node_line_map`:

```python
self._compare_anchor_id: str | None = None
self._compare_pick_mode: bool = False
```

### Step 4 — Add `CompareRequested` Message class

Below `PlanRequested` (lines 454-459):

```python
class CompareRequested(Message):
    """Emitted when a second node has been picked for compare."""

    def __init__(self, anchor_id: str, picked_id: str) -> None:
        super().__init__()
        self.anchor_id = anchor_id
        self.picked_id = picked_id
```

### Step 5 — Action methods

Add alongside the other actions (after `action_view_plan` around line
701). All notifications use `self.app.notify(...)` to match the existing
precedent in `action_open_operation` (line 681):

```python
def action_compare_with(self) -> None:
    """Enter compare-pick mode (x key)."""
    if not self._node_order:
        return
    if self._compare_pick_mode:
        self.app.notify(
            "Already in compare mode — Enter to confirm, Esc to cancel",
            severity="information",
        )
        return
    focused_id = self._node_order[self._focused_idx]
    self._compare_anchor_id = focused_id
    self._compare_pick_mode = True
    self._render_dag()
    self.app.notify(
        f"Select node to compare with {focused_id} — "
        "Enter=confirm, Esc=cancel"
    )

def action_cancel_compare(self) -> None:
    """Cancel compare-pick mode (escape key)."""
    if not self._compare_pick_mode:
        return
    self._compare_anchor_id = None
    self._compare_pick_mode = False
    self._render_dag()
    self.app.notify("Compare cancelled")
```

### Step 6 — Override `action_open_node` (Enter handling)

Replace `action_open_node` (currently lines 651-660). Preserve the
existing `FocusChanged` emission in the non-pick-mode path:

```python
def action_open_node(self) -> None:
    """Post NodeSelected or finalize compare-pick (enter key)."""
    if not self._node_order:
        return
    focused_id = self._node_order[self._focused_idx]
    if self._compare_pick_mode:
        if focused_id == self._compare_anchor_id:
            self.app.notify(
                "Pick a different node",
                severity="warning",
            )
            return
        anchor = self._compare_anchor_id
        self._compare_anchor_id = None
        self._compare_pick_mode = False
        self._render_dag()
        self.post_message(self.CompareRequested(anchor, focused_id))
        return
    self.post_message(self.NodeSelected(focused_id))
    self.post_message(self.FocusChanged(focused_id))
```

Pick-mode does NOT cancel on focus-change actions (arrows / column /
layer nav) — those actions only update `_focused_idx` and re-render,
which is exactly what the user wants while choosing the second node.
The anchor styling is re-applied on every re-render because
`_render_dag` reads `self._compare_anchor_id` (see Step 8).

### Step 7 — Extend `_render_node_box` to accept `is_anchor`

Update the signature at lines 192-198 to:

```python
def _render_node_box(
    node_id: str,
    description: str,
    is_head: bool,
    is_focused: bool,
    operation: str = "",
    is_anchor: bool = False,
) -> list[Text]:
```

Replace the border-style selection at line 206:

```python
if is_anchor:
    border_style = ANCHOR_BORDER_STYLE
elif is_head:
    border_style = HEAD_BORDER_STYLE
else:
    border_style = BORDER_STYLE
```

`is_anchor` takes precedence over `is_head` so that an anchor on the
HEAD node is still visually distinguishable from a non-anchor HEAD.
`FOCUSED_BG` is independent and keeps stacking on top — when the user
moves focus through other nodes after picking the anchor, the anchor
node retains its orange border without focus-purple background, and
the currently-focused node gets focus-purple as usual.

`NODE_ROWS` stays at `5` — no row change.

### Step 8 — Plumb `compare_anchor_id` through `_render_layer` and `_render_dag`

Update `_render_layer` signature at lines 270-277:

```python
def _render_layer(
    layer: list[str],
    node_descs: dict[str, str],
    head: str | None,
    focused_id: str | None,
    total_width: int,
    node_op_map: dict[str, str] | None = None,
    compare_anchor_id: str | None = None,
) -> list[Text]:
```

Update the `_render_node_box` call inside it (lines 283-289):

```python
box = _render_node_box(
    node_id=nid,
    description=node_descs.get(nid, ""),
    is_head=(nid == head),
    is_focused=(nid == focused_id),
    operation=op_map.get(nid, ""),
    is_anchor=(compare_anchor_id is not None and nid == compare_anchor_id),
)
```

Update the `_render_layer` callsite inside `_render_dag` at lines
539-542 to pass `compare_anchor_id=self._compare_anchor_id`:

```python
layer_lines = _render_layer(
    layer, self._node_descs, self._head, focused_id, total_width,
    node_op_map=self._node_op_map,
    compare_anchor_id=self._compare_anchor_id,
)
```

### Step 9 — App-level handler in `brainstorm_app.py`

Alongside other `@on(DAGDisplay.*)` handlers (around lines 3952-3995):

```python
@on(DAGDisplay.CompareRequested)
def on_dag_display_compare_requested(
    self, event: DAGDisplay.CompareRequested
) -> None:
    self._build_compare_matrix([event.anchor_id, event.picked_id])
    self.query_one(TabbedContent).active = "tab_compare"
```

## Verification

1. Launch `ait brainstorm` on a session with at least 3 nodes; switch
   to the (G)raph tab.
2. Focus a node and press `x` — toast appears: `"Select node to compare
   with <id> — Enter=confirm, Esc=cancel"`. Anchor node renders with
   an **orange** border (`#FFB86C` bold), visually distinct from
   HEAD-green and focus-purple.
3. Move with arrows / column / layer nav — focus moves; the anchor
   remains visually distinct, including when the anchor is also the
   currently-focused node (orange border + purple bg) and when focus
   has moved away (orange border + no purple bg).
4. Press `Enter` on a different node — Compare tab activates, showing
   the diff matrix for `[anchor, picked]`. Anchor styling clears.
5. Repeat step 2, then press `Esc` — toast `"Compare cancelled"`,
   anchor styling clears, Graph tab remains.
6. Repeat step 2, press `Enter` on the anchor itself — toast `"Pick a
   different node"` (warning severity), still in pick mode.
7. Press `x` twice in a row — second press emits the "Already in
   compare mode" toast and does not change the anchor.
8. Press `Esc` outside pick mode — no-op, no toast.
9. Regression: outside pick mode, `Enter` on a focused node opens
   `NodeDetailModal` as before AND posts `FocusChanged` (verify by
   ensuring the inline detail pane on the right side updates).
10. Regression: an anchor on a `compare` op-badge node renders orange
    border around a yellow `[compare]` badge — both visible, no clash.
11. Regression: pressing `x` with the focused node being the HEAD —
    the anchor renders orange (overriding green HEAD border) until
    confirmed/cancelled, then the HEAD-green border returns.

## Verification deltas (refinements vs original task description)

1. **Line-number references in original task were off.** The task body
   listed `OperationOpened` + `action_open_operation` at lines 429-434
   and 565-578; current positions are 433-438 and 673-687. Updated
   above.

2. **`action_open_node` posts `FocusChanged` in addition to
   `NodeSelected` today.** The original Step 5 (and the original
   archived plan's Step 6) showed a rewrite that dropped the
   `FocusChanged` emission — this would have regressed the inline
   detail pane (t748_2). Fix: preserve `post_message(FocusChanged)`
   in the non-pick-mode path (see Step 6).

3. **`_render_layer` did not previously take `compare_anchor_id`.**
   The original plan said to pass `is_anchor` to `_render_node_box`
   from `_render_layer`, but `_render_layer` has no access to
   `_compare_anchor_id`. Added the parameter in Step 8 and threaded
   it through `_render_dag`.

4. **Anchor color changed from terminal yellow → Dracula orange
   `#FFB86C`.** Dracula yellow `#F1FA8C` is already used by the
   `compare` op-badge style (line 55 of `brainstorm_dag_display.py`),
   so a yellow border on a yellow-badge node would be muddy. Orange
   is unused in `OP_BADGE_STYLES` and pairs cleanly with the existing
   HEAD-green / focus-purple precedents. User-confirmed during plan
   verification.

5. **`notify(...)` calls use `self.app.notify(...)`** to match the
   existing precedent at `action_open_operation` line 681. The
   original plan used bare `self.notify(...)`.

## Step 10 (cleanup, archival, merge)

See parent plan `aiplans/p748_browsable_node_graph.md` and the
shared task-workflow Step 9 (`./.aitask-scripts/aitask_archive.sh
748_4`).

## Post-Review Changes

### Change Request 1 (2026-05-17 14:55)

- **Requested by user:** After testing in `ait brainstorm 635` (a
  session with only two nodes), the Compare tab appeared to "close
  immediately" after picking the second node — suggesting a swallowed
  exception or an order-of-operations bug.
- **Root cause hypothesis:** `_build_compare_matrix` calls
  `query_one("#compare_content", VerticalScroll)` and
  `container.remove_children()`. The existing working callsite
  (`_on_compare_selected`) only fires while the user is already on
  the Compare tab — so `#compare_content` is mounted and the
  modification is visible. Our new `@on(CompareRequested)` path ran
  `_build_compare_matrix(...)` first and only then switched the
  active tab, so the user saw the post-switch view rendered against
  a `#compare_content` modified in the wrong order (or whose
  children update was overwritten by Textual's TabbedContent
  activation). The visible symptom was "screen closes immediately".
  Additionally, any exception raised inside the `@on` handler is
  swallowed silently by Textual's message-dispatch infra, hiding the
  real error from the user.
- **Changes made:** Reordered the `@on(DAGDisplay.CompareRequested)`
  handler in `brainstorm_app.py` to (1) set `tabbed.active = "tab_compare"`
  first, then (2) defer `_build_compare_matrix` via
  `call_after_refresh` so the Compare TabPane is fully activated/
  mounted before the matrix is rebuilt. Wrapped the deferred build in
  a `try/except` that surfaces any exception via `self.notify(...,
  severity="error")` so future failures are visible instead of
  silent.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`.

### Change Request 2 (2026-05-17 15:10)

- **Requested by user:** Re-test after Change Request 1 still showed
  the "closes immediately" symptom on first attempt, and now the
  second compare attempt surfaced `"Compare build failed: node id
  already mounted"` (caught by the new try/except notify wrapper).
  User asked whether the Enter shortcut might be conflicting with
  the existing node-detail Enter binding.
- **Root cause confirmed:** The error pinpointed the real bug —
  `_build_compare_matrix` calls `container.remove_children()` then
  `container.mount(table)` synchronously. Both operations are
  async-queued in Textual; on the SECOND consecutive compare attempt,
  the previous `#compare_table` is still mounted when the new
  `mount(table)` fires, triggering `MountError("id already mounted")`.
  The existing modal-based callsite (`_on_compare_selected`) does not
  trip this because typical user interaction inserts delay (modal
  close animation) between successive picks; the new keyboard-driven
  flow exercises it tightly.
- **Changes made:** Made `on_dag_display_compare_requested` an `async`
  handler that explicitly `await container.remove_children()` BEFORE
  calling `_build_compare_matrix(...)`. Pre-flushing guarantees no
  prior `#compare_table` is around when the new one mounts. Kept the
  `try/except → notify` wrapper for any other build-time failures.
- **Enter conflict ruled out:** The App-level `Binding("enter",
  "open_node_detail", ...)` is non-priority. DAGDisplay's
  `action_open_node` binding fires first and consumes Enter, so the
  App-level binding does NOT additionally fire. No double-trigger.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`.

### Change Request 3 (2026-05-17 15:25)

- **Requested by user:** After Change Request 2, the second-compare
  "id already mounted" error is gone, but the new symptom is that
  the Compare tab "flashes twice" and the Graph tab comes back, both
  attempts. The matrix never sticks.
- **Root cause:** Textual auto-reverts the active TabPane when the
  currently-focused widget lives on the *deactivating* pane, so the
  focused widget stays visible. The user reaches the @on handler
  while `DAGDisplay` (focusable, lives in `tab_dag`) holds focus.
  Setting `tabbed.active = "tab_compare"` briefly switches the pane,
  but Textual then re-activates `tab_dag` to keep `DAGDisplay`
  visible — manifesting as a flash, then revert.
- **Changes made:** Before activating `tab_compare`, the handler
  now shifts focus off `DAGDisplay` by focusing the parent `Tabs`
  widget (the tab bar) — `tabbed.query_one(Tabs).focus()`. With no
  focusable widget pinned to `tab_dag`, the activation sticks. After
  `_build_compare_matrix` mounts the table, its existing
  `call_after_refresh(table.focus)` finishes the focus shift to
  `#compare_table` so keyboard navigation works.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`.

### Change Request 4 (2026-05-17 15:40)

- **Requested by user:** The "Select node to compare with X —
  Enter=confirm, Esc=cancel" toast lingers visibly even after the
  user has confirmed or cancelled the pick. In other Textual TUIs,
  toasts auto-hide once they are no longer relevant.
- **Changes made:** In `brainstorm_dag_display.py`,
  `action_open_node` (compare-confirm path) and `action_cancel_compare`
  now call `self.app.clear_notifications()` (wrapped in
  `try/except AttributeError` for older Textual versions) just before
  posting `CompareRequested` / showing the "Compare cancelled" toast.
  Also added explicit short `timeout=2` (cancelled / already-in-mode)
  and `timeout=3` (entry hint) on the surrounding `notify` calls so
  the toast self-dismisses even if `clear_notifications` is
  unavailable.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_dag_display.py`.
