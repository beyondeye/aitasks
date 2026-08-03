---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Postponed
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1248
created_at: 2026-07-26 19:20
updated_at: 2026-07-30 07:56
boardidx: 36864
---

## Origin

Deferred by t1248 (board column scroll jump). t1248 fixed the nav-key route to
the symptom; this is a second, independent route to the same user-visible
behaviour, and it survives that fix.

## Problem

When board auto-refresh is enabled (`auto_refresh_minutes > 0` in
`board_config.json`; the default and this repo's value is `0`, which is why it
did not surface during the t1248 investigation), the periodic tick rebuilds the
board and then restores focus:

`_start_auto_refresh_timer` (`.aitask-scripts/board/aitask_board.py:5685-5691`)
→ `_auto_refresh_tick` → `refresh_board` → `_queue_refocus` → `_refocus_card`
(`:5854`) → `card.focus()` → `TaskCard.on_focus` → `scroll_visible()`.

If the user has wheel-scrolled a column away from the focused card, that refocus
pulls the column straight back to the card and the scroll position is lost —
the same complaint t1248 fixed for the nav-key trigger, arriving on a timer
instead of a keystroke.

Note `refresh_board` unmounts and remounts every column, so the columns are new
widgets and their scroll offsets are gone regardless; the refocus then decides
where the rebuilt column lands. Any fix has to preserve the *user's* scroll
position across the rebuild, not merely change where the focus scroll goes.

## Relevant context from t1248

- `TaskCard.on_focus` now calls `scroll_visible(animate=False, immediate=True)`,
  so the pull is instantaneous rather than a deferred animation — the position
  is still discarded, just without the `scroll_target_y` corruption.
- `_reanchor_to_viewport` / `_viewport_anchor` / `_card_fully_visible` already
  exist and express "what is on screen"; they may be reusable here, but note
  they operate on a *live* layout and the refresh path rebuilds it.
- `_recompose_column` (`:5874`) keeps the column shell and replaces its
  children, so it preserves `scroll_y` where a full `refresh_board` does not —
  worth examining as the cheaper path for a periodic refresh.

## Acceptance criteria

1. With auto-refresh enabled and a column wheel-scrolled away from the focused
   card, an auto-refresh tick must not discard the user's scroll position.
2. Focus restoration itself must keep working — the refresh must not leave focus
   on nothing, and the existing behaviour covered by
   `tests/test_board_empty_column_focus.py` (Case 8, `refresh_column` /
   `_refocus_card` falling back to column identity) must not regress.
3. Pin the fix with a headless Pilot test: enable auto-refresh (or invoke the
   tick directly), wheel-scroll a column, run the refresh, assert the scroll
   position survived. Prove the test fails before the fix.
