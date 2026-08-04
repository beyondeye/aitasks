---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_board, tui, tmux, python]
gates: [risk_evaluated]
anchor: 1248
created_at: 2026-07-26 19:19
updated_at: 2026-07-26 19:19
boardidx: 40960
---

## Origin

Residual left open by t1248 (board column scroll jump). t1248 fixed the *scroll*
consequence of a stray cursor key: the column no longer teleports. It did not
address the *selection* consequence, and this task tracks that.

## Problem

Inside tmux, wheel-scrolling a board column can deliver spurious `up` / `down`
cursor keys to `ait board` (tmux's alternate-screen wheel → cursor-key
emulation). The board binds those with `priority=True`
(`.aitask-scripts/board/aitask_board.py:5411-5414`), so each one runs
`action_nav_up` / `action_nav_down` and **moves the focused card**.

After t1248 that focus move is visually harmless — the cursor re-anchors to a
card already on screen instead of dragging the view back. But the selection has
still changed without the user asking. A keystroke issued immediately afterwards
acts on the wrong task:

- `enter` opens a different task's detail;
- `shift+up` / `shift+down` reorders a different task;
- any column-move or archive shortcut targets a different task.

The newly focused card does carry the cyan focus border, so this is not silent —
but a user who was scrolling, not navigating, has no reason to re-check which
card is selected before pressing the next key.

## Direction (evaluate, do not adopt blindly)

t1248's plan sketched a **recency guard**: ignore `nav_up` / `nav_down` that
arrive within ~200 ms of a wheel event on the same column. Known constraint from
that investigation: `VerticalScroll._on_mouse_scroll_down` calls `event.stop()`
when it scrolls, so the App never sees the wheel event — the timestamp has to be
taken either in a small `_on_mouse_scroll_down` override on the four column
classes (`KanbanColumn`, `InFlightColumn`, `TopicColumn`, `TrailColumn`, each
calling `super()`), or in a `Screen._forward_event` hook.

Weigh that against the cost: a recency guard also suppresses *genuine* keyboard
navigation for that window, which is a real UX regression for someone who
scrolls and then immediately navigates. Alternatives worth considering before
committing to it — requiring a second keypress before a destructive action when
focus changed without an explicit nav intent, or confirming destructive
shortcuts when the focus moved within the last N ms.

## Acceptance criteria

1. Decide, with reasons recorded, whether the board should suppress nav keys
   during an active wheel scroll or defend at the destructive-action sites
   instead. A documented "no change, here is why" is an acceptable outcome.
2. If a guard is implemented, genuine keyboard navigation immediately after a
   wheel scroll must not be swallowed — pin that with a test.
3. Any guard must be pinned by a headless Pilot test in the style of
   `tests/test_board_scroll_focus_jump.py` (wheel events posted through
   `app.screen._forward_event`; note that priority-bound keys are consumed at
   App level and are invisible at `Screen._forward_event`).
