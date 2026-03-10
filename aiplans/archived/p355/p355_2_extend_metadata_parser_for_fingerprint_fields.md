---
Task: t355_2_extend_metadata_parser_for_fingerprint_fields.md
Parent Task: aitasks/t355_check_for_existing_issues_overlap.md
Sibling Tasks: aitasks/t355/t355_3_*.md through t355_7_*.md
Archived Sibling Plans: aiplans/archived/p355/p355_1_extend_contribute_metadata_with_fingerprint_and_auto_labels.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `aitask-contribute` skill (t355_1, completed) now emits fingerprint fields in the `<!-- aitask-contribute-metadata -->` HTML comment block. The `parse_contribute_metadata()` function in `aitask_issue_import.sh` only parses `contributor` and `contributor_email`. This task extends it to also extract the 6 new fingerprint fields so downstream scripts (t355_3: contribution check) can use them.

## Implementation Plan

### Step 1: Extend `parse_contribute_metadata()` in `.aitask-scripts/aitask_issue_import.sh`

**File:** `.aitask-scripts/aitask_issue_import.sh` lines 392-419

1. Update comment to list all globals
2. Add 6 new global variable initializations (all default to `""`)
3. Add 6 new case patterns with robustness:
   - Single-value fields (`fingerprint_version`, `change_type`): strip all whitespace with `tr -d '[:space:]'`
   - List fields (`areas`, `file_paths`, `file_dirs`, `auto_labels`): strip trailing whitespace with `sed 's/[[:space:]]*$//'`
   - Missing fields: globals stay `""` (initialized at function entry)
   - Empty values: sed + tr produce `""` safely

### Step 2: Update `setup_parse_function()` in `tests/test_issue_import_contributor.sh`

Mirror the updated function in the test helper (lines 56-90).

### Step 3: Add test cases in `tests/test_issue_import_contributor.sh`

- Test 10a: Full metadata with all fingerprint fields
- Test 10b: Backwards compatibility (old format, no fingerprint fields)
- Test 10c: Fingerprint fields only (no contributor/email)
- Test 10d: Empty fingerprint field values
- Test 10e: Trailing whitespace on list fields
- Renumber existing Test 10 (syntax check) to Test 11

### Step 4: Verification

1. `bash tests/test_issue_import_contributor.sh`
2. `bash tests/test_contribute.sh`
3. `shellcheck .aitask-scripts/aitask_issue_import.sh`

### Step 5: Post-Implementation (Step 9)

Archive task and plan via `aitask_archive.sh`.

## Final Implementation Notes
- **Actual work done:** Extended `parse_contribute_metadata()` with 6 new fingerprint field globals (`CONTRIBUTE_FINGERPRINT_VERSION`, `CONTRIBUTE_AREAS`, `CONTRIBUTE_FILE_PATHS`, `CONTRIBUTE_FILE_DIRS`, `CONTRIBUTE_CHANGE_TYPE`, `CONTRIBUTE_AUTO_LABELS`). Updated test helper to mirror function. Added 5 new test groups (10a-10e) with 36 new assertions covering full parsing, backwards compatibility, missing fields, empty values, and trailing whitespace. Renumbered syntax check to Test 11.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None. Shellcheck SC2034 "appears unused" warnings for new globals are expected (consumed by t355_3).
- **Key decisions:** `areas` case pattern placed last to avoid any theoretical prefix collision with `auto_labels` (both unique, but safer). List fields use double-sed pipeline (strip prefix + strip trailing whitespace) for robustness. Single-value fields use `tr -d '[:space:]'` to strip all whitespace.
- **Notes for sibling tasks:** The parser now sets 8 globals total. Downstream scripts (t355_3) should check `[[ -n "$CONTRIBUTE_FINGERPRINT_VERSION" ]]` before using fingerprint data — if empty, the issue predates fingerprint support. The test file `tests/test_issue_import_contributor.sh` duplicates the parser in `setup_parse_function()` — if the parser changes again, both copies must be updated. All 58 tests pass; 123 contribute tests pass.
