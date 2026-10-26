---
Task: t2155_fix_stats_pane_selector_enter_and_cycle_focus_guard.md
Base branch: main
Output branch: main
---

# t2155 — Fix stats PaneSelector Enter-on-Cancel and the dead Tab panel cycle

## Context

aitasks_go (the Go port of the stats TUI) found two defects in `.aitask-scripts/stats/`.
Both were reproduced here with a `run_test` probe against Textual 8.2.7:

1. **PaneSelector: Enter on a focused Cancel saves.** After space, Tab, Tab (focus on
   `btn_cancel`), pressing Enter dismissed the modal with `['overview.summary']`. It should
   dismiss with `None`. The cause is the screen-level `on_key` in
   `stats/modals/pane_selector.py:127-130`, which catches every Enter before the Button
   handles it.

2. **`StatsApp._cycle_focus` never runs, and the problem is worse than the task says.** The
   guard `if self.screen is not self` is always true (an App is never its own screen). But
   the probe showed `_cycle_focus` is **never even called** when Tab is pressed (0 calls
   after 3 Tabs). The binding chain runs from the focused widget, through its ancestors, to
   the Screen, and only then to the App. `Screen.BINDINGS` already binds
   `tab → app.focus_next` and `shift+tab → app.focus_previous` (non-priority), and those
   handle the key first. So the App's `tab`/`shift+tab → focus_next_panel/prev_panel`
   bindings (`stats_app.py:179-180`) are dead. The guard fix the task proposes would only
   change unreachable code.

   Today Tab follows the default focus chain. A probe with the real `backlog.level` pane
   (single session) gives sidebar → layout_list → **DataTable** → sidebar. That default
   chain is currently the **only keyboard route into a content table** (cell navigation,
   scrolling). Running the cycle as written (`[sessions, sidebar, layouts]`) would loop
   sidebar → layouts → sidebar forever and cut that route off. So the fix has two goals:
   make the intended cycle run, and keep the content pane reachable as one slot of that
   cycle.

## Approach

### 1. `stats/modals/pane_selector.py` — Enter defers to a focused Button

In `on_key`, treat Enter as the save shortcut only when focus is not on a `Button` (already
imported). The Button then handles Enter itself and `on_button_pressed` decides Save or
Cancel:

```python
def on_key(self, event) -> None:
    if event.key == "enter" and not isinstance(self.focused, Button):
        self.dismiss(self._selected_pane_ids())
        event.stop()
```

Update the adjacent comment so it says Enter saves from the list, while a focused button
handles its own Enter. Leave the docstring "Enter saves, Escape cancels" as is (still true
for the list).

### 2. `stats/stats_app.py` — make the panel cycle actually fire, without capturing Tab in modals

- **Bindings (lines 179-180):** add `priority=True` to the `tab` and `shift+tab` bindings.
  Priority bindings are checked from the App down, before the Screen's `focus_next`.
  `keybinding_registry.register_app_bindings` rebuilds overrides with
  `dataclasses.replace`, so `priority` survives a user key override.
- **A priority binding also fires while a modal is on top**, which would take Tab away from
  the PaneSelector, NameInput and TUI-switcher modals. Add a `check_action` override that
  returns `False` for `focus_next_panel` / `focus_prev_panel` while a modal is on top, and
  `True` otherwise. When `check_action` is falsy, `App.run_action` returns `False`, so
  `_check_bindings` falls through to the modal Screen's own `tab → focus_next`. This
  `len(self.screen_stack) > 1` pattern already exists in `board/aitask_board.py:2427`
  (`check_action`), which this follows.
- **Fix the guard in `_cycle_focus`** (task Defect 2's literal fix) using the same
  predicate, so direct calls are also safe. Share it in one small helper:

```python
def _modal_on_top(self) -> bool:
    return len(self.screen_stack) > 1

def check_action(self, action: str, parameters) -> bool | None:
    # The panel-cycle Tab bindings are priority=True so they beat the Screen's
    # default focus_next; with a modal on top, decline them so Tab falls through
    # to the modal's own focus chain.
    if action in ("focus_next_panel", "focus_prev_panel") and self._modal_on_top():
        return False
    return True
```

  and in `_cycle_focus`: `if self._modal_on_top(): return`.
- **Content pane as the last cycle slot (keeps the keyboard route into tables).** In
  `_cycle_focus`, after building `[sessions?, sidebar, layouts]`, find the first focusable
  descendant of `#content`
  (`next((w for w in content.query("*") if w.focusable), None)`; `Widget.focusable`
  exists in 8.2.7 and covers `can_focus`, disabled and display). If there is one, append it
  as the final slot. Resolve the current slot like this:
  - focus is one of the ListViews → its index;
  - focus is `#content` or any widget under it (`content in focused.ancestors_with_self`) →
    the content slot's index. Shift+tab from anywhere in a multi-widget pane then returns
    to `layouts`, and Tab goes on to the first panel;
  - anything else → `-1` (as today).
  The resulting order is sessions → sidebar → layouts → content → sessions. When the pane
  has nothing focusable (Static/chart panes), the slot is left out and the cycle is the
  documented three-panel one. Document this order in a comment next to the cycle list.
  `_apply_focus_hint` stays unchanged. The hint is a ListView border cue, and a focused
  DataTable already shows its own focus styling.

  Neither mixin (`TuiSwitcherMixin`, `ShortcutsMixin`) defines `check_action`, so returning
  `True` for every other action keeps current behaviour. The `_apply_focus_hint()` call in
  `_cycle_focus` is still called (`on_descendant_focus` already refreshes it on every focus
  change, so the `.focused_panel` styling is not newly activated in practice).

### 3. Tests — `tests/test_stats_focus_cycle_and_pane_selector_live.py` (new)

`unittest.IsolatedAsyncioTestCase` + `App.run_test(size=(120, 40))`, following
`tests/test_stats_backlog_panes_live.py`. This is not a tmux boot, so it stays out of the
serial carve-out.

PaneSelector, hosted in a minimal `App` that pushes `PaneSelectorModal("x", [])` with a
result callback:
- Enter with Cancel focused (space, tab, tab) dismisses with `None`. **Red before the fix.**
- Enter with Save focused (space, tab) dismisses with the selection.
- Enter in the SelectionList (space, enter) dismisses with the selection, so the shortcut
  is preserved.

StatsApp panel cycle (patch `stats.stats_app.discover_stats_sessions` → `[]` so the run
is single-session and deterministic). Use a **real DataTable**: render `backlog.level`
with `_fixture()` from `tests/test_stats_backlog_panes_live.py`, the same way that module
does.
- Tab is routed through the cycle: a spy on `_cycle_focus` records a call for every Tab.
  **Red before the fix** (0 calls today).
- Entry and return through the content table: from `sidebar`, tab → `layout_list` → tab →
  the pane's `DataTable` → tab → `sidebar`. While the DataTable is focused, press `down`
  and assert its `cursor_row` advanced, which proves keys reach the table. Shift+tab from
  the DataTable → `layout_list`. Shift+tab from `sidebar` → the DataTable (wrap-around).
- A Static-only pane (`overview.summary`, nothing focusable) skips the content slot:
  sidebar → layout_list → sidebar.
- Multi-session ordering: patch discovery to return two fake sessions, building them the
  way `tests/test_tui_group_nav.py` (`_sess`) does if that is cheap, otherwise forcing
  `multi_session` before compose. With the DataTable pane, assert session_list → sidebar →
  layout_list → DataTable → session_list. Decide the construction while implementing and
  keep it deterministic.
- Modal fall-through: push `PaneSelectorModal`, press tab. Modal focus moves from the
  SelectionList to `btn_save`, and `_cycle_focus` is not invoked (spy). This guards the
  `priority=True` change against capturing Tab in modals.

Red/green proof: run the new file against the unfixed tree first, by applying the test
before the source edits, and record which tests fail.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_stats_focus_cycle_and_pane_selector_live.py -q`
  (red before the source edits, green after).
- Regression set:
  `bash tests/run_all_python_tests.sh --test-dir` is directory-scoped, so instead run the
  stats-related modules directly with pytest: `tests/test_stats_backlog_panes_live.py`,
  `tests/test_stats_backlog_panes.py`, `tests/test_tui_group_nav.py`,
  `tests/test_session_key_collision.py`, `tests/test_stats_include_registered.py`, plus
  any keybinding/shortcut registry tests that enumerate stats bindings
  (`grep -l "stats" tests/test_*shortcut* tests/test_*keybinding*`).
- Re-run the scratch probe
  (`/tmp/claude-1000/-home-ddt-Work-aitasks/de18ffa5-a152-4fab-9480-9352e47fbf0f/scratchpad/probe.py`).
  Expect `cycle calls` to be non-empty and `dismiss result [None]`.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`). There is no branch to merge. Commit code and plan
separately per Step 8, then archive with `./.aitask-scripts/aitask_archive.sh 2155` and
`./ait git push`.

## Risk

### Code-health risk: low
- `priority=True` Tab bindings could take Tab away from modal screens (PaneSelector,
  NameInput, TUI switcher) if the `check_action` fall-through misbehaves · severity: low
  (the change is confined to two stats-TUI files; the fall-through follows Textual's
  documented `check_action` contract, already used by `aitask_board.py`, and the plan's
  own modal fall-through test asserts it) · → mitigation: none (covered by plan step 3)
- Making the panel cycle live changes which widgets Tab can reach. A cycle limited to the
  ListViews would remove today's only keyboard route into content DataTables · severity:
  low (residual — the plan keeps `#content` as a cycle slot whenever it holds a focusable
  widget, and step 3 checks entry, key delivery and return with a real `backlog.level`
  DataTable) · → mitigation: none (designed into step 2; tested in step 3)

### Goal-achievement risk: low
None identified. Both defects were reproduced with a probe. The fix delivers the intended
behaviour, including the part the task's proposed guard-only fix would have missed (the
App binding never fires), and is pinned by tests that fail before the fix.
