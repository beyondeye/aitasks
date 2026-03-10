---
Task: t355_1_extend_contribute_metadata_with_fingerprint_and_auto_labels.md
Parent Task: aitasks/t355_contribute_metadata_system.md
Sibling Tasks: aitasks/t355/t355_2_*.md through t355_7_*.md
Archived Sibling Plans: (none yet — this is the first child)
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `aitask-contribute` skill generates issue bodies with a `<!-- aitask-contribute-metadata -->` HTML comment block. Currently it only contains `contributor`, `contributor_email`, and `based_on_version`. This task adds fingerprint fields to enable downstream overlap detection (t355_2 through t355_7 depend on these fields).

## Implementation Plan

### Step 1: Modify `build_issue_body()` in `.aitask-scripts/aitask_contribute.sh`

**File:** `.aitask-scripts/aitask_contribute.sh` lines 611-617

Add fingerprint fields to the metadata comment block. Replace current block:

```bash
    # Contributor metadata as HTML comment
    echo ""
    echo "<!-- aitask-contribute-metadata"
    echo "contributor: $contributor"
    echo "contributor_email: $contributor_email"
    echo "based_on_version: ${version:-unknown}"
    echo "-->"
```

With:

```bash
    # Compute fingerprint fields
    local sorted_files file_dirs area_name
    sorted_files=$(echo "$files" | tr ',' '\n' | sort | tr '\n' ',' | sed 's/,$//')
    file_dirs=$(echo "$files" | tr ',' '\n' | sed 's|/[^/]*$||' | sort -u | tr '\n' ',' | sed 's/,$//')
    area_name="${ARG_AREA:-unknown}"

    # Contributor metadata as HTML comment
    echo ""
    echo "<!-- aitask-contribute-metadata"
    echo "contributor: $contributor"
    echo "contributor_email: $contributor_email"
    echo "based_on_version: ${version:-unknown}"
    echo "fingerprint_version: 1"
    echo "areas: $area_name"
    echo "file_paths: $sorted_files"
    echo "file_dirs: $file_dirs"
    echo "change_type: $scope"
    echo "auto_labels: area:$area_name,scope:$scope"
    echo "-->"
```

### Step 2: Add tests in `tests/test_contribute.sh`

Added Test 11b after existing Test 11 to verify all 6 fingerprint fields.

### Verification

1. `bash tests/test_contribute.sh` — 123/123 passed
2. `shellcheck .aitask-scripts/aitask_contribute.sh` — no new warnings

## Final Implementation Notes
- **Actual work done:** Added 6 fingerprint fields (`fingerprint_version`, `areas`, `file_paths`, `file_dirs`, `change_type`, `auto_labels`) to the `<!-- aitask-contribute-metadata -->` HTML comment block in `build_issue_body()`. Added Test 11b with 6 assertions.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used `$ARG_AREA` global variable (not passed as parameter) since it's already in scope. Fields computed from existing data with portable shell commands.
- **Notes for sibling tasks:** The metadata block now contains fingerprint fields at the end (after `based_on_version`, before `-->`). The `fingerprint_version: 1` field can be used by t355_2 (metadata parser) to version the schema. `areas` uses the `--area` CLI flag value directly (not resolved directory paths). `file_dirs` extracts parent directories by stripping the last `/filename` component. When `--area` is not provided, `areas` defaults to `unknown`.
