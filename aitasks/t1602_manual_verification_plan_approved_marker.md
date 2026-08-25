---
priority: medium
effort: medium
depends: [1595]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1595]
anchor: 1595
followup_kind: manual_verification
created_at: 2026-08-25 12:33
updated_at: 2026-08-25 12:33
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1595

## Verification Checklist

- [ ] Approve-and-stop a task under default.yaml, then run `ait ls -v`: its line shows `Plan: approved <ts>`, `ait ls --plan-approved` returns it, and plain `ait ls` stays filename-only (no metadata leaks into the plain listing).
- [ ] Re-pick that task under default.yaml: the existing-plan prompt names the approval date, and the first option label reads literally "Use current plan (Recommended)" (prompt Variant B).
- [ ] With a risk-mitigation task landed since the plan was last verified, re-pick: the prompt shows "Verify plan (Recommended)" instead and names BOTH facts (approved on <ts> AND a mitigation landed) — force_verify outranks the marker (Variant A).
- [ ] Choose "Create plan from scratch" at that prompt: afterwards `ait ls --plan-approved` no longer returns the task (the marker was cleared before plan mode was entered).
- [ ] Force real drift on origin/<base> for a file the plan targets, re-pick, and take "Stop and re-verify plan": the marker is cleared (not refreshed), `ait ls -v` no longer advertises a deferred approved plan, and no `aitask/<task_name>` branch or `aiwork/<task_name>` worktree exists.
- [ ] Re-pick a marked task and start implementation: the marker is consumed once the implementation body is entered (`ait ls --plan-approved` no longer returns it), and the plan file is untouched.
- [ ] Sync two checkouts of the same task where one consumed the marker and the other only changed status: the clear survives the merge — the marker does not resurrect, and the task file never gains a literal `plan_approved_at: null` line.
