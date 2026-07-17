---
Task: t1157_9_chatlink_multi_workflow_verification.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_1_*.md … t1157_8_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_9 — Multi-workflow verification and soak coverage

## Changes

1. Extend the reusable Chatlink flow fixture into a seeded randomized harness.
   Interleave multiple projects, guilds, workflow types, sessions, attempts,
   questions, checkpoints, proposals, approvals, revisions, resumes/restarts,
   deaths, queue saturation, and daemon restarts.
2. Assert route isolation, one terminal outcome per attempt/session, no
   duplicate creation, completion/death ordering, level-triggered recovery,
   and single-writer store ordering.
3. Add deterministic boundary coverage for active/synthesis deadlines,
   proposal approval outside a sandbox, retention expiry, stale controls, and
   project-scoped reaping.
4. Produce an opt-in live Discord checklist covering two workflow channels,
   approval/revision/resume, visible budgets, task routing, and TUI state.

## Verification

- Run all Chatlink automated suites with fixed and printed randomized seeds.
- Confirm the full old single-repo bug path still passes.
- Hand off the live cases to the aggregate manual-verification sibling.

## Step 9 reference

Archive only after automated soak and the aggregate manual verification have
recorded their outcomes.
