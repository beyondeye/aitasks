---
Task: t748_browsable_node_graph.md
Base branch: main
plan_verified: []
---

# t748 — Browsable node graph in brainstorm Graph tab

## Context

The brainstorm TUI's Graph tab (`tab_dag`, content = `DAGDisplay`) currently
renders an ASCII DAG of proposal nodes but offers minimal interaction:
linear `j`/`k` navigation through a flat node order, `Enter` to open a full
modal, and `h` to set HEAD. Compared to the Dashboard tab — which has a 40/60
horizontal split with an inline detail pane that updates reactively as the
focused `NodeRow` changes, plus per-dimension drill-in via `DimensionRow` →
`SectionViewerScreen` — the Graph tab feels much less browsable.

This task makes the Graph tab a first-class navigation surface:

1. **2D arrow-key navigation** through the DAG (up/down between layers,
   left/right within a layer) in addition to existing `j`/`k`.
2. **Inline detail pane** to the right of the DAG (mirroring Dashboard's
   horizontal split), showing the same metadata + dimensions block as the
   Dashboard for the focused node, updated reactively.
3. **Context-aware operations** on the focused node: view proposal, view
   plan, and compare-with-another-node (interactive arrow+Enter pick).
4. **All Graph-tab operations surfaced to the Textual footer** —
   pre-existing (`Enter`, `h`, `j`, `k`) and new (`p`, `l`, `x`,
   arrows). Today the footer hides most of these; the user wants them
   visible while the Graph tab is focused.

The user explicitly flagged this as a complex task that must be split into
child tasks, so this parent plan scopes the split — each child has its own
detailed plan written in `aiplans/p748/p748_<N>_*.md`.

## Reused / preserved infrastructure

- `_show_node_detail(node_id)` — `brainstorm_app.py:2889`. The Dashboard's
  reactive detail-pane populator. We will mirror its exact output for the
  Graph tab; the user requested "same information and available operations
  as what is shown in dashboard tab when a node is selected".
- `DimensionRow` — `brainstorm_app.py:878` — focusable, posts `Activated`
  with `dim_key`. App's `on_dimension_row_activated`
  (`brainstorm_app.py:2959`) already routes to a filtered
  `SectionViewerScreen`. We will widen `_current_dashboard_node_id` so this
  handler also works when the focused node lives in the Graph tab.
- `SectionViewerScreen` — `lib/section_viewer.py:292` — pushable
  `ModalScreen` with `(content, title, section_filter)` constructor. Used
  for fullscreen view-proposal / view-plan from the Graph tab.
- `NodeDetailModal` — `brainstorm_app.py:377` — Metadata/Proposal/Plan
  tabbed modal. Stays as the `Enter`-on-focused-node target (unchanged).
- `_build_compare_matrix(selected_nodes)` — `brainstorm_app.py:3020`. Used
  to render the Compare tab matrix after picking the second node from the
  graph; we call it directly with `[anchor_id, picked_id]`.
- `DAGDisplay._layers` / `_node_order` / `_focused_idx` /
  `_node_line_map` — `brainstorm_dag_display.py:373-383`. We extend the
  navigation logic on top of the existing layout structures.
- Dashboard layout precedent: `brainstorm_app.py:1713-1722` — `TabPane` →
  `Horizontal` → `VerticalScroll(node_list_pane) | VerticalScroll(detail_pane)`.

## Sequencing — wait for t749 to land

t749 (`aitasks/t749_report_operation_that_generated_nod.md`,
status `Implementing`) refactors the information shown on nodes in the
brainstorm Dashboard tab — adding the operation that generated each
node, with expandable details (inputs, output, log, when run). t749 will
be split into child tasks of its own.

t748_2 of this plan deliberately **mirrors the Dashboard's
`_show_node_detail` output** for the Graph-tab inline detail pane.
Implementing t748_2 before t749 lands risks diverging the two panes:
either the Graph pane misses the new operation info t749 added, or it
re-implements it incorrectly.

**Action before resuming t748:**

1. Wait until all t749 children are archived (parent t749 archived, or
   at least all dashboard-rendering children landed).
2. Re-read `_show_node_detail` and the Dashboard `#dash_node_info`
   container population to capture the new structure (operation row,
   expand/collapse behavior, any new widget classes).
3. Update t748_2's plan in `aiplans/p748/p748_2_inline_detail_pane.md`
   to mirror the post-t749 detail rendering (including any new keys for
   "expand operation details" — those need to be added to the Graph
   tab's footer bindings too, per the footer-visibility deliverable).
4. If t749 introduces a new shared "node detail renderer" function,
   reuse it directly rather than re-cloning `_show_node_detail`.

The other three implementation children (t748_1 navigation, t748_3
view-proposal/view-plan + footer pass, t748_4 compare-with) are
**independent of t749** and could in principle be picked first — but
the user prefers to gate the whole parent on t749 to avoid context
churn.

This task should be marked `depends: [749]` (or `Postponed`) so it
doesn't surface in `aitask_pick` runs until t749 archives.

## Child task split (4 implementation children + 1 manual-verification sibling)

The four implementation children below are ordered so each is independently
testable, stacks cleanly on the previous one, and can be picked up in fresh
contexts.

### t748_1 — 2D arrow-key navigation in `DAGDisplay`

- Add `up` / `down` / `left` / `right` key handling alongside existing
  `j`/`k`. Track focus as a `(layer_idx, col_idx)` pair derived from the
  existing `_layers` structure; keep `_focused_idx` for the flat order.
- `left` / `right`: move within the current layer (clamp at edges).
- `up` / `down`: move to the adjacent layer, snapping to the column
  whose center is closest to the current column's center (so visually
  aligned nodes get a sensible up/down).
- `j` / `k` continue to walk the flat top-to-bottom-left-to-right order.
- Update `_render_dag()` to keep working — focus highlighting already
  uses `focused_id`, no change needed there.
- Verify TuiSwitcherMixin's `j` binding does not steal Graph-tab `j`
  (DAGDisplay's local `Binding("j", "next_node")` should win since
  DAGDisplay is the focused widget; confirm with a quick test).
- **Footer:** declare arrow bindings with appropriate footer labels
  (e.g. `Binding("up", "prev_layer", "↑ Layer", show=True)`,
  `Binding("right", "next_col", "→ Col", show=True)`, …) so the
  Textual footer surfaces them while the Graph tab is focused. (Arrow
  keys default to `show=False` in many Textual apps; we explicitly
  override that here per the user's footer-visibility preference.)
- **Files:** `.aitask-scripts/brainstorm/brainstorm_dag_display.py` only.
- Plan file: `aiplans/p748/p748_1_2d_arrow_navigation.md`.

### t748_2 — Horizontal split: DAG left, inline detail pane right

- Restructure `tab_dag` `TabPane` (`brainstorm_app.py:1723-1724`) into a
  `Horizontal` split mirroring `dashboard_split`:
  - Left (~60%): `DAGDisplay(id="dag_content")` (unchanged)
  - Right (~40%): `VerticalScroll(id="dag_detail_pane")` containing
    `Label(id="dag_node_title")` + `Container(id="dag_node_info")`.
- Add `DAGDisplay.FocusChanged(node_id)` `Message` and post it from
  `action_next_node` / `action_prev_node` and the new arrow-key actions
  introduced in t748_1 (whenever `_focused_idx` changes). Also post on
  initial `load_dag()` so the pane populates immediately.
- Add `BrainstormApp._show_dag_node_detail(node_id)` — a near-clone of
  `_show_node_detail` that targets `#dag_node_title` / `#dag_node_info`
  instead of `#dash_node_title` / `#dash_node_info`. Refactor: extract
  the shared body into `_render_node_detail(node_id, title_id, info_id)`
  and call from both `_show_node_detail` and `_show_dag_node_detail` to
  avoid duplication.
- Track focused-graph-node id via the existing `_current_dashboard_node_id`
  attribute or a new sibling attribute; the on-screen contract is that
  `on_dimension_row_activated` knows which node the focused
  `DimensionRow` belongs to. Cleanest: rename the attribute to
  `_current_focused_node_id` (or introduce `_current_graph_node_id` and
  make the handler check both); pick the cleanest approach during
  implementation.
- Add CSS for `#dag_split`, `#dag_detail_pane`, sized like
  `#dashboard_split`.
- **Files:** `.aitask-scripts/brainstorm/brainstorm_app.py` only.
- Plan file: `aiplans/p748/p748_2_inline_detail_pane.md`.

### t748_3 — Context-aware operations: view proposal / view plan + footer pass

This child has two parts: the new view-proposal/view-plan keys, AND a
footer-visibility pass over **all** DAGDisplay bindings (pre-existing
+ new) so the Graph-tab footer reflects every available operation.

**New bindings:**

- `Binding("p", "view_proposal", "Proposal", show=True)` and
  `Binding("l", "view_plan", "Plan", show=True)` on `DAGDisplay`. Both
  keys are confirmed free on the Graph tab.
- `action_view_proposal` reads the focused node's proposal via
  `read_proposal(self._session_path, focused_id)` and pushes
  `SectionViewerScreen(proposal, title=f"Proposal: {focused_id}")`.
- `action_view_plan` analogously with `read_plan` and the `"Plan: …"`
  title; if `read_plan` returns `None`, `notify` "No plan generated"
  and skip.
- `Enter` on a focused node continues to open `NodeDetailModal`
  unchanged (full Metadata/Proposal/Plan modal — useful when the user
  wants the minimap navigation).
- DAGDisplay imports already pull `get_head, list_nodes, read_node`
  from `brainstorm.brainstorm_dag`; add `read_proposal, read_plan`
  there.

**Footer-visibility pass on existing bindings:**

The user has called out that the Graph tab's pre-existing operations
are not surfaced to the Textual footer today: `j`/`k` are
`show=False`, and `Enter`/`h` are not even declared as `Binding`s
(they're handled in `on_key`). Convert them so they all show:

- Replace `Binding("j", "next_node", show=False)` and
  `Binding("k", "prev_node", show=False)` with `show=True` and
  user-friendly labels (e.g. `"j Next"`, `"k Prev"`).
- Replace the `on_key` handling of `Enter` with
  `Binding("enter", "select_node", "Detail", show=True)` and an
  `action_select_node` that posts `NodeSelected`. Drop the matching
  branch from `on_key`.
- Replace the `on_key` handling of `h` with
  `Binding("h", "set_head", "Set HEAD", show=True)` and an
  `action_set_head` that posts `HeadChanged`. Drop the matching
  branch from `on_key`.
- After this pass, `DAGDisplay.on_key` should be empty or removed
  entirely (everything is now binding-driven and visible in the footer).
- **Files:** `.aitask-scripts/brainstorm/brainstorm_dag_display.py`
  only.
- Plan file: `aiplans/p748/p748_3_view_proposal_plan_keys_and_footer.md`.

### t748_4 — Compare-with (`x`) — interactive second-node selection

- Add `Binding("x", "compare_with", "Compare", show=True)` on
  `DAGDisplay` so `x` is visible in the Graph-tab footer.
- `action_compare_with` enters a "compare-pick" mode: store the focused
  node id as `self._compare_anchor_id`, set a flag
  `self._compare_pick_mode = True`, re-render with the anchor in a
  third style (e.g., yellow border) distinct from HEAD-green and
  focused-bg-purple. Notify: "Select node to compare with `<anchor>` —
  Enter=confirm, Esc=cancel".
- While in compare-pick mode:
  - All existing nav keys (arrows, `j`/`k`) still move focus.
  - `Enter` posts a new `DAGDisplay.CompareRequested(anchor_id, picked_id)`
    message and exits compare-pick mode (only if `picked_id != anchor_id`;
    otherwise notify and stay in mode).
  - `Escape` exits compare-pick mode (clear anchor, re-render, notify
    "Compare cancelled").
- App-level handler `on_dag_display_compare_requested(event)` calls
  `self._build_compare_matrix([event.anchor_id, event.picked_id])`,
  then switches `TabbedContent.active = "tab_compare"`. Reuses the
  existing Compare tab pipeline end-to-end.
- Render style: extend `_render_node_box` to accept an `is_anchor`
  flag; add `ANCHOR_BORDER_STYLE` (yellow + bold) so the anchor is
  visually distinct from HEAD and focus.
- **Files:** `.aitask-scripts/brainstorm/brainstorm_dag_display.py`,
  `.aitask-scripts/brainstorm/brainstorm_app.py`.
- Plan file: `aiplans/p748/p748_4_compare_with_picker.md`.

### t748_5 — Manual verification (aggregate sibling)

Created automatically by the planning workflow's "manual verification
sibling" step (since 4 children are being created and this is a TUI flow).
The seeded checklist will cover:

- `[t748_1]` arrow-key 2D nav across multiple layers, edge clamping,
  no-conflict with `j` from TuiSwitcherMixin.
- `[t748_2]` detail pane updates immediately on every focus change,
  matches Dashboard content, dimension rows still drill into the
  filtered SectionViewerScreen.
- `[t748_3]` `p` / `l` open the right SectionViewerScreen; `l` notifies
  cleanly when no plan exists. **Footer shows every Graph-tab operation
  with show=True** (`j`/`k`/`Enter`/`h`/`p`/`l`/`x` and arrow nav)
  while the Graph tab is focused.
- `[t748_4]` `x` enters pick mode with visible anchor, `Enter` jumps to
  Compare tab with the right two nodes, `Esc` cancels cleanly,
  picking-the-anchor-itself is rejected.
- Plan file: not applicable (manual-verification tasks have a checklist
  rather than an implementation plan).

## Step 9 (parent archival)

Once all five children are archived, the parent will be auto-archived by
`aitask_archive.sh` (it detects empty `children_to_implement`).

## Verification (parent-level)

Each child has its own verification section in its own plan file. The
parent-level verification is the t748_5 manual-verification sibling
(end-to-end TUI walkthrough across all four implementation children).
