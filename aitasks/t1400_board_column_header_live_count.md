---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
anchor: 1243
followup_kind: risk_mitigation
created_at: 2026-08-03 22:43
updated_at: 2026-08-13 23:07
boardidx: 5120
---

## Origin

Risk-mitigation ("after") follow-up for t1243_5, created at Step 8d after
implementation landed.

## Risk addressed

> Two invariants the recompose used to maintain for free — `ColumnHeader.task_count`
> and the dirty `*` — become explicit obligations of the movement path, and a
> future third one could be missed the same way · severity: medium

`addresses`: code-health — recompose-maintained invariants become explicit
caller obligations.

## Goal

Make `ColumnHeader` derive its task count from the manager at render time
instead of baking it in at construction, so no movement path has to remember to
call `_sync_header_count`.

Today (`.aitask-scripts/board/aitask_board.py`):

- `ColumnHeader.__init__` stores `task_count`, and `compose` renders
  `f"{self.col_title} ({self.task_count})"`. The value is frozen at construction.
- `KanbanColumn.compose` computes it via
  `len(self.manager.get_column_tasks(self.col_id))`.
- Before t1243_5 every move recomposed the column, so the header was rebuilt for
  free. t1243_5's transplant does not, so it added `KanbanApp._sync_header_count`,
  called explicitly from the lateral path (and deliberately not from the to-edge
  path, where the count cannot change).

That is a remembered step, and the next in-place path that changes a column's
membership — **t1243_11's group block moves are the obvious candidate** — has to
remember it too or ship a stale header.

## Suggested direction

Have the header read the count from the manager when it renders (a Textual
reactive, or simply computing it in `compose` from `col_id` + manager) so the
only thing a caller must do is trigger a repaint. Then `_sync_header_count`
either disappears or shrinks to that repaint.

**Verify at render level, not on the attribute** —
`tests/test_board_dom_transplant.py::LateralTransplantTests::test_both_column_headers_repaint_their_counts`
already asserts the rendered header text and pairs it with an untouched-column
control; keep that contract and make it pass without the explicit sync call.

Do not regress: a same-column move must still not disturb the count, and an
untouched column's header must not be rewritten.
