---
Task: t1243_3_gap_indexing.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_3 — Gap indexing

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_3_gap_indexing.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — `lib/board_ordering.py`

Pure module, no Textual imports, signatures as in the task file
(`index_for_append`, `index_for_prepend`, `index_between`, `indices_between`,
`respace_indices(n, stride)`, `stride_for(k)`). Unit-test it standalone first —
it is the piece that must be provably correct before anything calls it.

## Step 2 — manager API

Add `move_task_to_column`, `reposition_task`, `move_task_to_edge`,
`move_tasks_to_column`; rename `normalize_indices` → `respace_column(col,
stride)`. Route **every** index read through `normalize_board_idx` — this fixes
the raw-`max()` `TypeError` in `move_task_col` and the raw `±10` arithmetic in
`_move_task_to_extreme` at the same time.

## Step 3 — rewire the four actions

Remove all four `normalize_indices` calls from the movement paths. Retire
`swap_tasks` from `_move_task_vertical` in favour of `reposition_task` (1 write,
and it fixes the equal-index no-op).

## Step 4 — compaction

Only on `None` from `index_between` / `indices_between`: one
`respace_column(col, stride=stride_for(K))`, then retry. Assert in code (not just
in tests) that the retry cannot fail — post-respace gaps are `stride` wide.

## Step 5 — flip the t1243_1 table

Edit the characterization table deliberately in this commit. A silent pass means
the table was not discriminating.

## Verification

Exact write counts **and** changed-path sets for healthy / at-bound /
over-bound; multi-hop transit dirties nothing outside the moved task; legacy
`10`-spaced column self-heals once; quoted-`boardidx` column no longer raises.

## Notes for sibling tasks

Record the replacement API surface here for **t1210_5**: `move_task_to_column`,
`move_tasks_to_column`, `reposition_task`, `move_task_to_edge`, and the fact that
`respace_column` must never be called from a move path.
