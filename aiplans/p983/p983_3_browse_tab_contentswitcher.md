---
Task: t983_3_browse_tab_contentswitcher.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_3_browse_tab_contentswitcher
Branch: aitask/t983_3_browse_tab_contentswitcher
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-15 14:43
---

# p983_3 — Browse tab (Dashboard + Graph → one tab)

Child of t983 — **highest structural seam**, de-risked by landing on the
already-tested `NodeDetailPanel` (t983_1) + `NodeSelection` (t983_2) + a pure
view-state helper.

## Context

The target IA (parent t983) collapses the two DAG *views* — Dashboard list
(`tab_dashboard`, key `d`) and Graph (`tab_dag`, key `g`) — into one **Browse**
tab with a graph⇄list toggle (`v`, **graph default**, per-session persist), ONE
shared `NodeDetailPanel`, and `space`-marking wired to `NodeSelection`. Today
these are two `TabPane`s under a `TabbedContent`, each with its own list/graph
widget AND its own detail panel; node-detail rendering and cursor handling are
duplicated and tab-scoped. This child unifies them onto the foundations the two
prior siblings landed.

This is the riskiest seam in t983 because the *nav / pane-focus / action-gating
key handlers currently branch on which **tab** is active* — after the collapse
they must branch on which **view** (list vs graph) the single Browse tab is
showing.

## Verify-pass findings (plan re-checked against current code, 2026-06-15)

t983_1 and t983_2 have landed since this plan was first written; **all line
references below are refreshed against the current `brainstorm_app.py` (8012
lines).** The approach is unchanged and confirmed sound. Key facts:

- **Foundations present.** `NodeDetailPanel` (`:2358-2397`) has the public
  `update(node_id)` and `show_content(title_text, widgets)` API; it is currently
  instantiated twice — `#dash_node_panel` (inner ids `dash_node_title` /
  `dash_node_info`, `:3745`) and `#dag_node_panel` (`dag_node_title` /
  `dag_node_info`, `:3757`). `NodeSelection` (`:1883-1951`) exists with
  `set_primary`/`mark`/`unmark`/`toggle`/`clear`/`remove`/`cardinality`/
  `effective` — **defined but never instantiated** (purely additive, as t983_2
  intended).
- **Tabs.** `compose()` yields a `TabbedContent#brainstorm_tabs` (`:3736`) with
  five `TabPane`s. Dashboard `:3737-3752`: `Horizontal#dashboard_split` →
  `VerticalScroll#node_list_pane` (left) + `VerticalScroll#detail_pane` (right,
  holds the four status `Label`s `#session_status_info`/`#module_status_info` +
  `#dash_node_panel`). Graph `:3753-3764`: `Horizontal#dag_split` →
  `DAGDisplay#dag_content` (left) + `VerticalScroll#dag_detail_pane` (right,
  holds `#dag_node_panel`).
- **`ContentSwitcher` is NOT imported** (`textual.containers` import at `:22`
  has only `Container, Horizontal, VerticalScroll`) — must be added.
- **`v` is free** in the main app (only bound inside `NodeDetailModal:1053`);
  **`space` is unbound anywhere** — both available.
- **The graph inline panel is LIVE, not vestigial.** `_show_dag_node_detail`
  (`:5978`) is called from `on_dag_display_focus_changed` (`:6124`) on every DAG
  focus change. (Separately, `DAGDisplay.NodeSelected` → `on_dag_display_node_selected`
  `:6045` opens the full `NodeDetailModal` on Enter — that modal path is
  unchanged by this task.)
- **Persistence pattern confirmed.** `_write_module_deferred` /
  `_module_deferred_map` (`brainstorm_session.py:1142-1167`) read/write
  `br_graph_state.yaml` (`GRAPH_STATE_FILE`) under the session worktree — the
  template to mirror for persisting the Browse view.
- **Full panel-consolidation blast radius** (the two panels → one):
  - CSS rules `#dash_node_title`/`#dash_node_info`/`#dag_node_title`/
    `#dag_node_info` (`:3192-3200`, `:3211-3224`), `#detail_pane` (60%, `:3145`),
    `#dag_detail_pane` (40%, `:3203`), `#dashboard_split`/`#dag_split`.
  - `_navigate_rows(direction, "dash_node_info"|"dag_node_info", (DimensionRow,))`
    (`:3842`, `:3861`) — dimension-row nav inside the detail pane.
  - `_dashboard_toggle_pane_focus` (`:4524`, queries `#dash_node_info` `:4556`) and
    `_graph_toggle_pane_focus` (`:4570`, queries `#dag_node_info` `:4589`) — the
    `tab`/`shift+tab` list↔detail / dag↔detail focus toggles (`:3871`, `:3881`).
  - `_show_brief_in_detail` (`:5983`, drives `#dash_node_panel.show_content`
    `:5992`) — the `b` Task-Brief toggle (key handler `:4000-4008`).
  - `_show_node_detail` (`:5973`) + `_show_dag_node_detail` (`:5978`).
- **Tab-id branch sites to repoint to `tab_browse`** (every `== "tab_dashboard"`
  / `== "tab_dag"` / `in ("tab_dashboard","tab_dag")`): helper
  `_open_node_detail_visible` (`:1227`); `BINDINGS` `d`/`g` (`:3560-3561`);
  `check_action` gate (`:3679`); on_key nav/route branches (`:3815`, `:3826`,
  `:3839`, `:3857`, `:3870`, `:3880`); `action_tab_dashboard`/`action_tab_graph`
  (`:4134-4142`); action gates `action_node_action` (`:4186`),
  `action_toggle_deferred` (`:4233`); `_TAB_SCOPED_ACTIONS["open_node_detail"]`
  (`:3584`, currently `tab_dashboard`).
- **Tests:** `tests/test_brainstorm_browse_view.py` does **not** exist (new).
  `tests/test_brainstorm_node_export.py` asserts `_open_node_detail_visible`
  against `"tab_dashboard"` (`:31`, `:34`) — must update to `tab_browse`. Test
  family is `tests/test_brainstorm*.py` (36 files); run via
  `tests/run_all_python_tests.sh` (pytest if present, else `unittest discover`).
  Harness to mirror: pure-headless `unittest` (`test_brainstorm_node_selection.py`,
  `test_brainstorm_wizard_steps.py`) for the view-state helper; pilot/`_HostApp` +
  `pilot.pause()` + `_text()` (`test_brainstorm_node_detail_panel.py`) for the
  compose/toggle pilot.

## Design decisions (with trade-offs)

1. **`ContentSwitcher`, not nested `TabbedContent`.** Browse hosts one
   `ContentSwitcher#browse_switcher` whose children are the *existing*
   `VerticalScroll#node_list_pane` and `DAGDisplay#dag_content`; `v` flips
   `switcher.current` between `"node_list_pane"` (list) and `"dag_content"`
   (graph). Nested tabs would re-introduce the "switch a tab to change shape"
   smell t983 removes. The shared `NodeDetailPanel` is a **persistent sibling**
   of the switcher (not inside it) so it survives toggles.

2. **One shared detail panel `#browse_node_panel`** with new neutral inner ids
   `browse_node_title` / `browse_node_info`. The two old panels + their four
   inner ids collapse to this one; CSS, `_navigate_rows`, the pane-focus toggle,
   and the Task-Brief path all repoint to the single panel. `_show_node_detail`
   + `_show_dag_node_detail` merge into one `_show_browse_node_detail(node_id)`;
   both `on_descendant_focus` (NodeRow) and `on_dag_display_focus_changed` call
   it. *Rejected:* keeping both panels and hiding one — leaves dead duplicate
   widgets/ids and defeats the "ONE shared panel" goal.

3. **Pure, headless view-state helper** (mirrors the wizard-steps model
   t983_2 mirrored). Module-level in `brainstorm_app.py`:
   `BROWSE_DEFAULT_VIEW = "graph"`, `BROWSE_VIEWS = ("graph", "list")`, and
   `browse_toggle_view(current) -> str` (flip). Persistence is **separate I/O**
   in `brainstorm_session.py` mirroring the deferred-marker pair:
   `_read_browse_view(wt) -> str` (default `"graph"`) / `_write_browse_view(wt,
   view)` against a `browse_view` key in `br_graph_state.yaml`. The pure flip +
   default is unit-tested headless; the session round-trip is tested via a tmp
   worktree. The current view also **drives nav routing** (see §4 below), so this
   helper is load-bearing beyond the toggle.

4. **Nav / pane-focus routing branches on the current Browse view, not the tab.**
   The on_key handlers that today read `tabbed.active == "tab_dashboard"` vs
   `"tab_dag"` become: `if tab is tab_browse:` then branch on
   `switcher.current`. Concretely — up/down: list view → `_navigate_rows` over
   `#node_list_pane` (NodeRow) / `#browse_node_info` (DimensionRow); graph view →
   DAGDisplay's own handling / `#browse_node_info` dims. `_dashboard_toggle_pane_focus`
   + `_graph_toggle_pane_focus` merge into one `_browse_toggle_pane_focus` that
   branches on view (list: `#node_list_pane`↔`#browse_node_info`; graph:
   `DAGDisplay`↔`#browse_node_info`).

5. **`NodeSelection` runs alongside the legacy cursor (user-confirmed).** Add
   `self._selection = NodeSelection()` in `__init__`. `_show_browse_node_detail`
   sets BOTH `self._current_focused_node_id = node_id` (unchanged legacy path,
   keeps the 13 sites working) AND `self._selection.set_primary(node_id)`. `space`
   → `self._selection.toggle(primary)` + re-render list marks. The node-deletion
   purge (`:4416-4417`) also calls `self._selection.remove(node_id)` so the model
   stays coherent. *Rejected (for now):* migrating all 13 `_current_focused_node_id`
   sites to `selection.primary` — cleaner/single-source (t983_2's stated intent)
   but widens this already-large diff; the dual-cursor-state is a **documented
   debt** to collapse in a later child (e.g. t983_9). Recorded in the §Risk
   section and in Final Implementation Notes for the sibling chain.

6. **Marks: list view now, graph best-effort (user-confirmed).** `NodeSelection`
   marks are fully correct + exhaustively unit-tested (already are, from t983_2).
   `NodeRow` gains a `marked` reactive/visual indicator so list view reflects the
   marked set. The DAG-node marked glyph is **best-effort**: if `DAGDisplay` can
   render a mark cheaply, do it; otherwise defer to a follow-up and note it. The
   model + list reflection are the hard bar; graph visual parity is not.

7. **Status labels stay in the Browse detail column for now.** `#session_status_info`
   / `#module_status_info` move into the Browse right-hand `VerticalScroll`
   (above `#browse_node_panel`), exactly as today in `#detail_pane`. A dedicated
   header strip is explicitly t983_9, not here.

8. **Keys `d` / `g` stay meaningful.** Both select Browse; additionally `d` sets
   list view and `g` sets graph view (preserving muscle memory), while `v`
   toggles. `action_tab_dashboard`/`action_tab_graph` repoint to activate
   `tab_browse` and set the switcher accordingly.

## Implementation steps (all in `.aitask-scripts/brainstorm/brainstorm_app.py` unless noted)

1. **Imports.** Add `ContentSwitcher` to the `textual.containers` import (`:22`).

2. **Pure view-state helper.** Add module-level `BROWSE_DEFAULT_VIEW`,
   `BROWSE_VIEWS`, `browse_toggle_view(current)` near the wizard-step helpers
   (~`:1869`, beside `NodeSelection`). In `brainstorm_session.py` add
   `_read_browse_view(wt)` / `_write_browse_view(wt, view)` mirroring
   `_module_deferred_map` / `_write_module_deferred` (`:1142-1167`), keyed
   `browse_view` in `br_graph_state.yaml`; export as needed.

3. **`NodeRow` marked indicator.** Add a `marked` reactive (or style toggle) to
   `NodeRow` (`:2145`) that renders a mark glyph/prefix when set; a helper to
   re-render all NodeRow marks from `self._selection.marked`.

4. **Compose `tab_browse`** — replace the `tab_dashboard` (`:3737-3752`) and
   `tab_dag` (`:3753-3764`) `TabPane`s with one:
   ```python
   with TabPane("(B)rowse", id="tab_browse"):
       with Horizontal(id="browse_split"):
           with ContentSwitcher(id="browse_switcher", initial="dag_content"):
               yield VerticalScroll(id="node_list_pane")
               yield DAGDisplay(id="dag_content")
           yield VerticalScroll(
               Label("Session Status", id="session_status_title"),
               Label("Loading...", id="session_status_info"),
               Label("Modules", id="module_status_title"),
               Label("", id="module_status_info"),
               NodeDetailPanel(self.session_path,
                   title_id="browse_node_title", info_id="browse_node_info",
                   id="browse_node_panel"),
               id="browse_detail_pane",
           )
   ```
   On mount, set `switcher.initial`/`current` from `_read_browse_view`.

5. **CSS.** Collapse `#dash_node_*`/`#dag_node_*` rules to `#browse_node_title`/
   `#browse_node_info`; rename `#dashboard_split`/`#dag_split` → `#browse_split`,
   `#detail_pane`/`#dag_detail_pane` → `#browse_detail_pane` (pick one width,
   e.g. 40%); add a `ContentSwitcher#browse_switcher { width: 1fr; }` rule.

6. **Detail handlers.** Merge `_show_node_detail` + `_show_dag_node_detail`
   (`:5973-5981`) into `_show_browse_node_detail(node_id)` updating
   `#browse_node_panel` and setting both `_current_focused_node_id` and
   `self._selection.set_primary(node_id)`. Repoint `on_descendant_focus`
   (`:6026`, NodeRow branch) and `on_dag_display_focus_changed` (`:6124`) to it.
   Repoint `_show_brief_in_detail` (`:5992`) to `#browse_node_panel`.

7. **`v` toggle + `space` mark bindings.** Add `Binding("v", "browse_toggle_view",
   "Toggle view")` and `Binding("space", "browse_mark", "Mark")`.
   `action_browse_toggle_view`: flip `switcher.current` via `browse_toggle_view`,
   persist via `_write_browse_view`. `action_browse_mark`:
   `self._selection.toggle(self._selection.primary)` (guard None) + re-render list
   marks. Gate both to `tab_browse` active / non-modal like the existing actions.

8. **Pane-focus toggle.** Merge `_dashboard_toggle_pane_focus` +
   `_graph_toggle_pane_focus` (`:4524-4601`) into `_browse_toggle_pane_focus`
   branching on `switcher.current`; repoint call sites (`:3871`, `:3881`).
   Repoint `_navigate_rows` detail-pane calls to `#browse_node_info` (`:3842`,
   `:3861`).

9. **Tab-id repoint.** Update every `tab_dashboard`/`tab_dag` branch listed in
   Verify-pass findings to `tab_browse` (+ switcher-view sub-branch where the old
   code distinguished list vs graph): `_open_node_detail_visible` (`:1227`),
   `check_action` (`:3679`), on_key (`:3815`,`:3826`,`:3839`,`:3857`,`:3870`,
   `:3880`), `action_tab_dashboard`/`action_tab_graph` (`:4134-4142`, per §8
   decision), `action_node_action` (`:4186`), `action_toggle_deferred` (`:4233`),
   `_TAB_SCOPED_ACTIONS["open_node_detail"]` → `tab_browse` (`:3584`). Update the
   `d`/`g` `BINDINGS` labels (`:3560-3561`) and the TabPane title key letter.

10. **Node-deletion purge.** At `:4416-4417` (and the `:4208` purge) also call
    `self._selection.remove(node_id)` for each deleted node.

## Verification

- **Pure unit** (`tests/test_brainstorm_browse_view.py`, NEW, headless
  `unittest`): `browse_toggle_view` flips graph↔list; `BROWSE_DEFAULT_VIEW ==
  "graph"`; `_read_browse_view` defaults to `"graph"` and round-trips through
  `_write_browse_view` across a fresh read (tmp worktree).
- **Pilot** (same file, `_HostApp`/`pilot.pause()` per the node_detail_panel
  harness): `v` flips `#browse_switcher.current`; the `#browse_node_panel`
  persists across toggles; `space` toggles membership in `self._selection.marked`
  and the focused NodeRow shows the marked indicator in list view.
- **Update + green in this child:** `tests/test_brainstorm_node_export.py`
  (`tab_dashboard` → `tab_browse` assertions at `:31`,`:34`); then the full
  `tests/test_brainstorm*.py` family via `bash tests/run_all_python_tests.sh`.
- **Manual:** `ait brainstorm <session>` → Browse tab; `v` toggles graph⇄list and
  the choice persists across reload; detail panel shared across toggles; `space`
  marks reflect in the list; `b` Task Brief still works; `d`/`g` select Browse +
  set view; Enter still opens the node-detail modal from the graph.

See **Step 9 (Post-Implementation)** of the task-workflow for cleanup, archival,
and merge. Archive via `./.aitask-scripts/aitask_archive.sh 983_3`.

## Risk

### Code-health risk: high
- **Wide blast radius on a central, load-bearing path.** The change touches tab
  compose, CSS, two→one panel consolidation, the on_key nav/route branches,
  pane-focus toggles, action gates, and ~30 `tab_dashboard`/`tab_dag` branch
  sites — a regression in key routing or focus handling is plausible. · severity:
  high · → mitigation: covered in-scope by the pure + pilot tests and the full
  `test_brainstorm*.py` suite (no separate task).
- **Dual cursor state (`_current_focused_node_id` + `self._selection.primary`)**
  kept in sync by hand creates a temporary implicit contract: a future edit that
  sets one but not the other drifts the selection. Documented debt, to collapse
  in a later child. · severity: medium · → mitigation: t1003
- **Best-effort graph marks** may leave list and graph views visually
  inconsistent on marked state until a follow-up. · severity: low · →
  mitigation: t1004

### Planned mitigations
- timing: after | name: t1003 (collapse_browse_cursor_state) | type: refactor | priority: medium | effort: medium | addresses: dual cursor state (code-health medium) | desc: migrate the 13 `_current_focused_node_id` sites onto `selection.primary` so there is one cursor source of truth; retire the dual-state debt
- timing: after | name: t1004 (dag_node_mark_rendering) | type: enhancement | priority: low | effort: medium | addresses: best-effort graph marks (code-health low) | desc: render marked state on DAGDisplay nodes so list and graph views show selection marks consistently

### Goal-achievement risk: low
- Approach is the parent-mandated one (ContentSwitcher + shared panel +
  NodeSelection), and every prerequisite (panel API, selection model, persistence
  template, free keys) is verified present. The pure view-state helper and the
  panel are independently testable, and the scope calls (cursor-alongside,
  list-marks-now) are user-confirmed. · severity: low · → mitigation: n/a
- None other identified.

## Final Implementation Notes

- **Actual work done:** Collapsed the `tab_dashboard` (list) and `tab_dag`
  (graph) `TabPane`s into one `tab_browse` hosting a `ContentSwitcher`
  (`#browse_switcher`) over the existing `#node_list_pane` and `#dag_content`,
  with ONE persistent shared `NodeDetailPanel` (`#browse_node_panel`, inner ids
  `browse_node_title`/`browse_node_info`) as a sibling of the switcher.
  - Added the pure, headless view-state helper to `brainstorm_app.py`
    (`BROWSE_DEFAULT_VIEW="graph"`, `BROWSE_VIEWS`, `BROWSE_VIEW_TO_PANE` /
    `BROWSE_PANE_TO_VIEW` maps, `browse_toggle_view(current)`), plus session I/O
    `_read_browse_view` / `_write_browse_view` in `brainstorm_session.py`
    (`browse_view` key in `br_graph_state.yaml`, mirrors
    `_module_deferred_map`/`_write_module_deferred`; both tolerate a missing
    graph-state file → graph default).
  - Wired `NodeSelection` in: `self._selection` in `__init__`,
    `_show_browse_node_detail` keeps the legacy `_current_focused_node_id` AND
    `_selection.set_primary` in sync, `space`→`action_browse_mark` toggles the
    primary's mark, and `NodeRow` gained a `marked` reactive glyph reflected by
    `_refresh_node_marks` and at list-build time in `_populate_node_list`. Both
    node-deletion purges call `_selection.remove`.
  - Merged `_show_node_detail`+`_show_dag_node_detail`→`_show_browse_node_detail`
    and `_dashboard_toggle_pane_focus`+`_graph_toggle_pane_focus`→
    `_browse_toggle_pane_focus` (branches on `switcher.current`). Repointed the
    on_key down/up/Tab routing, `check_action`, `_TAB_SCOPED_ACTIONS`,
    `_open_node_detail_visible`, `action_node_action`/`action_toggle_deferred`
    gates, and `action_tab_dashboard`/`action_tab_graph` (now select Browse +
    set list/graph view; `v`=`action_browse_toggle_view`). CSS collapsed the
    `#dash_node_*`/`#dag_node_*` + split/detail-pane rules to the `#browse_*`
    ids. `_load_existing_session` restores the persisted view.
- **Deviations from plan:** (1) `ContentSwitcher` imports from `textual.widgets`,
  not `textual.containers` (it is not in `textual.containers` in this Textual
  version). (2) The plan's verification only named `test_brainstorm_node_export.py`
  for updates, but the t983_1 `BrainstormAppComposeSmokeTests` in
  `test_brainstorm_node_detail_panel.py` (referenced `#dash_node_panel`/
  `#dag_node_panel`/`_show_node_detail`/`_show_dag_node_detail`), the graph-tab
  assertion in `test_brainstorm_node_action_integration.py`, and the
  `__new__`-bypass app in `test_brainstorm_node_delete.py` were all in the blast
  radius — updated. (3) The `d`/`g` action *names* (`tab_dashboard`/`tab_graph`)
  were kept (only their bodies + labels repointed) to avoid touching the
  `Binding` action strings, per §8.
- **Issues encountered:** The Textual `_SmokeApp` pattern (override `on_mount`
  to skip session load) does NOT prevent the base `BrainstormApp.on_mount` from
  running — Textual dispatches `on_mount` across the whole MRO, so
  `InitSessionModal` is still pushed. The t983_1 smoke test tolerated this (it
  queries base-screen widgets under the modal), but the new key-driven pilots
  must pop the modal first (`_dismiss_modals`) so `v`/`space` reach the base
  Browse screen. Also `read_yaml` raises `FileNotFoundError` on a missing file,
  so the new session helpers guard with `path.exists()` and the test fixture
  writes a minimal `br_graph_state.yaml`.
- **Key decisions:** `ContentSwitcher` over nested `TabbedContent` (no
  "switch-tab-to-change-shape" smell); ONE shared panel as a persistent switcher
  sibling (survives `v`); `NodeSelection` alongside the legacy cursor (dual
  state is documented debt → `collapse_browse_cursor_state`); marks reflected on
  list NodeRows now, DAG-node marks deferred (`dag_node_mark_rendering`);
  NodeRows stay mounted in the switcher even when the graph view shows, so a
  mark made in graph view is visible on switch.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - The single shared detail panel is `#browse_node_panel` (`NodeDetailPanel`,
    inner ids `browse_node_title`/`browse_node_info`); drive it via
    `panel.update(node_id)` or `panel.show_content(title, widgets)`.
    `_show_browse_node_detail(node_id)` is the one focus→detail entry point.
  - The Browse selection lives on `self._selection` (`NodeSelection`).
    **t983_4 (Operations dialog)** greys ops by `self._selection.cardinality`
    and runs them over `self._selection.effective()`; the `space` mark path and
    `remove`-on-delete are already wired.
  - **Documented debt for a later child:** the dual cursor state
    (`_current_focused_node_id` + `_selection.primary`, kept in sync by hand in
    `_show_browse_node_detail`) — risk-mitigation `collapse_browse_cursor_state`
    migrates the 13 legacy sites onto `_selection.primary`. DAG-node mark
    rendering is the `dag_node_mark_rendering` follow-up.
  - The current Browse view ("graph"|"list") is read via `_browse_current_view()`
    and set/persisted via `_set_browse_view(view)`; routing that used to branch
    on the active tab now branches on the switcher view.
  - Test harness for Browse pilots lives in `tests/test_brainstorm_browse_view.py`
    (`_BrowseSmokeApp`, `_dismiss_modals`, `_make_session` writing
    `br_graph_state.yaml`) — mirror it; remember to pop the auto-pushed modal.
