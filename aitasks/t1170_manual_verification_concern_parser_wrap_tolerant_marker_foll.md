---
priority: medium
effort: medium
depends: [1167]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1167]
created_at: 2026-07-20 09:48
updated_at: 2026-07-20 09:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1167

## Verification Checklist

- [ ] verify .aitask-scripts/monitor/concern_parser.py end-to-end in tmux (unit tests cover the pure parser only; the capture path is untested)
- [ ] Spawn a Codex shadow via minimonitor `e` on a plan review at a narrow pane width (~55 cols), with a concern whose region is a long full path — confirm the auto-offer FIRES (pre-fix it silently reported no concerns)
- [ ] Confirm the picker renders the rejoined region label readably, and that forwarding the selected concern to the followed agent produces the correct `- [priority | region] body` payload
- [ ] Confirm a normal short-region shadow review (producer rule respected) is unaffected — no regression in the common path
- [ ] Confirm a marker split wider than 3 rows is still dropped without crashing or corrupting adjacent concerns (the documented envelope limit)
