---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
anchor: 1326
created_at: 2026-07-30 10:31
updated_at: 2026-07-30 10:31
boardidx: 102400
---

## Problem

`WorkReportTaskSelectScreen` lists **one fewer task than the column contains**,
so exactly one task per column is silently unselectable when drafting a work
report. The user is never offered it and never learns it was omitted.

Reproduced deterministically (twice, identical numbers) against a live board:

```
tests/test_board_work_report.py:483
AssertionError: 147 != 148
```

`test_board_work_report.py::WorkReportFullColumnUnderSearchTests::test_hidden_cards_still_listed`
asserts `sl.option_count == len(col_tasks)`, where `col_tasks` comes from
`app.manager.get_column_tasks(col_id)` and `sl` is the screen's `SelectionList`.

## Why this is filed separately

Surfaced while implementing t1326 (cross-repo agent marks), but unrelated to it:

- The board imports nothing t1326 touched — verified by grep against
  `aitask_board.py` and `test_board_work_report.py` for `monitor_shared`,
  `agent_marks`, `minimonitor_app`, `monitor_app`: no hits.
- The assertion is a pure task-count comparison with no monitor involvement.
- It is the only red test in the full Python suite, and was already red before
  t1326's changes.

## Where to look

- `WorkReportTaskSelectScreen` and `_work_report_columns()` in
  `.aitask-scripts/board/aitask_board.py`
- `KanbanManager.get_column_tasks()` (`aitask_board.py:1050`) — the count the
  screen is measured against; note its documented normalisation and tie-breaking

The off-by-one is stable rather than a race, which points at a filter or guard in
the screen excluding one task category that the column query includes, rather
than at a timing gap between the two reads.

## Acceptance criteria

- [ ] Identify which task is dropped and why (a status? a lock? a boardidx tie?
      an off-by-one slice?) — name the mechanism, do not merely make the count match
- [ ] `test_hidden_cards_still_listed` passes
- [ ] A regression test pins the specific dropped-task condition, not only the
      aggregate count, so the same class of omission cannot silently return
- [ ] Full Python suite is green (this is currently its only failure)
