---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui]
gates: [risk_evaluated]
anchor: 1243
followup_kind: upstream_defect
created_at: 2026-07-29 21:36
updated_at: 2026-08-13 23:06
boardidx: 97280
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:59Z.9f019017dfd72065e2674e8c from=t1794_9 from_verified=yes at=2026-09-22T06:08:59Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1338_work_report_drops_unparseable_task_filenames.md) cites stale line anchors: aitask_board.py:7271-7272; symbols you name -> current module: TaskCard -> board_widgets.py.
