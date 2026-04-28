---
priority: medium
effort: medium
depends: [708]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [708]
created_at: 2026-04-28 23:32
updated_at: 2026-04-28 23:32
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t708

## Verification Checklist

- [ ] Manual test 1 (no drift): align local main with origin/main; run /aitask-pick on a task; approve a plan; expect no drift output between checkpoint and Step 7.
- [ ] Manual test 2 (soft drift): from a second clone push a commit touching docs/unrelated.md to origin/main; pick a task whose plan does not reference docs/; approve plan; expect AHEAD:1 + NO_OVERLAP soft warning.
- [ ] Manual test 3 (strong drift): from a second clone push a commit touching .aitask-scripts/aitask_archive.sh to origin/main; pick a task referencing aitask_archive.sh in the plan; expect AHEAD:1 + OVERLAP:.aitask-scripts/aitask_archive.sh strong warning.
- [ ] Manual test 4 (no network): git remote set-url origin file:///nonexistent; pick a task; expect silent FETCH_FAILED (no warning, no prompt) and proceed normally.
- [ ] Manual test 5 (Stop and re-verify branch): trigger a strong-drift warning; pick "Stop and re-verify plan"; confirm the lock is released, task status reverts to Ready, and the workflow ends without entering Step 7.
- [ ] Manual test 6 (profile opt-out): create a custom profile with remote_drift_check: skip; pick a task with that profile; confirm the drift check is silent regardless of remote state.
