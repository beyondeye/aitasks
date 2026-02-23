---
Task: t144_ait_clear_old_rewrite.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Rewrite ait clear_old → ait zip-old (t144)

## Context

The `aitask_clear_old.sh` script archives old task/plan files from `aitasks/archived/` and `aiplans/archived/` into `old.tar.gz`. Its current selection logic keeps only the most recent file uncompressed (for task numbering), but:

1. **"Keep most recent" is obsolete** — atomic numbering via `aitask_claim_id.sh` replaced local file scanning for parent IDs. Child numbering in `aitask_create.sh` already scans inside tar.gz.
2. **Missing safety checks** — doesn't verify if archived children belong to parents with still-active children. The task workflow reads archived siblings as context when implementing new sibling tasks (e.g., `aitasks/archived/t129/` is read during planning of t129_3+).
3. **Changelog can't find zipped files** — `resolve_task_file()` and `resolve_plan_file()` in `task_utils.sh` don't search inside `old.tar.gz`.
4. **Unclear naming** — rename `clear-old` → `zip-old` for clarity.

## Approach: Split into 3 child tasks

Execution order: Child 1 → Child 2 → Child 3

---

### Child 1: Rename script and update all references

Rename `aitask_clear_old.sh` → `aitask_zip_old.sh`, command `clear-old` → `zip-old`, skill `aitask-cleanold` → `aitask-zipold`.

**Files to change (8):**

| File | Change |
|------|--------|
| `aiscripts/aitask_clear_old.sh` | `git mv` → `aiscripts/aitask_zip_old.sh`, update comment on line 3 |
| `ait` | Line 30: `clear-old` → `zip-old`; Line 109: update dispatch |
| `.claude/skills/aitask-cleanold/` | `git mv` → `.claude/skills/aitask-zipold/`, update SKILL.md content |
| `docs/commands.md` | Lines 14, 30, 339-367: rename `clear-old` → `zip-old` |
| `docs/skills.md` | Lines 14, 28, 233-253: rename `aitask-cleanold` → `aitask-zipold` |
| `seed/claude_settings.local.json` | Line 30: update script name |
| `aitasks/metadata/claude_settings.seed.json` | Line 30: update script name |
| `tests/test_terminal_compat.sh` | Line 232: update script name in syntax check list |

No backward compatibility alias — `clear-old` is only used via skill and CLI.

**Verification:** `bash -n aiscripts/aitask_zip_old.sh`, `ait zip-old --help`, `ait zip-old --dry-run`, `bash tests/test_terminal_compat.sh`

---

### Child 2: Add tar.gz fallback to resolve functions

Update `resolve_task_file()` and `resolve_plan_file()` in `aiscripts/lib/task_utils.sh` to search inside `old.tar.gz` as a final fallback.

**Files to change (1+1 new):** `aiscripts/lib/task_utils.sh`, `tests/test_resolve_tar_gz.sh` (new)

**Approach:**
- Add module-level temp directory with EXIT trap cleanup
- Add `_search_tar_gz()` helper: searches `tar -tzf` listing for a pattern
- Add `_extract_from_tar_gz()` helper: extracts matching file to temp dir, returns temp path
- Add tar.gz fallback step to both `resolve_task_file()` and `resolve_plan_file()` — after checking uncompressed archived dir, before returning not-found
- Handle `./` prefix in tar entries (from `tar -czf ... -C "$temp_dir" .`)

**Callers that benefit (no changes needed to them):**
- `aitask_changelog.sh` — calls resolve functions, reads returned file path
- `aitask_issue_update.sh` — same pattern

---

### Child 3: Rewrite selection logic

Replace "keep most recent" with "keep files still relevant to active work".

**Files to change (1+1 new):** `aiscripts/aitask_zip_old.sh` (after rename from Child 1), `tests/test_zip_old.sh` (new)

**New selection rule — an archived file is "still relevant" if ANY of these hold:**

1. **Archived siblings of active children:** If `aitasks/t<N>/` exists (parent still has active children), keep:
   - All archived children in `aitasks/archived/t<N>/` (sibling context for active children)
   - Corresponding archived plan files in `aiplans/archived/p<N>/`
   - Note: the parent task file itself is NOT in `aitasks/archived/` in this case — it's still active in `aitasks/`. If a parent task IS in `aitasks/archived/`, it means all children completed, so it CAN be zipped (unless rule 2 applies).

2. **Dependency of an active task:** If an active task's `depends` field references task ID X, keep X's archived task file and plan file uncompressed. Active tasks may want to re-read the implementation of tasks that unlocked them.
   - Scan all active task files in `aitasks/` (including `aitasks/t*/`) for `depends:` frontmatter
   - Parse referenced task IDs (formats: `['130']`, `[t143_1]`, `[129_1]`, `[t85_10, t85_9]`)
   - Normalize to numeric form (e.g., `130`, `129_1`, `85_10`)
   - For each referenced ID found in archived dirs, keep it uncompressed

**Everything else gets archived to `old.tar.gz`.** This includes fully-done parent task files and their fully-done children (unless they're dependencies of active tasks).

**Implementation:**
- Add `get_active_parent_numbers()` — scans `aitasks/t*/` directories for parent numbers with active children
- Add `get_dependency_task_ids()` — scans all active task files' `depends:` field, returns set of referenced task IDs
- Add `is_task_relevant()` helper — checks if a task ID is protected by rule 1 (sibling of active child) or rule 2 (dependency of active task)
- Replace `find_most_recent()`, `find_most_recent_child()`, `get_files_to_archive()`, `get_child_files_to_archive()` with new logic
- Remove `KEEP_TASK` / `KEEP_PLAN` variables
- Update dry-run output, git commit message template, usage/help text

**Keep unchanged:** `archive_files()` function, `--dry-run`/`--no-commit`/`--verbose` flags, archive integrity verification, empty dir cleanup.

---

## Automated Tests

Tests follow the project pattern (see `tests/test_task_lock.sh`): isolated temp git repos, assert helpers, self-contained setup/teardown.

### Test file: `tests/test_resolve_tar_gz.sh` (Child 2)

14 test cases covering: resolve from active/archived/tar.gz dirs for parent/child tasks/plans, priority ordering, not-found behavior, temp cleanup, and end-to-end with extract_final_implementation_notes.

### Test file: `tests/test_zip_old.sh` (Child 3)

19 test cases covering: empty dirs, parent-only archival, active parent protection, inactive parent archival, plan files, mixed scenarios, dependency protection (all formats), actual archive creation, cumulative archiving, git commit, empty dir cleanup, no-commit flag, verbose output, and syntax check.

---

## Step 9 (Post-Implementation)

Archive t144 task and plan files per the task-workflow.
