---
priority: medium
effort: medium
depends: [949]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [949]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 11:04
updated_at: 2026-06-10 11:34
completed_at: 2026-06-10 11:34
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t949

## Verification Checklist

- [x] In `ait brainstorm`, open a node detail modal (Enter on a node), switch to the Proposal tab, press Tab → focus moves into the section minimap; arrow through rows, Enter scrolls the content to that section; press Tab again while on the minimap → focus stays put (no jump back to row 0). — PASS 2026-06-10 11:31 auto: Pilot harness — Tab focuses proposal_minimap (row0), Down->row1, Tab again stays row1 (no jump to 0)
- [x] Repeat the above on the Plan tab. — PASS 2026-06-10 11:31 auto: Pilot harness — same contract holds on Plan tab (plan_minimap row1 stays put on re-Tab)
- [x] Confirm the Tab/minimap behavior is identical to before the t949 change (it should be — PASS 2026-06-10 11:31 auto: behavior-neutral confirmed — dropped _InlineSectionMinimap had BINDINGS=[] which Textual merges across MRO (inert); no-op-on-minimap is NodeDetailModal.action_focus_minimap, untouched by t949
