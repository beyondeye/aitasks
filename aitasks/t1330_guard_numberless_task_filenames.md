---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, backend]
gates: [risk_evaluated]
anchor: 1243
followup_kind: upstream_defect
created_at: 2026-07-29 14:03
updated_at: 2026-08-13 23:06
boardidx: 89088
---

## Origin

Spawned from t1243_2 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_create.sh:1809` — `filename="t${task_num}_${task_name}.md"`
  has no guard that `task_num` is non-empty, so an empty id silently produces a
  numberless task file (`t_<slug>.md`). One exists in the live tree:
  `aitasks/t_refresh_codeagent_suite_default_model_expectations.md`, committed
  2026-07-29 09:55 in `9e7f18326` ("ait: Revert t1311 to Ready (risk mitigation
  pending)") — i.e. produced by the risk-mitigation "before" creation path.
- `.aitask-scripts/board/aitask_board.py:7258-7262` — the work-report entries loop
  silently `continue`s past a task whose filename `TaskCard._parse_filename`
  cannot parse, so `WorkReportTaskSelectScreen` under-reports versus
  `get_column_tasks`. `tests/test_board_work_report.py` asserts the two are equal,
  so a single unparseable file fails the suite with no indication of which file or
  why.

## Diagnostic context

Found while running the full Python suite for t1243_2. The suite reported exactly
one failure:

    FAIL: test_hidden_cards_still_listed
    (test_board_work_report.WorkReportFullColumnUnderSearchTests)
    AssertionError: 133 != 134

The test picks the first populated column from `_work_report_columns()`, which is
`unordered` (134 tasks in the live tree). Probing the live tree confirmed exactly
one task there whose filename does not parse:

    unordered: 134 tasks; unparseable=['t_refresh_codeagent_suite_default_model_expectations.md']

The two defects compose: (1) lets a numberless file be created, (2) turns its mere
existence into an opaque suite failure. t1243_2 did not cause it — the file was
committed at 09:55, before any t1243_2 code edit, and `_parse_filename`,
`get_column_tasks` and the work-report path are untouched by that task's diff.

## Suggested fix

In `aitask_create.sh`, fail loudly when `task_num` is empty rather than emitting
`t_<slug>.md` (the numbering step should already have errored — find why it did
not, in the risk-mitigation "before" creation path). Separately, decide the board's
contract for an unparseable filename: either surface it (notify / log which file
was skipped) or exclude it from `get_column_tasks` so the two counts agree by
construction. Repairing the existing live file needs coordination — it belongs to
t1311's in-flight work.
