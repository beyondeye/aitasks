---
priority: medium
effort: high
depends: []
xdeps: [47_4]
xdeprepo: aitasks_go
issue_type: feature
status: Ready
labels: [monitor, go_engine]
gates: [risk_evaluated]
created_at: 2026-11-24 22:18
updated_at: 2026-11-24 22:18
---

## Context

Created from aitasks_go `t47_1` (its plan: `aiplans/p47/p47_1_monitord_skeleton_protocol_lifecycle.md`
in the aitasks_go repository, "Step 7 (post-approval)", item 3). aitasks_go
`t47` ports the shared monitor status server to Go as `ait-monitord`
(`goengines/cmd/ait-monitord`, shipped through the one-way goengines export).
This task is the client-side switch that lets a user OPT IN to the Go server.
**Python stays the default.** Making Go the default is out of scope and stays
gated on the classifier cross-check `t2034_6`.

Today nothing selects a Go server: `status_server._spawn_server` hardcodes
`[python, SERVER_SCRIPT, "serve", ...]`, and the only switch is
`AITASKS_MONITOR_SERVER=0` (server off).

## Why this is blocked on aitasks_go t47_4 (not on the lifecycle task)

`status_server.probe` accepts any server that answers `welcome` with the right
version, and `MonitorClient._attempt` falls back to the in-process scanner only
on `UNAVAILABLE`. The Go lifecycle skeleton (aitasks_go t47_5) has an EMPTY
producer and would be accepted: minimonitor would show an empty pane list and
never fall back. So:

- `xdeps` names aitasks_go `t47_4`, which completes the producer (it depends on
  t47_5, t47_2 and t47_3 through its sibling chain).
- `ait-monitord version` prints a readiness capability, `PRODUCER:none|full`.
  It is `none` until t47_4 sets `full`. The launcher must refuse anything but
  `PRODUCER:full` BEFORE spawning, so a dev-slot build of a mid-series tree can
  never be activated either.

`ait-monitord version` output (text): `VERSION:<v>`, `COMMIT:<sha>`,
`CONTRACT:<n>`, `PROTO:<n>`, `PRODUCER:<none|full>`, `ENGINE:<abs path>`, one
per line; `--json` gives the same fields.

## Do

### The switch

- An opt-in env switch (proposed `AIT_GO_MONITOR=1`, shaped like `AIT_GO_TUI`
  / `AIT_USE_PYPY`) read in `status_server._spawn_server` / `ensure_server`.
- Resolve the binary like `testmap_resolve_engine` (`aitask_testmap.sh`): an
  explicit binary override, the dev slot (`$AITASKS_HOME/engine/dev/`), or
  `$AITASKS_HOME/engine/v<V>/ait-monitord`.
- Handshake before spawning: `VERSION` equal to the framework version (or the
  dev form for the dev slot), `PROTO` equal to `status_protocol.PROTO`, and
  `PRODUCER:full`.
- Spawn `<bin> serve --socket <sock> --lock-fd <fd> --version <V> --tmux-socket-path <T> --session <S> --project-root <R> [--grace G]`
  with the lock fd inherited, exactly as the Python server is spawned. The
  restart contract needs `serve --socket <sock>` adjacent, with the binary path
  as the token before `serve`.

### Fallback to the SHARED Python server at every Go-specific failure point

Today a failed start ends in `UNAVAILABLE`, which sends the client to its own
in-process scanner, not to the shared server. With the switch on:

1. **Before the spawn**: missing binary, or a `VERSION` / `PROTO` / `PRODUCER`
   mismatch -> spawn the Python server directly.
2. **The Go launch raises `OSError`, so no child exists** (an upgrade can
   remove or replace the binary between the version check and the launch;
   today `UNAVAILABLE:spawn_failed`): under the lock `ensure` still holds,
   spawn the Python server with the same lock fd and continue the probe loop on
   the remaining deadline. Nothing was bound, so there is no socket to clean.
   Only an `OSError` from the Python spawn still ends in `spawn_failed`.
3. **The Go child exits before `welcome`** (`proc.poll() is not None`; today
   `UNAVAILABLE:server_failed`): retry with the Python server inside the same
   `ensure` call. Socket ownership is safe: `ensure` still holds its own copy
   of the lock fd (the lock belongs to the shared open file description) and
   the exited child closed its copy. Read the Go child's last log line FIRST
   (the log is truncated on every spawn); remove a socket the child may have
   bound through `_remove_stale_socket`; spawn Python with the same lock fd;
   continue on the REMAINING deadline.
4. **Not recoverable inside `ensure`**: a Go child still alive at the deadline
   holds the lock, so no second server may start. `ensure` returns
   `UNAVAILABLE:start_timeout`; the client uses its in-process scanner.
   `GO_MONITOR_FALLBACK:start_timeout` names the remedy,
   `ait monitor --restart-server` (made to work below).

Every fallback prints `GO_MONITOR_FALLBACK:<reason>` only when the user opted
in.

### Verified recovery for a child stalled BEFORE binding

Such a child holds the inherited lock and has no socket file. Today
`_cmd_restart` calls `retire_one` only if the socket path exists; otherwise it
prints `NO_SERVER` and runs `ensure_server`, which waits on the held lock and
ends in `lock_timeout`. The gap is general (a Python server stalled before its
bind has it too); the switch makes it reachable.

- `restart` (and `status`) first ask `status_restart.find_server(target)`,
  which matches by the `serve --socket <target>` argv and needs no socket file.
  If a verified process exists, `retire_one` runs although the socket is
  absent: same owner re-check, SIGTERM, bounded wait, no SIGKILL. `NO_SERVER`
  only when there is neither a socket nor a matching process.
- `retire_one` on a socketless verified process reports `RETIRED:` or
  `RETIRE_FAILED:...|still_running` as usual; with no match and no socket it
  must not report `STALE` for a path that never existed.
- The directory-scoped `retire --all-keys --all-versions` (the install hook)
  enumerates stems from `monitor-*.lock` as well as `monitor-*.sock`, so an
  owner-scoped retire after an engine upgrade also reaches a socketless child
  of the replaced binary. A lock file with no socket and no process is skipped
  silently (lock files outlive their servers).
- Update the spec's "Restart" section and its contract table in the same change.

### Install and retire

- `install_engine_binary` / `lib/engine_install.sh` also install `ait-monitord`
  into `engine/v<V>/`, verified against its SUMS; a missing asset is a warning,
  never fatal.
- After the engine install replaces the binary (`ait setup`, `ait upgrade`) and
  after `ait engine build` (dev), run
  `status_restart.py retire --all-keys --all-versions --owner-path <binary>`.
- Check first (unverified claim from planning): `aitask_engine.sh` requires
  exactly one `BUILT:` line from `goengines/build.sh host`, which builds every
  `cmd/*`; with several commands that check may already fail.

## Acceptance tests

All on an isolated tmux server (`tmux -L`, scratch `TMUX_TMPDIR`,
`XDG_RUNTIME_DIR`, `HOME`) with one project session holding ONE KNOWN agent
pane. "The known pane" below means that pane id with its expected category in
the client's first snapshot.

Readiness:
- switch on, a `PRODUCER:full` binary -> the first snapshot contains the known
  pane;
- switch on, a `PRODUCER:none` binary -> Python serves, the known pane is
  present, `GO_MONITOR_FALLBACK:` names the reason;
- a `PRODUCER:full` binary whose first snapshot LACKS the known pane fails the
  test (the capability line alone is not accepted as proof).

Startup failures, with a fake engine binary answering `version` with
`PRODUCER:full`:
- `serve` exits non-zero at once -> `ensure` returns `STARTED`, the welcome
  says `server.impl == "python"`, the known pane is present,
  `GO_MONITOR_FALLBACK:server_failed:` carries the Go log line, exactly one
  process holds the lock;
- `serve` binds the socket, then exits before `welcome` -> the same, and the
  leftover socket was replaced (a different inode);
- the binary answers `version` and is gone before the launch (a fake that
  deletes itself after printing its `version` lines) -> the launch raises
  `OSError`, `ensure` returns `STARTED` with `server.impl == "python"`, the
  known pane is present, `GO_MONITOR_FALLBACK:spawn_failed:` names the error;
- `serve` stays alive WITHOUT binding a socket and never answers ->
  `UNAVAILABLE:start_timeout`, and NO Python server was spawned. Then, on the
  no-socket recovery path:
  1. assert no socket file exists and the lock is held;
  2. run `restart` WITH THE SWITCH OFF (with it on, the fake would stall
     again). For the installed version `restart` retires and then calls
     `ensure_server` and probes the replacement itself, so ONE invocation must
     print both `RETIRED:<sock>|pid=<the stalled child>` (not `NO_SERVER`) and
     `REPLACEMENT:<sock>|pid=<new pid>|version=<V>`, and exit 0; the stalled
     child is gone and the new pid differs;
  3. a client connected to that replacement gets `server.impl == "python"` and
     the known pane in its first snapshot;
  4. a following `ensure` returns `RUNNING:<sock>|<the same new pid>`, never
     `STARTED`;
- the same stalled fake, ignoring SIGTERM -> `restart` prints
  `RETIRE_FAILED:<sock>|pid=<pid>|still_running`, exits 1 and starts nothing.

## Protocol drift (advisory, from aitasks_go t47_1)

The Go codec is pinned to a Python reference generated from this repository at
a recorded commit. A change to `monitor/status_protocol.py`,
`monitor/status_recording.py`, the protocol spec, or
`tests/fixtures/monitor_status/basic.jsonl` needs the aitasks_go reference
regenerated (`goengines/ci/monitorproto_refgen.sh`, README "Python reference
and drift").
