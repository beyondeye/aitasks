---
priority: medium
effort: medium
depends: [t369_4]
issue_type: test
status: Ready
labels: [aitask_explain, aitask_pick]
created_at: 2026-03-11 18:34
updated_at: 2026-03-11 18:34
---

Write tests for aitask_explain_format_context.py and aitask_explain_context.sh. Test synthetic reference.yaml processing, greedy selection algorithm, cache reuse, --max-plans limiting, and graceful no-op. Follow existing test patterns (assert_eq/assert_contains, PASS/FAIL).

## Context

This task creates the test suite for the two new scripts introduced by t369_1 and t369_2. The tests need to work in a self-contained environment (temp directories with synthetic data) so they can run on any machine without depending on real codebrowser cache data. The test pattern follows the project's existing approach: standalone bash scripts with `assert_eq`/`assert_contains` helpers and a PASS/FAIL summary.

## Key Files to Modify

- **`tests/test_explain_context.sh`** (NEW) — The main test file covering both the Python formatter and the shell orchestrator.

## Reference Files for Patterns

- **`tests/test_setup_git.sh`** — The primary reference for test structure. Shows:
  - Shebang `#!/usr/bin/env bash` (no set -euo pipefail in tests since we need to capture failures)
  - `SCRIPT_DIR` / `PROJECT_DIR` setup
  - `PASS`/`FAIL`/`TOTAL` counters
  - `assert_eq()`, `assert_contains()`, `assert_not_contains()`, `assert_dir_exists()` helpers
  - Tests use temp directories created with `mktemp -d`
  - Cleanup with `rm -rf` at end
  - Summary: `echo "Results: $PASS/$TOTAL passed, $FAIL failed"`
- **`tests/test_draft_finalize.sh`** — Another test file showing similar patterns
- **`.aitask-scripts/aitask_explain_process_raw_data.py`** — Shows the YAML structure that `reference.yaml` uses. The tests need to create synthetic reference.yaml files matching this structure.
- **`.aitask-scripts/aitask_explain_format_context.py`** — The Python script being tested (from t369_1).
- **`.aitask-scripts/aitask_explain_context.sh`** — The shell script being tested (from t369_2).

## Implementation Plan

### Step 1: Create test file skeleton

Create `tests/test_explain_context.sh` with the standard test structure:
```bash
#!/usr/bin/env bash
# test_explain_context.sh - Tests for aitask_explain_context.sh and aitask_explain_format_context.py
# Run: bash tests/test_explain_context.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---
assert_eq() { ... }
assert_contains() { ... }
assert_not_contains() { ... }

# --- Setup ---
TMPDIR_BASE=$(mktemp -d "${TMPDIR:-/tmp}/test_explain_ctx_XXXXXX")
trap 'rm -rf "$TMPDIR_BASE"' EXIT
```

### Step 2: Create helper to generate synthetic reference.yaml

Write a function that creates a valid reference.yaml with controllable data:
```bash
create_synthetic_reference() {
    local output_dir="$1"
    local file_path="$2"    # e.g., "src/foo.py"
    local task_ids="$3"     # e.g., "166 209 221"
    # Creates reference.yaml with line_ranges mapping to those task IDs
    # Also creates plans/p<id>.md files with synthetic plan content
}
```

The reference.yaml structure must match what `aitask_explain_process_raw_data.py` produces:
```yaml
files:
  - path: "src/foo.py"
    commits:
      - num: 1
        hash: "abc1234"
        date: "2026-01-15"
        author: "Test Author"
        message: "feature: Add foo (t166)"
        task_id: "166"
    line_ranges:
      - start: 1
        end: 50
        commits: [1]
        tasks: ["166"]
      - start: 51
        end: 80
        commits: [2]
        tasks: ["209"]

tasks:
  - id: "166"
    task_file: "tasks/t166.md"
    plan_file: "plans/p166.md"
    has_notes: true
```

### Step 3: Write Python formatter tests

**Test 3a: Basic formatting with single file and single plan**
- Create synthetic reference.yaml with one file and one task
- Run `python3 aitask_explain_format_context.py --max-plans 1 --ref ref.yaml:run_dir -- src/foo.py`
- Assert output contains `## Historical Architectural Context`
- Assert output contains the task ID header
- Assert output contains plan content

**Test 3b: Max-plans limiting**
- Create reference.yaml with 3 tasks contributing to a file
- Run with `--max-plans 1`
- Assert only 1 plan appears (the one with most lines)
- Run with `--max-plans 2`
- Assert 2 plans appear

**Test 3c: Cross-file deduplication**
- Create reference.yaml with 2 files, both referencing task 166
- Run with `--max-plans 1` for both files
- Assert task 166 appears only once in output
- Assert the "Historical context for:" line lists both files

**Test 3d: Sorting by file coverage**
- Create data where task A covers 2 files and task B covers 1 file
- Assert task A appears before task B

**Test 3e: Missing plan file**
- Create reference.yaml referencing a plan that doesn't exist
- Assert output includes the missing plan note in Context Notes section
- Assert no crash

**Test 3f: No matching files**
- Run with a target file not present in any reference.yaml
- Assert empty or minimal output, no crash

### Step 4: Write shell orchestrator tests

These tests need a temporary git repo to simulate the cache management.

**Test 4a: No-op when max-plans is 0**
- Run `aitask_explain_context.sh --max-plans 0 some_file.sh`
- Assert exit code 0
- Assert empty output

**Test 4b: Graceful handling with non-existent files**
- Run with files that don't exist in any codebrowser cache
- Assert exit code 0
- Assert no crash (may produce empty output or a warning)

**Test 4c: Pre-populated cache test**
- Create a fake codebrowser cache directory structure manually:
  ```
  .aitask-explain/codebrowser/src__YYYYMMDD_HHMMSS/
    reference.yaml
    plans/p166.md
  ```
- Run the context script pointing at a file in `src/`
- Assert the formatter is called and produces output

### Step 5: Write the summary

```bash
echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ $FAIL -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
else
    echo "ALL TESTS PASSED"
    exit 0
fi
```

## Verification Steps

1. **Run the test**: `bash tests/test_explain_context.sh` and verify all tests pass.
2. **Verify test isolation**: Run twice in a row; both should pass (no stale temp dirs).
3. **Verify cleanup**: After test runs, check that the temp directory is cleaned up.
4. **Shellcheck**: Run `shellcheck tests/test_explain_context.sh` (non-blocking, just verify no critical issues).
