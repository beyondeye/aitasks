---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, python, gitremote]
created_at: 2026-08-07 15:54
updated_at: 2026-08-07 15:54
---

## Origin

Spawned from t1243_8 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_merge.py:232-235 — anchor merges newer-wins on a task-wide, minute-resolution updated_at, so an unrelated edit on a stale checkout can win a field it never touched; the same causality weakness boardgroup avoids via base-aware detection. anchor could adopt _BASE_AWARE_FIELDS.`
- `.aitask-scripts/aitask_update.sh:657-658 — write_task_file regenerates updated_at on EVERY write, so a --boardidx-only shell update records a semantic modification while the board's own layout write is deliberately timestamp-neutral; the two writers disagree about whether a pure layout move is a change.`

## Diagnostic context

t1243_8 introduced `boardgroup` and had to solve exactly this problem for it.
`updated_at` is **task-wide** and minute-resolution (`%Y-%m-%d %H:%M`), so it is
a proxy for causality, not causality: machine A edits field X at t1; unsynced
machine B edits only field Y at t2 > t1 while still carrying the old X;
newer-wins hands X to B, **which never touched it**. At minute granularity, two
edits in the same minute tie outright.

`boardgroup` escaped this by being resolved through **base-aware change
detection** — the merge base is read from git's conflicted index (stage 1),
supplied by `aitask_sync.sh` as `--base-file`, and the side that actually
differs from the base wins; both-changed-differently and no-base both fail
closed to unresolved/PARTIAL.

`anchor` (`aitask_merge.py:232-235`) still uses the newer-wins scalar branch and
has the identical weakness. It is a semantic topic-group key with cross-tool
consumers (`topic_semantics`, `trail_gather`, the By-Topic view,
`aitask_create.sh` parent inheritance), so an unrelated edit silently
re-anchoring a task is a real correctness problem, not a cosmetic one.

The second defect is a **writer disagreement** rather than a merge rule. The
board's Python path deliberately distinguishes layout writes (timestamp-neutral,
because `boardcol`/`boardidx` are per-checkout and merge local-wins) from
semantic writes, and `tests/test_board_persistence_seam.py` pins that contract.
The shell path has no such distinction: `write_task_file` regenerates
`updated_at` unconditionally, so `aitask_update.sh --batch <id> --boardidx N`
stamps a modification for a move the board considers a non-change. That makes
`updated_at` an unreliable discriminator for any consumer trying to tell "the
user changed something meaningful" from "a card moved".

## Suggested fix

For `anchor`: it is now cheap — both `_BASE_AWARE_FIELDS` and the `--base-file`
plumbing already exist. Adding `"anchor"` to the tuple gets base-aware
resolution and the fail-closed PARTIAL path for free. Decide deliberately
whether `anchor` should fail closed (surfacing a real concurrent re-anchor) or
retain newer-wins as a fallback when no base is available — the parent plan
(t1243) chose fail-closed for membership specifically to avoid guessing.

For the writer disagreement: decide which writer is right. Either teach
`write_task_file` a layout-only mode that preserves `updated_at` (matching the
board), or document that the shell CLI is always a semantic write and have the
board stop treating layout as timestamp-neutral. They must not disagree
silently. Note `tests/test_board_persistence_seam.py`'s frozen-clock assertions
pin the board side, so that side is the one with an explicit contract.

## Reverse pointer

Recorded in `aiplans/archived/p1243/p1243_8_boardgroup_field_and_model.md`
("Upstream defects identified").
