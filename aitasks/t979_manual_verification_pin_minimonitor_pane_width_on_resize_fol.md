---
priority: medium
effort: medium
depends: [978]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [978]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 16:35
updated_at: 2026-06-12 07:36
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t978

## Verification Checklist

- [ ] ait pick <N> → confirm the agent-* window spawns a minimonitor companion pane at ~40 columns
- [ ] Detach tmux (prefix d) → resize the terminal much wider → reattach (tmux attach) → confirm the minimonitor pane snaps back to ~40 columns instead of staying proportionally wide (the reported bug)
- [ ] Resize the terminal live (no detach) → confirm the minimonitor pane stays pinned to ~40 columns
- [ ] Set tmux.minimonitor.width: 50 in aitasks/metadata/project_config.yaml, relaunch → confirm the pane pins to 50 columns
- [ ] TODO: verify .aitask-scripts/monitor/minimonitor_app.py end-to-end in tmux
