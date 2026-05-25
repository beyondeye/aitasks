# Shared template fragments

This directory holds markdown fragments that are pulled in via template
includes by **two independent template pipelines**:

| Pipeline | Renderer | Include syntax | Production consumer |
|----------|----------|----------------|---------------------|
| Skill templates | minijinja (`skill_template.py`) | `{% include "X" %}` | `.claude/skills/task-workflow/planning.md` → `_planning_plan_contract.md` |
| Brainstorm crew templates | bash (`resolve_template_includes` in `lib/agentcrew_utils.sh`, called from `aitask_crew_addwork.sh`) | `<!-- include: X -->` | `.aitask-scripts/brainstorm/templates/detailer.md` → `_detailer_rules.md` |

Both renderers search this dir as a **fallback** after their primary search
dir(s):

- minijinja's loader path = `[<skill dir>, <skills root>, <repo>/.aitask-scripts/skill_templates]`
- the bash resolver's variadic signature lets `aitask_crew_addwork.sh` pass
  `(<work2do dir>, <repo>/.aitask-scripts/skill_templates)`

Each fragment may be consumed by EITHER pipeline (or both — content
permitting). The dir exists so cross-pipeline includes don't force a
fragment to live under one pipeline's "owner" dir.

## Fragment naming and scope

- `_planning_plan_contract.md` — the implementation-plan content contract
  embedded in `task-workflow/planning.md` (skill side). Single-level plans.
  Do NOT consume from detailer.md — the brainstorm detailer has a
  two-level (proposal + plan) structure and its own contract inlined in
  `detailer.md`.
- `_detailer_rules.md` — the 5 authoring rules embedded in
  `brainstorm/templates/detailer.md`'s `## Rules` section. Brainstorm-side
  fragment that demonstrates the bash resolver crossing into the shared
  dir; do NOT consume from planning.md.

The `_` prefix is a partials convention carried over from the brainstorm
templates dir (`_section_format.md` etc.) — every file here is an include
target, never rendered standalone.

## Staleness

Editing a fragment here propagates correctly to consumers:

- **Skill side:** `skill_template.py`'s `walk_closure()` scans every source
  for `{% include %}` directives and folds the resolved dep mtimes into
  `_is_stale()`. Touching a fragment re-renders every consuming skill on
  the next `aitask_skill_render.sh` invocation.
- **Brainstorm side:** detailer.md is freshly include-resolved into a new
  work2do file on every `ait crew addwork`, so no caching layer to
  invalidate.

## Verification

- `bash tests/test_skill_render_task_workflow.sh` exercises the minijinja
  side (Test 2c) and asserts no cross-leak from detailer-specific contract.
- `bash tests/test_crew_template_includes.sh` exercises the bash side
  (Tests 8 + 9) including the real `detailer.md` → `_detailer_rules.md`
  cross-dir resolution and the missing-fallback warning path.
