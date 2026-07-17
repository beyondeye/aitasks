---
Task: t1157_7_chatlink_tui_workflow_management.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_1_*.md … t1157_6_*.md, aitasks/t1157/t1157_8_*.md, aitasks/t1157/t1157_9_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_7 — Workflow-aware Chatlink TUI and configuration

## Preconditions

Read the final t1149_2/t1149_3 implementation records before changing any TUI
or wizard code. Extend their APIs; do not recreate their panel/wizard behavior.

## Changes

1. Expand the status view with connection, project, workflow, session/attempt,
   remaining-budget, paused/proposal, and expiry information while retaining the
   existing audit and status panels.
2. Keep normal polling cheap/read-only. Cache expensive preflight workers and
   never let the TUI approve, resume, restart, launch, or kill a workflow.
3. Extend the shipped wizard to edit project workflow definitions and the
   machine host registry separately. Preserve unknown keys, keep secrets out
   of YAML, and make legacy migration an explicit reviewable action.
4. Render per-workflow validation errors: duplicate triggers, unavailable
   projects, token/connection issues, and agent/image readiness.

## Verification

- Add Pilot coverage for multiple records/workflows, corrupt/expired state,
  cheap polling, cached worker refresh, host/project edits, and migration.
- Run the final t1149 tests plus Chatlink TUI/config/preflight suites.

## Step 9 reference

Record final UI terminology and config paths for the documentation child.
