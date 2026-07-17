---
Task: t1157_6_remote_explore_advanced_parity.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_1_*.md … t1157_5_*.md, aitasks/t1157/t1157_7_*.md … t1157_9_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_6 — Advanced remote-explore parity

## Changes

1. Adapt native file selection to Discord with a query/path modal,
   read-only search, paginated candidates, explicit selection, and free-text
   fallback.
2. Discover eligible related standalone tasks in the routed project and carry
   selected ids in a proposal. Immediately before approval, revalidate status
   and scope; merge and fold only through gateway-owned helpers.
3. Detect registered project references and provision only requested
   committed snapshots. Carry target project and validated `xdeprepo`/`xdeps`
   intent into routed task creation without exposing credentials.
4. On stale selection, invalid path, unavailable project, or changed task
   status, return to proposal review without partial task/fold mutation.

## Verification

- Test paginated file selection and forged-path rejection.
- Test eligibility/status drift and atomic folding behavior.
- Test cross-project snapshot isolation, routing, refs, and target task
  creation while unchanged single-project core flow remains green.

## Step 9 reference

Record any cross-repo wire contract that later agent variants must preserve.
