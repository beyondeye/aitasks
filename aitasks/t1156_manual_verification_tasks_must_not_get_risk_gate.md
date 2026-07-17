---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [gates, manual_verification, task_workflow]
assigned_to: dario-e@beyond-eye.com
anchor: 1138
created_at: 2026-07-15 19:31
updated_at: 2026-07-17 10:45
boardidx: 190
---

## Origin

Surfaced while verifying t1141 (manual_verification for the t1138 cross-repo
syncer rework) under the `fast` profile. All 9 verification checks passed, but
archival was blocked by an **unsatisfiable** declared gate.

## Symptom

t1141 (`issue_type: manual_verification`) carries `gates: [risk_evaluated]`.
The `risk_evaluated` machine verifier (`aitask-gate-risk`) checks that THIS
task's plan has a `## Risk` section with `### Code-health risk` /
`### Goal-achievement risk` subsections AND that the task's
`risk_code_health` / `risk_goal_achievement` frontmatter levels are set.

Manual-verification tasks skip Steps 6–7 (planning + the planning-time Risk
Evaluation Procedure) entirely — they run the Manual Verification Procedure
instead — so those artifacts are never produced. The gate fails, and with
`max_retries: 0` (see `aitasks/metadata/gates.yaml`) it is immediately
exhausted, so `aitask_archive.sh` refuses to archive
(`GATE_PENDING:risk_evaluated`, exit 2). The task can never archive through
the normal manual-verification flow.

## Root cause (identified)

`task-creation-batch.md` (the Batch Task Creation Procedure) auto-injects
`--gates "<profile.default_gates>"` into EVERY task it creates when the active
profile declares `default_gates` (lines ~25–29, 83–84, 101–102). The `fast`
profile declares `default_gates: [risk_evaluated]`
(`aitasks/metadata/profiles/fast.yaml:17`).

t1141 was created by the Risk-Mitigation "after" Follow-up Procedure
(`risk-mitigation-followup.md` Part 3, Step 8d) via that batch procedure with
`type: manual_verification`. The auto-injection stamped `risk_evaluated` onto a
manual_verification task that structurally cannot satisfy it.

Principle (per user): **a manual_verification task is not supposed to have a
risk gate.** More generally, planning-derived gates (`risk_evaluated`, and
likely `plan_approved`) should not be auto-injected onto `issue_type:
manual_verification` tasks, since they never run planning.

## Goal

Analyze and fix so manual_verification tasks are not created with
planning-derived gates:

1. Confirm the full set of gates that are meaningless for manual_verification
   tasks (at least `risk_evaluated`; assess `plan_approved`, others). The
   manual-verification flow records `review_approved`? (verify) — keep only
   gates it actually reaches.
2. Fix the auto-injection so it is exempted / filtered for
   `issue_type: manual_verification` (candidate site: `task-creation-batch.md`
   default_gates injection; and/or the create script; and/or the
   manual-verification-followup / risk-mitigation-followup creation callers).
   Regenerate affected skill goldens (see skill_authoring_conventions).
3. Add a test asserting a manual_verification task created under a profile with
   `default_gates: [risk_evaluated]` does NOT receive risk_evaluated (or is
   otherwise archivable).
4. Sweep for already-affected in-flight/archived manual_verification tasks that
   carry `risk_evaluated` and document remediation (t1141 itself was corrected
   by removing the gate during its verification pick).
5. Port the fix to Codex/OpenCode skill trees if the corrected surface is
   agent-specific.

## Related

- Discovered during: t1141 (manual_verification, anchor 1138).
- Gate registry: `aitasks/metadata/gates.yaml` (`risk_evaluated`, `max_retries: 0`).
- Creation path: `.claude/skills/task-workflow/task-creation-batch.md`,
  `.claude/skills/task-workflow/risk-mitigation-followup.md` (Part 3).
- Profile: `aitasks/metadata/profiles/fast.yaml`.
