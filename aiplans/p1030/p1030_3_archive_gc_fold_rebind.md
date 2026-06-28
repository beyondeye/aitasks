---
Task: t1030_3_archive_gc_fold_rebind.md
Parent Task: aitasks/t1030_task_attachments_support.md
Sibling Tasks: aitasks/t1030/t1030_1_frontmatter_cli_scaffold.md, aitasks/t1030/t1030_2_local_backend_cache_index.md
Archived Sibling Plans: aiplans/archived/p1030/p1030_1_*.md, aiplans/archived/p1030/p1030_2_*.md (read both first)
Worktree: aiwork/t1030_3_archive_gc_fold_rebind
Branch: aitask/t1030_3_archive_gc_fold_rebind
Base branch: main
---

# Plan — t1030_3 Archive decref + gc + fold re-bind

Close the attachment lifecycle: decref on archival, opt-in `ait attach gc` with
a grace knob, and re-bind attachments on fold. Builds on t1030_2's
`attachment_index.py` and `attachment_backend.sh`.

Design: `aidocs/task_attachments_design.md` §8 (archival / GC), §10 Q6 (fold).
Full spec in `aitasks/t1030/t1030_3_archive_gc_fold_rebind.md`.

**Before starting:** read t1030_2's archived plan + Final Notes for the
`index.json` schema and the `decref`/`zero-refcount`/`rebind` interface.

## Step 1 — Decref on archive (`aitask_archive.sh`)
- Add `handle_attachment_deref()` modeled on `handle_folded_tasks()`
  (~lines 275–369): read the archived task's `attachments:` via
  `read_yaml_mappings`, `attachment_index.py decref <hash> <task_id>` per hash.
- Call it in `archive_parent()` (~before the metadata update, line ~230) and
  `archive_child()` (~line 436).
- **Never delete blobs on archive** (design §8 — folded/superseded tasks can
  resurrect). Stage the modified `index.json` in the existing commit block
  (~lines 251–271 and child equivalent) so decref travels with the archival commit.

## Step 2 — `ait attach gc` (`aitask_attach.sh` cmd_gc)
- `attachment_index.py zero-refcount` → candidate hashes.
- Belt-and-suspenders: re-scan `aitasks/` (live tasks) to confirm no live
  reference before deleting (do not trust the ledger alone).
- **Grace knob**: skip candidates whose last decref is more recent than
  `attachments_gc_grace`. Add a `<duration> → seconds` parser (`30d`/`24h`).
- Delete via `attachment_backend_delete <hash>` + drop the index entry. Print
  swept-vs-retained summary. **Opt-in only** — archive never calls this.

## Step 3 — Fold re-bind (`aitask_fold_mark.sh`)
- At fold time, `attachment_index.py rebind <folded_id> <primary_id>` so the
  folded task's hashes re-bind to the primary (design §10 Q6). Folded files are
  deleted during archival, so re-bind MUST happen at fold time (here), before
  deletion.
- Reconcile with archival: ensure `handle_folded_tasks()` deletion does NOT also
  decref the (already re-bound / already-deleted) folded task's attachments —
  no double-handling. Document the ordering decision.

## Step 4 — Grace-knob config
- Add `attachments_gc_grace` (default `30d`) to
  `aitasks/metadata/project_config.yaml` (project policy, not per-workflow) and
  document it alongside `verify_build`/`test_command` (the project-config table
  in `task-workflow` SKILL.md).

## Step 5 — Tests
- `tests/test_attach_archive_gc.sh`: add attachment → archive → refcount drops,
  **blob retained**; decref-to-zero → `gc` sweeps it; a still-referenced hash is
  **retained**; grace window blocks a too-recent sweep.
- `tests/test_attach_fold_rebind.sh`: fold A→B → A's hashes ref B, survive A's
  deletion.

## Verification
- `shellcheck` clean; tests run under resolved Python.
- `bash tests/test_attach_archive_gc.sh` + `bash tests/test_attach_fold_rebind.sh` — PASS.
- Manual: add attachment, archive task (blob retained, refcount down), `gc`
  (orphans swept, referenced kept, grace respected); fold a task carrying an
  attachment → re-bind confirmed.

## Step 9 (Post-Implementation)
Standard per `task-workflow` Step 9. This is the **last child** — archival of the
final child should also archive the parent t1030 (Step 9 handles
`children_to_implement` emptying). Final Notes: record the `attachments_gc_grace`
home, the duration parser, and the fold-rebind vs archive-deletion ordering — and
flag for t1076_1 that version-aware GC must replace the simple refcount when
`index.json` becomes the artifact manifest.
