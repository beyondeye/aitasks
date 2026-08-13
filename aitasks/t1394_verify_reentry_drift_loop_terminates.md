---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [task_workflow, gates, claudeskills]
anchor: 635
followup_kind: risk_mitigation
created_at: 2026-08-03 16:53
updated_at: 2026-08-13 23:07
boardidx: 28672
---

## Origin

Risk-mitigation ("after") follow-up for t1380, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement risk, severity low:

> The Defect-2 loop-termination argument depends on the stop branch continuing
> to revert to `Ready`, and is argued in prose — grep guards over skill markdown
> cannot prove the live loop terminates.

t1380 added a remote drift check to Re-entry Routing's `IMPLEMENT` route. Its
"Stop and re-verify plan" branch reverts the task to `Ready`, which is what makes
the subsequent re-pick fail Step 3 Check 5's `Implementing` status gate, skip
Re-entry Routing, and land in the normal planning path instead of re-triggering
the very check that sent the user away.

Every guard shipped for this is **structural** — it asserts that SKILL.md
*states* the argument. Nothing executes the loop. A future edit that changed the
stop branch to leave the task `Implementing` would keep every guard green and
produce an infinite stop→re-pick loop.

## Goal

Drive the real `IMPLEMENT` re-entry path end to end in a scratch repo and
confirm the loop terminates.

## Checklist

- [ ] In a scratch clone with a `create_worktree: false`, `record_gates: true`
      profile (`fast`), pick a task and approve its plan so `plan_approved` is
      recorded, then kill the agent leaving the task `Implementing`.
- [ ] Push a commit to `origin/<base branch>` that touches a file the plan
      targets, so the drift check has something to report.
- [ ] Re-pick the task. Confirm Step 3 Check 5 reports `IMPLEMENT`, Re-entry
      Routing resolves the branches from the **plan header**, and the Remote
      Drift Check fires with the overlapping file named.
- [ ] Choose "Stop and re-verify plan". Confirm the task is reverted to `Ready`,
      the lock is released, `plan_approved` is recorded exactly once (not
      duplicated — the `recorded-pass` guard), and the worktree/branch are left
      in place.
- [ ] Pull, then re-pick. Confirm the run goes through **planning** (§6.0's
      existing-plan preference → Checkpoint), NOT Re-entry Routing, and that the
      drift check now passes. **This is the termination proof.**
- [ ] Separately: abort a task that has a recorded `plan_approved` and confirm
      `ait gate status <id>` shows the demotion and `resume-point` reports
      `PLAN`.

## Notes

`tests/test_gate_plan_approval_transitions.sh` already proves the ledger
transitions in isolation; what it cannot prove is that the live workflow reaches
them in the documented order. That is what this task verifies.
