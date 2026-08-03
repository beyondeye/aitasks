---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: performance
status: Done
labels: [test, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1375, 1376]
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus5
created_at: 2026-07-31 07:56
updated_at: 2026-08-03 09:43
completed_at: 2026-08-03 09:43
---

## Context

Third child of t1354 (parent plan `aiplans/p1354_speed_up_python_test_suite.md`);
independent of t1354_1/t1354_2. The Python suite has zero parallelism: pytest
is not installed in `~/.aitask/venv`, so `tests/run_all_python_tests.sh:54-62`
silently takes the `unittest discover` branch (single process, serial). A
parallel-safety audit (2026-07-31) found 172/174 modules safe under
`-n auto --dist loadfile`: 93/174 use mkdtemp, git only in throwaway repos, no
network binds, no $HOME writes, no fixed /tmp paths, no ordering chains;
Textual's `active_app` is a ContextVar. `--dist loadfile` (NOT the default
`load`) is mandatory — it keeps each file's tests on one worker, which fixes
the fixed-tmux-socket + kill-server races in test_tmux_exec.py /
test_launch_in_tmux_pane_pid.py and stops setUpClass fixtures splitting.

USER DECISION (recorded): pytest + pytest-xdist are a **dev-only opt-in tier**,
NOT standard install deps. The unittest fallback must remain fully working.

## Key Files to Modify

- `.aitask-scripts/aitask_setup.sh` — new dev deps tier
- `tests/run_all_python_tests.sh` — conditional xdist flags + serial carve-out
- `tests/test_minimonitor_concern_smoke.py` — socket isolation (parallel blocker)
- `tests/test_stats_multistage.py:132,:164` — pytest collection errors
- `tests/test_python_runner_exit_status.sh:293-302` — argv contract update
- Website/docs where `--with-*` setup flags are listed

## Reference Files for Patterns

- Setup tiers: `AIT_PIP_SPECS_COMMON` (aitask_setup.sh:29), `AIT_PIP_SPECS_CPYTHON_EXTRA` (:30), parallel import-name arrays (:31-32); the opt-in chat tier `AIT_PIP_SPECS_CHAT`/`AIT_IMPORTS_CHAT` (:38-39) + `install_chat_deps` (:691-712) + `ait setup --with-chat` is the model to copy. Verifiers: `verify_venv_imports` (:44), `verify_venv_specs` (:59). No seed copy of the dep list exists (verified 2026-07-31) — `aitask_setup.sh` is the single source.
- Runner contract (t1179): last line `PYTHON SUITE: PASSED|FAILED (runner=<backend>, exit=N)` on **stderr**, derived from the backend's real exit status; `--test-dir` subset arg; PYTHONPATH scrubbed (t1236).
- Contract tests: `tests/test_python_runner_exit_status.sh` (:293-302 asserts pytest argv is EXACTLY `<globs> -v <forwarded>` via a stub pytest package at :152-161; :275/:286 assert literal banners); `tests/test_runner_python_isolation.sh` (:52-72 greps the runner — any non-comment `PYTHONPATH=` assignment fails, missing `unset PYTHONPATH` fails); `tests/test_python_bootstrap_isolation.sh` (per-file import isolation — xdist prepend import mode is compatible); `tests/test_no_zero_collection.py` (t1211 — both backends must collect every module).
- Socket isolation model: `tests/test_board_header_row_live.py:40` (`f"ait_t1278_hdr_{os.getpid()}"` + kill-server teardown).

## Implementation Plan

1. **Dev tier in setup**: `AIT_PIP_SPECS_DEV=('pytest' 'pytest-xdist')` + `AIT_IMPORTS_DEV=('pytest' 'xdist')`, `install_dev_deps()` modeled on `install_chat_deps` (:691-712), flag `ait setup --with-dev`. CPython venv only (not PyPy, not COMMON). Update setup usage/help text and any docs page listing `--with-chat`/`--with-pypy`.
2. **Runner parallel lane** in `tests/run_all_python_tests.sh`: in the pytest branch only, when `"$PY" -c "import xdist"` succeeds, append `-n auto --dist loadfile` and carve out `tests/test_board_header_row_live.py` from the parallel pool (run it serially in the same invocation afterwards; combine exit statuses — nonzero if either phase failed — before the single verdict banner). Provide an env opt-out (e.g. `AIT_TEST_PARALLEL=0` forces the serial pytest path). Unittest branch byte-identical. Never introduce PYTHONPATH.
3. **Blocker fix**: `tests/test_minimonitor_concern_smoke.py:51` — its fixed socket `ait_t1187_smoke` lives on the shared `/tmp/tmux-$UID` with NO `TMUX_TMPDIR`, fixed session name, unconditional kill-session/kill-server (unsafe even against a second concurrent suite run today). Give it a mkdtemp `TMUX_TMPDIR` + `os.getpid()`-suffixed socket.
4. **Collection fixes**: `tests/test_stats_multistage.py:132` and `:164` — module-level `def test_collect_inflight(tmp: Path)`-style bare functions take a positional arg pytest reads as a missing fixture → collection ERROR (unittest ignores them today, so they run nowhere). Rename/underscore or convert so BOTH backends collect the same effective set (`test_no_zero_collection.py` is the watchdog; also note the ~6 files with bare module-level `def test_*` that pytest newly collects — verify none fail).
5. **Contract test update**: `tests/test_python_runner_exit_status.sh:293-302` — the exact-argv assertion must cover BOTH branches: with the stub pytest (no xdist) flags must be ABSENT; add a stub-xdist case asserting `-n auto --dist loadfile` present + the carve-out behavior. Prove each new assertion can fail before trusting it.
6. First real-pytest run: triage pre-existing latent failures (masked sys.path bootstraps per `tests/lib/import_isolated.py:8-16` may surface under a different import order) separately from parallelism bugs — do not conflate.

## Verification Steps

- With dev tier installed: `bash tests/run_all_python_tests.sh` green, last line `PYTHON SUITE: PASSED (runner=pytest, exit=0)`; wall time recorded (expect single-digit minutes → ~1-3 min pre-child-1/2, faster after).
- `--test-dir` subset runs work under the parallel lane; `AIT_TEST_PARALLEL=0` opt-out works.
- Contract shell tests green: test_python_runner_exit_status.sh, test_runner_python_isolation.sh, test_python_bootstrap_isolation.sh.
- With pytest ABSENT (unittest branch): behavior byte-identical (run the contract test's unittest cases).
- Never run the Python pool concurrently with tests/*.sh (shell suite owns the real git index) — note this in the runner header comment.
- This finally makes t1320's "machine WITH real pytest" checklist items physically testable — flag that at review.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T05:07:03Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-03T06:40:35Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-03T06:43:13Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:dd410f2fd5f5a837

> **✅ gate:risk_evaluated** run=2026-08-03T06:43:13Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1354_3/risk_evaluated_2026-08-03T06:43:13Z-risk_evaluated-a1.log`
