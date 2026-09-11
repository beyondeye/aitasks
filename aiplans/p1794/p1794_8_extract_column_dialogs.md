---
Task: t1794_8_extract_column_dialogs.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md … t1794_7_*.md, t1794_9_*.md … t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_8 — Extract the column dialogs into `board_column_dialogs.py`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1, C3, C5 PINNED). Last extraction.

## Move set (grep-confirm callers)

`ColorSwatch :7803`, `ColumnSelectItem :8017`, `ColumnSelectScreen :8037`,
`ColumnManageItem :8060`, `ColumnManageScreen :8128–8397`,
`ColumnMultiSelectScreen :6546`. Push sites (`_open_column_manage :13320`,
`_choose_move_destination`) stay in the board and import flat.

## Invariants

- Import pair in `aitask_board.py`; no `_shortcuts_scope` in the moved
  classes (verify; add a manifest row if one exists).
- C3: `tests/test_board_column_manage.py` patch sites (`:95, 695, 713, 729,
  745`) already target `board_task_manager` (child 4); anything the dialogs
  call directly that is patched → repoint to `B.board_column_dialogs` with a
  mutant.
- The column-manage save path is a commit boundary
  (`tui_conventions.md:347–406`) — behaviour unchanged.
- Record the final residual `^class` list and line count of
  `aitask_board.py` under `## Notes for sibling tasks` for child 11.

## Order

Rebase check (t1404, t1441, t1442, t1714 neighbours) → module → import pair
→ C3 sweep → guards/golden → suite → residual record.

## Verification

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`;
  `test_board_column_manage`, `test_board_columns_seam`,
  `test_board_package_contract`, `test_board_fixture_harness`,
  `test_board_keymap_characterization`, `test_shortcut_scopes` green.
- `grep -n '^class ColumnManageScreen\|^class ColumnSelectScreen\|^class ColorSwatch'
  .aitask-scripts/board/aitask_board.py` empty.
- Manual: column manage add/rename/recolour/reorder/delete (+ cancel); `m`
  move; `M` in By-Trail.

## Notes for sibling tasks

(filled at implementation: residual class list + line count for t1794_11)

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_8`.
