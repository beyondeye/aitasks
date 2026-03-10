---
priority: high
effort: medium
depends: [1]
issue_type: feature
status: Ready
labels: [aitask_contribute]
created_at: 2026-03-10 09:55
updated_at: 2026-03-10 18:39
---

## Context

This task creates the core `aitask_contribution_check.sh` script — a portable bash script that processes contribution issues by comparing fingerprint metadata, computing overlap scores, and posting analysis comments. It uses encapsulated platform-specific functions dispatched via `detect_platform()`, following the same pattern as `aitask_contribute.sh` and `aitask_issue_import.sh`.

This script is called by CI/CD wrappers (t355_4) and by the contribution-review skill (t355_6). It must work both in CI/CD environments and when invoked manually.

## Key Files to Create

- `.aitask-scripts/aitask_contribution_check.sh` — new core script
- `tests/test_contribution_check.sh` — new test file

## Reference Files for Patterns

- `.aitask-scripts/aitask_contribute.sh:188-284` — platform-specific function dispatch pattern (`github_create_issue()`, `gitlab_create_issue()`, `bitbucket_create_issue()`)
- `.aitask-scripts/aitask_contribute.sh:612-617` — metadata comment format to parse
- `.aitask-scripts/aitask_reviewguide_scan.sh:215-245` — `compute_label_overlap()` for set-intersection scoring pattern
- `.aitask-scripts/lib/task_utils.sh:85-97` — `detect_platform()` function
- `.aitask-scripts/aitask_issue_import.sh:394-419` — `parse_contribute_metadata()` for fingerprint parsing

## Implementation Plan

### 1. Platform-agnostic core functions

- `parse_fingerprint_from_body()` — extract fingerprint fields from issue body HTML comment (reuse pattern from `parse_contribute_metadata()`)
- `compute_overlap_score()` — weighted set-intersection scoring:
  - File path intersection: shared_files × 3 (strongest signal)
  - Directory intersection: shared_dirs × 2
  - Area intersection: shared_areas × 2
  - Change type match: +1
  - Thresholds: ≥ 4 "likely overlap", ≥ 7 "high overlap"
- `format_overlap_comment()` — generate markdown comment with overlap table + label suggestions
- `format_overlap_metadata()` — generate `<!-- overlap-results top_overlaps: 42:7,38:4 overlap_check_version: 1 -->` block

### 2. Encapsulated platform-specific functions

Dispatched via detected platform (from `--platform` flag or `detect_platform()`):

- `source_list_contribution_issues()` dispatches to:
  - `github_list_contribution_issues()` — `gh issue list -R "$REPO" --label contribution --json number,title,body --limit 50`
  - `gitlab_list_contribution_issues()` — CLI-first: `glab issue list -l contribution`; fallback: `curl` with GitLab REST API using `$GITLAB_TOKEN` or `$CI_JOB_TOKEN`
  - `bitbucket_list_contribution_issues()` — CLI-first: `bkt issue list`; fallback: `curl` with Bitbucket REST API using `$BITBUCKET_TOKEN`

- `source_post_issue_comment()` dispatches to:
  - `github_post_issue_comment()` — `gh issue comment "$ISSUE_NUM" -R "$REPO" --body "$COMMENT"`
  - `gitlab_post_issue_comment()` — `glab issue note "$ISSUE_IID"` or `curl` POST to notes API
  - `bitbucket_post_issue_comment()` — `bkt issue comment "$ISSUE_ID"` or `curl` POST

- `source_apply_issue_labels()` dispatches to:
  - `github_apply_issue_labels()` — `gh issue edit "$ISSUE_NUM" -R "$REPO" --add-label "$LABEL"`
  - `gitlab_apply_issue_labels()` — `glab issue update "$ISSUE_IID" --label "$LABELS"` or `curl` PUT
  - `bitbucket_apply_issue_labels()` — skip (no label API)

- `source_get_repo_labels()` — check which labels exist on the repo to filter auto_labels

### 3. Main flow

```bash
main() {
    parse_args "$@"                           # --platform, --repo, issue_number
    detect_or_use_platform                    # from flag or detect_platform()
    
    local issue_body
    issue_body=$(source_get_issue_body "$ISSUE_NUM")
    
    parse_fingerprint_from_body "$issue_body"  # sets FP_* globals
    
    local all_issues
    all_issues=$(source_list_contribution_issues)
    
    local overlaps=()
    # For each issue, parse fingerprint, compute score, collect top 5
    
    local comment
    comment=$(format_overlap_comment "${overlaps[@]}")
    
    source_post_issue_comment "$ISSUE_NUM" "$comment"
    
    # Apply existing auto_labels
    local repo_labels
    repo_labels=$(source_get_repo_labels)
    for label in $auto_labels; do
        if echo "$repo_labels" | grep -q "^$label$"; then
            source_apply_issue_labels "$ISSUE_NUM" "$label"
        fi
    done
}
```

### 4. CLI interface

```
Usage: aitask_contribution_check.sh <issue_number> [options]
  --platform <github|gitlab|bitbucket>   Override platform detection
  --repo <owner/repo>                    Target repository (default: from git remote)
  --limit <N>                            Max issues to compare (default: 50)
  --dry-run                              Print comment without posting
  --silent                               Minimal output
```

## Verification Steps

1. Run with `--dry-run` against a test issue to verify comment format
2. Run `shellcheck .aitask-scripts/aitask_contribution_check.sh`
3. Run `bash tests/test_contribution_check.sh`
4. Test platform detection and fallback paths
