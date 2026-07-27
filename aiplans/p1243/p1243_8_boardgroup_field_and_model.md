---
Task: t1243_8_boardgroup_field_and_model.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_8 — boardgroup field and model

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_8_boardgroup_field_and_model.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — the key split

`BOARD_LAYOUT_KEYS = ("boardcol","boardidx")`;
`BOARD_KEYS = BOARD_LAYOUT_KEYS + ("boardgroup",)`. Repoint each consumer per the
table in the task file — in particular narrow `_KEEP_LOCAL_FIELDS` to
`BOARD_LAYOUT_KEYS`, so membership is not silently local-won.

## Step 2 — supply the merge base

The diff3 base is unavailable in production (`merge.conflictStyle` is configured
nowhere; sync runs a plain `pull --rebase`). Read stage 1 from the conflicted
index instead:

- `aitask_sync.sh` extracts `task_git show ":1:$file_path"` to a temp file and
  passes `--base-file`;
- `aitask_merge.py` gains `--base-file` and uses it as the third side; the diff3
  parser stays only as a fallback;
- stage 1 needs no rebase side-swap — leave the existing `--rebase` swap alone.

## Step 3 — the resolution rule

Side-that-differs-from-base wins; both-differ-same takes that value;
both-differ-different and no-base both go to **unresolved / PARTIAL**. Resolve
`boardgroup` in a pre-loop block, ahead of the unconditional one-sided-presence
branch, mirroring how `_ACTIVE_TUPLE_FIELDS` already does it.

## Step 4 — the tombstone

Removal writes `boardgroup: ""`, not a deleted key. Omit ≠ clear.

## Step 5 — `lib/board_groups.py`

The INV-R derivation (unit bucketing + sort keys) and the shared match predicate.
**Grouping writes no index.** Contiguity is explicitly not an invariant — the
parent plan explains why it is unachievable under mixed merge rules.

## Step 6 — CLI + extension-points sweep

`--boardgroup` in `aitask_update.sh` only (mirroring `--boardidx`); slug
validation; fold no-op note. Walk the extension-points checklist and hand any
uncovered layer to t1243_13.

## Verification

Unit tests for the derivation and for every base/presence/divergence
combination; **a temporary-repository integration test** driving a real
unrelated-edit-vs-`boardgroup` conflict through the actual rebase path under the
default conflict style; a withheld-base negative control yielding PARTIAL; a
guard test that every `aitask_sync.sh` driver invocation passes `--base-file`.

Record in Final Implementation Notes: `anchor` has the same task-wide-timestamp
weakness. Observation only — do not widen scope.
