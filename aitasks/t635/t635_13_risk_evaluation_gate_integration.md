---
priority: low
effort: medium
depends: [t635_11]
issue_type: enhancement
status: Ready
labels: [gates, task_workflow]
created_at: 2026-06-02 12:49
updated_at: 2026-06-10 18:55
---

> **Formerly standalone task t912** (`t912_risk_evaluation_gate_integration`),
> reparented under t635 during the 2026-06-10 gates-integration design
> session (Phase 4 of `aidocs/gates/integration-roadmap.md`, decision D4).
> Archived plans referencing t912 (p884_7, p884_8) are historical record and
> intentionally not rewritten. Dependency updated from the bare framework
> parent (t635) to the orchestrator child (t635_11), which is what the
> integration actually needs.

## Context

Follow-up filed by t884_7 (trailing retrospective of the task risk-evaluation
feature, t884). The parent plan (`aiplans/p884_add_task_risk_evaluation_in_planning.md`)
locked a "standalone now + gates seam" decision: build risk evaluation
independent of the gates framework (t635) and document a forward-compatible seam,
to be wrapped as a first-class gate once the framework lands.

## Goal

Wrap the risk-evaluation feature as a first-class `aitask-gate-risk` gate once the
gates framework orchestrator + verifier contract (t635_11) is in place, replacing
the forward-compat seam note added in t884_3.

## Design already documented

`aidocs/gates/risk-evaluation-gate-seam.md` records the integration design in
detail: the `## Risk` plan section is the gate's *evidence*; the two frontmatter
levels (`risk_code_health` / `risk_goal_achievement`) are the gate's *verdict*;
the gate is satisfied when the section exists and the levels are written. The
feature currently lives in:
- `.claude/skills/task-workflow/risk-evaluation.md` (assessment, read-only at planning).
- `.claude/skills/task-workflow/SKILL.md` Step 7 (post-approval frontmatter write).
- `risk_evaluation` profile key (gates the whole feature via Jinja).

## Scope

Replace the standalone profile-gated dispatch with the gate wrapper per the seam
doc, keeping the `risk_evaluation` opt-in semantics. Regenerate goldens and run
`./.aitask-scripts/aitask_skill_verify.sh` in the same commit (gotcha #2 from the
t884 parent plan).

Note: the broader profile→gate-declaration configuration unification (which
checkpoint is toggled where) is t635_14 — this child performs the risk-specific
conversion per the seam doc; t635_14 then retires the duplicated Jinja toggle.

## Reference

- `aidocs/gates/risk-evaluation-gate-seam.md` (integration design).
- `aidocs/gates/aitask-gate-framework.md` (gates contract).
- `aidocs/gates/integration-roadmap.md` (Phase 4, D4).
- t635_11 (orchestrator + verifier contract), t884 (parent feature task).
