---
Task: t1236_pythonpath_isolated_python_test_lane.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1236 — Stop the Python test runner from masking per-file `sys.path` bootstraps

## Context

`tests/run_all_python_tests.sh:17-18` exports `PYTHONPATH` with
`.aitask-scripts/board` and `.aitask-scripts/lib` before invoking pytest /
unittest. Every Python test file already sets up its own `sys.path` from
`__file__`, so that export is pure belt-and-braces — and it actively **hides
bootstrap bugs**: a test whose own `sys.path.insert` points at the wrong
directory still imports fine under the runner and only breaks at TUI runtime.

t1217 flagged this as a code-health risk and defended against it with *manual*
verification steps (an `env -u PYTHONPATH` run plus import assertions). That
only works while someone remembers to run them. This task removes the masking
structurally.

**Measured fallout (done during planning, so the approach is evidence-backed,
not assumed):**

- A discovery-import probe (`unittest.defaultTestLoader.discover('tests')`) run
  both with and without the export reports **0 import failures either way**
  across all 153 `tests/test_*.py` files.
- A static audit of every test file's bootstrap: 144 of 153 manipulate
  `sys.path` themselves; the 9 that don't need no path at all (six load modules
  via `importlib.util.spec_from_file_location` with absolute paths, two only
  read files with `pathlib`/`re`, one shells out to `./ait board` under tmux).
- No test resolves a `board/` or `lib/` module *solely* via the export. The
  closest case, `tests/test_aitask_merge.py:10-15`, imports `gate_ledger` through
  a documented transitive bootstrap inside
  `.aitask-scripts/board/aitask_merge.py:36` — independent of `PYTHONPATH`.
- Nothing else invokes the runner: no CI workflow, no `ait` subcommand, no
  script. The only non-test mention is a doc line in
  `aidocs/framework/sed_macos_issues.md:331`.

So **Option 1 from the task (drop the export) is the honest fix** — the fallout
is zero at import time. Option 2 (a second `env -u PYTHONPATH` lane) is rejected:
it would double an already-long suite run while leaving the masking in place for
the main pass.

One strengthening beyond a bare deletion: the runner should **`unset`**
`PYTHONPATH`, not merely stop adding to it. A developer's ambient `PYTHONPATH`
is exactly the kind of thing that masks a broken bootstrap on one machine and
not another, and the task's own verification criterion is *"the suite passes
with no `PYTHONPATH` inherited from the runner."*

## Changes

### 1. `tests/run_all_python_tests.sh` — scrub `PYTHONPATH` instead of seeding it

Replace lines 17-18:

```bash
# Add board and lib modules to PYTHONPATH for imports
export PYTHONPATH="$PROJECT_DIR/.aitask-scripts/board:$PROJECT_DIR/.aitask-scripts/lib${PYTHONPATH:+:$PYTHONPATH}"
```

with:

```bash
# Do NOT seed PYTHONPATH (t1236). Every test file bootstraps its own sys.path
# from __file__; a runner-supplied path makes a wrong bootstrap pass here and
# fail only at TUI runtime. Any inherited value is scrubbed too, so the suite
# behaves identically regardless of the caller's environment.
unset PYTHONPATH
```

`PYTHONDONTWRITEBYTECODE=1` (line 19) stays. The scrub sits before both the
pytest and the unittest branches, so it covers whichever interpreter path is
taken (this venv has no pytest, so the unittest branch is the live one here).

### 2. `tests/test_runner_python_isolation.sh` — new structural guard

A shell guard in the existing repo style (modelled on
`tests/test_no_lib_to_tui_import.sh`, which sources `tests/lib/asserts.sh` and
prints a PASS/FAIL summary). It pins the change so the export cannot silently
come back:

- Factor the check into a function `check_runner <file>` that fails if the file
  contains a `PYTHONPATH=` assignment/export, and fails if it does not contain
  `unset PYTHONPATH`.
- **Test 1 (live surface):** run `check_runner tests/run_all_python_tests.sh` —
  must pass.
- **Test 2 (negative control — proves the guard discriminates):** copy the
  runner to a temp file, re-insert the old `export PYTHONPATH=...` line, run
  `check_runner` on the copy — must **fail**. A passing negative control means
  the guard is not actually checking anything.
- Header comment documents the detection scope honestly (it is a textual guard
  over one file; it does not detect a `PYTHONPATH` set indirectly through a
  variable or a sourced helper).

Add the standard `# Run: bash tests/test_runner_python_isolation.sh` line.

## Verification

1. **Guard test:** `bash tests/test_runner_python_isolation.sh` → PASS (both the
   live check and the negative control).

2. **Full suite with no inherited `PYTHONPATH`** (the task's primary criterion):

   ```bash
   PYTHONPATH=/nonexistent/poison bash tests/run_all_python_tests.sh
   ```

   Poisoning the inherited value proves the `unset` is doing the work. This run
   is long (>10 min — 153 files including tmux/TUI/git-tempdir tests), so run it
   in the background and read the summary. Import-time fallout is already known
   to be zero; what this run adds is *runtime* fallout — a test that spawns a
   subprocess and relied on inheriting the runner's `PYTHONPATH`. Two tests set
   it themselves for their subprocesses and are self-sufficient
   (`tests/test_no_zero_collection.py:116-120`,
   `tests/test_task_dir_module_constants.py:69-71`). If any other test does fail
   this way, fix **that test's own bootstrap** (give the subprocess an explicit
   `PYTHONPATH`/`sys.path`) — do not restore the runner export.

3. **Negative control (required — this is the whole point of the task):**

   - Break one bootstrap that the old export was masking. `tests/test_history_data.py:20`
     inserts `.aitask-scripts/lib` (needed for `task_yaml`, which
     `history_data` imports) — point it at a nonexistent dir:
     `sys.path.insert(0, str(_scripts / "lib_BROKEN_NEGCTRL"))`.
     (Its *other* insert, `codebrowser` on line 19, was never covered by the
     export, so breaking that one would prove nothing.)
   - **"Before" arm** — reproduce the pre-change runner exactly, without
     restoring the file:

     ```bash
     source .aitask-scripts/lib/python_resolve.sh; PY="$(require_ait_python)"
     PYTHONPATH="$PWD/.aitask-scripts/board:$PWD/.aitask-scripts/lib" \
       PYTHONDONTWRITEBYTECODE=1 "$PY" -m unittest discover -s tests -p 'test_*.py' -k history_data
     echo "before-arm exit: $?"     # expect 0 — the export masks the break
     ```

   - **"After" arm:**

     ```bash
     bash tests/run_all_python_tests.sh -k history_data
     echo "after-arm exit: $?"      # expect NON-ZERO — the break is now visible
     ```

     If `-k` turns out not to filter the discovery-failure placeholder, fall
     back to an unfiltered run of both arms and compare exit codes.

   - **Restore by reversing that single edit** (put `"lib"` back). Do **NOT**
     `git checkout --` the file — this is a shared checkout with unrelated
     uncommitted work (`tests/test_concern_parser.py`, `tests/test_syncer_rows.py`
     and others are currently modified).

4. `bash tests/test_no_lib_to_tui_import.sh` still passes (unaffected, but named
   in the task's acceptance criteria).

5. `shellcheck tests/run_all_python_tests.sh tests/test_runner_python_isolation.sh`.

## Out of scope

Per-invocation `PYTHONPATH=` settings inside individual shell tests
(`tests/test_crew_report.sh`, `tests/test_tmux_control.sh`, and ~8 others) are
deliberate per-command setups for `python -c` heredocs, not a shared masking
lane. They are left alone.

## Risk

### Code-health risk: medium
- Runtime (not import-time) dependence on the inherited `PYTHONPATH` by a test
  that spawns a Python subprocess — the import probe run during planning covers
  module import only, and the full suite was not run to completion during
  planning (>10 min). Bounded: any such failure surfaces in Verification step 2
  and is fixed in that test's own bootstrap · severity: medium
- The new guard is textual (greps one file), so it pins the exact regression it
  was written for but not a `PYTHONPATH` reintroduced indirectly (via a variable
  or a sourced helper). Documented in the guard's header rather than
  over-claimed · severity: low

### Goal-achievement risk: low
- None identified. The measured evidence (0 import failures without the export,
  no CI consumer, no test resolving board/lib solely via the export) shows the
  chosen approach delivers the stated goal, and the required negative control is
  specified concretely enough to prove the masking is gone.

## Step 9 (Post-Implementation)

Current-branch mode — no worktree/branch cleanup. After review and commit,
Step 9 runs the gate orchestrator (`risk_evaluated` is the task's active gate),
then archives via `./.aitask-scripts/aitask_archive.sh 1236`.
