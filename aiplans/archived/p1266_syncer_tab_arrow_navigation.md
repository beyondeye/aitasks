---
Task: t1266_syncer_tab_arrow_navigation.md
Base branch: main
plan_verified: []
---

# t1266 — Syncer tab-bar ⇄ content arrow navigation

## Context

`ait syncer` gained a tabbed shell (t1223_1) and a second content table
(t1223_3), but never the tab-bar ⇄ content keyboard navigation the other
tabbed framework TUIs already have. Today the only route from the tab bar
into a pane's content is `Tab` pressed twice (via `#detail_scroll`), `up` at
the first table row is silently swallowed by `DataTable`'s clamped cursor,
and `left`/`right` switch tabs **only** while the tab bar itself holds focus.

This task delivers the three-point navigation contract from the task file:
`down` on the bar enters the active pane's list at row 0; `up` on row 0
returns to the bar; `left`/`right` always switch tabs. Scope is **syncer
only** — settings and brainstorm already implement equivalent behaviour, and
promoting a shared `TabNavMixin` is explicitly out of scope.

## Mechanism decision — probed, not assumed

The task required probing the real `SyncerApp` under `run_test()` before
committing to a mechanism. Done (headless, textual 8.2.7, no files written).
Results:

| Probe | Result |
|---|---|
| App `priority=True` arrow binding fires **before** the focused `DataTable`'s own binding | ✅ |
| `raise SkipAction()` from the App action falls through to `DataTable.action_cursor_up` (row 2→1, focus retained) | ✅ |
| `up` at row 0 hands focus to `ContentTabs` | ✅ |
| `down` from the bar focuses the table at row 0 | ✅ |
| `left`/`right` **from the table** switch tabs and the switch sticks (bar focused first — t1060) | ✅ |
| Native `Tabs._move_tab` **wraps** (`_tabs.py:761`, modulo) — so wrap is inherited, not invented | ✅ |
| Settings placeholder: `down` from the bar is an explicit no-op, no exception | ✅ |
| `#detail_scroll`: `up`/`down` fall through, focus retained | ✅ |
| `#detail_scroll`: `left`/`right` **do** switch tabs (requirement 3 "from anywhere" holds for the one pane that would otherwise swallow them) | ✅ |
| Pre-mount exception taxonomy: `App.query_one(...)` raises `textual.app.ScreenStackError` (**not** `NoMatches`); `len(self.screen_stack)` is exception-free and returns `0` | ✅ |
| Modal gate (`check_action` → `False` while `len(screen_stack) > 1`): `Input` caret and `RadioSet` selection behave **identically to a baseline `SyncerApp` with no nav bindings**, and no tab switch occurs | ✅ |

**Chosen mechanism: App-level `priority=True` BINDINGS + `check_action`
modal gate** — the board pattern
(`board/aitask_board.py:5416-5420` + `:5495-5556`), which
`aidocs/framework/tui_conventions.md:73-102` names the *preferred* remedy
("blanket ... `len(self.screen_stack) > 1: return False`").

`on_key` (the settings/brainstorm mechanism) was **rejected**: the syncer's
panes are `DataTable`s with `cursor_type="row"`, whose `up`/`down`/`left`/
`right` bindings consume the key at App-bubble time, so an App-level `on_key`
never observes them. That is exactly the measurement the task demanded.

**Accepted trade-off:** `ShortcutsMixin.__init__` passes all of
`self.BINDINGS` through `register_app_bindings`, so the four nav actions
become rebindable rows in the syncer's `?` shortcut editor. This is identical
to what `KanbanApp` already does for its four `nav_*` arrows, so it is the
house behaviour, not a new precedent.

## Changes — `.aitask-scripts/syncer/syncer_app.py`

### 1. Module-level constants (beside `BRANCH_TAB_ACTIONS` / `VERSION_TAB_ACTIONS`, ~line 128)

```python
# Arrow-key navigation actions. Bound App-level with priority=True so they beat
# the focused DataTable's own cursor bindings; each action re-raises SkipAction
# when it is not the one that should handle the key, so ordinary cursor/scroll
# movement is untouched. Blanket-gated off in check_action while any screen is
# pushed (tui_conventions.md "Priority bindings + App.query_one gotcha").
NAV_ACTIONS = ("nav_up", "nav_down", "prev_tab", "next_tab")

# Active TabPane -> the id of the list that `down` from the tab bar enters.
# tab_settings is deliberately absent: its pane is a non-focusable Static
# placeholder until t1223_5, and `down` there is an explicit no-op. When t1223_5
# lands a focusable Settings pane, add its list id here.
TAB_LIST_IDS = {"tab_branches": "branches", "tab_versions": "versions"}
```

### 2. `BINDINGS` (append after `Binding("c", "recheck_version", ...)`, ~line 494)

```python
        # Tab bar <-> content navigation (t1266). priority=True is required:
        # a focused DataTable consumes all four arrows itself, so a non-priority
        # binding (or an on_key handler) would never see them.
        Binding("up", "nav_up", "Row up / leave list", show=False, priority=True),
        Binding("down", "nav_down", "Row down / enter list", show=False, priority=True),
        Binding("left", "prev_tab", "Previous tab", show=False, priority=True),
        Binding("right", "next_tab", "Next tab", show=False, priority=True),
```

### 3. Helpers (beside `_active_tab()`, ~line 638)

Both helpers catch **only** the pre-mount / not-composed exceptions, so a real
lifecycle or CSS-selector bug surfaces instead of silently degrading
navigation into a no-op. `App.query_one` resolves `self.screen` first, so
before mount it raises `ScreenStackError`, **not** `NoMatches` — a
`except NoMatches` alone would not cover the pre-mount case (probe-verified).

```python
    # Narrow on purpose: pre-mount App.query_one raises ScreenStackError (it
    # resolves self.screen first), a missing/retyped widget raises NoMatches /
    # WrongType. Anything else is a real bug and must surface — swallowing it
    # would turn every arrow key into a silent no-op.
    _QUERY_MISS = (ScreenStackError, NoMatches, WrongType)

    def _tab_bar(self):
        """The TabbedContent's Tabs bar, or None pre-mount / when not composed."""
        try:
            return self.query_one(TabbedContent).query_one(Tabs)
        except self._QUERY_MISS:
            return None

    def _active_list(self):
        """The active pane's DataTable, or None when the pane has no list."""
        list_id = TAB_LIST_IDS.get(self._active_tab())
        if list_id is None:
            return None
        try:
            return self.query_one(f"#{list_id}", DataTable)
        except self._QUERY_MISS:
            return None
```

Imports to add: `Tabs` to the `textual.widgets` block (~line 94),
`from textual.actions import SkipAction`,
`from textual.app import ScreenStackError`,
`from textual.css.query import NoMatches, WrongType`.

`_active_list()` can return `None` for **two different reasons**, and the
callers must not conflate them:

- **no list is mapped for this tab** (`tab_settings`) — a designed state; `down`
  is an explicit no-op that leaves focus on the bar;
- **mapped but the query missed** (pre-mount, or the widget is gone) — a
  degraded lookup; the key is handed back via `raise SkipAction()` rather than
  eaten.

Callers therefore test `self._active_tab() not in TAB_LIST_IDS` for the first
case *before* consulting the widget lookup for the second.

### 4. `check_action` — modal gate (first branch, before the tab gates)

```python
        # Arrow nav is main-screen-only. Returning False for a priority binding
        # makes Textual treat it as inactive, so the key falls through to the
        # focused modal widget (upgrade RadioSet/Input, the shortcut editor's
        # table, the TUI switcher's list). Blanket rather than per-class so a
        # future modal is covered without enumeration. No try/except: App.__init__
        # seeds the stack, so screen_stack is exception-free even pre-mount (it
        # returns []) — guarding it could only ever fail OPEN and let a priority
        # arrow hijack a modal widget.
        if action in NAV_ACTIONS:
            return len(self.screen_stack) <= 1
```

This is the one gate whose failure direction matters: a swallowed exception
here would return `True` and let an App-level priority arrow hijack a modal's
`Input` / `RadioSet`. The probe confirms `len(self.screen_stack)` cannot raise
(it is `0` before mount, `1` on the main screen, `≥2` with a modal pushed), so
the gate is written without any exception handling and any future breakage
surfaces loudly instead of failing open.

### 5. Actions (new section near the other `action_*` methods)

```python
    def action_nav_down(self) -> None:
        """`down`: from the tab bar, enter the active pane's list at row 0."""
        bar = self._tab_bar()
        if bar is None or self.focused is not bar:
            raise SkipAction()  # ordinary cursor/scroll movement
        if self._active_tab() not in TAB_LIST_IDS:
            return  # Settings placeholder: no list to enter — stay on the bar
        table = self._active_list()
        if table is None:
            raise SkipAction()  # mapped but not composed — hand the key back
        table.focus()
        if table.row_count:
            table.move_cursor(row=0)

    def action_nav_up(self) -> None:
        """`up`: on the list's first row, hand focus back to the tab bar."""
        table = self._active_list()
        if table is None or self.focused is not table or table.cursor_row > 0:
            raise SkipAction()  # mid-list, or not our widget
        bar = self._tab_bar()
        if bar is None:
            raise SkipAction()
        bar.focus()

    def _switch_tab(self, direction: int) -> None:
        """Move one tab, from anywhere. Delegates to Tabs so wrap matches the bar.

        Focus must leave the current pane *first*: assigning the active tab
        while a widget inside that pane holds focus is silently reverted
        (t1060). Focus then stays on the bar, from which `down` re-enters
        content — the brainstorm `_select_tab` convention.
        """
        bar = self._tab_bar()
        if bar is None:
            raise SkipAction()
        bar.focus()
        if direction > 0:
            bar.action_next_tab()
        else:
            bar.action_previous_tab()

    def action_prev_tab(self) -> None:
        self._switch_tab(-1)

    def action_next_tab(self) -> None:
        self._switch_tab(+1)
```

Needs `from textual.actions import SkipAction`.

### Decisions pinned by this design

- **Wrap, not clamp** at the ends — inherited from `Tabs._move_tab`, so the
  bar and the table behave identically.
- **Focus lands on the tab bar after a `left`/`right` switch** (not in the new
  pane's list). Required by t1060 and consistent with brainstorm; `down` is
  the one-key follow-up into content.
- **`down` from the bar always lands on row 0**, per the task's requirement 1.
- **`left`/`right` on `#detail_scroll` now switch tabs** instead of scrolling
  horizontally. That is the direct consequence of requirement 3 ("regardless
  of what holds focus"); vertical scrolling of the detail pane is unaffected.
  Probe-verified and pinned by
  `test_left_right_switch_tabs_from_the_detail_pane` — this is the pane the
  task's own constraint note warns about ("a pane that *is* horizontally
  scrollable would swallow the key instead"), so it gets a positive assertion
  rather than being inferred from the table-focused case.
- **Exception handling is narrow and fails toward the focused widget.** Helper
  lookups catch only `ScreenStackError` / `NoMatches` / `WrongType` and route a
  miss to `SkipAction`; the modal gate catches nothing at all.

## Tests — `tests/test_syncer_rows.py` (added to `TabbedShellTests`)

Uses the existing `booted()` fixture, `activate_tab()` helper and
`self._run(runner())` idiom.

| Test | Covers |
|---|---|
| `test_down_from_tab_bar_enters_the_active_list` | req 1, both Branches and Versions |
| `test_up_on_first_row_returns_to_the_tab_bar` | req 2 |
| `test_up_mid_list_moves_cursor_and_keeps_focus` | req 2 **negative control** — handoff must not fire mid-list |
| `test_left_right_switch_tabs_while_the_table_holds_focus` | req 3; asserts `TabbedContent.active` actually changed (t1060 makes a naive impl pass for the wrong reason) |
| `test_tab_switching_wraps_at_both_ends` | pins wrap |
| `test_arrows_in_an_upgrade_modal_do_not_switch_tabs` | pushes `UpgradeTargetScreen`; asserts `Input` caret moves on `left`, `RadioSet` selection moves on `down`, and `TabbedContent.active` is unchanged |
| `test_down_on_the_settings_placeholder_is_a_noop` | designed no-list case; focus stays on the bar, no exception |
| `test_down_falls_through_when_a_mapped_list_is_missing` | the **other** `None` reason: patch `TAB_LIST_IDS` so the active tab maps to an absent id, assert `down` does not consume the key or move focus (distinct rejection reasons, each tested) |
| `test_detail_scroll_keeps_vertical_arrows` | SkipAction fall-through: `up`/`down` scroll the pane, focus retained |
| `test_left_right_switch_tabs_from_the_detail_pane` | req 3's **"regardless of what holds focus"** claim at the one pane that would otherwise swallow the key: focus `#detail_scroll`, press `right` then `left`, assert `TabbedContent.active` changes both ways and focus lands on the bar. Also the positive pin for the *intended* removal of horizontal scrolling there |
| `test_nav_actions_inert_only_while_a_screen_is_pushed` | `check_action` unit assertions (`True` on the main screen, `False` with a modal pushed) |
| `test_nav_check_action_is_exception_free_before_mount` | builds the app without booting (the `:812` idiom) and asserts `check_action("nav_up", ())` returns `True` without raising — pins that the modal gate needs no `try/except` and therefore has no fail-open path |

`test_tab_bar_is_two_tabs_away_and_detail_stays_focusable` (`:738-751`) is
**left unchanged and must still pass** — nothing binds `tab`, so the
traversal chain is untouched (task verification step 7).

## Verification

1. `python3 tests/test_syncer_rows.py` — full file green (note the
   subclassing: `TabbedShellTests` tests re-run inside `VersionsTabTests` and
   `UpgradeActionTests`).
2. `bash tests/run_all_python_tests.sh` for the wider suite.
3. **Falsifiability** — drop each guard in turn and confirm the matching test
   exits non-zero, restoring by undoing *only* the mutation (never
   `git checkout --`):
   - remove the `table.cursor_row > 0` SkipAction → `test_up_mid_list_moves_cursor_and_keeps_focus` fails;
   - remove `bar.focus()` from `_switch_tab` → `test_left_right_switch_tabs_while_the_table_holds_focus` fails;
   - remove the `NAV_ACTIONS` modal gate → `test_arrows_in_an_upgrade_modal_do_not_switch_tabs` fails;
   - make `_switch_tab` return early instead of switching → `test_left_right_switch_tabs_from_the_detail_pane` fails (proving that test is not a duplicate of the table-focused one).
4. **Manual smoke** — `ait syncer`: from boot, `up` from the first branch row
   reaches the bar and `down` returns to it; `left`/`right` move between
   Branches/Versions/Settings from anywhere; `U`/`c` on Versions still follow
   their per-tab gating; `?` opens the shortcut editor with the four nav rows
   listed and its own arrows still working.

## Risk

### Code-health risk: medium
- App-level `priority=True` arrows preempt **every** focused widget on the main screen; a future focusable pane (t1223_5's real Settings tab) that owns its own arrows will silently lose them unless it is added to `TAB_LIST_IDS` / the fall-through logic. · severity: medium · → mitigation: t1267 (syncer_settings_tab_nav_coordination)
- The four nav actions become rebindable rows in the `?` shortcut editor as a side effect of `ShortcutsMixin` registering all `BINDINGS`; a user remap of `nav_up` silently changes the list-boundary behaviour. · severity: low · → mitigation: none proposed (matches `KanbanApp`)
- `left`/`right` on `#detail_scroll` stop scrolling horizontally — an intentional consequence of requirement 3, but a removal of existing behaviour. · severity: low · → mitigation: none proposed (pinned by test + plan decision)

### Goal-achievement risk: low
- Every requirement was probe-verified against the real `SyncerApp` before this plan was written, so the mechanism cannot turn out to be the wrong shape mid-implementation. Residual: wrap-vs-clamp was chosen as **wrap** by delegating to native `Tabs`; if clamp were wanted it is a one-line change. · severity: low · → mitigation: none needed

### Planned mitigations
- timing: after | name: syncer_settings_tab_nav_coordination | created: t1267 | type: chore | priority: medium | effort: low | addresses: code-health risk #1 (future focusable pane silently loses arrows) | desc: Add a bidirectional coordination note to t1223_5 so the real Settings pane extends TAB_LIST_IDS and re-verifies its widgets still receive arrows under the App-level priority bindings.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in two files.
  `.aitask-scripts/syncer/syncer_app.py` (+134): `NAV_ACTIONS` / `TAB_LIST_IDS`
  module constants beside the existing tab-gating tuples; four `priority=True`,
  `show=False` arrow bindings appended to `SyncerApp.BINDINGS`; `_tab_bar()` /
  `_active_list()` helpers with the narrow `_QUERY_MISS` catch; the `NAV_ACTIONS`
  modal gate as the first branch of `check_action`; and
  `action_nav_down` / `action_nav_up` / `_switch_tab` / `action_prev_tab` /
  `action_next_tab`. `tests/test_syncer_rows.py` (+278): 12 new tests in
  `TabbedShellTests` (each therefore runs 3x, via `VersionsTabTests` and
  `UpgradeActionTests`).

- **Deviations from plan:** None in design. One test-authoring correction: the
  modal-gate test first asserted `RadioSet.pressed_index`, which does **not**
  move on arrow keys — `pressed_index` is the index of the *checked* button and
  only changes on space/enter, while up/down move the private `_selected`
  highlight. Rewritten to a render-level assertion on the public `-selected`
  CSS class (`#mode_latest` -> `#mode_pinned`), which observes the same
  behaviour without reaching into a private attribute.

- **Issues encountered:**
  - The mechanism was probe-verified against the real `SyncerApp` under
    `run_test()` *before* the plan was written (the task demanded this). Two
    probe iterations were needed: the first used a 2-row fixture so the
    "SkipAction falls through mid-list" assertion was inconclusive, and read the
    modal's `Input` caret right after `focus()` (which resets it). Both were
    probe artifacts, not defects — resolved with a 6-row fixture and a
    baseline comparison against a plain `SyncerApp` carrying no nav bindings.
  - Pre-mount, `App.query_one(...)` raises `textual.app.ScreenStackError`, **not**
    `NoMatches` (it resolves `self.screen` first). An `except NoMatches` alone
    would not have covered the pre-mount path — this is why `_QUERY_MISS` is a
    three-tuple.
  - `len(self.screen_stack)` is exception-free even pre-mount (returns `0`), so
    the modal gate needs no `try/except` at all. This matters: a swallowed
    exception there could only ever fail **open** and let a priority arrow
    hijack a modal widget. Pinned by
    `test_nav_check_action_is_exception_free_before_mount`.

- **Key decisions:**
  - **Mechanism: App `priority=True` BINDINGS + `check_action` blanket modal
    gate** (the board pattern). `on_key` (settings/brainstorm) was measured and
    rejected: the syncer's panes are row-cursor `DataTable`s that consume all
    four arrows before the App sees them.
  - **Wrap, not clamp**, inherited by delegating to `Tabs.action_next_tab` /
    `action_previous_tab` (`_tabs.py:761` uses modulo), so the bar and the
    content panes behave identically.
  - **Focus lands on the tab bar after a tab switch**, not in the new pane —
    required by t1060 and consistent with brainstorm; `down` is the one-key
    follow-up into content.
  - **`_active_list()` returning `None` has two distinct causes** that callers
    must not conflate: no list mapped for the tab (Settings placeholder — a
    designed no-op that consumes the key) versus a mapped-but-unresolvable
    query (a degraded lookup that must `SkipAction` and hand the key back).
    Each is separately tested.
  - **Accepted trade-off:** the four nav actions become rebindable rows in the
    syncer's `?` shortcut editor, because `ShortcutsMixin.__init__` registers
    everything in `self.BINDINGS`. Identical to `KanbanApp`'s four `nav_*`
    arrows, so it is house behaviour rather than a new precedent.
  - **Accepted trade-off:** `left`/`right` on `#detail_scroll` now switch tabs
    instead of scrolling horizontally — the direct consequence of requirement 3.

- **Verification results:** `tests/test_syncer_rows.py` 147 passed;
  `tests/run_all_python_tests.sh` 2218 passed, every sub-suite green. The
  pre-existing `test_tab_bar_is_two_tabs_away_and_detail_stays_focusable` was
  left unmodified and still passes (nothing binds `tab`).
  Five falsifiability drops were run, each exiting 1, restored by undoing only
  the mutation: the `cursor_row > 0` boundary; `bar.focus()` in `_switch_tab`;
  the `NAV_ACTIONS` modal gate; a SkipAction-fall-through tab switch; and the
  degraded-lookup guard in `action_nav_up`. The last two carry **discriminating
  controls** — the fall-through design still passes the table-focused test
  (exit 0) and is caught only by `test_left_right_switch_tabs_from_the_detail_pane`,
  and the conflated-`None` variant still passes the normal handoff test and is
  caught only by `test_up_falls_through_when_the_mapped_list_is_missing`.

- **Not verified by this task:** the manual `ait syncer` smoke (interactive TUI)
  — offered as a follow-up at Step 8c.

- **Upstream defects identified:** None
