---
priority: medium
effort: medium
depends: [635_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [635_6]
created_at: 2026-06-15 16:29
updated_at: 2026-06-15 16:29
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t635_6

## Verification Checklist

- [ ] resume-point derivation PLAN: a fixture with an empty `## Gate Runs` ledger derives to PLAN (`aitask_gate.sh resume-point <fixture>` and `gate_ledger.py resume_point`).
- [ ] resume-point derivation IMPLEMENT: a fixture with `plan_approved pass` appended derives to IMPLEMENT.
- [ ] resume-point derivation POSTIMPL: a fixture with `plan_approved pass` + `review_approved pass` appended derives to POSTIMPL.
- [ ] skill IMPLEMENT routing: `/aitask-resume <fixture>` on an Implementing+plan_approved fixture surfaces the IMPLEMENT banner and hands off to task-workflow Step 3 -> Re-entry Routing -> Step 7 implementation body (observe the route; abort before doing real implementation work).
- [ ] skill POSTIMPL routing: `/aitask-resume <fixture>` on a review_approved fixture routes to task-workflow Step 9 and halts at the NON-SKIPPABLE merge approval (correct autonomous stop — do not merge/archive the throwaway fixture).
- [ ] --gate degradation: `/aitask-resume <fixture> --gate review_approved` reports the named gate's recorded ledger state and runs NO verifier (no orchestrator invoked, no second engine).
- [ ] not-in-flight advisory: `/aitask-resume <fixture>` on a Ready fixture (empty ledger) advises that resuming behaves like a fresh `/aitask-pick` and plans from scratch.
- [ ] parent-with-children rejection: `/aitask-resume <parent-id>` where the parent has children is rejected with guidance to re-invoke with a specific child id.
- [ ] teardown sanity: after all items, no leftover fixture task files remain in `aitasks/` and `git status` (code + data branch) is clean — fixtures were created without commit and deleted, and any lock/commit side effects from live skill-routing items were reverted via the abort procedure.
