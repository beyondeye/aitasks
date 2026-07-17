---
Task: t1157_4_bug_intake_budget_resume.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_1_*.md … t1157_3_*.md, aitasks/t1157/t1157_5_*.md … t1157_9_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_4 — Budget-aware resumable bug intake

## Changes

1. Migrate `aitask-explorechat` from a three-question prompt rule to an
   attempt budget contract. Export absolute active/synthesis deadlines, write a
   checkpoint after each meaningful round/answer, and cap every question wait
   to the remaining active window.
2. Render remaining time, response deadline, named timeout default, and
   soft-expiry behavior with each question. Use 20 active minutes plus a
   10-minute synthesis reserve by default; retain configuration overrides.
3. On soft expiry stop asking and synthesize; on hard expiry pause from the
   latest checkpoint. Replace final relay confirmation with a persisted
   unapproved proposal and terminate the sandbox.
4. Render initiator-only Approve, Request changes, Resume, Restart, and Abort
   actions. Approval has to be fresh and explicit; Request changes launches a
   15-minute revision attempt; seven-day expiry disables stale controls.
5. Preserve existing bug thread/reaction/audit semantics and gateway-side task
   validation.

## Verification

- Test more than three useful questions, clamped waits, soft/hard boundaries,
  no auto-create on timeout, delayed explicit approval, revision, resume,
  restart, expiry, and foreign/stale interaction rejection.
- Run relay, codeagent relay dispatch, daemon, and flow suites.

## Step 9 reference

Record exact user-facing timeout and proposal text for remote-explore reuse.
