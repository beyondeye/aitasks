---
Task: t1354_3_parallel_test_lane.md
Parent Task: aitasks/t1354_speed_up_python_test_suite.md
Sibling Tasks: aitasks/t1354/t1354_1_board_fixture_harness.md, aitasks/t1354/t1354_2_migrate_remaining_board_tests.md, aitasks/t1354/t1354_4_retrospective_measure.md
Archived Sibling Plans: aiplans/archived/p1354/p1354_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1354_3 — Dev deps tier + pytest-xdist parallel lane

## Goal

Give the Python suite a parallel lane: pytest + pytest-xdist as a **dev-only
opt-in** setup tier (USER DECISION — not standard deps; unittest fallback stays
fully working), `-n auto --dist loadfile` in the runner when xdist is present,
and fix the known parallel blockers + pytest collection errors. Independent of
t1354_1/2.

## Background (pinned from the 2026-07-31 audit)

- pytest absent from `~/.aitask/venv` → runner (`tests/run_all_python_tests.sh:54-62`)
  always takes `unittest discover`: serial, single process.
- 172/174 modules parallel-safe under `--dist loadfile` (mkdtemp discipline,
  throwaway git repos, no network binds, no $HOME writes, ContextVar
  active_app). `loadfile` is MANDATORY — the default `load` splits a file's
  tests across workers, breaking fixed-tmux-socket files
  (test_tmux_exec.py, test_launch_in_tmux_pane_pid.py) and setUpClass fixtures.
- Blockers: `tests/test_minimonitor_concern_smoke.py:51` (fixed socket
  `ait_t1187_smoke` on shared `/tmp/tmux-$UID`, no TMUX_TMPDIR, unconditional
  kill-server); `tests/test_board_header_row_live.py` (real board, real
  `.git/index.lock`, 45s hard boot budget) — must run serially.
- pytest newly collects bare module-level `def test_*` functions unittest
  ignores; `tests/test_stats_multistage.py:132,:164` take a positional arg
  → collection ERROR.

## Steps

1. **Dev tier** in `.aitask-scripts/aitask_setup.sh`, modeled on the chat tier
   (`AIT_PIP_SPECS_CHAT` :38, `install_chat_deps` :691-712, `--with-chat`):
   `AIT_PIP_SPECS_DEV=('pytest' 'pytest-xdist')`,
   `AIT_IMPORTS_DEV=('pytest' 'xdist')`, `install_dev_deps()`,
   flag `ait setup --with-dev`. CPython venv only. Update usage/help text and
   docs listing `--with-*` flags. (No seed copy of the dep list exists —
   verified; `aitask_setup.sh` is the single source.)
2. **Runner** `tests/run_all_python_tests.sh` pytest branch only: when
   `"$PY" -c "import xdist"` succeeds, append `-n auto --dist loadfile` and
   carve `tests/test_board_header_row_live.py` out of the parallel pool — run
   it serially afterwards in the same invocation, combining exit statuses
   (nonzero if either phase failed) before the single verdict banner.
   Env opt-out `AIT_TEST_PARALLEL=0` forces the serial pytest path.
   t1179 contract preserved: last line
   `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)` on stderr from the real
   exit status. NEVER introduce PYTHONPATH
   (`tests/test_runner_python_isolation.sh:52-72` greps for it). Unittest
   branch byte-identical. Note in the header comment: never run the Python
   pool concurrently with `tests/*.sh` (shell suite owns the real git index).
3. **Socket isolation**: `tests/test_minimonitor_concern_smoke.py:51` — mkdtemp
   `TMUX_TMPDIR` + `os.getpid()`-suffixed socket, mirroring
   `tests/test_board_header_row_live.py:40`.
4. **Collection fixes**: `tests/test_stats_multistage.py:132,:164` —
   rename/underscore the positional-arg module-level functions so BOTH backends
   collect the same effective set; sweep the other bare module-level
   `def test_*` files (~6) for new pytest failures. Watchdog:
   `tests/test_no_zero_collection.py` (t1211).
5. **Contract test**: `tests/test_python_runner_exit_status.sh:293-302` — the
   exact-argv assertion (stub pytest package :152-161) must cover BOTH
   branches: stub WITHOUT xdist → flags ABSENT; add a stub-xdist case → flags
   present + carve-out. Prove each new assertion can fail before trusting it.
6. **First real-pytest triage**: latent failures surfaced by a different
   import order (masked sys.path bootstraps, `tests/lib/import_isolated.py:8-16`)
   are pre-existing — fix or file them separately; do not conflate with
   parallelism bugs.

## Verification

- Dev tier installed: full run green, `PYTHON SUITE: PASSED (runner=pytest, exit=0)`,
  wall time recorded. `--test-dir` subsets work; `AIT_TEST_PARALLEL=0` works.
- Contract shell tests green: test_python_runner_exit_status.sh,
  test_runner_python_isolation.sh, test_python_bootstrap_isolation.sh.
- pytest absent: unittest branch behavior byte-identical.
- Flag at review: t1320's "machine WITH real pytest" checklist items are now
  physically testable.
