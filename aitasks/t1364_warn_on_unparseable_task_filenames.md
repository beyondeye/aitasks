---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [ui, board]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-31 17:58
updated_at: 2026-07-31 17:58
boardidx: 113664
---

## Origin

Surfaced at Step 8b of t1354_1 (board fixture harness). t1352 raised two
separate questions; t1354_1 fixed the **test** side and deliberately left the
**product** side for its own task, per the parent plan's recommendation:

> Decide whether an unparseable task filename should produce a visible warning
> in the board / `ait ls` rather than being silently dropped. This is a product
> decision, not a test fix.

## Current behaviour

`TaskCard._parse_filename` returns no task number for a file whose name carries
no id (e.g. `t_refresh_codeagent_suite_default_model_expectations.md`, created
2026-07-29). Consumers then skip it silently:

- `aitask_board.py:7271` — `action_work_report` does `if not task_num: continue`.
  This skip is **correct on its own terms**: a task with no id cannot be passed
  to the work report as `--tasks <id>`.
- The file still loads into `TaskManager.task_datas` and occupies a board
  column, so the board shows a card the work report cannot act on.

The mismatch cost a full diagnosis cycle in t1352 (`150 != 151`) because
nothing anywhere said a file had been dropped.

## The question to decide

Should an unparseable task filename be **visible** rather than silently
dropped? Options worth weighing:

1. A one-line notice in the board (e.g. on the work-report flow, or a startup
   toast) naming the offending file(s).
2. A warning line from `ait ls`.
3. A `ait doctor`-style check rather than a per-run warning.
4. Validation at creation time so the file can never be written — note the
   real one was produced by some creation path that should be identified.
5. Decide the current silence is correct and document it.

Prefer whichever keeps the common path quiet; a warning that fires on every
board boot would be worse than the current silence.

## Key files

- `.aitask-scripts/board/aitask_board.py` — `TaskCard._parse_filename`,
  `action_work_report` (~:7271), `TaskManager.load_tasks` (~:925)
- `.aitask-scripts/aitask_ls.sh`
- `aitasks/t_refresh_codeagent_suite_default_model_expectations.md` — the live
  instance; worth tracing which creation path produced it.

## Notes

`tests/test_board_work_report.py` now *pins* the drop behaviour: its fixture
keeps a deliberately numberless `t_unparseable.md` in the column under test and
asserts `option_count != len(column_tasks)`. Any change here must update that
test intentionally rather than incidentally.
