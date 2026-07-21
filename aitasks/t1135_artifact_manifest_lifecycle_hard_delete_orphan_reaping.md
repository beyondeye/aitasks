---
priority: low
effort: medium
depends: [t1076_2]
issue_type: feature
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-06 18:30
updated_at: 2026-07-06 18:30
boardidx: 220
---

**Design spec:** `aidocs/unified_artifact_design.md` §9 (lifecycle).

## Context

t1076_2 shipped a fail-closed guard in `ait attach decref-deleted`
(`.aitask-scripts/aitask_attach.sh::_attach_decref_deleted_txn`): a board
hard-delete of a task that still lists `artifacts:` entries ABORTS (die) unless
every handle is also listed by a `--protect-task` revived survivor. That guard
prevents silently stranding manifests, but pushes the work onto the user
("remove artifacts first"). This task replaces the guard with real handling.

## Key work

1. **Manifest lifecycle on hard-delete** — a decref-deleted analog for
   artifacts: when a doomed task is the last referrer of a handle, delete the
   manifest (and sweep orphan blobs with the same guards as
   `ait artifact rm`: keep blobs owned by the attachment meta ledger or
   referenced by any remaining manifest); when a `--protect-task` revived
   survivor lists the handle, ownership transfers (frontmatter already lists it
   — nothing to move; just don't delete the manifest). Then relax/remove the
   t1076_2 guard.
2. **Orphaned-manifest reaper** — a manifest no task file (active, archived, or
   Folded) references is unreachable via `ait artifact rm <task> <handle>`
   (rm is task-scoped). Reachable states: fold-then-archive (folded file deleted
   at archival after the primary rm'd its entry), historical bugs. Add a reap
   verb (e.g. `ait artifact gc` or an `rm --orphaned <handle>` escape hatch)
   that lists/removes such manifests, with the same blob-sweep guards.

## Reference files

- `.aitask-scripts/aitask_artifact.sh` — `_artifact_rm_txn` (the guards to
  reuse), `_artifact_handle_referenced_elsewhere` (the reference scan).
- `.aitask-scripts/aitask_attach.sh` — `cmd_decref_deleted` /
  `_attach_decref_deleted_txn` (the guard to replace; the rebind pattern).
- `.aitask-scripts/board/aitask_board.py` — `_decref_doomed_attachments`
  (fail-closed board call site).
- `tests/test_artifact_cli.sh` — decref-deleted guard cases to update.

## Verification

- Hard-delete of an artifact-bearing task cleans its manifests (or transfers to
  revived survivors) without user pre-work; blobs shared with attachments or
  other manifests survive (negative controls).
- The reaper finds and removes an orphaned manifest; a referenced manifest is
  never reaped (negative control).
