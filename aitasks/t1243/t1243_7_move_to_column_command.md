---
priority: high
effort: medium
depends: [t1243_6]
issue_type: feature
status: Ready
labels: [aitask_board, tui, python, custom_shortcuts]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-28 01:15
updated_at: 2026-08-04 10:03
---


## Context

**Child 7 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream D).

Moving several tasks to another column today means repeating `shift+left` /
`shift+right` per task per hop. This child adds a bulk move: pick tasks, pick a
destination column, move them in one operation with **exactly K writes**.

**Coordination — `t1210_5`.** `t1210_5` plans its own column-picker modal for the
By-Trail view. This child ships the shared picker chain and the batch-move API;
t1210_5 (dependency-guarded, and to carry `depends: [t1210_4, 1243_3, 1243_7]`)
consumes them rather than building a parallel path. When this lands, record the
shared entry points in `## Notes for sibling tasks`. `m` means the same thing in
every view — "move the selected task(s) to a column" — with per-view semantics
gated in `check_action`.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `KanbanCommandProvider` (de-dup
  first), a new task-select `ModalScreen`, `KanbanApp` `BINDINGS` +
  `check_action` + `action_move_to_column`.
- `tests/test_board_move_command.py` — **new**.

## Reference files for patterns

- `WorkReportTaskSelectScreen` — the exact prior art: `SelectionList` inside
  `#dep_picker_dialog`, `space` toggles, `Enter` confirms via `on_key`, dismisses
  ordered pairs or `None`.
- `KanbanApp.action_work_report` — the two-stage
  `push_screen(screen, callback)` chain (columns -> tasks -> launch), including
  the `None` (Esc, cancelled cleanly) vs `[]` (nothing selected) distinction.
- `ColumnSelectScreen` + `ColumnSelectItem` — the destination picker.
- `action_collapse_column` — shows how the synthetic `"unordered"` entry must be
  **hand-injected**; it is not in `manager.columns`.

## Implementation plan

### 1. Refactor before extending (NON-OPTIONAL, do it first)

`KanbanCommandProvider` duplicates its command list **verbatim** between
`discover()` and `search()`. Adding a command to one and not the other silently
breaks discovery or search. Collapse both onto a single `_COMMANDS` tuple of
`(display, action_attr, help)` before adding anything. (Per
`aidocs/framework/planning_conventions.md`, "Refactor duplicates before adding to
them".)

### 2. `m` — Move to column…

`m` is **free** in `KanbanApp.BINDINGS` (verified).

- **Focus on a card** → operate on the marked set from t1243_6 if non-empty, else
  the focused card alone.
- **Focus on a column** (empty/collapsed placeholder) → first open a
  `SelectionList` **task-select subdialog** scoped to that column, seeded with
  the current marks, then chain to the destination picker.
- Then `push_screen(ColumnSelectScreen(...), callback)` for the destination, with
  the synthetic `unordered` entry injected.
- Then `manager.move_tasks_to_column(tasks, col)` from t1243_3 — **K contiguous
  indices, K writes, input order preserved**.

### 3. Child rows are excluded

The subdialog **omits** child rows, and `move_tasks_to_column` **fails closed**
on a child id, returning a which-items report rather than skipping silently
(`TaskManager.move_task_col` resolves parents only). See t1243_6 for the rationale.

### 4. Palette entries

Add "Move Tasks to Column" (and "Clear Selection") through the new `_COMMANDS`
tuple, so they appear in both `discover()` and `search()`.

### 5. `check_action` gating

Hide `m` where movement is already hidden (`inflight`, `bytopic`, `bytrail`) and
when there is nothing movable in focus.

## Verification

- **Construction spies** over the two-stage modal chain (assert which screen was
  pushed with which arguments), following `test_board_work_report.py`'s
  `MagicMock`-app pattern — no board state mutated.
- K marked tasks → **exactly K writes** with an **exact changed-path set**, in
  the input order (order is part of the contract: the destination sequence must
  match the presented sequence).
- `None` (Esc) and `[]` (nothing selected) are distinguished and produce
  different messages; neither writes anything.
- A child id passed to `move_tasks_to_column` **fails closed** with a
  which-items report naming the offending ids.
- The synthetic `unordered` destination works when that column has tasks and is
  absent when it does not.
- A guard test asserting `discover()` and `search()` expose the **same** command
  set — the regression the de-dup prevents.

## Notes for sibling tasks

**The §1 `KanbanCommandProvider` de-dup is being done by `t1377_5`, not here.**

`t1377_5_board_column_management_dialog` adds palette entries for a new column
management dialog, so it hits the same verbatim-duplicated `discover()` /
`search()` lists this task's §1 mandates collapsing. Since t1243_7 sits behind the
serial chain `t1243_4 -> 5 -> 6` and t1377 carries no `depends` on it, t1377_5 does
the refactor first (per `aidocs/framework/planning_conventions.md`, "Refactor
duplicates before adding to them").

When picking this task:

- **Check whether `_COMMANDS` already exists** in `KanbanCommandProvider`. If it
  does, **consume it** — add your entries to the single tuple. Do not redo the
  refactor, and do not re-add duplicated lists.
- The parity guard test (`discover()` and `search()` expose the same set) will also
  already exist; extend it rather than writing a second one.
- Everything else here is unaffected: t1377 deliberately built its own picker in
  `monitor/` (the board's `ColumnSelectScreen` is not importable from there) and
  introduced **no** second picker inside the board, so this task's shared-picker
  chain with `t1210_5` is intact.
