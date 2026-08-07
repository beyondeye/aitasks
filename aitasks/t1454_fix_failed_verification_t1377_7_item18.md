---
priority: medium
effort: medium
depends: [1377_5]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1243
created_at: 2026-08-07 13:08
updated_at: 2026-08-07 13:08
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
