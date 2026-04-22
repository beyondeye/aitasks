---
priority: medium
effort: medium
depends: [604]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [604]
created_at: 2026-04-21 09:26
updated_at: 2026-04-21 09:26
boardidx: 40
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t604

## Verification Checklist

- [ ] Pick a manual-verification task with at least 2 pending items; at the first per-item prompt choose "Stop here, continue later"; confirm the task stays Implementing, the lock is held, no items flipped from pending to terminal, and the paused message displays the correct item index
- [ ] Archive a manual-verification task with one deferred item via `aitask_archive.sh --with-deferred-carryover <id>`; confirm the new carry-over task's filename ends in `_carryover.md` (not `_deferred_carryover.md`)
- [ ] Create a manual-verification task whose checklist has `- [ ] Group X:` followed by two nested `- [ ]` children; run `/aitask-pick <id>`; confirm the interactive loop prompts only for the two children, never for the header bullet
- [ ] Negative case: verify a `:` bullet followed by a same-indent sibling `- [ ]` is NOT filtered — still appears in the loop as a normal verifiable item
- [ ] Seed a manual-verification task whose deferred set includes a section header with nested children, archive with `--with-deferred-carryover`; confirm the seeded carry-over task's checklist does not include the orphan header
