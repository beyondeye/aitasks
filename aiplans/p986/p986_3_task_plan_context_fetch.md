---
Task: t986_3_task_plan_context_fetch.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_1_*.md, aitasks/t986/t986_2_*.md, aitasks/t986/t986_4_*.md, aitasks/t986/t986_5_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: aiwork/t986_3_task_plan_context_fetch
Branch: aitask/t986_3_task_plan_context_fetch
Base branch: main
---

# Plan: t986_3 — Task/plan context-fetch utility

## Context

For the "AskUserQuestion shown without source context" case, the shadow must
auto-fetch the task file + most-recent plan (and optionally sibling context) for
the task the source agent is on. Thin wrapper over the canonical scanners; pure;
parallelizable with t986_1/t986_2.

## Implementation steps

1. **Create** `.aitask-scripts/aitask_shadow_context.sh` (whitelisted helper;
   add to the helper-script whitelist).
2. Resolve task file: `aitask_query_files.sh task-file <id>` (then `archived-task`).
3. Resolve most-recent plan: `aitask_query_files.sh plan-file <id>`; pick the
   latest when several match.
4. Optional sibling context (flag-gated, default off):
   `aitask_query_files.sh sibling-context <parent>`.
5. Deeper history on demand only: defer to `aitask_explain_context.sh --max-plans N`
   (reuse its cache; do not fork the scan).
6. Emit a stable contract: `TASK_FILE:`, `PLAN_FILE:`, `SIBLING:` lines,
   `NOT_FOUND` when absent.

## Verification

- Fixture tasks (parent + child, active + archived) resolve the correct task and plan files.
- Most-recent-plan selection picks the latest when multiple plans exist.
- `NOT_FOUND` path is emitted for a missing task/plan.
- `shellcheck aitask_shadow_context.sh` clean; helper registered in the whitelist.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
