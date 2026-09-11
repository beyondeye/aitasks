---
priority: medium
effort: medium
depends: [t1794_11]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1794_1, 1794_2, 1794_3, 1794_4, 1794_5, 1794_6, 1794_7, 1794_8, 1794_9, 1794_10, 1794_11]
anchor: 1794
followup_kind: manual_verification
created_at: 2026-09-11 15:12
updated_at: 2026-09-11 15:12
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1794_1] `bash tests/run_all_python_tests.sh` last line `PYTHON SUITE: PASSED`.
- [ ] [t1794_1] The three new/extended test modules green; each negative control recorded red once with its guard disabled.
- [ ] [t1794_1] `bash tests/test_no_lib_to_tui_import.sh`, `bash tests/test_no_raw_tmux.sh` green; `python -m pytest tests/test_task_dir_module_constants.py -q` green.
- [ ] [t1794_1] `tests/perf/board_footprint.sh` emits three lines and they are in the aidoc.
- [ ] [t1794_1] `ait board` boots in tmux and `q` quits.
- [ ] [t1794_2] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- [ ] [t1794_2] `test_board_followup_glyph`, `test_board_plan_approved_marker`, `test_textual_markup_structure`, `test_board_inflight_view`, `test_board_workflow_phase`, `test_mark_glyphs_single_source`, `test_board_reference_doc_literals`, `test_board_package_contract`, `test_board_fixture_harness`, `test_board_keymap_characterization` green.
- [ ] [t1794_2] `grep -n '^class TaskCard\|^class PickerItem\|^class LoadingOverlay' .aitask-scripts/board/aitask_board.py` empty.
- [ ] [t1794_2] Manual: `ait board` cards render with badges; `z` renders trail cards.
- [ ] [t1794_3] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- [ ] [t1794_3] `tests/test_board_bytrail_view.py` green with no assertion changed in intent; child-1 guards and the characterization golden unchanged.
- [ ] [t1794_3] Manual: `ait board` → `z` → `s` / `enter` / `v` / `d` work.
- [ ] [t1794_4] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- [ ] [t1794_4] `test_board_persistence_seam`, `test_board_manager_moves`, `test_board_movement` (incl. `IsolationNegativeControlTests`), `test_board_column_manage`, `test_followup_kind_phantom_stub`, `test_atomic_task_writes`, `test_board_workflow_phase`, `test_task_dir_module_constants`, `test_board_fixture_harness`, `test_board_package_contract`, `test_board_keymap_characterization` green; mutant list with red runs recorded here.
- [ ] [t1794_4] `grep -n '^class Task\b\|^class TaskManager\|^def derive_workflow_phase' .aitask-scripts/board/aitask_board.py` empty.
- [ ] [t1794_4] Manual: edit a task in `ait board` (updated_at written); move a card.
- [ ] [t1794_5] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `test_board_bytrail_view`, `test_trail_screen_host_protocol`, `test_board_keymap_characterization`, `test_board_package_contract`, `test_board_fixture_harness`, `test_shortcut_scopes` green; `bash tests/test_shortcuts_registry_coverage.sh`, `bash tests/test_no_raw_tmux.sh` green.
- [ ] [t1794_5] Residual `def *trail*` list in `aitask_board.py` recorded here.
- [ ] [t1794_5] Manual: `ait board` → `z` → `s r d R v enter M S` as before; `T` hidden in By-Trail, live on a card in the normal view.
- [ ] [t1794_6] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; the listed bash tests and `shellcheck .aitask-scripts/aitask_trails.sh` green; child-1 guards and golden unchanged.
- [ ] [t1794_6] Manual: `ait trails` boots; `j`→`i` from the board and `j`→`b` back; `ait monitor` classifies the window as a TUI; no minimonitor auto-spawn; Settings → Shortcuts lists trail actions once under `board`.
- [ ] [t1794_7] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `test_board_detail_gates_section`, `test_settings_shortcuts_tab`, `test_shortcut_scopes`, `test_board_reference_doc_literals`, `test_board_package_contract`, `test_board_fixture_harness`, `test_board_keymap_characterization` green; `bash tests/test_no_raw_tmux.sh`, `bash tests/test_shortcuts_registry_coverage.sh` green.
- [ ] [t1794_7] `grep -n '^class TaskDetailScreen\|^class .*Field(' .aitask-scripts/board/aitask_board.py` empty.
- [ ] [t1794_7] Manual: `enter` on a card; edit every field type; `?` lists `board.detail`; Settings → Shortcuts still lists `board.detail`.
- [ ] [t1794_8] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `test_board_column_manage`, `test_board_columns_seam`, `test_board_package_contract`, `test_board_fixture_harness`, `test_board_keymap_characterization`, `test_shortcut_scopes` green.
- [ ] [t1794_8] `grep -n '^class ColumnManageScreen\|^class ColumnSelectScreen\|^class ColorSwatch' .aitask-scripts/board/aitask_board.py` empty.
- [ ] [t1794_8] Manual: column manage add/rename/recolour/reorder/delete (+ cancel); `m` move; `M` in By-Trail.
- [ ] [t1794_9] Every group (a)/(b) target and plan owner has a `NOTE_APPENDED:` line or a recorded skip; `aitask_query_files.sh inbox 1647_5` shows it unread; `./ait git log --oneline -5` shows the note commits.
- [ ] [t1794_10] `check_links.py --build` exit 0; `hugo build` succeeds; vocabulary scan clean; `test_board_reference_doc_literals` green.
- [ ] [t1794_10] `grep -rn 'no `ait trail` command' website/content/docs` empty.
- [ ] [t1794_10] Every documented key exists in `TrailsApp.BINDINGS`; `i` in `_index.md:38`.
- [ ] [t1794_10] Manual: `./serve.sh` and read the new page set, index, board reference.
- [ ] [t1794_11] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `bash tests/test_serial_carveout_doc_drift.sh` green.
- [ ] [t1794_11] The signed-margin table and verdict exist; `aitask_trails.sh`'s resolver matches the verdict.
- [ ] [t1794_11] `grep -n 'board/aitask_board.py' CLAUDE.md` shows the package description.
- [ ] [t1794_11] Acceptance-criteria walk recorded here.
