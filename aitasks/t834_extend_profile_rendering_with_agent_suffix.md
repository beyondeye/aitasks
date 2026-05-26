---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [codeagent, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 12:12
updated_at: 2026-05-26 18:26
boardidx: 40
---

## Context

Sibling task of t812 (remove geminicli) and t814 (add agy). This task
is a **prerequisite for t814**: it extends the framework's existing
execution-profile skill-rendering mechanism so that rendered SKILL.md
filenames carry an **agent-type suffix** in addition to the profile
suffix. This is needed because agy and Codex CLI both target the same
physical skills directory (`.agents/skills/<name>/SKILL.md`), and the
framework's current per-agent Jinja rendering cannot place two
different agent-specific versions at the same path without filename
disambiguation.

The user explicitly chose this approach over reverting to runtime
checks inside a single shared skill body (see memory entry
`feedback_shared_skill_path_extend_suffix.md`).

## Goal

Today's rendered variants land at
`.agents/skills/<name>-<profile>-/SKILL.md` (e.g.,
`aitask-pick-fast-/SKILL.md`). After this task, agents whose physical
path collides with another agent's get an additional **agent-suffix**
appended, e.g.,:

- `.agents/skills/aitask-pick-fast-codex-/SKILL.md`
- `.agents/skills/aitask-pick-fast-agy-/SKILL.md`

Each agent's runtime invocation reads its own pre-rendered variant.

Agents whose physical paths do NOT collide (e.g., claude →
`.claude/skills/`, opencode → `.opencode/skills/`) retain the
current single-suffix scheme unless adding the agent suffix is
trivially uniform (designer's call).

## Key implementation areas (to be explored during planning)

- `.aitask-scripts/lib/skill_template.py` — rendering output-path
  composition logic.
- `.aitask-scripts/lib/agent_skills_paths.sh` — agent → physical path
  mapping; introduce a "shared physical path" concept that triggers
  the agent suffix.
- `.aitask-scripts/aitask_skill_render.sh`,
  `aitask_skill_rerender.sh`, `aitask_skill_verify.sh` — rendering
  driver scripts that may need to learn the new naming.
- `.claude/skills/*-fast-/SKILL.md` (and other rendered profile
  variants) — confirm dispatcher stubs (the user-facing stub surface)
  can find the agent-suffixed variant at runtime.
- Skill stub surface (the entrypoint `.md` files that read the
  profile-suffixed variant) — extend to also resolve the
  agent-suffix when applicable.

## Out of scope

- Adding any new coding agent (agy is a separate task: t814).
- Removing geminicli (t812).

## Required outcomes

1. Skill rendering supports a `<profile>-<agent>` filename-suffix
   format for agents in a "shared physical path" set, gated by
   either a config flag or a per-agent property.
2. Existing agents (claude, codex, opencode) keep working with no
   visible change (codex may need re-rendering once it enters the
   shared-path set, but the test suite must still pass).
3. Skill goldens regenerated and committed; `aitask_skill_verify.sh`
   passes.
4. `.claude/skills/*-fast-/SKILL.md` stub-surface logic correctly
   resolves the agent-suffixed variant at runtime (where applicable).

## Planning hint

When picked, the planner should explore the existing rendering
pipeline end-to-end to understand how profile-suffix files are
currently composed, then decide on the minimum-impact way to layer
in the agent-suffix dimension. The choice between "always add agent
suffix" vs "only for shared-path agents" is a design call best made
during planning.
