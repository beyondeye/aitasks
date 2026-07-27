---
Task: t1243_14_retrospective_benchmark.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_14 — Retrospective benchmark

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_14_retrospective_benchmark.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — re-run the pre-registered benchmark

Same method as t1243_1 verbatim — ping-pong sampling, warm-up discarded, every
sample must carry a write, median + p90 + per-span totals. Comparability is the
whole point; do not "improve" the method here.

## Step 2 — re-run the write assertions at scale

Single move, bulk move of K, formation of K, block move of N. Record **actual**
counts and changed-path sets, not pass/fail.

## Step 3 — the comparison table

Baseline vs landed, per span, with median and p90 deltas and whether the ≥ 30%
target was met.

## Step 4 — answer the open questions

`STEP = 1024` compaction frequency in practice; which span now dominates; how
much latency the t1243_5 fallback left on the table if the spike failed; whether
"one move = one file write" held over a real session including the compaction
exception.

## Step 5 — file follow-ups only where a number justifies one

Every follow-up cites its measurement. "No follow-ups warranted", stated
explicitly with the supporting numbers, is a successful outcome.

## Verification

The table is recorded in this plan; every claim traces to a measured number.
