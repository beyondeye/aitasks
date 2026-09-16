---
priority: medium
effort: medium
depends: [1809]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1809]
anchor: 1794
followup_kind: manual_verification
created_at: 2026-09-16 12:12
updated_at: 2026-09-16 12:12
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1809

## Verification Checklist

- [ ] Start `ait board` from a linked worktree (git worktree add --detach + aitask_init_data.sh --link-worktree) and confirm the By-Trail banner no longer reads "(drift unavailable: ref_outside_project)" for a trail that is CURRENT in the primary checkout
- [ ] Confirm the same trail's By-Trail drift verdict in the linked worktree matches what the primary checkout shows for it (same verdict, not merely "no error")
- [ ] Start `ait board` in the primary checkout and confirm By-Trail drift still renders normally (control — the change must not alter the layout that already worked)
- [ ] Pick a task under a worktree-mode profile (create_worktree: true) and confirm drift/roadmap checks work inside the created aiwork/ worktree
