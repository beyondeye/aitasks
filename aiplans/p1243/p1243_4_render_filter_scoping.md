---
Task: t1243_4_render_filter_scoping.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_4 — Render filter scoping

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_4_render_filter_scoping.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 0b — read the checkpoint

Before anything else, read t1243_1's recorded decision in the parent plan. If the
premise was refuted, this task's scope was rewritten there — follow that, not the
original shape.

## Step 1 — `apply_filter(cols=None)`

`None` keeps today's whole-board pass byte-for-byte (view/filter toggles rely on
it). A given `cols` set iterates only those columns' cards and touches only those
columns' placeholders and focus rescue.

## Step 2 — cheap wins in the same pass

Cache the lowercased search haystack per `TaskCard`; assign
`card.styles.display` only when it changes.

## Step 3 — drop the per-keypress subprocess

Movement paths add the filenames they just wrote to `manager.modified_files`
directly instead of calling `refresh_git_status()`. Exact, because we produced
the changed set. Full scan stays on explicit refresh and commit.

## Step 4 — leave the seam open for t1243_10

Factor the match predicate into a **data-level** helper taking a `Task` (no
widget), and keep the visible-content accumulator widget-kind-agnostic. A
collapsed group mounts no member cards, so t1243_10 must be able to evaluate
members that have no widget without rewriting this pass.

## Verification

Spy: a lateral move queries only the two touched columns and spawns no
subprocess. The predicate helper is unit-tested with no widget mounted.
`tests/test_board_view_filter.py` passes unchanged. **The ≥ 30% median-latency
target is the pass condition** — record the delta and the dominant remaining span
either way.
