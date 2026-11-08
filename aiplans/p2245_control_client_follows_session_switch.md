---
Task: t2245_control_client_follows_session_switch.md
Base branch: main
Output branch: main
---

# t2245 — Control client must die when tmux switches it to another session

## Context

`TmuxControlClient` (`.aitask-scripts/monitor/monitor_core.py:1507`) attaches with
an exact-match `=<session>` target (t2242). But once attached, if the session is
destroyed under `detach-on-destroy off` (set in the user's tmux.conf), tmux does
not send `%exit` — it moves the live control client onto another session. The
reader loop ignores every non-`%exit` notification, so the backend stays
`CONNECTED` and every default-target query (`display-message`, `list-panes`
without `-t`, …) is answered from another project.

Probed on tmux 3.8 (isolated `-L` servers, `-f /dev/null`):

- Attach → `%begin/%end` ack (flags 0), then `%session-changed $0 zz`.
- `kill-session -t =zz` with `detach-on-destroy off` → `%session-changed $2 other sess`
  (new id; name may contain spaces), followed by later commands answering from it.
- `kill-session` sent *over the channel itself* → its `%begin/%end` block closes
  first, then `%session-changed $1 zz_mob`.
- `rename-session` of the attached session → `%session-renamed $2 zz3` (same id,
  no `%session-changed`).
- `switch-client -c <ctl> -t =zz_mob` → `%session-changed $1 zz_mob`.

So the attached session's identity is the id from the first `%session-changed`;
any later `%session-changed` naming a different id means this client now serves
another session. Chosen fix (task's option 2): treat that as death — the same
outcome `detach-on-destroy on` produces via `%exit`. Option 1 (setting
`detach-on-destroy` at attach) is rejected: it is a session option and would
change the user's own interactive clients.

## Implementation

### 1. `monitor_core.py` — detect the switch in `_reader_loop`

- Add module regex beside `_EXIT_RE`:
  `_SESSION_CHANGED_RE = re.compile(r"^%session-changed\s+(\$\d+)(?:\s.*)?$")`
  (only the id is captured — names are never compared, so non-UTF-8 / spaced
  names cannot false-trigger).
- `__init__`: `self._session_id: Optional[str] = None` — the anchored id.
- Extend `saw_exit` doc comment: also set when tmux switched this client to a
  different session (`detach-on-destroy off`, or a `switch-client` of the
  control client) — the same "attached session went away" event.
- New method (one seam, patchable by the live pre-fix control):
  ```python
  def _switched_away(self, session_id: str) -> bool:
      """True when a %session-changed moves this client off the session it
      attached to. The first notification (sent right after attach, to the
      exact-match target) anchors the id; renames keep the id."""
      if self._session_id is None:
          self._session_id = session_id
          return False
      return session_id != self._session_id
  ```
- In the outside-capture branch of `_reader_loop`, after the `_EXIT_RE` arm:
  ```python
  elif (m2 := _SESSION_CHANGED_RE.match(line)) and self._switched_away(m2.group(1)):
      self.saw_exit = True
      self._detach_switched_client()
      break  # now serving another session: treat as the session going away
  ```
  Breaking reaches `finally: _teardown_pending()`, so every pending/later
  request gets `(-1, "")` and nothing is delivered from the other session.
- `_detach_switched_client()`: unlike `%exit`, the tmux process is still alive
  and attached to the other session, and the supervisor swaps `_client` without
  `close()`. Close stdin (tmux drops a control client on EOF) — best-effort,
  `getattr(self._proc, "stdin", None)`, skip when `is_closing()`, suppress
  exceptions. No `await` here (the reader must not await its own `close()`).

No supervisor / status-server change needed: `_supervisor_loop` already copies
`saw_exit` into `_exit_seen` and reconnects with the exact-match argv (fails
→ FALLBACK if the session is gone, succeeds if it was recreated); the status
server's `_handle_exit_seen` probes tmux and restarts the client on a live
session.

### 2. Unit tests — `tests/test_monitor_producer_seams.py` (`ExitAndAccessorTests`)

Fake proc with a fed `StreamReader` plus a stub stdin recording `close()`:
- switch: `%session-changed $0 x` then `%session-changed $3 x_mob` → `saw_exit`,
  not alive, stdin closed.
- a pending future + a response block after the switch (`%begin 1 5 1`/`x_mob`/
  `%end 1 5 1`) → future resolves `(-1, "")`, never `x_mob`.
- rename: `%session-changed $0 x`, `%session-renamed $0 y`, `%session-changed $0 y`
  → not `saw_exit`, stdin not closed.
- spaced name in the new session (`%session-changed $2 other sess`) → detected.
- first notification only → not `saw_exit` (anchor only).

### 3. Live regression — `tests/test_tmux_control_resilience.sh` new Case B3

Own fixture `FB3` (added to the trap list and header comment). Explicitly
`tmux set-option -g detach-on-destroy off` (does not rely on the user's conf);
target `<S>` and decoy `<S>_mob` running.

- **Pre-fix control**: patch `TmuxControlClient._switched_away` to
  `lambda self, sid: False` (and so no detach); start backend, kill `=<S>`; assert
  that within a few seconds the *first* client is still alive, state
  `CONNECTED`, and `display-message -p '#{session_name}'` answers the decoy —
  else the regression is vacuous. Restore the method.
- **Fix**: recreate `<S>`, start backend, assert WHO == `<S>`; kill `=<S>`;
  poll: the first client must go dead, `b.exit_seen` true, and no WHO answer
  may ever equal the decoy. Assert no control-mode client remains on the decoy
  (`list-clients -F '#{client_control_mode} #{session_name}'`). Then recreate
  `<S>` and assert the supervisor reconnects (`CONNECTED`, new client) and WHO
  answers `<S>` — exercises full recovery without waiting out the 15 s backoff.
- Update Case B2's comment: it still pins `on` to isolate the reconnect path;
  B3 now covers the `off` behaviour.

### 4. Docs — `aidocs/framework/monitor_status_protocol.md` (~line 896)

The `%exit` bullet: add that a switch of the control client to another session
(`detach-on-destroy off`) is treated the same as `%exit` from a session destroy.
Current-state wording only.

### Post-phase (risk mitigations)

1. [status_server_switch_restart] In `tests/test_monitor_status_server_live.py`
   `TmuxExitTests`, add `test_session_switch_restarts_the_control_client`:
   create sessions `s1` (project `pa`, `agent-pick-1`) and `s2` (project `pb`),
   then `self.tmux("set-option", "-g", "detach-on-destroy", "off")`. `ensure`
   with `--grace 120`, then wait for `control_state == "connected"` (same loop as
   `test_server_exits_when_tmux_goes_away`; the server serves `sorted(mapping)[0]`
   = `s1`). Then `kill-session -t =s1`. Assert the server process stays
   alive, `server_log` contains `restarting the control client` within the
   deadline, and a later refresh reports `control_state == "connected"` again
   (now on `s2`), with no `EXIT:` line in the log. Update the module docstring's
   "Covered" list. (A pre-fix control is not possible in the subprocess server;
   Case B3 carries the mechanism's pre-fix control.)

## Verification

- `bash tests/test_tmux_control_resilience.sh` (all cases, incl. B3 control + fix).
- `python -m pytest tests/test_monitor_producer_seams.py` (via the venv python) /
  `bash tests/run_all_python_tests.sh --test-dir` subset if needed.
- `tests/test_monitor_status_server.py`, `tests/test_tmux_control*.py` /
  `tests/test_tmux_control*.sh` neighbours re-run for regressions.
- `shellcheck tests/test_tmux_control_resilience.sh`.
- `python3 tests/test_monitor_status_server_live.py` (venv python), incl. the new
  post-phase case.

## Step 9

Post-implementation: commit code (`bug: … (t2245)`), plan via
`aitask_task_commit.sh`, archive per Step 9.

## Risk

### Code-health risk: low
- A switch now raises `saw_exit`, so the status server also takes its "session detach → restart control client" path on a switch. That path is already live-tested only for a real `%exit`, not for one produced by a switch · severity: low · → mitigation: inline post-phase status_server_switch_restart
- Closing stdin from inside the reader loop is a new teardown route. The process is reaped by asyncio's child watcher, the same way as after `%exit`, but nothing awaits `wait()` · severity: low · → mitigation: inline post-phase status_server_switch_restart

### Goal-achievement risk: low
- The id anchor depends on tmux sending `%session-changed` right after attach. This was verified on tmux 3.8. A tmux that did not send it would take the first switch as the anchor and miss it. That fails open (today's behaviour), never wrongly kills a client · severity: low · → mitigation: none (fails open; covered by Case B3 + unit tests)

### Planned mitigations
- timing: post-phase | name: status_server_switch_restart | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: status-server restart path + stdin-close teardown on a switch | desc: live status-server test that a detach-on-destroy-off session switch restarts the control client
