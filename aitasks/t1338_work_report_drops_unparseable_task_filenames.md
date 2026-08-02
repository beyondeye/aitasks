---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-29 21:36
updated_at: 2026-07-29 21:36
boardidx: 720
---

## Origin

Spawned from t1314 during Step 8b review. t1314's full-suite run surfaced this
as a pre-existing failure unrelated to its own change (verified by restoring the
pristine `HEAD` copy of `aitask_board.py` and re-running — it failed
identically).

## Upstream defect

- `tests/test_board_work_report.py:483` — `test_hidden_cards_still_listed`
  asserts `sl.option_count == len(col_tasks)` against the **live** task tree, so
  any task file the board can load but `TaskCard._parse_filename` cannot parse
  makes the suite fail (currently `AssertionError: 140 != 141`).
- `.aitask-scripts/board/aitask_board.py:7271-7272` — `action_work_report`
  silently drops tasks whose filename yields no `task_num` (`if not task_num:
  continue`), so a work report is generated missing those tasks with no
  notification to the user.

## Diagnostic context

The test picks `candidates[0]` — the first *populated* column from
`app._work_report_columns()`, which puts the `unordered` ("Unsorted / Inbox")
pseudo-column first whenever it has tasks. That column currently holds 141
tasks, and `aitasks/t_refresh_codeagent_suite_default_model_expectations.md`
carries a `t_` prefix with **no numeric id**. `TaskCard._parse_filename` returns
no `task_num` for it, so `action_work_report`'s `continue` drops it from
`entries` — the `SelectionList` is built with 140 options for a 141-task
column, and the equality assertion fails.

Reproduced directly:

```
unordered total: 141 dropped: 1 ['t_refresh_codeagent_suite_default_model_expectations.md']
```

Two independent problems are tangled here, and they want separate decisions:

1. **The silent drop is a user-facing data-loss bug.** A work report quietly
   omits a task that is plainly visible on the board. Whatever the resolution
   for unnumbered files, the user should be told (notification listing the
   skipped filenames) rather than getting a silently short report.
2. **The test is live-data dependent.** Asserting an exact count against
   whatever happens to be in `aitasks/` means unrelated task-tree state can
   break an unrelated suite — as it did here, costing a full 13-minute run to
   diagnose. This is the same class as the fixture-vs-live-tree concern.

Note the malformed file itself may simply be a mistake worth renaming, but
renaming it only hides both defects — the code path and the test would still
break for the next unnumbered file.

## Suggested fix

- `action_work_report`: collect the dropped filenames instead of discarding
  them, and `self.notify(...)` a warning naming them (or include them with a
  synthesized label so the report is complete). Decide explicitly whether an
  unnumbered task belongs in a work report at all — and if not, say so to the
  user.
- `test_hidden_cards_still_listed`: build the assertion over a **fixture** tree
  rather than the live one, or assert the documented relationship
  (`option_count == len([t for t in col_tasks if parses(t)])`) plus a separate
  test that pins the notification for the dropped ones. An exact live count is
  not a stable contract.
