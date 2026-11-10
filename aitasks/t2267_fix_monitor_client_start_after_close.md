---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [monitor, applink]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: upstream_defect
created_at: 2026-11-09 23:19
updated_at: 2026-11-10 08:50
---

## Origin

Spawned from t2259 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/status_client.py:394-397 — start() on a client closed before it ever started still runs an attempt (ensure may spawn the status server; _attempt only checks _closed after ensure returns), while start_detached() refuses a closed client; no current caller hits it`
- `tests/test_scratchpad_app.py:930 — test_14g_unkillable_child_keeps_loop_responsive asserts a 1.0 s wall-clock Ctrl+Q shutdown budget that failed at 2.02 s under the 4-worker suite at load ~14 (passes alone 3/3)`

The two are unrelated. They were bundled at the Step 8b offer, so split them if
they should be picked separately.

## Diagnostic context

From t2259 (archived plan `aiplans/archived/p2259_fix_monitor_client_shared_start_cancellation.md`):

- **Closed-before-start client.** t2259 made `MonitorClient.start()` shield its
  startup task, so only `close()` cancels the startup. While auditing that, it
  noticed a mismatch in `start()`:
  - it guards only `_started`;
  - `start_detached()` guards `self._started or self._closed`.

  So on a client whose `close()` ran before any start, a later `start()`
  (directly, or via `_await_ready()` from a read method) still creates the
  startup task. `_attempt` then runs `ensure` in a worker thread, which may
  spawn the status server, and checks `_closed` only after `ensure` returns.
  `_start_body` skips the fallback because `self._closed` is true. `close()`
  already set `_ready`, so the caller returns at once.

  No current owner calls `start()` after `close()`: the monitor apps and applink
  all start at mount or construction. It is latent.
- **Scratchpad budget.** In t2259's full-suite run
  (`bash tests/run_all_python_tests.sh`, `-n 4 --dist loadfile`, load average
  ~14) the only failure was `tests/test_scratchpad_app.py::UnresolvedWriteTests::test_14g_unkillable_child_keeps_loop_responsive`:
  `AssertionError: 2.016375144943595 not less than 1.0` at `:930`, the
  `time.monotonic() - t0 < 1.0` check after `ctrl+q`. Re-run alone it passed
  3/3 (2.4–2.6 s per test run). It is unrelated to t2259: neither the test nor
  the scratchpad package imports `monitor/` or `applink/`. The 1.0 s wall-clock
  shutdown budget is load-sensitive.

## Suggested fix

- **`start()`:** return early when `self._closed` (after setting nothing), as
  `start_detached()` does. Pin it with a test: `close()` then `start()`, assert
  `ensure` is never called and `_start_task is None`, plus a pre-fix control.
- **Scratchpad test:** decide whether the 1.0 s budget measures the property (the
  loop stays responsive) or only scheduling latency under load. Either widen it
  with a recorded rationale, or measure the event-loop stall directly. Keep a
  control that still catches a genuinely blocked loop.
