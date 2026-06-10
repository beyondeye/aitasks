---
priority: high
effort: medium
depends: [t635_1]
issue_type: feature
status: Ready
labels: [gates, task_workflow]
created_at: 2026-06-10 18:52
updated_at: 2026-06-10 18:52
---

## Context

Phase 1 of `aidocs/gates/integration-roadmap.md` (decision D1/D2 seed).
task-workflow starts RECORDING its existing checkpoints as gate-run blocks
in the task file — purely additive appends, zero behavior change to the
interactive prompts. In attended mode the AskUserQuestion / ExitPlanMode
outcome IS the signal (hybrid-by-mode, decision D2).

## Scope

- Record as gate-run blocks (via `ait gate append` from t635_1):
  plan approved (Step 6 checkpoint), review approved (Step 8),
  merge approved (Step 9), build verified (Step 9 `verify_build`),
  risk evaluated (when `risk_evaluation: true`).
- **Design call to make here (roadmap "open problem 2"):** record-by-default
  vs opt-in. Proposal to evaluate: `gate_ledger` profile flag, default on
  for the core checkpoints, so Phase 2 re-entry (t635_5) works for every
  task — this deliberately bends the framework doc's "no `gates:` field =
  exactly like today" stance and must be decided explicitly at planning time.
- Regenerate goldens + `./.aitask-scripts/aitask_skill_verify.sh` in the
  same commit (task-workflow closure edits auto-render to other agents).

## Out of scope

Resume logic (t635_5), archival changes (t635_4), any gate that *drives*
a decision — this child only witnesses decisions already made.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 1, open problem 2)
- `.claude/skills/task-workflow/SKILL.md` Steps 6/8/9
