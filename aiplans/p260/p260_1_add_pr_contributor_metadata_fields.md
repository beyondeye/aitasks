---
Task: t260_1_add_pr_contributor_metadata_fields.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_2_*.md, aitasks/t260/t260_3_*.md, aitasks/t260/t260_4_*.md, aitasks/t260/t260_5_*.md, aitasks/t260/t260_6_*.md, aitasks/t260/t260_7_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Add PR/Contributor Metadata Fields (t260_1)

## Overview

Add three new YAML frontmatter fields (`pull_request`, `contributor`, `contributor_email`) to the task management scripts, following the exact pattern used by the existing `issue` field.

## Steps

### 1. Add extraction functions to `aiscripts/lib/task_utils.sh`

Add three functions after `extract_issue_url()` (around line 305):

```bash
extract_pr_url() {
    local file_path="$1"
    # Same pattern as extract_issue_url but for pull_request: field
}

extract_contributor() {
    local file_path="$1"
    # Same pattern but for contributor: field
}

extract_contributor_email() {
    local file_path="$1"
    # Same pattern but for contributor_email: field
}
```

Each function: reads the file, finds the YAML frontmatter block (between `---` markers), greps for the field, trims whitespace, returns value or empty string.

### 2. Modify `aiscripts/aitask_create.sh`

**a) Add global variables** (near line 30, after `BATCH_ISSUE`):
```bash
BATCH_PULL_REQUEST=""
BATCH_CONTRIBUTOR=""
BATCH_CONTRIBUTOR_EMAIL=""
```

**b) Add argument parsing** (in `parse_args()`, near `--issue)` case):
```bash
--pull-request) BATCH_PULL_REQUEST="$2"; shift ;;
--contributor) BATCH_CONTRIBUTOR="$2"; shift ;;
--contributor-email) BATCH_CONTRIBUTOR_EMAIL="$2"; shift ;;
```

**c) Write to YAML in task file creation functions:**
- In `create_task_file()`, `create_child_task_file()`, `create_draft_file()`:
- After the `issue:` conditional block, add:
```bash
[[ -n "$pull_request" ]] && echo "pull_request: $pull_request"
[[ -n "$contributor" ]] && echo "contributor: $contributor"
[[ -n "$contributor_email" ]] && echo "contributor_email: $contributor_email"
```

### 3. Modify `aiscripts/aitask_update.sh`

**a) Add variables:**
```bash
BATCH_PULL_REQUEST=""
BATCH_PULL_REQUEST_SET=false
BATCH_CONTRIBUTOR=""
BATCH_CONTRIBUTOR_SET=false
BATCH_CONTRIBUTOR_EMAIL=""
BATCH_CONTRIBUTOR_EMAIL_SET=false
CURRENT_PULL_REQUEST=""
CURRENT_CONTRIBUTOR=""
CURRENT_CONTRIBUTOR_EMAIL=""
```

**b) Add to `parse_yaml_frontmatter()` case statement:**
```bash
pull_request) CURRENT_PULL_REQUEST="$value" ;;
contributor) CURRENT_CONTRIBUTOR="$value" ;;
contributor_email) CURRENT_CONTRIBUTOR_EMAIL="$value" ;;
```

**c) Add argument parsing:**
```bash
--pull-request) BATCH_PULL_REQUEST="$2"; BATCH_PULL_REQUEST_SET=true; shift ;;
--contributor) BATCH_CONTRIBUTOR="$2"; BATCH_CONTRIBUTOR_SET=true; shift ;;
--contributor-email) BATCH_CONTRIBUTOR_EMAIL="$2"; BATCH_CONTRIBUTOR_EMAIL_SET=true; shift ;;
```

**d) Apply updates in write logic:**
```bash
[[ "$BATCH_PULL_REQUEST_SET" == true ]] && CURRENT_PULL_REQUEST="$BATCH_PULL_REQUEST"
[[ "$BATCH_CONTRIBUTOR_SET" == true ]] && CURRENT_CONTRIBUTOR="$BATCH_CONTRIBUTOR"
[[ "$BATCH_CONTRIBUTOR_EMAIL_SET" == true ]] && CURRENT_CONTRIBUTOR_EMAIL="$BATCH_CONTRIBUTOR_EMAIL"
```

**e) Write fields in `write_task_file()`** — same conditional pattern as issue field.

### 4. Modify `aiscripts/aitask_ls.sh`

**a) Add variables in frontmatter parsing loop:**
```bash
pull_request) pr_url="$value" ;;
contributor) contributor_name="$value" ;;
```

**b) Add to verbose output:**
After the issue display line, add:
```bash
[[ -n "$pr_url" ]] && pr_text=", PR: $pr_url"
[[ -n "$contributor_name" ]] && contributor_text=", Contributor: $contributor_name"
```

## Verification

1. Create task: `echo "test" | ./aiscripts/aitask_create.sh --batch --name "test_pr" --pull-request "https://github.com/o/r/pull/1" --contributor "user1" --contributor-email "123+user1@users.noreply.github.com" --desc-file - --commit`
2. Check file: `cat aitasks/t*_test_pr.md` — verify all three fields in frontmatter
3. List: `./ait ls -v` — verify PR and contributor shown
4. Update: `./ait update --batch <N> --contributor "user2"` — verify field updated
5. Tests: `bash tests/test_draft_finalize.sh`
6. Lint: `shellcheck aiscripts/aitask_create.sh aiscripts/aitask_update.sh aiscripts/aitask_ls.sh aiscripts/lib/task_utils.sh`

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_1`
