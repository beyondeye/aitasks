---
Task: t1243_10_group_collapse_and_filtering.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_10 — Group collapse and filtering

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_10_group_collapse_and_filtering.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — unit-level filtering

Generalise `apply_filter` from cards to units using t1243_4's data-level
predicate:

- expanded group: members evaluated as today, header visible iff ≥ 1 matches;
- collapsed group: **no member widgets exist** — evaluate member `Task` data
  (and their children's), header visible iff ≥ 1 matches;
- collapsed partial match: header stays, shows `· N match`; no auto-expand;
- a visible header counts toward `cols_with_visible`, so a column of only
  collapsed groups stops showing its empty placeholder;
- `GroupHeader` joins the focus-rescue isinstance tuple;
- the scoped `cols` pass queries headers too.

## Step 2 — persisted collapse state

`settings["collapsed_groups"]` = `["<col>/<slug>", ...]` in
`board_config.local.json`. Never write the project layer at runtime.

## Step 3 — lifecycle owners

Wire the five transitions in the task file's table (group rename, group column
move, dissolve, column rename, column delete), plus the coalesce
key-combination rule.

## Step 4 — prune-on-load

Drop keys whose `(col, slug)` has no members — the backstop for states no
transition caught (external CLI edits, tasks archived elsewhere).

## Verification

The full filtering matrix including the collapsed-matched-via-child case, each
in its scoped variant; **restart-and-assert after each of the five
transitions**; stale keys pruned; `board_config.json` byte-identical after any
runtime collapse/expand.
