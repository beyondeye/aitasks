---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: []
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-15 14:32
updated_at: 2026-03-15 14:48
completed_at: 2026-03-15 14:48
---

## Problem

The `/aitask-contribution-review` skill has two reliability issues:

### 1. No `list-issues` subcommand — Claude uses `gh` directly when no issue number is provided

When the skill is invoked without an `<issue_number>` argument, Claude improvises by calling `gh issue list` directly. This breaks on GitLab and Bitbucket remotes because `gh` is GitHub-specific.

The platform-encapsulated function `source_list_contribution_issues()` already exists in `aitask_contribution_check.sh` (which is sourced by `aitask_contribution_review.sh`) with backends for all three platforms (`github_list_contribution_issues`, `gitlab_list_contribution_issues`, `bitbucket_list_contribution_issues`), but it's not exposed as a subcommand in the review script.

### 2. No guard against re-importing already-imported issues

`aitask_issue_import.sh` has `check_duplicate_import()` that searches `issue:` frontmatter in both active and archived task files. However, the contribution-review SKILL.md has no check before proceeding with the workflow. For example, issue #9 was already imported as task t387, but the review workflow didn't detect this and proceeded with the full review.

## Fix

### Part A: Add `list-issues` subcommand to `aitask_contribution_review.sh`

Add a new subcommand `list-issues` that calls `source_list_contribution_issues()` and outputs structured lines:

```
@@@ISSUE:<num>@@@
TITLE:<title>
CONTRIBUTOR:<author>
HAS_METADATA:true|false
```

This reuses the existing platform-encapsulated backends. No new platform code needed.

### Part B: Update SKILL.md for the no-argument case

Add a new step before Step 1 (or modify Step 1) that handles the case when no `<issue_number>` is provided:

1. Run `./.aitask-scripts/aitask_contribution_review.sh list-issues` to get open contribution issues
2. Present the list to the user via `AskUserQuestion` (issue number as label, title as description)
3. Use the selected issue number to proceed with the normal Step 1

### Part C: Add `check-imported` subcommand to `aitask_contribution_review.sh`

Add a new subcommand `check-imported <issue_number>` that checks if the issue URL is already present in an existing task's `issue:` frontmatter (reusing the `check_duplicate_import` pattern from `aitask_issue_import.sh`). Output:

```
IMPORTED:<task_file_path>
```
or
```
NOT_IMPORTED
```

### Part D: Update SKILL.md with duplicate import guard

Add a check right after Step 1 (after fetching the issue):

1. Run `./.aitask-scripts/aitask_contribution_review.sh check-imported <issue_number>`
2. If `IMPORTED:<path>` is returned, inform the user: "Issue #N has already been imported as task tXXX (<path>)."
3. Use `AskUserQuestion` to ask whether to proceed anyway or abort.

## Files to modify

- `.aitask-scripts/aitask_contribution_review.sh` — Add `list-issues` and `check-imported` subcommands
- `.claude/skills/aitask-contribution-review/SKILL.md` — Add no-argument handling and duplicate import guard

## Reference

- `aitask_contribution_check.sh:117-121` — `github_list_contribution_issues()` (existing platform backend)
- `aitask_contribution_check.sh:209-231` — `gitlab_list_contribution_issues()` (existing platform backend)
- `aitask_contribution_check.sh:333-347` — `bitbucket_list_contribution_issues()` (existing platform backend)
- `aitask_issue_import.sh:479-489` — `check_duplicate_import()` (existing duplicate detection logic)
