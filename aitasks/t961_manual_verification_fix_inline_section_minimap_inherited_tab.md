---
priority: medium
effort: medium
depends: [949]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [949]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 11:04
updated_at: 2026-06-10 11:09
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t949

## Verification Checklist

- [ ] In `ait brainstorm`, open a node detail modal (Enter on a node), switch to the Proposal tab, press Tab → focus moves into the section minimap; arrow through rows, Enter scrolls the content to that section; press Tab again while on the minimap → focus stays put (no jump back to row 0).
- [ ] Repeat the above on the Plan tab.
- [ ] Confirm the Tab/minimap behavior is identical to before the t949 change (it should be — the change is behavior-neutral).
