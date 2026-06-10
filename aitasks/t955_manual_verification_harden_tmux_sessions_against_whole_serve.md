---
priority: medium
effort: medium
depends: [943]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [943]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 09:30
updated_at: 2026-06-10 11:35
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t943

## Verification Checklist

- [ ] Server escapes app.slice via real launch: run `ait ide` in a fresh graphical workspace, find the tmux server PID (pgrep -x tmux / parent of a pane_pid), `cat /proc/<pid>/cgroup` → contains `/session.slice/ait-tmux-…service` and NOT `/app.slice/`; `systemctl --user list-units 'ait-tmux-*'` shows it active.
- [ ] Survives compositor teardown (the real proof): with the server in session.slice, restart the Hyprland compositor (or `systemctl --user stop` a sibling `app-Hyprland-*.scope`) → `tmux list-sessions` still works and the ait session/panes survive.
- [ ] Negative control: rerun the teardown with `AIT_NO_SYSTEMD_RUN=1` (server lands in app.slice) and confirm the SAME teardown DOES kill it — demonstrating the contrast.
- [ ] Fallback rung on a non-systemd host (or with `AIT_NO_SYSTEMD_RUN=1`): `bash .aitask-scripts/lib/tmux_bootstrap.sh <project>` → `tmux has-session -t '=<session>'` succeeds, window `monitor` present, behavior identical to before.
- [ ] Server cleanly deactivates: from inside the ait session run `tmux kill-server` → the `ait-tmux-*.service` unit deactivates (no lingering unit, thanks to --collect / no RemainAfterExit).
