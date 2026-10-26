---
Task: t2147_post_mortem_pid_reads.md
Base branch: main
Output branch: main
---

# t2147 — Shared slow-start retry for post-mortem pid reads in test_bounded_run.py

## Context

t2142 fixed `TestCrewGitTimeout.test_git_cmd_timeout_reports_124` with an inline
retry loop. The loop runs each attempt under a longer deadline (1, 2, 4, 8 s) until
the fixture has demonstrably written its pid. Six other tests in
`tests/test_bounded_run.py` read the pid with `_read_pid` **after** the process
group was killed, under short deadlines. If the fixture is too slow to start, the
group dies before the pid is written, and `_read_pid`'s 30 s readiness wait cannot
recover it. This task moves the loop into one helper and applies it to those six
tests and to the original git test.

**A finding that changes the task's premise (checked against
`.aitask-scripts/lib/bounded_run.py`):** a fixture that never started does not
always produce the same outcome as one that did. Every fixture runs `trap …`
**first** and `echo $$ > pidfile` **second**, so a no-pid attempt can be in one
of two states:

- **trap not yet installed**: SIGTERM ends the fixture at once. This gives the
  *TERM-honoured* shape.
- **trap installed, pid write still pending**: a scheduling pause between the
  two statements, longer than deadline + grace, lets SIGKILL land before the
  echo. This gives the *TERM-ignoring* shape, exactly what a fixture that wrote
  its pid shows, but with no pid. (Review finding, reproduced: `Hangup` with no
  pid at 2.38 s, and `TimeoutExpired` with no pid at 2.55 s.)

So "pid written" means the fixture was ready. "No pid" proves nothing about
which state it was in. **Elapsed time cannot tell the two states apart either.**
`elapsed` also includes start-up overhead that nothing bounds from below: the CLI
test's interpreter start-up, and `Popen`'s fork/exec in the in-process tests.
Review reproduced a CLI attempt with 2.2 s of start-up and a delay before the
trap: d=0.5, rc 124, no pid, 2.86 s, which is a valid timeout. Hence the rule:

- **pid written** → the test's **original assertions in full**, grace minimums
  included (readiness is confirmed, so the cleanup really did wait out the grace).
- **no pid** → the outcome must be one of the test's **genuine-deadline
  outcomes**, under the test's **existing overall ceiling** (where it has one).
  Then retry. Do not infer the cleanup duration from elapsed time.

| test | pid written: original assertions | no pid: deadline outcomes + ceiling |
|---|---|---|
| expiry_kills (L97) | `TimeoutExpired`; elapsed < d+1+1.5 | same |
| expiry_terms (L111) | `TimeoutExpired` (marker checked after the loop) | `TimeoutExpired` |
| keyboard_interrupt (L136) | `KeyboardInterrupt`; SIGINT shield restored | same |
| signal_during_cleanup (L156) | `Hangup`; elapsed ≥ d+2-0.3 | `Hangup` or `TimeoutExpired` (no ceiling; the original has none) |
| stop_request_ignored (L195) | `TimeoutExpired`; d+1-0.2 ≤ elapsed < d+1+1+1.5 | `TimeoutExpired`, or `BoundedResult` with `.stopped` true; elapsed < d+1+1+1.5 |
| cli_inherited_grace (L232) | rc 124; d+3-0.3 ≤ elapsed < d+3+2 | rc 124; elapsed < d+3+2 |
| git_cmd_timeout (L435) | rc 124, message, elapsed < d+5+1 (unchanged) | same (the stub has no trap) |

A no-pid attempt is still rejected for: an exception of any other type, another
exit status, a normal return that was not a stop (`stopped` false), or a run past
the ceiling. A `TimeoutExpired`, `Hangup` (timer at d+0.7), `stopped` result or
rc 124 can only arise once the deadline has passed. So none of the accepted
outcomes is premature. The old tests fail at the `assertRaises` or the lower bound
when the trap was missing, and at the post-mortem `_read_pid` in every no-pid
case.

## Implementation (single file: `tests/test_bounded_run.py`)

1. **Add `_written_pid(path) -> int | None`** next to `_read_pid`. It reads the
   pidfile once, without waiting, and returns the first line as an int, or None if
   the file is missing or empty. This is the read t2142 inlined. `_read_pid` stays
   as it is: its two live-fixture callers (L273, L296) still need the readiness
   wait.

2. **Add `_TmpDirCase._run_until_started(self, call, check, deadlines, pidfile=None) -> int`**:
   ```python
   def _run_until_started(self, call, check, deadlines, pidfile=None):
       """Run ``call(deadline)`` under each deadline in turn until its fixture
       demonstrably ran (wrote its pid), and return that pid. <why: post-mortem
       read; no readiness wait can recover a pid never written — t2142/t2147>
       ``call`` returns its outcome: an expected exception is caught by the
       caller and returned, so an unexpected one propagates. ``check(outcome,
       elapsed, deadline, started)`` holds the per-attempt assertions that the
       deadline was genuinely reached. ``started`` is True when the pid was
       written, which means the fixture's trap was in place. False does NOT
       mean the trap was missing: a fixture paused between its trap and its pid
       write is TERM-ignoring and still dies pid-less at SIGKILL, so a no-pid
       check must accept either outcome shape, each under its own bounds."""
       pidfile = self.pidfile if pidfile is None else pidfile
       for deadline in deadlines:
           pidfile.unlink(missing_ok=True)
           start = time.monotonic()
           try:
               outcome = call(deadline)
           finally:
               # Register BEFORE any assertion (or an unexpected exception):
               # a failing attempt must still leave teardown a pid to kill.
               elapsed = time.monotonic() - start
               pid = _written_pid(pidfile)
               if pid is not None:
                   self.leftovers.append(pid)
           try:
               check(outcome, elapsed, deadline, pid is not None)
           except AssertionError as err:
               ran = "ran" if pid is not None else "never ran"
               err.args = (f"attempt with a {deadline:g}s deadline (fixture {ran}): {err}",)
               raise
           if pid is not None:
               return pid
       self.fail(f"the fixture never wrote {pidfile.name}, even with a "
                 f"{deadlines[-1]:g}s deadline")
   ```
   Note: `elapsed` and `pid` are bound in `finally`, so they exist on the normal
   path. If `call` raises, the exception propagates after registration.

3. **Convert the six tests and the git test** (`d` = deadline; each keeps its
   post-loop assertion on the returned pid):
   - **expiry_kills** (grace 1, `(1, 2, 4, 8)`): call returns the result or the
     caught `TimeoutExpired`. Check: `assertIsInstance(outcome, TimeoutExpired)`;
     `assertLess(elapsed, d + 1 + 1.5)`. After the loop: `_gone_within(pid)`.
   - **expiry_terms** (grace 2, `(1, 2, 4, 8)`): call does `marker.unlink(missing_ok=True)`
     first, so the post-loop marker check sees only the attempt that ran. Check:
     `TimeoutExpired`. After the loop: `marker.exists()`.
   - **keyboard_interrupt** (itimer `(0.5, 1, 2, 4)`, run_bounded timeout stays
     20): the SIGALRM handler is installed and restored around the whole helper
     call. Inside `call`, `setitimer(d)` with a finally that resets it to 0, and
     `KeyboardInterrupt` is caught and returned. Check: `KeyboardInterrupt`, and
     SIGINT handler `is default_int_handler`. Both hold whether or not the fixture
     ran. After the loop: `_gone_within(pid)`.
   - **signal_during_cleanup** (grace 2, timeouts `(0.3, 0.6, 1.2, 2.4)`): the
     SIGHUP handler is installed and restored around the helper. Inside `call`, a
     `threading.Timer(d + 0.7, …SIGHUP)` is started and cancelled in a finally.
     This keeps the original "0.7 s into the [d, d+2] cleanup" placement. `call`
     catches and returns `(Hangup, TimeoutExpired)`. Check: if started,
     `Hangup` and `elapsed >= d + 2 - 0.3`; if not,
     `assertIsInstance(outcome, (Hangup, subprocess.TimeoutExpired))`.
     After the loop: `assertFalse(_alive(pid))`.
   - **stop_request_ignored** (grace 1, stop_grace 1, `(0.5, 1, 2, 4)`): call
     returns the result or the caught `TimeoutExpired`. Check: always
     `elapsed < d + 1 + 1 + 1.5`. If started, also `TimeoutExpired` and
     `elapsed >= d + 1 - 0.2`. If not, the outcome is a `TimeoutExpired`, or a
     `BoundedResult` whose `.stopped` is true. After the loop: `_gone_within(pid)`.
   - **cli_inherited_grace** (grace 3, `(0.5, 1, 2, 4)`): `--timeout f"{d:g}"`,
     and the subprocess timeout stays at 30. Check: always rc `TIMED_OUT` and
     `elapsed < d + 3 + 2.0`. If started, also `elapsed >= d + 3 - 0.3`. After
     the loop: `_gone_within(pid)`.
   - **expiry_kills / expiry_terms / keyboard_interrupt** use the same check
     whether or not the pid was written, because their original assertions hold
     in every deadline state. For expiry_terms the in-between state writes the
     marker with no pid, which is why `call` unlinks the marker on every attempt.

   The three split checks share one shape: "always: deadline outcome + ceiling;
   `if started:` the readiness-dependent assertions". Each gets a one-line comment
   pointing at the helper docstring. The comment says why a no-pid attempt gets no
   elapsed lower bound: start-up overhead is unbounded, and the trap state is
   unknown.
   - **git_cmd_timeout_reports_124**: the inline loop becomes a helper call. The
     check is unchanged: rc 124, `f"timed out after {d}s"`, `AIT_CREW_GIT_TIMEOUT`,
     and `elapsed < d + KILL_GRACE + 1`. Keep the deadlines as ints so the stderr
     text matches. Keep the existing comment explaining why it retries, shortened
     to point at the helper.

4. **Contract tests for the helper.** Add a new `TestRunUntilStarted(_TmpDirCase)`.
   It is in-process, and its fake `call`s write the pidfile themselves:
   - *stops at the first started attempt*: the call writes the pid of a real
     `sleep 30` Popen only when `d == 2`. Assert the deadlines seen are `[1, 2]`,
     the returned pid matches, and `check` got `started == [False, True]`.
   - *registers before asserting*: the call writes the pid, and `check` raises.
     Assert an `AssertionError` whose message names the attempt, and that the pid
     is in `self.leftovers`.
   - *fails at exhaustion*: the call never writes. Assert an `AssertionError`
     whose message names the last deadline, and that every deadline was tried.
   - *clears a stale pidfile*: the pidfile is pre-seeded and the call never
     writes. Assert the helper fails rather than returning the stale pid.

   Every pid that goes into `leftovers` must belong to a `sleep` process the test
   spawned itself, never an arbitrary number, because teardown SIGKILLs every pid
   in that list. Add `addCleanup(proc.wait)` to reap it.

## Verification

- Run the module directly:
  `python3 -m pytest tests/test_bounded_run.py -v`. Everything passes.
- **Slow-start pre-fix controls** (scratchpad driver, not committed).
  `control.py <source-file> <Class.test> <mode> <sleep>` reads a test-module
  source, rewrites `REPO_ROOT` to the real repo, injects a delay, execs the source
  as a module and runs the one test with `unittest`. There are two modes, one per
  pid-less state:
  - **`before-trap`**: inserts `sleep <s>; ` before every `trap '` (and
    `sleep <s>\n` after the git stub's `#!/bin/sh\n`). This gives the
    TERM-honoured shape on attempt 1. `<s>` ≈ 1.5 × the first deadline, so attempt
    2 succeeds: expiry_kills 1.5, expiry_terms 1.5, keyboard 0.75,
    signal_during_cleanup 0.45, stop_ignored 0.75, cli 0.75, git 1.5.
  - **`after-trap`**: rewrites `TERM; echo` → `TERM; sleep <s>; echo`, i.e.
    trap installed, pid write pending. Under `trap '' TERM` the `sleep` inherits
    the ignored TERM, so the fixture is SIGKILLed pid-less. `<s>` lies between the
    attempt-2 kill time (d₂ + grace) and the attempt-3 kill time (d₃ + grace). Two
    pid-less TERM-ignoring attempts run, and attempt 3 writes its pid during the
    cleanup: expiry_kills 4, expiry_terms 3 (its trap exits on TERM, so the bound
    is d₂ < s < d₃), keyboard 2.5, signal_during_cleanup 2.9, stop_ignored 3.5,
    cli 4.5. git is not applicable: its stub has no trap.
  - Old body (`git show HEAD:tests/test_bounded_run.py`), both modes → each of the
    six tests **fails**: post-mortem `_read_pid` after about 30 s, or the
    assertion.
  - New body, both modes → all six **pass**. The git test is a refactor, so it
    passes in before-trap mode on both bodies.
  - **`startup+before-trap`** (cli_inherited_grace only): the driver also
    replaces the module's `CLI` with
    `["sh", "-c", '[ -e "$F" ] || { : > "$F"; sleep 2.2; }; exec "$0" "$@"', sys.executable, bounded_run.py]`
    (F = a scratch flag file), so only the **first** CLI launch pays 2.2 s of
    start-up. It runs together with before-trap `sleep 0.75`. Attempt 1 is
    review's case: rc 124, no pid, elapsed ≈ 2.86, which is inside the
    [d+2, d+2.7) window the previous revision would have rejected. It must be
    accepted and retried. Attempt 2 starts normally, the trap is up by d=1, and it
    passes under the full original bounds. Two runs: both shapes are accepted
    without inference. Only the first launch is slow because a 2.2 s start-up on
    the **started** attempt would rightly break the existing d+3+2 ceiling. That
    2 s start-up slack is the test's pre-existing contract, unchanged here.
  - New body with no injection → passes on the first attempt.
  - The driver wraps `_TmpDirCase._run_until_started` so it can wrap `check`, and
    prints each attempt's `(deadline, started, outcome type, elapsed)`. Each run
    therefore shows which state it hit, not just that it passed. In particular,
    attempt 1 of the startup control must print about 2.86 s with `started=False`.
- `bash tests/run_all_python_tests.sh` and read the last line for the verdict
  (`set -o pipefail` if piped).

## Step 9

Commit with `test: … (t2147)`, then archive via the standard Step 9
post-implementation flow.

## Risk

### Code-health risk: low
None identified. This is a test-only change in one file. It mirrors t2142's loop, and contract tests cover the helper.

### Goal-achievement risk: low
- The no-pid acceptance sets were derived by reading `bounded_run.py`. Review found and reproduced two states that an earlier revision mishandled: trap installed with the pid pending, and start-up overhead counted in elapsed. · severity: low · → mitigation: none needed. The before-trap, after-trap and startup controls drive each state on both bodies.

## Post-Review Changes

### Change Request 1 (2026-10-26 12:40)
- **Requested by user:** The per-attempt SIGHUP timer in
  signal_during_cleanup called `timer.cancel()` without draining. A callback
  already past its wait survived the cancellation and signalled the next
  attempt; the review reproduced it as attempt 2 failing its 2.30 s cleanup
  bound at 2.10 s. Drain each timer inside the protected region, and cover a
  dispatched callback that crosses cancellation.
- **Changes made:** Added a module-level context manager,
  `_signal_after(delay, sig)`. Its callback sends under a lock, and only while
  still armed. It sends with `signal.pthread_kill` to the main thread, so the
  signal is pending there before the disarm can take the lock. Exiting disarms
  under that lock, then cancels and joins the timer. A signal is therefore either
  handled inside the block's exit, which sits inside `call`'s `except`, or never
  sent. signal_during_cleanup's `call` now uses it. Added
  `TestSignalAfter`, with two tests:
  - a dispatched callback, delayed by a patched slow `pthread_kill`, raises inside
    the block and never after it;
  - a block that ends before the delay is never signalled.
- **Verification:** The naive cancel-only version fails
  `test_a_dispatched_signal_never_outlives_the_block` ("Hangup not raised").
  The fixed version passed 20 runs out of 20. The signal_during_cleanup controls
  pass on the new body in before-trap and after-trap modes. The module ran
  33 tests, OK.
- **Files affected:** tests/test_bounded_run.py

### Change Request 2 (2026-10-26 12:55)
- **Requested by user:** `test_a_dispatched_signal_never_outlives_the_block`
  assumed the Timer worker would enter the fake kill during a 0.15 s body sleep,
  with no handshake. A worker delayed by 0.25 s let the correct helper cancel an
  undispatched callback, and the test failed with "Hangup not raised".
  Synchronise on callback entry; use timeouts only as failure ceilings.
- **Changes made:** The fake `pthread_kill` sets an `entered` Event. The block
  (delay 0) exits only after `entered.wait(10)`, where the 10 s is a failure
  ceiling. Once entered, the callback holds the helper's lock while armed, so the
  correct exit waits for the send whatever the timing. The 0.3 s pause after
  entry is documented as widening the cancel-only control's window, not as a
  synchronisation. `test_a_block_that_ends_first_is_never_signalled` now uses a
  60 s delay and asserts the exit returns in under 10 s, with no post-sleep.
- **Verification:** The naive cancel-only helper failed 5 runs out of 5, plain
  and with a 0.25 s late Timer worker. One delayed run shows the stray `Hangup`
  escaping the block. The fixed helper with the 0.25 s late worker passed 5 out
  of 5, and plain 20 out of 20.
- **Files affected:** tests/test_bounded_run.py

## Final Implementation Notes
- **Actual work done:** All in `tests/test_bounded_run.py`:
  - `_written_pid()`: reads the pidfile once, without waiting.
  - `_TmpDirCase._run_until_started(call, check, deadlines, pidfile=None)`:
    the t2142 retry loop, factored out. It registers the pid in a `finally`
    before any check or unexpected exception, prefixes check failures with the
    attempt, and fails once every deadline is spent.
  - `_signal_after(delay, sig)`: a context manager (added in Change Request 1)
    whose signal can never reach a later attempt.
  - The six post-mortem `_read_pid` tests and `test_git_cmd_timeout_reports_124`
    now go through the helper, with per-attempt deadlines and scaled bounds.
  - New classes `TestRunUntilStarted` (5 tests) and `TestSignalAfter` (2 tests).
    The module went from 24 to 33 tests.
- **Deviations from plan:** Change Requests 1 and 2 (above) added
  `_signal_after` and its two contract tests. The plan's "no-pid" rule was
  revised twice during plan review, before implementation, and was implemented
  as approved.
- **Issues encountered:**
  - pytest is not installed on this machine, so the suite ran on the unittest
    backend (`runner=unittest`).
  - The system `python3` (3.9) has no `yaml`, so the module cannot be imported
    there; the `~/.aitask` venv (3.13) is the interpreter used.
  - The control driver's trace filter first dropped attempt-1 lines, because
    unittest's `... ` header has no trailing newline; fixed with an unanchored
    grep.
  - In zsh, `$m` does not word-split; use `${=args}`.
- **Key decisions:**
  - A no-pid attempt gets no elapsed lower bound and no shape inference: it
    accepts any deadline outcome under the test's existing ceiling, because
    start-up overhead (interpreter, `Popen`) is unbounded and the trap state is
    unknown.
  - Readiness-dependent bounds apply only when the pid was written.
  - Expected exceptions are caught inside each test's `call` and returned, so
    unexpected ones propagate with their traceback.
  - Per-attempt signal timers drain under a lock and are joined.
  - Controls (scratch, not committed): before-trap, after-trap and
    startup-overhead injections. All six converted tests fail on the old body in
    both modes and pass on the new one. The naive cancel-only signal timer fails
    `TestSignalAfter`; the fixed one passes, including with a late Timer worker.
- **Upstream defects identified:** None
