---
Task: t788_graph_tab_breaks_tab_navigation.md
Base branch: main
plan_verified: []
---

## Context

In `ait brainstorm` (Textual TUI), the top tab row (Dashboard / Graph /
Compare / Actions / Status) is navigable with left/right arrows. The
expected UX, consistent across every other tab, is:

- Left/right on the Tabs widget switches tabs *without* leaving the tab row.
- Pressing Down from the tab row enters the active tab's content.
- Pressing Up from the first row of any tab's content refocuses the tab row.

The **Graph tab breaks both halves of this contract** because of two
independent bugs in the brainstorm app:

1. **`on_tabbed_content_tab_activated`** explicitly calls
   `DAGDisplay.focus()` when `tab_dag` activates. This means simply
   navigating left/right across the tab row *into* the Graph tab steals
   focus from the Tabs widget down into the graph nodes — different from
   every other tab.

2. **`DAGDisplay.action_prev_layer`** (bound to Up) returns silently when
   the focused node is already at layer 0. There is no escalation to the
   tab row, so once the user is in the graph there is no way to press Up
   back out of it (whereas dashboard's `_navigate_rows` refocuses Tabs at
   the top boundary — see `brainstorm_app.py:3108-3111`).

The "down from tabs enters content" half is also missing for `tab_dag`:
the `tab_to_container` mapping at `brainstorm_app.py:2594-2598` has no
entry for it, because the auto-focus on activation made it unnecessary.
Once we remove the auto-focus, we need a Down handler so the user can
actually enter the graph deliberately.

## Files to modify

- `/home/ddt/Work/aitasks/.aitask-scripts/brainstorm/brainstorm_dag_display.py`
- `/home/ddt/Work/aitasks/.aitask-scripts/brainstorm/brainstorm_app.py`

## Fix 1 — DAGDisplay: emit a top-boundary message at layer 0

In `brainstorm_dag_display.py`, add a new `Message` subclass and have
`action_prev_layer` post it when the focused node is at the top layer.
This mirrors the existing `FocusChanged` / `NodeSelected` / etc. message
pattern already used by `DAGDisplay` (see lines 433-481).

Add (near the other `class … Message` definitions, ~line 481):

```python
class TopBoundaryHit(Message):
    """Emitted when Up is pressed while focus is on a layer-0 node.

    The app handles this by refocusing the top tab row so the user can
    exit the graph via Up, mirroring dashboard/actions/status behavior.
    """
```

Modify `action_prev_layer` (lines 636-654) so that when `li == 0`, it
posts the message instead of silently returning:

```python
def action_prev_layer(self) -> None:
    """Move focus to the nearest-center column of the previous layer (↑).

    At the top layer, emit TopBoundaryHit so the app can refocus the
    tab row instead of dead-ending here.
    """
    pos = self._layer_col_from_focused()
    if pos is None:
        return
    li, ci = pos
    if li == 0:
        self.post_message(self.TopBoundaryHit())
        return
    # … existing logic unchanged …
```

No other changes inside DAGDisplay are needed — `action_next_col` /
`action_prev_col` / `action_next_layer` keep their current bounded
behavior (left/right at row boundaries and Down at the last layer do not
escalate; only Up at the top does).

## Fix 2 — brainstorm_app: drop auto-focus on tab_dag activation

In `brainstorm_app.py`, update `on_tabbed_content_tab_activated`
(lines 3560-3568). Remove the `tab_dag` branch so the Tabs widget keeps
focus when the user switches tabs via left/right, identical to every
other tab:

```python
def on_tabbed_content_tab_activated(self, event) -> None:
    """Refresh Status tab when it becomes active."""
    if event.pane.id == "tab_status":
        self._refresh_status_tab()
```

Update the docstring (was "focus DAG on Graph tab") to drop the
no-longer-true claim.

## Fix 3 — brainstorm_app: Down from tabs enters DAGDisplay

In the `on_key` "Down from tab bar" block (lines 2578-2604), add a
`tab_dag` case so the user can deliberately enter the graph from the
tab row. The compare-tab branch above it (which `.focus()`es the
DataTable directly) is the right precedent — DAGDisplay is similarly
"the single focusable thing on this tab".

Insert *before* the `tab_to_container` mapping block (after the existing
`tab_compare` early-return, ~line 2593):

```python
if tabbed.active == "tab_dag":
    try:
        dag = self.query_one(DAGDisplay)
    except Exception:
        dag = None
    if dag is not None:
        dag.focus()
        event.prevent_default()
        event.stop()
        return
```

## Fix 4 — brainstorm_app: handle DAGDisplay.TopBoundaryHit

In `brainstorm_app.py`, add a message handler that refocuses the Tabs
widget when DAGDisplay reports a top-boundary hit. Place it next to the
existing DAG-related handlers (e.g. near
`on_tabbed_content_tab_activated`, or near other `on_dagdisplay_*`
handlers — `grep -n "on_dagdisplay_" .aitask-scripts/brainstorm/brainstorm_app.py`
will identify the right cluster during implementation):

```python
def on_dagdisplay_top_boundary_hit(self, event) -> None:
    """Refocus the tab row when Up is pressed at the top of the DAG."""
    try:
        tabs_widget = self.query_one(TabbedContent).query_one(Tabs)
    except Exception:
        return
    tabs_widget.focus()
    event.stop()
```

Naming: Textual derives the handler name by snake-casing the
`Message`'s fully-qualified name. `DAGDisplay.TopBoundaryHit` becomes
`on_dagdisplay_top_boundary_hit`. If a quick log inspection during
implementation shows the auto-derived name differs (Textual's exact
snake-case rules can be finicky for adjacent capitals), rename the
handler to match — the existing `on_dagdisplay_focus_changed` (or
similar) in the same file is the local source of truth for the
convention.

## What is intentionally NOT changed

- The right-pane (`#dag_node_info`) DimensionRow up/down navigation at
  `brainstorm_app.py:2624-2633` stays as-is. That code already only fires
  when a DimensionRow is focused, so removing DAGDisplay auto-focus does
  not break it. Up at the top of the DimensionRow list still falls
  through to the rest of `on_key` and does not currently escalate to the
  tab row — the user reported only the graph-tab path, and the dashboard
  / right-pane DimensionRow story is out of scope.
- `Tab` / `shift+tab` toggling between DAGDisplay and the right pane
  (lines 2649-2653) is unchanged.
- Keyboard shortcut `g` / `action_tab_graph` (line 2900) still switches
  to the graph tab. Tab activation no longer steals focus, so after `g`
  the user is on the Tabs widget — consistent with `d` / `c` / `a` / `s`
  for the other tabs.

## Verification

1. **Manual smoke test in `ait brainstorm`** (this is a Textual TUI;
   automated tests don't cover keyboard focus flow):
   - Launch `ait brainstorm` in a session with at least one graph node.
   - From the Dashboard tab, press Right twice → focus should remain on
     the tab row, now showing Graph as active. The DAG should *not*
     have a highlighted/focused node.
   - Press Down → focus should move into the DAG (a node becomes
     focus-highlighted).
   - Press Up repeatedly until the focused node is in layer 0. Press Up
     once more → focus should return to the tab row.
   - Press Right → tab nav should now move to Compare without entering
     the graph.
   - Repeat the "Up exits to tabs" check from each of the other tabs
     (Dashboard, Actions, Status) to confirm parity with the pre-existing
     behavior (regression check).
2. **No-regression checks:**
   - With a DimensionRow focused in the right-hand `#dag_node_info`
     pane (achieved via `Tab` toggle from DAGDisplay), confirm up/down
     still navigates among DimensionRows.
   - Confirm `g` keyboard shortcut still activates the Graph tab.
   - Confirm `h` / `enter` / `o` / `p` / `l` / `x` on a focused DAG node
     still trigger their respective actions (these depend on DAGDisplay
     having focus — verify by pressing Down to enter the graph first).
3. **Lint:** `shellcheck` does not apply (Python). Static checks: import
   `Message` and `Tabs` are already imported in the respective files
   (verify with `grep -n "^from textual" <file>` during implementation
   and add the imports only if grep shows them missing).

## Step 9 — Post-Implementation

Follow the standard task-workflow Step 9 process: review changes,
commit with `bug: Fix graph tab stealing focus from tab row (t788)`,
update the plan with Final Implementation Notes, and archive.

## Final Implementation Notes

- **Actual work done:** All four fixes from the plan were applied
  exactly as designed.
  - `brainstorm_dag_display.py`: Added `TopBoundaryHit(Message)`
    class beside the existing `Message` subclasses. Modified
    `action_prev_layer` to `post_message(self.TopBoundaryHit())` when
    `li == 0` (before its early return).
  - `brainstorm_app.py`: Stripped the `elif event.pane.id == "tab_dag":
    DAGDisplay.focus()` branch and its docstring claim from
    `on_tabbed_content_tab_activated`. Inserted a `tab_dag` early-return
    case in the Down-from-tabs block in `on_key` (mirrors the existing
    `tab_compare` precedent). Added `on_dag_display_top_boundary_hit`
    decorated with `@on(DAGDisplay.TopBoundaryHit)`, placed adjacent to
    the existing `on_dag_display_focus_changed` handler.
- **Deviations from plan:** None. The handler-name uncertainty noted in
  the plan (`on_dagdisplay_top_boundary_hit` vs
  `on_dag_display_top_boundary_hit`) was resolved during implementation
  by inspecting existing handlers — the codebase uses
  `on_dag_display_*` (underscore between DAG and Display), driven by the
  `@on(DAGDisplay.MessageName)` decorator pattern rather than Textual's
  auto-derived names. Used the decorator pattern for the new handler too.
- **Issues encountered:** None. Both Python files pass `ast.parse`. No
  new imports required — `Message`, `Tabs`, and `TabbedContent` were
  already imported in both files.
- **Key decisions:** Used a posted `Message` (Textual idiom) rather than
  exposing layer state via a public method, keeping `DAGDisplay`'s
  layer/column internals encapsulated. The right-pane DimensionRow
  navigation (which already had its own non-escalating handler) was
  intentionally left alone — out of scope per the user's bug report.
- **Upstream defects identified:** None.

