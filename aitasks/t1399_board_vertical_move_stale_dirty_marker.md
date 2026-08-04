---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-03 22:42
updated_at: 2026-08-04 09:44
---


## Origin

Spawned from t1243_5 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:8654-8663 — _swap_adjacent_cards reorders cards with move_child and never repaints them, so the dirty * marker that _move_task_vertical's write turns on (TaskManager._mark_written) does not appear on the moved card until the next full refresh. Pre-existing on the vertical axis; t1243_5 fixed the lateral and to-edge paths only, because touching the 184 ms vertical fast path buys no latency and adds risk.`
- `.aitask-scripts/board/aitask_board.py:7138-7147 — _column_widgets() issues four separate full-DOM class queries per call (~25 ms on a 200-card board, measured in t1243_4), three of which return empty in the normal kanban view. RESOLVED OUT OF THIS TASK: t1395 measured it at 0 calls on both move axes and proved it is a PLAIN-ARROW NAVIGATION cost, not a move-path one — the earlier "reached from the post-move refocus path via _card_fully_visible / _viewport_anchor" claim is false against current code. Now owned by t1403 (board_nav_column_widgets_query_cost). Do not address it here.`

## Diagnostic context

`TaskCard.compose` bakes the dirty `*` in at construction, reading
`manager.is_modified(...)`. Since t1243_4 the marker comes from
`TaskManager._mark_written` at the write site rather than from a per-keypress
`git status`, so a move flips the file to modified **in memory** — but only a
path that rebuilds the card renders the change.

- **Lateral / to-edge (fixed by t1243_5):** the transplant constructs a fresh
  `TaskCard`, so the marker is correct by construction. This is precisely why
  t1243_5 deviated from its own task file, which had specified `move_child` for
  the to-edge path — `move_child` preserves the widget and would have shipped
  this same defect on a third path.
- **Vertical (still broken):** `_swap_adjacent_cards` moves the existing widgets
  with `move_child` and calls only `apply_filter`, which sets `styles.display`
  and never recomposes. The card keeps its original render.

The marker is read at `TaskCard.compose` time only, so nothing repaints
mid-move; it heals on `r`, a view switch, a detail-screen return, or a commit —
all four full-scan sites verified present in t1243_4.

Not a regression from t1243_5: it predates that task and was left deliberately,
because the vertical axis is the measured fast path (184.1 ms baseline) and
t1243_5's target was lateral-only.

## Suggested fix

Repaint just the moved block after the swap — e.g. `card.refresh(recompose=True)`
on the moved card, or route the vertical path through t1243_5's
`_transplant_block` (which rebuilds the block and gets the marker right by
construction, at the cost of a prune+mount on a path that currently does neither).

**Measure before choosing.** The vertical axis is the fast path and its budget is
small; use `tests/test_board_movement.py` with `AITASK_BOARD_BENCH=1` and
**repeat the configuration** — a single run on this box produced a lateral
reading 500 ms outside the 5-run distribution (t1243_5, "Issues encountered").
A render-level assertion belongs in the test, not a `modified_files` check:
`tests/test_board_dom_transplant.py` has the idiom
(`card.query(".task-number").first().render().plain == "t9005 *"`).

The `_column_widgets()` bullet is **no longer part of this task** — t1395 disproved its move-path premise and t1403 now owns it on the navigation path. This task is only about the vertical dirty `*` marker.
