# Testing Conventions

Rules for designing tests in the aitasks framework. Currently scoped to
threading / asyncio coverage; additional conventions can be added here as
they emerge.

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
