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

## Run in autonomous mode

Verifies the `aitask-resume` skill (t635_6) routes correctly at each gate-ledger
resume stage. **Run this in autonomous auto-verification mode** — at the
manual-verification Step 1.5 prompt, choose the autonomous strategy so each item
is executed inline and the results documented at the end (see
`auto-verification.md` §2a).

## Fixture lifecycle (ephemeral; built and torn down by this verification)

The checklist drives the real skill against **throwaway gate fixtures the run
builds itself** — there is no committed fixture substrate:

- **Setup per fixture:** `aitask_create.sh --batch` (a low-priority scratch task,
  **no `--commit`**); set `status: Implementing` via `aitask_update.sh --batch
  <id> --status Implementing`; artificially populate the `## Gate Runs` ledger
  with `aitask_gate.sh append <id> <gate> pass` to land the target stage:
  - **PLAN** — append nothing (empty ledger).
  - **IMPLEMENT** — `append <id> plan_approved pass`.
  - **POSTIMPL** — `append <id> plan_approved pass` + `append <id> review_approved pass`.
- **Teardown:** unlock (`aitask_lock.sh --unlock <id>`), delete the fixture file,
  and reconcile so `git status` is clean on both the code and `aitask-data`
  branches.

## Data-branch safety (important for the autonomous runner)

- Prefer **derivation-level** checks (`gate_ledger.py resume_point <file>` on a
  scratch file, or `aitask_gate.sh resume-point` on an uncommitted fixture) where
  possible — they touch no shared state.
- The **live skill-routing items** (IMPLEMENT / POSTIMPL) drive `/aitask-resume`
  end-to-end, which claims ownership (lock + status commit + push to the
  `aitask-data` branch). **Observe the route, then abort** via the Task Abort
  Procedure (releases the lock, reverts status) and delete the fixture; do not
  let a throwaway fixture reach a real merge/archive. If a routing item cannot be
  exercised without leaving residue on the shared data branch, mark it `defer`
  with a reason rather than risk polluting it (the shared `aitask-data` branch
  has concurrent writers).

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
