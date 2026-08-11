---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, aitask_board, tui]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-08-11 22:21
updated_at: 2026-08-11 22:21
---

## Symptom

`tests/test_board_bytrail_view.py::LaunchFallbackTests::test_repeated_R_during_an_in_flight_baseline_launches_once`
failed in 2 of 4 whole-suite parallel runs (`bash tests/run_all_python_tests.sh`
with the xdist lane) while passing 3/3 alone and 4/4 for its own file under
`-n 4`. It was reported as a "launch-debounce timing flake"; it is not a timing
flake in the debounce logic.

## Root cause

The test's assertions are deterministic by construction: both async seams
(`_trail_baseline_worker`, `_launch_trail`) are replaced with instance lambdas,
there is exactly one `await pilot.pause()`, and no await sits between the later
assertions — so no scheduled callback can interleave with them, and CPU
slowness alone cannot flip any of them.

What the test *does* leave running is a real worker inside its own teardown:

    app._finish_trail_launch(["v1"], "", lambda: True)      # test line ~2180
      -> _after_trail_launch()                              # aitask_board.py:10515
      -> _reload_active_trail()                             # aitask_board.py:10254
      -> @work(thread=True) _trail_reload_worker            # aitask_board.py:10266
      -> load_trail_blob(handle)      # subprocess, 15s timeout
      -> app.call_from_thread(_on_trail_reload, ...)        # re-renders widgets

Two library facts turn that residue into a test failure:

- `App.run_test` ends its `finally` with `if self._exception: raise
  self._exception` (textual/app.py:2218, Textual 8.2.7).
- `@work` defaults to `exit_on_error=True`, and an errored worker calls
  `app._handle_exception(WorkerFailed(...))` (textual/worker.py:382-384).

So **any** exception raised in that worker — or in `_on_trail_reload`'s
`_rerender_trail()` running against a tearing-down app — surfaces as this
test's failure, at the `async with app.run_test(...)` exit, with a traceback
nowhere near the debounce assertions. That is exactly the observed signature:
untouched test, "timing" appearance, load-dependent.

The exposure window is not occasional but total: a probe delaying
`load_trail_blob` by 8s showed app shutdown still waits for the worker, so the
worker always completes inside the `run_test` block.

Its sibling in the same class,
`test_direct_launch_fallback_installs_watch_and_reloads` (line ~2068),
`patch.object(app, "_reload_active_trail", ...)` — this test is the only one in
the class that lets the real path run.

Additional residue observed at block exit: `_trail_launch_pending` still True,
two captured baseline callbacks never invoked, one live worker.

## Evidence

Positive control: injecting a single `raise RuntimeError(...)` into
`_on_trail_reload` makes the test fail with
`textual.worker.WorkerFailed: Worker raised exception: RuntimeError(...)`
while every assertion in the test body passes.

Under the fixture cwd `ARTIFACT_SCRIPT` (`.aitask-scripts/aitask_artifact.sh`)
does not exist, so `load_trail_blob` currently returns fast with
`artifact unresolved: [Errno 2] ...` — the benign branch. The failure needs one
of the paths that can raise instead (thread start under a loaded box, a
`_rerender_trail()` on a dismantled screen, `call_from_thread` after the loop
is gone). Reproduction attempts that all stayed green for this test: 3x alone,
6x under 20 CPU spinners, 2 full suites at `-n 4` (one under external load),
all 18 `test_board_*` modules in one process (1018 passed), 2 full suites at
`-n 8`.

## Work to do

1. Make the test stop running the real reload path — patch
   `app._reload_active_trail` (as its sibling does) or `_after_trail_launch`,
   and assert the reload was *requested*, so the launch-once guard the test
   exists to prove is preserved rather than weakened. Leaving pending state /
   uncalled callbacks at exit should be cleaned up in the same pass.
2. Audit the rest of `tests/test_board_bytrail_view.py` (and the other board
   test modules) for the same shape: a test that triggers `_reload_active_trail`
   / `_start_trail_drift` / any `@work` path without stubbing it, and therefore
   inherits an unbounded failure surface at teardown. Fix or explicitly justify
   each.
3. Record the failure mode where board TUI test authors will meet it — a
   Textual `@work` worker left in flight makes `run_test` fail the *enclosing*
   test with `WorkerFailed`, so a green assertion block is not evidence a test
   is isolated. `aidocs/framework/tui_conventions.md` (or
   `testing_conventions.md`) plus the harness docstring in
   `tests/lib/board_fixture.py` are the candidate homes.

## Acceptance criteria

- The named test no longer starts `_trail_reload_worker` (or any other real
  `@work` worker) inside `run_test`; proven by a probe/assertion on
  `app.workers` at block exit, not only by the test going green.
- The guard the test exists to prove (a second `R` during an in-flight baseline
  launches nothing) still fails if `_trail_launch_pending` is removed —
  negative control required.
- The audit's result is stated as which-tests, not a boolean: every board test
  that leaves a live worker at teardown is listed, with its disposition.

## Notes

- Unrelated finding while stress-running the suite: a whole-suite parallel run
  in a repo being edited concurrently by another session dies with
  `ERROR collecting gwN — Different tests were collected between gw3 and gwN`
  (observed while `tests/test_concern_picker_modal.py` was dirty in the working
  tree). Worth knowing before blaming a red parallel run on the code under
  test.
