---
Task: t983_7_compare_overlay_drop_tab.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_10_manual_verification_brainstorm_ia.md, aitasks/t983/t983_11_wizard_rehost_actions_screen.md, aitasks/t983/t983_8_session_tab_split.md, aitasks/t983/t983_9_running_strip_deconflict_docs.md
Archived Sibling Plans: aiplans/archived/p983/p983_1_node_detail_panel_widget.md, aiplans/archived/p983/p983_2_node_selection_model.md, aiplans/archived/p983/p983_3_browse_tab_contentswitcher.md, aiplans/archived/p983/p983_4_operations_dialog_cardinality.md, aiplans/archived/p983/p983_5_node_hub_overlay.md, aiplans/archived/p983/p983_6_wizard_rehost_drop_node_select.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-16 18:00
---

# p983_7 — Compare overlay; delete Compare tab

Child of t983 (brainstorm-TUI IA redesign). **Do not conflate the two compare
surfaces:** the dimension-matrix *tab* (`_build_compare_matrix` → `#compare_content`,
fed by `CompareNodeSelectModal`) — re-homed here — vs the comparator design *op*
(comparator agent; seeding handled in t983_4/_6, routes through the wizard). This
child re-homes the **matrix** surface only and leaves the comparator-agent op
untouched.

## Context

The parent IA collapses 5 tabs → 3 (Browse · Session · Running) and makes every
node operation contextual to the Browse selection. The dimension-matrix Compare
is currently a heavyweight **tab** that is blank until you pick nodes — exactly
the "transient analysis masquerading as a destination" smell the parent calls
out. This child re-hosts the matrix as a **modal overlay** opened from the
space-marked selection and the Node Hub, then deletes the Compare tab and its
node-select modal.

### Verification findings (plan re-checked against current 8419-line source)

The original task/plan line refs are **all stale** (siblings t983_3/_4/_5/_6
landed after they were written). Corrected refs and **three findings the stale
plan missed**, all in `.aitask-scripts/brainstorm/brainstorm_app.py` unless noted:

- `_build_compare_matrix` :6532 (+ `_add_similarity_row` :6607); `#compare_content`
  `TabPane("(C)ompare", id="tab_compare")` :4009; `CompareNodeSelectModal` :2140;
  `action_compare_diff` :4833; `self._compare_nodes` set :6604 / read :4836;
  `CompareDataTable` :3065.
- **FINDING 1 — a third matrix entry point the stale plan never mentioned.** The
  graph view has its own 2-node compare picker: `x` arms an anchor
  (`DAGDisplay.action_compare_with`, `brainstorm_dag_display.py:816`), `Enter`
  picks the second node and posts `DAGDisplay.CompareRequested(anchor, picked)`
  (`:766`), handled by `on_dag_display_compare_requested` (:6467) which switches
  to `tab_compare` and builds the matrix. Deleting the tab without re-homing this
  handler **breaks graph-view compare**. It must be re-pointed at the overlay,
  not dropped.
- **FINDING 2 — `_next_checkbox_index` is shared; do NOT delete it with the
  modal.** `CompareNodeSelectModal` uses it (:2210) but so does a second modal
  (:2290). Its only test is `tests/test_brainstorm_compare_modal.py`
  (`NextCheckboxIndexTests`). So the helper and its tests must survive the
  modal's deletion.
- **FINDING 3 — four matrix feeders, not one.** The matrix is reachable via `c`
  (`action_tab_compare` :4819), `r` (`action_compare_regenerate` :4828), the
  graph `x`/Enter flow (Finding 1), and `D` (`action_compare_diff` :4833, the
  proposal diff of the compared pair). `_TAB_SCOPED_ACTIONS` (:3819) scopes
  `compare_regenerate`/`compare_diff` to `tab_compare`; `on_key` (:4047) has a
  down-from-tab-bar branch focusing `#compare_table`. All five sites need
  reconciling, not just the `tab_compare` binding the task names.

The Node Hub launch contract from t983_5 is in place and ready to extend:
`NODE_HUB_OPERATIONS` + `NodeHubResult` (:1237) and `_on_node_hub_result` (:4364)
— "add a launch surface = add a verb + a branch" (its own docstring names
t983_7 as the next extender).

## Goal

Re-host the dimension matrix as a `CompareMatrixModal` overlay opened from (a) the
space-marked set in Browse, (b) the Node Hub, and (c) the graph `x`/Enter picker;
delete the Compare tab + `CompareNodeSelectModal`; re-home `D`/diff into the
overlay. Keep the matrix-build logic unit-testable.

## Design decisions (with trade-offs)

1. **`CompareMatrixModal(ModalScreen)` hosts the matrix.** `__init__(session_path,
   node_ids)`; `compose` renders a dialog container; `on_mount` builds the table
   into it. It owns its node set, so the app-level `self._compare_nodes` state is
   **dropped** (the overlay is the single source). *Rejected — a pushed full
   `Screen`:* the matrix is a transient read-only analysis; the modal idiom (like
   `NodeDetailModal`/`OperationHelpModal`) fits and auto-restores focus on dismiss.

2. **Plain `DataTable` in the overlay — delete `CompareDataTable` (resolves review
   concern 3).** `CompareDataTable` (:3065) exists solely to escape to the **tab
   bar** when Up is pressed at row 0 (`action_cursor_up` :3073 →
   `app.query_one(TabbedContent)…focus()`). Inside a modal that focuses a widget
   on the *base screen behind the overlay* — exactly the broken navigation the
   review flags. Since the tab is being deleted, that affordance is obsolete:
   delete `CompareDataTable` and have the builder return a plain
   `DataTable(id="compare_table", cursor_type="row")`. Standard cursor behavior
   (Up at row 0 stays put), `Escape` closes the modal. *Rejected — keep the class
   but make the escape conditional:* adds a mode flag for a behavior with no
   remaining caller; deletion is cleaner.

3. **Split the matrix build into a pure helper for testability** (mirrors t983_2
   `NodeSelection` / t983_4 `op_states_for_selection`). Extract a module-level
   `build_compare_table(node_dims: dict[str, dict], node_ids: list[str]) ->
   DataTable` holding the current row/color/similarity logic (no I/O — takes
   already-extracted dims). The modal's `on_mount` does the I/O (`read_node` +
   `extract_dimensions` per node, the loop now at :6539) then calls the pure
   builder. `_add_similarity_row` folds into the pure builder. *Trade-off:* one
   new module-level function; pays for itself as the unit-test seam the task's
   "keep its matrix-build logic unit-testable" asks for.

4. **`D`/diff lives inside the overlay, stacked over it (resolves review concern
   2).** The task leaves the home open ("Compare overlay or Node Hub"); the overlay
   *is* the compared-set context, so `D` is unambiguous there (the Hub is
   single-node, no natural pair). Add `Binding("D", "diff", "Diff")` to
   `CompareMatrixModal`; `action_diff` diffs `self.node_ids[:2]` via
   **`self.app.push_screen(DiffViewerScreen(...))`** — i.e. push the diff screen
   *over* the still-mounted compare modal and return to the matrix when the diff
   pops. **This is an established pattern in this file, not a new mechanism:**
   `NodeDetailModal.action_view_fullscreen` already does
   `self.app.push_screen(SectionViewerScreen(...))` from inside a ModalScreen
   (:1196), and `NodeActionSelectModal` pushes `OperationHelpModal` over itself
   (:2785). The old app-level `action_compare_diff` had an `if
   isinstance(self.screen, ModalScreen): return` guard *because* it was app-level;
   moving `D` into the modal removes that conflict entirely (the modal owns the
   binding). The body (proposal-path resolution + `DiffViewerScreen` push) is
   otherwise verbatim from :4843-4856. Dropping `self._compare_nodes` is safe — its
   only reader was that app-level `D`.

5. **Three triggers replace the deleted tab/modal; the overlay always takes an
   explicit node-id list, each entry point resolves it from its own context
   (resolves review concern 1).** A single helper
   `_open_compare_matrix(node_ids: list[str])` applies the 2–4 guard (notify on
   `<2` / `>4`) and pushes the modal. The triggers differ only in how they resolve
   the list — and the rule is stated so the Hub's focal node is **never silently
   ignored**:
   - **(a) Browse key** — repurpose `c` (freed by the tab deletion):
     `action_compare_matrix` resolves `sorted(self._selection.marked)` — in Browse
     the *marked set is the selection* (the cursor moves freely and is not
     auto-included). Guarded `tab_browse` + not-modal like its siblings.
   - **(b) Node Hub** — add `NODE_HUB_COMPARE = "compare"` verb; `NodeHub` gets a
     "Compare" button (`#btn_node_hub_compare`) + `Binding("c", "compare", ...)`,
     both dismissing `NodeHubResult(NODE_HUB_COMPARE, self.node_id)`.
     `_on_node_hub_result` resolves **`sorted(set(self._selection.marked) |
     {result.node_id})`** — the marked set **unioned with the hub's focal node**, so
     the node you are viewing always participates (union dedups if it was already
     marked). With nothing else marked this is 1 node → the guard notifies
     "Mark 1–3 more nodes to compare with `<node_id>`"; this makes the Hub's
     contract unambiguous: *"compare this node with its marked peers."*
   - **(c) Graph picker** — re-point `on_dag_display_compare_requested` (:6467) to
     `push_screen(CompareMatrixModal(self.session_path, [anchor, picked]))`
     (always exactly 2) instead of switching tabs + building into
     `#compare_content`. The DAG-side compare-pick mode (`x`/Enter/Esc in
     `brainstorm_dag_display.py`) is **unchanged** — only the app-side handler
     changes; the `await remove_children()` re-mount guard (:6488) is no longer
     needed (a fresh modal each time).
   *Rejected — route the matrix through the `A` Operations dialog `compare` op:*
   that op is the comparator **agent** (t983_4), a deliberately separate tool;
   folding the matrix there would re-conflate the two surfaces the task says to
   keep distinct.

6. **Key coordination with t983_9 (pending — running-strip/keybinding deconflict).**
   The parent's final tab keys are `b/s/r`; this task frees `c` (tab_compare) and
   removes `r` (compare_regenerate, whose letter t983_9 reclaims for "Running").
   I assign `c` → compare-matrix overlay now as the provisional Browse trigger and
   add an explicit coordination note + a bidirectional pointer in t983_9 (per the
   bidirectional-coordination convention) so the final keymap stays consistent.

## Implementation steps (all in `.aitask-scripts/brainstorm/brainstorm_app.py` unless noted)

1. **Pure builder.** Add module-level `build_compare_table(node_dims, node_ids)`
   near the other headless models (~`:1794`, by `_next_checkbox_index`), moving the
   row/color/`word_diff_texts`/similarity logic out of `_build_compare_matrix`
   (:6532) and `_add_similarity_row` (:6607). Returns a populated plain
   `DataTable(id="compare_table", cursor_type="row")`. No Textual `query`, no I/O.

2. **`CompareMatrixModal(ModalScreen)`** (define after `NodeHub`, ~`:1273`):
   `__init__(self, session_path, node_ids)`; `compose` yields a dialog container
   (id `compare_matrix_dialog`) with a title + a `VerticalScroll`; `on_mount`
   reads dims per node and mounts `build_compare_table(...)`, focusing it after
   refresh. `BINDINGS`: `escape`→`cancel` (dismiss None), `D`→`diff`. `action_diff`
   resolves the two proposal paths and calls **`self.app.push_screen(
   DiffViewerScreen(...))`** (stack over the modal, per design §4; body verbatim
   from old `action_compare_diff` :4843-4856). Add CSS for `#compare_matrix_dialog`
   mirroring `#node_detail_dialog` (incl. the `margin-bottom: 1` footer-clearance
   fix t983_5 added).

3. **Node Hub compare verb.** Add `NODE_HUB_COMPARE = "compare"` (:1237 block);
   in `NodeHub` add the `c` binding, the "Compare" button in `_dialog_buttons`,
   `action_compare`, and a `#btn_node_hub_compare` `Button.Pressed` handler — each
   dismissing `NodeHubResult(NODE_HUB_COMPARE, self.node_id)`. In
   `_on_node_hub_result` (:4364) add the `NODE_HUB_COMPARE` branch → resolve
   `sorted(set(self._selection.marked) | {result.node_id})` (marked ∪ focal node,
   design §5b) and call `_open_compare_matrix(...)`.

4. **Browse trigger + shared open helper.** Add
   `_open_compare_matrix(node_ids: list[str])` that applies the 2–4 guard (distinct
   notify for `<2` vs `>4`) and pushes `CompareMatrixModal`. Add
   `action_compare_matrix` (`tab_browse` + modal guard) resolving
   `sorted(self._selection.marked)` and calling the helper; the Hub branch (step 3)
   calls the same helper with its own resolved list.

5. **Delete the Compare tab + node-select modal + dead feeders.**
   - Remove `CompareNodeSelectModal` (:2140–2229) — **keep `_next_checkbox_index`
     (:1794)** and its `:2290` caller.
   - Remove `CompareDataTable` (:3065–3081) — obsolete with the tab (design §2).
   - Remove the `TabPane("(C)ompare"…)` block (:4009–4016).
   - Remove `_open_compare_select_modal` (:4809), `action_tab_compare` (:4819),
     `action_compare_regenerate` (:4828), `_on_compare_selected` (:6527),
     `action_compare_diff` (:4833), `_build_compare_matrix`/`_add_similarity_row`
     (folded into the modal+pure builder), and `self._compare_nodes` (:6604).
   - Bindings (:3799–3804): repoint `c`→`compare_matrix`; remove `r`
     (`compare_regenerate`) and the app-level `D` (`compare_diff`). Remove the
     `compare_regenerate`/`compare_diff` entries from `_TAB_SCOPED_ACTIONS`
     (:3820–3821). Remove the `tab_compare` down-from-tab-bar branch in `on_key`
     (:4047–4056).
   - Re-point `on_dag_display_compare_requested` (:6467) per design §5c.

6. **Test-file follow-up (Finding 2).** Rename `tests/test_brainstorm_compare_modal.py`
   → `tests/test_brainstorm_compare_overlay.py`, **keeping `NextCheckboxIndexTests`**
   (the helper survives), and add: `BuildCompareTableTests` (pure: synthetic
   `node_dims` → expected rows / same-marker / similarity row); a bare-host pilot
   pushing `CompareMatrixModal` asserting `#compare_table` renders; a **diff-stack
   pilot** (drive `D` → assert `isinstance(app.screen, DiffViewerScreen)`, then pop
   → assert `isinstance(app.screen, CompareMatrixModal)` — guards concern 2's
   stack-and-return); and a **Hub-union test** (`BrainstormApp.__new__` + a
   `_FakeSelection` with marks → `_on_node_hub_result(NodeHubResult(
   NODE_HUB_COMPARE, hub_id))` resolves marked ∪ {hub_id} and calls the guard —
   guards concern 1). Update the stale `"tab_compare"` string in
   `tests/test_brainstorm_node_export.py:37` to a still-existing tab id.

7. **Docs / coordination.** Add the bidirectional t983_9 keymap note (design §5).
   No website TUI-list change (Compare was never a listed TUI).

## Verification
- **Unit:** `python -m unittest tests.test_brainstorm_compare_overlay` — pure
  `build_compare_table` cases (2-node same/diff, ≥3-node similarity, empty-dims
  guard) + retained `NextCheckboxIndexTests`.
- **Suite:** `bash tests/run_all_python_tests.sh` (`tests/test_brainstorm*.py`)
  green — confirms the tab deletion broke no Browse/graph/wizard tests; pytest is
  absent in the venv, use unittest.
- **Lint:** `shellcheck` n/a (Python only).
- **Manual:** `ait brainstorm <session>` → Browse: `space`-mark 2–4 nodes → `c`
  → matrix overlay renders; `D` inside it opens the proposal diff, **Esc returns to
  the matrix** (not the base screen), Esc again closes. `<2` marked + `c` → notify.
  `Enter` on node X → Node Hub → "Compare" (button or `c`): with peers marked,
  overlay shows **X plus the marked peers**; with nothing marked, notify "Mark 1–3
  more nodes to compare with X". Graph view: `x` then Enter on a second node →
  overlay (no Compare tab flash). In the overlay, **Up at row 0 stays put** (no
  focus jump behind the modal). Confirm **no Compare tab** remains in the tab bar.

## Risk

### Code-health risk: medium
- Wide-ish blast radius: deletes a tab + 2 helper classes and re-points ~6 call
  sites (3 entry points, 2 bindings, 1 graph handler) in an 8.4k-line file. ·
  severity: medium · → mitigation: in-plan — every site enumerated by current line
  number in step 5; full `tests/test_brainstorm*.py` suite is the regression gate.
- Easy-to-miss shared helper: `_next_checkbox_index` is used by a second modal, so
  a naive "delete the modal and its test" would break an unrelated path. · severity:
  medium · → mitigation: in-plan — Finding 2 retains the helper + its tests
  (step 5/6).
- Reusing the tab's `CompareDataTable` (focuses the tab bar at row 0) or pushing
  the diff naively from inside the modal could break overlay navigation /
  screen-stacking (review concerns 2 + 3). · severity: medium · → mitigation:
  in-plan — overlay uses a plain `DataTable` (CompareDataTable deleted, design §2)
  and `D` stacks via the precedented `self.app.push_screen` pattern (design §4),
  both pilot-tested (step 6).
- The graph-view re-point (Finding 1) changes an `async` handler that currently
  manages a remove/re-mount race; the modal makes that race moot but the edit must
  not regress the graph picker. · severity: low · → mitigation: in-plan — pilot +
  manual graph-path check.

### Goal-achievement risk: low
- Approach is parent-mandated (overlay from marked set + Node Hub) and every
  prerequisite (`self._selection`, the Node Hub verb contract, the near-pure matrix
  builder) is verified present. The Node-Hub-vs-marked-set contract (review concern
  1) is now explicit: the overlay takes a resolved id-list, the Hub unions its focal
  node with the marks. · severity: low · → mitigation: in-plan — Hub-union test
  (step 6).
- The one open lever — the Browse trigger key — is a provisional `c` explicitly
  coordinated with t983_9 (design §6). · severity: low · → mitigation: in-plan —
  bidirectional t983_9 note.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_7`.
