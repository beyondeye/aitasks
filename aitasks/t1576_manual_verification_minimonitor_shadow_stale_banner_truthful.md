---
priority: medium
effort: medium
depends: [1573]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1573]
assigned_to: dario-e@beyond-eye.com
anchor: 1573
followup_kind: manual_verification
created_at: 2026-08-18 18:07
updated_at: 2026-08-18 18:12
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1573

## Verification Checklist

- [ ] - Explain-only shadow shows NO banner: spawn a shadow with `e`, ask it only to explain the plan (never review), let the followed agent type, and confirm the minimonitor shows no staleness banner and the pane list keeps that row.
- [ ] - A real review round still goes stale: take a real concern round, let the followed agent type after it, and confirm the one-row "shadow feedback is stale" banner appears.
- [ ] - Leaving the planning phase retires a standing warning: with a stale plan-review block on screen, let the agent move from planning into implementation and confirm the banner disappears at the transition.
- [ ] - A fresh round re-arms the banner after retirement: ask the shadow for a new round while the agent is implementing, let the agent type again, and confirm the banner comes back.
- [ ] - The retired row is actually reclaimed on screen (not just blanked): confirm the pane list gains the row back when the banner clears, at a narrow pane height where the row matters.
- [ ] - Press `c` while a warning is retired: confirm the concern picker still shows its own red stale banner for the block being acted on, even though the continuous banner is gone.
- [ ] - TODO: verify .aitask-scripts/monitor/minimonitor_app.py end-to-end in tmux
