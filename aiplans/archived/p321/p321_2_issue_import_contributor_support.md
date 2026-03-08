---
Task: t321_2_issue_import_contributor_support.md
Parent Task: aitasks/t321_removeautoupdatefromdocsorimplement.md
Sibling Tasks: aitasks/t321/t321_1_*.md, aitasks/t321/t321_3_*.md, aitasks/t321/t321_4_*.md, aitasks/t321/t321_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t321_2 — Issue Import Contributor Support

## Overview

Add contributor metadata parsing to `aitask_issue_import.sh` so that contribution issues (created by `aitask-contribute`) preserve contributor attribution when imported as tasks.

## Steps

### 1. Add metadata parsing function

Add to `.aitask-scripts/aitask_issue_import.sh` near other helper functions:

```bash
# Parse aitask-contribute metadata from issue body HTML comment
# Sets global: CONTRIBUTE_CONTRIBUTOR, CONTRIBUTE_EMAIL
parse_contribute_metadata() {
    local body="$1"
    CONTRIBUTE_CONTRIBUTOR=""
    CONTRIBUTE_EMAIL=""

    local in_block=false
    while IFS= read -r line; do
        if [[ "$line" == *"<!-- aitask-contribute-metadata"* ]]; then
            in_block=true
            continue
        fi
        if [[ "$in_block" == true ]]; then
            if [[ "$line" == *"-->"* ]]; then
                break
            fi
            case "$line" in
                *contributor_email:*)
                    CONTRIBUTE_EMAIL=$(echo "$line" | sed 's/.*contributor_email:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *contributor:*)
                    CONTRIBUTE_CONTRIBUTOR=$(echo "$line" | sed 's/.*contributor:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
            esac
        fi
    done <<< "$body"
}
```

Note: Parse `contributor_email` before `contributor` in the case statement to avoid `contributor:` matching `contributor_email:` lines. The `while` loop is more portable than multi-line sed.

### 2. Integrate into import flow

In the `import_single_issue()` function, after the issue body is fetched:

```bash
# Check for aitask-contribute metadata
parse_contribute_metadata "$issue_body"

# Add contributor flags to aitask_create.sh call if found
local contributor_flags=""
if [[ -n "$CONTRIBUTE_CONTRIBUTOR" ]]; then
    contributor_flags="--contributor \"$CONTRIBUTE_CONTRIBUTOR\""
    if [[ -n "$CONTRIBUTE_EMAIL" ]]; then
        contributor_flags="$contributor_flags --contributor-email \"$CONTRIBUTE_EMAIL\""
    fi
fi
```

Then append `$contributor_flags` to the `aitask_create.sh` invocation.

### 3. Ensure batch mode passes through

The contributor flags should work in both interactive and batch import modes since they're added at the `aitask_create.sh` call level.

## Key Files

- **Modify:** `.aitask-scripts/aitask_issue_import.sh`
- **Reference:** `.aitask-scripts/aitask_pr_import.sh` (how PR import passes contributor to create)
- **Reference:** `.aitask-scripts/aitask_create.sh` lines 125-126 (`--contributor`, `--contributor-email` flags)

## Verification

- Import a mock issue with `<!-- aitask-contribute-metadata contributor: testuser contributor_email: test@example.com based_on_version: 0.9.2 -->` in body
- Verify created task has `contributor: testuser` and `contributor_email: test@example.com` in frontmatter
- Import a regular issue (no metadata) — verify no contributor fields (backward compatible)
- `shellcheck .aitask-scripts/aitask_issue_import.sh` passes

## Final Implementation Notes

- **Actual work done:** Added `parse_contribute_metadata()` function and integrated it into both `import_single_issue()` (batch mode) and `interactive_import_issue()` (interactive mode). Created `tests/test_issue_import_contributor.sh` with 21 tests covering metadata parsing, edge cases, and integration.
- **Deviations from plan:** Instead of using `$contributor_flags` as a string variable, appended flags directly to the `create_args` array — cleaner and avoids quoting issues. Also added contributor parsing to the interactive flow (`interactive_import_issue()`), not just the batch flow.
- **Issues encountered:** None — the implementation followed the plan closely. The `case` statement ordering (contributor_email before contributor) correctly prevents substring matching.
- **Key decisions:** Extracted the parsing function as a unit-testable standalone by duplicating it in tests (since the script can't be sourced without executing `main()`). Tests cover: full metadata, no metadata, partial metadata, whitespace handling, wrong comment format, metadata in middle of body, and syntax checks.
- **Notes for sibling tasks:** The metadata format `<!-- aitask-contribute-metadata contributor: X contributor_email: Y based_on_version: Z -->` is now parsed by both batch and interactive import flows. The t321_5 tests are already done per t321_1's notes — this task adds issue-import-specific tests.

## Step 9 Reference
Post-implementation: archive task via task-workflow Step 9.
