---
priority: medium
effort: low
depends: [t635_33]
issue_type: refactor
status: Implementing
labels: [gates, task_workflow, execution_profiles]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-19 08:27
updated_at: 2026-07-22 12:37
---

## Context

t635_33 landed the `rendered_set` model: skill templates gate risk-producer machinery with
`{% if 'risk_evaluated' in rendered_set %}` where `rendered_set` is injected into the
render context by `lib/skill_template.py` (key-presence: `profile.rendered_gates` if the
key is present — even `[]` — else `profile.default_gates`, else `[]`). Runtime enforcement
follows the persisted `active_gates` tuple materialized at claim. See
`aiplans/p635/p635_33_gate_activation_render_time.md` (archived under
`aiplans/archived/p635/` after t635_33 completes).

The **divergent `task-workflown` / `aitask-pickn` tree was carved out** of t635_33: it
still contains ~8 stale `{% if profile.risk_evaluation %}` blocks keyed on the RETIRED
`risk_evaluation` profile toggle (removed in t635_14). This is a **latent t1147**: under a
profile whose `default_gates` includes `risk_evaluated` (e.g. `fast`), the pickn-rendered
workflow renders NO risk producer (the stale conditional is false — `risk_evaluation` is
absent from profiles) while the Step-9 orchestrator still enforces the declared gate —
a declared-but-unproduced gate blocks archival. Safe today ONLY because nobody runs
pickn + `fast`.

## Scope

1. Migrate every `{% if profile.risk_evaluation %}` block in the `task-workflown` /
   `aitask-pickn` sources to the t635_33 model:
   - render-time machinery gates → `{% if 'risk_evaluated' in rendered_set %}`
   - runtime gate checks → the `aitask_gate.sh active <id> risk_evaluated` decision verb
   - the Step-7 inline backfill (if the tree still has it) → the Step-4
     `materialize-active` call (always rendered, never Jinja-omitted)
2. Align the tree's Step-4 ownership step with task-workflow's (materialize-active +
   optional `active-gates-status` staleness notice).
3. Rerender + regenerate the tree's goldens; `aitask_skill_verify.sh` clean.

## Key files

- `.claude/skills/task-workflown/` and `.claude/skills/aitask-pickn/` sources (grep for
  `profile.risk_evaluation` — expect ~8 hits)
- `tests/golden/` entries for the pickn/task-workflown tree
- Reference implementation: `.claude/skills/task-workflow/{SKILL.md,planning.md}` after
  t635_33 (the migrated blocks)

## Verification

- `grep -r 'profile\.risk_evaluation' .claude/skills/` → zero hits in the pickn tree.
- Render-content assertions: pickn-rendered `fast` variant contains the risk producer;
  `default` variant omits it; materialize-active present in all variants.
- `aitask_skill_verify.sh` passes; goldens committed in the same change.
