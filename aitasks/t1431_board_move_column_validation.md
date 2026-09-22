---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, board_columns, python]
gates: [risk_evaluated]
anchor: 1243
followup_kind: risk_mitigation
created_at: 2026-08-05 15:53
updated_at: 2026-08-13 23:07
---

## Origin

Risk-mitigation ("after") follow-up for t1377_1, created at Step 8d after implementation landed.

## Risk addressed

code-health — the board's own move path keeps the unvalidated-column hole this
task closes in the CLI.

From p1377_1's `## Risk` section:

> The same unvalidated-column hole remains in the board's own
> `TaskManager.move_tasks_to_column`, so the framework would be left with two
> different validation stances for one field · severity: low ·
> → mitigation: board_move_column_validation

## Goal

t1377_1 added column-id validation to `ait update --boardcol` and to the new
headless seam (`lib/board_columns.move_task_to_column` refuses `unknown_column`).
The board's own in-process move path was left as it was, so the framework now
holds **two different stances** on the same field:

| Path | Validates `boardcol`? |
|---|---|
| `ait update --boardcol` | yes (t1377_1) |
| `lib/board_columns.move_task_to_column` | yes (t1377_1) |
| `TaskManager.move_task_to_column` / `move_tasks_to_column` | **no** |

`aitask_board.py:1570-1605`: `move_tasks_to_column` resolves the task names via
`_resolve_parents` and then writes `task.board_col = new_col` verbatim. Nothing
inspects `new_col` against the configured vocabulary, and
`Task.reload_and_save_board_fields` validates only *key names*, never values —
so an arbitrary string reaches disk and produces a task that renders in no
column at all.

In practice the board's own UI only ever passes a real column id (the pickers
are built from `manager.columns`), so this is latent rather than actively
breaking. It becomes reachable as soon as a caller supplies a column id that did
not come from the picker — which is exactly what the t1377 chain is adding.

Validate `new_col` in `move_task_to_column` / `move_tasks_to_column` against the
shared `lib/board_columns` vocabulary and refuse `unknown_column` through the
**existing** `MoveResult.refused` channel, so board and CLI hold one stance.

## Notes

- `lib/board_columns.load_columns(root)` returns `(configured_ids, titles)`
  where `titles` already includes the synthetic `unordered` — so
  `col_id in titles` is the single membership test, exactly as
  `move_task_to_column` uses it. Reuse that; do not re-derive the vocabulary.
- `MoveResult` (`aitask_board.py:998`) already carries
  `refused: tuple[tuple[str, str], ...]` and documents that a non-empty
  `refused` means **nothing** was written. The batch move already resolves the
  whole batch before its first write, so adding a column check at the top
  preserves that all-or-nothing property.
- `tests/test_board_persistence_seam.py`'s AST-parsed `EXPECTED_CALL_SITES` is a
  frozen table sorted by line number. Adding a guard clause does not add a
  `reload_and_save_board_fields` call site, but do not let a refactor reorder
  the existing ones.
- Add a negative control: a test that the guard actually refuses (revert the
  guard and confirm the test fails), not only that valid moves still pass.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:41Z.41f761b5015be2af82cfa54b from=t1794_9 from_verified=yes at=2026-09-22T06:09:41Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1431_board_move_column_validation.md) cites stale line anchors: aitask_board.py:1570-1605, aitask_board.py:998; symbols you name -> current module: TaskManager -> board_task_manager.py.
