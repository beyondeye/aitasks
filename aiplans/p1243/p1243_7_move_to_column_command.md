---
Task: t1243_7_move_to_column_command.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_7 — Move-to-column command

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_7_move_to_column_command.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — de-duplicate the command provider FIRST

`KanbanCommandProvider` repeats its command list verbatim in `discover()` and
`search()`. Collapse both onto one `_COMMANDS` tuple before adding anything —
otherwise this task ships the first drift.

## Step 2 — the task-select subdialog

Model it on `WorkReportTaskSelectScreen`: `SelectionList` in
`#dep_picker_dialog`, `space` toggles, `Enter` confirms via `on_key`, dismisses
ordered pairs or `None`. Seed it from the marked set. **Omit child rows.**

## Step 3 — the chain

`m` → (subdialog if a column is focused) → `ColumnSelectScreen` →
`move_tasks_to_column`. Follow `action_work_report`'s two-stage
`push_screen(screen, callback)` pattern, and hand-inject the synthetic
`unordered` destination — it is not in `manager.columns`.

## Step 4 — fail closed on children

`move_tasks_to_column` returns a which-items report on a child id rather than
skipping silently.

## Step 5 — palette + gating

Add "Move Tasks to Column" and "Clear Selection" via `_COMMANDS`; gate `m` in
`check_action`.

## Verification

Construction spies over the chain; K marked → exactly K writes in input order
with an exact changed-path set; `None` vs `[]` distinguished and neither writes;
child id fails closed; guard test that `discover()` and `search()` expose the
same set.

## Notes for sibling tasks

**t1210_5** consumes this chain rather than building its own picker; record the
entry points here.
