---
priority: medium
effort: medium
depends: [953]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [953]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 10:38
updated_at: 2026-06-11 10:59
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t953

## Verification Checklist

- [x] ait ide from a clean shell creates the session on the dedicated socket: `tmux -L ait ls` shows it, and the server runs under session.slice (`systemctl --user status` / systemd-cgls shows ait-tmux-*.service in session.slice, not app.slice) — PASS 2026-06-11 10:49 auto: ait ide spawned session on -L ait; server under ait-tmux-aitasks-*.service in session.slice (verified via systemctl Slice=session.slice + /proc cgroup), not app.slice
- [x] The user's personal default tmux server (`tmux ls`) is untouched by ait operations — PASS 2026-06-11 10:49 auto: default server (tmux ls) shows only pre-existing aitasks_go; ait spawned a server only on the -L ait socket, default untouched
- [x] With a same-name session alive on the default socket and none on the ait socket, `ait ide` shows the legacy-session prompt; answering y attaches to the legacy session, answering n creates a fresh session on the dedicated socket with the hint printed — PASS 2026-06-11 10:52 auto: legacy prompt fires when same-name session on default & none on ait; y attaches to legacy default-server session (ait socket stays empty); n prints 'Creating a fresh session' + AITASKS_TMUX_SOCKET=default hint and spawns on -L ait. pty-driven via script(1).
- [x] `AITASKS_TMUX_SOCKET=default ait ide` reaches the legacy default-socket session (explicit opt-out works end-to-end) — PASS 2026-06-11 10:51 auto: AITASKS_TMUX_SOCKET=default ait ide reached legacy aitasks on default server (added monitor window, attach failed only on non-TTY); ait socket stayed empty
- [x] Inside a personal (non-ait) tmux server, `ait ide` refuses with the socket-identity warning instead of failing cryptically or mutating the wrong server — PASS 2026-06-11 10:52 auto: inside a foreign 'personal' tmux server, ait ide refused with the socket-identity warning (names attached socket vs -L ait, suggests AITASKS_TMUX_SOCKET=personal ait ide) and exited 1; foreign server not mutated
- [x] The `j` TUI switcher cross-session teleport works between project sessions on the dedicated server (multi-project case) — PASS 2026-06-11 10:59 auto: live on -L ait — j switcher overlay listed multiple project sessions (aitasks/aitasks_go/aitasks_mob); selecting aitasks_go + Enter teleported attached client /dev/pts/11 from aitasks->aitasks_go via gateway-routed switch-client. (switcher unit suite 52/52)
- [x] ait monitor session-rename dialog and codebrowser focus handoff still work post gateway-routing (holdout migration smoke) — PASS 2026-06-11 10:59 auto: against live -L ait via real TmuxClient (socket_args=[-L,ait]) — SessionRenameDialog path rename-session -t =cur new rc=0 renamed on dedicated server; codebrowser focus handoff set/show/unset AITASK_CODEBROWSER_FOCUS round-tripped (read-back ok, unset cleared). monitor-rename-window unit 3/3.
