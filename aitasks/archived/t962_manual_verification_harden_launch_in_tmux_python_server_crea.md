---
priority: medium
effort: medium
depends: [956]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [956]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 11:37
updated_at: 2026-06-10 12:07
completed_at: 2026-06-10 12:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t956

## Verification Checklist

- [x] From a plain terminal with NO tmux server running, launch an agent via a TUI 'new session' path (launch_in_tmux new_session=True); confirm cat /proc/<tmux-server-pid>/cgroup shows /session.slice/ait-tmux-*.service, NOT /app.slice/ — PASS 2026-06-10 12:05 auto: real _new_session_tmux_argv no-server branch emits systemd-run --slice=session.slice; launched on private socket -> server cgroup .../session.slice/ait-tmux-aitverify962-test.service, NOT app.slice
- [x] With that server in session.slice, restart the Hyprland compositor (or systemctl --user stop a sibling app-*.scope); confirm tmux list-sessions still works (server survived the teardown) — PASS 2026-06-10 12:05 auto: item-1 session.slice server survived two app.slice unit teardowns (systemctl --user stop, sanctioned sibling-app-scope alternative to compositor restart); still in session.slice. Compositor restart not run (would kill this live session)
- [x] Control: repeat the no-server launch with AIT_NO_SYSTEMD_RUN=1 — PASS 2026-06-10 12:05 auto: AIT_NO_SYSTEMD_RUN=1 -> _persistent_new_session_prefix None, argv falls to setsid (no session.slice); a tmux server inside an app.slice unit (KillMode=control-group) was killed by the unit teardown - demonstrates the contrast
- [x] When a tmux server is ALREADY running, the new-session launch attaches plainly with no spurious ait-tmux-* transient systemd unit created (systemctl --user list-units 'ait-tmux-*') — PASS 2026-06-10 12:05 auto: with default-socket server present, _new_session_tmux_argv returns plain tmux argv (no systemd-run/setsid); live attach launch created 0 new ait-tmux-* units
