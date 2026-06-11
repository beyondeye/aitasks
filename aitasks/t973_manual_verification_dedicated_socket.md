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
updated_at: 2026-06-11 10:42
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t953

## Verification Checklist

- [ ] ait ide from a clean shell creates the session on the dedicated socket: `tmux -L ait ls` shows it, and the server runs under session.slice (`systemctl --user status` / systemd-cgls shows ait-tmux-*.service in session.slice, not app.slice)
- [ ] The user's personal default tmux server (`tmux ls`) is untouched by ait operations
- [ ] With a same-name session alive on the default socket and none on the ait socket, `ait ide` shows the legacy-session prompt; answering y attaches to the legacy session, answering n creates a fresh session on the dedicated socket with the hint printed
- [ ] `AITASKS_TMUX_SOCKET=default ait ide` reaches the legacy default-socket session (explicit opt-out works end-to-end)
- [ ] Inside a personal (non-ait) tmux server, `ait ide` refuses with the socket-identity warning instead of failing cryptically or mutating the wrong server
- [ ] The `j` TUI switcher cross-session teleport works between project sessions on the dedicated server (multi-project case)
- [ ] ait monitor session-rename dialog and codebrowser focus handoff still work post gateway-routing (holdout migration smoke)
