---
priority: high
effort: medium
depends: [t1243_6]
issue_type: feature
status: Implementing
labels: [aitask_board, tui, python, custom_shortcuts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
implemented_with: claudecode/opus5
created_at: 2026-07-28 01:15
updated_at: 2026-08-04 12:54
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

**`t1377_5` consumes your `_COMMANDS` de-dup — do it here, as §1 already says.**

At t1377 planning time t1243_4/_5 had not landed and this task sat behind three
children, so the de-dup was provisionally assigned to
`t1377_5_board_column_management_dialog`. That assumption is now void: t1243_4 and
t1243_5 have landed, and t1377_5 is blocked behind `t1377_1 -> 2 -> 3 -> 4`, so
**this task lands first**. Keep §1 exactly as written and do the refactor here.

What t1377_5 will do when it arrives:

- **Consume `_COMMANDS`** — add its "Manage Columns" / "Merge Columns" entries to
  your single tuple. It will not re-add duplicated lists.
- **Extend your parity guard** (`discover()` and `search()` expose the same set)
  rather than writing a second one.
- Bind its column-management dialog to **`e`**, not `m` — no keybinding conflict
  with this task.

No second picker is introduced inside the board by t1377: it deliberately built its
own picker in `monitor/` (the board's `ColumnSelectScreen` is not importable from
there), so this task's shared-picker chain with `t1210_5` is intact.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-04T09:54:50Z status=pass attempt=1 type=human
