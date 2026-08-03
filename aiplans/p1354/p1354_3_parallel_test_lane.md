---
Task: t1354_3_parallel_test_lane.md
Parent Task: aitasks/t1354_speed_up_python_test_suite.md
Sibling Tasks: aitasks/t1354/t1354_1_board_fixture_harness.md, aitasks/t1354/t1354_2_migrate_remaining_board_tests.md, aitasks/t1354/t1354_4_retrospective_measure.md
Archived Sibling Plans: aiplans/archived/p1354/p1354_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-03 08:05
---

# t1354_3 — Dev deps tier + pytest-xdist parallel lane

## Context

`bash tests/run_all_python_tests.sh` sits on every task's Step 8b verification
path. Siblings t1354_1/t1354_2 (archived) cut it 746s → **400.4s** by moving 17
board TUI modules off the live `aitasks/` tree onto `tests/lib/board_fixture.py`.

The second lever is untouched: the suite has **zero parallelism**. pytest is not
installed in `~/.aitask/venv` (re-confirmed today: `No module named pytest`,
`No module named xdist`), so `tests/run_all_python_tests.sh:51-61` always takes
the `unittest discover` branch — one process, strictly serial, on a 24-core box.

This child adds pytest + pytest-xdist as a **dev-only opt-in setup tier**
(USER DECISION — not standard deps; the unittest fallback must stay fully
working), a bounded `-n 2 --dist loadfile` lane in the runner, and fixes the blockers
that make switching backends unsafe today.

## Plan verification (2026-08-02) — what changed vs. the previous plan

Every claim in the task and the prior plan draft was re-checked against this
checkout. **Ten corrections**, four of them load-bearing.

### 1. The chat-tier model was named wrong, and is missing a piece

The plan says to copy `install_chat_deps` (`:691-712`). That function does not
exist. The real pattern is **two** functions:

- `setup_chat_deps()` — `.aitask-scripts/aitask_setup.sh:694-719`
- `chat_deps_present()` — `:686-689`, the predicate that makes a *plain* later
  `ait setup` revalidate/repair an already-installed tier
  (`if [[ "$INSTALL_CHAT" == "1" ]] || chat_deps_present; then`, `:3607-3610`)

The predicate is the half that keeps an opted-in tier healthy across upgrades;
copying only the installer would silently drop that. Both get a `_dev_` twin.

### 2. There is no setup usage/help text to update

Both the task and the plan say "update setup usage/help text". Verified:
`aitask_setup.sh` has **no** `usage()` and prints no flag list; `ait:98` says
only `setup    Install dependencies`. Neither `--with-pypy` nor `--with-chat`
is documented in any help output. So that step is not actionable as written —
**the real doc surfaces are enumerated in Step 6 below**, from an exhaustive
`--with-*` grep, and introducing a new usage block is out of scope (it would be
a separate UX change affecting three flags, not one).

### 3. `test_board_header_row_live.py:40` is **not** the TMUX_TMPDIR model

Task and plan both say "mkdtemp `TMUX_TMPDIR` + `os.getpid()`-suffixed socket,
mirroring `tests/test_board_header_row_live.py:40`". That line is
`SOCKET = f"ait_t1278_hdr_{os.getpid()}"` — a per-PID socket and **nothing
else**; there is no `TMUX_TMPDIR` anywhere in that file. The mkdtemp-`TMUX_TMPDIR`
half of the recipe comes from two *other* in-repo seams:

- `tests/lib/tmux_isolation.sh` — `require_isolated_tmux` (`TMUX_TMPDIR=$(mktemp -d)`
  + `kill-server`), the canonical policy for tmux-destructive **shell** tests
- `tests/lib/tmux_socket_containment.py:47-51` — `TMUX_TMPDIR` + fixed socket +
  `AIT_NO_SYSTEMD_RUN`, for mock-based Python tests

Both halves are still the right fix; the plan just cited the wrong source for
one of them. Step 3 applies both and says which seam each comes from.

### 4. The collection problem is 17x bigger, and is not "errors" — it is **vacuous passes**

This is the most significant finding. The plan frames Step 4 as "fix two
collection errors, and verify the other ~6 files don't fail". Measured:

**Six** files define module-level `def test_*`, and all six share the *identical*
t1211 script-style shape — a tally-based `assert_eq` that **increments a global
counter instead of raising**, a `main()` driver, and a `ScriptChecksTest`
`unittest.TestCase` wrapper that asserts `main() == 0`:

| file | bare `def test_*` | arg-taking |
|---|---|---|
| `tests/test_stats_multistage.py` | 4 | **2** (`:132`, `:164`) |
| `tests/test_gate_ledger_python_parser.py` | 7 | 0 |
| `tests/test_prompt_detection.py` | 7 | 0 |
| `tests/test_gate_orchestrator_registry.py` | 6 | 0 |
| `tests/test_idle_compare_modes.py` | 5 | 0 |
| `tests/test_stats_include_registered.py` | 1 | 0 |
| **total** | **30** | **2** |

Under pytest:
- the **2** arg-taking ones ERROR at collection (`fixture 'tmp' not found` —
  pytest ships `tmp_path`/`tmpdir`, never `tmp`), exactly as the plan says;
- the other **30 are collected and PASS vacuously.** `assert_eq` never raises, so
  a genuinely failing check is reported as a green pytest test. Worse, they
  *double-run* every check and mutate the module-global `PASS/FAIL/TOTAL` that
  `ScriptChecksTest` then asserts on, so the file's own oracle is corrupted by
  its own collection.

"Verify none fail" is therefore the wrong check — they don't fail, they pass for
the wrong reason. The plan's own stated requirement ("BOTH backends collect the
same effective set") is only met by renaming **all 32** bare `test_*` functions
across **all six** files, not the 2 error sites. Scope grows accordingly, and
Step 4 is rewritten around it.

### 5. A stub-xdist contract test needs a shim the plan never mentions

`tests/test_python_runner_exit_status.sh` steers the backend purely through
**cwd on `sys.path`** (`:20-30`): `$CWD_UNITTEST` holds a `pytest/__init__.py`
that *raises ImportError* so the unittest branch runs even on a machine with real
pytest; `$CWD_PYTEST` holds a stub `pytest` package that records argv.

There is no equivalent for xdist. So the moment `--with-dev` puts real xdist in
the venv, the existing exact-argv assertion (`:293-303`, expecting exactly
`<globs> -v -k smoke`) starts **failing on developer machines and passing on
clean ones** — a machine-dependent contract test. The no-xdist branch must be
made explicit with a blocking `xdist/__init__.py` in `$CWD_PYTEST`, mirroring the
existing pytest-blocking shim at `:146-150`.

### 6. `--dist loadfile` is now load-bearing for 39 modules, not 19

t1354_2's hand-off note says "19 modules". Measured today: **39** of 177
`tests/test_*.py` reference `chdir` or `board_fixture` — the harness chdirs the
process, so the default `--dist load` (which splits a *file's* tests across
workers) would be actively wrong. `loadfile` is mandatory, and now more so.

### 7. Runner line numbers drifted

The pytest/unittest branch is `tests/run_all_python_tests.sh:51-61`, not `:54-62`.

### 8. The parent task's `AITASKS_BOARD_BENCH` risk note is stale

The parent's risk section says "Never set `AITASKS_BOARD_BENCH=1` under `-n auto`".
That variable no longer exists anywhere in `tests/` or `.aitask-scripts/`
(grep: zero hits). Dropped; no action needed.

### 9. Re-audit: the rest of the 2026-07-31 parallel-safety audit still holds

Independently re-swept rather than trusted (it is two days old and two files
landed since):

- **fixed tmux sockets:** exactly one — `test_minimonitor_concern_smoke.py:51`.
  Every other socket literal is `getpid()`-suffixed. The sole blocker, as claimed.
- **network binds:** zero (`.bind(` / `listen(` / `127.0.0.1` / `localhost:` → no hits).
- **`$HOME` writes:** none. The two `expanduser`/`Path.home()` hits
  (`test_agent_marks.py:58`, `test_brainstorm_node_export.py:99`) *compute and
  compare* a path; neither writes.
- **fixed `/tmp` writes:** none. The `"/tmp/x"` / `"/tmp/fake_session"` hits in
  the brainstorm tests are inert constructor arguments, never opened.
- **real-repo `.git/index.lock`:** only `test_board_header_row_live.py` (via the
  real board's `git status --porcelain -- aitasks/`). The four tests that run a
  subprocess with `cwd=REPO_ROOT` are all read-only.
- **pytest layout:** no `conftest.py`, no `pytest.ini`/`pyproject.toml`/`setup.cfg`,
  no `tests/__init__.py` — a flat non-package dir, which is exactly the layout
  `tests/test_python_bootstrap_isolation.sh:24-27` pins as compatible with
  pytest's prepend import mode.

### 10. No timing target is claimed — and the parent's 60-90s is unreachable

The parent's "+xdist → ~60-90s" projection was computed against the *pre*-t1354_1
suite and assumed `-n auto`. Two things invalidate it.

**(a) The worker count is capped at 2, by decision (USER DECISION, 2026-08-03).**
This machine routinely runs ~10 concurrent agents. `-n auto` resolves to
`os.cpu_count()` — 24 here — so a single suite run would oversubscribe the box,
starve every other agent, and produce timings that say more about contention than
about the suite. The lane therefore defaults to **2 workers**, with an explicit
`AIT_TEST_WORKERS` override for anyone on an idle machine.

**(b) The binding constraint changes shape at low worker counts.** t1354_2's
hand-off named `test_syncer_rows.py` (~124s of 400.4s) as "the makespan floor",
which is the right analysis for `-n auto`: with many workers the floor is the
slowest **single file**, because `--dist loadfile` pins a file to one worker. At
`-n 2` that floor (~124s) sits *below* the two-way split of the total work
(~200s), so the constraint is **total work ÷ workers**, not the slowest file.
Consequence worth recording for t1354_4: splitting `test_syncer_rows.py` buys
little at N=2 and only starts to matter as N grows — so its split decision should
be made against the *configured* worker count, not against `auto`.

**No target is claimed here.** The prior draft of this plan asserted ~130-170s;
that figure assumed the uncapped lane and is withdrawn. The speedup under the cap
will be **measured** (Step 7) and reported as measured. Projections were never
gates in this family of tasks, and this one does not get to be an expectation
either. The authoritative before/after comparison remains **t1354_4's**
deliverable, which is also the right place to revisit the default worker count
with data in hand.

### 11. Review-driven hardening (plan review, 2026-08-02)

Five further gaps were raised at plan review; all five verified valid and folded
into the steps above rather than accepted as caveats:

| # | gap | resolution |
|---|---|---|
| a | full-suite claim measured in a **dirty shared checkout** whose untracked board tests the glob picks up — the verdict is not attributable to this task | **Step 7**: snapshot worktree + checked-clean surface, or the claim is deferred to t1354_4 |
| f | the snapshot's `.aitask-data` was linked **live**, so task/plan/metadata could change mid-run — including from this workflow's own gate-ledger commits — and `.gitignore:36` makes `--porcelain` structurally blind to it | **Step 7**: data tree pinned as a second *detached* worktree at a recorded SHA; claim scoped to that code/data pair, with t1354_4 owning the authoritative measurement |
| g | `git worktree remove` refuses on the deliberately-dirty verification tree | **Step 7**: `--force` removal of both worktrees + `prune`, run only *after* evidence is recorded |
| h | deleting the opt-in marker was documented as "opting out", but the runner activates on `import xdist`, so the lane stays on | **Step 1 / Step 6**: provisioning-vs-execution boundary documented as a three-row table; runner-honors-marker coupling considered and rejected with reasons |
| i | `aitasks`/`aiplans` are **untracked** (`.gitignore:37-38`), so a fresh worktree has neither — linking `.aitask-data` alone leaves every relative task/plan path dangling and would yield a green run over an empty tree | **Step 7**: recreate both symlinks in `aitask_init_data.sh:55-56`'s canonical relative form, then `readlink -e` + a non-empty-tree probe before the run counts |
| j | `-n auto` (24 workers) would take the whole machine, starving the ~10 agents normally running here and making timings measure contention | **Steps 2/5/10**: bounded default **`-n 2`** + `AIT_TEST_WORKERS` override, pinned by exact-argv assertion; the ~130-170s target is **withdrawn** — no target is claimed until remeasured under the cap |
| b | `"$@"` forwards to **both** phases, so a positional path selector re-adds the carved module to the parallel pool and runs it twice | **Step 2**: path selectors detected → lane disabled fail-safe; regression-tested |
| c | "both backends collect the same set" was backed only by a six-module spot-check and a unittest-only watchdog | **Step 4b**: real per-file cross-backend parity check over all 177 modules, with a negative control |
| d | the shell-suite header note reads as a safety guarantee but nothing enforces it | **Step 2**: reworded as explicitly unenforced policy; noted as pre-existing and unchanged by this task |
| e | an import-probe `dev_deps_present()` would treat an unrelated pre-installed `pytest` as opt-in consent | **Step 1**: persisted marker outside `$VENV_DIR` instead |

## Steps

### Step 1 — Dev tier in `.aitask-scripts/aitask_setup.sh`

Additive, modeled line-for-line on the chat tier. Nothing enters
`AIT_PIP_SPECS_COMMON` / `_CPYTHON_EXTRA`, so a default install is unchanged.

- After the chat tier block (`:34-39`), add with a comment in the same voice:
  ```bash
  AIT_PIP_SPECS_DEV=('pytest>=8,<9' 'pytest-xdist>=3,<4')
  AIT_IMPORTS_DEV=(pytest xdist)
  ```
- Next to `setup_chat_deps` (`:680-719`), add `dev_deps_present()` and
  `setup_dev_deps()` — same shape as the chat pair: bail with a `warn` if
  `$VENV_DIR/bin/pip` is absent, install, `verify_venv_imports` +
  `verify_venv_specs`, retry once, then `warn` and `return 0`. **CPython venv
  only** — never `$PYPY_VENV_DIR`. Never fails the overall setup.
- **Opt-in is a persisted marker, not an import probe — a deliberate divergence
  from the chat tier.** `chat_deps_present()` infers prior opt-in from
  `import discord`, which is safe only because nobody has `discord` in
  `~/.aitask/venv` by accident. `pytest` is the opposite: a developer may install
  it for unrelated reasons, and an import probe would then read that as consent
  and make a plain `ait setup` install **pytest-xdist** the user never asked for
  — silently converting an opt-in tier into an ambient one. So:
  - `setup_dev_deps()` writes a marker file `$HOME/.aitask/dev_tier` on success;
  - `dev_deps_present()` tests **only** for that marker — never for an importable
    module.

  The marker lives **beside** the venv, not inside it: `setup_python_venv`
  recreates `$VENV_DIR` when the interpreter is too old, and an in-venv marker
  would vanish with it — silently opting the user back out of a tier they chose.
  Outside, a venv recreation correctly triggers a reinstall on the next setup.
- **The marker governs provisioning; it does not govern execution — and the docs
  must not conflate the two.** The runner enables its lane by probing
  `import xdist`, so deleting the marker stops `ait setup` from reinstalling or
  repairing the tier but leaves an already-installed `pytest-xdist` in place and
  the parallel lane **still active**. Calling marker-removal "opting out" would
  therefore be false. Two distinct knobs, documented as such (Step 6):

  | intent | action |
  |---|---|
  | stop the parallel lane for a run / permanently | `AIT_TEST_PARALLEL=0` |
  | stop `ait setup` reinstalling & repairing the tier | remove `$HOME/.aitask/dev_tier` |
  | fully remove the tier | both, plus `~/.aitask/venv/bin/pip uninstall pytest-xdist pytest` |

  *Considered and rejected:* making the runner honor the marker instead. It would
  couple `tests/run_all_python_tests.sh` to setup's private state — the runner
  today depends only on what is importable, which is what makes it testable via
  the cwd shims — and it would leave `AIT_TEST_PARALLEL` as a redundant second
  mechanism. Keeping provisioning (marker) and execution (`AIT_TEST_PARALLEL`)
  on separate knobs is the cleaner layering; the fix is honest documentation of
  the boundary, not a new coupling.
- `main()`: `INSTALL_DEV=0` beside `INSTALL_CHAT=0` (`:3517`), `--with-dev)
  INSTALL_DEV=1; shift ;;` in the case block (`:3521-3522`), and
  `if [[ "$INSTALL_DEV" == "1" ]] || dev_deps_present; then setup_dev_deps; fi`
  after the chat block (`:3607-3610`).
- `shellcheck .aitask-scripts/aitask_setup.sh` must stay clean.

### Step 2 — Parallel lane in `tests/run_all_python_tests.sh`

Only the pytest branch changes. The unittest branch stays **byte-identical**.

- Expand the file glob **once** into an array so the pool and the carve-out are
  provably derived from the same set (a `--test-dir` subset may contain neither).
- Partition by basename against a named constant:
  ```bash
  # Serial carve-out: this module boots the real `ait board` in a tmux pane
  # against the real repo (taking .git/index.lock) under a 45s HARD boot budget
  # that fails rather than skips — so it must not compete with a loaded pool.
  SERIAL_CARVE_OUT=(test_board_header_row_live.py)
  ```
- Enable the lane only when **all three** hold: `"$PY" -c "import xdist"`
  succeeds, `${AIT_TEST_PARALLEL:-1}` is not `0`, and **no forwarded argument is
  a path selector** (next bullet). Then append
  `-n "${AIT_TEST_WORKERS:-2}" --dist loadfile`.
- **The worker count is bounded, never `auto`.** `-n auto` resolves to
  `os.cpu_count()` (24 on this machine). With ~10 agents commonly running
  concurrently here, that would oversubscribe the box, starve the other agents,
  and make every timing a measurement of contention. Default **2**;
  `AIT_TEST_WORKERS` overrides it for an idle machine or for t1354_4's
  measurement sweep. Validate the value is a positive integer and fall back to
  the default with a warning otherwise — it is interpolated into an argv, so a
  malformed value must not reach pytest as a bare token.
- **Forwarded path selectors disable the lane (fail-safe).** Everything in `"$@"`
  is forwarded verbatim to *every* pytest phase. The carve-out only removes
  `test_board_header_row_live.py` from the runner-built array — so
  `bash tests/run_all_python_tests.sh tests/test_board_header_row_live.py` would
  re-add it as a positional to **both** phases: it would run inside the loaded
  parallel pool (losing the `.git/index.lock` and 45s-boot-budget protection the
  carve-out exists to provide) **and** again serially. Partitioning the forwarded
  vector too is not reliably decidable — the runner cannot tell the value `smoke`
  in `-k smoke` from a bare selector without re-implementing pytest's option
  grammar. So the runner instead **detects** path selectors and falls back to the
  plain serial pytest path, printing why:
  - an argument is a path selector if it matches `*.py`, contains `.py::`, or
    names an existing filesystem path;
  - `--test-dir <dir>` remains the supported way to narrow a run, and it is
    unaffected (it is consumed before `"$@"` and rebuilds the array, so both
    partitions stay derived from one set).

  Fail-safe rather than clever: when the invocation shape is not one the
  partition describes, the lane turns itself off instead of silently voiding the
  carve-out. Regression-tested in Step 5.
- Run the serial phase afterwards **in the same invocation**, and combine:
  ```bash
  rc=$?                       # parallel pool
  [[ $rc -eq 0 ]] && rc=$serial_rc      # a phase-1 failure is never masked
  ```
- **Empty-phase guard (not in the prior plan).** `pytest` with no path argument
  collects the *current directory*. If either partition is empty — the normal
  case for `--test-dir <fixture>` — that phase must be **skipped entirely**, not
  invoked with no files. Treat a skipped phase as `rc=0`.
- **Banner contract preserved verbatim.** `backend` stays the literal `pytest`;
  the last line remains `PYTHON SUITE: PASSED|FAILED (runner=pytest, exit=N)` on
  stderr from the real status. *Decision:* a `runner=pytest+xdist` banner would
  be more descriptive but would break `test_python_runner_exit_status.sh:275`
  and `:286`, which assert the literal `runner=pytest, exit=…`. Lane visibility
  instead comes from a separate informational stderr line naming the flags and
  the carve-out — observable and assertable without touching the t1179 contract.
- **Never introduce `PYTHONPATH`.** `tests/test_runner_python_isolation.sh:52-72`
  strips whole-line comments and then fails on *any* remaining `PYTHONPATH=`,
  and separately fails if the bare `unset PYTHONPATH` line disappears.
- Header comment gains: the lane and its opt-out, the carve-out and why, the
  path-selector fallback, and the shell-suite note — the last **explicitly framed
  as an unenforced invocation policy, not a guarantee**. There is no shared lock
  between `run_all_python_tests.sh` and `tests/*.sh`, so a second developer or a
  CI job can still collide with the shell suite over the real git index. Two
  things must be true in the wording: it says *"policy, not enforced — nothing
  here prevents it"*, and it does not imply the parallel lane created the hazard.
  It did not: the collision exists today between the serial suite and the shell
  suite, and `--dist loadfile` neither widens nor narrows it (the one module that
  touches the real index is carved into a serial phase either way). Building real
  cross-suite coordination is a separate change and is out of scope here.

### Step 3 — Socket isolation in `tests/test_minimonitor_concern_smoke.py`

The sole parallel blocker, and unsafe even today against a second concurrent
suite run: socket `ait_t1187_smoke` (`:51`) and session `t1187_concern_smoke`
(`:52`) are both fixed, they live on the shared `/tmp/tmux-$UID`, and
`tearDownClass` (`:135`) calls an unconditional `kill-server`.

- `SOCKET` and `SESSION` become `os.getpid()`-suffixed — the
  `tests/test_board_header_row_live.py:40` model (correction 3).
- `setUpClass` additionally sets a `tempfile.mkdtemp()` `TMUX_TMPDIR` in
  `os.environ` before the first `_tmux()` call, with `addClassCleanup` to
  restore — the `tests/lib/tmux_isolation.sh` / `tmux_socket_containment.py`
  model. It must be set in the *environment* (not just passed to one subprocess)
  because the production path under test — `aitask_shadow_capture.sh` →
  `lib/tmux_exec.sh` — spawns its own tmux and inherits `os.environ`.
  `setUp` already does exactly this for `AITASKS_TMUX_SOCKET` (`:137-146`).
- Drop the unconditional `kill-session` at `:112`: with a per-PID session name
  there is nothing pre-existing to kill.

### Step 4 — Collection parity across both backends (rewritten per correction 4)

In **all six** script-style modules, rename every module-level `def test_*` to
`def _check_*` and update its call site inside that module's `main()`. Nothing
else changes: `main()`, the tally helpers and the `ScriptChecksTest` wrapper stay
exactly as t1211 shipped them.

Result: each file collects exactly one thing — `ScriptChecksTest` — under
**both** backends. The 2 collection errors disappear; so do the 30 vacuous
passes and the double-run counter corruption.

- `tests/test_stats_multistage.py` — 4 renames, `main()` at `:210-217`
- `tests/test_gate_ledger_python_parser.py` — 7, `main()` `:241`
- `tests/test_prompt_detection.py` — 7, `main()` `:174`
- `tests/test_gate_orchestrator_registry.py` — 6, `main()` `:203`
- `tests/test_idle_compare_modes.py` — 5, `main()` `:117`
- `tests/test_stats_include_registered.py` — 1, `main()` `:101`

Watchdog: `tests/test_no_zero_collection.py` (t1211/t1229) asserts every
`tests/test_*.py` still contributes ≥1 collected test and none fails to import.
It probes the **unittest** branch by design (`:11-15`), so it is exactly the
guard against an over-eager rename emptying a file. Its `ZERO_COLLECTION_ALLOWLIST`
(`:50`) must stay `frozenset()`.

### Step 4b — Prove collection parity across backends, don't assert it

`test_no_zero_collection.py` is deliberately unittest-only, and spot-checking the
six renamed modules only covers the files this task touched. Neither supports the
claim "**both** backends collect the same effective set" for the other 171
modules: a pytest-only omission anywhere else would leave the suite green while
the claim is false. Either the check becomes real or the claim must shrink — this
step makes it real.

New `tests/test_collection_parity.py`, structured on the existing probe pattern
in `test_no_zero_collection.py` (subprocess probe, result written to a **file**
not stdout, per-file attribution via `discover(pattern=<exact filename>)`):

- For every `tests/test_*.py`, compare the **per-file collected count** from
  `unittest` discovery against `pytest --collect-only -q <file>`.
- Assert equality per file, and report *all* mismatches at once (name, both
  counts) rather than failing on the first.
- Verified the comparison is well-defined on this tree, so a mismatch means a
  real divergence rather than a known backend quirk: **no** module uses the
  `load_tests` protocol (zero hits); `subTest` (25 modules) expands at *run*
  time and does not change collected counts; and every `class Test*` that does
  not literally spell `unittest.TestCase` inherits it through a base
  (`GitRepoTestBase`, `BrainstormCrewTestBase`, …), so both backends see it.
- `skipUnless` pytest is importable, so it is inert on a machine without the dev
  tier and active on exactly the machines where the claim matters — the same
  machines t1320's "WITH real pytest" checklist was written for.
- Negative control: run the probe against a synthetic tests dir containing a
  module with a bare module-level `def test_*` (pytest collects it, unittest does
  not) and assert the parity check **flags that file by name**. Observed failing
  before the check is trusted — a parity check that cannot detect the exact
  defect class this task just fixed would be decorative.

If parity turns out to be violated by a module for a legitimate backend-semantic
reason, it gets an explicit, justified allowlist entry (empty by design, like
`ZERO_COLLECTION_ALLOWLIST`) — never a silent widening of the assertion.

### Step 5 — Contract test: cover both lanes (`tests/test_python_runner_exit_status.sh`)

- Add a blocking `xdist/__init__.py` (`raise ImportError(...)`) to `$CWD_PYTEST`,
  mirroring the pytest-blocking shim at `:146-150` (correction 5). The existing
  `test_pytest_receives_the_expected_argv` (`:293-303`) then keeps asserting the
  **exact** vector `<globs> -v -k smoke` — flags **ABSENT** — deterministically
  on any machine.
- Add `CWD_PYTEST_XDIST`: stub `pytest` package (reuse the same `__main__.py`
  body) **plus** an importable empty `xdist/__init__.py`. New tests:
  - argv contains `-n`, `2`, `--dist`, `loadfile` and still ends with the
    forwarded args, asserted as an exact vector — this pins `loadfile` over the
    default `load` **and** pins the bounded default against a regression back to
    `auto`;
  - `AIT_TEST_WORKERS=4` produces `-n 4`, and a malformed value (`AIT_TEST_WORKERS=x`)
    falls back to `-n 2` with a warning rather than emitting `-n x`;
  - the carve-out: with a fixture dir containing a stub
    `test_board_header_row_live.py` plus one other module, the pool argv excludes
    the carved file and a **second** stub invocation receives it alone;
  - `AIT_TEST_PARALLEL=0` restores the plain serial pytest vector;
  - exit-status combination: phase-1 failure with phase-2 clean → non-zero
    `FAILED`; phase-1 clean with phase-2 failing → non-zero `FAILED`. The stub's
    `STUB_RC` already supports this; it needs a per-invocation argv file so the
    two phases are distinguishable.
- **Prove each new assertion can fail before trusting it** (project convention,
  and t1354_2's guard needed widening twice for exactly this reason): for each,
  make the corresponding runner behavior deliberately wrong in a *copy* of the
  runner, observe the assertion go red, then restore. Never mutate the real
  runner on disk to demonstrate a control.

### Step 6 — Documentation

Exhaustive `--with-*` grep (excluding archived tasks/plans, CHANGELOG and blog
history, which are historical records and must not be retro-edited) gives the
live surfaces. Three need the new flag or the new lane:

- `CLAUDE.md` → **Testing** section. Currently states the suite takes ~12 min and
  describes only the aggregate runner. Add: the opt-in `ait setup --with-dev`
  tier, the pytest+xdist lane and its **2-worker default plus `AIT_TEST_WORKERS`**
  (with the reason: this machine runs many agents concurrently, so the suite must
  not take the whole box), `AIT_TEST_PARALLEL=0`, the fact that the verdict
  banner still reads `runner=pytest|unittest`, and the **provisioning-vs-execution
  opt-out table** from Step 1 (deleting the marker does *not* stop the lane).
  This is the single most load-bearing doc — it is what every agent reads before
  running the suite.
- `website/content/docs/commands/setup-install.md:29` — lists the venv deps and
  cross-refs the PyPy tier; add the parallel-test dev tier alongside it.
- `tests/run_all_python_tests.sh` header comment — per Step 2.

No new website page, so no `_index.md` bullet is needed.

### Step 7 — Attributable verification surface (do this **before** measuring)

The working checkout is **not** a valid surface for a full-suite claim. An
unrelated concurrent session currently holds modified `.aitask-scripts/board/aitask_board.py`,
modified `tests/test_board_movement.py` and `tests/test_board_persistence_seam.py`,
and **untracked** `tests/test_board_manager_moves.py` + `tests/test_board_ordering.py`
— and the runner's `test_*.py` glob picks untracked files up. Recording that as a
caveat is not enough: those files can be edited, added or removed *during* a
10-minute measurement, so neither a green verdict nor a wall-clock number would be
attributable to this task. Worse, `aitask_board.py` is imported by many board
tests, so a failure there could be misread as a parallelism bug in Step 7's triage.

So the full-suite verification runs in a **snapshot worktree** — and, critically,
**both** halves of the tree are pinned to a revision. This repo runs in
data-branch mode: `aitasks/` and `aiplans/` are symlinks into `.aitask-data/`,
itself a worktree on the `aitask-data` branch. Linking that back **live** would
leave the task/plan/metadata tree free to change mid-run — including from *this
very workflow*, whose gate-ledger appends and status writes commit into
`aitasks/` while the suite is running. And it could not even be detected:
`.aitask-data/` is in `.gitignore:36`, so `git status --porcelain` is
structurally blind to it. Freezing it is therefore not optional.

```bash
data_sha="$(git -C .aitask-data rev-parse HEAD)"     # pin the data revision
git worktree add --detach ../t1354_3_verify_data "$data_sha"
git worktree add --detach ../t1354_3_verify HEAD     # pin the code revision

cd ../t1354_3_verify
ln -s "$(cd ../t1354_3_verify_data && pwd)" .aitask-data
# The two entry-point symlinks are UNTRACKED (.gitignore:37-38), so a fresh
# worktree has neither. Recreate them in the canonical relative form used by
# aitask_init_data.sh:55-56 — not absolute, so the tree stays relocatable.
ln -sfn .aitask-data/aitasks aitasks
ln -sfn .aitask-data/aiplans aiplans
```

**Then prove they resolve, before the run counts for anything:**

```bash
readlink -e aitasks && readlink -e aiplans          # both must print a real path
[ -d aitasks/metadata ] && [ -d aiplans ] || echo "SNAPSHOT NOT REPRESENTATIVE"
ls aitasks/t*.md >/dev/null                          # non-empty task tree
```

This check is not ceremony. `aitasks/` and `aiplans/` are gitignored
(`.gitignore:37-38`) and therefore **absent** from any fresh worktree —
`git ls-files aitasks aiplans` returns nothing. Without recreating them, every
relative `aitasks/...` / `aiplans/...` path in both the tests and production code
(e.g. `aitask_board.py:3735-3740`) would point at nothing, and the pinned data
worktree would sit there unreferenced. The failure mode is quiet: the board's
cwd-relative helpers already degrade silently (t1354_2 documented eight of them),
so a broken snapshot would not crash — it would produce a **green run over an
empty task tree**, i.e. exactly the vacuous pass this whole task exists to
eliminate. The `ls aitasks/t*.md` probe is what distinguishes "resolves" from
"resolves to something real".

- Two **detached** worktrees, so neither competes for a checked-out branch and
  neither can be advanced by another session. The data worktree is a real git
  worktree rather than an extracted tarball because the board runs
  `git status --porcelain -- aitasks/` (`aitask_board.py:1067`) — a plain
  directory would change those code paths' behavior and make the run prove
  something other than production.
- Record `data_sha` and the code `HEAD` in the plan's results table. The run is
  attributable to *that pair*, and says so.
- Copy in **only this task's changed files**, then check the code surface before
  trusting any number:
  ```bash
  git -C ../t1354_3_verify status --porcelain   # must list ONLY this task's files
  ```
  Untracked strays reachable by the `test_*.py` glob must be absent. Attribution
  is then *checked* for the code half and *pinned by SHA* for the data half —
  which is the part `--porcelain` can never show.
- **Never commit from either worktree.** All commits happen in the primary
  checkout.
- **Cleanup is deliberately forced.** The code worktree is intentionally dirty
  (this task's files were copied in), so a plain `git worktree remove` refuses.
  After the evidence is recorded in the plan:
  ```bash
  git worktree remove --force ../t1354_3_verify
  git worktree remove --force ../t1354_3_verify_data
  git worktree prune
  ```
  `--force` here discards only the deliberately-copied verification scratch, and
  it is run **after** the numbers are written down — never before.

**Scope of the claim, stated rather than implied.** Even pinned, this run is a
*this-task-in-isolation* signal: it shows the lane and the collection changes
leave the suite green and gives a timing figure for one code/data pair. The
**authoritative** before/after measurement across all of t1354 remains
**t1354_4**'s primary deliverable — it runs after this work lands, on a settled
tree, and owns the projected-vs-achieved reconciliation.

**Fallback, if the snapshot proves infeasible:** do **not** report a full-suite
claim at all. Narrow the reported verification to the targeted set — the contract
shell tests, the six renamed modules, `test_collection_parity.py`,
`test_no_zero_collection.py` and the minimonitor smoke — and say plainly that the
suite-level number is deferred to t1354_4. Reporting a number that cannot be
attributed is worse than reporting none.

### Step 7b — First real-pytest run and triage

Install the tier (`./ait setup --with-dev`), then run the suite **in the snapshot
worktree**. Two failure classes must be kept apart and **not** conflated:

1. **Pre-existing latent failures** surfaced by a different import order — the
   masked `sys.path` bootstraps that `tests/lib/import_isolated.py:8-16`
   documents. These are t1236-class defects, not parallelism bugs. Fix in place
   if trivial; otherwise record them under "Upstream defects identified" in the
   Final Implementation Notes and let Step 8b offer the follow-up.
2. **Genuine parallelism bugs** — reproduce serially first
   (`AIT_TEST_PARALLEL=0`); a failure that also reproduces serially is class 1.

## Verification

- `shellcheck .aitask-scripts/aitask_setup.sh` clean.
- **Dev tier installed:** `bash tests/run_all_python_tests.sh` green, last line
  `PYTHON SUITE: PASSED (runner=pytest, exit=0)`. Read **only** that line; when
  piping, use `set -o pipefail` / `${PIPESTATUS[0]}` (the banner is on stderr,
  the exit status is not).
- `--test-dir <subset>` works under the lane (exercises the empty-phase guard);
  `AIT_TEST_PARALLEL=0` produces the serial pytest vector; a forwarded `*.py`
  path selector disables the lane instead of double-running the carved module.
- **pytest absent** (from `$CWD_UNITTEST`): unittest branch byte-identical —
  the contract test's five unittest cases still green.
- Contract shell tests green: `test_python_runner_exit_status.sh` (incl. every
  new lane assertion **observed failing** first), `test_runner_python_isolation.sh`,
  `test_python_bootstrap_isolation.sh`.
- `tests/test_no_zero_collection.py` green with an empty allowlist.
- `tests/test_collection_parity.py` green over **all 177 modules** with an empty
  allowlist, and its negative control observed flagging a synthetic bare
  module-level `def test_*` before the check is trusted. This — not a six-module
  spot-check — is what backs the "both backends collect the same effective set"
  claim; without it the claim is narrowed in the Final Implementation Notes.
- `tests/test_minimonitor_concern_smoke.py` green standalone **and** while a
  second copy of it runs concurrently — the property the fixed socket broke.
- **Every full-suite claim — green verdict and wall clock alike — comes from the
  Step 7 snapshot worktree**, with `git status --porcelain` in it shown to list
  only this task's files. Both runs use one denominator on the same machine, and
  the record names the worker count, both pinned SHAs, and the machine's
  concurrent load at the time. **No target is asserted** (correction 10): the
  speedup under the 2-worker cap is reported as measured, not compared against a
  withdrawn projection. An *unattributable* number is not presented at all
  (Step 7 fallback — the measurement is t1354_4's deliverable).
- Flag at review: this finally makes **t1320**'s "machine WITH real pytest"
  checklist items physically testable.

## Risk

### Code-health risk: medium
- `tests/run_all_python_tests.sh` is on every task's verification path, and the
  two-phase carve-out changes how the exit status is derived — a mistake makes a
  **failing** suite read green, which is the exact t1179 defect this file exists
  to prevent · severity: **high** · → mitigation: the banner/backend string is
  left byte-identical (explicit decision in Step 2); both phase-failure
  directions get their own contract assertion, each **observed failing** on a
  deliberately-broken copy of the runner before being trusted (Step 5)
- Renaming 32 functions across six files changes what *both* backends collect; an
  over-eager rename could empty a file back to the zero-collection state t1211
  fixed · severity: medium · → mitigation: `tests/test_no_zero_collection.py`
  already guards exactly this and probes the unittest branch by design; it is run
  explicitly with `ZERO_COLLECTION_ALLOWLIST` kept empty (Step 4)
- The "both backends collect the same effective set" claim would otherwise rest
  on a six-module spot-check plus a unittest-only watchdog, so a **pytest-only
  omission in any of the other 171 modules** could leave the suite green while
  the claim is false · severity: medium · → mitigation: `test_collection_parity.py`
  compares per-file collected counts across both backends over every module, with
  a negative control observed flagging the exact defect class this task fixes
  (Step 4b); if it cannot be made to hold, the claim is narrowed rather than kept
- Forwarding `"$@"` verbatim to both phases lets a positional path selector
  re-add the carved module to the parallel pool, voiding its `.git/index.lock` /
  boot-budget protection *and* running it twice · severity: medium ·
  → mitigation: path selectors detected and the lane disabled fail-safe rather
  than partially partitioned, with a regression test (Steps 2 and 5)
- The runner's "never run concurrently with `tests/*.sh`" note is an **unenforced
  policy** — no shared lock exists, so a second developer or CI job can still
  collide over the real git index · severity: low · → mitigation: stated as
  policy-not-guarantee in the header comment rather than implying safety, and
  noted as pre-existing (the hazard is unchanged by this task; cross-suite
  coordination is a separate change, out of scope)
- Editing `aitask_setup.sh` touches the install flow every user runs · severity:
  medium · → mitigation: purely additive tier that never joins COMMON/CPYTHON_EXTRA,
  copied from the shipped chat tier including its `return 0`-on-failure contract,
  so a broken/offline dev tier cannot brick setup; `shellcheck` in Verification
- An import-probe `dev_deps_present()` would read a pre-existing unrelated
  `pytest` as prior consent and make a plain `ait setup` install **pytest-xdist**
  for a user who never passed `--with-dev`, silently turning an opt-in tier into
  an ambient dependency · severity: low · → mitigation: opt-in is a persisted
  marker (`$HOME/.aitask/dev_tier`), never an importable module; placed outside
  `$VENV_DIR` so a venv recreation cannot silently opt the user back out (Step 1)
- The marker governs **provisioning** while the runner activates on
  `import xdist`, so a user who deletes the marker expecting to "opt out" still
  gets parallel execution — a documented action that would not do what it says ·
  severity: low · → mitigation: the two knobs are separated by design and the
  boundary is documented as a three-row table in both Step 1 and `CLAUDE.md`
  (`AIT_TEST_PARALLEL=0` for execution, marker for provisioning, both plus an
  uninstall for full removal); coupling the runner to setup's private state was
  considered and rejected, with the reason recorded in Step 1
- Parallel workers where the suite has only ever run one could surface *new*
  flakiness that a single green run will not reveal; and an unbounded `-n auto`
  (24 here) would additionally starve the ~10 agents this machine commonly runs,
  turning every timing into a contention measurement · severity: medium ·
  → mitigation: the worker count is **bounded at 2** by decision with an
  `AIT_TEST_WORKERS` override, and the bounded default is pinned by an exact-argv
  assertion so it cannot regress to `auto` (Steps 2 and 5); `--dist loadfile` pinned and asserted
  in the argv contract (Step 5), the real-board module carved out to a serial
  phase, and `AIT_TEST_PARALLEL=0` as a first-class opt-out. Repeat-run flake
  hunting is **t1354_4**'s declared scope (its step 4) and is deliberately not
  duplicated here
- The six script-style modules keep a tally-based `assert_eq` that never raises,
  so the *class* of defect (a module-level `def test_*` passing vacuously under
  pytest) can silently return the next time someone adds one · severity: low ·
  → mitigation: `bare_module_test_fn_guard`
- This adds a **third** opt-in `--with-*` tier while none of the existing two
  appears in any help output (correction 2), compounding a discoverability gap
  rather than introducing one · severity: low · → mitigation:
  `setup_with_flags_usage`

### Goal-achievement risk: medium
- The first real-pytest run has never happened in this checkout (t1320), so the
  volume of latent pre-existing failures it surfaces is genuinely unknown and
  cannot be measured before installing the tier · severity: medium ·
  → mitigation: Step 7 separates the two failure classes by construction
  (re-run serially to classify), the unittest fallback stays fully working as a
  known-good reference, and class-1 defects are routed to the Step 8b upstream
  follow-up rather than absorbed silently
- The parent's headline projection (60-90s) is unreachable — it assumed `-n auto`,
  and the lane is now capped at 2 workers — so the delivered speedup will be
  visibly smaller than the parent task advertises · severity: medium ·
  → mitigation: no replacement target is claimed (correction 10); the result is
  measured and reported as measured, the cap's rationale is recorded, and
  t1354_4 revisits the worker count with data
- At `-n 2` the binding constraint is total work ÷ workers (~200s), not the
  slowest single file (~124s), so t1354_2's "makespan floor" hand-off note no
  longer describes this configuration and could mislead t1354_4 into splitting
  `test_syncer_rows.py` for little gain · severity: low · → mitigation: the
  shift is stated explicitly in correction 10 and flagged in the Notes for
  sibling tasks, so the split decision is made against the *configured* worker
  count rather than against `auto`
- The attributable-measurement requirement depends on an unrelated session's
  uncommitted work, which this task does not control, so the suite-level number
  may have to be deferred · severity: low · → mitigation: the Step 7 snapshot
  worktree removes the dependency in the normal case; if it cannot be made to
  work, the number is deferred to **t1354_4** (which owns it as its primary
  deliverable) rather than reported unattributably — the *correctness* claims
  all rest on targeted tests that do not need a clean full-suite run
- The verification snapshot is itself hand-assembled (two detached worktrees plus
  three recreated symlinks), and a mis-built one fails **silently**: the board's
  cwd-relative helpers degrade without raising, so a dangling `aitasks` link
  yields a green run over an empty task tree rather than an error · severity:
  medium · → mitigation: the snapshot is not trusted until `readlink -e` resolves
  both entry points **and** a non-empty-tree probe passes; the symlink form is
  copied from the canonical `aitask_init_data.sh:55-56` rather than invented
  (Step 7)
- The unittest branch must stay byte-identical for users who never opt in, but
  "byte-identical" is asserted only by the contract test's five unittest cases ·
  severity: low · → mitigation: the unittest branch is genuinely not edited (the
  partition/lane logic lives entirely inside the pytest arm), and the contract
  test runs both arms from cwd shims that make the backend deterministic
  regardless of what is installed locally

### Planned mitigations
- timing: after | name: bare_module_test_fn_guard | type: test | priority: low | effort: low | addresses: code-health — the vacuous-pass class can silently return | desc: Structural guard asserting no `tests/test_*.py` defines a module-level `def test_*` (they pass vacuously under pytest because the script-style `assert_eq` tallies instead of raising), with a negative control proving the guard flags a synthetic offender
- timing: after | name: setup_with_flags_usage | type: enhancement | priority: low | effort: low | addresses: code-health — install-flow discoverability | desc: Add a `usage()` to `aitask_setup.sh` enumerating the three opt-in tiers (`--with-pypy`, `--with-chat`, `--with-dev`) and surface it via `ait setup --help`; none of them appears in any help output today

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no worktree to remove; output branch `main`
per this plan's header. Run the declared gates (`./ait gates run 1354_3`), then
archive with `./.aitask-scripts/aitask_archive.sh 1354_3`.
