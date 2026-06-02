---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t884_6]
issue_type: chore
status: Implementing
labels: [task_workflow, child_tasks]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 00:31
updated_at: 2026-06-02 12:48
---

## Context

Trailing retrospective child of t884 (see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Per `aidocs/planning_conventions.md` ("in-scope sibling children + a trailing retrospective-evaluation child that depends on the others"), this child runs LAST, documents outcomes, and files the standalone follow-up tasks that t884 deliberately deferred. Depends on all prior t884 children.

## Key Files to Modify

(Primarily creates new tasks; minor doc note only.)
- Document outcomes of the risk-evaluation feature (what shipped, deviations, whether the read-time signal + propose-confirm shapes proved right) — a short retrospective note appended to this task's plan / `aiplans/`.

## Implementation Plan — follow-up tasks to file

1. **Cross-agent skill ports** (per CLAUDE.md "Skill changes done in Claude Code first; suggest separate aitasks to port to other agents"): file standalone aitasks to port the t884 skill/closure changes (`risk-evaluation.md`, `risk-mitigation-followup.md`, planning.md §6.1/6.0a, SKILL.md Step 7/8d, profiles.md `risk_evaluation` key) to:
   - **Codex CLI** (`.agents/skills/`, `.codex/`)
   - **OpenCode** (`.opencode/skills/`, `.opencode/commands/`)
2. **Enum single-source refactor** (per the parent plan's recorded decision + `aidocs/planning_conventions.md` "name the refactor, don't bury it"): file a standalone aitask to extract the `priority` + `risk` enum values (`high|medium|low`) — currently hardcoded across ~5 bash sites + board.py — into a single source of truth (bash sourced lib + mirrored Python constant, or a metadata file).
3. **Gates integration** (per the parent plan's standalone-now-+-seam decision): file a standalone aitask (depends on / referencing t635) to wrap the risk evaluation as a first-class `aitask-gate-risk` once the gates framework lands, replacing the forward-compat seam note added in t884_3.

Use the Batch Task Creation Procedure (`aitask_create.sh --batch --commit`) for each. Set sensible priority/effort/labels; reference t884 in each description.

## Reference Files for Patterns

- `task-creation-batch.md` — the create command template.
- `aidocs/adding_a_new_codeagent.md` / the rerender driver — context for what a cross-agent port entails.
- `aidocs/gates/aitask-gate-framework.md` — the gates contract the integration task targets.

## Verification Steps

- Confirm each follow-up task exists (`ait ls`) with correct metadata and cross-references to t884.
- Confirm the retrospective note is committed.

## Notes for sibling tasks

This child intentionally creates only follow-ups (no feature code). It is the single place the deferred ports/refactor/gates-integration are surfaced so they are not silently lost.
