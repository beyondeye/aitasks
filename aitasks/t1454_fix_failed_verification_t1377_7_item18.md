---
priority: medium
effort: medium
depends: [t1377_5]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1243
followup_kind: verification_failure
created_at: 2026-08-07 13:08
updated_at: 2026-08-13 23:07
---

## Failed verification item from t1377_5

> [t1377_5] Add, edit and delete a column through the new dialog and confirm each still works as it did from the command palette

### Source

- **Manual-verification task:** `aitasks/t1377/t1377_7_manual_verification_column_features.md` (item #18)
- **Origin feature task:** t1377_5
- **Origin archived plan:** `aiplans/archived/p1377/p1377_5_board_column_management_dialog.md`

### Commits that introduced the failing behavior

- cf56fae48 feature: Add the board column management dialog (t1377_5)

### Files touched by those commits

- .aitask-scripts/board/aitask_board.py
- tests/test_board_column_dialog.py
- tests/test_board_move_command.py
- tests/test_board_work_report.py

### Diagnosis (from the verification run)

**The `Delete` and `Edit` buttons in `ColumnManageScreen` can never act.**

`action_delete` / `action_edit` (`.aitask-scripts/board/aitask_board.py:6469`,
`:6475`) resolve their target through `_focused_item()` (`:6411`), which reads
`self.screen.focused` and returns a value only when it is a
`ColumnManageItem`. But activating a `Button` — by click or by Enter — *is*
what gives that Button focus, so by the time `_btn_delete` / `_btn_edit`
(`:6564`, `:6560`) run, `focused` is the Button and `_focused_item()` is
always `None`.

Observed live (real `ait board` in a tmux pane, isolated fixture repo):
pressing `Delete` emits the toast `Select a column to delete` and removes
nothing; pressing `Edit` emits `Select a column to edit`.

**Delete has no other path in the dialog**, so column deletion via the new
dialog is impossible: `ColumnManageScreen.BINDINGS` (`:6340`) is only
`escape` / `shift+up` / `shift+down`, and `ColumnManageItem.on_key`
(`:6277`) handles `enter` alone (→ edit). Edit is still reachable via
`Enter` on a focused row, and `Add` / `Merge` work because neither needs a
focused item. Delete remains reachable from the Ctrl+P palette
(`action_delete_column`).

**Why the tests missed it:** `tests/test_board_column_dialog.py:741` focuses
a row and then calls `screen.action_delete()` *directly*, bypassing the
button press that steals the focus. A regression test must go through the
real entry point (press the button / post `Button.Pressed`).

**Suggested fix direction:** have the screen remember the last focused
`ColumnManageItem` (updated on row focus) and have `action_edit` /
`action_delete` fall back to it when `self.screen.focused` is one of the
dialog's own buttons — or give the dialog an explicit delete key binding on
the row. Whichever is chosen, add a button-driven test for both verbs.

### Next steps

Fix per the diagnosis above and add button-level regression coverage. This
task was auto-generated from a manual-verification failure in t1377_7
item #18.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:54Z.896ec2fa514cac9a3d200e5f from=t1794_9 from_verified=yes at=2026-09-22T06:09:54Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1454_fix_failed_verification_t1377_7_item18.md) cites stale line anchors: aitask_board.py:6469; symbols you name -> current module: ColumnManageScreen -> board_column_dialogs.py.
