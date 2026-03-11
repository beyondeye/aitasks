---
Task: t369_5_write_tests.md
Parent Task: aitasks/t369_aitask_explain_for_aitask_pick.md
Sibling Tasks: aitasks/t369/t369_*_*.md
Archived Sibling Plans: aiplans/archived/p369/p369_*_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Write Tests for Explain Context Scripts (t369_5)

## Overview

Create a comprehensive test suite for the two new scripts introduced by t369_1 and t369_2:
- `.aitask-scripts/aitask_explain_format_context.py` (Python formatter)
- `.aitask-scripts/aitask_explain_context.sh` (Shell orchestrator)

Tests use synthetic data (temporary directories with hand-crafted reference.yaml and plan files) so they can run on any machine without depending on real codebrowser cache data.

**Dependency:** Requires t369_1 and t369_2 to be implemented first.

## Files to Create

| File | Description |
|------|-------------|
| `tests/test_explain_context.sh` | Self-contained test script with assert helpers |

## Reference Files

- **`tests/test_setup_git.sh`** -- Primary test pattern reference. Shows: shebang, PASS/FAIL/TOTAL counters, `assert_eq()`, `assert_contains()`, `assert_not_contains()` helpers, temp directory setup, cleanup via trap, summary output.
- **`.aitask-scripts/aitask_explain_process_raw_data.py`** -- Shows the exact YAML structure of reference.yaml that tests need to create synthetically.
- **`.aitask-scripts/aitask_explain_format_context.py`** -- The Python script under test (from t369_1).
- **`.aitask-scripts/aitask_explain_context.sh`** -- The shell script under test (from t369_2).

## Detailed Implementation Steps

### Step 1: Create test file skeleton

**File:** `tests/test_explain_context.sh`

```bash
#!/usr/bin/env bash
# test_explain_context.sh - Tests for explain context scripts
# Run: bash tests/test_explain_context.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    expected="$(echo "$expected" | xargs)"
    actual="$(echo "$actual" | xargs)"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_exit_code() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected exit code $expected, got $actual)"
    fi
}
```

### Step 2: Set up temp directory and helper to create synthetic reference.yaml

```bash
TMPDIR_BASE=$(mktemp -d "${TMPDIR:-/tmp}/test_explain_ctx_XXXXXX")
trap 'rm -rf "$TMPDIR_BASE"' EXIT

FORMAT_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_explain_format_context.py"
CONTEXT_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_explain_context.sh"

# Create a synthetic run directory with reference.yaml and plan files
# Usage: create_test_run <run_dir> <file_path> <task_id1:start:end> [task_id2:start:end ...]
create_test_run() {
    local run_dir="$1"
    local file_path="$2"
    shift 2

    mkdir -p "$run_dir/plans" "$run_dir/tasks"

    # Start writing reference.yaml
    cat > "$run_dir/reference.yaml" << YAMLEOF
files:
  - path: "$file_path"
    commits: []
    line_ranges:
YAMLEOF

    # Add line ranges
    local task_ids=()
    for spec in "$@"; do
        IFS=':' read -r tid start end <<< "$spec"
        task_ids+=("$tid")
        cat >> "$run_dir/reference.yaml" << YAMLEOF
      - start: $start
        end: $end
        commits: [1]
        tasks: ["$tid"]
YAMLEOF
    done

    # Add tasks index
    echo "" >> "$run_dir/reference.yaml"
    echo "tasks:" >> "$run_dir/reference.yaml"

    for tid in $(printf '%s\n' "${task_ids[@]}" | sort -u); do
        cat >> "$run_dir/reference.yaml" << YAMLEOF
  - id: "$tid"
    task_file: "tasks/t${tid}.md"
    plan_file: "plans/p${tid}.md"
    has_notes: true
YAMLEOF

        # Create plan file
        cat > "$run_dir/plans/p${tid}.md" << PLANEOF
---
Task: t${tid}_test.md
---

# Plan for task $tid

This is the implementation plan for task $tid.
It contains important architectural decisions.

## Steps
1. Step one
2. Step two
PLANEOF
    done
}
```

### Step 3: Write Python formatter tests

**Test 3a: Basic single-file, single-plan formatting**

```bash
echo "--- Test: Python formatter - basic single plan ---"
test_dir="$TMPDIR_BASE/test3a"
run_dir="$test_dir/run__20260101_120000"
create_test_run "$run_dir" "src/foo.py" "166:1:50"

output=$(python3 "$FORMAT_SCRIPT" \
    --max-plans 1 \
    --ref "$run_dir/reference.yaml:$run_dir" \
    -- "src/foo.py" 2>/dev/null)

assert_contains "Output has header" "Historical Architectural Context" "$output"
assert_contains "Output has task ID" "t166" "$output"
assert_contains "Output has plan content" "implementation plan for task 166" "$output"
assert_contains "Output has context-for line" "Historical context for" "$output"
```

**Test 3b: Max-plans limiting**

```bash
echo "--- Test: Python formatter - max-plans limiting ---"
test_dir="$TMPDIR_BASE/test3b"
run_dir="$test_dir/run__20260101_120000"
create_test_run "$run_dir" "src/foo.py" "166:1:50" "209:51:80" "221:81:100"

output1=$(python3 "$FORMAT_SCRIPT" \
    --max-plans 1 \
    --ref "$run_dir/reference.yaml:$run_dir" \
    -- "src/foo.py" 2>/dev/null)

# With max-plans 1, only the top plan (166, 50 lines) should appear
assert_contains "Max-plans 1: has top plan" "t166" "$output1"

output2=$(python3 "$FORMAT_SCRIPT" \
    --max-plans 2 \
    --ref "$run_dir/reference.yaml:$run_dir" \
    -- "src/foo.py" 2>/dev/null)

# With max-plans 2, should have 2 plans
assert_contains "Max-plans 2: has plan 166" "t166" "$output2"
assert_contains "Max-plans 2: has plan 209" "t209" "$output2"
```

**Test 3c: Cross-file deduplication**

```bash
echo "--- Test: Python formatter - cross-file deduplication ---"
test_dir="$TMPDIR_BASE/test3c"
run_dir="$test_dir/run__20260101_120000"

# Create reference.yaml with 2 files both referencing task 166
mkdir -p "$run_dir/plans" "$run_dir/tasks"
cat > "$run_dir/reference.yaml" << 'YAMLEOF'
files:
  - path: "src/foo.py"
    commits: []
    line_ranges:
      - start: 1
        end: 50
        commits: [1]
        tasks: ["166"]
  - path: "src/bar.py"
    commits: []
    line_ranges:
      - start: 1
        end: 30
        commits: [1]
        tasks: ["166"]

tasks:
  - id: "166"
    task_file: "tasks/t166.md"
    plan_file: "plans/p166.md"
    has_notes: true
YAMLEOF

cat > "$run_dir/plans/p166.md" << 'PLANEOF'
---
Task: t166_test.md
---

# Plan for task 166

Implementation plan content.
PLANEOF

output=$(python3 "$FORMAT_SCRIPT" \
    --max-plans 1 \
    --ref "$run_dir/reference.yaml:$run_dir" \
    -- "src/foo.py" "src/bar.py" 2>/dev/null)

# Task 166 should appear only once
plan_count=$(echo "$output" | grep -c "### t166" || true)
assert_eq "Dedup: plan appears once" "1" "$plan_count"

# Should list both files in the context-for line
assert_contains "Dedup: lists both files" "src/foo.py" "$output"
assert_contains "Dedup: lists both files" "src/bar.py" "$output"
```

**Test 3d: Missing plan file**

```bash
echo "--- Test: Python formatter - missing plan file ---"
test_dir="$TMPDIR_BASE/test3d"
run_dir="$test_dir/run__20260101_120000"
create_test_run "$run_dir" "src/foo.py" "999:1:50"
# Delete the plan file
rm "$run_dir/plans/p999.md"

output=$(python3 "$FORMAT_SCRIPT" \
    --max-plans 1 \
    --ref "$run_dir/reference.yaml:$run_dir" \
    -- "src/foo.py" 2>/dev/null)
ec=$?

assert_eq "Missing plan: exit code 0" "0" "$ec"
assert_contains "Missing plan: notes mention missing" "missing" "$output"
```

**Test 3e: No matching files**

```bash
echo "--- Test: Python formatter - no matching files ---"
test_dir="$TMPDIR_BASE/test3e"
run_dir="$test_dir/run__20260101_120000"
create_test_run "$run_dir" "src/foo.py" "166:1:50"

output=$(python3 "$FORMAT_SCRIPT" \
    --max-plans 1 \
    --ref "$run_dir/reference.yaml:$run_dir" \
    -- "src/nonexistent.py" 2>/dev/null)
ec=$?

assert_eq "No match: exit code 0" "0" "$ec"
# Output should be empty or minimal
```

**Test 3f: max-plans 0 exits immediately**

```bash
echo "--- Test: Python formatter - max-plans 0 ---"
output=$(python3 "$FORMAT_SCRIPT" \
    --max-plans 0 \
    --ref "dummy:dummy" \
    -- "dummy.py" 2>/dev/null)
ec=$?
assert_eq "Max-plans 0: clean exit" "0" "$ec"
```

### Step 4: Write shell orchestrator tests

**Test 4a: No-op when max-plans is 0**

```bash
echo "--- Test: Shell orchestrator - max-plans 0 no-op ---"
output=$("$CONTEXT_SCRIPT" --max-plans 0 "some_file.sh" 2>/dev/null)
ec=$?
assert_eq "No-op: exit code 0" "0" "$ec"
assert_eq "No-op: empty output" "" "$output"
```

**Test 4b: Help flag**

```bash
echo "--- Test: Shell orchestrator - help flag ---"
output=$("$CONTEXT_SCRIPT" --help 2>/dev/null)
ec=$?
assert_eq "Help: exit code 0" "0" "$ec"
assert_contains "Help: shows usage" "Usage" "$output"
```

### Step 5: Write summary

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

## Verification

1. Run: `bash tests/test_explain_context.sh` -- all tests should pass
2. Run twice in a row -- both should pass (no stale state)
3. After running, verify temp directory is cleaned up
4. `shellcheck tests/test_explain_context.sh` -- should be clean (non-blocking)

## Step 9: Post-Implementation

Follow `.claude/skills/task-workflow/SKILL.md` Step 9 for cleanup, archival, and merge.
