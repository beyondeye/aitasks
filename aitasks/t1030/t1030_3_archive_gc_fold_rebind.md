---
priority: medium
effort: medium
depends: [t1030_2]
issue_type: feature
status: Ready
labels: [task_attachments]
anchor: 1030
created_at: 2026-06-28 12:08
updated_at: 2026-06-28 12:08
---

Wire attachments into the **task lifecycle**: decref attachment hashes on archival, add an opt-in **`ait attach gc`** orphan sweep with a grace knob, and **re-bind attachments on fold**. Depends on the local backend + `index.json` from t1030_2.

Design spec: `aidocs/task_attachments_design.md` §8 (Archival / Garbage collection), §10 Q6 (fold semantics — attachments re-bind to the primary task), and the §8 open question on archive retention (keep + configurable grace).

## Context
Third and final child of t1030 (local-only v1). Closes the lifecycle so attachment blobs are reference-counted and never deleted out from under a live or archived task. Builds on t1030_2's `attachment_index.py` (incref/decref/zero-refcount/rebind) and the `attachment_backend_*` contract.

## Key Files to Modify / Create
- **`.aitask-scripts/aitask_archive.sh`**: add `handle_attachment_deref()` modeled on `handle_folded_tasks()` (~lines 275–369). Call it in `archive_parent()` (~before the metadata update at line 230) and `archive_child()` (~line 436). It reads the archived task's `attachments:` (via `read_yaml_mappings`), and for each hash calls `attachment_index.py decref <hash> <task_id>`. **Do NOT delete blobs on archive** (design §8: archives never delete synchronously — folded/superseded tasks may resurrect). Stage the modified `index.json` inside the existing commit block (lines 251–271 / child equivalent) so the decref travels with the archival commit.
- **`.aitask-scripts/aitask_attach.sh`**: implement `cmd_gc` (`ait attach gc`): enumerate `attachment_index.py zero-refcount`, confirm no live task in `aitasks/` references each candidate (belt-and-suspenders re-scan, not just the ledger), honor the **grace knob** (skip candidates whose last decref is more recent than `attachments_gc_grace`), then call `attachment_backend_delete <hash>` and drop the index entry. Print a summary of swept vs retained. **Opt-in only** — never invoked automatically by archive.
- **`.aitask-scripts/aitask_fold_mark.sh`**: at fold time, re-bind the folded task's attachment hashes to the primary task in `index.json` via `attachment_index.py rebind <folded_id> <primary_id>` (design §10 Q6: "they should re-bind to B at fold time"). Folded files are deleted during archival, so the re-bind MUST happen before deletion — do it at fold time here, and ensure `handle_folded_tasks()` deletion in `aitask_archive.sh` does not also try to decref the (already-deleted) folded task's attachments.
- **Grace-knob config**: add `attachments_gc_grace` (e.g. `30d`) — decide between `aitasks/metadata/project_config.yaml` (team-shared, table at the bottom of `task-workflow` SKILL.md) and the execution profile. Recommended: `project_config.yaml` (it is project policy, not per-workflow behavior). Document it wherever `verify_build`/`test_command` are documented. Parse `30d`/`24h` style values into seconds in a helper.
- **`tests/test_attach_archive_gc.sh`**, **`tests/test_attach_fold_rebind.sh`** (NEW).

## Reference Files for Patterns
- `.aitask-scripts/aitask_archive.sh` `handle_folded_tasks()` (~lines 275–369) — the read-list→iterate→per-item-action model, and the git staging block.
- `.aitask-scripts/aitask_fold_mark.sh` — fold marking flow (transitive folds, `children_to_implement` removal).
- `aidocs/task_attachments_design.md` §8–§10.
- t1030_2's `attachment_index.py` (`decref`, `zero-refcount`, `rebind`) and `attachment_backend.sh` (`delete`).
- `tests/lib/test_scaffold.sh`, `tests/lib/asserts.sh`.

## Implementation Plan
1. Add `handle_attachment_deref()` to `aitask_archive.sh` (parent + child paths); stage `index.json` in the existing commit.
2. Implement `cmd_gc` with the live-task re-scan + grace filter + `attachment_backend_delete`.
3. Add the grace-knob config + a `<duration> → seconds` parser.
4. Add fold re-bind to `aitask_fold_mark.sh`; reconcile with archival folded-task deletion so attachments are not double-handled.
5. Tests: (a) add attachment → archive task → refcount drops, blob retained; (b) decref to zero → `gc` sweeps it; a still-referenced hash is **retained**; grace window blocks a too-recent sweep; (c) fold A→B → A's hashes now ref B, survive A's deletion.

## Verification Steps
- `shellcheck` clean on modified scripts; tests run under resolved Python.
- `bash tests/test_attach_archive_gc.sh` and `bash tests/test_attach_fold_rebind.sh` — all PASS.
- Manual: add attachment to a fixture task, archive it (blob retained, refcount decremented), run `ait attach gc` (orphans swept, referenced blobs kept, grace respected); fold a task carrying an attachment and confirm re-bind.

## Notes for sibling tasks
- This completes t1030's local v1. The decref/gc/rebind operations on `index.json` are the lifecycle hooks t1076_1 must preserve when generalizing `index.json` → the artifact manifest (version-aware GC: a blob is GC-able only when no artifact *version* references it).
- Record in Final Implementation Notes: final home of `attachments_gc_grace`, the duration-parsing helper, and how fold-rebind vs archive-deletion ordering was resolved.
