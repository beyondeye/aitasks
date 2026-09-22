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
boardidx: 106496
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:02Z.8083637aa51142872344eb0b from=t1794_9 from_verified=yes at=2026-09-22T06:09:02Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1348_board_work_report_drops_one_column_task.md) cites stale line anchors: aitask_board.py:1050.
