---
priority: medium
effort: medium
depends: [t1794_11]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1794_1, t1794_2, t1794_3, t1794_4, t1794_5, t1794_6, t1794_7, t1794_8, t1794_9, t1794_10, t1794_11]
assigned_to: dario-e@beyond-eye.com
anchor: 1794
followup_kind: manual_verification
created_at: 2026-09-11 15:12
updated_at: 2026-09-23 16:35
completed_at: 2026-09-23 16:35
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1794_1] `bash tests/run_all_python_tests.sh` last line `PYTHON SUITE: PASSED`. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial
- [x] [t1794_1] The three new/extended test modules green; each negative control recorded red once with its guard disabled. — PASS 2026-09-23 16:27 auto: keymap_characterization 10, package_contract 31, fixture_harness 53 passed; negative-control red runs recorded in p1794_1 Final Notes (20 in-process red runs)
- [x] [t1794_1] `bash tests/test_no_lib_to_tui_import.sh`, `bash tests/test_no_raw_tmux.sh` green; `python -m pytest tests/test_task_dir_module_constants.py -q` green. — PASS 2026-09-23 16:27 auto: test_no_lib_to_tui_import.sh, test_no_raw_tmux.sh exit 0; test_task_dir_module_constants 8 passed
- [x] [t1794_1] `tests/perf/board_footprint.sh` emits three lines and they are in the aidoc. — PASS 2026-09-23 16:27 auto: --runs 1 aitask_board CPython emits provenance/run/summary lines (rss 176.4 MiB); same line shapes as python_tui_performance.md t1794 baseline
- [x] [t1794_1] `ait board` boots in tmux and `q` quits. — PASS 2026-09-23 16:33 auto: ait board booted in private tmux (-L, 200x50) in ~10s; q quit, server exited
- [x] [t1794_2] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial
- [x] [t1794_2] `test_board_followup_glyph`, `test_board_plan_approved_marker`, `test_textual_markup_structure`, `test_board_inflight_view`, `test_board_workflow_phase`, `test_mark_glyphs_single_source`, `test_board_reference_doc_literals`, `test_board_package_contract`, `test_board_fixture_harness`, `test_board_keymap_characterization` green. — PASS 2026-09-23 16:27 auto: all 10 named modules green in suite (0 failures)
- [x] [t1794_2] `grep -n '^class TaskCard\|^class PickerItem\|^class LoadingOverlay' .aitask-scripts/board/aitask_board.py` empty. — PASS 2026-09-23 16:27 auto: grep empty
- [x] [t1794_2] Manual: `ait board` cards render with badges; `z` renders trail cards. — PASS 2026-09-23 16:33 auto: cards render with badges (◇ ▲ ◈ ▼ ✗, effort/labels/status/children/folded); z opened selector, Enter rendered wave lanes with trail cards (classification, conf, drift) + summary pane
- [x] [t1794_3] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial
- [x] [t1794_3] `tests/test_board_bytrail_view.py` green with no assertion changed in intent; child-1 guards and the characterization golden unchanged. — PASS 2026-09-23 16:27 auto: bytrail_view 152 passed; 47 assertions removed in 5d518c967 all re-homed with identical expected values (ab.→tv. / TASKS_DIR arg); keymap golden untouched since c52534f14; guard edits only widen scope
- [x] [t1794_3] Manual: `ait board` → `z` → `s` / `enter` / `v` / `d` work. — PASS 2026-09-23 16:33 auto: in By-Trail s opens selector, Enter on focused card opens entry detail (rationale/wave/drift), v opens summary modal, d shows 'checking freshness…' then stale count; r redraws keeping focus
- [x] [t1794_4] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial
- [x] [t1794_4] `test_board_persistence_seam`, `test_board_manager_moves`, `test_board_movement` (incl. `IsolationNegativeControlTests`), `test_board_column_manage`, `test_followup_kind_phantom_stub`, `test_atomic_task_writes`, `test_board_workflow_phase`, `test_task_dir_module_constants`, `test_board_fixture_harness`, `test_board_package_contract`, `test_board_keymap_characterization` green; mutant list with red runs recorded here. — PASS 2026-09-23 16:27 auto: all named modules green; mutant table with red runs recorded in p1794_4 (## Mutants)
- [x] [t1794_4] `grep -n '^class Task\b\|^class TaskManager\|^def derive_workflow_phase' .aitask-scripts/board/aitask_board.py` empty. — PASS 2026-09-23 16:27 auto: grep empty
- [defer] [t1794_4] Manual: edit a task in `ait board` (updated_at written); move a card. — DEFER 2026-09-23 16:34
- [x] [t1794_5] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `test_board_bytrail_view`, `test_trail_screen_host_protocol`, `test_board_keymap_characterization`, `test_board_package_contract`, `test_board_fixture_harness`, `test_shortcut_scopes` green; `bash tests/test_shortcuts_registry_coverage.sh`, `bash tests/test_no_raw_tmux.sh` green. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial; named modules green; test_shortcuts_registry_coverage.sh, test_no_raw_tmux.sh exit 0
- [x] [t1794_5] Residual `def *trail*` list in `aitask_board.py` recorded here. — PASS 2026-09-23 16:27 auto: residual trail defs in aitask_board.py (6843 lines): _rerender_trail:3012, _restore_trail_focus:3100, action_view_bytrail:3615, _trail_task_target:4929
- [defer] [t1794_5] Manual: `ait board` → `z` → `s r d R v enter M S` as before; `T` hidden in By-Trail, live on a card in the normal view. — DEFER 2026-09-23 16:34
- [x] [t1794_6] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; the listed bash tests and `shellcheck .aitask-scripts/aitask_trails.sh` green; child-1 guards and golden unchanged. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial; test_shortcuts_registry_coverage.sh + test_terminal_compat.sh exit 0; shellcheck aitask_trails.sh only SC1091 info (same as aitask_board.sh), no warnings; golden unchanged
- [defer] [t1794_6] Manual: `ait trails` boots; `j`→`i` from the board and `j`→`b` back; `ait monitor` classifies the window as a TUI; no minimonitor auto-spawn; Settings → Shortcuts lists trail actions once under `board`. — DEFER 2026-09-23 16:34
- [x] [t1794_7] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `test_board_detail_gates_section`, `test_settings_shortcuts_tab`, `test_shortcut_scopes`, `test_board_reference_doc_literals`, `test_board_package_contract`, `test_board_fixture_harness`, `test_board_keymap_characterization` green; `bash tests/test_no_raw_tmux.sh`, `bash tests/test_shortcuts_registry_coverage.sh` green. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial; named modules green; test_no_raw_tmux.sh, test_shortcuts_registry_coverage.sh exit 0
- [x] [t1794_7] `grep -n '^class TaskDetailScreen\|^class .*Field(' .aitask-scripts/board/aitask_board.py` empty. — PASS 2026-09-23 16:27 auto: grep empty
- [defer] [t1794_7] Manual: `enter` on a card; edit every field type; `?` lists `board.detail`; Settings → Shortcuts still lists `board.detail`. — DEFER 2026-09-23 16:34
- [x] [t1794_8] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `test_board_column_manage`, `test_board_columns_seam`, `test_board_package_contract`, `test_board_fixture_harness`, `test_board_keymap_characterization`, `test_shortcut_scopes` green. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial; named modules green
- [x] [t1794_8] `grep -n '^class ColorSwatch\|^class ColumnEditScreen\|^class DeleteColumnConfirmScreen\|^class ColumnSelectItem\|^class ColumnSelectScreen\|^class ColumnManageItem\|^class MergeColumnsConfirmScreen\|^class ColumnManageScreen\|^class ColumnMultiSelectScreen' .aitask-scripts/board/aitask_board.py` empty. (Nine classes, not the three originally listed: the move set widened at implementation time — `ColumnManageScreen` pushes `ColumnEditScreen` / `DeleteColumnConfirmScreen` / `MergeColumnsConfirmScreen`, so leaving those behind would have needed an `import aitask_board` back, which C1 forbids.) — PASS 2026-09-23 16:27 auto: grep for all nine classes empty
- [x] [t1794_8] `python -m pytest tests/test_board_column_dialogs.py tests/test_board_column_dialog.py tests/test_board_columns_reconcile.py -q` green. — PASS 2026-09-23 16:27 auto: column_dialogs 10, column_dialog 40, columns_reconcile 25 passed in suite
- [defer] [t1794_8] Manual — column manage (`e`): add, rename, recolour (colour swatch focus + Enter/space select), shift+↑/↓ reorder, delete — each with its **cancel** path too. — DEFER 2026-09-23 16:34
- [defer] [t1794_8] Manual — **merge** flow end to end (`ColumnMultiSelectScreen` + `MergeColumnsConfirmScreen` both moved): Merge → multi-select sources (space toggles, Enter confirms) → pick destination → confirm; then the same flow cancelled at each of the three steps. Merging into `Unsorted / Inbox` must report that title, not the raw `unordered` id. — DEFER 2026-09-23 16:34
- [defer] [t1794_8] Manual — **Esc-with-changes dismiss result**: make a change in column manage (reorder or merge), then close with **Esc** rather than a button. The board must recompose and show the change immediately (`ColumnManageScreen.handle_escape` returns the `_changed` flag; a `None` here silently leaves a removed column rendered until the next manual refresh). — DEFER 2026-09-23 16:34
- [defer] [t1794_8] Manual: `m` move a card to a chosen column; `M` in By-Trail moves a wave. — DEFER 2026-09-23 16:34
- [x] [t1794_9] Every group (a)/(b) target and plan owner has a `NOTE_APPENDED:` line or a recorded skip; `aitask_query_files.sh inbox 1647_5` shows it unread; `./ait git log --oneline -5` shows the note commits. — PASS 2026-09-23 16:27 auto: 63 from=t1794_9 notes in 63 files / 63 commits; skips recorded in p1794_9; inbox 1647_5 shows t1794_9 note unread
- [x] [t1794_10] `check_links.py --build` exit 0; `hugo build` succeeds; vocabulary scan clean; `test_board_reference_doc_literals` green. — PASS 2026-09-23 16:27 auto: check_links.py --build SWEEP: PASSED exit 0; hugo build exit 0; docs_vocabulary_scan --root . OK; reference_doc_literals 10 passed
- [x] [t1794_10] `grep -rn 'no `ait trail` command' website/content/docs` empty. — PASS 2026-09-23 16:27 auto: grep empty
- [x] [t1794_10] Every documented key exists in `TrailsApp.BINDINGS`; `i` in `_index.md:38`. — PASS 2026-09-23 16:27 auto: every TrailsApp.BINDINGS key documented (M/S under Not available); extra doc keys a/Escape (detail modal), m (board-only); i documented at tuis/_index.md:34 (line drifted from :38)
- [defer] [t1794_10] Manual: `./serve.sh` and read the new page set, index, board reference. — DEFER 2026-09-23 16:34
- [x] [t1794_11] `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`; `bash tests/test_serial_carveout_doc_drift.sh` green. — PASS 2026-09-23 16:27 auto: PYTHON SUITE: PASSED (runner=pytest, exit=0) at 5e378b436 -- 7990 passed/2 skipped + 11 serial; test_serial_carveout_doc_drift.sh exit 0
- [x] [t1794_11] The signed-margin table and verdict exist; `aitask_trails.sh`'s resolver matches the verdict. — PASS 2026-09-23 16:27 auto: signed-margin table + 'Verdict: KEEP CPython' in python_tui_performance.md:508-612; aitask_trails.sh uses require_ait_python
- [x] [t1794_11] `grep -n 'board/aitask_board.py' CLAUDE.md` shows the package description. — PASS 2026-09-23 16:27 auto: literal grep now empty -- CLAUDE.md:143 describes the board/ package (p1794_11 verification used grep 'board/'); intent met
- [x] [t1794_11] Acceptance-criteria walk recorded here. — PASS 2026-09-23 16:27 auto: walk of all 7 parent criteria with evidence in p1794_11 Final Notes

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_6** id=2026-09-18T09:48:55Z.8684e49f579e7a0d7a6c5b58 from=t1794_6 from_verified=yes at=2026-09-18T09:48:55Z base=2070c66aebb47673c80e887e0011c66bf5b70f98 base_branch=main dirty=yes host=omg16
>
> | t1794_6 landed (code commit 2070c66ae). What the implementing session verified by hand in tmux (private socket) and what it did NOT, so your checklist can weight its items. Advisory; re-run everything yourself.
> | 
> | Exercised: `./ait trails` boots into the trail selector with the repo's real trails; `enter` renders the wave lanes with the summary pane and the By-Trail banner; `enter` on a card opens the detail modal, `v` the summary modal, Esc returns with a card focused; footer shows `? q ⏎ r R d s v T` and no `M`/`S`/`m`; from `ait board`, `j` then `i` creates and focuses the `trails` window, `j` then `b` returns; `TUI_NAMES` contains `trails` (monitor classifies the window).
> | 
> | NOT exercised by hand: `R` (agent refresh) and `T` end-to-end launches into a real agent; the artifact-version watch after a refresh; `d` against a genuinely stale artifact; Settings -> Shortcuts listing the trail actions once under `board`; `?` inside `ait trails` on a real terminal (covered by a Pilot probe only); no minimonitor auto-spawn beside the window (inferred from the registry row, not observed); PyPy is not used (launcher is CPython).
> | 
> | Known shared-text oddity: with no trail selected the hint says "create a trail with T on a task card" although the stand-alone shows no cards in that state.

> **👁 note:read** id=2026-09-23T13:19:43Z.39c4b684b6e41f4cecc993d4 by=t1794_12 at=2026-09-23T13:19:43Z mode=explicit ids=2026-09-18T09:48:55Z.8684e49f579e7a0d7a6c5b58
