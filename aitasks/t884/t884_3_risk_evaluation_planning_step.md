---
priority: high
effort: high
depends: [t884_2, t884_9]
issue_type: enhancement
status: Implementing
labels: [task_workflow, task-planning]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 00:30
updated_at: 2026-06-01 17:24
---

## Context

Core child of t884 (see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Adds the risk-evaluation step at the END of planning and the `## Risk` plan-section format, and writes the **two** risk frontmatter fields post-approval. Depends on t884_2 (the `risk_evaluation` profile key) and **t884_9** (the two-field frontmatter plumbing — `risk_code_health` / `risk_goal_achievement`, replacing the single aggregate `risk` field).

The eval assesses **two dimensions and assigns a level for each** (no aggregate): (A) **code-health** (`risk_code_health`) — stability / quality / maintainability / blast-radius; (B) **goal-achievement** (`risk_goal_achievement`) — will the planned implementation actually deliver the user's requested goals (approach soundness, requirement coverage, technical feasibility, completeness). Each is high/medium/low.

**Design/creation split (planning runs read-only):** during planning the step only *decides* and records to the plan's `## Risk` section + threads flags; the actual field writes are mutations that run **post-approval at SKILL.md Step 7** (same pattern as cross-repo `cross-repo-child-assignment.md`).

## Key Files to Modify

- New closure `.claude/skills/task-workflow/risk-evaluation.md` — the Risk Evaluation Procedure (design part): how to assess both dimensions **separately**, assign a level for each, and author the `## Risk` section. Include a forward-compatible **gates seam** note (how this eval maps to a future `aitask-gate-risk` once t635 lands — reference `aidocs/gates/`). Do NOT couple to gates. Keep it profile-agnostic (no `{{ profile.* }}` vars) so it stays a profile-invariant golden.
- `.claude/skills/task-workflow/planning.md` — at the **end of §6.1** (after the plan is designed, before "Use `ExitPlanMode`"), add the dispatch to the Risk Evaluation Procedure, wrapped in `{% if profile.risk_evaluation is defined and profile.risk_evaluation %}` … `{% endif %}` with `{%- … %}`/`{%- endif %}` lstrip (⚠️ strict-mode renderer requires the `is defined` guard; lstrip = zero footprint when off). Thread `risk_level_code_health`, `risk_level_goal_achievement`, and `risk_mitigations_planned` into the workflow context.
- Define the `## Risk` plan-section format (in the closure): **two subsections, each headed by its own level** — `### Code-health risk: <level>` and `### Goal-achievement risk: <level>`, each listing risk bullets `description · severity · → mitigation link (filled by t884_4)`. Either subsection may read "None identified."
- `.claude/skills/task-workflow/SKILL.md` — at **Step 7** (post-approval, the single creation funnel where cross-repo creation also hooks), add a same-guarded hook that writes **both** decided levels via `aitask_update.sh --batch <task_id> --risk-code-health <ch> --risk-goal-achievement <ga>` (skip silently if no `## Risk` section).
- Regenerate goldens under `tests/golden/procs/task-workflow/` (expect **zero diff** on committed planning/SKILL goldens — no committed profile sets the key; add `risk-evaluation-default.md`; add `risk-evaluation.md` to `WRAPPED_FILES_INVARIANT` + a synthetic-profile test in `tests/test_skill_render_task_workflow.sh`), rerender per-profile closures (`aitask_skill_rerender.sh {default,fast,remote}`), and run `./.aitask-scripts/aitask_skill_verify.sh` — **in the same commit**.

## Reference Files for Patterns

- `planning-cross-repo.md` (design-in-planning) + `cross-repo-child-assignment.md` (post-approval Step 7 creation) — the exact design/creation split pattern + flag threading.
- `.claude/skills/task-workflow/remote-drift-check.md` — the `{% if profile.X is defined and profile.X %}` guard form + `{%- … %}` lstrip for a key no committed profile sets (the exact analog for `risk_evaluation`).
- An archived plan with a `## Verification` section for plan body-section style.

## Implementation Plan

> Blocked until **t884_9** lands (the `--risk-code-health` / `--risk-goal-achievement` flags it writes at Step 7).

1. Author `risk-evaluation.md` (per-dimension assessment criteria, per-dimension level rubric, two-subsection `## Risk` template, gates seam note).
2. Insert the gated dispatch at end of planning.md §6.1 (`is defined` guard + lstrip); thread the two levels + `risk_mitigations_planned`.
3. Add the Step 7 gated two-field write in SKILL.md.
4. Regenerate goldens, add `risk-evaluation.md` to the render test's `WRAPPED_FILES_INVARIANT` + a synthetic-profile test, rerender per-profile closures; run `aitask_skill_verify.sh`.

## Verification Steps

- `bash tests/test_skill_render_task_workflow.sh` green — zero diff on committed planning/SKILL goldens; new `risk-evaluation-default.md` matches; synthetic-profile (`risk_evaluation: true`) test proves both the planning step and the Step 7 two-field write appear; default render shows neither.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `ait skillrun pick --profile fast --dry-run` sanity.
- Goldens + rerendered variants committed together with the source edits.

## Notes for sibling tasks

The two-subsection `## Risk` format (each subsection headed by its own level) is consumed by t884_4 (fills mitigation links) and surfaced in docs by t884_6. The `risk_mitigations_planned` flag gates t884_4's Step 7/8d creation; `risk_mitigation_tasks` stays a single shared list. Keep Step 6.0/8b/8c numbering intact (t884_5 adds 6.0a; t884_4 adds 8d — suffixes only). Use the `{% if profile.X is defined and profile.X %}` gate form (strict-mode renderer errors on bare access).
