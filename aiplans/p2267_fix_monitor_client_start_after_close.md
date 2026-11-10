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
