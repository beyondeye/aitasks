---
priority: medium
effort: medium
depends: [1]
issue_type: feature
status: Ready
labels: [auto-update]
created_at: 2026-03-08 09:34
updated_at: 2026-03-08 09:34
---

## Context

This is child task 2 of t321 (aitask-contribute skill). It adds contributor metadata parsing to `aitask_issue_import.sh` so that when a contribution issue (created by `aitask-contribute`) is imported as a task, the contributor attribution is preserved.

Currently `aitask_pr_import.sh` extracts contributor info from PR author and resolves their email, but `aitask_issue_import.sh` has no contributor support at all. The `aitask-contribute` script (t321_1) embeds contributor metadata in issue bodies as HTML comments (`<!-- aitask-contribute-metadata ... -->`). This task makes issue-import parse that metadata.

## Key Files to Modify

- `.aitask-scripts/aitask_issue_import.sh` — add contributor metadata parsing

## Reference Files for Patterns

- `.aitask-scripts/aitask_pr_import.sh` — see how contributor/contributor_email are extracted from PR author and passed to `aitask_create.sh` via `--contributor` and `--contributor-email` flags
- `.aitask-scripts/aitask_create.sh` — already supports `--contributor` and `--contributor-email` flags (lines 125-126)
- `.aitask-scripts/aitask_contribute.sh` (created in t321_1) — generates the `<!-- aitask-contribute-metadata ... -->` block

## Implementation Plan

### Step 1: Add metadata parsing function

Add a function to `aitask_issue_import.sh` that extracts contributor metadata from issue body text:

```bash
# Parse aitask-contribute metadata from issue body HTML comment
# Sets: CONTRIBUTE_CONTRIBUTOR, CONTRIBUTE_EMAIL
parse_contribute_metadata() {
    local body="$1"
    CONTRIBUTE_CONTRIBUTOR=""
    CONTRIBUTE_EMAIL=""

    # Look for <!-- aitask-contribute-metadata ... --> block
    local metadata_block
    metadata_block=$(echo "$body" | sed -n '/<!-- aitask-contribute-metadata/,/-->/p' 2>/dev/null) || return 0

    if [[ -n "$metadata_block" ]]; then
        CONTRIBUTE_CONTRIBUTOR=$(echo "$metadata_block" | grep 'contributor:' | head -1 | sed 's/.*contributor: *//' | tr -d '[:space:]')
        CONTRIBUTE_EMAIL=$(echo "$metadata_block" | grep 'contributor_email:' | head -1 | sed 's/.*contributor_email: *//' | tr -d '[:space:]')
    fi
}
```

### Step 2: Call parsing in import flow

In the `import_single_issue()` function (or equivalent), after fetching the issue body:
1. Call `parse_contribute_metadata "$issue_body"`
2. If `CONTRIBUTE_CONTRIBUTOR` is non-empty, pass to `aitask_create.sh`:
   - Add `--contributor "$CONTRIBUTE_CONTRIBUTOR"` flag
   - Add `--contributor-email "$CONTRIBUTE_EMAIL"` flag (if non-empty)

### Step 3: Handle batch mode

Ensure the contributor fields are passed through in batch mode as well. The existing `--contributor` and `--contributor-email` flags in `aitask_create.sh` handle the rest.

## Verification Steps

- Import a test issue that has `<!-- aitask-contribute-metadata contributor: testuser contributor_email: test@example.com -->` in its body
- Verify the created task file has `contributor: testuser` and `contributor_email: test@example.com` in its YAML frontmatter
- Import a regular issue (no metadata) — verify no contributor fields are set (backward compatible)
- `shellcheck .aitask-scripts/aitask_issue_import.sh` passes
