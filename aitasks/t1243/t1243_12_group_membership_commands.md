---
priority: high
effort: medium
depends: [t1243_11]
issue_type: feature
status: Ready
labels: [aitask_board, tui, python, custom_shortcuts]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-28 01:17
updated_at: 2026-07-28 01:17
---

## Context

**Child 12 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream D).

The user-facing surface for groups: add marked tasks to a group, remove them,
rename a group, and edit membership from the task detail screen. Everything
underneath already exists — this child wires it up.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `KanbanApp` `BINDINGS` +
  `check_action` + `action_group`, a group-slug picker/input modal, a rename
  confirm modal, `KanbanCommandProvider._COMMANDS`, and a `BoardGroupField` in
  `TaskDetailScreen`.
- `tests/test_board_group_commands.py` — **new**.

## Reference files for patterns

- `AnchorField` / `AnchorEditScreen` — **the mandated pattern for a new
  board-editable frontmatter field**: an always-present editable field (shown
  even when unset), an empty value clears, and the apply path shells out to
  `aitask_update.sh --batch <id> --<flag> <value> --silent` then reloads the
  detail screen. Mirror it exactly for `BoardGroupField`.
- `WorkReportTaskSelectScreen` (via t1243_7) — the task-select subdialog to reuse.
- `MarkedSelection` (t1243_6) — the marked set to operate on.
- `ColumnSelectScreen` — the picker shape for choosing an existing slug.
- `KanbanCommandProvider._COMMANDS` (t1243_7) — the single de-duplicated command
  list; add entries there, never to `discover()` / `search()` separately.

## Implementation plan

### 1. `G` — Group…

`G` is **free** in `KanbanApp.BINDINGS` (verified). It opens the group operations
for the current selection (the marked set from t1243_6, else the focused card):

- **Add to group** — pick an existing slug in this column or type a new one.
  Calls t1243_11's formation (K `boardgroup` writes, no index writes).
- **Remove from group** — writes the `""` tombstone (1 write per task).
- **Rename group** — rewrites the slug on exactly the member files.

### 2. Rename onto an existing slug: confirm, never silently merge

Group identity is `(column, slug)`, so renaming `G` to a slug already present in
that column would **fuse two distinct groups**. A lateral move coalescing is
fine — it is not a naming act and refusing it would block a legitimate move (see
t1243_11). A rename **is** a naming act, and silent fusion is a destructive
surprise. So: modal confirm — "Group 'X' already exists in this column — merge
into it?" -> merge / cancel. On cancel, **write nothing**. On merge, hand the
collapse-key combination to t1243_10's rule.

### 3. Child ids are refused

The subdialog omits child rows and the membership APIs **fail closed** on a child
id with a which-items report — same contract as t1243_6 / t1243_7. Group
membership is a parent-level concept; children travel with their parent.

### 4. Palette entries

Through `_COMMANDS`: "Add Tasks to Group", "Remove Tasks from Group",
"Rename Group".

### 5. `BoardGroupField` in `TaskDetailScreen`

Following `AnchorField`: always present (so an ungrouped task can be given a
group), empty clears, shells out to `aitask_update.sh --batch <id> --boardgroup
<slug> --silent`, then reloads the detail screen. Note this path advances
`updated_at` on its own, consistent with the in-process semantic writes
(`reload_and_save_board_fields(fields=("boardgroup",))` — there is no
`semantic=True` bool) — both matter for t1243_8's base-aware merge.

### 6. `check_action` gating

Hide `G` where movement is already hidden (`inflight`, `bytopic`, `bytrail`) and
when nothing groupable is in focus.

## Verification

- **Modal-chain construction spies** (the `MagicMock`-app pattern from
  `test_board_work_report.py`) for each of the three operations.
- Add-to-group: exactly K files changed, all `boardgroup`, **no `boardidx`**.
- Rename: rewrites **exactly** the member files and **migrates the collapse key**;
  a reload shows the group still collapsed under its new name.
- **Rename onto an existing slug prompts**, and on cancel **writes nothing**
  (assert the tree is byte-identical); on confirm, the groups merge and the
  collapse keys combine per t1243_10's rule.
- Removing the **last** member dissolves the group and **drops its collapse key**.
- A child id passed to any membership API fails closed with a which-items report.
- `BoardGroupField` renders for a task with no group, and its apply path invokes
  `aitask_update.sh` with the expected argv (spy the subprocess call).
- Palette: all three commands appear in **both** `discover()` and `search()` (the
  `_COMMANDS` guard test from t1243_7 still holds).
