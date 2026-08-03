---
priority: medium
effort: high
depends: [1243_7]
issue_type: feature
status: Ready
labels: [aitask_monitormini, aitask_board, tui, board_columns]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-03 10:37
updated_at: 2026-08-03 10:37
---

Umbrella task with two related deliverables that share the same underlying seams
(a column list/picker and a headless board-column writer). Decompose into
children at planning time.

## Deliverable 1 — minimonitor: choose *pick* vs *move to board column*

The `p` shortcut's pick-by-number flow in `ait minimonitor` is today a fixed
3-step chain (all hops are `push_screen(..., callback=...)` in
`.aitask-scripts/monitor/minimonitor_app.py:1152-1273`):

1. `TaskNumberInputModal` — `.aitask-scripts/monitor/monitor_shared.py:642`
   (returns the raw string; validation is the caller's job, done in
   `_on_pick_number_entered` at `minimonitor_app.py:1179` against
   `_PICK_TASK_ID_RE`).
2. `TaskPickConfirmDialog` — `monitor_shared.py:714`, a subclass of
   `TaskDetailDialog` (`:561`). Renders the task detail plus a docked
   `#pick-confirm-row` (eligibility warnings, already-running warning, the
   "kill followed agent" checkbox, and `btn-pick-ok` / `btn-pick-cancel`).
   Dismisses `(True, kill: bool)` or `None`.
3. `AgentCommandScreen` — `.aitask-scripts/lib/agent_command_screen.py:176`,
   invoked from `_launch_pick` (`minimonitor_app.py:1094-1150`).

**Goal:** at step 2, let the user choose between *pick the task* (today's path,
continuing to step 3) and *move the task to a board column* — selecting an
existing column, or creating a new one.

### What already helps

- `TaskPickConfirmDialog` already dismisses a **tuple**, so widening it to an
  `(action, payload)` shape is a natural extension rather than a rewrite.
- `NextSiblingDialog` (`monitor_shared.py:963`) is the exact precedent: a detail
  block plus three stacked buttons, dismissing `("pick", id)` /
  `("choose", parent_id)` / `None`, with a `.narrow` variant for the ~40-col
  companion pane.
- `ChooseSiblingModal` (`monitor_shared.py:1097`) + `_SiblingRow` (`:1036`) is
  the precedent for the follow-up "which column?" list (focusable rows, ↑/↓/Enter
  nav, OK/Cancel, `.narrow` variant).
- Both are already imported by `minimonitor_app.py` — no new module wiring.
- Every minimonitor modal must supply a `.narrow` variant; this is a hard
  convention in this package, not an optional polish step.

### The real blocker — minimonitor has no write path

`grep -rn boardcol .aitask-scripts/monitor/` returns **zero** hits. The whole
`monitor/` package is a read-only TUI over tmux plus task files (`TaskInfoCache`
in `monitor_core.py:2839` only reads). This feature introduces the first task-file
mutation in minimonitor, so the write seam is the load-bearing design decision.

Options surveyed:

- **`ait update --batch <N> --boardcol <id>`** (`.aitask-scripts/aitask_update.sh`;
  flag help at `:224`, parse at `:348`, emit at `:791`). Cross-process safe and
  already on the cross-repo allowlist (`:260`). **Two gaps:** it computes no gap
  `boardidx`, and it does **not validate that the column id exists** — a bad id
  yields a task that renders in no column at all, not even `unordered`. The board
  itself always writes `boardcol` *and* `boardidx` together, appending via
  `board_ordering.index_for_append`.
- **Importing `TaskManager`** from `.aitask-scripts/board/aitask_board.py` is a
  tested headless API (`move_task_to_column` `:1446` / `move_tasks_to_column`
  `:1450`, returning `MoveResult` `:895`) — but `aitask_board.py` imports Textual
  at module scope (`:55-62`) and `TaskManager.__init__` loads and parses *every*
  task. Too heavy for minimonitor.
- **Reading the column list** is already clean and Textual-free:
  `.aitask-scripts/lib/work_report_gather.py:221` `load_columns() -> (ordered_ids,
  {id: title})`, or the CLI `aitask_work_report_gather.sh --list-columns` which
  emits `COLUMN:<id>|<title>` and prepends `unordered` when tasks live there.

Likely shape: extract a **Textual-free board-column write helper** (`boardcol` +
gap-computed `boardidx`, with column-id validation) into `.aitask-scripts/lib/`,
reusing the pure `lib/board_ordering.py`; have minimonitor call it (or a thin
shell wrapper). Adding column-id validation to `aitask_update.sh --boardcol` is a
worthwhile standalone fix regardless of which path is chosen.

### "Create a new column" from minimonitor — feasibility

Feasible, but it is a **real subtask, not a small add**. Column creation exists
**only** inside the board TUI:

- `TaskManager.add_column` — `aitask_board.py:1564` (appends to `self.columns` and
  `self.column_order`, then `save_metadata()`).
- `ColumnEditScreen` — `:5215`; the id is **auto-slugged** from the title by the
  static `_generate_col_id(name, existing_ids)` (`:5231`), never user-chosen.
- Color comes from an 8-entry palette, `PALETTE_COLORS` at `:5167`.
- Persistence is layered: `load_layered_config` / `split_config` /
  `save_project_config` in `.aitask-scripts/lib/config_utils.py`, with
  `_PROJECT_KEYS = {"columns", "column_order"}` and `_USER_KEYS = {"settings"}`
  (`aitask_board.py:68-69`). Project columns live in
  `aitasks/metadata/board_config.json`; user prefs in `board_config.local.json`
  (gitignored).

There is **no CLI and no Textual-free writer for `board_config.json`**. So
create-new requires extracting slug generation + palette + layered save into a
headless seam. `ait settings` deliberately renders columns read-only
(`settings/settings_app.py:2366` — literally labelled
"read-only — edit via board TUI"), so a new headless writer changes that stance
and `ait settings` should be revisited for consistency.

**Recommended:** treat create-new-column as its own child, sequenced after the
move-to-existing-column child, so deliverable 1 can land useful value early.

## Deliverable 2 — ad-hoc column reorder/delete/merge dialog in `ait board`

### What exists today

| Op | Status | Where |
|---|---|---|
| Create | exists | `action_add_column` `aitask_board.py:8621` → `TaskManager.add_column` `:1564` |
| Rename / recolor | exists | `action_edit_column` `:8628` / `open_column_edit` `:8656` → `update_column` `:1570` |
| Reorder | exists | `ctrl+left` / `ctrl+right` (`:5822-5825`) → `_shift_column` `:8582` (swaps in `column_order`, saves metadata) |
| Delete | exists | `action_delete_column` `:8638` → `DeleteColumnConfirmScreen` `:5298` → `delete_column` `:1611` (tasks → `unordered`, `boardidx=0`) |
| **Merge** | **does not exist** | — |
| Collapse/expand | exists | `toggle_column_collapsed` `:1598`, `action_collapse_column` `:8689` |

So the gap is **discoverability plus merge**, not raw capability: add/edit/delete
are reachable **only through the Ctrl+P command palette**
(`KanbanCommandProvider` `:5447`) or the ✎ header button (`ColumnEditButton`
`:1648`). **No keybinding is bound to add/edit/delete.** A single ad-hoc
management modal behind one key is the natural consolidation.

### Merge has a latent implementation already

`TaskManager.update_column(col_id, new_id, title, color)` (`:1570`) **already**
handles `col_id != new_id` by patching `column_order` and rewriting every
member task's `boardcol` via
`task.reload_and_save_board_fields(("boardcol",))`. The UI never exercises it —
`_handle_column_edit_result` (`:8613`) passes the same id twice. A merge (move
all of column A's tasks into B, then drop A) can be built on this existing,
already-written migration path.

**Merge semantics to decide:** `boardidx` collision handling when two columns
merge (the members of A need fresh appended indices in B, not their old ones);
whether merge is N→1 or strictly 2→1; what happens to `settings.collapsed_columns`
entries for the removed column.

### Reuse targets in the board TUI

- `ColumnSelectScreen` `:5422` — already parameterized by a column list
  (`__init__(manager, action_label, columns=None)`), dismisses a `col_id`. Direct
  fit for a merge-source / move-to picker.
- `WorkReportColumnSelectScreen` `:4148` — `SelectionList`-based **multi-select**
  over `(id, title)` pairs; the template for an N→1 merge.
- `ColumnEditScreen` `:5215`, `DeleteColumnConfirmScreen` `:5298`,
  `ColumnSelectItem` `:5402`, `PickerItem` `:2381`, `ColorSwatch` `:5179`.
- Already-styled CSS ids: `#column_edit_dialog`, `.picker-dialog`.

## Coordination with t1243 (mandatory — read before planning)

`t1243_board_task_groups_and_fast_reordering` is an active decomposition parent
(3 children Done, 12 Ready, strictly serial via `depends`). Plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md`.

- **`t1243_7_move_to_column_command` is literally a board "move to column"
  command** (Workstream D). It builds the same column-picker chain this task
  needs. `depends: [1243_7]` is set on this task accordingly, matching the
  protocol `t1210_5_trail_move_to_column_commands` already follows
  (`depends: [t1210_4, t1243_3, t1243_7]`). **Do not build a second, parallel
  column picker** — consume or extend whatever t1243_7 lands.
- **`t1369_board_batch_move_linear_index_arithmetic`** (Ready, `anchor: 1243`)
  rewrites `TaskManager.move_tasks_to_column` to linear index arithmetic and
  names t1243_7 and t1210_5 as its large-K consumers. It should land before
  t1243_7; anything here that writes board fields must be re-checked against its
  result.
- **`t1243_5_lateral_dom_transplant`** replaces the `refresh_columns` /
  `_recompose_column` path for lateral moves with an in-place DOM transplant and
  makes movement actions **async / `run_worker`**. Any new column-move UI landing
  before it will be rewritten by it — prefer landing after, or keep the new UI
  strictly above the render layer.
- **`t1243_4_render_filter_scoping`** scopes `apply_filter` to touched columns and
  removes the per-keypress `git status`; it requires the match predicate be
  factored into a data-level helper and `cols_with_visible` kept
  widget-kind-agnostic.
- **Workstream C (`t1243_8` … `t1243_12`)** introduces the `boardgroup`
  frontmatter field, group headers, group collapse and group filtering. A
  column **delete or merge** dialog must reckon with groups: a collapsed group
  mounts a `GroupHeader` and zero member cards, and `settings.collapsed_groups`
  holds per-group state. Deliverable 2 should be designed against the
  post-Workstream-C model, or explicitly scoped to land before it with a stated
  migration.
- **`t1371_atomic_frontmatter_patch_writes` is `Implementing` right now** and
  touches the frontmatter write seam (`reload_and_save_board_fields`, reshaped by
  the completed `t1243_2`). Check its landed diff before designing any write path.

## Contracts that must not be broken

- `Task.reload_and_save_board_fields(fields)` (`aitask_board.py:263-312`) —
  `fields` is **required and validated**; a caller must name exactly the fields it
  mutated. Naming a field it did not mutate can revert another writer's change
  (e.g. a stale `boardcol` from an index-only move).
- `BOARD_LAYOUT_KEYS = ("boardcol", "boardidx")` (`lib/task_yaml.py:55`) — because
  these are layout keys, merge conflicts on them resolve **silently local-wins**
  and writes naming only them do **not** bump `updated_at`. A new headless writer
  must preserve both properties.
- `normalize_board_idx` (`lib/task_yaml.py:68`) is the single coercion point —
  reuse it, do not re-implement int parsing.
- `respace_column` (`aitask_board.py:1551`) is **the exhaustion remedy only** and
  must never be called from a movement path (there is a `respace_after_move`
  negative-control test in `tests/test_board_movement.py`).
- Column ids containing `|`, CR or LF are a fatal error in the work-report
  protocol (`lib/work_report_gather.py:221-251`); any new column-creation seam
  must reject them.
- A `column_order` entry with no matching `columns` entry is silently dropped by
  both the renderer and `load_columns()`; reorder/delete/merge must keep the two
  lists consistent.

## Acceptance criteria

1. In minimonitor, the pick-by-number detail step offers an explicit choice
   between picking the task and moving it to a board column; the pick path is
   byte-for-byte unchanged when chosen.
2. Moving to an existing column from minimonitor writes both `boardcol` and a
   correctly gap-computed `boardidx`, validates the column id, and is visible in
   `ait board` on next refresh.
3. Creating a new column from minimonitor either works through a documented
   headless seam, or is explicitly deferred with the reason recorded.
4. `ait board` exposes a single ad-hoc column-management dialog covering reorder,
   delete and merge (add/edit either folded in or left on the palette, decided at
   planning).
5. Column merge migrates every member task's `boardcol`, assigns fresh
   destination indices, removes the source column from both `columns` and
   `column_order`, and cleans up any `settings.collapsed_columns` entry.
6. All new minimonitor modals ship a `.narrow` variant.
7. No parallel re-implementation of t1243_7's column picker.
8. Tests cover the headless write seam and the merge migration; existing board
   movement/ordering tests still pass.

## Open questions for planning

- Should the headless board-column seam be a new `lib/` module, a new
  `aitask_board_column.sh`, or an extension of `aitask_update.sh`?
- Does `ait settings` stop being read-only about columns once a headless writer
  exists?
- Is merge N→1 or 2→1?
- Should deliverable 2 wait for Workstream C (`boardgroup`), or land before it
  with a documented migration?
