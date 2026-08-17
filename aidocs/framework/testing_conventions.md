# Testing Conventions

Rules for designing tests in the aitasks framework. Additional conventions can
be added here as they emerge.

## Threading / asyncio migrations require thorough automated coverage

Smoke + manual verification is not enough. When a plan introduces a background
thread, dedicated asyncio loop, `run_coroutine_threadsafe` bridge, or any
other concurrency primitive, the test plan must enumerate concrete cases
across each axis below. Threading bugs hide in race windows that manual smoke
cannot reach; skipping any axis is a planning gap, not a "stretch."

Walk this checklist explicitly in the plan body before exiting plan mode:

1. **Lifecycle:** start idempotency, start-after-stop, stop idempotency, stop
   with pending work.
2. **Concurrency:** N concurrent callers from multiple threads — bump N to 50+
   to flush latent ordering bugs.
3. **Mixed contexts:** sync caller invoked from inside a running asyncio loop
   on a different thread (the load-bearing test that proves the architecture
   solves the deadlock the migration was meant to address).
4. **Failure recovery:** transport failure (e.g., server killed externally),
   then next request returns a dead-client sentinel cleanly without raising.
5. **Resource boundaries:** binary not on PATH / config missing — start fails
   cleanly, fallback engages, no thread leaks.
6. **Resource cleanup:** after stop, assert thread joined within timeout AND
   `threading.enumerate()` no longer lists the worker.
7. **Behavior parity:** for every operation with a new code path, run new vs
   old and assert identical results (exact rc; exact stdout when rc==0).
   Document the contract explicitly when error-path stdout diverges (e.g.,
   control-mode `%error` body vs subprocess stderr) so future maintainers
   don't tighten the assertion incorrectly.

If a planned case is flaky on timing (e.g., sub-ms timeout assertions on a
fast IPC), DROP the case rather than weakening it with sleeps / retries —
note the dropped case in Final Implementation Notes and rely on adjacent
cases that exercise the same semantics deterministically.

## A Textual `@work` worker left in flight fails the *enclosing* `run_test`

`App.run_test` ends its `finally` with `if self._exception: raise
self._exception` (textual/app.py:2218, Textual 8.2.7), and `@work` defaults to
`exit_on_error=True`, so an errored worker routes through
`app._handle_exception(WorkerFailed(...))` (textual/worker.py:382-384). A worker
still running when the `async with app.run_test(...)` block exits therefore fails
the test that started it, with a traceback nowhere near its assertions — so **a
green assertion block is not evidence a test is isolated.** The test looks
untouched, the failure looks like a timing flake, and it is load-dependent.

The exposure window is total, not occasional. Measured on t1487: a probe delaying
the worker's subprocess by 8s showed app shutdown still waits for the worker, so
it always completes inside the `run_test` block.

How to apply:

- Stub the worker-*starting* method (`patch.object` / an instance lambda) and
  assert the work was **requested** — do not let the real worker run. Stubbing the
  entry point rather than the worker keeps the behaviour under test intact.
- `await app.workers.wait_for_complete()` is the **wrong** tool for this: it waits
  on the very worker that raises. It is right only for tests that deliberately
  drive a real worker and then drain it.
- To *prove* isolation rather than assume it, record worker starts by standing in
  for the node's `run_worker` — the single choke point `@work` dispatches through
  (`textual/_work_decorator.py`) — and assert both that nothing started and that
  `app.workers` is empty at block exit. The two are not redundant:
  `WorkerManager._remove_worker` is the worker's own done-callback, so an empty
  `app.workers` is also what a worker that started *and finished* leaves behind.
  `tests/lib/board_fixture.py` ships `block_app_worker_starts` /
  `assertNoLiveWorkers` for the board suite.
- A probe like that needs its own positive control: mutate the stub away and
  confirm the probe fails **naming the expected worker**, not merely that the test
  goes red somewhere earlier.

Reference callers: `LaunchFallbackTests` in `tests/test_board_bytrail_view.py`
(the stubbed shape); `ThreadWorkerTests` in the same file is the deliberate
opposite — it exists to drive the real thread hop and drains before block exit.

## Golden-file regression tests for template-engine output

Any code path that produces output through an external template engine
(minijinja, jinja2, mustache, handlebars, …) needs golden-file regression tests
in addition to whatever "renders without error" / "stub markers present" check
already exists (e.g. `ait skill verify`). Template engines have non-trivial
release cadences and subtly shift output across versions — whitespace handling,
filter semantics, escape rules, default-value behavior. A "renders successfully"
check catches only *hard* failures; silent output drift still ships broken
behavior.

How to apply:

- For every `(input, parameter-combination)` the renderer supports, render once
  at acceptance and commit the output as a golden under `tests/golden/<scope>/`.
- Add a `tests/test_*.sh` script that re-renders fresh and asserts an empty diff
  against the golden (PASS/FAIL summary, matching the repo's test convention).
- Cover EVERY combination — for skill rendering, every `(skill × profile ×
  agent)` tuple, not a representative sample. Minor per-combination differences
  are exactly what version drift hides in.
- When the engine is intentionally upgraded, regenerate the goldens in a
  dedicated commit (`test: regenerate golden files for minijinja X.Y → X.Z`) so
  the diff is reviewable.
- This applies beyond skill rendering — any future code path that pipes through a
  template engine inherits the same requirement.
