---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Postponed
labels: [task_attachments, design]
created_at: 2026-06-30 17:39
updated_at: 2026-06-30 17:39
boardidx: 20
---

Track the deferred migration of attachment metadata from one-file-per-blob to
deterministic **hash-prefix bucket** files. **Postponed** — do not implement until
both activation triggers below hold.

## Design of record

`aidocs/attachment_metadata_bucketing.md` is the authoritative design (layout,
schema, migration steps, the rejected task-keyed and constant-size alternatives,
and the full reasoning). Do not re-derive — read it. The recommendation there is
to **keep per-blob metadata now** and treat hash-prefix bucketing as a mechanical,
reversible future migration only.

## Activation triggers (BOTH must hold — this is a condition, not a dependency edge)

1. **Scale:** a single 2-hex `attachments/meta/<2>/` shard dir exceeds ~5,000 meta
   files (≈ >1.3M total attachments) **and** a generated, non-canonical aggregate
   index has proven insufficient for the reporting/scale need. Below this, per-blob
   is strictly better (conflict isolation, O(1) refcount lookup).
2. **t1076 manifest reconciliation:** the bucketing layout must be settled against
   the per-artifact **manifest** model (`aidocs/unified_artifact_design.md` §4b)
   first, so we do not bucket and then re-key by artifact handle. Per-blob meta
   files are the convergent shape for that manifest; bucketing prematurely would
   create churn t1076_1 must undo.

## Scope when revived (hash-prefix only)

- Configurable `attachment_meta_bucket_width` (0 = per-blob [default], 2, or 4 hex).
- `meta/<prefix>.json` read-modify-write under the global `with_attach_lock`.
- A reversible rebuild migration (per-blob ⇄ buckets) touching only the `meta/`
  subtree; blobs and `refs`-as-source-of-truth are untouched.
- **No** semantic/name-based grouping and **no** task-keyed or constant-size
  scheme (see the design note for why).

Created as a deferred tracking task during t1030_5.
