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
boardidx: 117760
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:09Z.450ecd7bdacad836684096f4 from=t1794_9 from_verified=yes at=2026-09-22T06:09:09Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1364_warn_on_unparseable_task_filenames.md) cites stale line anchors: aitask_board.py:7271; symbols you name -> current module: TaskCard -> board_widgets.py, TaskManager -> board_task_manager.py.
