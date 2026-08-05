---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, board_columns, python]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-05 15:53
updated_at: 2026-08-05 15:53
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
