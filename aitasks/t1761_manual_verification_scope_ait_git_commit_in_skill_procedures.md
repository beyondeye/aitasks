---
priority: medium
effort: medium
depends: [1748]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1748]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-09 13:00
updated_at: 2026-09-09 13:00
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1748

## Verification Checklist

- [ ] [t1748] Run /aitask-pick on any task under the fast profile; confirm the plan-externalization commit reaches aitask_task_commit.sh and reports COMMITTED:, with no permission prompt.
- [ ] [t1748] Abort a task whose plan was never externalized (task-abort.md); confirm the agent reports the optional SKIPPED:unknown:<plan_file> correctly and does not read exit 0 as a partial failure.
- [ ] [t1748] With a second session holding staged task-data files, run a converted site; confirm git show --name-only on the resulting commit lists only this task's paths.
- [ ] [t1748] Confirm aitask_task_commit.sh runs without a permission prompt under the Codex and OpenCode trees — touchpoints 3, 6 and 7 were written but only the Claude one (touchpoint 1) was exercised during t1748.
