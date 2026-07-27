---
Task: t1243_9_group_focus_and_rendering.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_9 — Group focus and rendering

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_9_group_focus_and_rendering.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — `GroupHeader`

Focusable `Static`, carries `column_id`, renders `▾ perf work (3)`. Emitted as a
**flat sibling** of the member cards inside `KanbanColumn`, the same shape as
`.child-wrapper` rows. Single-member group → plain card, no header.

## Step 2 — the focus-unit abstraction

`_focused_unit()` (cards **and** headers); `_get_column_units` /
`_visible_column_units`; unit-aware `_column_focus_target` and
`_get_focused_col_id`. Keep `_focused_card()` as the narrow "focused task"
accessor the task-level gates need. Restate the t1209 invariant over units.

Without this, a column of only collapsed groups makes `_column_focus_target`
return `None` and focus is silently lost.

## Step 3 — keep the two notions of "unit" apart

Navigation stops include expanded child cards (as today). Movement units do not:
header → whole group, parent card → its `_card_block()`, child card → refused.

## Step 4 — navigation and dispatch

`↓`/`↑` walk header → member → its children → next member → next unit.
`←`/`→` preserve positional index over navigation stops. Wire movement dispatch
per the table in the task file; a member's lateral move carries its `boardgroup`
into the destination column and is **notified**.

## Step 5 — `x` and refocus

`x` toggles children on a card, group collapse on a header. Collapsing hides
members *and* their child-wrappers and moves focus to the header — never leave
focus on an unmounted widget. Specify refocus after filter, collapse, block move
and member move.

## Verification

Real Pilot for every case in the task file, including the
**grouped-parent-with-visible-children integration case** and the
column-of-only-collapsed-groups case that motivated the abstraction.
