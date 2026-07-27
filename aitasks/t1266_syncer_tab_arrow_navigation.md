---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1223
implemented_with: claudecode/opus5
created_at: 2026-07-27 09:31
updated_at: 2026-07-27 13:52
---

## Context

`ait syncer` gained a tabbed shell in t1223_1 and a second content table in
t1223_3, but it never gained the tab-bar ⇄ content keyboard navigation the
other tabbed framework TUIs already have. Today the only way into a pane's
content from the tab bar is `Tab` (twice, via `#detail_scroll`), `up` at the
first row is silently swallowed, and `left`/`right` switch tabs **only** while
the tab bar itself holds focus.

**The syncer is the odd one out** — verified against live source:

| | bar → content | content → bar | focus after tab switch |
|---|---|---|---|
| settings | `on_key` `down` → `_nav_vertical` → `focusable[0]` | `up` at index 0 → `Tabs.focus()` | bar, then `_focus_first_in_tab` |
| brainstorm | `on_key` `down` from `Tabs` → first row / DAG | `RowNavMixin` top-boundary → `Tabs.focus()` | bar (`down` re-enters) |
| syncer | **none** (`tab` only) | **none** (`up` clamped by `DataTable`) | stays on bar |

Scope decision (user-confirmed): **syncer only**. Settings and brainstorm
already implement the behaviour; brainstorm additionally drives a DAG/graph
view with arrow keys, so retrofitting a shared mixin across all three is a
separate, larger question. Promoting a `TabNavMixin` into
`.aitask-scripts/lib/` is explicitly **out of scope** here — do it once this
contract has proven itself in one TUI.

## Goal — the navigation contract

1. **`down` on the tab bar enters the active pane's list**, landing on its
   first row.
2. **`up` on the list's first row returns focus to the tab bar.** Anywhere
   else in the list, `up` moves the row cursor as it does today.
3. **`left` / `right` always switch tabs**, regardless of what holds focus
   inside the TUI.

## Key files to modify

- `.aitask-scripts/syncer/syncer_app.py` — the navigation itself.
- `tests/test_syncer_rows.py` — extend the existing `TabbedShellTests` /
  `run_test()` half.

## Verified constraints (live source, textual 8.2.7)

- `Tabs` binds **only** `left`/`right` (`textual/widgets/_tabs.py:247-250`);
  it binds no `up`/`down`, and `ContentTabs` adds nothing. So `down` from the
  bar is free for the taking.
- `DataTable` binds `up`/`down`/`left`/`right`
  (`textual/widgets/_data_table.py:273-285`). With `cursor_type="row"`,
  `action_cursor_up/down` **consume** the key even at the clamped boundary, so
  requirement 2 cannot be met by letting the key bubble.
- `action_cursor_left/right` with a row cursor delegate to
  `Widget.action_scroll_left/right`, which `raise SkipAction()` only when
  there is no horizontal scrollbar (`textual/widget.py:4863-4871`). A pane
  that *is* horizontally scrollable would swallow the key instead — so
  requirement 3 must not depend on that fall-through.
- `ContentTabs` is a **sibling** of the pane content, not an ancestor, and
  `TabbedContent` declares no `BINDINGS` — a bubbling arrow key never reaches
  the tab bar on its own.
- **Setting `TabbedContent.active` while a widget inside the current pane
  holds focus is silently reverted** (t1060). Requirement 3 therefore has to
  hand focus to the tab bar as part of switching — the
  `brainstorm_app._select_tab` pattern (`brainstorm_app.py:2704-2723`).
- Probe result (headless, textual 8.2.7): an App-level `priority=True` arrow
  binding fires before the focused `DataTable`'s own binding, and
  `raise textual.actions.SkipAction()` from the App action correctly falls
  through to `DataTable.action_cursor_up` (cursor observed moving 2→1→0).

## Reference patterns

- `.aitask-scripts/board/aitask_board.py:5414-5420` — the sanctioned
  "App binds `priority=True` arrows" precedent, with the matching
  `check_action` gating at `:5495-5545` (screen-stack and focused-widget
  based). `aidocs/framework/tui_conventions.md` documents why the gate is
  mandatory: an App priority binding fires *before* a pushed modal's own
  binding, so an ungated arrow binding silently breaks every modal.
- `.aitask-scripts/settings/settings_app.py:1618-1665` (`_nav_vertical`) and
  `:1790-1794` (`on_key`) — the alternative house mechanism, which keeps arrow
  keys out of the remappable shortcut registry.
- `.aitask-scripts/brainstorm/brainstorm_app.py:2298-2332` (`on_key` down from
  the bar) and `:2704-2723` (`_select_tab`).

**Mechanism is a planning decision.** `on_key` (settings/brainstorm) keeps four
nav keys out of the syncer's `?` shortcuts editor; `priority=True` BINDINGS
(board) is deterministic and already probe-verified. Whichever is chosen,
**probe the real `SyncerApp` under `run_test()` before committing to it** —
`on_key` at App level may never observe an arrow the focused `DataTable`
consumed, and that must be measured, not assumed.

## Implementation notes

- The syncer's Settings tab is still a non-focusable `Static` placeholder until
  t1223_5, so `down` from the bar there has no list to enter. Decide and test
  the no-list case explicitly rather than letting it throw.
- Map the active tab to its list rather than hardcoding one table: Branches →
  `#branches`, Versions → `#versions`.
- Whatever gating is used must keep the arrows working inside the upgrade
  modals (`syncer/upgrade_screens.py`), which use a `RadioSet` (`up`/`down`
  change the selection) and an `Input` (`left`/`right` move the caret).

## Verification steps

Extend `tests/test_syncer_rows.py` (run with `python3`, not `bash`) using the
existing `booted()` fixture and `activate_tab()` helper:

1. `down` on the tab bar focuses `#branches` with the cursor on row 0; the
   same on the Versions tab focuses `#versions`.
2. `up` on row 0 focuses the tab bar; `up` on row 1 moves the cursor to row 0
   and leaves focus on the table (negative control — the handoff must not fire
   mid-list).
3. `left`/`right` switch tabs while the **table** holds focus, not just the
   bar; assert `TabbedContent.active` actually changed (the t1060 revert makes
   a naive implementation pass for the wrong reason).
4. `left`/`right` wrap or clamp at the ends — pin whichever is chosen.
5. Arrow keys inside a pushed upgrade modal do **not** switch tabs and do
   still drive the modal's own widgets.
6. `down` on the tab bar with the Settings (placeholder) tab active is a
   no-op and does not raise.
7. The pre-existing focus-traversal test
   (`test_tab_bar_is_two_tabs_away_and_detail_stays_focusable`) still passes,
   or is deliberately updated with the reason recorded.

Falsifiability: after the suite is green, drop each guard in turn (the `up`
boundary check, the tab-bar focus handoff in the switch, the modal gate) and
confirm the matching test exits non-zero. Restore by undoing only the mutation
— never `git checkout --`.

Manual smoke: `ait syncer` — from boot, `up` from the first branch row reaches
the bar, `down` returns to it, `left`/`right` move between Branches/Versions/
Settings from anywhere, and `U`/`c` on Versions still behave per their per-tab
gating.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-27T10:52:42Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-27T11:47:55Z status=pass attempt=1 type=human
