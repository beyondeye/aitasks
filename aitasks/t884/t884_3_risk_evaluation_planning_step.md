---
priority: high
effort: high
depends: [t884_2]
issue_type: enhancement
status: Ready
labels: [task_workflow, task-planning]
created_at: 2026-06-01 00:30
updated_at: 2026-06-01 00:30
---

## Context

Core child of t884 (see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Adds the risk-evaluation step at the END of planning and the `## Risk` plan-section format, and writes the `risk` frontmatter field post-approval. Depends on t884_1 (the `risk` field) and t884_2 (the `risk_evaluation` profile key).

The eval assesses **two dimensions**: (A) **code-health** — stability / quality / maintainability; (B) **goal-achievement** — will the planned implementation actually deliver the user's requested goals (approach soundness, requirement coverage, technical feasibility, completeness). It assigns ONE **aggregate** `risk` level (high/medium/low).

**Design/creation split (planning runs read-only):** during planning the step only *decides* and records to the plan's `## Risk` section + threads flags; the actual `risk`-field write is a mutation that runs **post-approval at SKILL.md Step 7** (same pattern as cross-repo `cross-repo-child-assignment.md`).

## Key Files to Modify

- New closure `.claude/skills/task-workflow/risk-evaluation.md` — the Risk Evaluation Procedure (design part): how to assess both dimensions, assign the aggregate level, and author the `## Risk` section. Include a forward-compatible **gates seam** note (how this eval maps to a future `aitask-gate-risk` once t635 lands — reference `aidocs/gates/`). Do NOT couple to gates.
- `.claude/skills/task-workflow/planning.md` — at the **end of §6.1** (after the plan is designed, before "Save Plan to External File"), add the dispatch to the Risk Evaluation Procedure, wrapped in `{% if profile.risk_evaluation %}`. Define the `## Risk` plan-section format here (or in the closure): aggregate level + two subsections (Code-health risks / Goal-achievement risks), each risk a bullet with `description · severity · dimension · → mitigation link (filled by t884_4)`. Thread `risk_level` and `risk_mitigations_planned` into the workflow context.
- `.claude/skills/task-workflow/SKILL.md` — at **Step 7** (post-approval, the single creation funnel where cross-repo creation also hooks), add a `{% if profile.risk_evaluation %}`-gated hook that writes the decided `risk` level to the task via `aitask_update.sh --batch <id> --risk <level>`.
- Regenerate goldens under `tests/golden/skills/` + `tests/golden/procs/task-workflow/` and run `./.aitask-scripts/aitask_skill_verify.sh` — **in the same commit**.

## Reference Files for Patterns

- `planning-cross-repo.md` (design-in-planning) + `cross-repo-child-assignment.md` (post-approval Step 7 creation) — the exact design/creation split pattern + flag threading.
- `.claude/skills/task-workflow/planning.md` §6.0/§6.1 Jinja gating (e.g. `plan_preference`) for `{% if profile.<key> %}` form.
- An archived plan with a `## Verification` section for plan body-section style.

## Implementation Plan

1. Author `risk-evaluation.md` (assessment criteria for both dimensions, aggregate-level rubric, `## Risk` section template, gates seam note).
2. Insert the gated dispatch at end of planning.md §6.1; define the `## Risk` section.
3. Add the Step 7 gated `risk`-field write in SKILL.md.
4. Regenerate all rendered variants (`aitask_skill_render.sh` / rerender driver) + goldens; run `aitask_skill_verify.sh`.

## Verification Steps

- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- Render the `default` (key absent) variant → confirm NO risk step appears (feature off). Render a variant with `risk_evaluation: true` → risk step + Step 7 write appear.
- `ait skillrun pick --profile <p> --dry-run` sanity.
- Goldens regenerated and committed together.

## Notes for sibling tasks

The `## Risk` section format defined here is consumed by t884_4 (fills mitigation links) and surfaced in docs by t884_6. The `risk_mitigations_planned` flag is the gate t884_4 keys its Step 7/8d creation on. Keep Step 6.0/8b/8c numbering intact (t884_5 adds 6.0a; t884_4 adds 8d — suffixes only).
