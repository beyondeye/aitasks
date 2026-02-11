---
Task: t53_6_update_github_issue_after_task_impl.md
Parent Task: aitasks/t53_import_gh_issue_as_task.md
Sibling Tasks: aitasks/t53/t53_5_*.md
Archived Sibling Plans: aiplans/archived/p53/p53_*_*.md
Branch: main
Base branch: main
---

# Plan: Create `aitask_issue_update.sh` + Update t53_5 (t53_6)

## Context

This task creates a new bash script that updates/closes GitHub issues after task implementation, and updates sibling task t53_5 to use it. The script reads a task's `issue` metadata field, auto-detects associated git commits, extracts "Final Implementation Notes" from the plan file, and posts an update comment on the linked issue via `gh` CLI. It follows the same platform abstraction pattern as `aitask_import.sh`.

## Files to Create/Modify

1. **`aitask_issue_update.sh`** (NEW) - Main script (~250 lines)
2. **`aitasks/t53/t53_5_auto_close_issue_on_task_completion.md`** - Update depends + rewrite implementation plan

## Implementation Steps

### Step 1: Create `aitask_issue_update.sh`

- [x] Script skeleton with header, constants, colors, helpers
- [x] Platform backend functions (GitHub)
- [x] Dispatcher layer
- [x] Task/plan resolution functions
- [x] Core logic (detect_commits, build_comment_body, run_update)
- [x] Argument parsing + help
- [x] Make executable

### Step 2: Update t53_5 task file

- [x] Change depends to include t53_6
- [x] Update context section
- [x] Rewrite implementation plan to use aitask_issue_update.sh

## Comment Format

The GitHub issue comment follows this structure:
1. Header: "Resolved via aitask t<N>"
2. Plan file reference (prominent): "Full implementation details: `<archived_plan_path>`"
3. Full "Final Implementation Notes" section from the plan file
4. Associated commits in a code block

## Verification

1. `./aitask_issue_update.sh --help` - verify help text
2. `./aitask_issue_update.sh --dry-run 84` - verify with t84 which has issue field
3. Test with task without issue field - verify clear error
4. Test `--commits` override

## Final Implementation Notes
- **Actual work done:** Created `aitask_issue_update.sh` (~310 lines) with full platform abstraction following `aitask_import.sh` conventions. Script supports `--close`, `--no-comment`, `--commits` override, and `--dry-run` flags. Resolves task files and plan files from both active and archived directories. Auto-detects associated commits from git log by searching for task ID in commit messages. Builds GitHub issue comments with plan file reference, Final Implementation Notes section, and commit list. Also updated sibling t53_5 to depend on t53_6 and rewrote its implementation plan to use `aitask_issue_update.sh` instead of inline `gh` commands.
- **Deviations from plan:** None significant. Script came out at ~310 lines instead of estimated ~250 due to comprehensive help text and comment formatting.
- **Issues encountered:** None. The existing patterns from `aitask_import.sh` and `aitask_update.sh` were straightforward to adapt.
- **Key decisions:** Used `gh issue close --comment` for atomic close+comment in a single API call. Plan file reference is placed prominently first in the comment body (before implementation notes). Parent task commit detection uses regex `t<N>[^0-9_]` to avoid matching child task commits.
- **Notes for sibling tasks:** The `aitask_issue_update.sh` script is ready to be called from the aitask-pick workflow (t53_5). Usage: `./aitask_issue_update.sh --close <task_num>` to close with full implementation notes, or `./aitask_issue_update.sh <task_num>` for comment-only. The script reads the `issue` field from the task's YAML frontmatter and resolves plan files automatically.

## Post-Implementation

Follow Step 9 of aitask-pick workflow for archival.
