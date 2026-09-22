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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:33Z.9161609578a0f0543a980b37 from=t1794_9 from_verified=yes at=2026-09-22T06:08:33Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1243/t1243_12_group_membership_commands.md) cites symbols you name -> current module: AnchorField -> board_detail_screen.py, KanbanApp -> aitask_board.py, KanbanCommandProvider -> aitask_board.py, TaskDetailScreen -> board_detail_screen.py.
> | 
> | Specific to the t1243 family: TaskManager now lives in board_task_manager.py and takes its paths as required keyword-only constructor args (tasks_dir, metadata_file, gates_registry_file, ...); it reads no aitask_board module globals. Tests that used patch.object(aitask_board, 'TASKS_DIR'/...) around a bare TaskManager() now pass those values to the constructor instead. Group / block-move / column operations you add to TaskManager go there; KanbanApp-side bindings and rendering stay in aitask_board.py (TaskDetailScreen additions go to board_detail_screen.py).
