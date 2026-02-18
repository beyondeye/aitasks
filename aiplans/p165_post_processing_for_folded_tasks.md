---
Task: t165_post_processing_for_folded_tasks.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Folded tasks with linked GitHub issues don't get their issues updated during post-implementation archival. In `aitask_archive.sh`, `handle_folded_tasks()` extracts the issue URL and outputs `FOLDED_ISSUE:<folded_id>:<url>`, then deletes the task file with `git rm`. When the SKILL.md workflow later calls `aitask_issue_update.sh <folded_id>`, the script tries to `resolve_task_file()` which dies because the file was deleted (not archived/moved).

For ISSUE and PARENT_ISSUE, task files are moved to `aitasks/archived/` so `resolve_task_file()` finds them. For folded tasks, they're deleted entirely — that's the gap.

## Plan

### 1. Add `--issue-url <url>` flag to `aitask_issue_update.sh`

**File:** `aiscripts/aitask_issue_update.sh`

- Add global variable: `ISSUE_URL_OVERRIDE=""`
- Add to `parse_args()`: `--issue-url) ISSUE_URL_OVERRIDE="$2"; shift 2 ;;`
- Modify `run_update()` to bypass task file resolution when `--issue-url` is provided:
  - Skip `resolve_task_file()` and `extract_issue_url()`
  - Use `ISSUE_URL_OVERRIDE` directly as the issue URL
  - TASK_NUM is still required for commit detection (`detect_commits`), plan file resolution (`resolve_plan_file`), and comment header
- Update help text to document the new flag

### 2. Update SKILL.md FOLDED_ISSUE handling in Step 9

**File:** `.claude/skills/task-workflow/SKILL.md`

Replace the current `FOLDED_ISSUE` line in the output parsing section with inline handling that:
- Uses `AskUserQuestion` with the same options as the Issue Update Procedure
- Passes `--issue-url <issue_url>` from the output line
- Uses the **primary task's ID** as TASK_NUM so commits and plan reference the actual implementation
- Commands:
  - Close with notes: `./aiscripts/aitask_issue_update.sh --issue-url "<url>" --close <task_id>`
  - Comment only: `./aiscripts/aitask_issue_update.sh --issue-url "<url>" <task_id>`
  - Close silently: `./aiscripts/aitask_issue_update.sh --issue-url "<url>" --close --no-comment <task_id>`

### 3. No changes needed to `aitask_archive.sh`

## Verification

1. Run `./aiscripts/aitask_issue_update.sh --issue-url "https://github.com/test/repo/issues/1" --dry-run 165` to verify the `--issue-url` flag bypasses task file resolution
2. Verify `--issue-url` appears in `./aiscripts/aitask_issue_update.sh --help`

## Final Implementation Notes
- **Actual work done:** Added `--issue-url` flag to `aitask_issue_update.sh` and updated SKILL.md FOLDED_ISSUE handling — exactly as planned.
- **Deviations from plan:** None.
- **Issues encountered:** None — the fix was straightforward.
- **Key decisions:** Used the primary task ID (not folded task ID) as TASK_NUM when calling `aitask_issue_update.sh` for folded tasks, so the comment references the primary task's commits and plan file.

## Step 9 (Post-Implementation)

Reference to task-workflow SKILL.md for cleanup, archival, and merge steps.
