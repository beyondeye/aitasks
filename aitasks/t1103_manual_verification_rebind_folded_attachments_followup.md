---
priority: medium
effort: medium
depends: [1096]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1096]
created_at: 2026-07-01 11:54
updated_at: 2026-07-01 11:54
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1096

## Verification Checklist

- [ ] In a live `ait board`: attach a file to a primary task and to a task folded into it (shared blob), then hard-delete the primary via the board's delete action; confirm the revived (unfolded) task shows status Ready and `ait attach ls <revived>` still lists the shared attachment.
- [ ] After that live delete, run `ait attach gc` and confirm the shared blob is NOT reclaimed (the revived task still owns the ledger ref).
- [ ] Hard-delete the revived task too, then `ait attach gc` past grace; confirm the once-folded blob IS finally reclaimed (the deferred leak is closed end-to-end through the real board UI).
- [ ] Board hard-delete of a primary whose folded task shares a blob but where a `--protect-task` id is unresolvable (simulate a missing folded file): confirm the delete fails closed (task NOT deleted, error notification) rather than orphaning the blob.
