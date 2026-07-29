---
Task: t1243_11_group_formation_and_block_moves.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_11 — Group formation and block moves

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_11_group_formation_and_block_moves.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — formation and removal write only `boardgroup`

K writes to join, 1 write (the `""` tombstone) to leave, all via
`reload_and_save_board_fields(fields=("boardgroup",))` — `fields` is required and
naming a non-layout key is what makes the write semantic; there is no
`semantic=True` bool. **No `boardidx` is touched and non-members are never
rewritten** — naming `boardgroup` alone is also what keeps a stale in-memory
index from overwriting a concurrent move. Neither operation has a gap or
compaction case — do not write those tests for them.

## Step 2 — generalise `_card_block`

From "card + its child-wrappers" to "header + each member's own block", so the
group moves as one and children stay adjacent to their parent.

## Step 3 — block moves

Lateral / to-edge: N writes, order preserved. Vertical past an adjacent unit: N
distinct indices below/above that unit's sort key — N writes, **neighbour
untouched**. Assign them contiguously since we are writing anyway
(opportunistic tidiness, never a repair pass). Bounded compaction via
`respace_column(col, stride=stride_for(N))` on a too-small interval.

Do **not** implement "rewrite the smaller side" — it dirties a file the user
never selected.

## Step 4 — coalesce on move

Same slug in the destination column is one group by derivation. Arriving members
get indices above the residents' maximum and render after them. Notify; do not
refuse. Collapse keys combine per t1243_10.

## Step 5 — `delete_column` tidy-up

Replace the `board_idx = 0` mass-tie with contiguous indices preserving relative
order and group runs.

## Verification

Exact changed-path sets for every operation; the neighbour block provably
untouched; at-gap / exhausted-gap / retry plus the **K = 1023/1024/1025** stride
boundary; reload round-trip (INV-R) after every operation.
