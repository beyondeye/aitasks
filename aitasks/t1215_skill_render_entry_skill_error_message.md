---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [claudeskills, bash_scripts]
gates: [risk_evaluated]
created_at: 2026-07-22 11:37
updated_at: 2026-07-22 11:37
boardidx: 30
---

## Context

`./.aitask-scripts/aitask_skill_render.sh <skill> --profile <p> --agent <a>` resolves its entry template via `agent_authoring_template` (`.aitask-scripts/lib/agent_skills_paths.sh:79`), which unconditionally returns `.claude/skills/<skill>/SKILL.md.j2`. When that file does not exist the script fails at `aitask_skill_render.sh:94` with:

```
skill_render: template not found: /.../.claude/skills/task-workflow/SKILL.md.j2
```

This message is misleading for **dependency-only skills** like `task-workflow`: they intentionally have no `SKILL.md.j2` entry template. Their authoring source is the plain `SKILL.md` (which contains Jinja `{% if profile... %}` blocks), and their per-profile variants (`task-workflow-<profile>-/SKILL.md`) are rendered by the t777_22 dep-walker (`lib/skill_template.py walk_closure`) as part of rendering a *caller* entry skill (e.g. `aitask-pick`). A user (or agent) who runs the renderer directly on such a skill gets a "template not found" error that reads like breakage, when the real situation is "this is not an entry skill — render one of its callers instead".

## Goal

Improve the error path in `aitask_skill_render.sh` so the not-an-entry-skill case is diagnosed distinctly:

- When `.claude/skills/<skill>/SKILL.md.j2` is missing but `.claude/skills/<skill>/SKILL.md` **exists and contains Jinja markers** (e.g. `{%`), print a targeted message such as:
  `skill_render: '<skill>' is not an entry skill — it has no SKILL.md.j2 and is rendered as part of its callers' closure (e.g. render 'aitask-pick' and the walker writes <skill>-<profile>- variants). Nothing to do directly.`
- When neither `SKILL.md.j2` nor `SKILL.md` exists, keep a plain "template not found / unknown skill" error.
- Keep the exit code non-zero in both cases (callers must not treat it as a successful render), unless investigation shows a caller depends on a specific code — then preserve the existing code.

## Notes / boundaries

- Do not add a direct-render mode for dependency skills; the closure walk from a caller remains the only sanctioned render path (hand-maintained forks like `task-workflown` are out of scope — see the rerender-misses-task-workflown note).
- Follow `aidocs/framework/shell_conventions.md` for any edits under `.aitask-scripts/`.
- Add/extend a test that asserts both messages (dependency-skill case and truly-unknown-skill case), following the existing bash test conventions in `tests/`.

## Verification

- `./.aitask-scripts/aitask_skill_render.sh task-workflow --profile fast --agent claude` exits non-zero with the new targeted message.
- `./.aitask-scripts/aitask_skill_render.sh no_such_skill --profile fast --agent claude` exits non-zero with the unknown-skill message.
- `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast --agent claude` still exits 0.
- `shellcheck .aitask-scripts/aitask_skill_render.sh` passes.
