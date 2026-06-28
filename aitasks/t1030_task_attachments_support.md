---
priority: low
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [task_attachments]
file_references: [aidocs/task_attachments_design.md]
children_to_implement: [t1030_1, t1030_2, t1030_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-18 15:26
updated_at: 2026-06-28 12:08
boardidx: 240
---

look at
aidocs/task_attachments_design.md

for the task definition

## Coordination — t1065 unified artifact model

t1065 (`aidocs/unified_artifact_design.md`) designs a unified **artifact**
capability and constrains this task's storage seam:

- The backend adapter + universal local cache should be designed to serve
  **both attachments and artifacts** — i.e. generalize `attachment_backend` to a
  shared `artifact_backend` (same content-addressed naming, same backend table).
- **Attachments are the single-version degenerate case** of the artifact pointer
  model: a stable id whose one immutable hash is never repointed.
- t1030's **inline-hash frontmatter is safe only because attachments are
  immutable**. Mutable artifacts keep `current` / `versions` / `backend` in a
  separate **manifest**, not the task file (so edits/backend-moves never rewrite
  task files). Reconcile the `attachments:` (inline) vs `artifacts:` (handle-only)
  frontmatter schemas, and decide whether `index.json` becomes the shared
  manifest.

See `aidocs/unified_artifact_design.md` §3–§5, §10 and its decomposition (§11).

**Implementation:** the generalization is **t1076_1**
(`storage_abstraction_generalization`, under parent t1076), which `depends: [1030]`
— it builds on this task's attachment backend + cache + index.
