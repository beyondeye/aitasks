---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui]
gates: [risk_evaluated]
anchor: 1213
created_at: 2026-07-28 11:55
updated_at: 2026-07-28 11:55
boardidx: 62464
---

## Problem

In `ait board`, switching **into** the In-Flight view (`i`) and switching **back
out** of it (`a` / `l` / `f`) both leave the board with **no focused widget** —
nothing is highlighted anywhere on screen until the user presses `Escape` or an
arrow key. When the user then presses an arrow, focus restarts at the board's
default anchor (leftmost column, first card) rather than the card they were on,
so their place is lost across the round trip.

Found while manually verifying t1213 (the t1209 focusable-empty-columns
follow-up). It is **pre-existing** and orthogonal to t1209 — that task only ever
promised a focus anchor for *board* columns — but it lives in exactly the seam
t1209 built, so it is recorded here rather than reopened there.

## Reproduction (verified in tmux against the real TUI)

Driven against a sandbox `TASK_DIR` (`Left(2) | Empty(0) | Right(1)`), reading
focus from the rendered pane: a focused `TaskCard` draws a `╔═╗` border, a
focused placeholder carries the `$primary 30%` accent background.

1. Focus a card in the rightmost populated column (`t3 charlie` → `╔═╗`).
2. Press `i` (In-Flight view). → **0** focused rows in the pane capture.
3. Press `a` (All view). → still **0** focused rows.
4. Press `Down`. → focus appears on `t1 alpha`, the first card of the *leftmost*
   column — neither the card nor even the column the user came from.

Both legs reproduce whether the in-flight lanes are **empty** or **populated**:
with a real `InFlightTaskCard` on screen (`Agent can continue (1)`), entering the
view still left it unfocused (plain `┌─┐` border). Pressing `Escape` inside the
view does focus the in-flight card, so the view is not keyboard-dead — this is a
lost-place / no-visible-cursor annoyance, not a lockup.

**Negative control — this is In-Flight-specific.** The same round trip through
By-Topic (`y` → `a`) and Locked (`l` → `a`) *preserves* focus. Their cards carry
real board column ids, so the refocus capture below still resolves after the
rebuild.

## Root cause (read from source)

`refresh_board` captures the fallback column before teardown
(`.aitask-scripts/board/aitask_board.py:6099`):

```python
refocus_col_id = refocus_col_id or self._get_focused_col_id() or ""
```

and `_queue_refocus` → `_refocus_column` → `_column_focus_target` returns `None`
when that column id does not exist in the rebuilt DOM — a **silent no-op with no
final fallback**.

The In-Flight view uses a separate column-id namespace: `InFlightColumn.col_id =
f"inflight-{group}"` and its cards are built as
`InFlightTaskCard(item, ..., column_id=self.col_id)` (~1812-1831). So:

- **Entering:** the capture is a board id (`zz_right`), which no longer exists
  among the mounted `inflight-*` columns → no-op → focus dropped.
- **Leaving:** nothing is focused, so the capture is `""` → `_queue_refocus` has
  nothing to queue → focus stays dropped.

Related: an in-flight lane with no items yields
`Static("No tasks", classes="inflight-empty")` (~1829), which is **not
focusable** — the in-flight analogue of the `EmptyColumnPlaceholder` t1209 added
for board columns is missing.

## Suggested directions (not prescriptive — decide at plan time)

- A **final fallback** in the refocus tail: when the queued column id resolves to
  no target in the rebuilt DOM, fall back to the board's default anchor (the
  leftmost-first sweep `action_focus_board` already implements). This alone fixes
  both legs and is view-agnostic — it would also cover any future view that
  introduces its own column-id namespace.
- Optionally, remember the last *board* column id across a view switch so
  returning to All/Locked/Free restores the user's column rather than the
  leftmost one.
- Optionally, give the empty in-flight lane a focusable placeholder for parity
  with `EmptyColumnPlaceholder`.

Prefer the structural fix (fallback in the shared refocus tail) over patching
`_set_base_filter` per view.

## Acceptance criteria

- Entering the In-Flight view from a focused board card leaves **some** widget
  focused (an in-flight card when one exists; a sensible anchor when the lanes
  are empty).
- Returning from In-Flight to All/Locked/Free leaves a focused card, without the
  user pressing `Escape`.
- By-Topic and Locked round trips keep their current (correct) behaviour —
  regression guard.
- Covered by a Textual-Pilot case alongside
  `tests/test_board_empty_column_focus.py`, asserting `app.screen.focused` is not
  `None` after each leg; prove the new case fails against the unfixed source
  before trusting it.
