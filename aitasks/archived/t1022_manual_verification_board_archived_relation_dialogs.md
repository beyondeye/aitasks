---
priority: medium
effort: medium
depends: [1021]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [1021]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-17 12:02
updated_at: 2026-06-18 11:19
completed_at: 2026-06-18 11:19
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1021

## Verification Checklist

- [x] In a workspace whose `aitasks#<id>` cross-repo dependency is ARCHIVED in the other repo, open `ait board` -> task detail -> focus the Cross-repo deps line -> Enter; confirm the popup renders the archived task's CONTENT (not "(UNREACHABLE)" / "not found in project"), and the status badge agrees with the resolved content. — PASS 2026-06-18 11:17 unittest baseline plus scratch board harness: archived sister#822 status Done, no UNREACHABLE/not-found, popup body contained ARCHIVED_SISTER_822_CONTENT
- [x] Verify both the single-ref cross-repo popup and the multi-ref CrossRepoRefPickerScreen resolve an archived target. — PASS 2026-06-18 11:17 scratch board harness: CrossRepoRefPickerScreen held sister#822 and sister#822_14; both resolved archived content
- [x] Open a parent task's Children dialog where a child is archived (anomaly path); confirm it opens read-only instead of showing "(not found)". — PASS 2026-06-18 11:17 scratch board harness: ChildrenField resolved archived t20_1_child.md with archived=True, so detail path is read-only instead of not-found
- [fail] Open a Folded Tasks / Folded Into / Parent relation where the target is archived; confirm it resolves read-only. — FAIL 2026-06-18 11:17 follow-up t1026
- [x] Confirm a genuinely-missing cross-repo task id still shows the "Task t<id> not found in project" error (no crash). — PASS 2026-06-18 11:17 scratch board harness: missing sister#999 returned NOT_FOUND/UNREACHABLE display and popup error Task t999 not found in project sister without exception
