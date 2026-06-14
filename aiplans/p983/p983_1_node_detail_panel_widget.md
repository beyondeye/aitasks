---
Task: t983_1_node_detail_panel_widget.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_1_node_detail_panel_widget
Branch: aitask/t983_1_node_detail_panel_widget
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-14 12:15
---

# p983_1 — Extract `NodeDetailPanel` widget

Foundation child of the t983 brainstorm-TUI IA redesign. **Testability-first:**
land a reusable, independently-testable widget + its pilot test. Pure
extraction for the inline panes; a deliberate (minor) reconciliation for the
modal.

## Context

The target IA (parent t983) hosts ONE shared node-detail panel in a new Browse
tab (t983_3). Node detail is currently rendered in **3 places**:
1. Dashboard inline pane (`_show_node_detail`)
2. Graph inline pane (`_show_dag_node_detail`)
3. `NodeDetailModal` Metadata tab (`NodeDetailModal.on_mount`)

The two inline panes are *already* DRY via `_render_node_detail_widgets`
(`.aitask-scripts/brainstorm/brainstorm_app.py:5768`). The modal still keeps a
**separate text-metadata path** (`:1095-1117`) that builds plain `\n`-joined
lines into a single `Static(id="metadata_content")`. This child collapses all
three onto one renderer wrapped in a reusable `NodeDetailPanel`, so t983_3 can
host a single instance.

## Verify-pass findings (plan re-checked against current code)

- All line references in the original plan are **accurate**: renderer `:5768`
  (returns `tuple[str, list]`), `_show_node_detail:5858`,
  `_show_dag_node_detail:5868`, `NodeDetailModal:1047`, metadata text-path
  `:1095-1117`.
- `_render_node_detail_widgets` depends on `self` **only** via
  `self.session_path` — every other symbol (`read_node`, `_read_groups` [module
  fn at :210], `resolve_node_group`, `OP_BADGE_STYLES`, `UNKNOWN_OP_STYLE`,
  `get_dimension_fields`, `group_dimensions_by_prefix`, `read_proposal`,
  `parse_sections`, `dimension_matches_tag`, `DimensionRow`, `Static`) is
  module-level. → it extracts cleanly to a module-level function, making the
  widget testable without instantiating the full App.
- **Blast radius is wider than the original plan stated.** The four container
  IDs are referenced beyond the two detail handlers:
  - CSS rules `#dash_node_title/#dash_node_info/#dag_node_title/#dag_node_info`
    (`:2995-3027`).
  - Keyboard nav: `_navigate_rows(direction, "dash_node_info", ...)` /
    `"dag_node_info"` (`:3637`, `:3656`), and `_dashboard_toggle_pane_focus`
    (`:4351` queries `#dash_node_info`) / `_graph_toggle_pane_focus` (`:4384`
    queries `#dag_node_info`) to focus `DimensionRow`s.
  - **`_show_brief_in_detail` (`:5878`) reuses `#dash_node_title`/`#dash_node_info`**
    to show the "Task Brief" (the `b` toggle), i.e. the dashboard detail
    containers are *dual-purpose* (node detail AND task brief).
- The regression test `tests/test_brainstorm_node_detail_minimap.py` asserts
  only on the modal's **Proposal** tab (`#proposal_content`/`#proposal_minimap`/
  `#proposal_pane`) — it has **zero** references to `#metadata_content`, so the
  modal-metadata fold won't break it.

## Design decisions (with trade-offs)

1. **Preserve the existing container IDs inside the panel** (lowest blast
   radius). `NodeDetailPanel` composes a title `Label` + content `Container`
   whose IDs are passed in at construction. Dashboard uses
   `dash_node_title`/`dash_node_info`; Graph uses `dag_node_title`/`dag_node_info`.
   Because Textual `query_one("#id")` is DOM-global regardless of nesting, this
   keeps the CSS, `_navigate_rows`, both toggle-focus methods, and
   `_show_brief_in_detail` working **unchanged**. *Rejected alternative:* switch
   to class-based selectors and repoint all of CSS + nav + brief — more churn,
   more regression surface, no benefit for a foundation extraction.

2. **Extract the renderer to a module-level function**
   `render_node_detail_widgets(session_path, node_id) -> tuple[str, list]` and
   remove the App method (only 2 callers, both repointed). The panel and the
   modal both call the module function. This is what makes the widget unit- and
   pilot-testable in isolation (testability-first).

3. **Subclass `Container`, not bare `Widget`.** The task text says
   `NodeDetailPanel(Widget)`; `Container` *is* a `Widget` and is the established
   pattern for composite widgets in this file (`FuzzyCheckList(Container)`),
   already imported (`:22`) — no new import, sane layout defaults. (Method named
   `update(node_id)` per the plan; base `Container` has no `update`, so no
   clash.)

4. **Modal fold = a deliberate, minor reconciliation (not "no behavior
   change").** The inline panes are byte-for-byte behavior-preserving. The
   modal's Metadata tab changes from plain `\n`-joined text → the shared
   renderer's rich widgets (styled `meta_field` lines, group/operation badge,
   and interactive `DimensionRow`s). This is the intended DRY win ("3 → 1").
   Edge noted: a `DimensionRow` activated inside the modal bubbles
   `DimensionRow.Activated` to the App's `on_dimension_row_activated`, which uses
   `self._current_focused_node_id` — that equals the modal's node (the modal is
   opened from the focused node), so it stays coherent. The modal is slated to
   become the Node Hub ▸ Detail in t983_6; deeper rewiring belongs there, not
   here. This risk is covered by the new test (below), so no separate mitigation
   task is spawned.

## Implementation steps

All in `.aitask-scripts/brainstorm/brainstorm_app.py` unless noted.

1. **Module-level renderer.** Move the body of `_render_node_detail_widgets`
   (`:5768-5856`) to a module-level `render_node_detail_widgets(session_path,
   node_id)` (place it near the other module helpers / above the App class),
   replacing `self.session_path` → `session_path`. Delete the App method.

2. **`NodeDetailPanel(Container)`** (define near the other custom widgets, e.g.
   after `DimensionRow`):
   ```python
   class NodeDetailPanel(Container):
       """Reusable node-detail pane: a title Label + a content Container,
       driven by the shared render_node_detail_widgets renderer. Used by the
       Dashboard, Graph, and NodeDetailModal so all three share one rendering."""

       def __init__(self, session_path, *, title_id, info_id, **kwargs):
           super().__init__(**kwargs)
           self._session_path = session_path
           self._title_id = title_id
           self._info_id = info_id

       def compose(self) -> ComposeResult:
           yield Label("", id=self._title_id)
           yield Container(id=self._info_id)

       def update(self, node_id: str) -> None:
           title_text, widgets = render_node_detail_widgets(
               self._session_path, node_id)
           self.query_one(f"#{self._title_id}", Label).update(title_text)
           container = self.query_one(f"#{self._info_id}", Container)
           container.remove_children()
           for w in widgets:
               container.mount(w)
   ```
   (No `DEFAULT_CSS` needed — the existing `#dash_node_*`/`#dag_node_*` rules
   still target the inner children by ID.)

3. **Dashboard `compose` (`:3548-3549`).** Replace the interleaved
   `Label(id="dash_node_title")` + `Container(id="dash_node_info")` pair with
   `NodeDetailPanel(self.session_path, title_id="dash_node_title",
   info_id="dash_node_info", id="dash_node_panel")`. (Keep it as the last child
   of `detail_pane`, after the session/module status labels.)

4. **Graph `compose` (`:3556-3557`).** Replace the `dag_node_title`/`dag_node_info`
   pair with `NodeDetailPanel(self.session_path, title_id="dag_node_title",
   info_id="dag_node_info", id="dag_node_panel")` inside `dag_detail_pane`.

5. **Repoint the two detail handlers.**
   ```python
   def _show_node_detail(self, node_id):
       self._current_focused_node_id = node_id
       self.query_one("#dash_node_panel", NodeDetailPanel).update(node_id)

   def _show_dag_node_detail(self, node_id):
       self._current_focused_node_id = node_id
       self.query_one("#dag_node_panel", NodeDetailPanel).update(node_id)
   ```
   Leave `_show_brief_in_detail`, `_navigate_rows`, and both `*_toggle_pane_focus`
   untouched — they keep querying the preserved inner IDs.

6. **Modal fold.**
   - `NodeDetailModal.compose` (`:1071-1074`): replace
     `Static(id="metadata_content")` inside `VerticalScroll(id="metadata_scroll")`
     with `NodeDetailPanel(self.session_path, title_id="modal_node_title",
     info_id="modal_node_info", id="modal_node_panel")` (unique IDs — the
     dashboard is still mounted under the modal).
   - `NodeDetailModal.on_mount` (`:1095-1117`): delete the text-building block;
     replace with `self.query_one("#modal_node_panel",
     NodeDetailPanel).update(self.node_id)`. Keep the Proposal tab + minimap
     block unchanged.

7. **New test `tests/test_brainstorm_node_detail_panel.py`** (pure `.py`, run via
   `tests/run_all_python_tests.sh`; mirror the harness in
   `test_brainstorm_node_detail_minimap.py`):
   - `_make_session(td, node_id, ...)` writing `br_nodes/<id>.yaml` (description,
     parents, created_at, a couple dimension keys e.g. `requirements_perf: fast`)
     + `br_proposals/<id>.md`.
   - **Headless unit test** of `render_node_detail_widgets(session, node_id)`:
     assert title == `f"Node: {node_id}"`, assert `meta_field` Statics for
     Description/Parents/Created, and ≥1 `DimensionRow` for the dimensions.
   - **Pilot test** of `NodeDetailPanel`: a `_HostApp` mounting
     `NodeDetailPanel(session, title_id="t", info_id="i")`, call
     `panel.update(node_id)` after `pilot.pause()`, assert the title `Label`
     text and the content `Container`'s children (meta fields + `DimensionRow`s).

## Verification

- `python -m pytest tests/test_brainstorm_node_detail_panel.py -v` (or
  `bash tests/run_all_python_tests.sh`) — new test green.
- Regression green: `tests/test_brainstorm_node_detail_minimap.py`,
  `tests/test_brainstorm_node_export.py`.
- Manual: `ait brainstorm <session>` → Dashboard focus a node (detail renders
  as before), press `b` (Task Brief still shows), Tab/arrows navigate dimension
  rows; Graph tab focus a DAG node (detail renders); press Enter on a node →
  modal Metadata tab now shows the shared rich rendering, Proposal tab + minimap
  unchanged.

## Risk

### Code-health risk: medium
- Modal-metadata fold changes the modal's Metadata tab from plain text to the
  shared interactive renderer (`DimensionRow`s); `DimensionRow.Activated`
  bubbles to the App handler inside the modal. · severity: medium · → mitigation:
  covered in-scope by the new pilot/headless test + green minimap/export
  regression (no separate task).
- Inline-pane extraction is behavior-preserving (container IDs preserved →
  CSS/nav/`_show_brief_in_detail` untouched). · severity: low · → mitigation: n/a

### Goal-achievement risk: low
- None identified. Approach matches the parent decomposition (item 1), renderer
  proven to depend only on `session_path`, all three renderings + test covered.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_1`.
