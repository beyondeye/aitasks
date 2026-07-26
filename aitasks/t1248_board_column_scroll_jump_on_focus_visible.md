---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui, tmux, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-26 11:33
updated_at: 2026-07-26 12:02
---

## Symptom

In `ait board`, while scrolling a task column with the mouse wheel, the column
suddenly jumps back to (near) the top and scrolling continues from there — the
scroll position is lost. Reproduced in both directions, independent of scroll
speed. Most visible in the first column (Unsorted / Inbox), which is the tallest.

**Only reproduces inside tmux.** Verified by the reporter: running `ait board`
in a plain terminal (Ghostty, no tmux) does not exhibit it.

## Root cause

Confirmed from a 4118-event instrumented trace of the real `KanbanApp`
(PyPy runtime, real terminal), which caught the fault 9 times. Sequence, using
the episode at t=79.1s:

1. Wheel scrolling is healthy: `KanbanColumn._scroll_to(animate=False)` walks
   `scroll_y` 2, 4, 6 … 156, 158 with `scroll_y == scroll_target_y` throughout.
2. `t=78.899` — a `TaskCard` receives **focus** mid-scroll, with no click, no
   resize and no board refresh in the trace. Focus lands on the *next* card in
   the column; across the 9 episodes it walked t1216 → t1218 → t1220 → t1221 →
   t1222 → t1223, exactly one card per episode, always in the scroll direction.
   The only code path that advances focus by exactly one card is
   `action_nav_down` / `action_nav_up` (`aitask_board.py:6406-6435`,
   `cards[idx + 1].focus()`), i.e. a `down` / `up` key press arrived.
3. `TaskCard.on_focus` (`aitask_board.py:1672-1674`) calls `self.scroll_visible()`
   with Textual's defaults — `animate=True, immediate=False` — so the scroll is
   **deferred** (`screen.py:_invoke_and_clear_callbacks`) and **animated**.
4. `t=79.111` (~200 ms later, while the user is still wheeling) the deferred
   callback lands:
   `_scroll_to(req_y=8.0, animate=True)` → `scroll_target_y = 8` while
   `scroll_y` is still `158`; a follow-up call drives `scroll_target_y` to `0`.
5. The next wheel tick computes its destination from the **target**, not the
   actual position — `_scroll_down_for_pointer` uses
   `self.scroll_target_y + self.app.scroll_sensitivity_y`
   (`textual/widget.py:3301`, mirrored at `:3379` for up) — so it resumes from
   the poisoned target: the column snaps from `158` to `2`.

Net effect: one stray focus change destroys the live scroll position, and the
damage persists because `scroll_target_y` is left desynced from `scroll_y`.

### Why tmux-only

The focus-moving input is a cursor key produced by tmux's alternate-screen
wheel → cursor-key emulation. The board binds `up`/`down` with `priority=True`
(`aitask_board.py:5411-5412`), and Textual resolves priority bindings at App
level (`textual/app.py:4137`, `_check_bindings(..., priority=True)`) **before**
the event reaches `Screen._forward_event` — which is why screen-level input
logging never sees them, and why the board reacts to them as card navigation
rather than as scrolling. Environment: tmux 3.7b, `mouse on`, client Ghostty,
pane `alternate_on=1 mouse_any_flag=1`.

## What was ruled out (do not re-investigate)

- **Wheel handling itself.** Synthetic SGR wheel input against the real
  `KanbanApp` — slow single ticks, 8-tick bursts, 300-event bursts, both
  directions, with and without a focused card — produced 100% monotonic
  scrolling, zero backward steps, and `scroll_y == scroll_target_y` at every
  step.
- **Periodic refresh.** `auto_refresh_minutes` is `0`, there is no filesystem
  watcher and no other App-level `set_interval`; the board sat rock-steady for
  30 s of idle observation.
- **`apply_filter` / `_recompose_column` virtual-size churn.** No
  `_size_updated` on the scrolled column appears anywhere near the jumps.
- **Rendering artifact.** The trace shows the internal scroll position really
  does move backwards; it is not a stale tmux frame.

## Acceptance criteria

1. A stray `up`/`down` key arriving while the user is wheel-scrolling a column
   no longer teleports that column. Whatever focus behaviour is chosen, the
   column's `scroll_target_y` must never be left pointing somewhere the user
   did not ask for.
2. `TaskCard.on_focus` no longer issues a deferred, animated scroll that can
   land behind live user input. Candidate directions (pick with evidence, do
   not adopt blindly):
   - call `scroll_visible(animate=False, immediate=True)` so target and actual
     move together and nothing is queued behind the user;
   - skip the scroll entirely when the card is already fully visible;
   - suppress the focus-driven scroll while the container is actively
     scrolling — Textual exposes `Widget.is_scrolling` and `_last_scroll_time`
     (`textual/widget.py:2588-2601`) for exactly this.
3. Keyboard card navigation still scrolls the newly focused card into view when
   it is off-screen (the behaviour `on_focus` exists to provide) — this must not
   regress; cover it with a render/scroll-position assertion.
4. A regression test drives the real `KanbanApp` via `Pilot`: scroll a column to
   a mid position with wheel events, then trigger a focus change on a card near
   the top, then send one more wheel tick, and assert the column did **not** jump
   backwards. The test must fail against the current code (prove the harness can
   fail before pinning it).
5. Separately assess whether the board should be defensive about tmux's
   wheel → cursor-key emulation at all (e.g. ignoring nav keys that arrive
   during an active wheel scroll), and record the decision. If the conclusion is
   that this half belongs upstream (tmux or Textual), say so explicitly rather
   than leaving it implied.

## Reproduction harness

The investigation used a monkeypatched wrapper around the real app that logs
every `Widget._scroll_to`, `scroll_visible` and `_size_updated` on
`KanbanColumn`, plus every input event reaching `Screen._forward_event`. Note
that priority-bound keys are invisible at that seam — any follow-up
instrumentation must hook `App._check_bindings` (or `App.on_event`) to see the
`up`/`down` keys that actually trigger this.
