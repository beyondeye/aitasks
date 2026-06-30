---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [task_attachments]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-30 17:39
updated_at: 2026-06-30 19:15
completed_at: 2026-06-30 19:15
---

Explicit task **hard-delete** does not decref the deleted task's attachments,
leaking orphaned blobs.

## Defect

`_do_delete` (`.aitask-scripts/board/aitask_board.py:6508`, reached via `ait
board` delete) `git rm`s a task's files and commits **without touching the
attachment ledger**. Any CLI task-delete path has the same gap. So a deleted
task's id stays **stale in the blob's `refs` set forever** → the blob is never
zero-refcount → `ait attach gc` never reclaims it (a permanent orphaned-blob
leak). A parent delete that cascade-deletes children has the same problem for
each child.

This is distinct from archival (which deliberately never decrefs, decision D4 —
an archived task is a real referrer) and from fold (which `rebind`s, transferring
the ref). Hard-delete is the third lifecycle case and is the only one where a
decref *should* fire. See `aidocs/attachment_metadata_bucketing.md` §2/§2a and
`aidocs/task_attachments_design.md` §8 ("Hard-delete").

## Fix shape

Before removing the task file(s), read each doomed task's `attachments:`
frontmatter hashes (including any cascade-deleted children); under
`with_attach_lock` (`.aitask-scripts/lib/attachment_lock.sh`), run `attach_meta
decref <hash> <task_id> now=<epoch>` for each (`.aitask-scripts/lib/attachment_meta.sh`),
stage the touched meta relpaths (`attach_meta_relpath <hash>`) into the same
delete commit. This is `ait attach rm` applied to all of a task's attachments at
once — an O(k) operation driven by the task's own frontmatter (k = attachments on
that task), no tree scan.

Prefer a **bash helper** the board shells out to (e.g. an `aitask_attach.sh`
subcommand or a small `lib` function) rather than re-implementing the ledger/lock
logic in Python — the board already shells out for archive/delete git ops, and the
attach lock + ledger primitives live in bash. This matches the
encapsulate-workflow-bash-in-a-helper convention.

## Tests

- Delete a task with an attachment → blob decref'd → `orphaned_at` stamped → `ait
  attach gc` reclaims it past grace.
- Shared blob (2 tasks reference it) → delete one task → blob retained (`refs`
  still lists the other).
- Parent delete cascades decref to each deleted child's attachments.

## Reference files

- `.aitask-scripts/board/aitask_board.py` — `_do_delete` (~:6508), `_execute_delete`
  (~:6496), `_collect_delete_files` (~:6318).
- `.aitask-scripts/lib/attachment_meta.sh`, `.aitask-scripts/lib/attachment_lock.sh`,
  `.aitask-scripts/lib/attachment_meta.py` (decref + `orphaned_at` semantics).
- `.aitask-scripts/aitask_attach.sh` (`rm` path, the existing decref call site ~:342).
- Tests precedent: `tests/test_attach_archive_gc.sh`, `tests/test_attach_local_backend.sh`.

Discovered during t1030_5 (bucketed-metadata evaluation).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T15:59:13Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-06-30T16:13:17Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-06-30T16:15:53Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:95e5a4e1e77d7f70

> **✅ gate:risk_evaluated** run=2026-06-30T16:15:53Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1093/risk_evaluated_2026-06-30T16:15:53Z-risk_evaluated-a1.log`
