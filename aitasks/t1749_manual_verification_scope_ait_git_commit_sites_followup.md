---
priority: medium
effort: medium
depends: [1728]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1728]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-08 22:18
updated_at: 2026-09-08 22:18
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1728

## Verification Checklist

- [ ] On the live .aitask-data branch with two concurrent sessions: stage a file in session A, then have session B run a skill that bumps models_*.json. Confirm A's staged file is neither committed by B nor unstaged.
- [ ] Same two-session scenario, but B stages a different version of the SAME models_*.json. Confirm B's commit does not destroy A's staged version of that path.
- [ ] Trigger a real manual-verification failure follow-up (ait verification item marked fail) and confirm the origin's archived plan back-reference commit contains only that plan file.
- [ ] Interrupt aitask_verified_update.sh with Ctrl-C mid-run and confirm ait_unstage_staged_by_us left no stray entries in the shared .aitask-data index.
