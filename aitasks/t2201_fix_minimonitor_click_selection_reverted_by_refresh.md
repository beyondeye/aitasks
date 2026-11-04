---
priority: high
effort: medium
depends: [2183, t2037_3]
issue_type: bug
status: Ready
labels: [minimonitor, tui, monitor]
gates: [risk_evaluated]
created_at: 2026-11-04 17:01
updated_at: 2026-11-04 17:45
---

## Sequencing decision (user request, 2026-11-04)

Defer this task until t2183 (incremental UI updates, rendering only changed
cards) and t2037_3 (monitor/minimonitor subscribe to the shared status server)
are complete. t2037_3 includes the server and client prerequisites; unrelated
applink migration is not a prerequisite for this fix.

After those improvements land, reproduce the selection race against the new
update paths before choosing a fix. The analysis and fix direction below
describe the pre-improvement code and must be reassessed. Preserve the user's
latest selection with the smallest necessary change; avoid adding focus
machinery for teardown paths that t2183 removes. If the prerequisite work
already fixes the issue, verify that behavior and record the outcome without
adding redundant code.

## Symptom (user report, 2026-11-04)

In `ait minimonitor`, clicking an agent card close to a list refresh: the
clicked card is highlighted at first, then the selection jumps away — usually
back to the previously selected agent, sometimes to some other agent. The
minimonitor also feels sluggish at the same moments (e.g. `e` to spawn a
shadow takes noticeably longer).

## Root cause (traced, not yet reproduced in a test)

The highlight is Textual focus (`MiniPaneCard:focus`). Only four sites move
focus on the main screen: the refresh-tick restore (`_restore_focus`), its
card-0 fallback (`_auto_select_own_window`), the terminal focus-in auto-select
(`_auto_select_after_focus_in`, t1683) and arrow-key `_nav`. No other worker,
timer or mixin touches main-screen focus (the `monitor_shared.py` `.focus()`
calls are all inside modal dialogs).

1. **Stale focus snapshot — "jumps back to the previous one".**
   `MiniMonitorApp._refresh_data` (`.aitask-scripts/monitor/minimonitor_app.py`,
   ~line 1794) captures `saved_pane_id = self._focused_pane_id` at the TOP of
   the tick, then awaits: session→project mapping, `_update_own_window_info`,
   `capture_all_async` (every pane), the desync probe, the own-agent panel
   build, `remove_children` + `mount_all` — and only then calls
   `_restore_focus(saved_pane_id)` (~line 1887). A click during any of those
   awaits updates `_focused_pane_id` via `on_descendant_focus`, but the restore
   uses the stale snapshot and re-focuses the old card.
   The full monitor already has the guard the minimonitor lacks: its
   `_restore_focus` (`monitor_app.py`, the t545 branch) respects a valid
   currently-focused `PaneCard` instead of reverting to the saved id. That
   guard alone does NOT port as-is: the minimonitor tears down every card on
   every tick, so after the rebuild `self.focused` is never the card the user
   clicked (that widget was removed). The user's latest intent has to be read
   as a pane id, at restore time.
2. **Deferred restore overwrites a queued click.** `_restore_focus` and
   `_auto_select_own_window` use `card.focus(...)`, which Textual defers via
   `call_later` onto the App queue. `_refresh_data` runs in a timer/worker task,
   so a click already queued on the App pump is processed first and the deferred
   focus then lands on top of it — the same mechanism t1683 fixed for focus-in
   (it switched to synchronous `self.set_focus`).
3. **"Jumps to some other agent" — candidates to confirm in the repro.**
   - Card-0 fallback: if the saved/intended card is not found, or the
     focus-in auto-select runs while a rebuild has left nothing focused
     (`remove_children` clears focus), card 0 is selected.
   - Every tick removes and remounts all cards, and while the list is childless
     `scroll_y` is clamped to 0 until `_restore_list_scroll` runs (t1539). A
     click resolved against a stale compositor map or against the clamped
     layout can hit a different card than the one the user saw.
   - Textual's `Screen._reset_focus` when the focused card is removed: verify
     which widget it picks (the `MiniPaneList` `VerticalScroll` is focusable by
     default) and whether any `DescendantFocus` it posts can overwrite
     `_focused_pane_id` after the restore set it.

## Why it happens "close to a refresh" and why it feels slow — load evidence

Measured live 2026-11-04 on the developer machine (24 cores, load ≈5.9,
20 GiB available — the box itself is not starved):

- one `tmux -L ait` server at 40–73 % of a core, serving 50 control-mode
  clients (46 minimonitors + 5 monitors) across 111 panes in 5 sessions;
- plain `display-message` round trip: 3–119 ms;
- a full `capture-pane -p -e -S -200` sweep of all 111 panes (shell loop,
  includes fork cost): 0.9–4.4 s — and every minimonitor runs a sweep every
  3 s.

So each minimonitor tick now takes seconds, and the stale-snapshot window in
(1) is seconds long rather than milliseconds. `e` (shadow spawn) issues tmux
commands that queue on the same saturated server. **The load is NOT this
task's scope** — it is owned by t2034 / t2037 (shared monitor status server:
one scanner instead of N) and t2183 (minimonitor renders only changed cards,
no full teardown per tick). This task fixes the focus logic, which is a
correctness bug at any load; load only widens the window.

## Fix direction

- Restore the user's **current** intent, not the start-of-tick snapshot: read
  `self._focused_pane_id` (kept current by `on_descendant_focus`) at restore
  time, after the rebuild. Make sure Textual's own focus resets during
  `remove_children` cannot pollute that value (verify, don't assume — see 3).
- Make the restore and the card-0 fallback synchronous (`self.set_focus(card,
  scroll_visible=False)`), the same reasoning as `_auto_select_after_focus_in`.
- Keep the t1539/t1653/t1683 invariants: neither restore branch scrolls; the
  focus-in path still never steals a click.
- Walk both orders explicitly: click-before-restore and click-after-restore
  (but before the deferred callback would have run), plus a click during the
  awaits before the rebuild and a click between `remove_children` and
  `mount_all`.

## Tests

- Regression test under `App.run_test` (see
  `tests/test_minimonitor_focus_in_click.py` and
  `tests/test_minimonitor_scroll_preservation.py` for existing harnesses):
  make `capture_all_async` block on an event, click card B while the tick is
  suspended, release the tick, and assert focus and `_focused_pane_id` end on
  B — on both the current code (red) and the fix (green). A second case clicks
  between the rebuild and the restore.
- Read `aidocs/framework/testing_conventions.md` first: the test boots a
  Textual app that can reach `@work`/worker tasks.
- Keep the existing minimonitor tests green, including the serial carve-out
  live pin tests.

## Coordination

t2183 owns the incremental rendering changes and t2037_3 owns migration to the
shared status server. This task follows both: inspect their final update and
rebuild paths, reuse their selection-preservation behavior, and test only the
remaining race. The earlier advisory note to t2183 described the original
proposal; it does not make t2183 depend on this task.
