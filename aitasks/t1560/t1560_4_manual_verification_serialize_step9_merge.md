---
priority: medium
effort: medium
depends: [t1560_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1560_1, 1560_2, 1560_3]
anchor: 1560
followup_kind: manual_verification
created_at: 2026-08-18 12:26
updated_at: 2026-08-18 12:26
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1560_1] Drive two REAL agent sessions to Step 9 under a worktree profile (create_worktree: true) on the same checkout; confirm the second is held out and its merge prompt names the holding task id.
- [ ] [t1560_1] Confirm the WAITING progress is visible on stderr in a live terminal while queued — a long queue must look queued, not hung.
- [ ] [t1560_1] Drive a real conflict-parked merge: leave session A at the conflict, confirm session B cannot enter, then abort in A and confirm B proceeds.
- [ ] [t1560_1] Kill an agent pane mid-critical-section and confirm exactly one waiter reclaims, and that a still-running pane is never displaced.
- [ ] [t1560_1] Run the wedge path by hand: no tmux and no AIT_AGENT_PID, confirm NO_SESSION_ANCHOR is refused with both remedies readable, then confirm status + force-release recover a planted wedged lock.
- [ ] [t1560_1] Confirm the helper whitelist works: invoke aitask_merge_task.sh from a skill in Claude Code and confirm no permission prompt appears.
- [ ] [t1560_2] Read the rendered merge-approval question in a REAL terminal at a realistic pane width — confirm the queued-behind clause is readable and does not wrap the pinned prefix off-screen.
- [ ] [t1560_2] Walk the rendered SKILL-default.md Step 9 by eye and confirm every broker verdict has a branch and no in-flight exit reaches cleanup.
- [ ] [t1560_2] Confirm ait monitor / minimonitor still classify the merge-approval prompt as POSTIMPL/WAITING against a live agent showing it.
- [ ] [t1560_2] Resume a task at POSTIMPL after an error/blocked verification exit and confirm aitask/<task_name> and its worktree are still present and the merge re-reserves.
- [ ] [t1560_3] Build the website and read the two changed pages in a browser: the locks table, the anchor precondition, and the force-release ladder must each be findable without prior knowledge.
- [ ] [t1560_3] Confirm no page names a real repository or lists diffviewer among the TUIs.
