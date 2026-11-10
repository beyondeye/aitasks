---
Task: t2267_fix_monitor_client_start_after_close.md
Base branch: main
Output branch: main
---

# t2267 — `start()` after `close()` runs no attempt; scratchpad latency budgets measure the app

## Context

Two unrelated latent defects, both spawned from t2259's review.

1. **Closed-before-start client.** `MonitorClient.start()`
   (`.aitask-scripts/monitor/status_client.py:387-412`) checks only `_started`.
   `start_detached()` (`:438`) checks `self._started or self._closed`. So after
   `close()` on a client that never started, a later `start()` (called directly,
   or through `_await_ready()` from any read) still creates the startup task. Its
   `_attempt` then runs `ensure` in a worker thread, which may spawn the status
   server, and checks `_closed` only after `ensure` returns. No current caller
   does this, so the defect is latent.
   **Measured at planning time** (the candidate tests defined inline, `start()`
   patched in memory, no file written):
   - pre-fix: both new tests fail with `AssertionError: 1 != 0` on `ensure.calls`;
   - fixed: both pass;
   - the existing file (61 tests) on the fixed `start()`: `failures=0 errors=0`.

2. **Scratchpad latency budgets measure Textual's test harness, not the app.**
   `tests/test_scratchpad_app.py:930` asserts that `ctrl+q` exits within 1.0 s,
   timed around `pilot.press`. Under load it failed at 2.016 s. `press_timed`
   (`:283`), used at `:355` (test_04) and `:921` (14g), has the same shape.
   `pilot.press` → `App._press_keys` sends the key and then runs
   `wait_for_idle(0)` twice (Textual 8.2.7 `_wait.py`). Each call keeps sleeping
   in 20 ms windows until the process's CPU time advances by less than 1 ms in a
   window, **capped at 1 s**. A busy process therefore holds every press for up
   to about 2 s.
   **Measured:**
   - with `textual._wait.SLEEP_IDLE = -1` set from the moment `ctrl+q` is
     handled, the unmodified 14g fails at `:930` with `2.043 not less than 1.0`
     (reported: 2.016);
   - in that same run, key → `action_flush_quit` took 0.000 s, key →
     `_sp_exit_now` 0.001 s, and key → press-returned 2.039 s;
   - unloaded: key → `_sp_exit_now` 0.001 s, press returned at 0.062 s.

   So the budget measures the pilot's idle settle. The 0.3 s per-key bounds
   share the mechanism: with the process busy for the whole test, the old
   test_04 and the old 14g both fail at `b` (`2.007` / `2.010 not less than
   0.3`). They have not failed in the suite yet only because a typed key is
   cheap. **User decision (planning):** fix all three sites, not only `:930`.

   **What the budgets protect** (the t2073_2 plan, case 14g and risk lines): the
   loop must not block on a save, including through a blocking `waitpid` on an
   unkillable helper; and `ctrl+q` while STUCK must exit promptly, **without**
   waiting for the stuck child. The fix keeps those properties and times the app
   itself: from posting the key to its observable effect.

## Implementation

1. **`.aitask-scripts/monitor/status_client.py` — `start()`.**
   - Add before the `if self._started:` branch:
     ```python
     if self._closed:
         # A closed client never starts, as start_detached() refuses it: no
         # attempt, so no ensure() and no spawned status server.
         return True
     ```
     Nothing is set: `_started` stays `False` and `_start_task` stays `None`.
   - Add a docstring sentence: on a closed client, `start()` returns True at
     once without an attempt, as `start_detached()` does, so a read on a client
     closed before it started never runs `ensure` either. Returning True keeps
     the "resolved either way" contract.
   - `_await_ready()` (`:939`) is unchanged. It calls `start()` while
     `_started` is False, and the early return now covers it.

2. **`aidocs/framework/monitor_status_protocol.md`, "Connection setup and the
   local control client" (after the "Cancelling a caller never cancels the
   startup" bullet, ~`:1099`).** New current-state bullet:
   - **A closed client never starts.** After `close()`, `start()` returns at
     once and `start_detached()` does nothing.
   - Neither runs an attempt, so neither calls `ensure` nor spawns the status
     server.
   - A read on a client closed before it started therefore runs no attempt
     either. Reads reach `start()` through their ready wait.

3. **`tests/test_monitor_status_client.py` — two tests in `CloseTests`** (`:1296`):
   - `test_start_after_close_runs_no_attempt` does `c = self.client()`, then
     `await c.close()`, then `assertTrue(await wait_for(c.start(), 3.0))`. It
     then asserts:
     - `self.ensure.calls == 0` (message: "start() on a closed client ran an
       attempt");
     - `c._start_task is None`;
     - `c._started is False`.
   - `test_a_read_after_close_runs_no_attempt` does `close()`, then
     `await wait_for(c.capture_all_async(), 3.0)`, then asserts
     `ensure.calls == 0` (message: "a read on a closed client ran an attempt")
     and `c._start_task is None`.

4. **`tests/test_scratchpad_app.py` — time the key, not the pilot.**
   - Import `from textual import events` beside the other `textual` imports
     (`:54-57`).
   - **Replace `press_timed` (`:283-286`)** with three `_Base` helpers:
     - `key_latency(app, key, handled, timeout=10.0) -> float`. It builds the
       event exactly as the pilot does: `events.Key(key, key if len(key) == 1
       else None)`, then `set_sender(app)`. It posts the event with
       `app.post_message`, the same queue the pilot's driver uses. It then
       polls `handled()` every 0.01 s and returns the seconds from post to
       effect. Past `timeout` (liveness only) it calls `self.fail("timed out
       waiting: <key> handled")`. Docstring: why not `pilot.press` (the idle
       settle above, with the measured 2.04 s press for a 1 ms exit).
     - `type_latency(app, key)` computes `expected = app._sp_editor.text + key`
       and returns `key_latency(app, key, lambda: app._sp_editor.text ==
       expected)`. The cursor is at the end of the text at both call sites.
     - `record_action(app, name) -> list`. Like `record_exit`, it wraps
       `app.action_<name>` on the instance and appends `time.monotonic()` per
       call. Textual resolves actions with `getattr(namespace, "action_…")`, so
       the instance wrapper is the one dispatched.
   - **test_04 (`:342-364`).**
     - Take `saves_now = self.record_action(app, "save_now")` right after
       `owner()`.
     - The `b`…`f` loop becomes `assertLess(await self.type_latency(app, key),
       0.3, key)`.
     - `ctrl+s` becomes `n = len(saves_now)` and then `assertLess(await
       self.key_latency(app, "ctrl+s", lambda: len(saves_now) > n), 0.3,
       "ctrl+s")`.
     - Not the `_sp_save_now_requested` flag: with slow setup presses the
       1 s debounce can start the save before `ctrl+s`. The flag is then
       already True and the predicate passes vacuously. This was measured: the
       flag precondition failed under the busy injection, and the action
       recorder passes.
     - The remaining assertions are unchanged.
   - **14g (`:913-932`).**
     - The `b`…`f` loop uses `type_latency`.
     - Replace `t0 = …`, `pilot.press("ctrl+q")`, the `wait_for(…exit…)` and
       `assertLess(… 1.0)` with:
       ```python
       proc = app._sp_stuck_proc
       self.assertIsNotNone(proc)
       self.assertLess(await self.key_latency(app, "ctrl+q", lambda: app._sp_shutdown), 1.0)
       self.assertIsNone(proc.poll(), "quit waited for the stuck save's child")
       ```
     - Comment: the fake child sleeps 60 s. A quit that waits on it, blocking
       or not, misses the 1 s budget by more than an order of magnitude and
       leaves `proc` exited.
     - The `ctrl+s` press stays an untimed `pilot.press`, and the
       `saves`/`unresolved` assertions are unchanged.
   - `press_timed` has no other caller. Delete it rather than keeping it
     unused.

### Assertion classes and pre-fix controls

| Test / assertion | Class | On the baseline |
|---|---|---|
| new `test_start_after_close_runs_no_attempt`: `ensure.calls == 0` | D | **red, failure** `1 != 0` (measured) |
| same: `start()` True, `_start_task is None`, `_started` False | D/P | not reached on the baseline (fails first on calls) |
| new `test_a_read_after_close_runs_no_attempt`: `ensure.calls == 0` | D | **red, failure** `1 != 0` (measured) |
| every existing client test | P | green on the fixed `start()` (61/61, measured) |
| test_04 / 14g latency assertions | C (measurement moved from pilot settle to key → effect) | old: **red** under the busy injection (2.007 / 2.010 vs 0.3); new: green under the same injection (measured) |
| 14g `proc.poll() is None` | S (states the no-wait property without timing) | green on current code |

### Mutation controls (still catch a genuinely blocked loop; measured at planning, new bodies)

- **M1:** `_sp_poll_stuck` first blocks in `proc.wait(timeout=1.0)`. 14g fails
  at `b` with `1.004 not less than 0.3`.
- **M2:** the quit-while-STUCK branch never exits, so quit waits
  asynchronously for the child. 14g fails with `timed out waiting: 'ctrl+q'
  handled`.
- **M3:** that branch first calls `self._sp_stuck_proc.wait()`, so quit blocks
  on the child. 14g fails with `58.38 not less than 1.0` (about 60 s run).
- **M4:** `_sp_await_store` swaps `await asyncio.sleep(POLL)` for
  `time.sleep(1.0); await asyncio.sleep(0)`. test_04 fails at `b` with about
  `3.00 not less than 0.3`, 3 of 3 runs.

## Verification

1. **Both files green.**
   ```bash
   PY="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   "$PY" -m unittest tests.test_monitor_status_client tests.test_scratchpad_app 2>&1 | tail -5
   ```
2. **Client red proof.** Record the literal pre-fix SHA first, and never stash.
   - `git worktree add --detach "$SCRATCH/proof" <sha>`;
   - copy the new `tests/test_monitor_status_client.py` into it and run it
     there;
   - expect exactly the two new tests to fail, as **failures** with `1 != 0`.
   - Remove the worktree afterwards.
3. **Scratchpad red proof and controls.** A scratch script (in the scratchpad
   dir, run with the ait Python from `tests/`) runs these:
   - old test_04/14g from the proof worktree, with `textual._wait.SLEEP_IDLE =
     -1`: expect `b` failures of about 2.0 s;
   - new test_04/14g, normally and under the same injection: expect green;
   - M1–M4 applied in memory: anchored text substitution with
     `count(anchor) == 1` asserted, or a method wrapper for M1. Expect each to
     fail as listed above.

   The script and its output go **verbatim** into Final Implementation Notes.
4. **Full Python suite.**
   ```bash
   set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3
   ```
   Read only the last line (`PYTHON SUITE: …`).

## Step 9 (Post-Implementation)

Current-branch mode: commit
`bug: Refuse a closed MonitorClient's start and time scratchpad keys at the app (t2267)`.
Then archive through Step 9.

**Out of scope, noted but not inspected:** other wall-clock budgets near
`pilot.press` in `tests/test_frozenagent_app.py:1103`,
`tests/test_settings_artifacts_tab.py:683/693` and
`tests/test_minimonitor_startup_input_latency.py`. Whether they time the pilot
settle is a candidate Step 8b follow-up.

## Risk

### Code-health risk: low
- `start()` on a closed client now returns without an attempt. A caller that
  restarted a closed client expecting a reconnect would stay unsubscribed ·
  severity: low (residual — no caller restarts a closed client: the monitor apps
  and applink close only at teardown (t2259 audit), and `start_detached()`
  already refuses a closed client) · → mitigation: none
- The latency helpers post the key themselves instead of through the pilot's
  driver, so they could drift from the real key path · severity: low (residual —
  the event is built as the pilot builds it on the same app queue, and each
  timing ends on the key's observable effect (editor text, the `save_now` action
  call, `_sp_shutdown`), so an unhandled key times out instead of passing) ·
  → mitigation: none

### Goal-achievement risk: low
- The new bounds are still wall-clock (key → effect) · severity: low (residual —
  measured 0.001 s key → exit against 1.0 s, and per-key timings well under 0.3 s
  with the process held busy; a blocked loop or a quit that waits on the 60 s
  child misses by 3x to 58x (M1–M4)) · → mitigation: none

## Final Implementation Notes

- **Actual work done:** as planned.
  - `MonitorClient.start()` returns True at once on a closed client, with no
    attempt and nothing set, matching `start_detached()`.
  - The protocol doc has a "closed client never starts" bullet.
  - `CloseTests` has two new tests: `start()` after `close()`, and a read
    after `close()`.
  - In `tests/test_scratchpad_app.py`, `press_timed` is replaced by
    `key_latency` / `type_latency` / `record_action`. The 0.3 s per-key bounds
    (test_04, 14g) and the 1.0 s ctrl+q bound (14g) now time key → effect.
    14g also asserts that the stuck child is still running at exit.
- **Deviations from plan:** `key_latency` sends with `app._driver.send_message`,
  not `app.post_message`.
  - That is the exact call `App._press_keys` makes, and the technique t1660
    established in `tests/test_minimonitor_startup_input_latency.py`
    (`_press_and_observe`), which surfaced only after planning.
  - It removes the "drifts from the real key path" residual risk.
  - Wall-clock timing is kept deliberately, unlike t1660's turn count. The
    property here is that the loop never blocks on a save, and a blocked loop
    runs no turns, so a turn count would pass M1, M3 and M4. The docstring
    records this.
  - All controls were re-run on the final helper (results below).
- **Issues encountered:**
  - The full suite (`bash tests/run_all_python_tests.sh`, about 11 min) ended
    `PYTHON SUITE: FAILED (runner=pytest, exit=1)`: 1 failed, 11857 passed,
    6 skipped.
  - The failure was
    `tests/test_metadata_writer_inventory.py::NewWriterTripwire::test_no_unclassified_file_writes_metadata`.
    It flagged `.aitask-scripts/aitask_issue_update.sh` (modified) and
    `.aitask-scripts/lib/release_issue_ledger.sh` (untracked). Both belong to
    another session's uncommitted issue-update work in this shared worktree;
    t2267 touches neither file. The tripwire is working as intended.
  - That suite run collected the earlier `post_message` version of the helper.
    The final version was re-verified with
    `python -m unittest tests.test_scratchpad_app` (41 OK) and the probe below.
- **Key decisions:**
  - The user chose (at planning) to fix all three scratchpad bounds, not only
    the reported `:930`.
  - test_04 detects `ctrl+s` through an action-call recorder, not the
    `_sp_save_now_requested` flag. Under a slow setup, the debounce can start
    the save before `ctrl+s` and leave the flag already True. This was
    measured: the flag precondition failed under the busy injection.
- **Upstream defects identified:**
  - `tests/test_frozenagent_app.py:1092-1103 — the 2.0 s budget times ten pilot.press("shift+down") calls plus pilot.pause(); each press carries Textual's wait_for_idle settle (two calls, up to 1 s each), so a busy process can blow the budget whatever the incremental repaint costs (same mechanism as t2267's scratchpad bounds)`

### Verification record (verbatim)

Pre-fix SHA: `79416f14c44f9c0a329fdee722468c6b2f9422df`.

**Client red proof:** a detached worktree at that SHA, with the new
`tests/test_monitor_status_client.py` copied in:
```
FAIL: test_a_read_after_close_runs_no_attempt (tests.test_monitor_status_client.CloseTests.test_a_read_after_close_runs_no_attempt)
AssertionError: 1 != 0 : a read on a closed client ran an attempt
FAIL: test_start_after_close_runs_no_attempt (tests.test_monitor_status_client.CloseTests.test_start_after_close_runs_no_attempt)
AssertionError: 1 != 0 : start() on a closed client ran an attempt
Ran 63 tests in 4.231s
FAILED (failures=2)
```
After the fix, the whole file passes (63 tests), and both modified files
together pass (104 tests).

**Scratchpad red proof and controls.** The probe script is below. "proof" is
the pre-fix worktree's `tests/`; "aitasks" is the fixed tree.

Old tests (proof):
```
== proof normal: run=2 failures=0 errors=0 (3s)
== proof never_idle: run=2 failures=2 errors=0 (12s)
    test_04_input_responsive_and_saves_serialized_while_held -> AssertionError: 2.009989085025154 not less than 0.3 : b
    test_14g_unkillable_child_keeps_loop_responsive -> AssertionError: 2.007886284030974 not less than 0.3 : b
== proof never_idle_from_quit: run=1 failures=1 errors=0 (4s)
    test_14g_unkillable_child_keeps_loop_responsive -> AssertionError: 2.0426407520426437 not less than 1.0
```
New tests, final `driver.send_message` helper:
```
== aitasks normal: run=2 failures=0 errors=0 (2s)
== aitasks never_idle: run=2 failures=0 errors=0 (11s)
== aitasks never_idle_from_quit: run=1 failures=0 errors=0 (2s)
== aitasks M1: run=1 failures=1 errors=0 (3s)
    test_14g_unkillable_child_keeps_loop_responsive -> AssertionError: 1.0034151650033891 not less than 0.3 : b
== aitasks M2: run=1 failures=1 errors=0 (12s)
    test_14g_unkillable_child_keeps_loop_responsive -> AssertionError: timed out waiting: 'ctrl+q' handled
== aitasks M3: run=1 failures=1 errors=0 (60s)
    test_14g_unkillable_child_keeps_loop_responsive -> AssertionError: 58.39770950505044 not less than 1.0
== aitasks M4: run=1 failures=1 errors=0 (31s)
    test_04_input_responsive_and_saves_serialized_while_held -> AssertionError: 6.005580194992945 not less than 0.3 : b
```

Driver (from the repo root; `T04` and `T14` are the two `Class.test` names):
```bash
PY="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
run() { "$PY" t2267_scratchpad_probe.py "$@" 2>/dev/null | grep -E '^(==|   )'; }
run <proof>/tests never_idle "$T04" "$T14"     # likewise normal / never_idle_from_quit
run "$PWD/tests" M1 "$T14"                      # M2, M3 likewise; M4 with "$T04"
```

`t2267_scratchpad_probe.py`:
```python
"""t2267: scratchpad latency red proof + mutation controls.

usage: <ait python> t2267_scratchpad_probe.py <tests_dir> <mode> <Class.test> [...]
  mode: normal | never_idle | M1 | M2 | M3 | M4
One mode per process, so a mutant never leaks into another run.
"""
import inspect
import os
import subprocess
import sys
import textwrap
import time
import unittest

tests_dir, mode, *cases = sys.argv[1:]
os.chdir(tests_dir)
sys.path.insert(0, tests_dir)
import test_scratchpad_app as T  # noqa: E402
import textual._wait as W  # noqa: E402

sp = T.sp


def mutate(func, anchor, replacement):
    src = textwrap.dedent(inspect.getsource(func))
    assert src.count(anchor) == 1, (func.__name__, src.count(anchor))
    ns = {}
    exec(src.replace(anchor, replacement), sp.__dict__, ns)
    return ns[func.__name__]


QUIT_STUCK = ('            if self._sp_stuck_pgid is not None:\n'
              '                self._sp_exit_now(\n')

if mode == "never_idle":
    # wait_for_idle compares each 20 ms window's CPU time against SLEEP_IDLE
    # (read as a global per iteration): -1 means "never idle", so every
    # pilot.press runs both of its idle waits to the 1 s cap.
    W.SLEEP_IDLE = -1.0
elif mode == "never_idle_from_quit":
    # Busy only once ctrl+q is handled: reproduces the reported :930 failure
    # (the per-key presses before it settle normally).
    real_flush = sp.ScratchpadApp.action_flush_quit

    def busy_flush(self):
        W.SLEEP_IDLE = -1.0
        return real_flush(self)

    sp.ScratchpadApp.action_flush_quit = busy_flush
elif mode == "M1":
    # Blocking waitpid in the stuck poll: the loop blocks up to 1 s per poll.
    real_poll = sp.ScratchpadApp._sp_poll_stuck

    def m1(self):
        if self._sp_stuck_proc is not None:
            try:
                self._sp_stuck_proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        return real_poll(self)

    sp.ScratchpadApp._sp_poll_stuck = m1
elif mode == "M2":
    # Quit while STUCK never exits: it waits (asynchronously) for the child.
    sp.ScratchpadApp._sp_save_loop = mutate(
        sp.ScratchpadApp._sp_save_loop, QUIT_STUCK,
        QUIT_STUCK.replace("is not None:", "is not None and False:"))
elif mode == "M3":
    # Quit while STUCK blocks the loop on the child before exiting.
    sp.ScratchpadApp._sp_save_loop = mutate(
        sp.ScratchpadApp._sp_save_loop, QUIT_STUCK,
        '            if self._sp_stuck_pgid is not None:\n'
        '                self._sp_stuck_proc.wait()\n'
        '                self._sp_exit_now(\n')
elif mode == "M4":
    # The held save's poll blocks the loop 1 s per iteration, yielding once.
    sp._sp_await_store = mutate(
        sp._sp_await_store, "            await asyncio.sleep(POLL)\n",
        "            time.sleep(1.0)\n            await asyncio.sleep(0)\n")
elif mode != "normal":
    sys.exit(f"unknown mode {mode}")

suite = unittest.TestSuite(
    getattr(T, cls)(meth) for cls, meth in (c.split(".") for c in cases))
t0 = time.monotonic()
with open(os.devnull, "w") as sink:
    r = unittest.TextTestRunner(verbosity=0, stream=sink).run(suite)
print(f"== {os.path.basename(os.path.dirname(os.path.abspath(tests_dir)))} {mode}: "
      f"run={r.testsRun} failures={len(r.failures)} errors={len(r.errors)} "
      f"({time.monotonic() - t0:.0f}s)")
for t, tb in r.failures + r.errors:
    print("   ", t._testMethodName, "->", tb.strip().splitlines()[-1])
```
