---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, minimonitor, textual]
gates: [risk_evaluated]
created_at: 2026-09-02 10:45
updated_at: 2026-09-02 10:45
---

## Problem

In `ait minimonitor`, when the minimonitor pane is **not** the active tmux pane,
the first click on an agent card does not select the card under the cursor. The
user has to click a second time. The symptom is only obvious when the agent list
is long enough to have a vertical scrollbar — with a short, unscrollable list it
is invisible.

Reported live on a 40x61 minimonitor pane with ~20 agent cards.

## Root cause

`MiniMonitorApp.on_app_focus()` (`.aitask-scripts/monitor/minimonitor_app.py:2015`)
fires on **every** terminal focus-in and unconditionally calls
`_auto_select_own_window()` (`:2005`), which is:

```python
list_cards = list(self.query("#mini-pane-list MiniPaneCard"))
if list_cards:
    list_cards[0].focus()
```

Two Textual facts turn that into the reported bug:

1. **`Widget.focus()` is deferred.** `textual/widget.py:4579` posts an
   `events.Callback` via `call_later`, i.e. into the app's own FIFO message
   queue. Click-focus, by contrast, is **synchronous**:
   `Screen._forward_event` calls `set_focus(focusable_widget, scroll_visible=False)`
   inline (`textual/screen.py:1932`).
2. **`focus()` defaults to `scroll_visible=True`,** so the deferred call also
   scrolls `#mini-pane-list` back to the top.

Dispatch order compounds it. `MessagePump._get_dispatch_methods` takes
`cls.__dict__.get(f"_{name}") or cls.__dict__.get(name)` **per MRO class**,
subclass first — so `MiniMonitorApp.on_app_focus` runs *before*
`App._on_app_focus`. Textual's own `_watch_app_focus` then restores
`_last_focused_on_app_blur` with `scroll_visible=False` (it is guarded on
`screen.focused is None`, which holds because `AppBlur` cleared focus) — and the
queued card-0 focus lands after that and overwrites it.

Both possible interleavings with the click are broken:

- **Mouse bytes already queued when `AppFocus` is dispatched** — the click
  focuses the correct card synchronously, then the queued callback focuses
  card 0 and scrolls to top. The click is silently undone.
- **Mouse bytes arrive in a later read** — the callback runs first, scrolling the
  list to the top; the click then lands at the same screen `y` but over a
  *different* card. The user selects an agent they did not aim at.

tmux is not implicated: `MouseDown1Pane` is bound to
`select-pane -t = \; send-keys -M`, so the click IS forwarded, and
`focus-events on` delivers the focus-in immediately before it.

## Why the auto-select is redundant

Textual already restores the previously focused widget on `AppFocus`, and does it
*without scrolling* (`App._watch_app_focus`, `scroll_visible=False`). The
minimonitor's handler therefore duplicates that behaviour with a strictly worse
version: it ignores what was focused and forces a scroll.

Its original purpose (t511, commit `5f77c04c4`) was that after an `s` switch —
`action_switch_to` prefers the companion pane, so the *target* window's
minimonitor becomes active — that minimonitor should highlight the right agent.
At the time `_auto_select_own_window` selected the card matching the own window
index; it has since degraded to "first card", and its docstring at `:2015` still
claims the old behaviour ("re-selects the card matching this window's agent").

## Blast radius beyond the click

`AppFocus` fires on any focus-in, not just a click-to-activate: alt-tabbing back
into the terminal, or any tmux pane switch onto the minimonitor, also resets the
selection to card 0 and scrolls the list to the top.

## Interaction with the existing scroll machinery (t1539 / t1653)

`MiniPaneList.scroll_to_region` (`:738`) already refuses uninvited scrolls — but
only while `_list_scroll_lock` is held, i.e. during the rebuild window. The
comment at `:1992` explicitly classifies
`on_app_focus -> _auto_select_own_window` as an *active gesture* that runs with
the lock clear and should be allowed to scroll. **That classification is the
bug** — a focus-in caused by a click is not a scroll gesture.

Any fix must not regress t1539's mid-list restore or t1653's bottom pin.

## Fix shape (to be settled during planning)

The auto-select must become (a) **non-scrolling** and (b) **guarded at the
deferred moment**, not at schedule time — an inline `self.focused is None` check
in `on_app_focus` always passes, because `AppBlur` cleared focus and
`App._on_app_focus` has not run yet.

Sketch:

- Never scroll on focus-in: any focus-in-driven `focus()` uses
  `scroll_visible=False`.
- Defer the decision behind a guard that bails when a `MiniPaneCard` is already
  focused by the time it runs, so Textual's own restore and a click both win.
- Consider dropping `on_app_focus` entirely and relying on Textual's restore,
  keeping only a first-focus-ever fallback for the case where nothing was ever
  focused. `AUTO_FOCUS = "*"` on `App` already focuses the first focusable widget
  at mount, so that case is narrow — confirm before removing.
- Fix the stale `on_app_focus` docstring either way.

## Regression test

Headless and discriminating, using `App.run_test()` / `Pilot`:

- Boot `MiniMonitorApp` with enough cards that `#mini-pane-list` scrolls.
- Scroll mid-list and focus a card that is not card 0.
- Post `events.AppBlur()`, then `events.AppFocus()`, then `await pilot.click(...)`
  on a specific card.
- Assert: the clicked card is focused **and** `scroll_y` is unchanged.

Cover both interleavings (click queued before vs. after the focus-in callback
flush), and add a negative control confirming the test fails against the
pre-fix source.

Precedents for the harness: `tests/test_brainstorm_dag_click_focus.py`
(click-to-focus), `tests/test_minimonitor_scroll_preservation.py` (scrollable
minimonitor fixture + negative-control discipline).

## Key references

- `.aitask-scripts/monitor/minimonitor_app.py:2005` `_auto_select_own_window`
- `.aitask-scripts/monitor/minimonitor_app.py:2015` `on_app_focus`
- `.aitask-scripts/monitor/minimonitor_app.py:1978` `_restore_focus` (already
  uses `scroll_visible=False`, and its comment names this call path)
- `.aitask-scripts/monitor/minimonitor_app.py:738` `MiniPaneList.scroll_to_region`
- `.aitask-scripts/monitor/minimonitor_app.py:2642` `on_descendant_focus`
- Origin of `on_app_focus`: commit `5f77c04c4` (t511)
- `aidocs/framework/tui_conventions.md`
