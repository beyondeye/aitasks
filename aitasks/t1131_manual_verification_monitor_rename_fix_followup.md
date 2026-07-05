---
priority: medium
effort: medium
depends: [1130]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1130]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-05 16:57
updated_at: 2026-07-05 17:23
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1130

## Verification Checklist

- [x] In tmux, from a pane whose window is NOT 'monitor', run `env -u TMUX_PANE ait monitor` — PASS 2026-07-05 17:23 Verified with bash tests/test_monitor_rename_window_target.sh (3/3 pass) and live tmux window @48 named verify1131-safe: env -u TMUX_PANE timeout 4 ./ait monitor exited 124 and the window name remained verify1131-safe, not monitor.
- [x] Run a normal `ait monitor` (TMUX_PANE set) in its own new window — PASS 2026-07-05 17:23 Verified in live tmux window @49: normal timeout 10 ./ait monitor with TMUX_PANE set renamed the window from verify1131-normal to monitor; sending j opened the TUI Switcher with tmux Monitor selected/listed.
- [x] Spawn an explore agent + minimonitor companion, then start/refresh a monitor — PASS 2026-07-05 17:23 Verified with disposable tmux window @50 named agent-explore-1: launched timeout 25 ./ait codeagent invoke explore, added timeout 25 ./ait minimonitor split, then ran env -u TMUX_PANE timeout 5 ./ait monitor in the same window. After monitor start, the window name remained agent-explore-1, not monitor.
