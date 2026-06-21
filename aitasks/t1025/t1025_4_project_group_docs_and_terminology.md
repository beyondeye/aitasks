---
priority: medium
effort: low
depends: [t1025_3]
issue_type: documentation
status: Implementing
labels: [web_site, git-integration]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-18 00:02
updated_at: 2026-06-21 11:46
---

## Context

Fourth child of t1025 (depends on t1025_3). Rolls out the `project-group`
terminology and user-facing docs once the behavior (t1025_1..t1025_3) exists.
Must NOT churn the immovable `project`-named surfaces (`ait projects`,
`project_config.yaml`, `projects.yaml`, `--project`, `AITASKS_PROJECT_*`,
`xdeprepo`). See parent plan `aiplans/p1025_*.md`.

## Key Files to Modify

- `aidocs/framework/cross_repo_references.md`: define `project-group`, the
  registry `project_group` field, the bootstrap-from-config rule, and the
  `ait projects group list|set|unset|sync` verbs.
- `website/content/docs/workflows/multi_project.md` (and/or a new page): document
  grouping + two-axis TUI navigation. If a NEW page is added, also add a bullet
  to the hand-curated `website/content/docs/workflows/_index.md` grouping
  (sidebar auto-builds but the index body does not).
- User-facing TUI docs: the two-axis navigation (left/right ring + `[`/`]` group
  switch). Keep consistent with `aidocs/framework/tui_conventions.md` (updated in
  t1025_2).

## Reference Files for Patterns

- Existing cross-repo / multi-project doc prose and example naming.
- Documentation conventions: current-state-only; generic invented example project
  names (e.g. frontend/backend), never the author's real repos; no "sister" repo
  terminology.

## Implementation Plan

1. Add `project-group` section to `cross_repo_references.md`.
2. Update/extend the multi-project workflow page; update `_index.md` if a page is
   added.
3. Document the two-axis navigation in user-facing TUI docs.

## Verification

- Docs only. If any skill/template surface is touched (unlikely),
  `./.aitask-scripts/aitask_skill_verify.sh` and regenerate goldens same commit.
- `cd website && hugo build --gc --minify` succeeds; manual link/render check.
