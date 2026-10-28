---
priority: medium
effort: medium
depends: [2037]
xdeps: [17, 23]
xdeprepo: aitasks_go
issue_type: feature
status: Ready
labels: [monitor, tmux]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-25 09:36
---

The `ait-monitord` binary skeleton (parent: Go monitor status server task).

## Do

- `goengines/cmd/ait-monitord` (name per the parent) with a Go codec for the
  t2034_3 protocol; conformance tests against the recorded fixtures and the
  Python codec's round-trip cases.
- Lifecycle identical to the Python server: socket path per (tmux socket,
  `VERSION`), `ensure` under an exclusive lock (`internal/platform` flock), idle
  exit, stale-socket recovery, shutdown on control-mode `%exit` (through the Go
  tmux package, aitasks_go#17).
- The switch that selects the Go or Python server; the Python one stays the
  default.

## Verification

`ait engine test`; lifecycle tests mirroring the Python server's.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t17_2** id=2026-10-28T16:04:06Z.c09a974edd7625c11932989f from=aitasks_go#t17_2 from_verified=yes at=2026-10-28T16:04:06Z base=444391966b2c7625e47a8a0b2736cdca84272082 base_branch=main dirty=no host=omg16
>
> | aitasks_go t17_2 (commit 79c4a43, as of this tree) landed the Go control-mode client in goengines/tmux; this is what "shutdown on control-mode %exit" plugs into.
> | 
> | - Shutdown route (tested live): b := tmux.NewControlBackend(runner, session, tmux.WithOnClientExit(func(i tmux.ExitInfo){ if i.Kind == tmux.ExitTmux { b.Stop() } })). The callback runs on its own goroutine, never on the supervisor, and may call Stop. Stop waits for the supervisor and any in-flight Start, never for callbacks, and no reconnect client survives it.
> | - tmux 3.8 sends a BARE "%exit" (no reason text) both for kill-session of the attached session and for detach-client. ExitInfo.Reason therefore cannot tell "session gone" from "client detached". If monitord must only exit when the session or server is really gone, check that separately: e.g. let the supervisor's reconnect fail and see StateFallback, or run has-session via Runner.RunChecked.
> | - The supervisor reconnects after %exit too (Python parity). With the session gone, every attach fails and the state ends at StateFallback after len(backoffs) attempts.
> | - Only tmux.ControlEligible argvs ride the channel: an allowlist of full verb names that answer in one reply block, no pane creators, no ";" sequences. Runner.RunViaControl routes the rest to the subprocess. Nested commands (if-shell, run-shell -C, source-file) answer in a 2nd block on -C, so they are deliberately excluded.
> | - One server per tmux socket: a control client is per *session* (attach -t =<session>), so a server-wide watcher must pick a session to attach to.
