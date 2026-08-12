---
priority: medium
effort: medium
depends: [1485]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1485]
anchor: 1171
followup_kind: manual_verification
created_at: 2026-08-12 15:37
updated_at: 2026-08-12 15:37
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1485

## Verification Checklist

- [ ] Run `ait brainstorm archive <N>` against a REAL brainstorm session (one with actual proposal nodes and a live crew worktree, not the init-only test fixture): confirm the PLAN:<path> line names the real HEAD node, the exported proposal actually lands in aiplans/, ARCHIVED:<N> prints, and the crew worktree is cleaned up
- [ ] Force a real finalize failure on a live session — e.g. a fast-tracked module still in implementation and unsynced, which raises the "Cannot finalize: module(s) ... not synced" ValueError — and confirm the archive aborts with "Failed to finalize session", emits no ARCHIVED: and no PLAN:, and leaves both the session status and the crew worktree untouched
- [ ] Confirm the reworded --help / header output of `ait brainstorm archive --help` reads correctly ("exports HEAD node's proposal", "Proposal exported to aiplans/") and matches what the command actually does
- [ ] TODO: verify .aitask-scripts/aitask_brainstorm_archive.sh end-to-end in tmux
