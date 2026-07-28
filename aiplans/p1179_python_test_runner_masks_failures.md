---
Task: t1179_python_test_runner_masks_failures.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1179 — Python test runner masks failures

## Context

t1179 was filed from t1171's Step 8b review with two upstream defects. Both were
re-checked against live HEAD before planning; the findings differ from the filed
description, and that changes the acceptance criteria — see the explicit
restatement below.

**Defect (2) — order-dependent dual-import `isinstance` failure — is already
fixed.** t1211 (`26af930bb`, landed *after* t1179 was filed) made
`shortcut_scopes`' manifest sweep exec each TUI module under a private
`_PROBE_PREFIX` name instead of its canonical name; that re-binding was what gave
`AgentCommandScreen` a second class identity under full discovery. A full run of
`bash tests/run_all_python_tests.sh` on current HEAD reports
`Ran 2479 tests in 697.662s … OK` and **exits 0**. `test_shortcut_scopes.py` pins
the identity property in both directions, including a negative control. No work
remains for (2).

**Defect (1) is real, but its mechanism is not the one in the report.** The
report says `run_all_python_tests.sh:22-26` "prints `Results: 25 passed, 0
failed` and exits 0". The runner contains no `Results:` line, and its last
command is the pytest/unittest invocation under `set -euo pipefail`, so direct
execution already propagates the framework's status. What actually happens,
reproduced during planning:

- Six *script-style* test modules (`test_prompt_detection.py`,
  `test_idle_compare_modes.py`, …) print their own green tallies
  (`Results: 25 passed, 0 failed`, `PASS: all 7 tests passed`) to **stdout**.
  unittest's verdict (`Ran N tests` / `OK` / `FAILED`) goes to **stderr**.
- Redirected or piped, CPython block-buffers stdout and flushes at process exit
  — **after** stderr's verdict. Measured on a two-file fixture: buffered puts
  `FAILED (failures=1)` on line 14 and the green `Results: 3 passed` on line 15;
  with `PYTHONUNBUFFERED=1` the green line moves to line 1 and `FAILED` to line
  15. In the real suite this leaves ~30 lines of green tallies below the verdict.
- And the common invocation `bash tests/run_all_python_tests.sh 2>&1 | tail -40`
  discards the runner's status: a pipeline exits with `tail`'s `0`. That is where
  the reported "exits 0" came from.

So the runner never lies, but it makes the truth invisible exactly when it
matters.

**Neighbouring contract (must not regress).** t1236 replaced the runner's
`PYTHONPATH` seeding with `unset PYTHONPATH`, recovered onto main as `a39a2611c`
(t1306) mid-planning. `tests/test_runner_python_isolation.sh` fails on *any*
`PYTHONPATH=` assignment on a non-comment line of the runner, and on a missing
`unset PYTHONPATH`. Both guards are green today (9/9). Every choice below is
constrained by that: **nothing in this task touches `PYTHONPATH`.** (The tree is
clean as of `a39a2611c`; the earlier clash with t1306's uncommitted recovery of
this same file is resolved.)

## Acceptance criteria (revised — supersedes the task's literal claim)

The task's literal claim ("the runner prints a false summary and exits 0") is not
reproducible; fixing it as written is a no-op. These criteria replace it and are
what the work should be judged against. **The task file's `## Suggested fix`
section is updated with this restatement as the first implementation step**, so
the AC change is recorded in git rather than left implicit.

1. Direct execution keeps propagating the framework's exit status, now via an
   explicit captured `rc` rather than as an accident of "last command wins".
2. The **last line of the runner's output is always a verdict derived from that
   status** — `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)` — so no per-module
   tally can ever be the last thing a reader sees.
3. Body output is ordered truthfully (`PYTHONUNBUFFERED=1`), so a module's own
   green tally can no longer appear below the framework's `FAILED`.
4. The verdict and exit path are **backend-independent by construction** and
   exercised under *both* the pytest and unittest branches.
5. **Explicitly NOT fixed, and documented as such:** a piped invocation
   (`… | tail`) still exits with the pipeline's last status. No change to this
   script can alter that — only `set -o pipefail` or `${PIPESTATUS[0]}` in the
   *caller* preserves it. Stated in the runner header, in `CLAUDE.md`, and in the
   task's restated AC; the stderr banner is what makes the truth survive
   `2>&1 | tail` even when the status does not.
6. **Explicitly out of scope:** wiring the suite into `.github/workflows/` (the
   report notes CI has zero references to `tests/`). The suite takes ~12 minutes;
   CI wiring is a separate decision, deferred rather than silently absorbed.
7. **No `PYTHONPATH` regression:** `test_runner_python_isolation.sh` and
   `test_python_bootstrap_isolation.sh` stay green.

## Changes

### 1. `tests/run_all_python_tests.sh` — make the verdict unmissable

The current 30-line script keeps its shape (`unset PYTHONPATH` untouched); five
edits:

- **Split `SCRIPT_DIR` from `TEST_DIR`** and accept `--test-dir <dir>` **as the
  first argument only** (consumed with `shift 2`; every remaining argument still
  forwards to the backend). `PROJECT_DIR` keeps resolving from `SCRIPT_DIR`, so
  the `python_resolve.sh` source is unaffected. This is what lets the regression
  test drive the real runner against fixture directories instead of the
  12-minute suite; it also makes subset runs possible. The first-arg-only
  contract is documented in the header and pinned by a test.
- **`export PYTHONUNBUFFERED=1`** beside the existing `PYTHONDONTWRITEBYTECODE=1`.
- **Select a backend into a command array; do not execute inside the branch:**
  ```bash
  if "$PY" -c "import pytest" 2>/dev/null; then
      backend=pytest
      cmd=("$PY" -m pytest "$TEST_DIR"/test_*.py -v "$@")
  else
      backend=unittest
      echo "pytest not found, using unittest discovery"
      cmd=("$PY" -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v "$@")
  fi
  ```
- **One shared execution + verdict tail** outside the branch — this is what makes
  AC 4 structural rather than a promise:
  ```bash
  set +e; "${cmd[@]}"; rc=$?; set -e
  if [ "$rc" -eq 0 ]; then
      echo "PYTHON SUITE: PASSED (runner=$backend, exit=$rc)" >&2
  else
      echo "PYTHON SUITE: FAILED (runner=$backend, exit=$rc)" >&2
  fi
  exit "$rc"
  ```
  stderr is deliberate: it is the stream unittest already uses for `OK`/`FAILED`,
  so the banner lands adjacent to the framework verdict and survives
  `>/dev/null` on stdout.
- **Header comment** stating the `--test-dir` contract and the pipeline caveat
  (AC 5). The isolation guard strips whole-line comments before scanning, so
  prose may mention `PYTHONPATH`; no non-comment line may assign it.

### 2. `tests/test_python_runner_exit_status.sh` (new) — pin it on both backends

House style per `tests/test_gate_declaration_backfill.sh`: `set -u`,
`SCRIPT_DIR`/`PROJECT_DIR`, `. "$PROJECT_DIR/tests/lib/asserts.sh"`,
`PASS`/`FAIL`/`TOTAL`, `Results:` summary, `exit 1` on failure. Skips cleanly
with a printed reason if `require_ait_python` resolves no interpreter.

Fixture modules, generated into `mktemp -d` dirs:

- `test_aa_failing.py` — `self.assertEqual(1, 2)`.
- `test_zz_script_style.py` — passes under the framework **and** prints
  `Results: 3 passed, 0 failed` to stdout, reproducing the six real script-style
  modules that buried the verdict.
- `test_bb_broken_import.py` — `import definitely_not_a_module`; a collection
  error, a different failure channel from an assertion.

**Backend coverage without `PYTHONPATH`.** No interpreter on this machine has
pytest (checked: `python3`, `/usr/bin/python3`, the aitask venv), so an unguarded
fixture test would exercise only the unittest fallback while production prefers
pytest wherever it is installed. The pytest branch is driven by a **stub backend
resolved from the current working directory**: the fixture writes a `pytest/`
package (`__init__.py` + `__main__.py`) into a temp dir and invokes the runner
with that dir as **cwd**. CPython puts cwd on `sys.path` for both `-c` and `-m`,
so the runner's `import pytest` probe succeeds and `"$PY" -m pytest` executes the
stub — with `PYTHONPATH` unset throughout, so t1236's contract and its guard are
untouched. Verified during planning: probe returned `probe ok 0.0.0-stub`, the
stub ran under `-m`, exit code 3 propagated, and argv was recorded verbatim. The
runner resolves `TEST_DIR`/`PROJECT_DIR` from `BASH_SOURCE`, so running it from a
foreign cwd is safe.

The stub covers the pytest branch's *dispatch, argument construction, and verdict
propagation*. It does not simulate pytest's own reporting, and the plan does not
claim it does. On a machine with real pytest, the auto-selection cases exercise
it for real.

Cases (run under both backends unless noted):

1. **Green fixture** → exit 0, output contains `PYTHON SUITE: PASSED`.
2. **Failing fixture** → **non-zero** exit, contains `PYTHON SUITE: FAILED`, does
   *not* contain `PYTHON SUITE: PASSED`. (1 and 2 are two-sided, so the test
   discriminates: a runner hardwired to exit 0 fails case 2; one hardwired
   non-zero fails case 1.)
3. **Banner is the last line** of `2>&1` output in the failing case — the direct
   regression guard for the reported symptom.
4. **Body ordering** (unittest branch): the fixture's `Results: 3 passed, 0
   failed` appears *before* the framework's `FAILED (` line. Verified during
   planning to fail without `PYTHONUNBUFFERED=1`.
5. **Import error** → non-zero, `PYTHON SUITE: FAILED`.
6. **Backend dispatch**: the banner's `runner=` field is `unittest` for a normal
   cwd and `pytest` when run from the stub cwd — a mis-wired branch cannot pass
   silently.
7. **Argument contract** — two assertions:
   - *unittest*: `--test-dir <d> -p 'test_zz_*.py'` narrows the run to the
     passing module → **exit 0**, where the same dir without the extra `-p` exits
     non-zero. Verified during planning that `-p` is last-wins. This pair proves
     both halves: had `shift` consumed one arg, `<d>` would leak in as a
     positional and the run would error; had it consumed three, the `-p` filter
     would be eaten and the failing module would run.
   - *pytest stub*: the recorded `sys.argv[1:]` equals the expanded
     `<dir>/test_*.py` list, then `-v`, then the forwarded args verbatim.
8. **Isolation still holds**: with `PYTHONPATH` exported by the caller, a fixture
   module records `os.environ.get("PYTHONPATH")` as absent — a cheap local guard
   that this task's edits to the guarded file did not reopen t1236's hole.

### 3. `CLAUDE.md` — Testing section

The section documents only the individually-run bash tests. Add the aggregate
Python runner, its `--test-dir` form, its ~12-minute cost, the rule that only the
`PYTHON SUITE:` line is the suite verdict (an earlier `Results:` tally belongs to
one module), and the pipefail/`PIPESTATUS[0]` caveat from AC 5. This is the
durable guard against a future session repeating the misread that produced this
task.

## Verification

```bash
# The new regression test (fast — fixture dirs, both backends, not the real suite)
bash tests/test_python_runner_exit_status.sh          # expect: all pass, exit 0

# The neighbouring contract this task edits around (AC 7) — must stay green
bash tests/test_runner_python_isolation.sh            # expect 9/9
bash tests/test_python_bootstrap_isolation.sh

# Negative control — the test must catch a regression.
#   temporarily replace the runner's `exit "$rc"` with `exit 0`
#     → cases 2/5 must FAIL and the script must exit 1
#   temporarily drop `export PYTHONUNBUFFERED=1` → case 4 must FAIL
#   revert each by undoing the mutation directly — do NOT `git checkout --`
shellcheck tests/run_all_python_tests.sh tests/test_python_runner_exit_status.sh

# Real suite: assert the final-line contract, do not eyeball it (~12 min)
bash tests/run_all_python_tests.sh > /tmp/pyrun.log 2>&1; rc=$?
echo "exit=$rc"
tail -n1 /tmp/pyrun.log \
  | grep -qE '^PYTHON SUITE: (PASSED|FAILED) \(runner=(pytest|unittest), exit=[0-9]+\)$' \
  && echo "FINAL_LINE_OK" || echo "FINAL_LINE_VIOLATION"
# and the verdict must agree with the captured status:
tail -n1 /tmp/pyrun.log | grep -q "exit=$rc" && echo "VERDICT_AGREES" || echo "VERDICT_MISMATCH"
```

Shared checkout: other sessions commit into this working tree. Stage only this
task's paths explicitly; never `git add -A`, and re-check `git diff --cached`
before committing.

## Risk

### Code-health risk: low
- `--test-dir` is a runner-owned first positional that changes the existing
  pass-through contract; a caller passing `--test-dir` intending it for the
  backend, or a `shift` off by one, would silently change test selection ·
  severity: low · → mitigation: none planned (declined) — covered instead by the
  two-sided argument-contract assertion in case 7, which fails on either
  mis-shift.
- The file is freshly guarded by t1236/t1306's isolation lane; an edit that
  reintroduced a `PYTHONPATH` assignment would undo a separately owned fix ·
  severity: low · → mitigation: none planned (declined) — the design touches no
  `PYTHONPATH`, and AC 7 plus case 8 re-run the existing guards.
- Otherwise confined to a developer-only runner, one new test file, and a docs
  paragraph. No framework or TUI code, no runtime path, no callers besides humans
  and the new test.

### Goal-achievement risk: medium
- The task text describes a mechanism that does not exist in the source. This
  plan reframes the goal from "repair a false zero exit" to "make the true
  verdict unmissable", and closes defect (2) as already fixed by t1211 rather
  than re-implementing it. If the user's intent was CI wiring or a literal
  count-derived summary line, the delivered shape would be wrong · severity:
  medium · → mitigation: none planned (declined) — controlled instead by the
  explicit **Acceptance criteria** section above, written into the task file
  before implementation so the reframing is reviewable, not silent.
- Requirement coverage is otherwise complete against the restated AC: status
  propagated explicitly, verdict derived from it, both backends exercised, and a
  regression test asserting non-zero exit against a deliberately failing fixture.

## Post-implementation

Step 9: no branch was created (profile `fast` works on the current branch), so
merge is a no-op; run the gate orchestrator, then archive t1179.
