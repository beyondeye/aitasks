---
priority: high
effort: low
depends: [t355_1, 1]
issue_type: feature
status: Implementing
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-10 09:18
updated_at: 2026-03-10 16:19
---

## Context

The `aitask_issue_import.sh` script has a `parse_contribute_metadata()` function (lines 394-419) that extracts `contributor` and `contributor_email` from the `<!-- aitask-contribute-metadata -->` HTML comment block in issue bodies. This task extends the parser to also extract the new fingerprint fields added by t355_1.

## Key Files to Modify

- `.aitask-scripts/aitask_issue_import.sh` — `parse_contribute_metadata()` function (lines 394-419)
- Add or extend existing tests for the metadata parser

## Reference Files for Patterns

- `.aitask-scripts/aitask_issue_import.sh:394-419` — existing `parse_contribute_metadata()` function with `while/case` loop
- `.aitask-scripts/aitask_issue_import.sh:409-416` — existing field matching pattern (note: `contributor_email` matches before `contributor` to avoid prefix collision)

## Implementation Plan

1. Add new global variables at the top of `parse_contribute_metadata()`:
   - `CONTRIBUTE_FINGERPRINT_VERSION=""`
   - `CONTRIBUTE_AREAS=""`
   - `CONTRIBUTE_FILE_PATHS=""`
   - `CONTRIBUTE_FILE_DIRS=""`
   - `CONTRIBUTE_CHANGE_TYPE=""`
   - `CONTRIBUTE_AUTO_LABELS=""`

2. Extend the `case` statement in the parsing loop to match new fields:
   ```bash
   *fingerprint_version:*) CONTRIBUTE_FINGERPRINT_VERSION=$(echo "$line" | sed 's/.*fingerprint_version:[[:space:]]*//' | tr -d '[:space:]') ;;
   *file_paths:*) CONTRIBUTE_FILE_PATHS=$(echo "$line" | sed 's/.*file_paths:[[:space:]]*//') ;;
   *file_dirs:*) CONTRIBUTE_FILE_DIRS=$(echo "$line" | sed 's/.*file_dirs:[[:space:]]*//') ;;
   *change_type:*) CONTRIBUTE_CHANGE_TYPE=$(echo "$line" | sed 's/.*change_type:[[:space:]]*//' | tr -d '[:space:]') ;;
   *auto_labels:*) CONTRIBUTE_AUTO_LABELS=$(echo "$line" | sed 's/.*auto_labels:[[:space:]]*//') ;;
   *areas:*) CONTRIBUTE_AREAS=$(echo "$line" | sed 's/.*areas:[[:space:]]*//') ;;
   ```

3. **Ordering matters:** `file_paths` must match before `file_dirs` to avoid partial prefix collision (but since both have unique suffixes after `file_`, this is safe with the `*field:*` pattern). `auto_labels` is unique, no ordering concern.

4. Backwards compatible: old issues without fingerprint fields will have empty globals.

## Verification Steps

1. Create a test issue body string with all metadata fields and verify parsing
2. Create a test issue body string with only old fields (contributor, email) and verify old fields parse correctly and new fields are empty
3. Run existing tests: `bash tests/test_contribute.sh`
