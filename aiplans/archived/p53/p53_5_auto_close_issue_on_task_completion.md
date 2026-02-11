---
Task: t53_5_auto_close_issue_on_task_completion.md
Parent Task: aitasks/t53_import_gh_issue_as_task.md
Sibling Tasks: aitasks/t53/t53_5_*.md
Archived Sibling Plans: aiplans/archived/p53/p53_*_*.md
Branch: main
Base branch: main
---

# Plan: Add issue update/close to aitask-pick Step 9 (t53_5)

## Context

When a task has a linked issue URL in its `issue` metadata field, the aitask-pick workflow should offer to update/close that issue during post-implementation (Step 9). The workflow in SKILL.md is platform-agnostic — it only checks for the `issue` field and calls `aitask_issue_update.sh`. All platform-specific logic (GitHub, GitLab, Bitbucket, etc.) is handled by the bash script itself.

## File to Modify

- `.claude/skills/aitask-pick/SKILL.md` — Add issue update sub-steps to Step 9

## Changes

### 1. Add issue update block for child tasks (Step 9, lines ~545-546)

Insert after "Archive the child plan file" block and before "Check if all children complete". The new sub-step.

### 2. Add issue update block for parent tasks (Step 9, lines ~589-593)

Insert after "Archive the plan file" block and before "Commit archived files to git". Same logic but using parent task num.

### 3. Add issue update for parent task when all children complete (Step 9, lines ~563-566)

When all children are done and the parent is also being archived, insert the same issue update block after archiving the parent plan file and before the final commit. This checks the **parent** task's `issue` field.

### 4. Add note to Notes section (line ~661)

## Verification

1. Read the modified SKILL.md and verify the issue update blocks are correctly placed
2. Verify the script invocations match `aitask_issue_update.sh` usage: `--close`, `--no-comment`, plain
3. Verify issue update appears in all three archival paths: child, parent, and parent-when-all-children-complete
4. Follow Step 9 of aitask-pick workflow for archival of this task

## Final Implementation Notes
- **Actual work done:** Added an "Issue Update Procedure" section to SKILL.md (defined once, between Abort Handling and Notes) and referenced it with one-liners from 3 locations in Step 9: child task archival, parent-when-all-children-complete archival, and standalone parent task archival. Also added a note to the Notes section about the feature.
- **Deviations from plan:** Initially implemented with the full procedure duplicated 3 times (78 insertions). After user feedback about unnecessary duplication, refactored to define-once-reference-thrice pattern (35 insertions).
- **Issues encountered:** None.
- **Key decisions:** The procedure is platform-agnostic in SKILL.md — it only checks for the `issue` field and delegates to `aitask_issue_update.sh` which handles platform specifics.
- **Notes for sibling tasks:** This was the last remaining child task for t53. The `issue` field workflow is now complete: bash scripts support it (t53_1), board UI shows it (t53_2), import creates it (t53_3/t53_4), issue gets updated after implementation (t53_6), and the aitask-pick workflow triggers the update during archival (t53_5).
