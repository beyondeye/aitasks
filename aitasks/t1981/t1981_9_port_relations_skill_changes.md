---
priority: medium
effort: low
depends: [t1981_4, t1981_5, t1981_6]
issue_type: chore
status: Ready
labels: [task_relations, skills]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-04 15:39
---

## Context

Child of t1981. Skill changes land in the Claude Code tree first (`.claude/skills/`).
This child ports them to the other supported agent trees: Codex CLI / agy
(`.agents/skills/`) and OpenCode (`.opencode/skills/`, `.opencode/commands/`).
Design anchor: `aidocs/framework/task_relations.md`.

Changes to port, from what actually landed:
- **t1981_4:** the plan-approval enqueue in task-workflow Step 7 and
  `plan-approved-stop.md`.
- **t1981_5:** the related-work procedure (Step 3 check and Step 8 re-check),
  the Step 8e notify flow, and `/aitask-note` store-first.
- **t1981_6:** the obsolescence band display in the related-work check.

## Scope

1. **Inventory first.** Diff every skill or procedure file that t1981_4, t1981_5
   and t1981_6 changed. List the corresponding files in each agent tree.
2. **Port each change**, adapting to the target agent's skill format. The
   headless relations operation itself is Claude-only in v1 (D5). The
   *consumers* (pick-time check, Step 8e, `/aitask-note`) must work under every
   agent: they only call `ait relations` CLIs.
3. **Regenerate goldens** and run `./.aitask-scripts/aitask_skill_verify.sh`.

## Reference patterns

- `aidocs/framework/skill_authoring_conventions.md`
- `aidocs/framework/stub-skill-pattern.md`
- `aidocs/framework/adding_a_new_codeagent.md` (shared-root semantics of
  `.agents/`)
- `aidocs/framework/agent_runtime_guards_audit.md`, before adding or moving any
  `{% if agent %}` gate.

## Implementation plan

See `aiplans/p1981/p1981_9_port_relations_skill_changes.md`.

## Verification

- `aitask_skill_verify.sh` passes.
- The goldens are regenerated in the same commit.
- A rendered variant per agent shows the new steps.
