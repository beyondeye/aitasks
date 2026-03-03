---
Task: t301_fix_folded_task_handling_in_child_and_transitive_archival.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix Folded Task Handling in Child and Transitive Archival (t301)

## Context

When t268_8 (a child task with `folded_tasks: [289]`) was archived, t289 was never deleted because `archive_child()` in `aitask_archive.sh` never calls `handle_folded_tasks()`. Similarly, when the parent t268 was auto-archived (all children complete), it also skipped `handle_folded_tasks()`. This bug, along with several edge cases and documentation inconsistencies, needs fixing.

## Changes

### 1. Issue 1 — Child archival skips folded task cleanup
**File:** `aiscripts/aitask_archive.sh`, `archive_child()` (~line 396)

Add `handle_folded_tasks "$task_id" "$child_task_file"` after releasing the child lock (line 396) and before the "Check if all children are complete" section (line 398).

- [x] Done

### 2. Issue 2 — Parent auto-archival skips folded task cleanup
**File:** `aiscripts/aitask_archive.sh`, `archive_child()` (~line 428)

Add `handle_folded_tasks "$parent_num" "$parent_task_file"` inside the `if [[ -z "$remaining_children" ]]` block, before `archive_metadata_update "$parent_task_file"` (line 429).

- [x] Done

### 3. Issue 3 — Outdated SKILL.md note
**File:** `.claude/skills/task-workflow/SKILL.md`, line 503

Replace outdated note about child archival not needing folded task handling.

- [x] Done

### 4. Issue 4 — Transitive folding creates orphans
**File:** `.claude/skills/aitask-fold/SKILL.md`, Step 3d

Add a transitive folded tasks handling sub-step between 3d and 3e.

- [x] Done

### 5. Issue 5 — `handle_folded_tasks()` resolves files by top-level glob only
**File:** `aiscripts/aitask_archive.sh`, `handle_folded_tasks()` (~lines 288, 326)

Replace top-level-only glob with logic handling both parent and child task IDs.

- [x] Done

### 6. Issue 6 — Documentation inconsistency in explore skill
**File:** `.claude/skills/aitask-explore/SKILL.md`, lines 155 and 260

Change example `[106, 129_5]` to `[106, 129]`.

- [x] Done

### 7. New test file
**File:** `tests/test_archive_folded.sh`

Create tests for child archival with folded tasks, parent auto-archival with folded tasks, and child task ID resolution.

- [x] Done

## Verification

1. `shellcheck aiscripts/aitask_archive.sh` — only pre-existing SC1091/SC2012 informational messages
2. `bash tests/test_archive_folded.sh` — 8/8 passed
3. `bash tests/test_draft_finalize.sh` — 35/35 passed
4. Step 9 (archival, push)

## Final Implementation Notes
- **Actual work done:** All 6 issues fixed plus test file created, as planned
- **Deviations from plan:** The `handle_folded_tasks` call in `archive_child()` was placed BEFORE `archive_metadata_update`/`archive_move` (not after `release_lock` as initially planned) — the file path becomes stale after `archive_move`, consistent with how `archive_parent()` calls it before the move
- **Issues encountered:** Initial test placement of `handle_folded_tasks` after `release_lock` caused the function to read a moved file path; fixed by moving the call earlier in the flow. Test subshell `(cd ...)` prevented counter propagation; fixed with `pushd/popd`
- **Key decisions:** Used inline child-ID-aware resolution rather than `resolve_task_file()` because the latter calls `die()` on missing files, while `handle_folded_tasks()` needs to silently skip already-deleted tasks
