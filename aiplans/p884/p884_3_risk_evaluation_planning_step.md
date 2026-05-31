---
Task: t884_3_risk_evaluation_planning_step.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_3_risk_evaluation_planning_step
Branch: aitask/t884_3_risk_evaluation_planning_step
Base branch: main
---

# Plan: t884_3 — Risk-evaluation step + `## Risk` plan section + Step 7 write

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Depends on t884_1 (`risk` field) and t884_2 (`risk_evaluation` key).

## Goal

A risk-evaluation step at the END of planning that assesses **two dimensions** —
(A) code-health (stability/quality/maintainability), (B) goal-achievement (will
the plan deliver the user's requested goals: approach soundness, requirement
coverage, feasibility) — assigns one **aggregate** `risk` level, and records a
`## Risk` plan section. The `risk`-field **write** is post-approval (Step 7), since
plan mode is read-only.

## Steps

1. **New closure `.claude/skills/task-workflow/risk-evaluation.md`** — assessment rubric for both dimensions, aggregate-level criteria, `## Risk` section template (aggregate level + two subsections; each risk: `description · severity · dimension · → mitigation link`), and a forward-compatible **gates seam** note (maps eval → a future `aitask-gate-risk` once t635 lands; reference `aidocs/gates/`; do NOT couple).
2. **`planning.md` end of §6.1** — `{% if profile.risk_evaluation %}`-gated dispatch to the Risk Evaluation Procedure (design/decide only); thread `risk_level` + `risk_mitigations_planned` into context. Place before "Save Plan to External File".
3. **`SKILL.md` Step 7** — `{% if profile.risk_evaluation %}`-gated hook writing the decided level: `aitask_update.sh --batch <id> --risk <level>` (post-approval, alongside cross-repo creation funnel).
4. **Regenerate** rendered variants + goldens (`tests/golden/skills/`, `tests/golden/procs/task-workflow/`); run `./.aitask-scripts/aitask_skill_verify.sh` — same commit.

## Reference patterns

- `planning-cross-repo.md` (design) + `cross-repo-child-assignment.md` (Step 7 creation) — design/creation split + flag threading.
- `planning.md` §6.0 Jinja gating form (`plan_preference`).

## Verification

- `aitask_skill_verify.sh` passes. Default (key absent) rendered variant: no risk step. `risk_evaluation: true` variant: step + Step 7 write present.
- `ait skillrun pick --profile <p> --dry-run` sanity. Goldens committed together.

## Notes for sibling tasks

`## Risk` format here is consumed by t884_4 (mitigation links) + t884_6 (docs). `risk_mitigations_planned` gates t884_4's creation. Keep 6.0/8b/8c numbering — t884_5 adds 6.0a, t884_4 adds 8d (suffixes only).
