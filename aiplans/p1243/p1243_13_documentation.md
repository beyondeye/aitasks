---
Task: t1243_13_documentation.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_13 — Documentation

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_13_documentation.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — read the live sources

Read `aidocs/framework/documentation_conventions.md` and each target file as it
stands now. Document the **landed** behaviour — children 9–12 may have adjusted
details the design plan predates.

## Step 2 — board feature docs

Groups, marking (`space`), bulk move (`m`), group commands (`G`), and `x`'s
widened meaning. Current-state prose only; no version history. Do not mention
`diffviewer` or add it to any list of TUIs.

## Step 3 — the frontmatter sweep

Walk the extension-points layer-5 list for `boardgroup`: seed instructions →
regenerate AGENTS.md via the `ait setup` path; hand-edit the Codex/OpenCode
mirrors (markerless — running the inserter appends a duplicate block);
`CLAUDE.md`; `task-format.md`; the board reference row. Confirm and note that
**no creation flag exists** (`--boardgroup` is update-only, mirroring
`--boardidx`) rather than inventing one.

## Step 4 — pick up t1243_8's leftovers

Any layer t1243_8 flagged as uncovered in its Final Implementation Notes.

## Verification

Drift grep both directions between documented keys and `KanbanApp.BINDINGS`;
grep each frontmatter surface explicitly and **report the hit count**;
AGENTS.md matches the seed with no duplicate block; `hugo build --gc --minify`
succeeds.
