---
priority: low
effort: medium
depends: [635]
issue_type: enhancement
status: Ready
labels: [gates, task_workflow]
created_at: 2026-06-02 12:49
updated_at: 2026-06-02 12:49
boardidx: 20
---

## Context

Follow-up filed by t884_7 (trailing retrospective of the task risk-evaluation
feature, t884). The parent plan (`aiplans/p884_add_task_risk_evaluation_in_planning.md`)
locked a "standalone now + gates seam" decision: build risk evaluation
independent of the gates framework (t635) and document a forward-compatible seam,
to be wrapped as a first-class gate once the framework lands.

## Goal

Wrap the risk-evaluation feature as a first-class `aitask-gate-risk` gate once the
gates framework (t635) is in place, replacing the forward-compat seam note added
in t884_3.

## Depends on

- **t635** (gates framework) — this task cannot start until the framework lands.

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

## Reference

- `aidocs/gates/risk-evaluation-gate-seam.md` (integration design).
- `aidocs/gates/aitask-gate-framework.md` (gates contract).
- t635 (gates framework), t884 (parent feature task).
