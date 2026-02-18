---
Task: t162_add_missing_task_types.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Task t162 requests adding missing task types: `style`, `test`, `chore`. Currently we have `bug`, `documentation`, `feature`, `performance`, `refactor`. The architecture loads types dynamically from `aitasks/metadata/task_types.txt`, so adding types to that file makes them immediately available in the board, create, and update flows. However, documentation, display names, label detection, and changelog grouping all have hardcoded references that need updating.

Note: `performance` was already in the data files but missing from most documentation — this plan corrects that too.

## Plan

### 1. Core data files — add `chore`, `style`, `test` (keep alphabetically sorted)

- `seed/task_types.txt`
- `aitasks/metadata/task_types.txt`

Final contents (8 types): `bug`, `chore`, `documentation`, `feature`, `performance`, `refactor`, `style`, `test`

### 2. Stats display names — `aiscripts/aitask_stats.sh:51-58`

Add explicit cases in `get_type_display_name()`:
- `documentation` -> "Documentation"
- `performance` -> "Performance"
- `style` -> "Style Changes"
- `test` -> "Tests"
- `chore` -> "Chores"

### 3. GitHub label detection — `aiscripts/aitask_issue_import.sh:130-139`

Add detection branches in `github_detect_type()` for:
- `test|testing|tests` -> `test`
- `style|styling|formatting|lint|linting` -> `style`
- `chore|maintenance|housekeeping|deps|dependencies` -> `chore`
- `documentation|docs` -> `documentation`
- `performance|perf|optimization` -> `performance`

### 4. Help text — `aiscripts/aitask_ls.sh:40`

Update `issue_type: bug|feature|refactor` to include all 8 types.

### 5. Test fixture — `tests/test_draft_finalize.sh:104`

Update `printf` to include all 8 types.

### 6. Documentation updates

- `docs/task-format.md:40` — update type list in frontmatter table
- `docs/task-format.md:88-93` — update code block listing default types
- `docs/board.md:196,479` — update defaults list
- `docs/commands.md:121` — update type list
- `docs/workflows.md:67` — update auto-detected types list

### 7. Skill files

- `.claude/skills/task-workflow/SKILL.md:383` — update valid types in commit message convention
- `.claude/skills/aitask-changelog/SKILL.md:19,48-51` — add section headers for new types

### No changes needed (confirmed)

- `aiscripts/aitask_create.sh` — loads dynamically
- `aiscripts/aitask_update.sh` — loads dynamically
- `aiscripts/board/aitask_board.py` — loads dynamically via `_load_task_types()`
- `aiscripts/aitask_changelog.sh` — extracts from task file frontmatter

## Final Implementation Notes
- **Actual work done:** Added `chore`, `style`, `test` to both data files. Updated stats display names, GitHub label detection, help text, test fixture, 4 docs files, and 2 skill files. Also corrected missing `documentation` and `performance` references throughout docs.
- **Deviations from plan:** None — all planned changes implemented as specified.
- **Issues encountered:** None. All 35 tests pass.
- **Key decisions:** Refactored `github_detect_type()` to extract label names once into a variable instead of repeating the `jq` call per branch. Chose "Maintenance" as the changelog header for `chore` type (matching keepachangelog conventions).
