---
Task: t1354_speed_up_python_test_suite.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1354 — Speed up the Python test suite (parent plan / decomposition)

## Context

`bash tests/run_all_python_tests.sh` takes ~12 min (746s, ~2900 tests) and sits
on every task's Step 8b critical path. Measured this session (2026-07-31,
24-core machine, `~/.aitask/venv` CPython 3.14):

- Per-file timing sweep of all 174 modules: top 2 files = 42% (test_board_bytrail_view 165s,
  test_syncer_rows 124s), top 10 = 74%, top 20 = 87%; the other 154 files ≈ 90s.
- Root cause A: board TUI tests `os.chdir(REPO_ROOT)` and boot the real
  `KanbanApp` against the **live** `aitasks/` tree (208 parents + 108 children →
  5,698 widgets, CSS over 3,212 nodes per boot). A/B measured: live tree 2.00s/boot,
  78ms/`pilot.pause()`; 8-task fixture tree 0.21s/boot (9.5x), 25ms/pause (3x).
  `TaskManager.load_tasks()` is only 0.08s — the cost is widget mount + CSS, and
  it grows with every task file added to the repo.
- Root cause B: zero parallelism — pytest is not installed in `~/.aitask/venv`,
  so the runner silently takes the `unittest discover` branch (single process,
  serial). A parallel-safety audit found 172/174 files safe under
  `-n auto --dist loadfile`; 2 blockers.
- The live-tree coupling is also a live correctness bug: folded tasks t1346 +
  t1352 (test_board_work_report.py:483 flakes on concurrent task-file changes /
  a numberless task file; it returned rc=1 in the sweep — failing right now).

User decisions already made: pytest+pytest-xdist are **dev-only opt-in** deps
(not standard install); decomposition into **4 children** approved.

## Acceptance / measurement contract

One denominator: wall time of `bash tests/run_all_python_tests.sh` on this
machine, suite green. Re-measure the baseline at each child's start (the tree
grows; 2026-07-31 numbers are indicative). Projection — not a hard gate:
fixtures ~746s→~280s; + xdist ~60–120s. If a target is missed, present the
data to the user; never silently re-scope (child 4 owns the final read-out).

## Decomposition — 4 children under t1354

Dependencies: 1→2 sequential; 3 independent of 1–2; 4 depends on 1,2,3.

### Child 1 — `board_fixture_harness` (spike: riskiest first)

Build the shared fixture-tree harness and migrate the 2 worst files. Proves
the pattern (full `KanbanApp` Pilot boots against a temp tree) before the bulk
migration, and fixes both folded bugs.

- New `tests/lib/board_fixture.py`: promote `build_tree()` from
  `tests/test_board_movement.py:121` (creates `<tree>/.aitask-data/aitasks/metadata/`,
  one task .md per card via `serialize_frontmatter`, `board_config.json` +
  `board_config.local.json` with `{auto_refresh_minutes:0, sync_on_refresh:False}`,
  `aitasks -> .aitask-data/aitasks` symlink, `git init/commit`) and the
  `_load_board_module(task_dir)` pattern from
  `tests/test_board_decref_doomed_attachments.py:36-52` (sets
  `os.environ["TASK_DIR"]`, imports `aitask_board.py` under a unique synthetic
  module name so import-time constants at `aitask_board.py:66-77` pick up the
  fixture; `lib/config_utils.py:74 task_dir()` reads the env var).
  `tests/test_board_movement.py` and `tests/test_board_persistence_seam.py:66-68`
  import from the promoted location (no fork; keep one seam).
  - Known seams the spike must resolve (choose in-child): with cwd inside the
    temp tree, cwd-relative constants (`DATA_WORKTREE`, `CODEAGENT_SCRIPT`,
    `./.aitask-scripts/aitask_lock.sh` shelled by `refresh_lock_map`
    `aitask_board.py:1084-1091`, git-modified probe `:1066-1069`) either degrade
    gracefully (degrade paths are already tested) or the harness symlinks
    `.aitask-scripts` into the tree. The cheaper `mock.patch.object` alternative
    (documented at `tests/test_board_persistence_seam.py:19-33`) is valid for
    non-boot tests but does NOT update derived constants (`METADATA_FILE` etc.)
    — the harness documents which mode to use when.
  - Fixture shape: parents + children spanning all board columns, with the
    metadata the migrated assertions actually need (≥1 non-board key per task —
    `_is_phantom_stub` drops board-keys-only files).
- Migrate `tests/test_board_bytrail_view.py` (165s; `ByTrailTestBase.setUpClass`
  chdir at `:75`, no TASK_DIR override) and `tests/test_board_work_report.py`
  (26s; base at `:46-57`).
  - t1346/t1352 fix: `test_hidden_cards_still_listed` (`:483`) asserts against
    the fixture column — both sides of the equality from the same fixture
    moment; the existing "skipTest when no populated column" paths become
    unconditional real assertions. Do NOT widen assertions to ranges.
  - Migration rule (coverage guard): where a test's property depends on volume
    or shape (scale, archived tasks, unparseable filenames), the fixture must
    reproduce that shape — including a deliberately numberless
    `t_<name>.md` file to pin the t1352 production filter
    (`TaskCard._parse_filename` drop) behavior.
- Verify: both files green + per-file before/after timing recorded in the plan.

### Child 2 — `migrate_remaining_board_tests` (depends: child 1)

- Re-enumerate live-tree modules at task start (grep `chdir(REPO_ROOT)` in
  `tests/test_*.py` without TASK_DIR override). 2026-07-31 list (~200s):
  test_board_detail_collapsible, test_board_filter_row_layout,
  test_board_view_filter, test_board_topic_view, test_board_scroll_focus_jump,
  test_board_toggle_children_gate, test_board_empty_column_focus,
  test_board_detail_nested_actions, test_board_detail_arrow_nav (+ any smaller
  ones the re-enumeration finds, e.g. settings/shortcut modules reading live
  metadata: test_settings_brainstorm_descriptions.py:27,
  test_profile_editor_shadow_tier.py:150 — read-only; migrate only if cheap).
- Migrate each to the child-1 harness, one file per commit-reviewable step,
  checking each assertion's property survives the fixture shape.
- Add a regression guard test: no `tests/test_board_*.py` may
  `os.chdir(REPO_ROOT)` without a TASK_DIR override. Guard must come with a
  negative control proving it can fail (temporarily seed a violating fixture in
  the test's own tmpdir — not by reverting a real file).
- Verify: migrated files green; guard discriminates (negctrl asserts the
  expected failure id); per-file timings recorded.

### Child 3 — `parallel_test_lane` (independent of 1–2)

- **Dev deps tier** in `.aitask-scripts/aitask_setup.sh`, modeled on the chat
  tier (`AIT_PIP_SPECS_CHAT` `:38`, `install_chat_deps` `:691-712`): new
  `AIT_PIP_SPECS_DEV=('pytest' 'pytest-xdist')` + import-names array + an
  `ait setup --with-dev` flag. CPython venv only (not PyPy/common). No seed
  copy exists to sync (verified). Update setup help text/docs where the other
  `--with-*` flags are listed.
- **Runner** `tests/run_all_python_tests.sh`: in the pytest branch, when
  `xdist` is importable add `-n auto --dist loadfile`; keep the unittest
  fallback byte-identical; never introduce `PYTHONPATH`
  (test_runner_python_isolation.sh greps for it); preserve the t1179 contract —
  last line `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)` on stderr from the
  backend's real exit status. Serial carve-out: run
  `tests/test_board_header_row_live.py` (real board, real git index, 45s hard
  boot budget) after the parallel pool in the same invocation, combining exit
  statuses before the single verdict banner.
- **Blockers/collection fixes:**
  - `tests/test_minimonitor_concern_smoke.py:51` — mkdtemp `TMUX_TMPDIR` +
    `os.getpid()`-suffixed socket (mirror `test_board_header_row_live.py:40`).
  - `tests/test_stats_multistage.py:132,:164` — module-level
    `def test_*(tmp: Path)` helpers error at pytest collection; rename/underscore
    so both backends collect the same set (`test_no_zero_collection.py` is the
    watchdog).
  - Update `tests/test_python_runner_exit_status.sh:293-302` — the exact-argv
    assertion must learn the conditional xdist flags (stub pytest package has no
    xdist → also assert the flags are ABSENT without xdist: both branches).
- Verify: with dev tier installed — parallel run green, verdict contract tests
  green, `--test-dir` subset runs still work; without pytest — unittest branch
  byte-identical behavior.

### Child 4 — `retrospective_measure` (depends: 1, 2, 3)

Bounded retrospective (per planning conventions): re-run the per-file sweep +
the one-denominator full-suite measurement (both backends); record
before/after in the plan. `test_syncer_rows.py` (124s, 136 tests, ~76
`SyncerApp` boots via the `booted()` ctx-manager `:869-913`, fully mocked, not
live-tree-coupled) becomes the per-worker floor under `--dist loadfile` — split
it by test class into 2–3 files ONLY if the measured data shows it is the
binding constraint. File standalone follow-up tasks only where data justifies
them; present results to the user (missed targets are the user's call).

## Manual-verification sibling

Offered at child creation per the workflow (candidate items: t1320 overlap —
runner behavior on a machine WITH real pytest is finally physically testable
once the dev tier is installed).

## Rejected alternatives

- **pytest as a standard dep** — rejected by user (dev-only tier).
- **Sharing one app boot across tests per class** — state leak between tests;
  flake-prone; rejected in favor of making each boot cheap.
- **Trimming `pilot.pause()` calls** — cost is proportional to tree size;
  fixing the tree fixes the pauses (78ms→25ms measured); hand-trimming 932 call
  sites is high-touch for a fraction of the win.
- **PyPy for tests** — out of scope per `aidocs/framework/python_tui_performance.md`
  (only `ait board` routes through PyPy; criteria for reconsidering not met).
- **Range-widened assertions for t1346/t1352** — explicitly rejected in t1346
  (hides real regressions).

## Step 9 (Post-Implementation)

Per-child: standard task-workflow Step 9 (merge/archive on current branch,
fast profile). Parent archives automatically when the last child completes;
folded t1346 + t1352 are deleted at parent archival.

## Risk

### Code-health risk: medium
- Fixture migration can silently weaken what a test proves (live-scale
  properties shrink away) · severity: medium · → mitigation: per-assertion
  review rule in children 1–2 + deliberate shape fixtures (numberless file,
  archived tasks); no separate task.
- Runner change could break the t1179 verdict/exit contract or the t1236
  isolation lane · severity: medium · → mitigation: contract tests updated
  in-child (both flag branches asserted); no separate task.
- xdist under CPU contention makes timing-sensitive tests flaky
  (board_header_row_live 45s budget, board_movement bench) · severity: low ·
  → mitigation: loadfile + serial carve-out designed into child 3.

### Goal-achievement risk: medium
- Full `KanbanApp` boot in a temp tree may trip cwd-relative script seams
  (lock probe, git probe) in unforeseen ways · severity: medium · → mitigation:
  child 1 is deliberately the spike; two fallback strategies documented
  (symlink `.aitask-scripts` vs. degrade paths).
- Projected end-state (~60–120s) may not materialize (worker startup, syncer
  floor) · severity: low · → mitigation: child 4 retrospective with
  user-confirmed disposition of any miss.

Mitigations are internal to the decomposition — no separate before/after
mitigation tasks proposed (`risk_mitigations_planned = false`).
