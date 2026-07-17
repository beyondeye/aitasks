---
Task: t1157_3_multi_workflow_daemon_router.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_1_*.md, aitasks/t1157/t1157_2_*.md, aitasks/t1157/t1157_4_*.md … t1157_9_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_3 — Multi-workflow daemon router

## Changes

1. Define a workflow-handler registry above the generic chat adapter. Handlers
   own trigger matching, attempt creation, rendering policy, launch contract,
   and completion policy; the daemon owns one subscription and one sequential
   mutation consumer.
2. Refactor `daemon.py`, `intake.py`, `flow.py`, and `reconcile.py` to route
   adapter, flow, death, deadline, and approval events through workflow session
   and attempt ids. Retain the current enqueue-only scanner/single-writer
   invariant.
3. Resolve each workflow's project through `ChatlinkHostConfig`; snapshot,
   launch, label, reap, validate, and create tasks in the routed project.
   Scope container ownership and cursor recovery by project/workflow.
4. Preserve legacy singleton behavior through the implicit workflow adapter and
   fail quiet/audit unknown or foreign events.

## Verification

- Add two-project/two-guild mock integration coverage with no cross-talk.
- Cover duplicate/replayed events, payload/death order, restart recovery,
  queue regeneration, and foreign-container reaping.
- Run daemon, flow, and sandbox launch suites.

## Step 9 reference

Document routing and compatibility details for bug/explore handlers.
