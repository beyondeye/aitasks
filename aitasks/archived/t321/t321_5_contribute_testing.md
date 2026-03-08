---
priority: medium
effort: medium
depends: [1]
issue_type: test
status: Done
labels: [auto-update]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-08 09:36
updated_at: 2026-03-08 22:01
completed_at: 2026-03-08 22:01
---

## Context

This is child task 5 of t321 (aitask-contribute skill). It creates the test script for the core `aitask_contribute.sh` functionality.

## Key Files to Create

- `tests/test_contribute.sh` — self-contained test script

## Reference Files for Patterns

- `tests/test_claim_id.sh` — test structure pattern (assert_eq/assert_contains, PASS/FAIL summary, temp dir setup)
- `tests/test_pr_contributor_metadata.sh` — test pattern for contributor-related functionality
- `.aitask-scripts/aitask_contribute.sh` (created in t321_1) — the script being tested

## Implementation Plan

### Test Setup

The test creates a temporary directory with:
- A mock aitasks project structure (`.aitask-scripts/VERSION`, key directories)
- Mock files that differ from "upstream" versions
- An `AITASK_CONTRIBUTE_UPSTREAM_DIR` env var override that points to a local directory with "upstream" files (avoids network calls to GitHub API)

### Test Cases

1. **`--help` output** — verify the script outputs help text and exits 0
2. **`--list-areas` output** — verify it outputs the predefined areas
3. **Argument parsing** — verify `--area scripts --files "foo.sh" --title "test" --dry-run` runs without error
4. **Dry-run output structure** — verify the dry-run output contains expected sections:
   - `## Contribution:` heading
   - `### Motivation` heading
   - `### Changed Files` heading
   - `### Code Changes` heading
   - `<!-- aitask-contribute-metadata` block
5. **Missing `--files` error** — verify the script errors when `--files` is missing
6. **Missing `--title` error** — verify the script errors when `--title` is missing
7. **`--list-changes` output** — create files that differ from upstream, verify they appear in output
8. **Large diff handling** — create a file with >50 line diff, verify:
   - Rendered preview is truncated to preview lines
   - Full diff appears in HTML comment
   - Preview note "*Preview — full diff available in raw view*" is present
9. **Small diff handling** — create a file with <50 line diff, verify full diff is shown directly (no HTML comment)
10. **Contributor metadata** — verify the HTML comment contains contributor and contributor_email fields
11. **Mode detection** — test that mode is correctly detected (may need to mock git remote)

### Test Isolation Strategy

To avoid network calls:
- Set `AITASK_CONTRIBUTE_UPSTREAM_DIR` env var pointing to a temp directory with "upstream" files
- The script should check this env var and use local files instead of calling `repo_fetch_file()` when set
- This is the same pattern used by other tests to mock external dependencies

### Script Structure

```bash
#!/usr/bin/env bash
set -euo pipefail

# Test helpers
PASS=0; FAIL=0; TOTAL=0
assert_eq() { ... }
assert_contains() { ... }

# Setup temp dirs
setup() { ... }
cleanup() { ... }
trap cleanup EXIT

# Test cases
test_help_output() { ... }
test_list_areas() { ... }
# ... etc

# Run all tests
setup
test_help_output
test_list_areas
# ...

# Summary
echo "Results: $PASS passed, $FAIL failed out of $TOTAL tests"
```

## Verification Steps

- `bash tests/test_contribute.sh` outputs PASS/FAIL summary with all tests passing
- `shellcheck tests/test_contribute.sh` passes
- Tests run without network access (all upstream fetching is mocked)
