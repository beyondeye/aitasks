---
priority: low
effort: low
depends: []
issue_type: performance
status: Ready
labels: [aitask_board, python, script-performance]
anchor: 1243
created_at: 2026-08-02 13:08
updated_at: 2026-08-02 13:08
boardidx: 3072
---

## Context

Follow-up from **t1243_3** (`gap_indexing`), raised at its Step-8 review and
deferred there by explicit user disposition — the behaviour is correct, only the
index arithmetic is superlinear, so it did not warrant reopening a landed and
fully-tested change.

`TaskManager.move_tasks_to_column` (`.aitask-scripts/board/aitask_board.py:1426-1434`)
computes each task's destination index by re-scanning the whole destination
column inside the loop:

```python
indices = self._column_indices(new_col)          # N entries
for task in tasks:                               # K tasks
    task.board_idx = board_ordering.index_for_append(indices)
    indices.append(task.board_idx)
    ...
```

`index_for_append` (`.aitask-scripts/lib/board_ordering.py`) does
`list(indices)` followed by `max(values)`, so each iteration is O(N + i) and the
loop is **O(K x (N + K))** in total.

The work is redundant: the value appended each round is by construction the new
maximum, so after the first index `M = max(existing) + STEP` every subsequent
value is exactly `M + i * STEP`. No re-scan is needed.

**Not currently reachable at damaging scale.** Today the only caller is
`move_task_to_column`, i.e. K = 1. The consumers that pass a large K are
**t1243_7** (`m` — move marked tasks to a column) and **t1210_5** (`M` — move a
whole By-Trail wave), neither of which has landed. Fixing it before those ship
keeps the cost linear from their first use.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `TaskManager.move_tasks_to_column`.

## Implementation plan

Compute the base index once and increment:

```python
        start = board_ordering.index_for_append(self._column_indices(new_col))
        moved = []
        for i, task in enumerate(tasks):
            task.board_col = new_col
            task.board_idx = start + i * board_ordering.STEP
            task.reload_and_save_board_fields(("boardcol", "boardidx"))
            moved.append(task.filename)
```

This must be **exactly behaviour-preserving**: same indices, same values, same
write count, same input ordering. It is an arithmetic simplification, not a
semantic change.

Consider whether the batch stride belongs in `lib/board_ordering.py` as a named
helper (e.g. `indices_for_append_run(indices, k)`) rather than open-coded
arithmetic in the manager — the module is the declared arithmetic home for this
family, and t1243_11's block moves will want the same run.

## Verification

- `tests/test_board_manager_moves.py` must pass **unedited**. Its happy-path
  cases already pin the exact resulting indices
  (`test_k_tasks_land_in_input_order_with_k_writes`,
  `test_append_only_batch_never_compacts` — the latter asserts
  `[10 + i * STEP for i in range(1, 6)]`), the input ordering, the write count,
  and that the batch never compacts. An unedited pass is the proof that the
  optimization changed nothing observable; **if any of those assertions move,
  stop** — that is a real behavioural delta, not a value to update.
- `tests/test_board_movement.py`'s `FLIP_TABLE` must also pass unedited.
- Add a scaling assertion so the regression cannot return silently: spy on
  `board_ordering.index_for_append` and assert it is called **once** per
  `move_tasks_to_column` call regardless of K (a call-count guard is stable,
  whereas a wall-clock timing assertion would be flaky in the shared suite).
- `bash tests/run_all_python_tests.sh` — read only the last line for the verdict.
