---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, test]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-31 06:43
updated_at: 2026-07-31 06:43
---

## Origin

Spawned from t1216_4 during Step 8b review.

## Upstream defect

- `tests/test_board_work_report.py:483` — `test_hidden_cards_still_listed`
  asserts `sl.option_count == len(col_tasks)` against the **live** task tree,
  but `action_work_report` (`aitask_board.py:7271`) deliberately skips any task
  whose filename `TaskCard._parse_filename` cannot parse (`if not task_num:
  continue`). A single malformed task file anywhere in the first populated
  work-report column therefore fails the whole Python suite. Currently
  triggered by `aitasks/t_refresh_codeagent_suite_default_model_expectations.md`
  (created 2026-07-29), whose filename carries no task number.

## Diagnostic context

Surfaced while verifying t1216_4 (shadow spawn ported to `ait monitor`). The
full suite reported `2951 tests, 1 failure` with
`AssertionError: 150 != 151`. t1216_4 touches only the monitor/shadow modules
and `agent_launch_utils`; it does not touch `aitask_board.py`, so the failure
could not originate there.

Reproduced independently of the test, from live data alone:

```
column tasks: 151
kept: 150  dropped(unparseable): 1
   DROPPED: t_refresh_codeagent_suite_default_model_expectations.md
duplicate ids: []
```

i.e. `manager.get_column_tasks("unordered")` returns 151 rows while the
`SelectionList` built by `action_work_report` legitimately carries 150. The
production skip is correct — a task with no id cannot be passed to the work
report as `--tasks <id>` — so the defect is in the test's equality assumption,
not in the board.

Two things are worth deciding separately:

1. **The test** couples a strict equality to whatever happens to be on disk.
   Any malformed task file, now or later, breaks an unrelated suite run and
   costs a diagnosis cycle.
2. **The data artifact** — a task file whose filename has no task number. Worth
   checking which creation path produced it, and whether the board/`ait ls`
   surfaces should warn about unparseable task filenames rather than silently
   dropping them.

## Suggested fix

Make the assertion mirror the production filter: compare `sl.option_count`
against the number of column tasks whose filename actually parses (or assert
`<=` plus an explicit parse-failure count), so the test measures the
"search-hidden cards are still listed" property it is named for rather than the
tidiness of the live task tree. Separately, decide whether the numberless task
file should be renamed/repaired and whether unparseable filenames deserve a
visible warning.
