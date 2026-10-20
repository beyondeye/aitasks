---
priority: medium
effort: medium
depends: [t2074_9]
issue_type: documentation
status: Ready
labels: [claudeskills, agents_md, seed, documentation, skills]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:33
updated_at: 2026-10-20 12:34
---

## Context

This is part of t2074, which removes legacy repository mode. Agent instructions
and skill prose still say that `./ait git` "passes through to plain `git`" in
legacy mode, and that the data branch is optional. This task removes that
wording from the canonical sources and regenerates every derived file with the
repository's own tooling. It depends on t2074_9, which owns the
token-producing skill edits and their goldens, so this task changes only
wording that carries no token. Read
`aiplans/p2074_remove_legacy_repository_mode_support.md`, in particular the
"Unrelated legacy (exclude)" list.

## Edits (canonical sources)

- `seed/aitasks_agent_instructions.seed.md` :58-60 and :73. This is the shared
  layer that `AGENTS.md`, `.codex/instructions.md` and
  `.opencode/instructions.md` are generated from.
- `CLAUDE.md` :265-279 ("Git Operations on Task/Plan Files"). It is
  hand-maintained (`CLAUDEMD_HAND_MAINTAINED_SENTINEL`, `aitask_setup.sh:1366`),
  so edit it by hand.
- `.claude/skills/ait-git/SKILL.md` :9 (the conditional "when task data lives
  on a separate branch") and :57-59 (the legacy bullet).
- `.claude/skills/task-workflow/repo-structure.md` :30-36 (Detection). The
  website page `concepts/git-branching-model.md:29` links to it.
- `.claude/skills/task-workflow/SKILL.md` :762 ("safe in legacy mode…").
- `.claude/skills/task-workflow/cross-repo-child-assignment.md` :131.
- `README.md` :20 and :93-98: it lists `aitasks/` and `aiplans/` as committed
  to your repo.
- `.aitask-scripts/aitask_setup.sh:1297`: the comment about legacy
  non-data-branch installs.

**Do not reword** the pinned anchor `SKILL.md:843` "**If a separate branch was
created:**". There, "separate branch" means the per-task worktree branch.

## Regenerate (never hand-edit derived files)

- `AGENTS.md`, `.codex/instructions.md` and `.opencode/instructions.md`, via the
  setup assemblers (`assemble_aitasks_instructions` at `aitask_setup.sh:1291`,
  and `update_agentsmd`).
- The goldens: `tests/golden/procs/task-workflow/SKILL-*.md`,
  `cross-repo-child-assignment-default.md`, and every golden whose source
  changed.
- The committed remote prerenders under
  `{.claude,.agents,.opencode}/skills/task-workflow-remote*-/`. Use
  `aitask_skill_rerender.sh remote`, then run `aitask_skill_verify.sh`.
- `tests/fixtures/skills/task-workflow/*.pre-rewrite` are rewrite-test inputs.
  Leave them alone unless a test requires otherwise, and record the decision.

## Port check

Codex and OpenCode trees are renders of the canonical source. If any
non-rendered wrapper under `.agents/` or `.opencode/` still mentions the legacy
layout, create a follow-up task for each agent, per the CLAUDE.md "Working on
Skills" rule. Stale untracked leftovers
(`.claude/skills/task-workflow-fast-/parallel-cross-repo-planning.md`,
`.agents/skills/task-workflow-fast-codex-/parallel-cross-repo-planning.md`)
have no canonical source. Report them; do not delete them without asking.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/test_skill_render_task_workflow.sh` and every
  `tests/test_skill_render_*.sh`
- `bash tests/test_agent_instructions.sh`
- `grep -rn "legacy mode\|passes through to plain" CLAUDE.md seed/ AGENTS.md .codex/ .opencode/instructions.md .claude/skills/ait-git .claude/skills/task-workflow`
  must return nothing, or only justified historical references
