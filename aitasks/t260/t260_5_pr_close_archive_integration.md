---
priority: medium
effort: medium
depends: [t260_4]
issue_type: feature
status: Ready
labels: [bash_scripts, skills]
created_at: 2026-03-01 15:32
updated_at: 2026-03-01 15:32
---

## Context

This is child task 5 of the "Create aitasks from Pull Requests" feature (t260). When a task that originated from a PR is completed and archived, the original PR should be closed/declined with a comment explaining that the ideas were incorporated via the aitask workflow.

**Why this task is needed:** Currently, the archive workflow handles issue closing via `aitask_issue_update.sh` and structured `ISSUE:` output lines. We need the same pattern for PRs: the archive script outputs `PR:` lines, the skill workflow parses them, and a new script handles the actual PR close/decline on the platform.

**Depends on:** t260_1 (metadata fields must exist)

## Key Files to Create/Modify

1. **Create `aiscripts/aitask_pr_close.sh`** — New script (~300-400 lines)
   - Platform backends for closing/declining PRs
   - Comment generation with implementation notes

2. **Modify `aiscripts/aitask_archive.sh`** (~350 lines)
   - Add `pull_request:` extraction and `PR:` output (parallel to `ISSUE:` output)

3. **Modify `.claude/skills/task-workflow/SKILL.md`** (~450 lines)
   - Add `PR:` structured output handling in Step 9

4. **Modify `.claude/skills/task-workflow/procedures.md`**
   - Add "PR Close/Decline Procedure"

5. **Modify `ait`** (dispatcher script)
   - Add `pr-close)` command case

## Reference Files for Patterns

- **`aiscripts/aitask_issue_update.sh`** (~350 lines) — PRIMARY REFERENCE for the close script. Shows:
  - Platform dispatcher pattern for posting comments and closing
  - `github_close_issue()`, `gitlab_close_issue()`, `bitbucket_close_issue()`
  - Comment body generation with implementation notes and commit list
  - `--close`, `--no-comment`, `--dry-run` flags
  - `extract_final_implementation_notes()` for plan file content

- **`aiscripts/aitask_archive.sh`** (~350 lines) — Shows:
  - How `ISSUE:` output lines are generated (around line 209)
  - How `FOLDED_ISSUE:` lines are emitted for deleted folded tasks
  - The structured output format the skill parses

- **`.claude/skills/task-workflow/SKILL.md`** Step 9 — Shows:
  - How `ISSUE:` lines are parsed and handled
  - The AskUserQuestion flow for issue update decisions
  - Commands for issue update/close

- **`.claude/skills/task-workflow/procedures.md`** — Shows:
  - "Issue Update Procedure" format to replicate for PRs

## Implementation Plan

### Part 1: Create `aitask_pr_close.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"

# Platform backends:

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
        # GitLab: post note first, then close (glab mr close doesn't support --comment)
        glab issue note "$mr_num" -m "$comment"  # Note: use mr note if available
        glab mr close "$mr_num"
    else
        glab mr close "$mr_num"
    fi
}

bitbucket_close_pr() {
    local pr_num="$1" comment="$2"
    if [[ -n "$comment" ]]; then
        bkt pr comment "$pr_num" -b "$comment"
    fi
    bkt pr decline "$pr_num"  # Bitbucket uses "decline" not "close"
}
```

**Comment body format:**
```markdown
## Resolved via aitask t{TASK_ID}

This pull request was reviewed through the aitask workflow. While the PR was not merged directly, the ideas and approach were incorporated into the implementation.

**Full implementation details:** `{plan_file_path}`

### Implementation Notes
{Extracted from ## Final Implementation Notes section of plan}

### Associated Commits
```
{commit_hash} {commit_message}
```

Thank you for your contribution, @{contributor}!
```

**CLI flags:**
```
TASK_NUM              Required positional arg
--pr-url URL          Override task file lookup (for folded tasks)
--source PLATFORM     Force platform detection
--close               Close/decline the PR (default behavior)
--no-comment          Close without posting comment
--dry-run             Preview comment without posting
--commits RANGE       Override commit detection
```

**PR number extraction from URL:**
```bash
extract_pr_number_from_url() {
    local url="$1"
    # GitHub: .../pull/42 → 42
    # GitLab: .../merge_requests/42 → 42
    # Bitbucket: .../pull-requests/42 → 42
    echo "$url" | grep -oE '[0-9]+$'
}
```

### Part 2: Modify `aitask_archive.sh`

After the existing `ISSUE:` output block (around line 209), add:
```bash
local pr_url
pr_url=$(extract_pr_url "$task_file")
if [[ -n "$pr_url" ]]; then
    echo "PR:$task_num:$pr_url"
fi
```

Also handle folded tasks with PR URLs (same pattern as `FOLDED_ISSUE:`):
```bash
# In the folded task deletion loop:
local folded_pr_url
folded_pr_url=$(extract_pr_url "$folded_file")
if [[ -n "$folded_pr_url" ]]; then
    echo "FOLDED_PR:$folded_task_id:$folded_pr_url"
fi
```

### Part 3: Update task-workflow SKILL.md Step 9

In Step 9, after the existing `ISSUE:` handling block, add parallel handling for `PR:` lines:

```
- `PR:<task_num>:<pr_url>` — Execute the **PR Close/Decline Procedure** (see `procedures.md`) for the task
- `FOLDED_PR:<folded_task_num>:<pr_url>` — Handle inline (same pattern as FOLDED_ISSUE but for PRs)
```

The AskUserQuestion for PR close should offer:
- "Close/decline with notes" — Post implementation notes and close
- "Comment only" — Post notes but leave open
- "Close/decline silently" — Close without comment
- "Skip" — Don't touch the PR

### Part 4: Add PR Close/Decline Procedure to procedures.md

Model after the "Issue Update Procedure":

```markdown
### PR Close/Decline Procedure

When the archive script outputs `PR:<task_num>:<pr_url>`:

1. Use `AskUserQuestion`:
   - Question: "Task t<N> has a linked PR: <pr_url>. What should happen to it?"
   - Header: "PR"
   - Options:
     - "Close/decline with notes" (description: "Post implementation notes and close/decline the PR")
     - "Comment only" (description: "Post implementation notes but leave PR open")
     - "Close/decline silently" (description: "Close/decline without posting a comment")
     - "Skip" (description: "Don't touch the PR")

2. Execute based on selection:
   - "Close with notes": `./aiscripts/aitask_pr_close.sh --close <task_id>`
   - "Comment only": `./aiscripts/aitask_pr_close.sh <task_id>` (comment without close)
   - "Close silently": `./aiscripts/aitask_pr_close.sh --close --no-comment <task_id>`
   - "Skip": do nothing
```

### Part 5: Register in ait dispatcher

```bash
pr-close)   shift; exec "$SCRIPTS_DIR/aitask_pr_close.sh" "$@" ;;
```

## Verification Steps

1. **Create and archive a task with PR metadata:**
   ```bash
   echo "Test PR close" | ./aiscripts/aitask_create.sh --batch --name "test_pr_close" \
     --pull-request "https://github.com/owner/repo/pull/42" \
     --contributor "octocat" \
     --contributor-email "12345+octocat@users.noreply.github.com" \
     --desc-file - --commit
   
   # Set to Done status
   ./ait update --batch <task_num> --status Done
   
   # Archive and verify PR: output
   ./aiscripts/aitask_archive.sh <task_num>  # Should output PR:<num>:<url>
   ```

2. **Test pr-close script dry-run:**
   ```bash
   ./ait pr-close --dry-run <task_num>  # Should show comment without posting
   ```

3. **Run shellcheck:**
   ```bash
   shellcheck aiscripts/aitask_pr_close.sh
   ```

4. **Verify skill workflow handles PR: lines:**
   - Run `/aitask-pick` on a PR-originated task
   - Complete implementation and archive
   - Verify PR close prompt appears
