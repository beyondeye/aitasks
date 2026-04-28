---
priority: medium
effort: medium
depends: [692]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [692]
created_at: 2026-04-28 10:26
updated_at: 2026-04-28 10:26
boardidx: 220
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t692

## Verification Checklist

- [ ] On PC A, run /aitask-pick <N> and stop after status flips to Implementing (e.g., abort during plan mode)
- [ ] From PC B (same user/email), run /aitask-pick <N>; confirm an AskUserQuestion appears with PC A's hostname + locked_at, offering "Reclaim and continue" / "Pick a different task"
- [ ] Choose "Pick a different task" -> confirm task reverts to Ready, lock is released, picker returns to label/task-selection step
- [ ] Choose "Reclaim and continue" -> confirm lock YAML on aitask-locks now records PC B's hostname, status remains Implementing, workflow continues into Step 5
- [ ] Trigger Step 7 guard path (plan-mode deferral or skipped Step 4) with a foreign-host lock - confirm the new hostname check surfaces the same prompt
