---
Task: t884_3_risk_evaluation_planning_step.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_3_risk_evaluation_planning_step
Branch: aitask/t884_3_risk_evaluation_planning_step
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 17:28
---

# Plan: t884_3 — Risk-evaluation step + `## Risk` plan section + Step 7 two-field write

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Depends on **t884_2** (`risk_evaluation` profile key — landed) and **t884_9**
> (the two-field frontmatter plumbing `--risk-code-health` / `--risk-goal-achievement` — landed).

## Context

When directing a coding agent it's hard to know up front whether a planned change
will hurt code health, **and** whether the plan will actually deliver the user's
requested goals. t884 adds a structured **risk evaluation** at the end of planning.
This child wires the **evaluation step itself**: a new closure that assesses the
two risk dimensions, the gated dispatch at the end of planning, and the
post-approval frontmatter write.

**Verify-path correction (2026-06-01):** the pre-existing plan described a *single
aggregate* `risk` field. Per the user redirect that produced **t884_9**, risk is
now estimated and stored as **two independent fields** with **no aggregate**:
- `risk_code_health` — stability / quality / maintainability / blast-radius.
- `risk_goal_achievement` — will the implementation deliver the requested goals
  (approach soundness, requirement coverage, feasibility, completeness).

Each is `high|medium|low`. This plan is rewritten to the two-field design.

**Design/creation split (planning is read-only):** during planning the step only
*decides* both levels and records them to the plan's `## Risk` section + threads
flags; the actual field **writes** are mutations that run **post-approval at
SKILL.md Step 7** — same pattern as `planning-cross-repo.md` (design) +
`cross-repo-child-assignment.md` (Step 7 creation).

## Verify-pass findings (anchors confirmed against the current tree)

- `aitask_update.sh` exposes `--risk-code-health LEVEL` / `--risk-goal-achievement LEVEL`
  (parse arms at ~250-251) — the Step 7 write target exists. ✅
- `risk_evaluation` profile key is registered (`profile_editor.py` schema/info/group;
  `profiles.md` row) and **no committed profile sets it** → feature OFF, committed
  planning/SKILL goldens must stay byte-identical. ✅
- `risk-evaluation.md` does **not** exist yet — to be created. ✅
- planning.md insertion point: immediately before
  `{%- include "_planning_plan_contract.md" -%}` (line ~270) / "Use `ExitPlanMode`"
  (line ~272) — the true end of §6.1's plan-design block. ✅
- SKILL.md Step 7 post-approval funnel: the cross-repo hook sits at line ~281,
  right after "Repository structure awareness"; the new write hook goes alongside it. ✅
- Render test `tests/test_skill_render_task_workflow.sh`: `WRAPPED_FILES_INVARIANT`
  array (line ~90), Test 4 synthetic-profile pattern (line ~228). ✅

## Steps

### 1. New closure `.claude/skills/task-workflow/risk-evaluation.md` (the design part)

Profile-agnostic (**no `{{ profile.* }}` vars**) so it renders identically across
profiles and stays a profile-invariant golden. Contents:

- **Per-dimension assessment criteria**, assessed **separately**:
  - *Code-health* (`risk_code_health`): stability, quality, maintainability,
    blast-radius of the planned change.
  - *Goal-achievement* (`risk_goal_achievement`): approach soundness, requirement
    coverage, technical feasibility, completeness vs the user's requested goals.
- **Per-dimension level rubric** — `high|medium|low` guidance for each dimension
  independently (no aggregation/derivation across the two).
- **`## Risk` section template** — two subsections, **each headed by its own level**:
  ```markdown
  ## Risk

  ### Code-health risk: <high|medium|low>
  - <description> · severity: <…> · → mitigation: <link filled by t884_4>
  - …  (or "None identified.")

  ### Goal-achievement risk: <high|medium|low>
  - <description> · severity: <…> · → mitigation: <link filled by t884_4>
  - …  (or "None identified.")
  ```
- **Return/thread contract:** the procedure decides `risk_level_code_health`,
  `risk_level_goal_achievement`, and `risk_mitigations_planned` and hands them
  back to the planning flow. It performs **no mutations** (read-only plan mode).
- **Gates seam note (forward-compat):** a short comment that this eval maps to a
  future `aitask-gate-risk` once t635 lands (reference `aidocs/gates/`); **do NOT
  couple** to gates.

### 2. `planning.md` — gated dispatch at the end of §6.1

Insert immediately before the `{%- include "_planning_plan_contract.md" -%}` line
(~270), wrapped so it has **zero footprint when the key is off**:

```jinja
{%- if profile.risk_evaluation is defined and profile.risk_evaluation %}
- **Risk evaluation (end of planning):** Read and follow the **Risk Evaluation
  Procedure** (see `risk-evaluation.md`). It assesses both risk dimensions,
  assigns a level for each, and authors the `## Risk` section into the plan.
  Thread `risk_level_code_health`, `risk_level_goal_achievement`, and
  `risk_mitigations_planned` into the workflow context for Step 7.
{%- endif %}
```

⚠️ The renderer runs `undefined_behavior="strict"`, so the `is defined` guard is
**required** (a bare `{% if profile.risk_evaluation %}` errors on the absent key —
mirror `remote-drift-check.md`'s guard form). The `{%-`/`-%}` lstrip yields a
byte-identical render when the key is absent.

### 3. `SKILL.md` Step 7 — gated post-approval two-field write

Add a same-guarded hook in the Step 7 post-approval funnel, alongside the
cross-repo-child-assignment hook (~line 281):

```jinja
{%- if profile.risk_evaluation is defined and profile.risk_evaluation %}

**Risk fields (post-approval write):** If the approved plan has a `## Risk`
section, write both decided levels now:
```bash
./.aitask-scripts/aitask_update.sh --batch <task_id> \
  --risk-code-health <risk_level_code_health> \
  --risk-goal-achievement <risk_level_goal_achievement>
```
Skip silently if the plan has no `## Risk` section.
{%- endif %}
```

### 4. Tests, goldens, rerenders — **same commit**

- Add `risk-evaluation.md` to `WRAPPED_FILES_INVARIANT` in
  `tests/test_skill_render_task_workflow.sh` (it's profile-agnostic → one canonical
  golden, byte-identical across profiles).
- Add a **synthetic-profile test** (mirror Test 4): a temp profile with
  `risk_evaluation: true` proves (a) the planning step dispatch appears and (b) the
  Step 7 two-field write appears; the default render shows neither.
- Add the canonical golden `tests/golden/procs/task-workflow/risk-evaluation-default.md`.
- Regenerate goldens: committed `planning-{default,fast,remote}.md` and
  `SKILL-{default,fast,remote}.md` must show **zero diff** (no committed profile
  sets the key).
- Rerender per-profile closures: `aitask_skill_rerender.sh {default,fast,remote}`.
- Run `./.aitask-scripts/aitask_skill_verify.sh`.

## Reference patterns

- `planning-cross-repo.md` (design-in-planning) + `cross-repo-child-assignment.md`
  (post-approval Step 7 creation) — the exact design/creation split + flag threading.
- `remote-drift-check.md` — the `{% if profile.X is defined and profile.X %}` guard
  + `{%- … %}` lstrip for a key no committed profile sets (exact analog).

## Verification

- `bash tests/test_skill_render_task_workflow.sh` green — zero diff on committed
  planning/SKILL goldens; new `risk-evaluation-default.md` matches; synthetic-profile
  (`risk_evaluation: true`) test proves both the planning step and the Step 7
  two-field write appear; default render shows neither.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `ait skillrun pick --profile fast --dry-run` sanity.
- Goldens + rerendered variants committed together with the source edits.

## Notes for sibling tasks

- The two-subsection `## Risk` format (each subsection headed by its own level) is
  consumed by **t884_4** (fills mitigation links) and surfaced in docs by **t884_6**.
- `risk_mitigations_planned` gates t884_4's Step 7 / Step 8d creation;
  `risk_mitigation_tasks` stays a single shared list.
- Keep Step 6.0 / 8b / 8c numbering intact (t884_5 adds 6.0a; t884_4 adds 8d —
  suffixes only).
- Always use the `{% if profile.X is defined and profile.X %}` gate form
  (strict-mode renderer errors on bare access).

## Step 9 (Post-Implementation)

Standard child-task archival per the shared workflow Step 9: commit code changes
(`enhancement: … (t884_3)`) + goldens/rerenders in the **same commit**, update +
commit the plan file via `./ait git`, then `aitask_archive.sh 884_3`.
