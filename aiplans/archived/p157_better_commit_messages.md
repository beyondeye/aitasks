---
Task: t157_better_commit_messages.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Commit messages across the aitasks project are inconsistent and hard to parse in git history. This refactoring standardizes all commit messages with two prefix categories:

1. **`ait:`** for administrative/lifecycle commits (task creation, status changes, archival, updates, deletion, folding, setup, changelog, version bumps)
2. **`<issue_type>:`** for implementation commits at task completion, using the task's `issue_type` frontmatter field (`feature`, `bug`, `refactor`, `documentation`)

## Changes

### 1. Shell Scripts — Add `ait: ` prefix to commit messages

**`aiscripts/aitask_setup.sh`** (3 edits)
- Line 327: `"Add aitask framework"` → `"ait: Add aitask framework"`
- Line 402: `"Add aitask framework"` → `"ait: Add aitask framework"`
- Line 521: `"Add aitasks/new/ to .gitignore (draft tasks)"` → `"ait: Add aitasks/new/ to .gitignore (draft tasks)"`

**`aiscripts/aitask_create.sh`** (5 edits)
- Line 480: `"Add child task ${task_id}: ..."` → `"ait: Add child task ${task_id}: ..."`
- Line 537: `"Add task ${task_id}: ..."` → `"ait: Add task ${task_id}: ..."`
- Line 1090: `"Add task t${task_num}: ..."` → `"ait: Add task t${task_num}: ..."`
- Line 1199: `"Add child task ${task_id}: ..."` → `"ait: Add child task ${task_id}: ..."`
- Line 1225: `"Add task ${task_id}: ..."` → `"ait: Add task ${task_id}: ..."`

**`aiscripts/aitask_update.sh`** (2 edits)
- Line 1151: `"Update task t${task_num}: ..."` → `"ait: Update task t${task_num}: ..."`
- Line 1324: `"Update task t${BATCH_TASK_NUM}: ..."` → `"ait: Update task t${BATCH_TASK_NUM}: ..."`

**`aiscripts/aitask_zip_old.sh`** (1 edit)
- Line 392: `"Archive old task and plan files` → `"ait: Archive old task and plan files`

**`aiscripts/aitask_issue_import.sh`** (1 edit)
- Line 560: `"Add task ${task_id}: ..."` → `"ait: Add task ${task_id}: ..."`

**`create_new_release.sh`** (1 edit)
- Line 62: `"Bump version to $new_version"` → `"ait: Bump version to $new_version"`

**`aiscripts/aitask_claim_id.sh`** (2 edits — git plumbing commits on remote branch)
- Line 108: `"Initialize task ID counter at $next_id"` → `"ait: Initialize task ID counter at $next_id"`
- Line 162: `"Claim task ID t$current_id, advance counter to $new_id"` → `"ait: Claim task ID t$current_id, advance counter to $new_id"`

**`aiscripts/aitask_lock.sh`** (4 edits — git plumbing commits on remote branch)
- Line 71: `"Initialize task lock branch"` → `"ait: Initialize task lock branch"`
- Line 142: `"Lock task t$task_id for $email"` → `"ait: Lock task t$task_id for $email"`
- Line 197: `"Unlock task t$task_id"` → `"ait: Unlock task t$task_id"`
- Line 329: `"Cleanup ${#stale_files[@]} stale lock(s)"` → `"ait: Cleanup ${#stale_files[@]} stale lock(s)"`

### 2. Python Board TUI — Add `ait: ` prefix

**`aiscripts/board/aitask_board.py`** (3 edits)
- Line 1372: `f"Update {task_num}: {task_name}"` → `f"ait: Update {task_num}: {task_name}"`
- Line 1378: `f"Update tasks: {', '.join(task_nums)}"` → `f"ait: Update tasks: {', '.join(task_nums)}"`
- Line 2353: `f"Delete task {task_num} and associated files"` → `f"ait: Delete task {task_num} and associated files"`

### 3. Skill Files — Update commit message conventions

**`.claude/skills/task-workflow/SKILL.md`** (6 edits)
- Line 121: Add `ait: ` prefix to "Start work on t<N>..." commit
- Line 347: Update note to reference `<issue_type>: <description> (t<task_id>)` format
- Line 383: Rewrite implementation commit convention to specify `<issue_type>: <description> (t<task_id>)` format
- Line 501: Add `ait: ` prefix to child archival commit
- Line 548: Add `ait: ` prefix to parent archival commit
- Line 588: Add `ait: ` prefix to abort revert commit

**`.claude/skills/aitask-fold/SKILL.md`** (1 edit)
- Line 198: Add `ait: ` prefix to fold commit

**`.claude/skills/aitask-changelog/SKILL.md`** (1 edit)
- Line 191: Add `ait: ` prefix to changelog commit

**`.claude/skills/aitask-review/SKILL.md`** (replace filter block)
- Lines 69-80: Replace 11 individual patterns with single `^ait: ` pattern

### 4. Tests — Update assertions

**`tests/test_setup_git.sh`** (2 edits)
- Line 117, 136: `"Add aitask framework"` → `"ait: Add aitask framework"`

**`tests/test_zip_old.sh`** (1 edit)
- Line 332: `"Archive old task and plan files"` → `"ait: Archive old task and plan files"`

## Verification

1. Run `bash tests/test_setup_git.sh`
2. Run `bash tests/test_zip_old.sh`
3. Grep for remaining un-prefixed commit messages
4. Verify `(tNN)` detection still works

## Final Implementation Notes
- **Actual work done:** All commit messages across 15 files (8 shell scripts, 1 Python file, 4 skill files, 2 test files) plus 1 new plan file were updated. The aitask-review filter was simplified from 11 patterns to 1. The implementation commit convention in task-workflow SKILL.md was rewritten to specify the `<issue_type>: <description> (t<task_id>)` format.
- **Deviations from plan:** None. All planned changes were implemented as specified.
- **Issues encountered:** None. All changes were mechanical string prefix additions except for the task-workflow implementation commit convention rewrite and the review filter simplification.
- **Key decisions:** Collapsed the 11 review filter patterns to a single `^ait: ` pattern for future-proofing. Included git plumbing commits (aitask_claim_id.sh, aitask_lock.sh) for consistency even though they live on separate remote branches.
