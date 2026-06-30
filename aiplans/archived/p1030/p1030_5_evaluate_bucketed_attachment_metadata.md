---
Task: t1030_5_evaluate_bucketed_attachment_metadata.md
Parent Task: aitasks/t1030_task_attachments_support.md
Archived Sibling Plans: aiplans/archived/p1030/p1030_1_frontmatter_cli_scaffold.md, aiplans/archived/p1030/p1030_2_local_backend_cache_index.md, aiplans/archived/p1030/p1030_3_archive_gc_fold_rebind.md, aiplans/archived/p1030/p1030_4_manual_verification_auto.md
Base branch: main
plan_verified: []
---

# Plan — t1030_5 Evaluate bucketed attachment metadata

## Context

This is the last child of **t1030** (framework-managed file attachments). Its
siblings already shipped and verified a storage model:

- **t1030_2** built the storage core with the **canonical refcount ledger as one
  metadata file per blob** at `attachments/meta/<2>/<62>.json` (`attachment_meta.py`),
  explicitly *replacing* a single global `index.json`. The rationale was
  concurrency: a single index is a global write-hotspot that manufactures merge
  conflicts between *unrelated* attachments on the shared `.aitask-data` branch.
- **t1030_3** added retention-safe GC + fold re-bind over that per-blob ledger
  (whole-tree scans of `meta/**.json`; archiving never decrefs).

t1030_5 asks the deferred design question the user flagged at the time: should the
ledger move from one-file-per-blob to deterministic **hash-prefix bucket** files
(e.g. `meta/ab.json` for all hashes starting `ab`) to avoid many small Git-tracked
files at scale? The deliverable is a **design note** comparing single-global-index
vs per-blob vs hash-prefix-buckets, answering the 8 design questions in the task,
and giving a recommendation for t1030's direction. **No code changes.**

The decision is also constrained by **t1065/t1076** (`unified_artifact_design.md`):
the artifact **manifest** (`art:<id> → current/versions/backend`, §4b) generalizes
t1030's ledger into *per-artifact records keyed by a stable handle*. Both shipped
sibling plans note that per-blob meta files are *closer* to that manifest shape
than a global index — so the storage layer is heading toward **finer** per-record
granularity, not coarser buckets.

## Current refcount lifecycle (verified, load-bearing for the bucket analysis)

A blob's `refs` set shrinks in **exactly one case: `ait attach rm <task>
<attachment>`** (the only `decref` call site, `aitask_attach.sh:342`). The only
scripts that touch the ledger are `aitask_attach.sh` (incref on add / decref on
rm) and `aitask_fold_mark.sh` (rebind on fold). Therefore:

- **Archiving never decrefs** (D4) — an archived task stays a referrer.
- **Fold rebinds, not decrefs** (`aitask_fold_mark.sh:442`) — A's ref transfers to
  the primary B; count preserved, just reassigned.
- **Hard-delete (e.g. `ait board` delete) has NO decref hook — a confirmed leak.**
  `_do_delete` (`aitask_board.py:6508`) `git rm`s the task + plan files and commits
  without touching the ledger, so a deleted task's id stays **stale in the blob's
  `refs` forever** → the blob is never zero-refcount → GC never reclaims it. Same
  for parent delete (cascade-deletes children, none decref). This is a real
  **upstream defect** (user-confirmed) → a follow-up task is spawned (see below).
  The *intended* behavior: hard-delete should decref each of the task's
  attachments.

This corrects the task-keyed bucket proposal's premise: archive does nothing to
the ledger, `rm` edits one entry, and **hard-delete decref is cleanly O(k) under
per-blob** — read the doomed task's `attachments:` frontmatter (the authoritative
hash list) and `decref <hash> <task_id>` each under the global lock, no tree scan.
So the *only* lifecycle op a task-keyed layout could even theoretically speed up is
**fold-rebind**, and that single narrow win is undercut by the shared-blob problem
(reason 0).

## Recommendation (the design note's conclusion)

**Keep per-attachment metadata. Do NOT switch to buckets now — neither
hash-prefix nor task-keyed. Document hash-prefix buckets as a deferred,
mechanical future migration gated on an explicit file-count threshold, and only
after reconciling with the t1076 manifest model.** Load-bearing reasons:

0. **Task-keyed buckets (one file per introducing task) are feasible but
   regressive.** Refcount is inherently a *per-blob* set (`refs:[42,7]`) because
   blobs are content-addressed and **shared** (dedup); keying by task means "is
   blob X still referenced?" becomes an O(tasks) scan across all task buckets —
   moving cost onto the *hot* `refs <hash>` lookup (today an O(1) file read). It
   also **duplicates the per-task binding already held in frontmatter** and
   denormalizes blob-intrinsics across every referencing task (the current design
   stores them once, `die`s on mismatch). The lifecycle-match appeal collapses for
   shared blobs (deleting task 42's bucket must not delete a blob task 7 refs →
   cross-bucket scan again). The user's instinct — match metadata to lifecycle —
   is *already* satisfied: per-task data in the per-task file (frontmatter), shared
   data in the per-blob file; task-keying breaks that correct split.
0b. **Constant-size / insertion-order buckets are strictly worse**, not simpler:
   non-deterministic placement needs a hash→bucket lookup table = the global index
   we removed. Only hash-prefix buckets keep O(1) deterministic lookup.

1. **Buckets undo the exact win per-blob files were chosen for.** Any two blobs
   sharing the bucket prefix would co-locate in one file → the global
   write-hotspot / unrelated-conflict problem returns on a branch that *has*
   concurrent writers (syncer + parallel sessions). With 2-hex buckets (256
   files) birthday collisions start early; the conflict-isolation regression is
   immediate.
2. **Locking buys nothing today.** The shipped model serializes *all* mutations
   on one global `attachments/.attach.lock`; `attachment_meta.py` is the lock-free
   primitive. Per-bucket locking would only matter under a finer-grained lock
   scheme the design explicitly deferred — and it cross-races the global
   transaction. (Answers Q4.)
3. **GC/rebind cost is unchanged.** `zero-refcount`/`rebind` whole-tree-scan
   `meta/**.json` (O(attachments)). Buckets reduce *file count* but parse the same
   total bytes; a bucket merge has the same rollback complexity with a *worse*
   blast radius (one corrupt/conflicted bucket file affects many logical
   attachments). (Answers Q5.)
4. **Per-blob is the convergent shape for t1076.** The unified-artifact manifest
   is per-artifact-handle records with versions. Bucketing now creates churn that
   t1076_1 would have to undo/re-key. (Answers Q8 direction.)

Git comfortably handles thousands of small files (the repo already tracks
hundreds of task/plan files); per-blob diffs are small and conflict-isolated — a
feature, not a defect (Q3). The realistic v1/v2 scale (screenshots/small
artifacts per task; dozens–low-hundreds per project) sits far below any threshold
where file count matters, and the 2-hex shard already caps any directory at a few
thousand entries.

## Deliverable (user-chosen: dedicated aidocs note + cross-ref)

### File 1 (NEW) — `aidocs/attachment_metadata_bucketing.md`

RFC-style note matching the existing aidocs design-doc style. Sections:

- **Status / scope** — design evaluation, no implementation, creates no tasks
  (mirrors the headers of `task_attachments_design.md` / `unified_artifact_design.md`).
- **Current state** — the shipped per-blob ledger (cite
  `attachment_meta.py`, `attachments/meta/<2>/<62>.json`, the global `.attach.lock`,
  no `index.json`); state refs as the source of truth and that per-task display
  fields stay authoritative in task frontmatter.
- **Refcount lifecycle (when does `refs` change?)** — the verified facts above:
  decref only on `ait attach rm`; archive never decrefs (D4); fold rebinds.
  **Document the intended hard-delete behavior (decref each of the task's
  attachments) and flag the current gap** (`aitask_board.py:6508` `_do_delete`
  leaks refs) with a pointer to the follow-up task. Show the clean per-blob fix
  (O(k) decref via the doomed task's frontmatter). Frame *why this matters* for the
  bucket question.
- **Four layouts compared** — table over *single global index* / *per-blob
  (shipped)* / *hash-prefix buckets* / *task-keyed buckets* (with a note on
  constant-size) across: concurrency/conflict isolation, diff readability, refcount
  lookup cost (`refs <hash>`), GC scan cost, file count, lock granularity, rollback
  blast radius, dedup/shared-blob fit, t1076 manifest fit.
- **The frontmatter-is-already-a-per-task-bucket insight** — each task's
  `attachments:` list already holds the per-task binding (`name`, `added_at`,
  `hash`); the `meta/` files exist *only* for the shared cross-task facts (`refs`
  + blob-intrinsics). This is the structural reason task-keying the ledger fights
  its purpose. (Directly addresses the user's task-bucket proposal.)
- **No semantic/name-based bucketing** — restate and justify (names are mutable,
  collidable, per-task display fields; the lifecycle ledger must not depend on
  them). (Answers the AC + seed analysis.)
- **The 8 design questions, answered** — one short subsection each:
  1. Per-blob is sufficient for v1/v2 scale; buckets not planned now.
  2. Threshold that would justify buckets: a single 2-hex shard dir exceeding
     ~5,000 `meta` files (≈>1.3M total attachments) **and** a generated aggregate
     index proving insufficient — i.e. effectively never at task-attachment scale.
  3. If buckets were ever chosen, **hash-prefix** is the only viable scheme:
     configurable `attachment_meta_bucket_width` (0 = per-blob [default], 2, 4),
     2-hex first, not adaptive (determinism > cleverness). **Task-keyed and
     constant-size schemes are rejected here** — task-keyed breaks the shared
     refcount (reason 0); constant-size needs a lookup index (reason 0b).
  4. Bucket locking: not needed under the current single-global-lock model; any
     per-bucket scheme (hash- or task-keyed) reintroduces cross-race with the
     global transaction — rejected for v1.
  5. add/rm/rebind/zero-refcount/GC under buckets: hash-prefix = RMW the whole
     bucket file under the global lock (same scan cost, worse rollback blast
     radius); **task-keyed makes `refs <hash>` and GC O(tasks) scans** and only
     speeds fold-rebind — net negative given the verified lifecycle (archive/rm
     get no benefit). Per-blob keeps `refs <hash>` O(1).
  6. Rollback + explicit Git staging for bucket files: same preimage/HEAD-restore
     + explicit-path staging as today, but a bucket touches multiple attachments
     so a failed commit reverts unrelated entries together (regression vs per-blob).
  7. Aggregate index stays **explicitly non-canonical, generated-only** — the
     right escape hatch for fast counts/reports without bucketing the canonical
     ledger (consistent with t1030_2 design §4/§10 Q4).
  8. **Migration path (deferred, hash-prefix only):** mechanical and reversible.
     Under the global `.attach.lock`, read every `meta/<2>/<62>.json`, group by
     chosen prefix width, write `meta/<prefix>.json` bucket files, single commit;
     blobs and `refs`-as-source-of-truth are untouched (only the `meta/` subtree
     changes). Inverse rebuild restores per-blob. Task-keyed is **not** a migration
     target (reason 0). **Precondition:** reconcile with the t1076 manifest first
     so we don't bucket then re-key by artifact handle.
- **Recommendation** — the reasons above (incl. the task-keyed and constant-size
  analyses); "keep per-blob, defer hash-prefix buckets, generated aggregate index
  is the pressure valve."
- **Cross-references** — `task_attachments_design.md`, `unified_artifact_design.md`
  (§4b manifest), `gitremoteproviderintegration.md` (dispatcher pattern home).

### File 2 (EDIT) — `aidocs/task_attachments_design.md` §10 Q4 + §8

- **§10 Q4 ("Ledger format")** already records "one JSON file per blob … Any future
  aggregate index would be a generated cache only." Append one sentence recording
  the **resolved bucketing decision** + pointer:
  `Bucketed (hash-prefix) metadata was evaluated (t1030_5) and **deferred** — it
  reintroduces the write-hotspot per-blob files removed and fights the t1076
  per-artifact manifest direction; see` `attachment_metadata_bucketing.md`.
  Per the documentation current-state-only rule, this stays a one-line resolved
  note, not a history dump. (Canonical architecture is unchanged — the
  recommendation keeps per-blob — so this is a cross-ref, not a rewrite.)
- **§8 (Lifecycle)** currently covers add/fetch/archival/GC but not explicit
  hard-delete. Add one sentence: an explicit task **hard-delete** (e.g. `ait board`)
  *should* decref each of the task's attachments; the current board path does not
  (a known gap, tracked separately) — so a hard-deleted task's blobs currently stay
  pinned until that lands. Keeps §8 honest about the third lifecycle case without
  over-detailing.

### File 3 (NEW TASK, post-approval) — decref-on-hard-delete follow-up

Create a standalone `bug` task (via the Batch Task Creation Procedure) capturing
the confirmed defect, so it survives t1030's archival. Description to include:
- **Defect:** `_do_delete` (`aitask_board.py:6508`) and any CLI task-delete path
  `git rm` task files without decref'ing their attachments → permanent orphaned-blob
  leak (GC never sees them as zero-refcount).
- **Fix shape:** before removing the task file(s), read each doomed task's
  `attachments:` frontmatter hashes (incl. cascade-deleted children); under
  `with_attach_lock` (`lib/attachment_lock.sh`), `attach_meta decref <hash>
  <task_id> now=<epoch>` each (`lib/attachment_meta.sh`), stage the touched meta
  relpaths (`attach_meta_relpath`) into the same delete commit. Prefer a **bash
  helper** the board shells out to (matches the encapsulate-bash-in-helper
  convention) rather than re-implementing ledger/lock logic in Python.
- **Tests:** delete a task with an attachment → blob decref'd → `orphaned_at`
  stamped → GC reclaims past grace; shared blob (2 tasks) → delete one → retained;
  parent delete cascades decref to children.
- Also **record it in this task's Final Notes "Upstream defects identified"** bullet
  (`aitask_board.py:6508 _do_delete — hard-delete leaks attachment refs`) so the
  Step 8b upstream-defect channel is consistent.

### File 4 (NEW TASK, post-approval) — bucket-migration tracking task

Create a standalone `enhancement` task (Batch Task Creation Procedure), **status
`Postponed`, priority/effort low/low**, so it stays off the active board but
tracked and revivable. Purpose: track the deferred migration to hash-prefix bucket
metadata. Description to include:
- **Reference** `aidocs/attachment_metadata_bucketing.md` as the design of record
  (the layout, schema, migration steps, and rejected task-keyed/constant-size
  alternatives live there — do not re-derive).
- **Two activation triggers** (both must hold; this is *not* a simple dependency
  edge, hence Postponed): (1) the file-count threshold — a single 2-hex `meta`
  shard dir exceeding ~5,000 files (≈>1.3M attachments) *and* a generated aggregate
  index proven insufficient; (2) the **t1076 manifest reconciliation precondition**
  — buckets must be settled against the per-artifact manifest model first, to avoid
  bucketing then re-keying by artifact handle.
- **Scope when revived:** the hash-prefix migration only (`attachment_meta_bucket_width`
  config, `meta/<prefix>.json` RMW under `with_attach_lock`, reversible rebuild),
  per the design note.

## Out of scope

- No change to `attachment_meta.py`, `aitask_attach.sh`, the lock, or any test.
- No new config key is *added* (`attachment_meta_bucket_width` is named in the
  note only as the *shape a future migration would take*, not introduced now).
- The website docs are untouched (this is internal design/aidocs).

## Risk

### Code-health risk: low
- Documentation-only change; two markdown files, no code, no behavior. New aidocs
  note is isolated; the design-doc edit is a one-line cross-ref in an existing
  open-questions section · severity: low · → mitigation: none needed.
- Stale-doc / drift risk: the note could contradict the shipped source if it
  misstates the model · severity: low · → mitigation: every claim about current
  behavior is sourced from the read files (`attachment_meta.py`, the two archived
  sibling plans, design §4/§8/§10) — verified during planning, re-checked at write.

### Goal-achievement risk: low
- The note must actually answer all 8 task questions and honor the AC (no
  name-based grouping; refs source of truth; Git many-small-files vs bucket
  contention; GC/rebind stale-decision avoidance; sync with the design doc) ·
  severity: low · → mitigation: the deliverable outline maps one subsection per
  question + an explicit "no semantic bucketing" section; AC checklist verified at
  Step 8.

**Planned mitigations:** None — both dimensions are low and mitigated in-task
(source-verified claims, question-by-question coverage). No before/after follow-up
tasks warranted.

## Verification

- `grep -n '^## ' aidocs/attachment_metadata_bucketing.md` — confirms all expected
  sections incl. the 8-question block and the recommendation.
- Re-read the AC list in the task file and tick each against the note:
  no semantic grouping ✓, refs = source of truth ✓, Git small-files-vs-bucket
  trade-off ✓, GC/rebind stale-decision avoidance ✓, design-doc sync ✓.
- `grep -n 'attachment_metadata_bucketing' aidocs/task_attachments_design.md` —
  confirms the cross-ref landed in §10 Q4; `grep -n 'hard-delete' aidocs/task_attachments_design.md`
  confirms the §8 lifecycle sentence.
- Follow-up tasks: confirm `aitask_create.sh` printed a new task id for **both**
  the decref-on-hard-delete **bug** (File 3) and the bucket-migration
  **enhancement** (File 4, `status: Postponed`), and that each file exists with the
  expected description + design-note reference.
- Markdown sanity: links resolve (relative paths to sibling aidocs).

## Step 9 (Post-Implementation)

Standard per `task-workflow` Step 9. **t1030_5 is the only entry in the parent's
`children_to_implement: [t1030_5]`**, so archiving this child **will auto-archive
the parent t1030** (archival fires when `children_to_implement` empties). Final
Notes must record: the recommendation (keep per-blob, defer buckets), the deferred
bucket-migration shape + its t1076 precondition, the two doc files produced, the
**hard-delete decref defect** under "Upstream defects identified"
(`aitask_board.py:6508 _do_delete`), and the **two follow-up task ids** created
(the decref-on-hard-delete bug + the Postponed bucket-migration tracking task).
Doc-only task (no code changes here): no `verify_build`; the `risk_evaluated` gate
is the only declared gate.

## Final Implementation Notes

- **Actual work done:** Produced the design-evaluation deliverable for t1030_5 —
  no code changes.
  - NEW `aidocs/attachment_metadata_bucketing.md`: RFC-style note with the shipped
    per-blob current state, the verified refcount lifecycle, a four-layout
    comparison table (single-index / per-blob / hash-prefix buckets / task-keyed
    buckets, + constant-size note), the task-keyed shared-refcount analysis, all 8
    design questions answered, the t1076 manifest convergence argument, and the
    recommendation.
  - EDIT `aidocs/task_attachments_design.md`: §10 Q4 bucketing-deferred cross-ref
    + a new §8 "Hard-delete" lifecycle note.
- **Recommendation:** Keep per-attachment (per-blob) metadata. Defer hash-prefix
  buckets to a documented, mechanical, reversible future migration gated on a
  file-count threshold AND t1076 manifest reconciliation. Reject task-keyed buckets
  (break the shared refcount; duplicate frontmatter) and constant-size buckets
  (need a lookup index). No semantic/name-based grouping under any option. The
  generated, non-canonical aggregate index is the pressure valve for reporting/scale.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Deliverable placement = dedicated aidocs note + cross-ref
  (user-chosen). The hard-delete decref gap and the bucket migration are tracked as
  standalone follow-up tasks (user-chosen), not folded into this design task.
- **Upstream defects identified:** `.aitask-scripts/board/aitask_board.py:6508
  _do_delete — hard-delete leaks attachment refs (no decref on explicit task
  delete), permanently orphaning blobs (GC never sees them as zero-refcount).`
  Filed as follow-up bug **t1093**.
- **Follow-up tasks created:** **t1093** (bug — decref attachments on task
  hard-delete); **t1094** (enhancement, status Postponed — migrate attachment
  metadata to hash-prefix buckets, referencing the new design note with both
  activation triggers).
- **Notes for sibling tasks:** This is the last child of t1030; archiving it
  empties `children_to_implement` and auto-archives parent t1030. The attachment
  metadata layout is settled (per-blob); future bucketing work flows through t1094
  and must reconcile with the t1076 artifact manifest first.
