---
priority: medium
effort: medium
depends: [t1030_2]
issue_type: feature
status: Implementing
labels: [task_attachments]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1030
implemented_with: claudecode/opus4_8
created_at: 2026-06-28 12:08
updated_at: 2026-06-30 09:24
---

Wire attachments into the **task lifecycle**: decref attachment hashes on archival, add an opt-in **`ait attach gc`** orphan sweep with a grace knob, and **re-bind attachments on fold**. Depends on the per-blob metadata ledger + local backend from t1030_2.

> **Design update — read first (t1030_2 landed, 2026-06-29).** The refcount ledger
> is **per-attachment metadata files** (`attachments/meta/<2>/<62>.json`), **not** a
> single global `index.json`; blobs live at `attachments/blobs/<2>/<62>`. The helper
> is **`lib/attachment_meta.py`** (a **lock-free** primitive), invoked as
> `attachment_meta.py --meta-dir <attachments/meta> <incref|decref|refs|zero-refcount|rebind>`.
> **All metadata MUTATIONS must run under the single global `attachments/.attach.lock`**
> (acquire via `with_attach_lock` from `lib/attachment_lock.sh`) — a per-blob lock
> would not exclude an in-flight `add`/`rm` transaction. `zero-refcount` is an
> **advisory** scan: before deleting any blob, `gc` MUST re-acquire the global lock
> and re-read `refs` to confirm it is still empty. References below to
> `attachment_index.py` / `index.json` mean this per-blob model. See the t1030_2
> plan `aiplans/p1030/p1030_2_local_backend_cache_index.md`.

Design spec: `aidocs/task_attachments_design.md` §8 (Archival / Garbage collection), §10 Q6 (fold semantics — attachments re-bind to the primary task), and the §8 open question on archive retention (keep + configurable grace).

## Context
Third and final child of t1030 (local-only v1). Closes the lifecycle so attachment blobs are reference-counted and never deleted out from under a live or archived task. Builds on t1030_2's `attachment_meta.py` (incref/decref/refs/zero-refcount/rebind, per-blob meta files), the global `.attach.lock` transaction (`with_attach_lock`), and the `attachment_backend_*` contract.

## Key Files to Modify / Create
- **`.aitask-scripts/aitask_archive.sh`**: add `handle_attachment_deref()` modeled on `handle_folded_tasks()` (~lines 275–369). Call it in `archive_parent()` (~before the metadata update at line 230) and `archive_child()` (~line 436). It reads the archived task's `attachments:` (via `read_yaml_mappings`), and for each hash calls `attachment_meta.py --meta-dir <attachments/meta> decref <hash> <task_id>` **under the global `.attach.lock`** (`with_attach_lock`). **Do NOT delete blobs on archive** (design §8: archives never delete synchronously — folded/superseded tasks may resurrect). Stage each modified **per-blob meta file** (`attachments/meta/<2>/<62>.json`) inside the existing commit block (lines 251–271 / child equivalent) so the decref travels with the archival commit.
- **`.aitask-scripts/aitask_attach.sh`**: implement `cmd_gc` (`ait attach gc`) **under `with_attach_lock`**: enumerate `attachment_meta.py … zero-refcount` (advisory), then for each candidate **re-read `refs` under the held lock** to confirm still-empty, confirm no live task in `aitasks/` references it (belt-and-suspenders re-scan), honor the **grace knob** (skip candidates whose last decref is more recent than `attachments_gc_grace`), then call `attachment_backend_delete <hash>` and remove the blob's **meta file**. Print a summary of swept vs retained. **Opt-in only** — never invoked automatically by archive.
- **`.aitask-scripts/aitask_fold_mark.sh`**: at fold time, re-bind the folded task's attachment hashes to the primary task via `attachment_meta.py --meta-dir <attachments/meta> rebind <folded_id> <primary_id>` **under `.attach.lock`** (scans every per-blob meta file's `refs`; design §10 Q6: "they should re-bind to B at fold time"). Folded files are deleted during archival, so the re-bind MUST happen before deletion — do it at fold time here, and ensure `handle_folded_tasks()` deletion in `aitask_archive.sh` does not also try to decref the (already-deleted) folded task's attachments. Stage the touched meta files in the fold commit.
- **Grace-knob config**: add `attachments_gc_grace` (e.g. `30d`) — decide between `aitasks/metadata/project_config.yaml` (team-shared, table at the bottom of `task-workflow` SKILL.md) and the execution profile. Recommended: `project_config.yaml` (it is project policy, not per-workflow behavior). Document it wherever `verify_build`/`test_command` are documented. Parse `30d`/`24h` style values into seconds in a helper.
- **`tests/test_attach_archive_gc.sh`**, **`tests/test_attach_fold_rebind.sh`** (NEW).

## Reference Files for Patterns
- `.aitask-scripts/aitask_archive.sh` `handle_folded_tasks()` (~lines 275–369) — the read-list→iterate→per-item-action model, and the git staging block.
- `.aitask-scripts/aitask_fold_mark.sh` — fold marking flow (transitive folds, `children_to_implement` removal).
- `aidocs/task_attachments_design.md` §8–§10.
- t1030_2's `lib/attachment_meta.py` (`decref`, `zero-refcount`, `rebind`; `--meta-dir`), `lib/attachment_lock.sh` (`with_attach_lock`), and `attachment_backend.sh` (`delete`).
- `tests/lib/test_scaffold.sh`, `tests/lib/asserts.sh`.

## Implementation Plan
1. Add `handle_attachment_deref()` to `aitask_archive.sh` (parent + child paths); under `with_attach_lock`, decref each hash and stage the touched per-blob meta files in the existing commit.
2. Implement `cmd_gc` with the live-task re-scan + grace filter + `attachment_backend_delete`.
3. Add the grace-knob config + a `<duration> → seconds` parser.
4. Add fold re-bind to `aitask_fold_mark.sh`; reconcile with archival folded-task deletion so attachments are not double-handled.
5. Tests: (a) add attachment → archive task → refcount drops, blob retained; (b) decref to zero → `gc` sweeps it; a still-referenced hash is **retained**; grace window blocks a too-recent sweep; (c) fold A→B → A's hashes now ref B, survive A's deletion.

## Verification Steps
- `shellcheck` clean on modified scripts; tests run under resolved Python.
- `bash tests/test_attach_archive_gc.sh` and `bash tests/test_attach_fold_rebind.sh` — all PASS.
- Manual: add attachment to a fixture task, archive it (blob retained, refcount decremented), run `ait attach gc` (orphans swept, referenced blobs kept, grace respected); fold a task carrying an attachment and confirm re-bind.

## Notes for sibling tasks
- This completes t1030's local v1. The decref/gc/rebind operations on the **per-blob meta files** are the lifecycle hooks t1076_1 must preserve when generalizing the per-blob ledger → the artifact manifest (version-aware GC: a blob is GC-able only when no artifact *version* references it). Per-blob meta files are already close to the per-artifact manifest shape.
- Record in Final Implementation Notes: final home of `attachments_gc_grace`, the duration-parsing helper, and how fold-rebind vs archive-deletion ordering was resolved.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T06:24:36Z status=pass attempt=1 type=human
