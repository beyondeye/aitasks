---
priority: medium
effort: medium
depends: [956]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [956]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 11:37
updated_at: 2026-06-10 11:53
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t956

## Verification Checklist

- [ ] From a plain terminal with NO tmux server running, launch an agent via a TUI 'new session' path (launch_in_tmux new_session=True); confirm cat /proc/<tmux-server-pid>/cgroup shows /session.slice/ait-tmux-*.service, NOT /app.slice/
- [ ] With that server in session.slice, restart the Hyprland compositor (or systemctl --user stop a sibling app-*.scope); confirm tmux list-sessions still works (server survived the teardown)
- [ ] Control: repeat the no-server launch with AIT_NO_SYSTEMD_RUN=1 — server lands in /app.slice/ and the same teardown kills it (demonstrates the contrast)
- [ ] When a tmux server is ALREADY running, the new-session launch attaches plainly with no spurious ait-tmux-* transient systemd unit created (systemctl --user list-units 'ait-tmux-*')
