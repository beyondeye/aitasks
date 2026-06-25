---
priority: medium
effort: high
depends: [t1076_2]
issue_type: feature
status: Ready
labels: [task_attachments, html_plans]
anchor: 1065
created_at: 2026-06-25 11:04
updated_at: 2026-06-25 11:04
---

**Design spec:** `aidocs/unified_artifact_design.md` §6 (+ §5 cache wrapper).

## Context
Third substrate piece (parent t1076) — the **sharing** dimension this whole effort
adds. Makes `art:<id>` a portable, project-config-resolvable handle (NOT a raw URL)
that resolves on any machine with the project config.

## Key work
- Resolution chain: handle -> manifest (current hash + backend) -> project config
  (how to reach backend) -> backend get -> verify hash -> local cache -> local path.
- **Project-config backend config**: new `artifacts:` block in
  `aitasks/metadata/project_config.yaml` (git-tracked, team-shared) — kept separate
  from execution profiles and userconfig.
- Wrapper bash script: put/get/head/write-back into the universal local cache.
- Hash-first so backend swaps touch only the manifest, never task files.

## Reference files / patterns
- t1076_1, t1076_2 (siblings) — backend/manifest + handle model.
- `aitasks/metadata/project_config.yaml` — config home (add `artifacts:` block).
- `aidocs/task_attachments_design.md` §"Universal local cache".

## Verification
- A handle authored on one checkout resolves on a second checkout that has only the
  project config (simulate: clear cache, resolve, confirm fetch+cache+verify).
- Backend swap in config re-resolves the same handle without any task-file change.
