---
priority: medium
effort: medium
depends: [1322]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1322]
created_at: 2026-07-29 13:13
updated_at: 2026-07-29 13:13
boardidx: 82944
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1322

## Verification Checklist

- [ ] Launch `ait monitor` beside an agent whose task is archived mid-session; confirm the row flips from yellow IDLE to the blue DONE badge within one refresh tick (~3s) WITHOUT restarting the monitor.
- [ ] Confirm the blue dot and DONE badge are comfortably legible on your actual terminal theme, both dark and light, at a wide terminal and at minimonitor's narrow docked width.
- [ ] Confirm the `CODE AGENTS (n)` header legend renders all four swatches and does not wrap or truncate at narrow widths.
- [ ] Confirm the session bar shows `N done` and that a completed agent is NOT also counted in `N idle`.
- [ ] Park a completed agent on a final prompt (the satisfaction-feedback question) and confirm it reads PROMPT, not DONE, and counts once as awaiting.
- [ ] Confirm auto-switch (`a`) never parks focus on a completed agent and still jumps to a genuinely idle one.
- [ ] In `ait minimonitor`, confirm the compact bar shows `Nd` and that the docked followed-agent panel deliberately shows NO completed badge (this is by design).
- [ ] Launch an agent via the board's resume path (`agent-resume-<id>` window) and confirm it now shows a task title and gate summary at all, then reaches DONE after archival.
- [ ] Confirm a shadow pane's diamond glyph never renders in the completed colour.
- [ ] Archive a task whose file is bundled into aitasks/archived/_b0/old*.tar.zst and confirm the pane degrades gracefully (no title) without the monitor stalling or spinning on re-globs.
