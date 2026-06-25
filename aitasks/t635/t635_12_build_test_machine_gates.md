---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t635_11]
issue_type: feature
status: Implementing
labels: [gates, task_workflow, testing]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 18:54
updated_at: 2026-06-25 10:28
---

## Context

Phase 4 of `aidocs/gates/integration-roadmap.md` (decision D4, first wave).
The cleanest conceptual fit for the verifier contract: task-workflow Step
9's `verify_build` and the ad-hoc "run tests / check lint" verify region
become machine gates.

## Scope

- Ship `aitask-gate-build` / `aitask-gate-tests-pass` (and lint where the
  project config defines one) verifier skills against the t635_11 contract;
  commands sourced from `project_config.yaml` (`verify_build`) — no
  hardcoded project commands.
- task-workflow's verify region calls `ait gates run <task-id>` when the
  task declares these gates (framework doc integration table row for
  implementation §Verify); the existing inline behavior remains for tasks
  without declared gates.
- `applies_when:`-style short-circuit (framework doc open question 3) may
  be pulled in here if build gates need change-scoped skipping; otherwise
  explicitly defer with a note.
- Goldens + skill verify in the same commit.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 4, D4)
- `aidocs/gates/aitask-gate-framework.md` (verifier contract; integration
  table)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-25T07:28:44Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-25T07:28:45Z status=pass attempt=1 type=machine
