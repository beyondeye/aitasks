---
priority: medium
effort: high
depends: [1030]
issue_type: feature
status: Ready
labels: [task_attachments, html_plans]
anchor: 1065
created_at: 2026-06-25 11:04
updated_at: 2026-06-30 11:43
---

## Heads-up — what t1030 actually shipped (verified t1030_4, 2026-06-30)

The "Key work" below says the artifact manifest *generalizes t1030's `index.json`*
— but **t1030 shipped with no `index.json`** (verified end-to-end in t1030_4; a
test asserts its absence). The as-built attachment storage is:

- **Canonical refcount ledger = per-blob meta files** at
  `attachments/meta/<2>/<62>.json` (`lib/attachment_meta.{sh,py}`), blobs at
  `attachments/blobs/<2>/<62>` (local backend).
- The `attachment_backend` contract (put/get/head/delete/list) and the universal
  cache + loud-error write-back resolver (`attachment_resolve`) **are** real and
  ready to promote to `artifact_backend` — that part of the plan is accurate.
- **Archiving never decrefs** (archived task = real referrer); the
  `attachments_gc_grace` knob governs only rm/deletion orphans.

Implication for the manifest design: there is no single mutable index to
"generalize" — the mutable `art:<id> -> {current, versions[], backend}` manifest
is genuinely **new** substrate, not a rename of an existing file. Reconcile the
per-blob-meta ledger (immutable attachments, inline-hash frontmatter) against the
new mutable artifact manifest deliberately; do not assume an `index.json` exists
to extend.

**Design spec:** `aidocs/unified_artifact_design.md` §4b, §5 (+ §2 seam B).

## Context
First substrate piece of the unified artifact model (parent t1076). Generalizes
t1030's attachment storage so it serves **both attachments and artifacts**. Must
land after t1030 ships its local attachment backend + cache + index.

## Key work
- Promote t1030's `attachment_backend` contract (put/get/head/delete/list) to a
  shared **`artifact_backend`** (same content-addressed naming + backend table:
  local / S3-compat / GCS / gh-release / gdrive).
- Define the **artifact manifest** (§4b): the mutable `art:<id> ->
  {current, versions[], backend}` index, generalizing t1030's `index.json`.
  Settle the open question: where the manifest lives / how it travels (committed
  local index vs. backend-resident), under the constraint that updating it never
  touches a task file and any configured PC resolves the handle.
- Universal local cache + write-back wrapper (cache -> backend head+get -> loud error).

## Reference files / patterns
- `aidocs/task_attachments_design.md` §5 (adapter), "Universal local cache", §8.
- `aidocs/gitremoteproviderintegration.md` — platform-extensible dispatcher pattern.
- t1030 (`aitasks/t1030_task_attachments_support.md`) — external dependency.

## Verification
- `artifact_backend` round-trips a blob (put -> head -> get -> verify hash) on the
  local backend; cache hit/miss paths behave per §5.
- Manifest read/write does not touch any task file.

Depends on t1030 (external) — wired in frontmatter.
