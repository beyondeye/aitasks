---
Task: t1243_2_board_field_persistence_seam.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_2 — Board field persistence seam

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_2_board_field_persistence_seam.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — rewrite the seam

Replace the hardcoded `boardcol`/`boardidx` snapshot in
`Task.reload_and_save_board_fields` with a loop over `BOARD_KEYS`, plus a
`semantic: bool = False` parameter that calls `self._update_timestamp()` before
`save()`. The exact body is in the task file.

Two details that carry the contract:

- `if v is not None` preserves an empty-string tombstone while never inventing a
  key that was genuinely absent;
- **no existing call site changes** — layout moves stay `semantic=False` and
  timestamp-neutral.

## Step 2 — retire the dead attribute

`Task._BOARD_KEYS = BOARD_KEYS` is assigned and never read. Either delete it or
make the new loop read it — leave no unread duplicate.

## Step 3 — tests

Reuse t1243_1's temp tree and differ. Cover: external-concurrent-edit survival;
`semantic=True` advances `updated_at` while `False` leaves the file otherwise
byte-identical; a synthetic third board key round-trips; a deleted file is not
recreated.

## Step 4 — negative control

Revert to the two-name snapshot and confirm the third-key test fails. A guard
that cannot fail pins nothing.
