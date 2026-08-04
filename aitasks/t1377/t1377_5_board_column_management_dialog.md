---
priority: high
effort: medium
depends: [t1377_4]
issue_type: feature
status: Ready
labels: [aitask_board, board_columns, tui, custom_shortcuts]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-04 09:56
updated_at: 2026-08-04 19:21
---



## Context

`ait board` already supports add / edit / delete / reorder / collapse of columns,
but **no key is bound to add, edit or delete** — they are reachable only through the
Ctrl+P command palette or the header pencil button. So the real gap is
**discoverability plus merge**, not raw capability. This child consolidates all of
it behind one dialog on one key, and wires in the merge engine from t1377_4.

## Key Files to Modify

- **`.aitask-scripts/board/aitask_board.py`** — `_COMMANDS` de-dup,
  `ColumnManageScreen`, the `e` binding, `check_action` gating, CSS.
- **`aitasks/t1243/t1243_7_move_to_column_command.md`** and
  **`aitasks/t1243/t1243_10_group_collapse_and_filtering.md`** — reverse notes.
- **`tests/`** — dialog + parity tests.

## Reference Files for Patterns

- `aitask_board.py` `ColumnSelectScreen` — single-select column picker, already
  parameterised by a column list. **Reuse it**; the parent's AC7 forbids a second
  picker inside the board.
- `aitask_board.py` `WorkReportColumnSelectScreen` — `SelectionList`-based
  multi-select over `(id, title)` pairs. The template for the N->1 merge source
  selection.
- `aitask_board.py` `ColumnEditScreen`, `DeleteColumnConfirmScreen`,
  `ColumnSelectItem`, `PickerItem`, `ColorSwatch`.
- `aitask_board.py` `_shift_column` — today's one-step reorder; the dialog
  generalises it to a whole-list rewrite of `column_order` + `save_metadata()`.
- `aitask_board.py` `action_collapse_column` — the precedent for hand-injecting the
  synthetic `unordered` entry into a picker list.
- `KanbanApp.CSS` — `#column_edit_dialog`, `#dep_picker_dialog`, `.picker-dialog`
  (which already carries the t1366 scroll/focus fix).
- `aidocs/framework/tui_conventions.md` — footer visibility, uppercase-sibling
  adjacency, and the note that a dialog inside an already-manifested module is
  picked up automatically by `register_all_known_bindings()` (no
  `KNOWN_BINDING_SOURCES` edit needed).

## Implementation Plan

### Step 1 — `_COMMANDS`: check first, consume if present

`KanbanCommandProvider` duplicates its command list **verbatim** between
`discover()` and `search()`. Adding a command to one and not the other silently
breaks discovery or search, so it must be collapsed onto a single `_COMMANDS` tuple
of `(display, action_attr, help)` **before** any new command is added
(`aidocs/framework/planning_conventions.md`, "Refactor duplicates before adding to
them").

**`t1243_7_move_to_column_command` is expected to have landed that refactor** — it
is its §1 mandate, and it sits far ahead of this child in the queue. So:

- **Grep for `_COMMANDS` first.** If it exists, **consume it**: add the
  "Manage Columns" / "Merge Columns" entries to the single tuple, and **extend**
  t1243_7's existing parity guard rather than writing a second one. Do not redo the
  refactor.
- **Only if it is still absent** (t1243_7 slipped), do the de-dup here first,
  exactly as t1243_7 §1 specifies, and record it in that task's
  `## Notes for sibling tasks`.

Either way, exactly one `_COMMANDS` tuple and one parity guard must exist when this
child is done.

### Step 2 — one dialog behind one key

`ColumnManageScreen`, bound to **`e`** (verified free in `KanbanApp.BINDINGS`; `m`
is reserved by t1243_7 and `G` by t1243_12 — do not take either). Footer-visible
with a short label, gated in `check_action` to the kanban views and hidden in
In-Flight / By-Topic / By-Trail, which render derived lanes rather than columns —
mirroring how `w` is column-scoped.

Contents, reusing existing screens:

- the column list in `column_order`, with up/down to reorder — rewrites
  `column_order` wholesale then `save_metadata()`;
- **Add** / **Edit** -> `ColumnEditScreen` via `_handle_column_edit_result`;
- **Delete** -> `DeleteColumnConfirmScreen`;
- **Merge** -> `SelectionList` multi-select of sources -> `ColumnSelectScreen` for
  the destination -> `merge_columns`, with a confirm naming the task count. List
  `unordered` as a source only when it holds tasks.

Keep the palette entries working (they now route through `_COMMANDS`) and add
"Manage Columns" / "Merge Columns" there too.

**Partial-merge reporting (contract from t1377_4).** Branch on `result.complete`:
complete -> `notify("Merged N tasks into <dest>")`; partial -> `severity="warning"`
naming the counts and the retry, e.g.
`"Merged 7 of 9 into Backlog — 2 failed, re-run to finish"`. A bare "Merged" toast
on a partial merge is the specific failure this clause exists to prevent.

### Step 3 — Workstream C (`boardgroup`) — check, don't assume

**The order between t1377 and t1243's Workstream C is undecided** — `t1243_8` is
`Ready` and both chains are live. Do not hard-code either assumption.

Grep for `collapsed_groups` in `.aitask-scripts/board/aitask_board.py` and `lib/`:

- **Absent** (Workstream C has not landed): build the dialog against the current
  model. `BOARD_KEYS == BOARD_LAYOUT_KEYS == ("boardcol", "boardidx")`, there are no
  group headers, and no composite keys exist. `t1243_10` already carries a sibling
  note telling it to extend `merge_columns` / `update_column` when it lands after
  t1377.
- **Present** (Workstream C landed first): the dialog must reckon with groups — a
  collapsed group mounts a `GroupHeader` and zero member cards, and
  `settings.collapsed_groups` holds composite `"<col>/<slug>"` keys. t1377_4's
  "Composite group collapse keys" section owns the engine half; this child's half is
  making the delete / merge confirmations report **group** counts as well as task
  counts, and keeping the column list unit-aware. Read
  `aiplans/archived/p1243/p1243_10_*.md` for the coalesce rule.

Either way, do **not** pre-build group handling speculatively, and do not leave a
note claiming an order that did not happen.

## Verification Steps

```bash
bash tests/run_all_python_tests.sh     # read ONLY the last line for the verdict
```

Tests:

- `_COMMANDS` parity guard: `discover()` and `search()` expose the same set — with a
  negative control proving the guard discriminates (add a command to one path only
  and show the test fails).
- The dialog's reorder persists `column_order` and survives a reload.
- Merge flow end-to-end through the real `KanbanApp` on the fixture harness
  (`tests/lib/board_fixture.py`).
- A **partial** merge takes the warning-severity notification path, not the success
  one.
- Footer visibility per view via `check_action`, including at least one view where
  `e` must be **hidden**.

## Coordination — read before starting

`t1243_4` was `Implementing` in `aitask_board.py` during planning (`apply_filter`,
`refresh_git_status`) and `t1243_5` will later rewrite movement actions to async.
Those are different regions from column management, but this child edits
`BINDINGS`, `CSS` and `KanbanCommandProvider`. **Re-read `aitask_board.py`
immediately before implementing**, grep for symbols rather than trusting line
numbers, and keep the new UI strictly above the render layer so t1243_5 does not
rewrite it. Stage explicit paths; never `git stash` / `git add -A` in this shared
checkout.
