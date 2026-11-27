---
Task: t2373_fix_control_start_no_server_second_listing.md
Base branch: main
Output branch: main
---

# t2373 — classify the one failed start listing, not a second probe

## Context

`TmuxControlClient._start_pass` (`.aitask-scripts/monitor/monitor_core.py`
~L1781) lists sessions via `_inspect()` (`run_async`, which drops stderr). When
that listing fails on a reconnect (`_expected_project_id` set), it calls
`_server_is_gone()`, which runs a **second** `list-sessions` through
`run_checked` and only then reads tmux's no-server answer. A server that comes
back between the two calls erases the outage: `lost_project` stays `""`, the
supervisor raises no `exit_seen`. Found by inspection while porting this code to
Go (aitasks_go#t134); the Go port now classifies the one listing that failed.

Fix: the start listing itself goes through `run_checked`, so its own outcome
says "no server"; the second probe disappears. Rule kept: only tmux's own
no-server answer counts — a timeout, a missing binary, an exception, any other
non-zero exit is "could not look", never absence.

## Changes

### 1. `.aitask-scripts/monitor/monitor_core.py`

- Replace `_inspect` with a checked listing returning both facts from ONE call:

  ```python
  async def _inspect(self) -> tuple[Optional[list[tuple[str, str]]], bool]:
      """List the server's sessions ONCE: ``(rows, no_server)``.

      ``rows`` is None when the listing failed. ``no_server`` is True only when
      THAT failure was tmux's own no-server answer (``run_checked`` outcome
      ``no_server``) — a timeout, a missing binary or any other failure is not
      it. Classified from the same call that failed: a second listing could
      meet a server that came back meanwhile and erase the outage (t2373).
      (Listing, never ``display-message -t`` — kept docstring paragraph.)
      """
      try:
          result = await asyncio.to_thread(
              self._gateway.run_checked,
              ["list-sessions", "-F", SESSION_ID_NAME_FORMAT], _START_QUERY_TIMEOUT,
          )
      except Exception:
          # Not being able to ask is not an answer. (An exception here would
          # also end the supervisor's reconnect loop for good.)
          return None, False
      if result.outcome == "ok":
          return parse_session_rows(result.stdout), False
      return None, result.outcome == "no_server"
  ```

  `asyncio.to_thread(run_checked)` is the exact call `_server_is_gone` already
  made on this path (same gateway, socket args, timeout, `tmux_text_kwargs`
  decoding, `parse_session_rows` splits on `\n` only — U+2028 names unaffected).
  No new gateway API.
- Delete `_server_is_gone` (its docstring rationale — why the reconnect must
  recognise a shutdown while the old client is closing — moves into a comment
  at the use site).
- `_start_pass`:

  ```python
  rows, no_server = await self._inspect()
  if rows is None:
      # Asked only on a reconnect: the server can go away while the previous
      # client is being closed, and that client's %exit is ignored (_closing).
      if self._expected_project_id is not None and no_server:
          self.lost_project = "server_gone"
      return False
  ```

- Update the `lost_project` attribute comment if it names the probe (it says
  "when tmux itself said there is no server to list" — still true; leave).

### 2. Tests

- **New unit class** in `tests/test_tmux_exec.py` (beside
  `TestControlAttachArgv`), `TestControlStartListing`, no tmux needed. The
  fake `_gateway` has ONE ordered reply queue of `TmuxResult`s shared by
  `run_async` and `run_checked`: each `list-sessions` call — through either
  method — pops the next reply and appends `(method, args)` to one call log.
  `run_async` returns the popped reply as `(rc, stdout)` (so `no_server` reads
  `(1, "")` there, the way `run_async` drops stderr); `run_checked` returns it
  whole. One queue is what makes the old code walk the real race: its
  `run_async` listing consumes the `no_server` reply, and its second-probe
  `run_checked` then sees the server back (`ok`). (Two separate scripts would
  let the old code meet `no_server` on both calls and fail only on call count.)
  Cases, driving `asyncio.run(client._start_pass(final=True))`:
  1. **the task's seam** — queue `[no_server, ok(project row)]`,
     `expected_project_id` set → returns False, `lost_project ==
     "server_gone"`, call log is exactly one `run_checked` listing, and the
     `ok` reply is still unconsumed.
  2. `[failed]` (timeout) → `lost_project == ""`, one call.
  3. `[no_tmux]` → `""` (no binary is not "no server").
  4. `run_checked` raises → returns False, `""`.
  5. `[no_server]` without `expected_project_id` (first start) → `""`.
  6. `[ok(rows without the project)]` on reconnect → `"gone"` (the existing
     path through the new return shape).
- **Red proof first, assertion by assertion**: add the class before touching
  `monitor_core.py` and run it against current code. Case 1 must fail **on the
  loss reason** — `lost_project == ""`, not `"server_gone"` — with the call
  log reading `run_async` then `run_checked` (two listings, the `ok` reply
  consumed by the second). Record that output verbatim in the plan's Final
  Implementation Notes. Then apply the fix and the same test is green on the
  first call. A red result that is only a call-count mismatch would not prove
  the outage was missed, so the loss reason is asserted before the call count.
- **Cancellation while the threaded listing is in flight** (new, same file,
  `TestControlStartListingCancel`). The existing live cancel tests hold
  `_verify_attach`, i.e. after the listing and the attach spawn; this one holds
  the listing itself. It runs at **client** level on the test's own loop, not
  through `TmuxControlBackend.start()`, because a failed backend start calls
  `self.stop()` before it returns: that stops the loop, joins its thread and
  clears `_starting`, so a release after it would see zero spawns from
  teardown alone. (`stop()` and the start timeout both end the start by
  cancelling the task running `client.start()` — `_cancel_reconnect_task` /
  `cf.cancel()` — which is what this test does directly.)
  - The fake `_gateway.run_checked` sets a `threading.Event` `entered`, blocks
    on `release`, sets `finished`, then answers `ok` with the project row (no
    helper row → create mode, so a spawn would come next). Patch
    `asyncio.create_subprocess_exec` (as `monitor_core` reaches it) with a
    recorder that logs the argv and raises `FileNotFoundError`, so nothing
    real is ever spawned.
  - Inside one `asyncio.run(...)`: `task = asyncio.create_task(client.start())`;
    `assert await asyncio.to_thread(entered.wait, 2)` ("listing never
    started"). Only after that succeeds, `task.cancel()`. Then, **with the loop
    still running**, `release.set()`, drain the worker with
    `assert await asyncio.to_thread(finished.wait, 2)` ("listing worker never
    finished"), and give the loop a few turns (`await asyncio.sleep(0.1)`).
    Assert `task.cancelled()`, exactly one `run_checked` call, recorder
    empty, `client._proc is None`. Both waits are asserted because
    `Event.wait` returns False on timeout. Ignored, a late worker would let the
    test cancel before the listing began and pass without testing anything.
    The body runs under `try/finally: release.set()`, and the test also
    registers `self.addCleanup(release.set)`, so a failed assertion cannot
    leave the worker thread blocked. The thread's `ok` answer arrives while the loop
    could still act on it, so a start that ignored the cancel would reach the
    spawn here, and the zero-spawn result cannot come from teardown.
  - **Positive control**: same harness, same loop and the same asserted waits
    and cleanup, with no `task.cancel()`: after release and drain, `await task`
    returns False and the recorder logs
    exactly one `tmux … -C` argv. That proves the recorder catches the spawn
    the cancel case says never happened, on the same route.
  - The subprocess timeout (`_START_QUERY_TIMEOUT`, child killed by
    `subprocess.run`) still bounds a listing that has already started; the
    discarded thread result is harmless.
- **Live pre-fix control** `tests/test_control_helper_session_live.py`
  `test_control_server_shutdown_without_the_no_server_probe_is_silent` patches
  `_server_is_gone`, which no longer exists. Re-target it: patch
  `TmuxControlClient._inspect` with a wrapper that calls the real one and
  returns `(rows, False)` — "a failed reconnect listing is never classified" —
  keeping its assertion (`exit_seen` False). Rename nothing else.

## Verification

```bash
python3 -m pytest tests/test_tmux_exec.py -q -k StartListing   # red before, green after
python3 -m pytest tests/test_tmux_exec.py -q
python3 -m pytest tests/test_control_helper_session_live.py -q  # live tmux, private sockets
python3 -m pytest tests/test_monitor_producer_seams.py -q
bash tests/test_tmux_control.sh; bash tests/test_tmux_control_resilience.sh
bash tests/test_no_raw_tmux.sh
grep -rn "_server_is_gone" .aitask-scripts tests   # expect nothing
```

The live file's `test_server_shut_down_between_timeout_and_reconnect` (real
kill-server during reconnect → `exit_seen`) and the stalled-server test
(timeouts are not a shutdown) exercise the thread-hop listing against real
tmux. The live cancel/timeout no-leak tests hold `_verify_attach`, after the
listing. Cancelling during the listing itself is covered by the new
`TestControlStartListingCancel`.

## Step 9

Post-implementation per task-workflow Step 9: commit code (`bug: … (t2373)`),
commit plan via `aitask_task_commit.sh`, archive.

## Risk

### Code-health risk: low
None identified. (Considered: the start listing now runs as `to_thread` +
`subprocess.run` instead of an asyncio subprocess, on every connect, not just
after a failure. That is the call already used on this path; it is bounded by
`_START_QUERY_TIMEOUT` (the child is killed on timeout), and a cancelled pass
holds no attach process during the listing, so `_abort_spawned` has nothing to
end. The new `TestControlStartListingCancel` cancels a live `client.start()`
task while the listing is in flight, then releases and drains the worker with
the loop still running, and checks that no attach is spawned. Its positive
control runs the same route.)

### Goal-achievement risk: low
None identified. The seam test is the reviewer's exact scenario, driven from
one ordered reply queue, and it fails on the loss reason against current code
before the fix.
