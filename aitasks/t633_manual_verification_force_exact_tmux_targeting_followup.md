---
priority: medium
effort: medium
depends: [632]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [632]
created_at: 2026-04-23 18:08
updated_at: 2026-04-23 18:08
boardidx: 130
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t632

## Verification Checklist

- [ ] tmux kill-server to clear all sessions
- [ ] cd to project A and run `ait ide` — confirm it starts session A with a `monitor` window
- [ ] Detach (Ctrl-b d)
- [ ] cd to project B and run `ait ide` — must start a NEW session B, not attach to A
- [ ] `tmux list-sessions` should show both sessions
- [ ] Switch TUIs in each project (board, codebrowser, settings, monitor) and confirm windows stay in each project's own session — no cross-leakage
- [ ] Start a brainstorm in project A; in project B the brainstorm switch must NOT focus A's brainstorm window
- [ ] Verify minimonitor companion panes spawn in the correct project's session (e.g. from board, launch a code agent in project B and check the companion pane is in session B)
