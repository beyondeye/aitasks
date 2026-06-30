# Attachment Metadata Layout — Per-Blob vs Buckets (Evaluation)

Should the attachment refcount ledger move from **one metadata file per blob** to
deterministic **bucket** files (grouping many attachments per file)? This note
evaluates the question, compares the candidate layouts, and gives a recommendation
for the t1030 attachment system.

Status: **design evaluation / RFC**. It produces a comparison, answers, and a
recommendation; it is **not** an implementation and creates no canonical-schema
change. Forward-looking migration shape is documented for a possible future, not
adopted now. Sibling design: [`task_attachments_design.md`](task_attachments_design.md)
(the shipped attachment model) and [`unified_artifact_design.md`](unified_artifact_design.md)
(the artifact manifest this decision must converge with).

## 1. Current state (what shipped)

The canonical lifecycle ledger is **one JSON file per blob** at
`attachments/meta/<2>/<62>.json` (`lib/attachment_meta.py`) — there is **no global
`index.json`** (a test asserts its absence). Blobs live separately at
`attachments/blobs/<2>/<62>`. Each meta file holds blob-intrinsic fields plus the
refcount set:

```json
{ "hash": "sha256:<hex>", "refs": ["1030_2", "42"],
  "mime": "image/png", "size": 12345, "backend": "local" }
```

- **`refs` is the refcount source of truth** — the set of task ids referencing the
  blob. Archive-time GC consumes it.
- **Per-task display fields (`name`, `added_at`) are NOT here** — they stay
  authoritative in each task's `attachments:` frontmatter, because the same bytes
  can attach to two tasks under different names. The meta file holds only the
  *shared, cross-task* facts.
- All mutations serialize on one global `attachments/.attach.lock`
  (`lib/attachment_lock.sh`); `attachment_meta.py` is a **lock-free** primitive
  (the caller owns the lock). Writes are atomic (temp + `os.replace`), so reads are
  untorn lock-free.

Per-blob was chosen over a single `index.json` (t1030_2, user-directed) precisely
to **avoid a global write-hotspot**: a single index forces every add/rm/rebind to
rewrite the whole file, manufacturing merge conflicts between *unrelated*
attachments on the shared `.aitask-data` branch (which has concurrent writers —
the syncer plus parallel sessions).

## 2. Refcount lifecycle — when does `refs` actually change?

This is load-bearing for the bucket question, so it is stated precisely. The only
scripts that touch the ledger are `aitask_attach.sh` (incref/decref) and
`aitask_fold_mark.sh` (rebind):

- **Add** → `incref <hash> <task>` (`aitask_attach.sh:255`).
- **`ait attach rm`** → `decref <hash> <task>` (`aitask_attach.sh:342`) — the
  **only** routine decref.
- **Archive never decrefs** (decision D4) — an archived task is a real referrer
  (browsable history); `aitask_archive.sh` makes no ledger change.
- **Fold rebinds, not decrefs** (`aitask_fold_mark.sh:442`) — folding A into B
  *transfers* A's ref to B; the count is preserved, just reassigned.

### 2a. Known gap — hard-delete leaks refs (tracked separately)

A task can be **explicitly hard-deleted** (e.g. from `ait board`), which fully
removes its files. That path — `_do_delete` (`aitask_board.py:6508`) — `git rm`s
the task + plan files and commits **without decref'ing the task's attachments**. So
a deleted task's id stays **stale in the blob's `refs` forever** → the blob is
never zero-refcount → `ait attach gc` never reclaims it (a permanent orphaned-blob
leak). The same applies to a parent delete that cascade-deletes children.

**Intended behavior:** an explicit hard-delete should decref each of the deleted
task's attachments. Under the per-blob layout this fix is **clean and targeted**:
read the doomed task's `attachments:` frontmatter (the authoritative list of hashes
it references) and, under `with_attach_lock`, `decref <hash> <task_id>` each one —
an O(k) operation (k = attachments on that task), **no tree scan**. It is literally
`ait attach rm` applied to all of the task's attachments at once, reusing the
already-shipped `lib/attachment_meta.sh` + `lib/attachment_lock.sh`. This is filed
as a separate follow-up bug (see §7); it is not a bucketing concern.

## 3. The layouts compared

Four candidate layouts (the user proposed **task-keyed** and **constant-size**
during evaluation; both are analyzed honestly here):

| Dimension | Single global index | **Per-blob (shipped)** | Hash-prefix buckets | Task-keyed buckets |
|---|---|---|---|---|
| Refcount lookup `refs <hash>` | parse whole index | **O(1) file read** | O(1) read of one bucket | **O(tasks) scan** (no single home for `refs`) |
| GC `zero-refcount` / `rebind` scan | one file | O(attachments) files | O(buckets) files, same bytes | O(tasks) files, same bytes |
| Concurrency / conflict isolation | **global hotspot** | **best — per-attachment** | prefix-collisions co-locate → hotspot returns | task-collisions rare, but shared-blob writes cross buckets |
| Diff readability | one churning file | small, isolated | medium, multi-entry | medium, multi-entry |
| File count | 1 | many | few | ~one per attaching task |
| Lock granularity (today) | global | global | global | global |
| Rollback blast radius | whole index | **one attachment** | many attachments per bucket | many attachments per bucket |
| Dedup / shared-blob fit | fine (one record) | **fine (one record, `refs` set)** | fine | **broken — refcount isn't per-task** |
| t1076 manifest fit | poor (coarse) | **good — closest to per-artifact record** | poor (coarse) | poor (wrong key) |

Two schemes fail immediately:

- **Constant-size / insertion-order buckets** are *not simpler* — non-deterministic
  placement means "which bucket holds hash X?" needs a hash→bucket lookup table,
  i.e. the global index we deleted. Only **hash-prefix** buckets keep O(1)
  deterministic lookup, which is why the seed analysis chose them.
- **Task-keyed buckets** (one file per introducing task, e.g. 5 attachments → one
  `meta/by-task/42.json`) are feasible but **regressive** — see §4.

## 4. Why task-keyed buckets don't work (the shared-refcount problem)

The appeal of task-keying is lifecycle-matching: delete/fold a task → drop/move one
bucket file. But it fights the ledger's reason to exist:

1. **Refcount is inherently per-blob, because blobs are shared (dedup).** A blob
   attached to tasks 42 and 7 has `refs: [42, 7]` in one place. Key by task and
   there is **no single home** for that set; "is blob X still referenced?" becomes a
   scan across every task bucket — pushing cost onto the *hot* `refs <hash>` lookup
   (today O(1)).
2. **It duplicates what frontmatter already holds.** Each task's `attachments:`
   list *is already* a per-task bucket of `{name, added_at, hash}`. The `meta/`
   files exist *only* for the shared cross-task facts (`refs` + blob-intrinsics).
   A task-keyed meta file re-implements the frontmatter and **denormalizes**
   blob-intrinsics across every referencing task (the shipped design stores them
   once and `die`s loudly on mismatch — a property task-keying loses).
3. **The lifecycle win is narrow and undercut.** Given §2: archive does nothing to
   the ledger, `rm` edits one entry, and **hard-delete decref is already O(k)** via
   the task's frontmatter under per-blob. So the *only* op a task bucket could speed
   up is **fold-rebind** (tree-scan → rename). And even that collapses for shared
   blobs: deleting task 42's bucket must not delete a blob task 7 still references →
   you are back to a cross-bucket refcount scan.

The user's instinct — *match metadata to lifecycle* — is sound, and the shipped
design **already satisfies it** by splitting correctly: per-task data in the
per-task file (frontmatter), shared data in the per-blob file. Task-keying breaks
that correct split for the shared half.

## 5. The 8 design questions

1. **Is per-attachment metadata sufficient for v1/v2 scale, or plan buckets now?**
   Sufficient. v1/v2 attachments are screenshots and small artifacts (dozens to
   low-hundreds per project). The 2-hex shard already caps any directory at a few
   thousand entries. No bucketing is planned now.
2. **What thresholds justify buckets?** A single 2-hex `meta` shard dir exceeding
   ~5,000 files (≈ >1.3M total attachments) **and** a generated aggregate index
   (Q7) proving insufficient — i.e. effectively never at task-attachment scale.
   Below that, file count is not a real cost.
3. **Which bucket width if chosen?** Only **hash-prefix** is viable: a configurable
   `attachment_meta_bucket_width` (0 = per-blob [default], 2, or 4 hex), starting at
   2-hex, **not adaptive** (determinism beats cleverness — the lookup must stay a
   pure function of the hash). Task-keyed and constant-size are rejected (§3, §4).
4. **How should bucket-level locking work; does it reintroduce contention?** It is
   **not needed today**: all mutations already serialize on the single global
   `.attach.lock`, so lock *granularity* is moot. Any per-bucket scheme (hash- or
   task-keyed) would cross-race the global add/rm transaction (a different lock dir
   does not exclude an in-flight `add`/`rm`) — so it is rejected for v1. A
   finer-grained lock is only sound atop a provably non-overlapping partition,
   which is not established.
5. **How do add/rm/rebind/zero-refcount/GC operate under buckets?** Hash-prefix:
   read-modify-write the whole bucket file under the global lock — same total scan
   bytes as per-blob, but a **worse rollback blast radius** (one corrupt or
   conflicted bucket affects many logical attachments). Task-keyed additionally
   makes `refs <hash>` and GC O(tasks) scans (§4). Per-blob keeps `refs <hash>`
   O(1) and isolates every mutation to one small file.
6. **How do rollback and explicit Git staging work for bucket files?** The same
   mechanics as today — pre-image/HEAD-restore rollback and explicit (never blanket)
   path staging — but because a bucket holds multiple attachments, a failed commit
   reverts **unrelated entries together**, and a merge conflict spans unrelated
   attachments. That is a regression versus per-blob's per-attachment isolation.
7. **Should an aggregate index stay non-canonical / generated-only?** Yes —
   explicitly. If fast counts or cross-attachment reports are ever needed, a
   **generated, non-authoritative** aggregate index is the right pressure valve;
   it never becomes the source of truth (consistent with `task_attachments_design.md`
   §4 / §10 Q4). This removes the main motivation for bucketing the *canonical*
   ledger.
8. **Migration path if buckets are deferred (and how it would run if revived).**
   Deferred. The migration would be **mechanical and reversible**, hash-prefix only:
   under the global `.attach.lock`, read every `meta/<2>/<62>.json`, group by the
   chosen prefix width, write `meta/<prefix>.json` bucket files, single commit;
   blobs and `refs`-as-source-of-truth are untouched (only the `meta/` subtree
   changes), and the inverse rebuild restores per-blob. Task-keyed is **not** a
   migration target. **Precondition:** reconcile with the t1076 artifact manifest
   first (§6), so we don't bucket and then re-key by artifact handle.

## 6. Convergence with the t1076 artifact manifest

[`unified_artifact_design.md`](unified_artifact_design.md) §4b promotes t1030's
ledger into a per-artifact **manifest** (`art:<id> → current / versions / backend`)
keyed by a **stable handle**, with an attachment as the single-version degenerate
case. Both shipped sibling plans (t1030_2, t1030_3) note that **per-blob meta files
are *closer* to that per-artifact-record shape than a global index ever was**. The
storage layer is therefore heading toward **finer, per-record** granularity — the
opposite of coarse buckets. Bucketing now would create churn that t1076_1's
generalization would have to undo or re-key. This is the decisive long-horizon
reason to keep per-blob.

## 7. Recommendation

**Keep per-attachment metadata. Do NOT adopt buckets now — neither hash-prefix nor
task-keyed.** Document hash-prefix buckets as a deferred, mechanical, reversible
future migration, gated on the Q2 file-count threshold **and** the t1076 manifest
reconciliation. The generated aggregate index (Q7) is the pressure valve for any
reporting/scale need short of that threshold.

Summary of why:

- Buckets undo the conflict-isolation win per-blob files were chosen for (§1).
- Locking gains nothing under the current single-global-lock model (Q4).
- GC/rebind scan cost is unchanged; rollback blast radius is worse (Q5/Q6).
- Per-blob is the convergent shape for the t1076 manifest (§6).
- Task-keyed breaks the shared refcount and duplicates frontmatter (§4);
  constant-size needs a lookup index (§3).
- **No semantic / name-based grouping** for the canonical ledger under any option:
  attachment names are mutable, collidable, per-task display fields, so the
  lifecycle ledger must not key on them. Hash-prefix is the only stable, blob-
  intrinsic, evenly-distributed key.

Tracked follow-ups: a **bug** for the hard-delete decref leak (§2a), and a
**Postponed** enhancement to track the hash-prefix migration referencing this note.

## 8. Cross-references

- [`task_attachments_design.md`](task_attachments_design.md) — shipped attachment
  model (storage layout §4, lifecycle §8, ledger-format open question §10 Q4).
- [`unified_artifact_design.md`](unified_artifact_design.md) — the §4b artifact
  manifest this decision converges with.
- [`gitremoteproviderintegration.md`](gitremoteproviderintegration.md) — the
  platform-extensible dispatcher pattern the backend adapter follows.
