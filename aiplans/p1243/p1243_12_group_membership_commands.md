---
Task: t1243_12_group_membership_commands.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_12 — Group membership commands

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_12_group_membership_commands.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — `G`

Opens add / remove / rename for the marked set (else the focused card). Add and
remove delegate to t1243_11; rename rewrites the slug on exactly the member
files.

## Step 2 — rename-onto-existing confirms

A lateral move may coalesce silently (it is not a naming act). A **rename** that
fuses two distinct groups is a destructive surprise, so prompt: "Group 'X'
already exists in this column — merge into it?" → merge / cancel. On cancel,
write nothing.

## Step 3 — child refusal

Subdialog omits child rows; membership APIs fail closed with a which-items
report.

## Step 4 — palette entries

Through `_COMMANDS` (never `discover()` / `search()` separately).

## Step 5 — `BoardGroupField`

Mirror `AnchorField` exactly: always present, empty clears, shells out to
`aitask_update.sh --batch <id> --boardgroup <slug> --silent`, then reloads the
detail screen.

## Verification

Modal-chain spies; add touches K files and no index; rename rewrites exactly the
member files and migrates the collapse key; **rename-onto-existing on cancel
leaves the tree byte-identical**; last-member removal dissolves the group and
drops its key; `BoardGroupField` argv asserted via a subprocess spy.
