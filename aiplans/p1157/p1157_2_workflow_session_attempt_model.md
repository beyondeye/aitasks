---
Task: t1157_2_workflow_session_attempt_model.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_1_*.md, aitasks/t1157/t1157_3_*.md … t1157_9_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_2 — Durable workflow sessions and attempts

## Changes

1. Replace the bug-specific singleton record model with versioned workflow
   session and attempt records in `sessions_store.py`. Preserve a stable
   session/thread id; retain per-attempt relay id, project, snapshot commit,
   deadline, status, and cleanup outcome.
2. Add strict atomic `Checkpoint` and unapproved `TaskProposal` records to the
   relay/session contract. Store intent, findings, transcript/Q&A outcomes,
   requested changes, and proposal metadata separately from creation payloads.
3. Add central transition validation for active, awaiting user, synthesizing,
   awaiting approval, paused, revising, creating, terminal, and expired
   states. Make stale controls and superseded attempts no-ops.
4. Migrate legacy records as one bug workflow session/attempt, retain existing
   terminal semantics, and preserve minimal durable state after sandbox cleanup
   until seven-day expiry.
5. Extend reconciliation to recover checkpoints/proposals and to pause rather
   than create when an attempt ends before approved completion.

## Verification

- Add schema/migration/transition rejection tests and atomic crash-window
  tests to relay and daemon suites.
- Prove no unapproved proposal can reach `task_create.py`, Resume carries
  checkpoint/transcript, Restart does not, and expiry disables both.

## Step 9 reference

Record the final record format and migration behavior for routing siblings.
