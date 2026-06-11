# Shared template fragments

This directory holds markdown fragments that are pulled in via template
includes by **two independent template pipelines**:

| Pipeline | Renderer | Include syntax | Production consumer |
|----------|----------|----------------|---------------------|
| Skill templates | minijinja (`skill_template.py`) | `{% include "X" %}`, `{% from "X" import Y %}`, `{% import "X" as Y %}` | `.claude/skills/task-workflow/planning.md` → `_planning_plan_contract.md`; 4 *_auto_continue skills → `_auto_continue_block.j2` (macro import) |
| Brainstorm crew templates | bash (`resolve_template_includes` in `lib/agentcrew_utils.sh`, called from `aitask_crew_addwork.sh`) | `<!-- include: X -->` | No current cross-dir consumer — the resolver can fall back here, but brainstorm templates currently include from their own dir (e.g. `brainstorm/templates/explorer.md` → `_section_format.md`). |

For the broader authoring rules (when to reach for a macro vs. an
`{% include %}` vs. a procedure-markdown extraction, plus the minijinja
caveats), see `aidocs/framework/skill_authoring_conventions.md` §"Jinja templating
in skills".

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
- `_auto_continue_block.j2` — Jinja macro (`auto_continue_block`) that
  emits the post-task-creation "Continue / Save for later"
  decision-point block. Consumed via `{% from "_auto_continue_block.j2"
  import auto_continue_block %}` by 4 skills (`aitask-explore`,
  `aitask-fold`, `aitask-pr-import`, `aitask-revert`). The `.j2`
  extension marks it as a macro library rather than a standalone
  fragment.

The `_` prefix is a partials convention carried over from the brainstorm
templates dir (`_section_format.md` etc.) — every file here is an include
target, never rendered standalone.

## Staleness

Editing a fragment here propagates correctly to consumers:

- **Skill side:** `skill_template.py`'s `walk_closure()` scans every source
  for `{% include %}`, `{% from %}`, and `{% import %}` directives and
  folds the resolved dep mtimes into `_is_stale()`. Touching a fragment
  re-renders every consuming skill on the next `aitask_skill_render.sh`
  invocation. Alongside the mtime fast-path, `_any_target_differs()` compares
  each target's on-disk content against the fresh render, so a committed
  prerender that drifted under git-equalized mtimes (`git checkout`/clone
  resets source and target to the same timestamp) is still repaired.
- **Brainstorm side:** crew templates (e.g. explorer.md) are freshly
  include-resolved into a new work2do file on every `ait crew addwork`, so
  no caching layer to invalidate.

## Verification

- `bash tests/test_skill_render_task_workflow.sh` exercises the minijinja
  side (Test 2c): `_planning_plan_contract.md` resolves into planning.md.
- `bash tests/test_crew_template_includes.sh` exercises the bash side —
  in-dir includes (Test 7, `_section_format.md`) and the multi-base-dir
  resolver capability plus its missing-fallback warning path (Test 8).
