---
priority: medium
effort: medium
depends: [1021]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1021]
created_at: 2026-06-17 12:02
updated_at: 2026-06-17 12:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1021

## Verification Checklist

- [ ] In a workspace whose `aitasks#<id>` cross-repo dependency is ARCHIVED in the other repo, open `ait board` -> task detail -> focus the Cross-repo deps line -> Enter; confirm the popup renders the archived task's CONTENT (not "(UNREACHABLE)" / "not found in project"), and the status badge agrees with the resolved content.
- [ ] Verify both the single-ref cross-repo popup and the multi-ref CrossRepoRefPickerScreen resolve an archived target.
- [ ] Open a parent task's Children dialog where a child is archived (anomaly path); confirm it opens read-only instead of showing "(not found)".
- [ ] Open a Folded Tasks / Folded Into / Parent relation where the target is archived; confirm it resolves read-only.
- [ ] Confirm a genuinely-missing cross-repo task id still shows the "Task t<id> not found in project" error (no crash).
