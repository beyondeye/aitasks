---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [task_attachments]
created_at: 2026-06-30 19:07
updated_at: 2026-06-30 19:07
---

Rebind folded-origin attachment refs to the revived tasks when a primary task
that has `folded_tasks` is **hard-deleted** (the `ait board` delete unfolds them).

## Background

Fold (`aitask_fold_mark.sh`) merges each folded task's attachment entries INTO the
primary's frontmatter and **rebinds** their ledger refs to the primary
(`_fold_rebind_refs` → `attach_meta rebind <folded_id> <primary_id>`), without
stripping the folded files' frontmatter. The board's hard-delete of the primary
*revives* (unfolds) the folded tasks (status → Ready, `folded_into` cleared) but does
**not** restore their attachment ownership.

t1093 (decref-on-hard-delete) landed a **conservative guard**: `ait attach
decref-deleted --protect-task <folded_id>...` SKIPS decref'ing any primary hash a
revived folded task still lists, so no blob is orphaned out from under a revived task
(no data loss; the gc cross-check keeps it blocked). But this leaves a **stale ledger
ref**: the blob's ref still points at the now-deleted primary instead of the revived
folded task. When that revived task is later deleted, `decref-deleted` is a no-op for
it (its id was never in `refs`), so the stale primary ref persists forever → the exact
leak t1093 fixes, just deferred.

## Goal

On hard-delete of a primary with folded tasks, **move** each folded-origin attachment
ref from the primary back to the revived folded task that lists it (proper
rebind-on-unfold), instead of merely skipping it. Likely a new `ait attach` mode (or
an extension of `decref-deleted`) that, per revived folded task, for each of its
frontmatter hashes currently referenced by the primary, does `incref <hash>
<folded_id>` + `decref <hash> <primary_id>` under the attach lock, then stages/commits
the touched meta. Wire it into the board's `_do_delete` unfold path. Remove the interim
guard's stale-ref behavior once the rebind lands.

## Required tests

- **Primary-owned duplicate hash:** a hash the primary owns independently AND that also
  appears in a revived folded task → after delete the ref belongs to the revived task,
  not orphaned and not left on the deleted primary.
- **Multiple folded tasks sharing one hash:** two revived folded tasks both list the
  same blob → the ref is restored to the correct surviving referrer(s); blob retained.
- A revived folded task with a hash NOT referenced by the primary (defensive no-op).

## Reference

- t1093 plan: `aiplans/archived/p1093_*.md` (or `aiplans/p1093_*.md`) — the guard + the
  decision to split this out. Helper: `.aitask-scripts/aitask_attach.sh`
  (`decref-deleted`, `--protect-task`). Board: `_do_delete` /
  `_decref_doomed_attachments` in `.aitask-scripts/board/aitask_board.py`.
- Fold model: `aitask_fold_mark.sh` (`_fold_rebind_refs`, `_fold_transfer_attachments`).
- Ledger primitives: `.aitask-scripts/lib/attachment_meta.py` (`incref`/`decref`/`rebind`).

Spawned from t1093 (decref attachments on task hard-delete).
