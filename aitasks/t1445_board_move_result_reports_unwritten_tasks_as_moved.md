---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, board_columns]
gates: [risk_evaluated]
anchor: 1243
followup_kind: upstream_defect
created_at: 2026-08-06 15:24
updated_at: 2026-08-13 23:07
---

## Origin

Spawned from t1377_4 during Step 8b review.

## Upstream defect

- `aitask_board.py:1839 (move_tasks_to_column)` — counts a task as moved when
  `reload_and_save_board_fields` silently skipped its save (failed reload), so
  `MoveResult.moved` can name a task that was never written. `merge_columns` now
  compensates by verifying against disk, but every other consumer of the movement API
  (`move_task_to_column` from the board / minimonitor move actions, `delete_column`,
  `move_task_to_edge`, `reposition_task`, `update_column`) still trusts it.
  `delete_column` has the same drain-and-strand shape as the bug fixed in t1377_4.

## Diagnostic context

`Task.reload_and_save_board_fields` re-reads the file before writing and **returns
early, raising nothing**, when that reload fails:

```python
snapshot = {k: self.metadata.get(k) for k in keys}
if not self.load():
    return                      # file gone OR unreadable — no exception
...
self.save()
```

`Task.load()` returns `False` for **any** read exception — not only a missing file.
A permission error or an undecodable file takes the same path, and on failure it also
wipes `self.metadata`, so `board_col` then reads as the `unordered` default.

`move_tasks_to_column` calls `_mark_written(task)` and appends to `moved` regardless:

```python
task.reload_and_save_board_fields(("boardcol", "boardidx"))
self._mark_written(task)
moved.append(task.filename)
```

So `MoveResult.moved` can name a task whose file still holds its **old** `boardcol`.

Why this matters beyond a false report: `delete_column` drains a column and then
removes it. If a member silently failed to write, the file keeps `boardcol: <deleted>`
while the column disappears from `columns` / `column_order`, leaving the task rendered
by no column at all. That is exactly the orphan t1377_4 had to defend against, and the
same shape exists here.

t1377_4 fixed it only inside `merge_columns`, via `_classify_members` — it re-reads
every member from disk after each source's move (raising or not) and drains a source
only when every member is confirmed landed. It also added `Task.load_ok`,
`TaskManager.unreadable_files` and `_revalidate_unreadable()` to track files that exist
but cannot be read. Those primitives are already in place and reusable.

## Suggested fix

Make the lower level report the skip rather than having each caller re-derive it:
have `reload_and_save_board_fields` return whether it actually saved (it already
computes this), and have `move_tasks_to_column` exclude non-written tasks from
`MoveResult.moved` — likely via a new `MoveResult` field so existing consumers are not
silently re-interpreted. Then audit `delete_column` for the drain-and-strand case and
reuse `unreadable_files` as the "cannot verify" guard.

Note `tests/test_board_persistence_seam.py::EXPECTED_CALL_SITES` is an AST-parsed
frozen table over `reload_and_save_board_fields` call sites — changing call sites
requires editing it in the same commit. `tests/test_board_column_manage.py`
(`SilentSkipTests`) shows how to drive the no-exception skip deterministically.
