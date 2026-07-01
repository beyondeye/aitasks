---
priority: medium
effort: medium
depends: [1093]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1093]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-30 19:15
updated_at: 2026-07-01 12:17
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1093

## Verification Checklist

- [ ] In `ait board`: attach a file to a task, delete the task, then run `ait attach gc` past the grace window — confirm the blob + meta are reclaimed (no orphan leak).
- [ ] In `ait board`: attach files to a parent and its children, delete the parent — confirm the cascade decref releases every doomed task's attachments and `gc` then reclaims them.
- [ ] In `ait board`: with a shared blob referenced by a surviving task, delete one referencing task — confirm the blob is retained (other ref intact) and `gc` does not reclaim it.
- [ ] Force a decref-helper failure (e.g. busy attach lock or a failing pre-commit hook) during a board delete — confirm the task is NOT deleted (fail-closed) and the error notification appears.
- [ ] Delete a primary that has a folded task sharing an attachment hash — confirm the folded-origin blob is retained (SKIPPED, not orphaned) and the revived (unfolded) task still resolves its attachment.
- [ ] TODO: verify .aitask-scripts/board/aitask_board.py delete flow end-to-end in tmux.
