---
priority: medium
effort: medium
depends: [1130]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1130]
created_at: 2026-07-05 16:57
updated_at: 2026-07-05 16:57
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1130

## Verification Checklist

- [ ] In tmux, from a pane whose window is NOT 'monitor', run `env -u TMUX_PANE ait monitor` — confirm the currently-active window is NOT renamed to 'monitor' (fail-safe skip)
- [ ] Run a normal `ait monitor` (TMUX_PANE set) in its own new window — confirm that window IS named 'monitor' and the TUI switcher (`j`) can find it
- [ ] Spawn an explore agent + minimonitor companion, then start/refresh a monitor — confirm no agent-explore window gets mislabeled 'monitor' (original t1130 symptom does not recur)
