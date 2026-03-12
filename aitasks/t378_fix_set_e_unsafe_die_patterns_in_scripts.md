---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [cli, ci]
created_at: 2026-03-12 12:14
updated_at: 2026-03-12 12:14
---

## Problem

The `contribution-check` GitHub Actions workflow fails silently with exit code 1 and no output when processing issues. The root cause is a `set -e` interaction bug in `aitask_contribution_check.sh` and 7 other scripts.

## Root Cause

The pattern `[[ ... ]] && die "message"` or `command || die "message"` is unsafe as the **last statement in a function** when the script uses `set -e`. When the test evaluates to false (i.e., the happy path — no error), the `&&`/`||` expression returns exit code 1, which becomes the function's return code. The calling code then triggers `set -e`, causing the script to exit silently.

Example from `aitask_contribution_check.sh:91`:
```bash
[[ -z "$ARG_ISSUE" ]] && die "Issue number is required. Use --help for usage."
```
When `ARG_ISSUE` is "5", `[[ -z "5" ]]` returns 1, `&&` short-circuits, entire expression returns 1, function returns 1, `set -e` kills the script.

## Fix

Convert all `cmd && die` / `cmd || die` patterns that are the last statement in a function to `if` statements:

```bash
# Before (UNSAFE as last statement under set -e):
[[ -z "$ARG_ISSUE" ]] && die "Issue number is required."

# After (SAFE):
if [[ -z "$ARG_ISSUE" ]]; then
    die "Issue number is required."
fi
```

## Affected Files (24 instances across 8 files)

1. **aitask_contribution_check.sh** (3 instances)
   - Line 91 `parse_args()`: `[[ -z "$ARG_ISSUE" ]] && die`
   - Line 103 `github_check_cli()`: `gh auth status || die`
   - Line 309 `bitbucket_check_cli()`: `[[ ... ]] || die`

2. **aitask_contribute.sh** (3 instances)
   - Line 162 `github_check_cli()`: `gh auth status || die`
   - Line 215 `gitlab_check_cli()`: `glab auth status || die`
   - Line 268 `bitbucket_check_cli()`: `bkt auth status || die`

3. **aitask_issue_import.sh** (3 instances)
   - Line 129 `github_check_cli()`: `gh auth status || die`
   - Line 216 `gitlab_check_cli()`: `glab auth status || die`
   - Line 284 `bitbucket_check_cli()`: `bkt auth status || die`

4. **aitask_issue_update.sh** (3 instances)
   - Line 38 `github_check_cli()`: `gh auth status || die`
   - Line 81 `gitlab_check_cli()`: `glab auth status || die`
   - Line 139 `bitbucket_check_cli()`: `bkt auth status || die`

5. **aitask_pr_close.sh** (3 instances)
   - Line 39 `github_check_cli()`: `gh auth status || die`
   - Line 82 `gitlab_check_cli()`: `glab auth status || die`
   - Line 141 `bitbucket_check_cli()`: `bkt auth status || die`

6. **aitask_pr_import.sh** (4 instances)
   - Line 83 `github_check_cli()`: `gh auth status || die`
   - Line 204 `gitlab_check_cli()`: `glab auth status || die`
   - Line 342 `bitbucket_check_cli()`: `bkt auth status || die`
   - Line 357 `bitbucket_resolve_repo()`: `[[ ... ]] || die`

7. **aitask_codeagent.sh** (2 instances)
   - Line 39 `require_jq()`: `command -v jq || die`
   - Line 57 `parse_agent_string()`: `$valid || die`

8. **aitask_verified_update.sh** (2 instances)
   - Line 47 `require_jq()`: `command -v jq || die`
   - Line 161 `ensure_model_exists()`: `|| die`

## Testing

After fixing, verify:
1. `bash .aitask-scripts/aitask_contribution_check.sh 5 --platform github --repo beyondeye/aitasks --dry-run` produces output (not silent exit)
2. Run existing tests: `bash tests/test_contribution_check.sh`
3. All 8 affected scripts still work in both success and error paths
