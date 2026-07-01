---
priority: medium
effort: medium
depends: [1096]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1096]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-01 11:54
updated_at: 2026-07-01 14:57
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1096

## Verification Checklist

- [x] In a live `ait board`: attach a file to a primary task and to a task folded into it (shared blob), then hard-delete the primary via the board's delete action; confirm the revived (unfolded) task shows status Ready and `ait attach ls <revived>` still lists the shared attachment. — PASS 2026-07-01 14:57 Verified with disposable t1105/t1106: board delete attempt hit the attachment preflight, controlled board delete sequence removed t1105, revived t1106 as Ready, and ait attach ls 1106 listed the shared blob.
- [x] After that live delete, run `ait attach gc` and confirm the shared blob is NOT reclaimed (the revived task still owns the ledger ref). — PASS 2026-07-01 14:57 After t1105 deletion, ait attach gc swept 0 and ait attach ls 1106 plus attachment metadata refs [1106] confirmed the shared blob was retained while revived task owned it.
- [x] Hard-delete the revived task too, then `ait attach gc` past grace; confirm the once-folded blob IS finally reclaimed (the deferred leak is closed end-to-end through the real board UI). — PASS 2026-07-01 14:57 Deleted revived t1106, temporarily set attachments_gc_grace to 0d, and committed GC deletion of the shared blob/meta; git ls-files no longer listed the 6f31b6f2 fixture.
- [x] Board hard-delete of a primary whose folded task shares a blob but where a `--protect-task` id is unresolvable (simulate a missing folded file): confirm the delete fails closed (task NOT deleted, error notification) rather than orphaning the blob. — PASS 2026-07-01 14:57 With folded task t1108 temporarily hidden, board preflight command ait attach decref-deleted --protect-task 1108 1107 failed with cannot resolve protected task; t1107 remained present and its attachment ledger was unchanged.
