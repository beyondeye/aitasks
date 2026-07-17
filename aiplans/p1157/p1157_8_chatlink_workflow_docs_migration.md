---
Task: t1157_8_chatlink_workflow_docs_migration.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_1_*.md … t1157_7_*.md, aitasks/t1157/t1157_9_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_8 — Chatlink workflow documentation and migration

## Changes

1. Derive docs from all landed child implementation records, not prior plan
   wording.
2. Update bug-intake documentation for visible budgets, no auto-create,
   proposal/approval, revision, resume/restart, and expiry.
3. Add remote-explore and multi-workflow setup documentation covering layered
   configuration, one bot across guilds/projects, workflow channel triggers,
   and migration from legacy singleton config.
4. Update maintainer runtime/protocol/sandbox docs with session-vs-attempt,
   cleanup/retention, and gateway validation contracts. Explain Discord-first,
   sandbox read-only, and no implementation handoff boundaries.
5. Add focused troubleshooting for routing/configuration/stale-control cases
   and retain documented manual fallback where implementation supports it.

## Verification

- Run the website build and link checks.
- Verify examples match code/config and contain no secret values.

## Step 9 reference

Record any doc-only follow-up found during verification.
