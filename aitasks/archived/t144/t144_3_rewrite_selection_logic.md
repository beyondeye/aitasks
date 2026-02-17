---
priority: medium
effort: medium
depends: [t144_2, t144_1]
issue_type: feature
status: Done
labels: [aitasks, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-17 10:49
updated_at: 2026-02-17 12:33
completed_at: 2026-02-17 12:33
---

## Context

This is child 3 of t144 (ait clear_old rewrite). The current `aitask_zip_old.sh` (renamed from `aitask_clear_old.sh` by child 1) uses a "keep most recent" selection logic that is obsolete and unsafe. It needs to be rewritten with a "keep files still relevant to active work" approach.

## Key Files to Modify

1. **`aiscripts/aitask_zip_old.sh`** — Rewrite selection logic (the core of this task)

## New Files to Create

1. **`tests/test_zip_old.sh`** — Automated test file (see test cases below)

## Reference Files for Patterns

- `aiscripts/aitask_zip_old.sh`: Current script (after rename by child 1) — keep the `archive_files()` function, CLI parsing, and dry-run/verbose/no-commit infrastructure. Rewrite the selection functions.
- `tests/test_task_lock.sh`: Test file structure pattern
- Active task files in `aitasks/` — check `depends:` frontmatter format

## New Selection Logic

An archived file is "still relevant" (must stay uncompressed) if ANY of these hold:

### Rule 1: Archived siblings of active children
If `aitasks/t<N>/` exists (parent still has active children), keep:
- All archived children in `aitasks/archived/t<N>/`
- Corresponding archived plan files in `aiplans/archived/p<N>/`
- Note: the parent task file itself is NOT in `aitasks/archived/` — it's still active. If a parent IS in archived, all children are done, so it CAN be zipped.

### Rule 2: Dependency of an active task
If an active task's `depends` field references task ID X, keep X's archived task+plan files.
- Scan all active task files in `aitasks/` and `aitasks/t*/` for `depends:` frontmatter
- Parse formats: `depends: ['130']`, `depends: [t143_1]`, `depends: [129_1]`, `depends: [t85_10, t85_9]`
- Normalize to numeric form (e.g., `130`, `129_1`, `85_10`)
- Keep referenced archived files uncompressed

Everything else → archive to `old.tar.gz`.

## Implementation Plan

### Step 1: Add `get_active_parent_numbers()` function

Scans `aitasks/t*/` directories, returns space-separated list of parent numbers that have active children.

### Step 2: Add `get_dependency_task_ids()` function

Scans all active task files for `depends:` frontmatter line. Parses the YAML list format (handles `['130']`, `[t143_1]`, `[129_1]`). Strips `t` prefix and quotes. Returns space-separated list of referenced task IDs. Note: only scan active task files (not archived ones).

### Step 3: Add `is_parent_active()` and `is_dependency()` helpers

Simple membership checks against the sets from steps 1 and 2.

### Step 4: Replace selection logic in `main()`

Replace the current steps 1-2b with new logic:

**For parent task files** (`aitasks/archived/t*_*.md`):
- Extract parent number from filename
- If `is_dependency(parent_num)` → skip (keep uncompressed)
- Otherwise → add to archive list

**For child task directories** (`aitasks/archived/t*/`):
- Extract parent number from directory name
- If `is_parent_active(parent_num)` → skip entire directory
- Otherwise, for each child file:
  - Extract child task ID (e.g., `10_2`)
  - If `is_dependency(child_id)` → skip individual file
  - Otherwise → add to archive list

Same logic for plan files with `p` prefix and `aiplans/archived/`.

### Step 5: Update dry-run output

Show:
- "Skipping (active siblings): t129/" for rule 1
- "Skipping (dependency of active task): t97_added_features.md" for rule 2
- Regular "Will archive: t85_universal_install.md" for archivable files

### Step 6: Update git commit message

Replace the old "Kept most recent: ..." with listing skipped parent numbers.

### Step 7: Update usage/help text

Remove "keeping only the most recent", describe the new safety-aware selection.

### Step 8: Remove old functions

Delete `find_most_recent()`, `find_most_recent_child()`, `get_files_to_archive()`, `get_child_files_to_archive()`, and `KEEP_TASK`/`KEEP_PLAN` variables.

### Step 9: Create tests/test_zip_old.sh

Test cases (19 total):
1. Empty archived dirs — nothing to do
2. All parent tasks archived, no active children — all get archived
3. Active parent skips its archived children
4. Archived parent task with all children done gets archived (not a dependency)
5. Inactive parent's children get archived
6. Plan files follow same logic
7. Mixed scenario (some active, some inactive parents)
8. Actual archive creation — verify tar.gz contents and file removal
9. Cumulative archiving — run twice, verify accumulation
10. Git commit message content
11. Empty child dirs cleaned up after archiving
12. No-commit flag works
13. Verbose output content
14. Syntax check
15. Dependency keeps archived task (depends: ['30'])
16. Dependency keeps archived plan
17. Dependency keeps archived child task (deps + active parent)
18. No dependency — archived task gets archived
19. Multiple depends formats parsed correctly

## Verification Steps

- `bash -n aiscripts/aitask_zip_old.sh` (syntax check)
- `bash tests/test_zip_old.sh` (run all 19 tests)
- `./ait zip-old --dry-run` on the real project — verify t129/ and t143/ children skipped, other files listed for archival
- `./ait zip-old --dry-run -v` for detailed output verification
