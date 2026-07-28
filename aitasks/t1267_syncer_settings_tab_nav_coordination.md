---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-27 14:49
updated_at: 2026-07-27 14:49
---

## Origin

Risk-mitigation ("after") follow-up for t1266, created at Step 8d after
implementation landed.

## Risk addressed

Code-health risk #1 from `aiplans/archived/p1266_syncer_tab_arrow_navigation.md`
(severity: medium), verbatim:

> App-level `priority=True` arrows preempt **every** focused widget on the main
> screen; a future focusable pane (t1223_5's real Settings tab) that owns its own
> arrows will silently lose them unless it is added to `TAB_LIST_IDS` / the
> fall-through logic.

## Goal

t1266 gave `ait syncer` App-level `priority=True` bindings for `up` / `down` /
`left` / `right` (`.aitask-scripts/syncer/syncer_app.py`, `NAV_ACTIONS`). These
fire **before** the focused widget's own bindings on the main screen. Today that
is safe because the only focusable main-screen widgets are two row-cursor
`DataTable`s and a `VerticalScroll`, all of which the nav actions explicitly
account for.

The syncer's Settings pane is still a non-focusable `Static` placeholder, so it
is deliberately absent from `TAB_LIST_IDS`. **t1223_5** (`Settings tab and push
action`) will replace it with real, focusable content — at which point any
widget in that pane that owns arrow keys (an `Input` caret, a `Select` overlay,
a `RadioSet`, a nested `DataTable`) will silently lose them unless the nav
actions are extended.

This task closes that loop:

1. Add a coordination note to `aitasks/t1223/t1223_5_settings_tab_and_push_action.md`
   pointing at `NAV_ACTIONS` / `TAB_LIST_IDS` / `action_nav_up` / `action_nav_down`
   in `.aitask-scripts/syncer/syncer_app.py`, stating that the new pane must
   either be registered in `TAB_LIST_IDS` (if its primary content is a list) or
   have its focusable widgets added to the `SkipAction` fall-through conditions.
   Add the reverse pointer back to this task so the link is bidirectional.
2. Verify the note survives: re-read t1223_5 and confirm the reference resolves
   to live symbol names (they are pinned by `tests/test_syncer_rows.py`).

If t1223_5 has already landed by the time this task is picked, replace step 1
with the actual fix: extend `TAB_LIST_IDS` / the fall-through conditions and add
a test asserting the Settings pane's focusable widgets still receive their arrow
keys (mirroring `test_arrows_in_an_upgrade_modal_do_not_switch_tabs`).

## Status — the substantive fix landed with t1223_5 (2026-07-28)

t1223_5 landed before this task was picked, so its "If t1223_5 has already
landed" branch applies and **it did the work**:

- `TAB_LIST_IDS` gained `"tab_settings": "settings"`, so `↓` from the tab bar
  enters the new Settings table and the pane is a first-class arrow-nav target
  (`test_down_from_the_bar_enters_the_settings_table`).
- `test_arrows_in_a_settings_modal_do_not_switch_tabs` asserts the Settings
  modals keep their arrows — the `RadioSet` highlight and the `SelectionList`
  cursor both move, and `←`/`→` do not switch tabs.
- **No fall-through change was needed.** The Settings pane's own content is a
  row-cursor `DataTable` (which owns no `←`/`→`), and every widget that does own
  arrows lives on a *pushed screen*, where `check_action`'s blanket
  `len(self.screen_stack) <= 1` gate already disables all four nav actions —
  pinned by the pre-existing `test_nav_actions_inert_only_while_a_screen_is_pushed`.

What remains here is verification and disposal: re-check the above against the
live source and close this task if nothing further is needed.

## Key files

- `.aitask-scripts/syncer/syncer_app.py` — `NAV_ACTIONS`, `TAB_LIST_IDS`,
  `action_nav_up`, `action_nav_down`, `_switch_tab`, `check_action`.
- `aitasks/t1223/t1223_5_settings_tab_and_push_action.md` — the coordination target.
- `tests/test_syncer_rows.py` — the `TabbedShellTests` nav section added by t1266.
