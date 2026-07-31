---
Task: t1354_1_board_fixture_harness.md
Parent Task: aitasks/t1354_speed_up_python_test_suite.md
Sibling Tasks: aitasks/t1354/t1354_2_migrate_remaining_board_tests.md, aitasks/t1354/t1354_3_parallel_test_lane.md, aitasks/t1354/t1354_4_retrospective_measure.md
Archived Sibling Plans: aiplans/archived/p1354/p1354_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1354_1 — Board fixture harness + migrate the two worst files (spike)

## Goal

Build the shared board-fixture harness in `tests/lib/board_fixture.py`, prove
full `KanbanApp` Pilot boots work against a temp task tree, and migrate
`tests/test_board_bytrail_view.py` (165.6s baseline) and
`tests/test_board_work_report.py` (25.9s baseline, currently failing rc=1).
Fixes the two bugs folded into the parent (t1346/t1352 — see `## Merged from`
sections in `aitasks/t1354_speed_up_python_test_suite.md`).

## Why this shape (from the parent plan)

Live-tree boot measured at 2.00s + 78ms/`pilot.pause()`; 8-task fixture tree
0.21s + 25ms. `TaskManager.load_tasks()` is only 0.08s — the cost is widget
mount + CSS over 316 live task cards. This child is deliberately the riskiest
spike: if full-app boots can't be made fixture-clean, the parent approach needs
rethinking before t1354_2 does the bulk migration.

## Steps

1. **Baseline**: re-measure both files (`python -m unittest discover -s tests
   -p <file>`, wall time); record here.
2. **Harness** `tests/lib/board_fixture.py`:
   - Promote `build_tree()` (+ `fixture_name`, fixture-text builders) from
     `tests/test_board_movement.py:121` — it already creates
     `.aitask-data/aitasks/metadata/`, per-card task files via
     `serialize_frontmatter`, `board_config.json` + `board_config.local.json`
     (`auto_refresh_minutes: 0`, `sync_on_refresh: false`), the
     `aitasks -> .aitask-data/aitasks` symlink, and `git init/commit`.
   - Promote the `_load_board_module(task_dir)` pattern from
     `tests/test_board_decref_doomed_attachments.py:36-52` (TASK_DIR env +
     unique synthetic module name via `spec_from_file_location`; constants at
     `aitask_board.py:66-77` resolve via `lib/config_utils.py:74`).
   - Add a convenience boot helper (e.g. `boot_fixture_board(cards)`) returning
     a ready module + tree for `KanbanApp().run_test()` tests.
   - **Spike decision to make here**: cwd-relative seams when chdir'd into the
     tree — `DATA_WORKTREE` (:71), `CODEAGENT_SCRIPT` (:74),
     `refresh_lock_map`'s `./.aitask-scripts/aitask_lock.sh --list`
     (aitask_board.py:1084-1091), git-modified probe (:1066-1069). Either rely
     on the tested degrade paths or symlink `.aitask-scripts` into the tree.
     Document the choice + the boot-mode vs `mock.patch.object` patch-mode
     rule (see `tests/test_board_persistence_seam.py:19-33` — patch-mode does
     NOT update derived constants) in the module docstring.
   - Fixture tasks need ≥1 non-board metadata key or
     `TaskManager._is_phantom_stub` (aitask_board.py:921) drops them.
3. **Re-point existing importers**: `tests/test_board_movement.py` and
   `tests/test_board_persistence_seam.py:66-68` import the promoted helpers
   (no logic change; both stay green).
4. **Migrate `test_board_bytrail_view.py`**: replace both
   `os.chdir(REPO_ROOT)` + live-import sites (`ByTrailTestBase.setUpClass`
   :71-81 and :1022-1025) with the harness. The live tree's artifact-less
   state was the implicit "no-trails fixture" — make that an explicit
   artifact-less fixture tree.
5. **Migrate `test_board_work_report.py`** (base :46-57) and fix t1346/t1352:
   - `test_hidden_cards_still_listed` (:483): both sides of the equality from
     the same fixture moment; former skipTest-when-empty paths become
     unconditional assertions; NO range-widening.
   - Include a deliberately numberless `t_<name>.md` in the fixture to pin the
     production filter behavior (`TaskCard._parse_filename` drop in
     `action_work_report`, aitask_board.py:7271).
6. **Surface at review (Step 8b)**: t1352's open sub-question — should
   board/`ait ls` warn visibly about unparseable task filenames instead of
   silently dropping them? Propose as standalone follow-up if kept.

## Verification

- Both migrated files + test_board_movement + test_board_persistence_seam
  green; per-file before/after timings recorded here (expect ~10x on bytrail).
- Negative check: break the fixture's populated column and confirm the
  migrated work-report test FAILS (no vacuous skips).
- Full suite green or failures demonstrably pre-existing.
