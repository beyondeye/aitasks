---
Task: t1243_1_movement_baseline_and_harness.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_1 — Movement baseline and harness

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_1_movement_baseline_and_harness.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — temp-tree fixture

Build a helper that materialises a synthetic `TASK_DIR`: `aitasks/`,
`aitasks/metadata/board_config.json` with a known column set, and N real `t*.md`
files carrying `boardcol` / `boardidx` / `status` frontmatter.

## Step 2 — subprocess runner (do this before any scenario)

`TASKS_DIR` is bound at module import, and the suite runs every `test_*.py` in
one pytest process where 16 board tests already import `aitask_board`. So the
scenario body runs in a **child interpreter**:

- `sys.executable`, `env["TASK_DIR"]` = temp tree, `PYTHONPATH` covering
  `.aitask-scripts/board` and `.aitask-scripts/lib`;
- the child imports `aitask_board`, runs one scenario under Pilot, and writes a
  result dict to a **JSON path given in argv**;
- the parent reads that JSON. Never parse stdout — Textual and pytest write there.

## Step 3 — the two oracles

- call-count spy wrapping `Task.reload_and_save_board_fields`;
- path+hash snapshot of the whole temp tree before and after, diffed.

Both are needed: the spy counts writes, the differ proves *which* files changed
and that untouched frontmatter survived.

## Step 4 — characterization flip table

A dict of scenario → `(expected_write_count, expected_changed_paths)` for
`_move_task_lateral`, `_move_task_vertical`, `_move_task_to_extreme`,
`_shift_column`, asserted exactly. t1243_3 must edit this table deliberately.

## Step 5 — pre-registered benchmark

Fix method and rules **before** running anything (they are quoted in full in the
task file): ping-pong sampling, warm-up discarded, every sample must carry a
write, median + p90 + per-span totals. Premise rule: filter+recompose ≥ 40% of
median. Target rule for t1243_4/5: ≥ 30% median reduction.

## Step 6 — decision checkpoint

Compare to the premise rule. If refuted, revise/replace/postpone t1243_4 and
t1243_5 — edit those task files and plans — and record the data and decision in
the parent plan. Do not let the chain carry a falsified premise.

## Verification

Standalone **and** full-suite runs agree; the suite exits 1 on a reverted
behaviour; the in-process negative control demonstrably reads the real tree; the
repo's own `aitasks/` is untouched.
