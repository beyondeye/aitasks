---
priority: medium
effort: medium
depends: [t777_27]
issue_type: refactor
status: Implementing
labels: [t777, skill-templates, minijinja]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-23 23:39
updated_at: 2026-05-26 09:50
---

# Goal

De-duplicate branch text inside the t777-converted skill templates by applying two distinct levers, matching the existing framework conventions:

1. **Across skills** — when the same ~15-line decision block is duplicated across multiple skills (`aitask-explore`, `aitask-fold`, `aitask-pr-import`, `aitask-revert`), extract it into a **common procedure markdown file** (the same pattern as `task-workflow/satisfaction-feedback.md`, `task-workflow/task-creation-batch.md`, `task-workflow/related-task-discovery.md`). Each calling skill's `.md.j2` replaces the duplicated block with a one-line "Execute the X Procedure" reference. The common procedure file is itself profile-aware and rendered per-profile.

2. **Within a single skill** — when the duplication is two near-identical blocks inside one template (e.g., `aitask-pick` parent-task vs. child-task confirmation), prefer a **MiniJinja `{% macro %}` defined in the same file** that both call-sites invoke with their differing arguments. Do NOT factor into a separate `.j2` include file; keep the in-file scope.

# Why a separate task

The conversion siblings t777_6..t777_13 each landed their own `.md.j2`, naturally producing parallel duplication. Now that the conversion has stabilized, the dedup refactor is a single focused pass with shared review burden. Gated on **t777_27** so the parity tests against the recovered originals exist before any `.j2` is touched.

# Concrete duplication targets

## Cross-skill (lever 1 — common procedure markdown)

The `*_auto_continue` decision-point block appears in 4 skills with ~95% identical text, only the question wording and skill-name token vary:

- `.claude/skills/aitask-explore/SKILL.md.j2` lines ~178–196
- `.claude/skills/aitask-fold/SKILL.md.j2` lines ~78–95
- `.claude/skills/aitask-pr-import/SKILL.md.j2` lines ~259–278
- `.claude/skills/aitask-revert/SKILL.md.j2` lines ~613–631

Total duplicated lines: ~76 across the four templates.

Refactor:

1. Add a new common procedure file `.claude/skills/task-workflow/decision-point-auto-continue.md` (NB — write the `.md.j2` source; the renderer produces the `.md`). It branches on `profile.explore_auto_continue` and renders the appropriate decision-point text given a few template parameters (skill_name, question_prefix, task_ref, next_step).
2. Each calling SKILL.md.j2 replaces the 19-line block with:
   > Execute the **Auto-Continue Decision Procedure** (see `.claude/skills/task-workflow/decision-point-auto-continue.md`) with `skill_name` = `"<explore|fold|revert|pr-import>"`, `question_prefix` = `"<…>"`, `next_step` = `"<…>"`.
3. Register the new file in whatever closure / dependency walker `aitask_skill_render.sh` uses for `task-workflow` siblings (mirror what was done for `satisfaction-feedback.md`).
4. Regenerate the per-profile goldens under `tests/golden/skills/{aitask-explore,aitask-fold,aitask-pr-import,aitask-revert}/` and the new `tests/golden/procs/task-workflow/decision-point-auto-continue-*.md`.

Verify the four skills end up with byte-identical *rendered* output to their current goldens (semantic preservation) — any divergence is a bug in the procedure parameters.

## Within-skill (lever 2 — `{% macro %}`)

`.claude/skills/aitask-pick/SKILL.md.j2` lines ~24–34 (parent-task confirmation) and lines ~53–63 (child-task confirmation) duplicate the `skip_task_confirmation` branch with only the AskUserQuestion `Question:` string differing.

Refactor:

1. At the top of `aitask-pick/SKILL.md.j2`, define a `confirm_task_selection(task_summary)` macro that wraps the `{% if profile.skip_task_confirmation %} … {% else %} … {% endif %}` block.
2. Replace both call-sites with `{{ confirm_task_selection("<1-2 sentence summary of the task>") }}` and `{{ confirm_task_selection("<1-2 sentence summary of the child task> (Parent: <parent task name>)") }}`.
3. Regenerate `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md` and verify byte-identical.

## (Optional / nice-to-have) `{% set %}` cleanup

Across all templates, `{% if profile.X is defined and profile.X %}` can be tidied with `{% set has_X = profile.X is defined and profile.X %}` at the top of the file. This is purely cosmetic — include only if it doesn't expand the diff awkwardly. Skip if it churns goldens for no semantic reason.

## NOT in scope

- `{% extends %} / {% block %}` template inheritance. The renderer wrapper at `.aitask-scripts/lib/skill_template.py` line 11 explicitly recommends against it.
- `{% include %}` for cross-skill sharing. Per the project preference, cross-skill sharing happens at the **common procedure markdown** layer, not the Jinja include layer.
- Anything beyond the four listed `*_auto_continue` skills and `aitask-pick`. Other dedup opportunities (e.g., `aitask-review`'s `review_default_modes` block, which is a single-skill block — could use a macro if it has internal duplication, otherwise leave it) can be filed as a follow-up.

# Acceptance criteria

- The parity tests from t777_27 (`bash tests/test_skill_parity_runtime_vs_rendered.sh`) still pass for `aitask-pick` after the macro refactor.
- For each of the four `*_auto_continue` skills: rendered output for every `(profile, agent)` pair is byte-identical to the goldens checked in just before this task started. Goldens are updated only if the regeneration is semantically equivalent and the diff is reviewed.
- The new `.claude/skills/task-workflow/decision-point-auto-continue.md.j2` (or whatever name we choose) is referenced by all four skills via the standard "Execute the X Procedure" sentence.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `shellcheck .aitask-scripts/aitask_*.sh` passes.
- Total `.md.j2` line count drops by at least 60 lines net across the five touched skill templates (~76 expected gross savings minus ~10–15 lines for the procedure references and macros).
- Closure-walker tests (`tests/test_skill_render_uniform.sh`, etc.) still pass.

# Dependencies

- `depends: [777, t777_27]` — parity tests must exist before this refactor lands.
