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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:54Z.744237a64d76268b810da1e4 from=t1794_9 from_verified=yes at=2026-09-22T06:08:54Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1330_guard_numberless_task_filenames.md) cites stale line anchors: aitask_board.py:7258-7262; symbols you name -> current module: TaskCard -> board_widgets.py.
