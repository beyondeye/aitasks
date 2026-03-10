---
Task: t358_codex_get_confused_by_aitasks_aiplans_symlinks.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: t358 — Add symlink/worktree awareness to workflow instructions

## Context

When code agents (especially Codex CLI) start the implementation phase, they encounter
`aitasks/` and `aiplans/` directories that are **symlinks** pointing to `.aitask-data/aitasks/`
and `.aitask-data/aiplans/`. The `.aitask-data/` directory is a separate git worktree on the
`aitask-data` orphan branch. This confuses agents that expect a standard repo layout.

The workflow already has indirect references (Step 8/9 mention `./ait git` for task files), but
there was no explicit upfront explanation of the symlink architecture.

## Approach

1. Created `repo-structure.md` in `.claude/skills/task-workflow/` alongside `planning.md`,
   `procedures.md`, and `profiles.md` — contains the full explanation of the architecture
2. Added references to this file from:
   - Step 7 in `SKILL.md` (before implementation begins)
   - Notes section in `SKILL.md`
   - `.codex/instructions.md` (Codex-specific instructions)

## Changes Made

### New file: `.claude/skills/task-workflow/repo-structure.md`
- Architecture overview (`.aitask-data/`, symlinks)
- 5 rules for implementation (don't git add task files, don't be alarmed by symlinks, etc.)
- Detection section (branch mode vs legacy mode)
- Common confusion points

### Modified: `.claude/skills/task-workflow/SKILL.md`
- Step 7: Added "Repository structure awareness" reference line after Agent Attribution
- Notes section: Added bullet about symlinks and data worktree

## Final Implementation Notes

- **Actual work done:** Created `repo-structure.md` as standalone documentation and added references from SKILL.md Step 7 and Notes section. The Codex-specific `.codex/instructions.md` change was removed per user review — the general note in the shared workflow is sufficient.
- **Deviations from plan:** Dropped the `.codex/instructions.md` change after user feedback that the general workflow reference covers all agents.
- **Issues encountered:** None.
- **Key decisions:** Extracted documentation to a separate file (`repo-structure.md`) rather than inlining it, following the pattern of `planning.md`, `procedures.md`, and `profiles.md` in the same directory.

## Post-implementation suggestions

Create separate aitasks to update Gemini CLI, OpenCode, and Codex tool mapping files
with equivalent references to `repo-structure.md`.
