---
priority: medium
effort: medium
depends: [2]
issue_type: feature
status: Ready
labels: [aitask_contribute]
created_at: 2026-03-10 10:57
updated_at: 2026-03-10 10:57
---

## Context

The `aitask_issue_import.sh` script currently imports one issue per task. This task adds a `--merge-issues N1,N2,...` flag to import multiple contribution issues as a single task, with merged descriptions, unioned metadata, and multi-contributor attribution.

This capability is used by the `aitask-contribution-review` skill (t355_6) when the AI recommends grouping related issues.

## Key Files to Modify

- `.aitask-scripts/aitask_issue_import.sh` — add `--merge-issues` mode
- `.aitask-scripts/aitask_create.sh` — may need to support `related_issues:` and `contributors:` frontmatter fields
- `.claude/skills/task-workflow/procedures.md` — update Contributor Attribution Procedure for multi-contributor

## Reference Files for Patterns

- `.aitask-scripts/aitask_issue_import.sh:437-530` — `import_single_issue()` function (pattern to extend)
- `.aitask-scripts/aitask_issue_import.sh:394-419` — `parse_contribute_metadata()` for extracting contributor info
- `.aitask-scripts/aitask_issue_import.sh:421-433` — `check_duplicate_import()` for existing dedup
- `.aitask-scripts/aitask_create.sh:1114-1126` — frontmatter field handling
- `.claude/skills/task-workflow/procedures.md` — Contributor Attribution Procedure

## Implementation Plan

### 1. New `--merge-issues` flag

Parse `--merge-issues N1,N2,...` in argument handling. When set, enter merge mode instead of single-issue import.

### 2. Merge mode flow

```bash
merge_issues() {
    local issue_nums="$1"  # comma-separated
    IFS=',' read -ra issues <<< "$issue_nums"
    
    # Fetch all issues
    local bodies=()
    local contributors=()
    local primary_contributor=""
    local primary_email=""
    local max_diff_lines=0
    
    for num in "${issues[@]}"; do
        body=$(source_fetch_issue "$num")
        bodies+=("$body")
        
        parse_contribute_metadata "$body"
        # Track contributor with largest diff contribution
        local diff_lines=$(count_diff_lines "$body")
        if (( diff_lines > max_diff_lines )); then
            max_diff_lines=$diff_lines
            primary_contributor="$CONTRIBUTE_CONTRIBUTOR"
            primary_email="$CONTRIBUTE_EMAIL"
        fi
        contributors+=("$CONTRIBUTE_CONTRIBUTOR|$CONTRIBUTE_EMAIL|$issue_url")
    done
    
    # Combine descriptions with section boundaries
    combined_desc="## Merged Contribution Issues\n\n"
    for i in "${!issues[@]}"; do
        combined_desc+="### Issue #${issues[$i]}\n\n${bodies[$i]}\n\n---\n\n"
    done
    
    # Resolve metadata: highest priority, highest effort, union labels
    # Create task with combined data
    aitask_create.sh --batch \
        --name "$merged_name" \
        --desc-file - \
        --contributor "$primary_contributor" \
        --contributor-email "$primary_email" \
        --issue "$primary_issue_url" \
        ... <<< "$combined_desc"
    
    # Post comment on each source issue
    for num in "${issues[@]}"; do
        source_post_comment "$num" "This issue has been imported as part of merged task t$task_id"
    done
}
```

### 3. New frontmatter fields

- `related_issues:` — YAML list of all source issue URLs (primary stays in `issue:`)
- `contributors:` — YAML list of secondary contributor objects:
  ```yaml
  contributors:
    - name: bob
      email: bob@example.com
      issue: https://github.com/owner/repo/issues/38
  ```

### 4. Update Contributor Attribution Procedure

In `procedures.md`, update the Contributor Attribution Procedure to handle the `contributors:` list:
- Primary contributor: `Co-Authored-By` trailer (unchanged)
- Secondary contributors: formatted as commit body text: `Also based on contributions from: bob (#38), charlie (#15)`

### 5. Diff line counting for primary contributor selection

Count `+`/`-` lines in the diff sections of each issue body to determine which contributor has the largest code change. This identifies the "primary contributor."

## Verification Steps

1. Test with mock issue data: `aitask_issue_import.sh --merge-issues 1,2,3 --dry-run` (if dry-run supported)
2. Verify merged task file contains all issue descriptions
3. Verify `contributors:` field in frontmatter
4. Verify `related_issues:` field in frontmatter
5. Run existing tests: `bash tests/test_contribute.sh`
