---
Task: t95_skills_defined_in_claude_dir_are_source_of_truth.md
---

## Context

Currently the repo maintains two identical copies of skill definitions:
- `skills/` (root) — packaged into release tarballs
- `.claude/skills/` — the actual installed skills used by Claude Code

This duplication means edits to skills must be mirrored in both places. The goal is to eliminate `skills/` from the repo and have the GitHub release workflow dynamically build it from `.claude/skills/aitask*` directories, making `.claude/skills/` the single source of truth.

## Plan

### 1. Modify `.github/workflows/release.yml`

Add a step before tarball creation that builds the `skills/` staging directory from `.claude/skills/aitask-*/`.

### 2. Delete `skills/` directory from the repo

Remove the now-redundant `skills/` directory and all its contents from version control.

### 3. Add `skills/` to `.gitignore`

Create a `.gitignore` with `skills/` to prevent accidentally re-committing the directory.

## Files to modify
- `.github/workflows/release.yml` — add build step
- `skills/` — delete entirely
- `.gitignore` — create with `skills/` entry

## Final Implementation Notes
- **Actual work done:** All three planned steps implemented as designed — no deviations
- **Deviations from plan:** None
- **Issues encountered:** None — the `skills/` and `.claude/skills/` directories were already identical
- **Key decisions:** Used `cp -r` in the workflow to copy entire skill directories (not just SKILL.md), ensuring any future multi-file skills are handled correctly
