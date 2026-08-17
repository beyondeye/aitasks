---
priority: medium
effort: medium
depends: [1536]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1536]
assigned_to: dario-e@beyond-eye.com
anchor: 1536
followup_kind: manual_verification
created_at: 2026-08-17 17:39
updated_at: 2026-08-17 18:37
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1536

## Verification Checklist

- [ ] Run a real /aitask-pick under a create_worktree:true profile (no shipped profile sets it, so the scripted acceptance run in t1536 never exercised the live pick path).
- [ ] Step 5 creates nothing: after the base-branch decision, confirm no aiwork/ directory and no aitask/<task_name> branch exist yet.
- [ ] Step 5 widget wording: the interactive base-branch question states, inside the widget itself, that the branch and worktree are cut after plan approval and the drift check — not in surrounding prose.
- [ ] Profile-driven display line: with base_branch set in the profile, the "using base branch <b>" line carries the same deferral sentence.
- [ ] Plan header at Step 6: the externalized plan records Worktree:, Base branch: and Output branch: while aiwork/<task_name> still does not exist on disk.
- [ ] Fork timing: the worktree appears only after the plan is approved AND the Remote Drift Check returns "Continue anyway" — not before.
- [ ] Drift stop leaves nothing: choose "Stop and re-verify plan" and confirm no worktree or aitask/ branch was created, then re-pick and confirm it cuts cleanly from the pulled base.
- [ ] Approve-and-stop leaves nothing: choose "Approve and stop here" and confirm the same, then re-pick without a "branch already exists" failure (the t1392 collision).
- [ ] Decomposed parent: let planning create child tasks and stop — confirm the parent stranded no worktree.
- [ ] Risk-mitigation "before" stop: confirm the worktree DOES exist on that path and that a re-pick reuses it rather than failing.
- [ ] Reuse after a move: git worktree move the task worktree elsewhere, resume, and confirm the agent works in the moved directory (not aiwork/<task_name>).
- [ ] Re-entry under a DIFFERENT profile: resume a worktree-mode task under fast and confirm the fork still runs (header-driven), then resume a current-branch task under a worktree profile and confirm no worktree appears.
- [ ] Re-entry ordering: on the IMPLEMENT route confirm the drift check runs BEFORE the fork.
- [ ] POSTIMPL resume: confirm no fork is attempted and Step 9 proceeds from the repo root.
- [ ] Legacy plan: strip Base branch: from a plan header, resume, and confirm the agent asks to confirm the base instead of silently using main — then confirm the branch is cut from the answer given.
- [ ] Abort before the fork: confirm the abort reports cleanly and removes nothing.
- [ ] Abort after a worktree move: confirm the abort names the surviving worktree path instead of reporting a clean abort.
- [ ] Crash recovery: interrupt a task between plan approval and the fork, re-pick, and confirm the survey reads "(none — current branch, or fork not reached)" rather than implying current-branch mode.
- [ ] Step 9 merge: complete a worktree-mode task end to end and confirm the merge and worktree cleanup still work.
