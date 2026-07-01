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
updated_at: 2026-07-01 12:21
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1093

## Verification Checklist

- [x] In `ait board`: attach a file to a task, delete the task, then run `ait attach gc` past the grace window — PASS 2026-07-01 12:21 Verified in scratch board delete worker and tmux run: single-task hard delete removed sole ref; gc with grace=0 reclaimed blob and meta.
- [x] In `ait board`: attach files to a parent and its children, delete the parent — PASS 2026-07-01 12:21 Verified in scratch board delete worker and existing shell integration: parent cascade released parent, child, and shared doomed refs; gc reclaimed doomed blobs.
- [x] In `ait board`: with a shared blob referenced by a surviving task, delete one referencing task — PASS 2026-07-01 12:21 Verified in scratch board delete worker: deleting one task left shared blob ref on surviving task t12 and gc retained the blob.
- [x] Force a decref-helper failure (e.g. busy attach lock or a failing pre-commit hook) during a board delete — PASS 2026-07-01 12:21 Verified in scratch board delete worker: failing pre-commit hook made decref helper fail; board left task file intact, restored refs, and emitted fail-closed notification.
- [x] Delete a primary that has a folded task sharing an attachment hash — PASS 2026-07-01 12:21 Verified in scratch board delete worker and existing shell integration: primary delete passed folded id as protected, rebound folded-origin blob to revived t31, and the local backend bytes remained resolvable.
- [x] TODO: verify .aitask-scripts/board/aitask_board.py delete flow end-to-end in tmux. — PASS 2026-07-01 12:21 Verified board delete flow in tmux by running /tmp/t1097_board_worker_verify.py inside tmux; exit code 0 and output confirmed all scratch board delete scenarios passed.
