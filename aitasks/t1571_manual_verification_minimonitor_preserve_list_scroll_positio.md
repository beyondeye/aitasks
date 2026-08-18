---
priority: medium
effort: medium
depends: [1539]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1539]
anchor: 1539
followup_kind: manual_verification
created_at: 2026-08-18 14:20
updated_at: 2026-08-18 14:20
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1539

## Verification Checklist

- [ ] With more than one screenful of agents, scroll the list with a physical mouse wheel and confirm the position holds across several refresh ticks (default 3 s)
- [ ] Scroll to the bottom, let an agent above the fold be killed, and confirm the view stays pinned to the bottom rather than jumping to the top
- [ ] Scroll to a mid-list agent, kill that exact agent, and confirm the view settles on a neighbouring row rather than snapping to the top
- [ ] Drag the scrollbar thumb with a real mouse (not the wheel) and confirm the position holds across refresh ticks — this is the ScrollTo path, distinct from the wheel
- [ ] Confirm keyboard up/down still scrolls the focused card into view: the rebuild lock must not suppress active gestures, only the passive refresh
- [ ] Confirm `s` (or regaining terminal focus on the pane) still re-selects and scrolls to this window's own agent
- [ ] Confirm a list SHORTER than one screenful shows no stutter, no lag and no scroll artifacts — the restore path runs on every tick regardless of overflow
- [ ] TODO: verify .aitask-scripts/monitor/minimonitor_app.py end-to-end in tmux
