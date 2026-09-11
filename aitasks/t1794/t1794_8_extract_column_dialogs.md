---
priority: medium
effort: medium
depends: [t1794_7]
issue_type: refactor
status: Ready
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 8 of t1794 — the last extraction: the column-management dialogs and
column pickers move to `board_column_dialogs.py`. After this child,
`aitask_board.py` holds `KanbanApp`, the Kanban render paths, the board key
map / `check_action`, `InFlightTaskCard`, the task-select screens, the module
constants and the three injected helpers — the shape the parent acceptance
criteria describe.

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— C1, C3, C5; "Target file map". Anchors at `e2f12c499` (unchanged at
`c78deab36`).

## Key files to modify

- `.aitask-scripts/board/board_column_dialogs.py` — NEW: `ColorSwatch`
  (`:7803`), `ColumnSelectItem` (`:8017`), `ColumnSelectScreen` (`:8037`),
  `ColumnManageItem` (`:8060`), `ColumnManageScreen` (`:8128–8397`),
  `ColumnMultiSelectScreen` (`:6546`). Grep each for board-only callers
  first; the column dialogs are pushed by `_open_column_manage :13320` and
  `_choose_move_destination` (board) — those push sites stay in the board and
  import the screens flat.
- `.aitask-scripts/board/aitask_board.py` — `import board_column_dialogs` +
  flat re-imports; delete the definitions.
- `tests/test_board_column_manage.py` — C3 sweep: its `patch.object(B, …)`
  sites (`:95, 695, 713, 729, 745`) target `save_project_config` /
  `save_local_config`, which child 4 already repointed to
  `board_task_manager`; confirm nothing in the moved dialogs calls a patched
  name directly (if one does, repoint to `B.board_column_dialogs` with a
  mutant).
- `tests/test_board_package_contract.py` — pairing entry if needed.
- Markup-escape tests for `ColumnSelectItem.render()` / `ColorSwatch.render()`
  (referenced by pending t1441 / t1442 — search `tests/` for
  `ColumnSelectItem`) address the new module.

## Reference files for patterns

- `aitask_board.py:53–66` — import pairing.
- `lib/board_columns.py` — the column model these dialogs edit (already in
  `lib/`); `tests/test_board_columns_seam.py` — the seam tests.
- `aidocs/framework/tui_conventions.md:347–406` — "an explicit save commits,
  an incidental one never does": the column-manage save path is a commit
  boundary; do not change its behaviour while moving it.

## Implementation plan

1. **Rebase check** (parent pre-phase) over `:6546–6612`, `:7803–7840`,
   `:8017–8397`, `:13300–13340`; pending neighbours **t1404** (column-key
   duplication), **t1441 / t1442** (render markup bugs), **t1714** (column
   CRUD write mutex) — read, do not pre-implement; foreign `Implementing` →
   stop at the checkpoint.
2. Grep-confirm the move set; create the module; replace definitions; import
   pair.
3. C3 sweep + mutants; run the child-1 guards and the characterization golden.
4. Record in this child's plan the final residual class list of
   `aitask_board.py` (`grep -n '^class ' …`) and its line count, for child 11.

## Verification steps

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `python -m pytest tests/test_board_column_manage.py
  tests/test_board_columns_seam.py tests/test_board_package_contract.py
  tests/test_board_fixture_harness.py tests/test_board_keymap_characterization.py -q`
  green; `bash tests/test_shortcut_scopes.py`-equivalent
  (`python -m pytest tests/test_shortcut_scopes.py -q`) green (no new scope —
  verify the dialogs carry no `_shortcuts_scope`; if one does, add the
  manifest row).
- `grep -n '^class ColumnManageScreen\|^class ColumnSelectScreen\|^class ColorSwatch'
  .aitask-scripts/board/aitask_board.py` returns nothing.
- Manual in tmux: `ait board` → column manage (add / rename / recolour /
  reorder / delete a column, then cancel and confirm paths), `m` move a card
  to a chosen column, `M` in By-Trail moves a wave.
