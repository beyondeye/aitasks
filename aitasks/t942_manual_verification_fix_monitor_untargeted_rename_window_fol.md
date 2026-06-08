---
priority: medium
effort: medium
depends: [941]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [941]
created_at: 2026-06-06 23:53
updated_at: 2026-06-06 23:53
boardidx: 30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t941

## Verification Checklist

- [ ] tmux kill-server (clear all sessions), then run `ait ide` in the project — confirm exactly ONE window named `monitor`
- [ ] Open a board via the TUI switcher (`j` then board) and make that board window the active window in the session
- [ ] From a second terminal/client attached to the SAME session, launch a second `ait monitor` (or trigger a monitor relaunch) while the board window stays active
- [ ] Expected: no board window is ever renamed `monitor`; no duplicate `monitor` window appears; `tmux list-windows` shows board windows keep the `board` name and only monitor's own pane's window is named `monitor`
- [ ] Edge case: run `ait monitor` manually inside an arbitrary shell window (not active) and confirm only THAT window is renamed to `monitor`
- [ ] TODO: verify .aitask-scripts/monitor/monitor_app.py on_mount window-naming end-to-end in tmux
