---
Task: t260_5_pr_close_archive_integration.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_1_*.md through t260_7_*.md
Archived Sibling Plans: aiplans/archived/p260/p260_1_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: PR Close/Decline in Archive Workflow (t260_5)

## Overview

Integrate PR closing/declining into the task archive workflow, parallel to the existing issue close integration. Create a new `aitask_pr_close.sh` script and update the archive script and skill workflow.

## Steps

### 1. Add `extract_pr_url()` usage to `aiscripts/aitask_archive.sh`

After the existing `ISSUE:` output block (~line 209):

```bash
local pr_url
pr_url=$(extract_pr_url "$task_file")
if [[ -n "$pr_url" ]]; then
    echo "PR:$task_num:$pr_url"
fi
```

Also in the folded task loop, after `FOLDED_ISSUE:`:
```bash
local folded_pr_url
folded_pr_url=$(extract_pr_url "$folded_file")
if [[ -n "$folded_pr_url" ]]; then
    echo "FOLDED_PR:$folded_task_id:$folded_pr_url"
fi
```

### 2. Create `aiscripts/aitask_pr_close.sh`

New script following `aitask_issue_update.sh` pattern:

**Structure:**
- Shebang, set -euo pipefail, source libraries
- Platform backends: `github_close_pr()`, `gitlab_close_pr()`, `bitbucket_close_pr()`
- Comment generation: `build_pr_close_comment()`
- PR number extraction from URL: `extract_pr_number_from_url()`
- Main logic: parse args, detect platform, resolve plan file, detect commits, build comment, post/close

**Platform backends:**

```bash
github_close_pr() {
    local pr_num="$1" comment="$2"
    if [[ -n "$comment" ]]; then
        gh pr close "$pr_num" --comment "$comment"
    else
        gh pr close "$pr_num"
    fi
}

gitlab_close_pr() {
    local mr_num="$1" comment="$2"
    if [[ -n "$comment" ]]; then
        glab mr note "$mr_num" -m "$comment"
    fi
    glab mr close "$mr_num"
}

bitbucket_close_pr() {
    local pr_num="$1" comment="$2"
    if [[ -n "$comment" ]]; then
        bkt pr comment "$pr_num" -b "$comment"
    fi
    bkt pr decline "$pr_num"
}
```

**Comment body:**
```markdown
## Resolved via aitask t{TASK_ID}

This pull request was reviewed through the aitask workflow. While the PR was not merged directly, the ideas and approach were incorporated into the implementation.

**Full implementation details:** `{plan_file_path}`

### Implementation Notes
{Final Implementation Notes from plan}

### Associated Commits
\`\`\`
{commit_hash} {commit_message}
\`\`\`

Thank you for your contribution, @{contributor}!
```

**CLI flags:**
- `TASK_NUM` (positional)
- `--pr-url URL` — override task file lookup
- `--source PLATFORM` — force platform
- `--close` — close/decline (default)
- `--no-comment` — close without comment
- `--dry-run` — preview only
- `--commits RANGE` — override commit detection

### 3. Update `task-workflow/SKILL.md` Step 9

Add `PR:` handling after the existing `ISSUE:` handling block:

```markdown
- `PR:<task_num>:<pr_url>` — Execute the **PR Close/Decline Procedure** (see `procedures.md`)
- `FOLDED_PR:<folded_task_num>:<pr_url>` — Handle inline:
  - AskUserQuestion: "Folded task t<N> had a linked PR: <pr_url>. Close/decline it?"
  - Options: "Close with notes" / "Comment only" / "Close silently" / "Skip"
  - Execute appropriate aitask_pr_close.sh command
```

### 4. Add PR Close/Decline Procedure to `procedures.md`

```markdown
### PR Close/Decline Procedure

When the archive script outputs `PR:<task_num>:<pr_url>`:

1. AskUserQuestion:
   - "Task t<N> has a linked PR: <pr_url>. What should happen to it?"
   - Options: "Close/decline with notes" / "Comment only" / "Close/decline silently" / "Skip"

2. Execute:
   - Close with notes: `./aiscripts/aitask_pr_close.sh --close <task_id>`
   - Comment only: `./aiscripts/aitask_pr_close.sh <task_id>` (no --close)
   - Close silently: `./aiscripts/aitask_pr_close.sh --close --no-comment <task_id>`
   - Skip: do nothing
```

### 5. Register `pr-close` in `ait` dispatcher

```bash
pr-close)   shift; exec "$SCRIPTS_DIR/aitask_pr_close.sh" "$@" ;;
```

## Verification

1. Create + archive a task with `pull_request:` — verify `PR:` output line
2. `./ait pr-close --dry-run <task_num>` — verify comment preview
3. Test with folded tasks having PR metadata
4. `shellcheck aiscripts/aitask_pr_close.sh`
5. End-to-end: `/aitask-pick` → implement → archive → verify PR close prompt

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_5`
