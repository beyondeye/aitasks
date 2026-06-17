---
Task: t1025_4_project_group_docs_and_terminology.md
Parent Task: aitasks/t1025_design_project_group_grouping_and_tui_navigation.md
Sibling Tasks: aitasks/t1025/t1025_1_*.md, aitasks/t1025/t1025_2_*.md, aitasks/t1025/t1025_3_*.md
Archived Sibling Plans: aiplans/archived/p1025/p1025_1_*.md, aiplans/archived/p1025/p1025_2_*.md, aiplans/archived/p1025/p1025_3_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: project-group terminology + user-facing docs (t1025_4)

Depends on t1025_3 (behavior + bindings exist). See parent plan `aiplans/p1025_*.md`.

## Steps

1. `aidocs/framework/cross_repo_references.md`: add a `project-group` section —
   the registry `project_group` field, the bootstrap-from-config rule, the slug
   contract, and the `ait projects group list|set|unset|sync` verbs. Do NOT touch
   the immovable `project`-named surfaces.
2. `website/content/docs/workflows/multi_project.md` (or a new page): document
   grouping + two-axis TUI navigation. If a NEW page is added, add a bullet to the
   hand-curated `website/content/docs/workflows/_index.md` grouping.
3. User-facing TUI docs: the two-axis navigation (left/right ring + `[`/`]` group
   switch), consistent with `aidocs/framework/tui_conventions.md` (t1025_2).
4. Follow doc conventions: current-state-only; generic invented example project
   names (frontend/backend), never the author's real repos; no "sister" repo term.

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- Manual link/render check of the changed pages + sidebar/index.
- If any skill/template surface is touched (unlikely):
  `./.aitask-scripts/aitask_skill_verify.sh` and regenerate goldens same commit.

## Step 9
Standard child archival.
