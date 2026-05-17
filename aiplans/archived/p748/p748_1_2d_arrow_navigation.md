---
Task: t748_1_2d_arrow_navigation.md
Parent Task: aitasks/t748_browsable_node_graph.md
Sibling Tasks: aitasks/t748/t748_2_inline_detail_pane.md, aitasks/t748/t748_3_view_proposal_plan_keys.md, aitasks/t748/t748_4_compare_with_picker.md, aitasks/t748/t748_5_manual_verification_browsable_node_graph.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-17 11:12
---

# t748_1 — 2D arrow-key navigation in `DAGDisplay`

## Context

Part of t748 (Browsable Node Graph). The brainstorm Graph tab currently navigates the DAG only via `j` / `k` (flat top-to-bottom-left-to-right walk over `_node_order`) — but `j` already conflicts with the app-wide `TuiSwitcherMixin` binding (`.aitask-scripts/lib/tui_switcher.py:863` — `Binding("j", "tui_switcher", ...)`) used in every aitasks TUI. This child replaces the broken `j` / `k` scheme with true 2D arrow-key navigation matching the visual layout: `↑` / `↓` between layers, `←` / `→` within a layer. All four bindings must be footer-visible (`show=True`) per CLAUDE.md "TUI footer must surface keys".

External plan file at `aiplans/p748/p748_1_2d_arrow_navigation.md` was verified against the live source: `BINDINGS` at lines 407-412 (all `show=True`); constants `BOX_WIDTH=28` / `COL_GAP=4` / `COL_STRIDE=32` at lines 37-39; `_layers` / `_node_order` / `_focused_idx` in `__init__` at lines 436-447; `action_next_node` / `action_prev_node` at 537-547. A local `center_x(col) = col * COL_STRIDE + BOX_WIDTH // 2` already lives inside `_render_edges` (line 338) — the new layer-snap helper mirrors that formula for consistency.

Sibling t748_2 (inline detail pane) owns the `DAGDisplay.FocusChanged(node_id)` message class and has not yet been started (no `plan_verified` entries on any p748 sibling). This task will NOT post `FocusChanged` — that wiring is deferred to t748_2's implementer, who will need to extend the four new arrow actions added here (plus existing `action_open_node` / `action_head_node` / `action_open_operation`) with `self.post_message(self.FocusChanged(...))`. Deferral is documented in Final Implementation Notes.

## Files to Modify

`.aitask-scripts/brainstorm/brainstorm_dag_display.py` — only file touched.

## Implementation

### Step 1 — Replace `j` / `k` bindings with four arrow bindings

In `DAGDisplay.BINDINGS` (lines 407-412), DELETE the two existing flat-walk bindings:

```python
Binding("j", "next_node", "Next", show=True),   # remove (conflicts with TuiSwitcherMixin)
Binding("k", "prev_node", "Prev", show=True),   # remove (symmetric removal)
```

And ADD four arrow bindings:

```python
Binding("up",    "prev_layer", "↑ Layer", show=True),
Binding("down",  "next_layer", "↓ Layer", show=True),
Binding("left",  "prev_col",   "← Col",   show=True),
Binding("right", "next_col",   "→ Col",   show=True),
```

Keep the other three bindings (`enter`, `h`, `o`) unchanged.

### Step 2 — Remove `action_next_node` / `action_prev_node`

Delete the two action methods at lines 537-547 (no callers remain after the bindings are dropped — confirm via `grep -n 'next_node\|prev_node' .aitask-scripts/brainstorm/`).

### Step 3 — Add three private helpers on `DAGDisplay`

```python
def _layer_col_from_focused(self) -> tuple[int, int] | None:
    if not self._node_order or not self._layers:
        return None
    focused_id = self._node_order[self._focused_idx]
    for li, layer in enumerate(self._layers):
        if focused_id in layer:
            return (li, layer.index(focused_id))
    return None

def _focused_idx_from_layer_col(self, layer_idx: int, col_idx: int) -> int:
    target_id = self._layers[layer_idx][col_idx]
    return self._node_order.index(target_id)

def _col_center(self, col_idx: int) -> int:
    # Matches local center_x() in _render_edges (line 338) — keep in sync.
    return col_idx * COL_STRIDE + BOX_WIDTH // 2
```

### Step 4 — Add four action methods

- `action_prev_col` / `action_next_col`: derive `(li, ci)` via `_layer_col_from_focused()`; clamp at layer edges (no wrap); update `_focused_idx` via `_focused_idx_from_layer_col`; call `_render_dag()`.
- `action_prev_layer` / `action_next_layer`: derive `(li, ci)`; clamp at first/last layer; compute `src_center = self._col_center(ci)`; pick `best_ci = min(range(len(target_layer)), key=lambda c: abs(self._col_center(c) - src_center))`; update `_focused_idx` and re-render.

All four return immediately when `_layer_col_from_focused()` returns `None`.

### Step 5 — Sibling note (FocusChanged deferred)

Add to Final Implementation Notes:

> t748_2 owns `DAGDisplay.FocusChanged(node_id)`. When t748_2 lands, its implementer must add `self.post_message(self.FocusChanged(self._node_order[self._focused_idx]))` calls into the four new arrow actions (`action_prev_layer`, `action_next_layer`, `action_prev_col`, `action_next_col`) and into existing `action_open_node` / `action_head_node` / `action_open_operation`.

## Verification

1. Launch `ait brainstorm` on a session with a multi-layer DAG.
2. Tab to (G)raph. Footer shows: `Enter Open | h Set HEAD | o Operation | ↑ Layer | ↓ Layer | ← Col | → Col` (note: no `j` / `k` — confirms cleanup).
3. Press `j` on the Graph tab — the TUI switcher overlay opens (confirms the global binding now reaches the app unobstructed).
4. `←` / `→` — focus moves within layer, clamps at edges, does not wrap.
5. `↓` / `↑` — focus jumps to nearest-center column in the adjacent layer, clamps at first / last layer.
6. Tab away and back to Graph — focus position preserved.

## Step 9

Standard archival via `./.aitask-scripts/aitask_archive.sh 748_1` (see parent plan's "Step 9 (parent archival)" section).

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — `BINDINGS` now lists four arrow bindings (`up`/`down`/`left`/`right` → `prev_layer`/`next_layer`/`prev_col`/`next_col`, all `show=True`) in place of the removed `j` (`next_node`) and `k` (`prev_node`). Three private helpers added (`_layer_col_from_focused`, `_focused_idx_from_layer_col`, `_col_center`) and four action methods added (`action_prev_col`, `action_next_col`, `action_prev_layer`, `action_next_layer`). The original `action_next_node` / `action_prev_node` methods deleted. Layer-snap uses `min(range(len(target_layer)), key=lambda c: abs(self._col_center(c) - src_center))`.
  - `.aitask-scripts/brainstorm/brainstorm_app.py` — two unplanned but necessary follow-ups discovered during user testing of the first iteration: (a) the existing app-level `on_key` intercept at lines 2591-2599 swallowed `up` on the Graph tab and refocused the Tabs widget — deleted, since DAGDisplay now owns `up`; (b) `on_tabbed_content_tab_activated` extended to call `self.query_one(DAGDisplay).focus()` when `tab_dag` is activated, otherwise focus stayed on the Tabs widget and arrow keys never reached DAGDisplay.
- **Deviations from plan:** The original plan touched only `brainstorm_dag_display.py`. The two `brainstorm_app.py` edits were added during the Step 8 review loop after the first iteration manifested as "arrows do nothing" in `brainstorm-635`. Verification step 3 in the plan ("pressing `j` opens the TUI switcher") is now expected — `j` reaches the App-level binding because DAGDisplay no longer claims it. Auto-focus on `tab_dag` activation makes "Tab away and back to Graph — focus preserved" work as written.
- **Issues encountered:**
  - First Step 8 iteration shipped only the dag_display changes; user reported `j` working (App-level TuiSwitcherMixin) but arrows doing nothing. Diagnosed by greppinig for `tab_dag` + `event.key` in `brainstorm_app.py` — found the `up`-intercept at line 2594 and the absence of a focus call in `on_tabbed_content_tab_activated`.
  - The `up`-intercept's comment claimed "no row widget on this tab" — that was historically true (before DAGDisplay had per-key navigation worth keeping focus for). The comment is now stale and the intercept is deleted; users who want to escape from DAGDisplay back to the tab bar can use Shift+Tab or letter-key tab switches.
- **Key decisions:**
  - Removed `j`/`k` symmetrically (rather than rebinding to other letters) per user direction during Step 6 planning, since `j` conflicts with `TuiSwitcherMixin` and asymmetric removal would be confusing.
  - Auto-focus DAGDisplay via `on_tabbed_content_tab_activated` (covers all activation paths: `g` letter key, programmatic `tabbed.active = "tab_dag"`, future click-to-tab) rather than only in `action_tab_graph`.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t748_2 (`FocusChanged`):** When t748_2 adds the inline detail pane and its `DAGDisplay.FocusChanged(node_id)` message class, the implementer MUST add `self.post_message(self.FocusChanged(self._node_order[self._focused_idx]))` to all four new arrow actions added here (`action_prev_layer`, `action_next_layer`, `action_prev_col`, `action_next_col`) AND to the existing `action_open_node` / `action_head_node` / `action_open_operation`. Otherwise the detail pane will be stale after arrow navigation.
  - **t748_3 (proposal/plan keys), t748_4 (compare picker):** Bindings on DAGDisplay should be defined with `show=True` to stay consistent with the footer-visible convention this task established. The bindings list is sorted in screen-priority order (navigation first, then `enter`/`h`/`o`/etc.); new bindings should slot in at the appropriate semantic group.
  - **t748_5 (manual verification):** When writing the manual-verification checklist, include items for: (a) arrows clamp at first/last layer (no wrap), (b) arrows clamp at leftmost/rightmost column within a layer (no wrap), (c) up/down picks the nearest-center column when the target layer has different width, (d) Graph tab auto-focuses DAGDisplay on activation, (e) `j` opens the TUI switcher overlay from the Graph tab (regression check that the global binding reaches the app).
