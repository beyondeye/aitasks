---
Task: t399_aitaskredesign.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t399 - Aitask Redesign

## Context

Task `t399` defines a new `/aitask-redesign` skill for situations where an
existing task or plan still contains useful user intent, but the original
implementation direction is no longer the right one. The core use cases are:

- redesign after a full or partial revert
- redesign after changed requirements or changed infrastructure
- brainstorm alternative designs from an existing task/plan before
  implementation

The current repository already has strong adjacent workflows:

- `/aitask-revert` for backing changes out while keeping traceability
- `/aitask-explore` for guided investigation that creates new tasks
- `/aitask-fold` for merging overlapping tasks
- task-workflow planning for child-task decomposition and external plan files

The new skill should reuse those patterns rather than introduce new shell
infrastructure unless a real gap is discovered during implementation.

## Approved V1 Scope

- Implement a new `/aitask-redesign` skill in `.claude/skills/`
- Support two modes inside the same skill:
  - redesign an existing task because constraints changed
  - brainstorm alternative designs from an existing task/plan
- Create a **new** redesign task and a matching plan file; do not mutate the
  original task in place in v1
- Add lightweight wrappers for OpenCode and Codex/Gemini after the Claude skill
  is defined
- Document the new skill and its workflows on the website
- Defer full AgentCrew-powered deep brainstorming to a later follow-up unless
  the workflow spec shows it can be added cleanly without breaking the
  user-in-the-loop approval model

## Child Task Breakdown

### t399_1 - Redesign workflow spec

Create a source-of-truth design note in `aidocs/brainstorming/aitask_redesign_spec.md` that
defines:

- exact user-visible workflow
- supported source-task states and discovery paths
- redesign triggers and brainstorming behavior
- the task/plan artifact templates to generate
- why v1 creates a new task instead of editing the original task
- why deep AgentCrew brainstorming is deferred in v1

### t399_2 - Implement redesign skill and wrappers

Implement the approved workflow using existing helpers first:

- `.claude/skills/aitask-redesign/SKILL.md`
- optional helper markdowns under `.claude/skills/aitask-redesign/`
- `.agents/skills/aitask-redesign/SKILL.md`
- `.opencode/skills/aitask-redesign/SKILL.md`
- `.opencode/commands/aitask-redesign.md`

The implementation should resolve source tasks/plans, ask redesign questions,
compare 2-3 approaches, require approval, create the new redesign task and plan
file, then offer continue-now vs save-for-later.

### t399_3 - Document redesign skill and workflows

Document the new feature in the website docs:

- `website/content/docs/skills/aitask-redesign.md`
- `website/content/docs/workflows/task-redesign.md`
- `website/content/docs/skills/_index.md`
- `docs/README.md`
- `website/content/docs/skills/verified-scores.md` if child 2 adds feedback

The docs should cover both redesign and brainstorm use cases, and explicitly
cross-link the workflow to `/aitask-revert`.

## Dependency Order

`t399_1 -> t399_2 -> t399_3`

This keeps the workflow/design decisions stable before the skill is written,
and keeps the public docs aligned with the final implemented behavior.

## Verification Strategy

- Child 1: spec answers the main product questions and defines exact templates
- Child 2: smoke-walk the new flow against a real task id and verify every
  referenced helper path exists
- Child 3: run `hugo build --gc --minify` inside `website/`

## Post-Implementation Note

Each child task will follow the normal shared workflow through Step 9, so the
resulting task and plan files are archived with full traceability when the child
is completed.
