---
Task: t403_add_archived_task_subcommand_to_query_files.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `aitask-revert` skill (`.claude/skills/aitask-revert/SKILL.md`, line 28) calls `aitask_query_files.sh archived-task <number>`, a subcommand that doesn't exist. Additionally, tasks can be in `old.tar.gz` deep archives, which the revert disposition logic doesn't handle.

Two fixes:
1. Add `archived-task` subcommand to `aitask_query_files.sh` (with tar.gz awareness)
2. Add `unpack` subcommand to `aitask_zip_old.sh` that extracts a task from `old.tar.gz` — the SKILL.md calls this immediately after task resolution, avoiding conditional tar.gz logic

## Plan

### Step 1: Add `cmd_archived_task()` to `aitask_query_files.sh`
- Check filesystem (`$ARCHIVED_DIR/t<N>_*.md`) first → `ARCHIVED_TASK:<path>`
- Fall back to `_search_tar_gz` in `old.tar.gz` → `ARCHIVED_TASK_TAR_GZ:<entry>`
- Otherwise → `NOT_FOUND`

### Step 2: Add `unpack` subcommand to `aitask_zip_old.sh`
- Extract parent + children + plans from both task and plan tar.gz archives
- Rebuild tar.gz without extracted entries (or delete if empty)
- No-op (`NOT_IN_ARCHIVE`) when task not found in any archive

### Step 3: Update SKILL.md
- Step 1: Updated parsing docs for new `archived-task` output tags
- Always run `unpack` immediately after task resolution (no-op if not in tar.gz)
- Removed conditional tar.gz block from Step 4 disposition templates

### Step 4-5: Automated tests
- `test_query.sh`: 6 new tests for `archived-task` (filesystem, tar.gz, priority, not-found, prefix, help)
- `test_zip_old.sh`: 7 new tests for `unpack` (parent, parent+children, plans, no-op, not-found, empty tar, prefix)

## Final Implementation Notes
- **Actual work done:** Implemented all planned changes as described
- **Deviations from plan:** User feedback simplified the SKILL.md approach — instead of a conditional tar.gz block in Step 4 disposition templates, `unpack` is always called in Step 1 immediately after task resolution. This is simpler and the no-op behavior makes it safe.
- **Issues encountered:** Test 24 in `test_zip_old.sh` initially failed because `git commit` returned non-zero when there were no changes (redundant commit in setup). Fixed by removing the unnecessary commit.
- **Key decisions:** Used distinct output tags (`ARCHIVED_TASK` vs `ARCHIVED_TASK_TAR_GZ`) so callers know the source. The `unpack` subcommand handles both task and plan archives in one call.
