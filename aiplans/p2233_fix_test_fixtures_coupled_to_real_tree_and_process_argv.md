---
Task: t2233_fix_test_fixtures_coupled_to_real_tree_and_process_argv.md
Base branch: main
Output branch: main
---

# t2233 — test fixtures coupled to the real tree and to the runner's argv

## Context

t2233 names two upstream test defects found during t2211_2's review:

1. `tests/test_board_movement.py` `IsolationNegativeControlTests` asserted
   that the **live** `aitasks/` tree holds no `*_fixture.md` file, so any real task
   with that suffix (t2226 has one today) made it fail.
2. `tests/test_sitrep_window.py` uses `LIVE_PID = os.getpid()` as a "not a
   companion" pane pid. Fixtures that reach `monitor_core._is_companion_process`
   (the cmdline rung of `pane_is_helper`) read the **runner's own**
   `/proc/<pid>/cmdline`, so when the runner's argv contains `minimonitor` or
   `monitor_app` (`_COMPANION_KEYWORDS`, `monitor_core.py:404`) the "agent"
   fixture turns into a companion.

### Reality check (measured during planning)

- **Defect 1 is already fixed, by another task that is still in flight.**
  t2230 (status `Implementing`, same user) has the fix as step 5 of its plan
  (`aiplans/p2230_…md:175`). The fix is in the working tree, uncommitted: the
  control is now hermetic and builds two temp roots with sentinels. As the
  tree stands, `pytest tests/test_board_movement.py -k IsolationNegativeControl`
  gives `1 passed`. Under the "gate on in-flight / shared file" rule, **t2233
  does not touch `tests/test_board_movement.py`**. That file is t2230's to
  commit. Its outcome is recorded below in "Disposition of defect 1".
- **Defect 2 reproduced.** `python -m unittest tests.test_sitrep_window
  tests.test_minimonitor_sibling_fallback` → `FAILED (failures=22)`, all of them
  in `MatcherTests`, `ClassifyParityTests`, `SpawnTests` and `RoleSpawnTests`.
  The same module run alone → 79 OK.
- **Blast radius measured, not assumed.** I probed the module itself plus 15
  other test modules that use `os.getpid()` near pane-format or companion
  code. Each one ran twice in a child Python whose cmdline either did or did
  not carry `minimonitor` (`sys.argv` was reset, but `/proc` still shows the
  original argv). Only `tests.test_sitrep_window` changed (79/0 → 79/22). The
  other 15 gave identical counts either way, so the fix stays in this one file.
- Every caller looks `_is_companion_process` up as a `monitor_core` module
  global (`monitor_core.py:1153`, `:2795`, `:4092`). `patch.object(mc, …)`
  therefore reaches all of them, as `ConsumerTableTests`'
  `no_cmdline_companions()` already relies on.

## Approach

Neutralise the coupling **only for the runner's own pid**, and leave the real
cmdline rung live for every other pid. An all-`False` patch (the
`ConsumerTableTests` shape) would also blind the one test that needs the real
rung: `test_booting_companion_without_a_marker_does_not_match`, whose stand-in
is a *different* pid with a real `minimonitor` argv. A pid-scoped patch keeps
that test real with no carve-out, so a class-wide setUp can apply it.

`LIVE_PID` keeps its second role unchanged: as the live pid inside
`minimonitor:{LIVE_PID}` markers, where `is_live_companion_marker` needs a
process that is alive (`os.kill(pid, 0)`) and never reads its cmdline.

## Implementation steps (all in `tests/test_sitrep_window.py`)

1. **Reword the `LIVE_PID` comment** (line 60) to describe both roles truthfully:
   a live pid for companion markers, and the default pane pid. Its cmdline is
   the runner's own, so any fixture that reaches the cmdline rung must go
   through `runner_pid_is_not_a_companion()`.

2. **Add the helper** right after `LIVE_PID` / `pane()`:
   ```python
   def runner_pid_is_not_a_companion():
       """Patch the cmdline rung so THIS runner's pid is never a companion.

       Only LIVE_PID is answered `False`; every other pid still reaches the real
       `/proc` (or `ps`) read, so a stand-in spawned with a `minimonitor` argv is
       still classified for real. Without it the verdicts depend on how the
       suite was invoked: a runner whose argv names `minimonitor` or
       `monitor_app` (e.g. `unittest tests.test_sitrep_window
       tests.test_minimonitor_sibling_fallback`) turns every LIVE_PID agent
       fixture into a companion (t2233).
       """
       real = mc._is_companion_process

       def rung(pid):
           return False if str(pid) == str(LIVE_PID) else real(pid)

       return patch.object(mc, "_is_companion_process", rung)
   ```
   `str()` on both sides because the parsed rows can carry the pid as `int` or
   `str`.

3. **Apply it to the affected fixtures:**
   - `MatcherTests`: add a `setUp` that `start()`s the patch and
     `addCleanup(p.stop)`. In the docstring of
     `test_booting_companion_without_a_marker_does_not_match`, add one sentence
     saying the stand-in's pid is not `LIVE_PID`, so the class patch leaves its
     cmdline rung real.
   - `ClassifyParityTests`: the same `setUp`.
   - `_SpawnFixture.setUp`: add `runner_pid_is_not_a_companion().start()`
     next to the other `patch.object(...).start()` calls. The existing
     `addCleanup(patch.stopall)` stops it, and both `SpawnTests` and
     `RoleSpawnTests` inherit it.
   - Leave `ConsumerTableTests` / `no_cmdline_companions()` alone. They are
     already isolated and fall outside the reproduced failure set.

4. **Add a regression test**, `ArgvIndependenceTests`, that runs the fixtures
   in the condition that used to break them:
   ```python
   class ArgvIndependenceTests(unittest.TestCase):
       """The fixtures' verdicts do not depend on the runner's argv (t2233)."""

       CLASSES = ("MatcherTests", "ClassifyParityTests", "SpawnTests", "RoleSpawnTests")

       def test_fixtures_pass_under_a_minimonitor_argv(self):
           code = textwrap.dedent('''
               import sys, unittest
               here, names = sys.argv[1], sys.argv[2].split(",")
               sys.argv = sys.argv[:1]
               sys.path.insert(0, here)
               import test_sitrep_window as m
               # the condition must really hold, or this test proves nothing
               print("COUPLED:%d" % int(m._REAL_RUNG(m.LIVE_PID)), flush=True)
               suite = unittest.TestSuite(
                   unittest.defaultTestLoader.loadTestsFromTestCase(getattr(m, n))
                   for n in names)
               r = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
               print("RAN:%d FAILED:%d" % (r.testsRun, len(r.failures) + len(r.errors)))
               sys.exit(0 if r.wasSuccessful() else 1)
           ''')
           res = subprocess.run(
               [sys.executable, "-c", code, str(Path(__file__).resolve().parent),
                ",".join(self.CLASSES), "minimonitor"],
               capture_output=True, text=True, timeout=120, cwd=REPO_ROOT)
           self.assertIn("COUPLED:1", res.stdout, res.stdout + res.stderr)
           self.assertEqual(res.returncode, 0, res.stdout + res.stderr[-4000:])
           self.assertRegex(res.stdout, r"RAN:[1-9]\d* FAILED:0")
   ```
   - The child's own cmdline carries `minimonitor`, and in the child
     `LIVE_PID` is the child's pid, so this reproduces the t2233 condition
     exactly.
   - Capture the unpatched rung at import as `_REAL_RUNG =
     mc._is_companion_process`, a module constant next to the helper. The
     `COUPLED:1` witness then reads the real function, never a patched one.
     The helper keeps reading `mc._is_companion_process` at call time, as in
     step 2.
   - It is an **attested positive**. If the platform cannot see the
     keyword in the child's argv, `COUPLED:1` is missing and the test fails
     instead of passing vacuously.
   - No recursion: the child loads only the four named classes, never
     `ArgvIndependenceTests`.
   - Add `import textwrap` to the imports.

5. **Disposition of defect 1:** the file stays owned by t2230. t2233 makes
   no edit to `tests/test_board_movement.py`. Send t2230 an advisory note
   (`./ait note 2230 --from 2233 --text …`) saying:
   - t2233's board-movement defect is delivered by t2230's step 5, which is
     currently uncommitted in the working tree;
   - **t2233's archival is blocked until that edit is committed**;
   - if t2230 drops or reverts the edit, t2233's first defect returns.

   Record the note id in the Final Implementation Notes.

6. **Completion condition for defect 1 (BLOCKING, checked before Step 9
   archival).** An advisory note does not make the fix land. A test that
   passes against the shared dirty tree says nothing about committed code. So
   t2233 is archived only when all of the following hold:
   - **Committed.** Find the t2230 commit that carries the hermetic control:
     ```bash
     git log --format='%H %s' -- tests/test_board_movement.py | grep -m1 '(t2230)'
     ```
     Then confirm that commit's blob contains it:
     `git show <sha>:tests/test_board_movement.py | grep -c 'def test_in_process_task_dir_override_reads_the_cwd_tree'`
     → `1`. It must also no longer carry the live-tree assertion:
     `grep -c 'the real tree must contain none of the fixture files'` → `0`.
     Record the **full** SHA in the Final Implementation Notes.
   - **Still in HEAD.** `git show HEAD:tests/test_board_movement.py` passes the
     same two greps, so no later commit has re-broken it.
   - **Re-run against the committed version, not the working tree.** Write
     `git show HEAD:tests/test_board_movement.py` to an isolated scratch copy.
     Use the same layout as the mutant in Verification: `$SCRATCH/committed/tests/`
     plus symlinked `.aitask-scripts` and `tests/lib`, and any other
     `tests/`-relative imports the file needs, traced before reuse. Then run
     `pytest <copy> -k IsolationNegativeControl` → `1 passed`. Record the
     output line next to the SHA.

   **If any check fails** (t2230 has not committed yet, or committed something
   else): do **not** archive. Commit the sitrep fix (Step 8), then end with the
   **Stopped** banner, `outcome=in-flight`. The task stays `Implementing` with
   its commit recorded, so `/aitask-pick 2233` resumes at post-implementation
   and re-runs this condition. The reason line names the missing evidence
   ("t2230's board-movement fix not yet committed"), and the next step is
   "after t2230 commits, `/aitask-pick 2233`". Never take over or commit
   t2230's edit from this session.

## Verification

- Red→green: before the edit, the scratch probe
  (`$SCRATCH/probe.py tests.test_sitrep_window minimonitor`) gives
  `run=79 fail=22`. After the edit it must give `run=80 fail=0`.
- `python -m unittest tests.test_sitrep_window tests.test_minimonitor_sibling_fallback`
  → OK (previously 22 failures).
- `python -m unittest tests.test_sitrep_window` → OK (alone, unchanged).
- **Pre-fix control for the new regression test** (an isolated mutant, with no
  stash or restore of the shared tree): copy the edited file to
  `$SCRATCH/mut/tests/test_sitrep_window.py` and symlink
  `$SCRATCH/mut/.aitask-scripts` → the real one and `$SCRATCH/mut/tests/lib`
  → the real one, so `REPO_ROOT` resolves to the mutant root. Then make
  `runner_pid_is_not_a_companion` return a no-op patch (`rung = real`). Running
  `ArgvIndependenceTests` from the mutant must **fail** with `COUPLED:1` and
  `FAILED:` > 0. This proves the test catches the coupling. Delete the mutant
  afterwards.
- `bash tests/run_all_python_tests.sh --test-dir tests`, last line read with
  `PIPESTATUS`. Expected `PASSED`. If it fails, attribute each failure as
  pre-existing or caused here before deciding anything.

## Post-implementation

Step 8: commit only `tests/test_sitrep_window.py` as
`bug: Isolate sitrep window fixtures from the runner's argv (t2233)`. Step 9
archival (with the `risk_evaluated` gate) runs **only after** step 6's
completion condition passes. Otherwise the task stays in flight as step 6
describes.

## Risk

### Code-health risk: low
None identified. The change is test-only and confined to one file. The
neutraliser is scoped to the runner's own pid, so the real cmdline rung stays
covered (the booting stand-in test still exercises it). Product code is
untouched.

### Goal-achievement risk: low
- Defect 1 is delivered by in-flight t2230, whose edit is still uncommitted.
  t2233 could close while committed code still carries the defect ·
  severity: low (residual: archival is gated on step 6's
  committed-SHA + committed-version re-run condition) · → mitigation: none. It
  is handled within the plan by steps 5–6, and t2233 never takes ownership of
  t2230's file.

## Final Implementation Notes
- **Actual work done:** Steps 1–6 as planned, all in `tests/test_sitrep_window.py`:
  - reworded the `LIVE_PID` comment;
  - added the `_REAL_RUNG` import-time capture and the
    `runner_pid_is_not_a_companion()` pid-scoped patch;
  - applied the patch in `MatcherTests.setUp`, `ClassifyParityTests.setUp` and
    `_SpawnFixture.setUp` (stopped by the existing `patch.stopall` cleanup);
  - noted in the booting stand-in test's docstring that its cmdline rung stays
    real;
  - added `ArgvIndependenceTests.test_fixtures_pass_under_a_minimonitor_argv`
    (child interpreter with `minimonitor` in argv, `COUPLED:1` witness).

  `tests/test_board_movement.py` was not touched.
- **Deviations from plan:** none in code. The child-script witness wraps the rung in `bool()` before `int()`.
- **Issues encountered:**
  - The first blast-radius probe errored on import, because the script's dir
    rather than the repo was on `sys.path`. Fixed by inserting cwd, then re-run.
  - The full suite exceeded the 600 s foreground timeout and finished in the
    background. Verdict below.
- **Key decisions:** Scoped the neutraliser to the runner's own pid instead of
  an all-`False` patch. That keeps the real cmdline rung exercised by the
  booting stand-in test with no carve-out.
- **Verification evidence:**
  - Scratch probe `tests.test_sitrep_window minimonitor`: pre-fix
    `run=79 fail=22`, post-fix `run=80 fail=0` (plain argv: `run=80 fail=0`).
  - `python -m unittest tests.test_sitrep_window tests.test_minimonitor_sibling_fallback`
    → `Ran 92 tests … OK` (pre-fix: `FAILED (failures=22)`). Module alone →
    `Ran 80 tests … OK`.
  - Isolated mutant: a scratch copy with the `.aitask-scripts` and `tests/lib`
    symlinks, and the neutraliser reduced to `return real(pid)`. Its
    `ArgvIndependenceTests` → FAIL with `COUPLED:1` and
    `RAN:49 FAILED:22`. The unmutated copy in the same layout → OK. Mutant
    deleted.
  - `bash tests/run_all_python_tests.sh --test-dir tests` → rc=0, last line
    `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
  - Blast-radius probe: 15 other modules gave identical results with and
    without `minimonitor` in argv:
    - agent_sessions_contract_call_sites, agent_sessions_transitions,
      agent_sessions_identity, agent_sessions_lease, agent_sessions;
    - agent_freeze, agent_keys, agent_restore;
    - list_panes_arity_characterization, frozenagent_app,
      minimonitor_concern_smoke, minimonitor_sibling_fallback;
    - monitor_sitrep_harvest_close, monitor_companion_filter,
      monitor_status_server.
- **Defect 1 completion ledger (step 6 — PASSED):**
  - Note to t2230: `NOTE_APPENDED:2026-11-08T08:30:52Z.5c3c9e319ebf0b69b8fda680`
    (`LIVE_NONE:unlocked`). t2230 had been archived by then.
  - Committed: `dc5811dede606751c6047b568b00905c31a8a86f` — `bug: Act on
    window ids, not listing-time indexes, in the TUI switcher (t2230)`. Its
    blob has `def test_in_process_task_dir_override_reads_the_cwd_tree` ×1 and
    `the real tree must contain none of the fixture files` ×0.
  - HEAD: the same greps give 1 / 0, and the working-tree file is clean.
  - Re-run against `git show HEAD:tests/test_board_movement.py` in an isolated
    scratch copy (symlinked `.aitask-scripts`, `tests/lib`):
    `pytest -k IsolationNegativeControl` → `1 passed, 33 deselected`.
- **Upstream defects identified:** None
