---
Task: t311_require_plan_mode_for_codex_for_interactive_skills.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Require Plan Mode for Codex CLI Interactive Skills (t311)

## Context

Codex CLI's `request_user_input` only works in plan mode (Suggest mode internally). When not in plan mode, interactive skills silently skip all user questions, causing wrong decisions. Task-workflow skills also had issues with skipped plan creation and post-implementation finalization.

## Implementation

1. Created `.agents/skills/codex_interactive_prereqs.md` — plan mode requirement check for all interactive skills
2. Added "Task-Workflow Adaptations" section to `.agents/skills/codex_tool_mapping.md` — plan file creation and post-implementation finalization instructions for task-workflow skills
3. Updated 14 interactive Codex skill wrappers with `## Prerequisites` section referencing the prereqs file
4. Updated `aitasks/t130/t130_3_codex_docs_update.md` with note about plan mode requirement

## Final Implementation Notes

- **Actual work done:** Created shared prerequisites file, updated tool mapping with task-workflow adaptations, added Prerequisites section to 14 interactive wrappers, added note to t130_3
- **Deviations from plan:** None — implemented as planned
- **Issues encountered:** None
- **Key decisions:** Separated concerns: plan mode check in dedicated prereqs file (all interactive skills), task-workflow adaptations in existing tool mapping file (already referenced by all wrappers). Non-interactive skills (pickrem, pickweb, stats) left unchanged.
