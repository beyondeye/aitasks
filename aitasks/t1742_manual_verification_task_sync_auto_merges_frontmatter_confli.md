---
priority: medium
effort: medium
depends: [1727]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1727]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-08 16:48
updated_at: 2026-09-08 16:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1727

## Verification Checklist

- [ ] Real two-machine convergence (the production scenario every automated test only simulates with local clones): on the second host, move a task's boardcol in `ait board` and push; on this host edit the same task's labels; then `/aitask-pick <id>` and confirm it reports SYNCED, the stderr notice names the merge, and BOTH fields survive in the task file.
- [ ] Same collision through a real task_push: claim a task on one host while the other has already pushed a conflicting frontmatter edit, and confirm the claim commit actually lands on the remote (check `git log` on the remote, not just the reported status).
- [ ] Interactive `ait sync` body-conflict path with a REAL $EDITOR in a terminal — exercises the two retargeted call sites (ait_automerge_conflict_path, ait_automerge_advance). tests/test_sync_branch_mode_automerge.sh Tests 5-8 drive these with a stub editor, never a real one.
- [ ] Confirm the new stderr notice ("auto-merged task-data conflict(s) during pull (N file(s)) - rebase completed") is legible in a live agent pane and does not disturb the pick skill's parsing of the SYNCED stdout token.
- [ ] Confirm per-file "Auto-merged: <f>" lines still appear in interactive `ait sync`, and are absent from `ait sync --batch` and from a pick-time sync (the AIT_AUTOMERGE_PROGRESS_FN split).
- [ ] TODO: verify .aitask-scripts/lib/task_utils.sh end-to-end in tmux (diff-scan interactive-surface match).
