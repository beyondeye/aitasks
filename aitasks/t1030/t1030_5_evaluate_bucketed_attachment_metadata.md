---
priority: medium
effort: medium
depends: [t1030_2]
issue_type: enhancement
status: Implementing
labels: [task_attachments, brainstorming, design]
assigned_to: dario-e@beyond-eye.com
anchor: 1030
created_at: 2026-06-29 10:14
updated_at: 2026-06-30 11:49
---

## Heads-up — shipped storage model (verified t1030_4, 2026-06-30)

The per-attachment metadata model this task evaluates is **landed**, not "moving":
t1030_2/t1030_3 shipped it and t1030_4 verified it end-to-end. Confirmed facts to
write any bucketing design against:

- **Canonical refcount ledger = per-blob meta files** at
  `attachments/meta/<2>/<62>.json`. There is **no `index.json`** (a test asserts
  its absence). Blobs live at `attachments/blobs/<2>/<62>` (local backend).
- **Archiving never decrefs** — an archived task is a real referrer (browsable
  history), so its blobs are retained indefinitely. The `attachments_gc_grace`
  knob governs only blobs orphaned by `ait attach rm` or task *deletion*. Design
  question 4 (bucket locking) and 5 (GC/rebind under buckets) must preserve this:
  the GC blocking-set already scans active **and** archived (non-Folded) task
  frontmatter as a belt-and-suspenders cross-check against ledger drift
  (`_attach_gc_blocking_hashes` in `aitask_attach.sh`).

Evaluate and design a possible refactor from one metadata file per attachment to deterministic metadata "buckets" for task attachments.

Context:

- t1030_2 is moving attachment lifecycle metadata away from a single global `attachments/index.json` toward per-attachment metadata files at `attachments/meta/<2>/<62>.json`.
- That per-file design improves concurrency and isolates conflicts, but it can create many small Git-tracked metadata files if attachment volume grows.
- The user asked whether a bucketed layout could be a better middle ground: grouping metadata for multiple related attachments into bucket files.

Seed analysis:

- Do not bucket by display name, "similar names", task name, or other semantic/UI metadata. Attachment names are per-task display fields, can differ for the same hash, can collide, and can change. The lifecycle ledger should not depend on unstable presentation metadata.
- If bucketed metadata is useful, prefer deterministic hash-prefix buckets. SHA-256 prefixes are stable, evenly distributed, and blob-intrinsic.
- Possible layouts:
  - `attachments/meta/ab.json` for all hashes starting with `ab`.
  - `attachments/meta/ab/cd.json` for all hashes starting with `abcd`.
  - Keep blobs separate, e.g. `attachments/blobs/<2>/<62>`.
- Example bucket content:

```json
{
  "sha256:abcd...": {
    "refs": ["1030_2", "42"],
    "mime": "image/png",
    "size": 12345,
    "backend": "local"
  }
}
```

Design questions to answer:

1. Whether per-attachment metadata is sufficient for expected v1/v2 scale, or whether bucketed metadata should be planned now.
2. What attachment count/file-count thresholds justify bucketed metadata.
3. Which bucket width is the right default if buckets are chosen: 2 hex chars, 4 hex chars, adaptive, or configurable.
4. How bucket-level locking should work, and whether bucket locks reintroduce too much contention.
5. How add/rm/rebind/zero-refcount/GC would operate under bucketed metadata.
6. How rollback and explicit Git staging should work for bucket files.
7. Whether an aggregate index should remain explicitly non-canonical and generated-only.
8. Migration path from per-attachment metadata to bucketed metadata, if bucketed metadata is deferred.

Expected output:

- A short design note or plan comparing:
  - single global index,
  - per-attachment metadata,
  - hash-prefix bucket metadata.
- A recommendation for current t1030 direction: keep per-attachment metadata, switch to buckets now, or keep buckets as a documented future migration.
- If buckets are recommended, specify the exact layout, schema, locking, rollback, tests, and migration steps.

Acceptance criteria:

- The design does not use name-based or semantic grouping for canonical lifecycle metadata unless it gives a strong reason and handles mutable/colliding display names.
- The design states the source of truth for refs and makes clear that per-task display fields remain authoritative in task frontmatter.
- The design accounts for Git behavior with many small files versus bucket-file contention.
- The design defines how GC/rebind scans avoid stale destructive decisions.
- The design is synchronized with `aidocs/task_attachments_design.md` if it changes the recommended architecture.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T14:36:19Z status=pass attempt=1 type=human
