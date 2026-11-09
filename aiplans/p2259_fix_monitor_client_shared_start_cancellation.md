---
Task: t2259_fix_monitor_client_shared_start_cancellation.md
Base branch: main
Output branch: main
---

# t2259 — Make `MonitorClient.start()` cancellation-safe

## Context

`MonitorClient.start()` (`.aitask-scripts/monitor/status_client.py:387-405`)
creates the startup task and then awaits it **unshielded**. Cancelling the first
caller therefore cancels the shared startup. `_start_body`'s `finally` still sets
`_ready`, but neither `_enter_fallback` nor a reconnect runs. The client is left
in `connecting` with `_started=True`, so every later `start()` returns at once and
the client is never subscribed and never falls back. t2037_4 worked around this
for applink with `start_detached()`. The monitor apps are unaffected today only
because nothing cancels their first caller.

**Approach: task Option 1.** `start()` awaits the startup task through
`asyncio.shield`, so `close()` is the only thing that cancels the startup. This
removes the defect for every caller, including any future shared one. Option 2
(documenting `start()` as single-owner) would leave the trap in place.

**Caller audit.** This is the precondition for Option 1: no caller may depend on
"cancelling my `start()` aborts the attempt".
- `MonitorClient` has exactly two construction sites:
  - `monitor/monitor_shared.py:78` `build_monitor_client`, used by
    `monitor_app.py:895` and `minimonitor_app.py:2022`. Both apps call
    `close_control_client()` from `on_unmount` and from
    `_teardown_prior_monitoring`.
  - `applink/server.py:496`. It already uses `start_detached()`; the client is
    closed in `_release_client_if_idle` and at shutdown.
- The other `.start()` hits are different classes: `TmuxControlClient` in
  `monitor_core.py:1900/1975`, `ReplayServer` in `status_recording.py:709`, and
  servers in tests.
- The only thing that relies on the old semantics is the test
  `test_cancelled_start_closes_the_socket`. It is rewritten below.

## Implementation

1. **`.aitask-scripts/monitor/status_client.py` — `start()` (387-405).** Keep the
   structure: only the call that creates the task awaits it, and later callers
   wait on `_ready` exactly as today, so a startup exception still reaches only
   the first caller.
   ```python
   self._start_task = asyncio.create_task(self._start_body())
   try:
       await asyncio.shield(self._start_task)
   except asyncio.CancelledError:
       # This caller's own cancellation: propagate it; the attempt carries on.
       # close() cancelling the start is not this caller's cancellation.
       task = asyncio.current_task()
       if task is not None and task.cancelling():
           raise
   return True
   ```
   Replace the comment at 394-396 with the current-state rationale. Without the
   shield, cancelling the first caller would cancel the startup for every caller
   and leave the client in `connecting` with no fallback and no reconnect. With
   it, only `close()` cancels the startup. Add one docstring sentence: `start()`
   is safe for a client shared by several callers.

   Cancellation by `close()` still works. It cancels the inner `_start_task`, the
   shield's outer future is cancelled with it, and the caller's `cancelling()` is
   0, so it returns True as today. That is covered by
   `test_close_during_an_unanswered_hello_closes_the_socket`.

2. **Same file — `start_detached()` docstring (419-431).** Its claim that
   ":meth:`start` awaits its startup task unshielded …" is now false. New text:
   it begins the first attempt synchronously, without awaiting it. It is meant
   for the owner of a shared client's lifetime (applink), which claims the start
   with no await, so the first attempt is already running before any caller
   reads. The startup belongs to the client either way: `start()` shields it too,
   and only `close()` cancels it. The code is unchanged.

3. **`.aitask-scripts/applink/server.py:485-492` docstring.** Reword the
   "Detached, because …" sentence. It currently implies that `start()` would let
   one push loop's cancellation strand the client. New wording: detached, so the
   first attempt is already running when the first push loop reads; the startup
   belongs to the client, not to any one loop, and only `close` cancels it. The
   `pusher.py:252-253` comment stays accurate and is left alone.

4. **`aidocs/framework/monitor_status_protocol.md:1077-1098`.**
   - First bullet: "cancellation included" becomes "cancellation by `close()`
     included".
   - Replace the "**A shared client starts detached.**" bullet with
     "**Cancelling a caller never cancels the startup.**" The bullet says:
     - `start()` awaits the client-owned startup task shielded, so a cancelled
       caller only stops waiting, and the attempt still reaches a subscribed
       mode or a fallback with its reconnect;
     - only `close()` cancels the startup;
     - applink calls the synchronous `start_detached()` from the owner of the
       client's lifetime, so the first attempt is running before any push loop
       reads.

   The text describes the current state only, with no history.

5. **`tests/test_monitor_status_client.py`.**
   - **New `SharedClientTests.test_a_cancelled_first_caller_never_cancels_the_start`.**
     The setup is a real server and `HeldEnsure`, as in the detached test.
     1. `a = create_task(c.start())` makes `a` the first caller, which owns the
        start; `b = create_task(c.start())` is a second caller.
     2. Wait for `held.entered`, then cancel `a` and assert it raises
        `CancelledError`.
     3. Assert `c._start_task` is **not done**.
     4. Release the held attempt. `b` returns True, the mode is `SERVER`, and
        `capture_all_async()` contains `%1`.
     5. A later `await c.start()` also returns, with the mode still `SERVER`.

     This is the reviewer's repro.
   - **New `test_a_cancelled_first_caller_still_reaches_fallback_with_a_reconnect`.**
     It mirrors the detached fallback test, but with a `start()`-owned start and
     `ensure` returning UNAVAILABLE. The expected result is `FALLBACK` with a
     live `_reconnect_task`.
   - **Rewrite `HandshakeCleanupTests.test_cancelled_start_closes_the_socket`** as
     `test_a_cancelled_start_caller_leaves_the_socket_to_close`. Keep the setup:
     a scripted server and an unanswered hello. Then:
     1. Cancel the sole caller and assert it raises `CancelledError`.
     2. Assert `c._start_task` is not done, no recorded link `is_closing()`, and
        `c._connecting` is non-empty.
     3. `await c.close()`.
     4. Run the original checks: `assert_all_closed()`, `srv.eofs == 1`,
        `c._connecting == set()`, and also `c._start_task.done()`.

     The purpose is kept: the client still closes its own handshake socket, now
     through its only canceller.
   - **Both new `SharedClientTests` start `a` and then `await asyncio.sleep(0)`
     before starting `b`.** This makes "`a` is the first caller" explicit rather
     than relying on FIFO task scheduling.
   - **Update the docstring of `test_a_cancelled_waiter_never_cancels_a_detached_start`.**
     Its recorded positive control ("use `create_task(c.start())` instead of
     `start_detached()` …") stops failing once `start()` is fixed, so the
     docstring would be wrong. The new control is **mutant B**: a *waiting*
     `start()` (the `_started` branch) awaits `_start_task` unshielded instead of
     `_ready`, but keeps the pre-fix code's `cancelling()` swallow. The waiter
     then swallows the startup's cancellation, and the test fails on its **mode
     assertion** with `CONNECTING is not SERVER`.

     The docstring also says that a *bare* unshielded await (mutant A) is not
     that control. Under mutant A, `b` itself ends cancelled, and the test
     errors with `CancelledError` at `await asyncio.wait_for(b, 3.0)` before
     any state assertion. Both results were measured at planning time (below)
     and are re-run in Verification.

### Assertion classes and the pre-fix control

| Test | Assertions | Class | On the baseline (pre-fix `status_client.py`) |
|---|---|---|---|
| new `…first_caller_never_cancels_the_start` | `_start_task` not done; `SERVER`; `%1` read; later `start()` still `SERVER` | D | **red, failure** at `assertFalse(c._start_task.done())`: "cancelling the first caller cancelled the startup" |
| same | `a` raises `CancelledError`; `b` returns True | P | green: the old code already did both |
| new `…first_caller_still_reaches_fallback…` | `FALLBACK`; live reconnect task | D | **red, failure**: `CONNECTING is not FALLBACK` |
| same | `a` raises `CancelledError`; `b` returns True | P | green |
| rewritten `…cancelled_start_caller_leaves_the_socket_to_close` | start pending, socket open and `_connecting` non-empty after the cancel | C (contract: cancelling a caller no longer aborts the attempt) | **red, failure**: "cancelling the caller aborted the attempt" |
| same | after `close()`: all closed, `eofs == 1`, `_connecting` empty, start done | P | green |
| 4 existing detached `SharedClientTests` | unchanged (docstring only) | P | green |
| every other test in the file | unchanged | P | green |

**Acceptance rule.** Copy the new test file into a detached worktree at the
literal pre-fix SHA and run it there. The set of failing test names must be
exactly those three. Each must be an assertion **failure**, not an error, on the
D/C assertion named above (read the messages, not just the counts). After the
fix, the whole file is green.

**Measured at planning time** (in memory: `mock.patch.object` on
`MonitorClient.start`; no file written; the tests were defined inline exactly as
specified above):
- The new tests on the pre-fix `start()` give `failures=3 errors=0`, with the
  three messages in the table.
- The new tests on the shielded `start()` give `failures=0 errors=0`.
- The existing file on the shielded `start()` runs 59 tests with `failures=1`,
  which is `test_cancelled_start_closes_the_socket` (the C test this plan
  rewrites). That confirms it is the only test relying on the old semantics.
- The detached tests under mutant A give `failures=0 errors=2`: `CancelledError`
  at lines 1341 and 1357 (`await asyncio.wait_for(b, 3.0)`).
- The detached tests under mutant B give `failures=2 errors=0`: `CONNECTING is
  not SERVER` (line 1342) and `CONNECTING is not FALLBACK` (line 1358).

## Verification

1. **Red proof.** Use the scratchpad and never stash:
   ```bash
   SHA=$(git rev-parse HEAD)        # record the literal value before committing
   git worktree add --detach "$SCRATCH/proof" "$SHA"
   cp tests/test_monitor_status_client.py "$SCRATCH/proof/tests/"
   PY="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   (cd "$SCRATCH/proof" && "$PY" -m unittest tests.test_monitor_status_client -v 2>&1 | tail -40)
   ```
   Expect exactly the three D/C tests to fail.
2. **Mutation control for the detached docstring (mutant B).** In the same proof
   worktree, copy in the *fixed* `status_client.py`. Then, with a Python text
   substitution, replace the `_started` branch's `await self._ready.wait()` with
   an unshielded `await self._start_task` inside a `try`/`except
   asyncio.CancelledError` that re-raises only when
   `asyncio.current_task().cancelling()` is set.
   - Anchor the substitution on the three-line branch, `if self._started:` /
     `await self._ready.wait()` / `return True`, so it cannot match a docstring.
     Assert the count is 1, and grep the mutated lines.
   - Run `SharedClientTests`. Expect exactly the two detached waiter tests to
     **fail, not error**, on `assertIs(c.mode, SERVER)` and
     `assertIs(c.mode, FALLBACK)`.
   - Then remove the worktree (`git worktree remove --force`).
3. **Green run.** Run `"$PY" -m unittest tests.test_monitor_status_client -v` in
   the repo.
4. **Regressions.** Run the applink and monitor consumers:
   `tests/test_applink_status_subscribe.py`,
   `tests/test_applink_pane_status_provenance.py` and
   `tests/test_minimonitor_startup_input_latency.py`. Then run the whole suite
   with `bash tests/run_all_python_tests.sh` and read only the final
   `PYTHON SUITE:` line, using `set -o pipefail` if piping.
5. **Lint.** No shell files change, so shellcheck is not needed.

## Out of scope (noted, not changed)

- A `start()` on a client that was closed before it ever started still runs an
  attempt. `start_detached()` refuses to start a closed client; `start()` does
  not. This is a separate, pre-existing inconsistency that no current caller hits.
  It goes into the Final Implementation Notes as an observation.

## Post-implementation

Step 9 of the shared workflow handles the review, the commit (`bug: … (t2259)`),
archival and the push.

## Risk

### Code-health risk: low
- A lifecycle owner that cancels its `start()` caller but never calls `close()`
  would now leave the attempt running until `close()` or loop shutdown, including
  a local control client the attempt starts in fallback. All three current owners
  call `close()` (see the caller audit in Context) · severity: low · → mitigation:
  none (addressed in-plan by the caller audit)

### Goal-achievement risk: low
None identified.
