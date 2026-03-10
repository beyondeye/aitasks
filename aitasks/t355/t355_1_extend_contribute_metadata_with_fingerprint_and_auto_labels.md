---
priority: high
effort: low
depends: []
issue_type: feature
status: Ready
labels: [aitask_contribute]
created_at: 2026-03-10 09:18
updated_at: 2026-03-10 09:18
---

## Context

The `aitask-contribute` skill creates contribution issues with a `<!-- aitask-contribute-metadata -->` HTML comment block containing `contributor`, `contributor_email`, and `based_on_version`. This task extends that block with fingerprint fields and auto-label suggestions to enable downstream overlap detection.

This is the foundation task — all other t355 child tasks depend on these metadata fields.

## Key Files to Modify

- `.aitask-scripts/aitask_contribute.sh` — `build_issue_body()` function (line ~612-617) where the metadata comment is generated
- `tests/test_contribute.sh` — add tests verifying fingerprint fields in dry-run output

## Reference Files for Patterns

- `.aitask-scripts/aitask_contribute.sh:612-617` — existing metadata comment generation
- `.aitask-scripts/aitask_contribute.sh:516-618` — full `build_issue_body()` function

## Implementation Plan

Add these fields to the `<!-- aitask-contribute-metadata -->` block in `build_issue_body()`:

```
fingerprint_version: 1
areas: <area_names>
file_paths: <sorted_comma_separated_files>
file_dirs: <unique_parent_directories>
change_type: <scope>
auto_labels: area:<area>,scope:<scope>
```

Field computation from existing function arguments:
- `areas`: from `$ARG_AREA` variable (framework mode) or resolved area name (project mode)
- `file_paths`: sort `$files` (already comma-separated) alphabetically
- `file_dirs`: extract unique parent directories from file paths
- `change_type`: from `$scope` parameter (bug-fix, enhancement, new-feature, documentation)
- `auto_labels`: construct from area name and scope: `area:$area,scope:$scope`
- `fingerprint_version`: hardcoded `1`

All fields are computed from data already available in `build_issue_body()`. No new data sources needed.

## Verification Steps

1. Run dry-run mode: `./.aitask-scripts/aitask_contribute.sh --dry-run --area scripts --files ".aitask-scripts/foo.sh" --title "test" --motivation "test" --scope enhancement --merge-approach "clean merge"`
2. Verify output contains all fingerprint fields in the metadata comment
3. Run existing tests: `bash tests/test_contribute.sh`
4. Verify tests pass and new fields are present in test output
