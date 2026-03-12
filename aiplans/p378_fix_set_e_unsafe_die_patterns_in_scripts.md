---
Task: t378_fix_set_e_unsafe_die_patterns_in_scripts.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix set -e unsafe die patterns (t378)

## Context

Scripts using `set -e` silently exit when `cmd || die` / `cmd && die` is the last statement in a function. When the condition evaluates to false (happy path), the `||`/`&&` expression returns exit code 1, which becomes the function's return code and triggers `set -e`. This caused the `contribution-check` GitHub Actions workflow to fail silently.

## Fix Strategy

Convert each unsafe last-statement pattern to an `if` statement:

```bash
# Before (UNSAFE):
command || die "message"
[[ condition ]] && die "message"

# After (SAFE):
if ! command; then
    die "message"
fi

if [[ condition ]]; then
    die "message"
fi
```

## Instances Fixed (23 across 8 files)

### 1. `aitask_contribution_check.sh` (3)
- Line 91 `parse_args()`: `[[ -z "$ARG_ISSUE" ]] && die`
- Line 103 `github_check_cli()`: `gh auth status || die`
- Line 309 `bitbucket_check_cli()`: `[[ -n ... ]] || die`

### 2. `aitask_contribute.sh` (3)
- Line 162 `github_check_cli()`: `gh auth status || die`
- Line 215 `gitlab_check_cli()`: `glab auth status || die`
- Line 268 `bitbucket_check_cli()`: `bkt auth status || die`

### 3. `aitask_issue_import.sh` (3)
- Line 129 `github_check_cli()`: `gh auth status || die`
- Line 216 `gitlab_check_cli()`: `glab auth status || die`
- Line 284 `bitbucket_check_cli()`: `bkt auth status || die`

### 4. `aitask_issue_update.sh` (3)
- Line 38 `github_check_cli()`: `gh auth status || die`
- Line 81 `gitlab_check_cli()`: `glab auth status || die`
- Line 139 `bitbucket_check_cli()`: `bkt auth status || die`

### 5. `aitask_pr_close.sh` (3)
- Line 39 `github_check_cli()`: `gh auth status || die`
- Line 82 `gitlab_check_cli()`: `glab auth status || die`
- Line 141 `bitbucket_check_cli()`: `bkt auth status || die`

### 6. `aitask_pr_import.sh` (4)
- Line 83 `github_check_cli()`: `gh auth status || die`
- Line 204 `gitlab_check_cli()`: `glab auth status || die`
- Line 342 `bitbucket_check_cli()`: `bkt auth status || die`
- Line 357 `bitbucket_resolve_repo()`: `[[ -n ... ]] || die`

### 7. `aitask_codeagent.sh` (2)
- Line 39 `require_jq()`: `command -v jq || die`
- Line 57 `parse_agent_string()`: `$valid || die`

### 8. `aitask_verified_update.sh` (2)
- Line 47 `require_jq()`: `command -v jq || die`
- Line 160-161 `ensure_model_exists()`: `jq -e ... || die`

## Caller Impact Analysis

All 8 scripts use `set -euo pipefail`. The affected functions are called as plain statements (not in conditionals or exit-code checks). Callers rely on `die` for error handling (which calls `exit 1`). No caller checks these functions' return codes.

The fix changes the happy-path return from exit code 1 (the bug) to exit code 0 (correct). Skills that call these scripts only observe script-level exit codes and stdout/stderr, which are unchanged.

## Final Implementation Notes
- **Actual work done:** Converted 23 unsafe `cmd || die` / `cmd && die` last-statement patterns to `if/then/fi` across 8 shell scripts, exactly as planned.
- **Deviations from plan:** None. The task description listed 24 instances but actual count was 23 (one instance in the task description was slightly miscounted).
- **Issues encountered:** None. All changes were mechanical and straightforward.
- **Key decisions:** For `[[ -n X && -n Y ]] || die` patterns, inverted to `if [[ -z X || -z Y ]]; then die; fi` for readability rather than negating the compound condition.
- **Verification:** shellcheck clean (no new warnings), all 43 test suites pass (800+ assertions, 0 failures).
