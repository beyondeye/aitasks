---
priority: medium
effort: low
depends: []
issue_type: bug
status: Folded
labels: [test]
gates: [risk_evaluated]
folded_into: 1354
anchor: 1111
created_at: 2026-07-30 08:12
updated_at: 2026-07-31 07:41
boardidx: 800
---

## Origin

Spawned from t1216_3 during Step 8b review. It made that task's full-suite run
red for a reason unrelated to any code change in it.

## Upstream defect

- `tests/test_board_work_report.py:483 — WorkReportFullColumnUnderSearchTests::test_hidden_cards_still_listed asserts sl.option_count == len(col_tasks) against the LIVE aitasks/ tree, so any concurrent task-file change during the ~12-minute suite makes it fail (observed 145 != 146).`

## Diagnostic context

The test snapshots the live board column with
`app.manager.get_column_tasks(col_id)`, then applies a search filter, opens the
work-report screens, and asserts the resulting `SelectionList.option_count`
equals the length of that earlier snapshot. It even calls `skipTest` when the
live tree has no populated column, so the dependence on real data is
acknowledged in the test itself.

Observed during t1216_3: `AssertionError: 145 != 146` in a 2788-test run lasting
746s. During that window the t1216_3 workflow itself committed task-status and
gate-ledger changes to `aitasks/`, and other sessions may have too. Any task
appearing or moving column mid-run shifts the count.

Established as independent of t1216_3 rather than assumed: importing
`aitask_board` loads none of the modules that task changed
(`monitor.monitor_app`, `monitor.monitor_shared`, `monitor.minimonitor_app`) —
verified by inspecting `sys.modules` after the import.

## Impact

Every task that runs `bash tests/run_all_python_tests.sh` can hit a red suite
for no reason connected to its own change. That trains agents and humans to
discount the suite verdict, which is the real cost — the framework's own
convention is to read the last line as authoritative.

## Suggested fix

Decouple the assertion from live data: build the board over a fixture task tree
(as the other board tests do), or re-read the column immediately before the
comparison so both sides come from the same moment. Do not simply widen the
assertion to a range — that would keep the nondeterminism and hide real
regressions.
