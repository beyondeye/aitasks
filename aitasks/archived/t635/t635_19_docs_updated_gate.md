---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t635_11]
issue_type: feature
status: Done
labels: [gates, task_workflow, web_site]
gates: [risk_evaluated]
risk_mitigation_tasks: [t635_27, t635_28, t635_29]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 19:03
updated_at: 2026-07-01 10:47
completed_at: 2026-07-01 10:47
---

## Context

A DOCUMENTATION checkpoint is entirely missing from today's task-workflow —
unlike tests, review, risk, and follow-ups, nothing asks "do the docs need
updating for this change?". The framework doc's own registry example and
worked lifecycle already include a `docs_updated` machine gate; this child
ships it. Unlike t635_12/t635_13 this is NOT a conversion of an existing
pseudo-gate — it is a new gate filling a real gap.

## Scope

- `aitask-gate-docs-updated` verifier skill against the t635_11 contract:
  inspect the task's change set, determine whether user-facing docs
  (website pages) and/or `aidocs/` design docs are affected, update them
  (or report what needs updating on fail).
- Change-scoped short-circuit: the gate returns `skip` (distinct from
  `pass`, so history shows it was evaluated) when the diff touches no
  doc-relevant surface — the framework doc's `applies_when:` predicate
  (open question 3) or an in-verifier equivalent; decide at planning.
- Repo-specific doc knowledge: where doc roots live should come from
  project config (e.g. a `doc_paths:` key in `project_config.yaml` or the
  registry entry), not be hardcoded — other projects using aitasks have
  different doc layouts.
- Candidate for `default_gates` in this repo's `gates.yaml`; verify the
  workflows `_index.md` manual-list rule is part of the verifier's
  checklist for this repo (website pages need their hand-curated index
  bullet).
- Doc updates the verifier produces must follow
  `aidocs/framework/documentation_conventions.md` (current-state-only,
  generic project names, agent-generic wording).

## Relationship to t635_18

t635_18 is the one-time comprehensive documentation sweep for the gates
feature itself; this gate is the PERMANENT per-task checkpoint that keeps
docs from drifting afterward — including for the remaining t635 children
(the framework dogfooding its own documentation gate).

## References

- `aidocs/gates/aitask-gate-framework.md` (registry example `docs_updated`,
  open question 3 `applies_when:`)
- `aidocs/gates/integration-roadmap.md` (Phase 4)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-01T06:47:14Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-01T07:43:55Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-01T07:47:28Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:5bd94acca8be83da

> **✅ gate:risk_evaluated** run=2026-07-01T07:47:28Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/635_19/risk_evaluated_2026-07-01T07:47:28Z-risk_evaluated-a1.log`
