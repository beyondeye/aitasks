---
priority: medium
effort: high
depends: [1030]
issue_type: feature
status: Ready
labels: [task_attachments, html_plans]
anchor: 1065
created_at: 2026-06-25 11:04
updated_at: 2026-06-25 11:05
---

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
