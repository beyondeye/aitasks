---
Task: t260_3_create_pr_import_script.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_1_*.md through t260_7_*.md
Archived Sibling Plans: aiplans/archived/p260/p260_1_*.md, aiplans/archived/p260/p260_2_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Create aitask_pr_import.sh (t260_3)

## Overview

Create the core PR data extraction script following `aitask_issue_import.sh`'s dispatcher architecture. This is the largest child task — expected ~800-1200 lines.

## Steps

### 1. Create script skeleton

Create `aiscripts/aitask_pr_import.sh`:
- Shebang: `#!/usr/bin/env bash`
- `set -euo pipefail`
- Source `lib/terminal_compat.sh` and `lib/task_utils.sh`
- Define `PR_DATA_DIR=".aitask-pr-data"`

### 2. Implement `parse_args()`

All CLI flags (see task description for full list):
- `--batch`, `--pr NUM`, `--range START-END`, `--all`
- `--data-only`, `--source PLATFORM`
- `--priority`, `--effort`, `--type`, `--status`, `--labels`
- `--skip-duplicates`, `--commit`, `--silent`
- `--max-diff-lines N` (default 5000), `--no-diff`, `--no-reviews`
- `--list` (just output PR listing for skill to parse)

### 3. Implement GitHub backend functions

- `github_check_cli()` — `gh auth status`
- `github_fetch_pr()` — `gh pr view $num --json title,body,author,labels,url,comments,createdAt,updatedAt,headRefName,baseRefName,state,additions,deletions,changedFiles`
- `github_fetch_pr_diff()` — `gh pr diff $num`
- `github_fetch_pr_reviews()` — `gh api repos/{owner}/{repo}/pulls/${num}/reviews`
- `github_fetch_pr_review_comments()` — `gh api repos/{owner}/{repo}/pulls/${num}/comments`
- `github_list_prs()` — `gh pr list --state open --limit 500 --json number,title,labels,url,author`
- `github_extract_pr_author()` — `jq -r '.author.login'`
- `github_resolve_contributor_email()` — Fetch user ID via `gh api users/<username> --jq '.id'`, construct `<id>+<username>@users.noreply.github.com`

### 4. Implement GitLab backend functions

- `gitlab_check_cli()` — `glab auth status`
- `gitlab_fetch_pr()` — `glab mr view $num -F json` + normalize to GitHub-compatible JSON with jq
- `gitlab_fetch_pr_diff()` — `glab mr diff $num`
- `gitlab_fetch_pr_reviews()` — `glab api projects/:fullpath/merge_requests/${num}/notes?sort=asc&per_page=100`
- `gitlab_list_prs()` — `glab mr list --all --output json`
- `gitlab_resolve_contributor_email()` — `glab api users?username=<name> --jq '.[0].id'`, construct `<id>+<username>@noreply.gitlab.com`

### 5. Implement Bitbucket backend functions

- `bitbucket_check_cli()` — `bkt auth status`
- `bitbucket_fetch_pr()` — `bkt pr view $num --json`
- `bitbucket_fetch_pr_diff()` — `bkt pr diff $num`
- `bitbucket_list_prs()` — `bkt pr list --json`
- Bitbucket contributor email: fall back to username-based format (no standard noreply scheme)

### 6. Implement source dispatcher functions

```bash
source_fetch_pr() { "${PLATFORM}_fetch_pr" "$@"; }
source_fetch_pr_diff() { "${PLATFORM}_fetch_pr_diff" "$@"; }
source_fetch_pr_reviews() { "${PLATFORM}_fetch_pr_reviews" "$@"; }
source_list_prs() { "${PLATFORM}_list_prs" "$@"; }
source_resolve_contributor_email() { "${PLATFORM}_resolve_contributor_email" "$@"; }
```

### 7. Implement intermediate data file generation

`write_pr_data_file()`:
- Create `$PR_DATA_DIR/` if needed
- Write YAML frontmatter with PR metadata
- Write markdown body with sections: Description, Comments, Reviews, Inline Review Comments, Changed Files, Diff
- Truncate diff at `--max-diff-lines` with warning

### 8. Implement comment/review formatting

- `format_pr_comments()` — Same pattern as `github_format_comments()` in issue import
- `format_pr_reviews()` — Format review comments with state (APPROVED, CHANGES_REQUESTED, etc.)
- `format_inline_review_comments()` — Format with file path, line number, comment body

### 9. Implement duplicate detection

```bash
check_duplicate_pr_import() {
    local pr_num="$1" url_pattern="$2"
    grep -rl "^pull_request:.*${url_pattern}$" "$TASK_DIR"/ "$ARCHIVED_DIR"/ 2>/dev/null
}
```

### 10. Implement task creation (non-data-only mode)

Pipe description to `aitask_create.sh --batch` with `--pull-request`, `--contributor`, `--contributor-email` flags.

### 11. Implement interactive mode

fzf-based menu:
1. Import specific PR (enter number)
2. Fetch open PRs and choose (multi-select with preview)
3. Import PR range
4. Import all open PRs

### 12. Implement batch mode entry point

`run_batch_mode()` function handling all batch flags.

### 13. Register in `ait` dispatcher

Add `pr-import)` case in `ait` script.

### 14. Update `.gitignore`

Add `.aitask-pr-data/` entry.

## Key Design Decisions

- Intermediate data uses markdown with YAML frontmatter (not JSON) for human readability
- Diff truncation default: 5000 lines (configurable via `--max-diff-lines`)
- Contributor email resolved during import (not deferred to commit time)
- `--list` flag outputs structured PR list for skill parsing
- `--data-only` writes intermediate file without creating task (for skill use)

## Verification

1. `./ait pr-import --batch --pr 1 --data-only` — verify intermediate file
2. `./ait pr-import --batch --pr 1 --commit` — verify task creation
3. `./ait pr-import` — verify interactive mode
4. `shellcheck aiscripts/aitask_pr_import.sh`
5. `git check-ignore .aitask-pr-data/test.md` — verify gitignore

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_3`
