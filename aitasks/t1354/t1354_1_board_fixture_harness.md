---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [test, tui, board]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus5
created_at: 2026-07-31 07:56
updated_at: 2026-07-31 13:39
---

## Context

First child of t1354 (speed up the Python test suite; parent plan
`aiplans/p1354_speed_up_python_test_suite.md`). The suite takes ~746s; the top
cost is board TUI tests booting the real `KanbanApp` against the **live**
`aitasks/` tree (measured 2.00s/boot + 78ms/`pilot.pause()` live vs 0.21s/boot
+ 25ms/pause on an 8-task fixture tree). This child is the deliberate spike: it
builds the shared fixture harness, proves full `KanbanApp` Pilot boots work
against a temp tree, and migrates the 2 worst files — which also fixes both
bugs folded into the parent (t1346/t1352, preserved under `## Merged from`
headers in `aitasks/t1354_speed_up_python_test_suite.md`).

## Key Files to Modify

- `tests/lib/board_fixture.py` (NEW) — shared harness
- `tests/test_board_bytrail_view.py` (165.6s baseline) — migrate off live tree
- `tests/test_board_work_report.py` (25.9s baseline; **currently failing rc=1**) — migrate + fix t1346/t1352
- `tests/test_board_movement.py` — import promoted helpers from `tests/lib/` (keep behavior identical)
- `tests/test_board_persistence_seam.py` — update its `from test_board_movement import build_tree, ...` (line ~66-68) to the promoted location

## Reference Files for Patterns

- `tests/test_board_movement.py:121` `build_tree(root, cards, *, branch_mode=True, settings=None)` — creates `<tree>/.aitask-data/aitasks/metadata/`, one task `.md` per card via `serialize_frontmatter` (byte-identical re-saves), `board_config.json` (5 columns) + `board_config.local.json` `{"settings": {"auto_refresh_minutes": 0, "collapsed_columns": [], "sync_on_refresh": false}}`, symlink `<tree>/aitasks -> .aitask-data/aitasks`, `git init/add/commit` in `.aitask-data`. Metadata per task from `_META_BASE` (:54-59): priority/effort/issue_type/status + boardcol/boardidx — **at least one non-board key is required** or `TaskManager._is_phantom_stub` (aitask_board.py:921) drops the file and assertions pass vacuously.
- `tests/test_board_decref_doomed_attachments.py:36-52` `_load_board_module(task_dir)` — sets `os.environ["TASK_DIR"]`, imports `aitask_board.py` via `importlib.util.spec_from_file_location` under a unique synthetic module name (`f"aitask_board_t1093_{id(task_dir)}"`), restores env. Import-time constants at `aitask_board.py:66-77` (`TASKS_DIR = task_dir()`, `METADATA_FILE`, `TASK_TYPES_FILE`, `GATES_REGISTRY_FILE`...) resolve through `lib/config_utils.py:74 task_dir()` = `Path(os.environ.get("TASK_DIR", "aitasks"))`.
- `tests/test_board_persistence_seam.py:19-33` documents the cheaper `mock.patch.object(aitask_board, "TASKS_DIR", ...)` alternative (globals read at call time) — valid for non-boot tests but does NOT update derived constants (`METADATA_FILE` etc.); the harness must document which mode to use when.
- `tests/test_task_dir_module_constants.py` (t881) — guard pinning that board constants honor TASK_DIR (fresh-subprocess probing).

## Implementation Plan

1. Re-measure baseline for the two files (`python -m unittest discover -s tests -p <file>` wall time) — record in the plan.
2. Create `tests/lib/board_fixture.py`: promote `build_tree` + `fixture_name` + `_fixture_text`-style helpers and the `_load_board_module` pattern; add a convenience `boot_fixture_board(cards=...)` that returns (module, tree) ready for `KanbanApp().run_test()`. Default fixture shape: a handful of parents + children spanning all board columns.
3. Resolve the cwd seams (spike decision): with cwd inside the temp tree, cwd-relative constants (`DATA_WORKTREE` :71, `CODEAGENT_SCRIPT` :74, the `./.aitask-scripts/aitask_lock.sh --list` shelled by `refresh_lock_map` aitask_board.py:1084-1091, git-modified probe :1066-1069) must either degrade gracefully (degrade paths already tested — test_board_dialog_subprocess_degrade / test_board_refresh_degrade) or the harness symlinks `.aitask-scripts` into the tree. Document the chosen strategy in the module docstring.
4. Point `test_board_movement.py` + `test_board_persistence_seam.py` at the promoted helpers (no logic change; both files must stay green).
5. Migrate `test_board_bytrail_view.py`: replace `ByTrailTestBase.setUpClass`'s `os.chdir(REPO_ROOT)` + live import (:71-81, second site :1022-1025) with the harness. Fixture reproduces what assertions need (live-tree emptiness was previously the "no-trails fixture" — make that explicit with an artifact-less fixture tree).
6. Migrate `test_board_work_report.py` (base :46-57). Fix t1346/t1352: `test_hidden_cards_still_listed` (:483) asserts `sl.option_count` against the fixture column — both sides from the same fixture moment; former `skipTest`-when-empty paths become unconditional real assertions; do NOT widen to ranges. Include a deliberately numberless `t_<name>.md` in the fixture to pin the production filter (`TaskCard._parse_filename` drop at `action_work_report`, aitask_board.py:7271) — the t1352 behavior.
7. Decide separately (surface to user at review): t1352's open sub-question — should board/`ait ls` visibly warn about unparseable task filenames instead of silently dropping them? If kept, propose it as a standalone follow-up task at Step 8b, not buried here.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` subset: the two migrated files + test_board_movement + test_board_persistence_seam green.
- Per-file before/after wall times recorded in the plan (expect ~10x on bytrail).
- Negative check: temporarily rename the fixture's populated column and confirm the migrated work-report test FAILS (proves it's no longer vacuously skipping).
- Full suite green (or failures demonstrably pre-existing).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-31T10:39:20Z status=pass attempt=1 type=human
