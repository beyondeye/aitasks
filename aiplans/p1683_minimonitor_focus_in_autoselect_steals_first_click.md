---
Task: t1683_minimonitor_focus_in_autoselect_steals_first_click.md
Branch: main
Base branch: main
Output branch: main
---

# t1683 — minimonitor: focus-in auto-select steals the first click

## Context

In `ait minimonitor`, when the minimonitor pane is **not** the active tmux pane,
the first click on an agent card does not select the card under the cursor — the
user has to click twice. The symptom is only visible when the agent list is long
enough to scroll (reported live on a 40x61 pane with ~20 cards).

`MiniMonitorApp.on_app_focus()` fires on *every* terminal focus-in and
unconditionally calls `_auto_select_own_window()`, which does
`list_cards[0].focus()`. Two Textual facts turn that into the bug:

1. `Widget.focus()` is **deferred** (`widget.py:4597` → `app.call_later`), while
   click-focus is **synchronous** (`Screen._forward_event` →
   `set_focus(..., scroll_visible=False)`, `screen.py:1932`).
2. `focus()` defaults to `scroll_visible=True`, so the deferred call also drags
   `#mini-pane-list` back to the top.

Textual already restores the pre-blur widget on `AppFocus`, non-scrolling
(`App._watch_app_focus`, guarded on `screen.focused is None`) — and
`MessagePump._get_dispatch_methods` walks the MRO **subclass first**, so
`MiniMonitorApp.on_app_focus` runs *before* `App._on_app_focus`. The queued
card-0 focus therefore lands last and overwrites both Textual's restore and the
click.

**Both interleavings reproduce headlessly** (probed against the unmodified
source, 20 cards, `size=(40,12)`, `scroll_y=14`, card `%10` focused):

| interleaving | focused / `scroll_y` observed | expected |
|---|---|---|
| mouse queued behind the focus-in | `%0` / `0` | `%10` / `14` |
| callback flushes first, then the click | `%3` / `0` | `%10` / `14` |

The second row is the "you select an agent you did not aim at" symptom: the list
scrolled, so the same screen `y` is now a different card.

**Intended outcome:** a focus-in never moves the selection or the scroll
position when anything is already focused, and never scrolls at all.

## Approach

Two edits in `.aitask-scripts/monitor/minimonitor_app.py`, both empirically
validated by the probe (results table under Verification):

1. **Never scroll on an auto-select.** `_auto_select_own_window` uses
   `focus(scroll_visible=False)`. Unconditional — not a parameter — because
   *neither* of its two call sites wants a scroll: `_restore_focus`'s fallback
   runs inside a passive refresh where the captured anchor is authoritative
   (t1539, exactly the reason its sibling branch six lines above already passes
   `scroll_visible=False`), and a focus-in is not a scroll gesture.

2. **Guard the focus-in at the deferred moment, and settle focus synchronously
   there.** `on_app_focus` only schedules; the decision runs in
   `_auto_select_after_focus_in`, which bails when *anything* is focused and
   otherwise calls `self.set_focus(card, scroll_visible=False)` — **not**
   `Widget.focus()`, which would defer a second time and land after a click
   still queued behind it.

Why `self.focused is not None` rather than `isinstance(..., MiniPaneCard)`: by
the time the callback runs, anything focused is more authoritative than "card 0"
— a card Textual restored, the card the click just focused, or a modal's own
control. The current code steals focus out of an open dialog on any alt-tab;
this fixes that too.

The fallback is deliberately **kept** rather than deleted. `AUTO_FOCUS = "*"`
does *not* cover the empty case here: at compose the list is empty, so auto-focus
lands on `#mini-own-agent` (a `VerticalScroll`), and a card is only selected
later by `_restore_focus`'s per-tick fallback. A guarded, non-scrolling,
synchronous fallback closes that window deterministically for six lines.

### Files

**`.aitask-scripts/monitor/minimonitor_app.py`**

- New `_first_list_card()` helper (`:2005` area) — the shared query, so the two
  focus paths do not duplicate it.
- `_auto_select_own_window()` — `focus(scroll_visible=False)`; docstring records
  the accepted consequence (a mid-list reader whose focused agent dies keeps
  their position, with focus on an off-screen card 0).
- `on_app_focus()` — body becomes `self.call_later(self._auto_select_after_focus_in)`;
  docstring replaced (the current one still claims the pre-t511-degradation
  behaviour, "re-selects the card matching this window's agent").
- New `_auto_select_after_focus_in()` — the guard + synchronous `set_focus`.
- `_restore_focus()` comment at `:1992` — it currently classifies
  `on_app_focus -> _auto_select_own_window` as an *active gesture* allowed to
  scroll. That classification **is** the bug; rewrite it to say neither branch of
  the method scrolls, and that keyboard nav (which goes through `Widget.focus()`
  directly) is the real active gesture.

**`tests/test_minimonitor_focus_in_click.py`** (new) — see Verification.

**`aidocs/framework/tui_conventions.md`** — a short section after
`## Startup focus: AUTO_FOCUS …` recording the reusable trap: `Widget.focus()`
is deferred and click-focus is synchronous, `on_*` handlers dispatch subclass
-first so an inline `self.focused is None` check in an `AppFocus` handler always
passes, and Textual already restores focus on `AppFocus` without scrolling.

### Post-phase (risk mitigations)

- **`pin_restore_focus_fallback_scroll_contract`** — after the two
  `_auto_select_*` edits land and the seven cases below pass, extend
  `…restore_focus_fallback_does_not_scroll` into a two-sided pin of the
  `_restore_focus`-fallback contract: assert not only that `scroll_y` is
  unchanged but that the fallback **still focuses card 0**. The un-named sibling
  call site then has both halves of its new behaviour asserted, so a later edit
  that turns the fallback into a no-op cannot pass by "not scrolling".

## Verification

New module `tests/test_minimonitor_focus_in_click.py`, headless, reusing the
`_ListHost` pattern from `tests/test_minimonitor_scroll_preservation.py` (the
real `MiniMonitorApp` with only `__init__` narrowed; `TMUX` scrubbed at import so
the real `on_mount` takes its "Not inside tmux" early return). Fixture: 20
`MiniPaneCard`s in `run_test(size=(40,12))`, `scroll_to(y=14, force=True)`, card
`%10` focused.

Interleaving 1 is driven by `app.post_message(AppFocus())` immediately followed
by `app.post_message(MouseDown(...))` — **not** `pilot.click`, which `await`s a
`pause()` before each event and would drain the pending callback first, making
that interleaving unreachable. Screen coordinates come from `card.region` before
the focus-in.

Seven cases. All three columns below are **measured**, not predicted — the
middle column is a deliberate mutant that keeps edit 1 (`scroll_visible=False`)
and drops edit 2 (the guard), i.e. `on_app_focus` back to an unconditional
`self._auto_select_own_window()`.

| # | test | pre-fix | scroll-fix only, no guard | fixed |
|---|---|---|---|---|
| 1 | `…click_queued_with_the_focus_in_wins` | `%0` / `0` | `%0` / `14` | `%10` / `14` |
| 2 | `…click_after_the_callback_lands_on_the_aimed_card` | `%3` / `0` | `%10` / `14` | `%10` / `14` |
| 3 | `…focus_in_alone_preserves_the_focused_card_and_scroll` | `%0` / `0` | `%0` / `14` | `%10` / `14` |
| 4 | `…focus_in_without_a_preceding_blur_preserves_focus` | `%0` / `0` | `%0` / `14` | `%10` / `14` |
| 5 | `…nothing_focused_selects_card_zero_without_scrolling` | `%0` / `0` | `%0` / `14` | `%0` / `14` |
| 6 | `…does_not_steal_focus_from_another_widget` | `%0` / `0` | `%0` / `14` | `#mini-own-agent` / `14` |
| 7 | `…restore_focus_fallback_does_not_scroll` | `%0` / `0` | `%0` / `14` | `%0` / `14` |

**Rows 3 and 4 test the stated invariant directly** — a focus-in with a card
already focused and **no click at all**. Row 3 is the alt-tab round trip
(`AppBlur` → settle → `AppFocus`), where Textual's own restore re-focuses `%10`
and the guard must leave it alone. Row 4 posts a bare `AppFocus` with `%10` still
focused and **no** preceding blur — `app_focus` is already `True`, so
`App._watch_app_focus` never fires and the guard is the *only* thing standing
between the card and card 0. Neither row exists without this addition, and the
mutant column shows why they are load-bearing: row 2 passes against the
guard-less mutant, because the later click re-focuses `%10` and hides the
mistake. Rows 1, 3, 4 and 6 are what actually see it.

Row 5 is the non-vacuity control for the fallback (deleting `on_app_focus`
outright fails it); row 6 pins the guard as `focused is not None` rather than a
card-only check.

**Two negative controls, both to be run and recorded in the module docstring:**

1. **Revert both edits** (pre-fix source) — all seven tests fail with column
   `pre-fix` above.
2. **Keep `scroll_visible=False`, drop the guard** — restore `on_app_focus` to
   an unconditional `self._auto_select_own_window()`. Rows **1, 3, 4, 6** fail;
   rows 2, 5, 7 pass. This is the control that proves the guard is pinned
   independently of the non-scrolling change.

**Regression:** these four modules are green at baseline and must stay green —
`test_minimonitor_scroll_preservation.py` (t1539 mid-list restore),
`test_minimonitor_bottom_pin.py` (t1653), `test_minimonitor_own_task_info.py`
(cites `_auto_select_own_window`'s "always focuses a list card" claim, still true
via `_restore_focus`), `test_minimonitor_top_chrome_render.py`. Then
`bash tests/run_all_python_tests.sh --test-dir tests` and
`shellcheck` is not applicable (no shell changes).

## Step 8d follow-up to create

`tests/test_multi_session_minimonitor.sh` Tier 1d asserts an
`_auto_select_own_window` **predicate that no longer exists in the source** —
`snap_window_index == own_window_index and snap_session in ("", own_session)`,
the pre-degradation t511 behaviour. The test defines that predicate locally and
asserts against its own copy, so it stays green no matter what the real method
does, including after this change. That is misleading regression coverage, not
coverage.

Create at Step 8d (a plain follow-up, not a risk mitigation):

- **type:** `test` · **priority:** low · **effort:** low · **labels:** `tui`,
  `minimonitor`
- **scope:** remove or rewrite `tests/test_multi_session_minimonitor.sh` Tier 1d
  so it exercises the real `MiniMonitorApp` focus-selection behaviour (or is
  deleted as superseded by `tests/test_minimonitor_focus_in_click.py`), and
  audit the file's other tiers for the same self-mirroring pattern.
- **depends:** t1683.

Deliberately not folded into t1683: it is a test-hygiene cleanup with its own
audit scope, and mixing it in would put an unrelated shell-test rewrite inside a
focused bug fix.

## Step 9 (Post-Implementation)

Standard close-out: commit as `bug: <description> (t1683)` on `main`, run the
`risk_evaluated` gate, then archive the task and plan per the shared workflow's
Step 9.

## Risk

### Code-health risk: low

- `_restore_focus`'s fallback stops scrolling card 0 into view, so a mid-list
  reader whose focused agent dies keeps their scroll position while focus moves
  to an off-screen card 0. This matches t1539's intent (the anchor restore owns
  the position) and self-heals on the next arrow key, but it is a real behaviour
  change at a call site the task did not name · severity: low · → mitigation:
  inline post-phase pin_restore_focus_fallback_scroll_contract

### Goal-achievement risk: low

- The fix is proven headlessly, against a faithful model of the production
  message ordering (same `App` FIFO, same `Screen._forward_event`), but the
  defect was reported from a live 40x61 tmux pane. tmux's `focus-events on` +
  `MouseDown1Pane` forwarding is excluded by the task's own analysis rather than
  by measurement here · severity: low · → mitigation: none (accepted — a live-pane
  manual verification was proposed and declined)

### Planned mitigations
- timing: post-phase | name: pin_restore_focus_fallback_scroll_contract | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — `_restore_focus` fallback behaviour change | desc: pin both halves of the fallback contract (focuses card 0 AND does not scroll), not just the non-scrolling half
