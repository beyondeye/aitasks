#!/usr/bin/env bash
# test_explain_context.sh - Automated tests for aitask_explain_context.sh
# Run: bash tests/test_explain_context.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_explain_context.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
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
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_exit_zero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (command exited non-zero)"
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Setup ---

TMPDIR_BASE="$(mktemp -d "${TMPDIR:-/tmp}/explain_ctx_XXXXXX")"

# Create a minimal git repo for testing
setup_git_repo() {
    local repo_dir="$TMPDIR_BASE/repo"
    mkdir -p "$repo_dir/src" "$repo_dir/.aitask-scripts/lib"
    cd "$repo_dir"
    git init -q
    git config user.email "test@test.com"
    git config user.name "Test"

    # Create minimal task_utils.sh and terminal_compat.sh
    cat > "$repo_dir/.aitask-scripts/lib/terminal_compat.sh" << 'SHEOF'
[[ -n "${_AIT_TERMINAL_COMPAT_LOADED:-}" ]] && return
_AIT_TERMINAL_COMPAT_LOADED=1
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'
die()     { echo -e "${RED}Error: $1${NC}" >&2; exit 1; }
die_code() { local code="$1"; shift; echo -e "${RED}Error: $1${NC}" >&2; exit "$code"; }
info()    { echo -e "${BLUE}$1${NC}"; }
warn()    { echo -e "${YELLOW}Warning: $1${NC}" >&2; }
SHEOF

    cat > "$repo_dir/.aitask-scripts/lib/task_utils.sh" << 'SHEOF'
[[ -n "${_AIT_TASK_UTILS_LOADED:-}" ]] && return
_AIT_TASK_UTILS_LOADED=1
SCRIPT_DIR_TU="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR_TU/terminal_compat.sh"
SHEOF

    # Create a source file and commit it
    echo 'print("hello")' > "$repo_dir/src/foo.py"
    echo 'print("bar")' > "$repo_dir/src/bar.py"
    git add -A
    git commit -q -m "Initial commit"

    echo "$repo_dir"
}

# Create a pre-populated codebrowser cache directory
setup_cache() {
    local repo_dir="$1"
    local cb_dir="$repo_dir/.aitask-explain/codebrowser"
    local run_dir="$cb_dir/src__20990101_120000"
    mkdir -p "$run_dir/plans"

    cat > "$run_dir/reference.yaml" << 'YAMLEOF'
files:
  - path: src/foo.py
    line_ranges:
      - start: 1
        end: 50
        commits: [1]
        tasks: ["100"]
  - path: src/bar.py
    line_ranges:
      - start: 1
        end: 30
        commits: [1]
        tasks: ["100"]

tasks:
  - id: "100"
    task_file: "tasks/t100.md"
    plan_file: "plans/p100.md"
YAMLEOF

    cat > "$run_dir/plans/p100.md" << 'EOF'
---
Task: t100_test.md
---

# Test Plan

This is a test plan for verification.

## Steps
1. Do something
EOF

    echo "$run_dir"
}

# Copy the script under test and the format script to the test repo
install_scripts() {
    local repo_dir="$1"
    cp "$SCRIPT" "$repo_dir/.aitask-scripts/aitask_explain_context.sh"
    chmod +x "$repo_dir/.aitask-scripts/aitask_explain_context.sh"

    # Copy the Python formatter
    cp "$PROJECT_DIR/.aitask-scripts/aitask_explain_format_context.py" \
        "$repo_dir/.aitask-scripts/aitask_explain_format_context.py"
    chmod +x "$repo_dir/.aitask-scripts/aitask_explain_format_context.py"

    # Create a stub extract script that outputs a known RUN_DIR
    cat > "$repo_dir/.aitask-scripts/aitask_explain_extract_raw_data.sh" << 'EXEOF'
#!/usr/bin/env bash
# Stub extract script for testing
set -euo pipefail

AITASK_EXPLAIN_DIR="${AITASK_EXPLAIN_DIR:-.aitask-explain}"
SOURCE_KEY=""
DIR_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-recurse|--gather) shift ;;
        --source-key) SOURCE_KEY="$2"; shift 2 ;;
        *) DIR_PATH="$1"; shift ;;
    esac
done

# Create a run dir with reference.yaml
run_id="$(date +%Y%m%d_%H%M%S)"
run_dir="${AITASK_EXPLAIN_DIR}/${SOURCE_KEY}__${run_id}"
mkdir -p "$run_dir/plans"

cat > "$run_dir/reference.yaml" << 'YAMLEOF'
files:
  - path: src/foo.py
    line_ranges:
      - start: 1
        end: 10
        commits: [1]
        tasks: ["999"]

tasks:
  - id: "999"
    task_file: "tasks/t999.md"
    plan_file: "plans/p999.md"
YAMLEOF

cat > "$run_dir/plans/p999.md" << 'EOF'
# Generated Test Plan

Auto-generated by stub extract script.
EOF

echo "RUN_DIR: $run_dir"
EXEOF
    chmod +x "$repo_dir/.aitask-scripts/aitask_explain_extract_raw_data.sh"
}

# --- Tests ---

REPO_DIR=$(setup_git_repo)
install_scripts "$REPO_DIR"

# Test 1: --max-plans 0 is a no-op
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 0 2>&1)
exit_code=$?
assert_eq "no-op with --max-plans 0 exits 0" "0" "$exit_code"
assert_eq "no-op produces no output" "" "$output"

# Test 2: --help shows usage
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --help 2>&1)
assert_contains "help shows usage" "Usage:" "$output"
assert_contains "help shows --max-plans" "--max-plans" "$output"
assert_contains "help shows examples" "Examples:" "$output"

# Test 3: -h also shows help
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh -h 2>&1)
assert_contains "short help flag works" "Usage:" "$output"

# Test 4: No files specified produces error
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 2>&1 || true)
assert_contains "no files error" "No input files specified" "$output"

# Test 5: --max-plans without value produces error
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2>&1 || true)
assert_contains "missing max-plans value error" "requires a number" "$output"

# Test 6: Non-existent file with no cache exits gracefully
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 nonexistent.py 2>&1)
exit_code=$?
assert_eq "non-existent file exits 0" "0" "$exit_code"

# Test 7: With pre-populated cache, produces markdown output
run_dir=$(setup_cache "$REPO_DIR")
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 src/foo.py 2>&1)
assert_contains "cached data produces header" "## Historical Architectural Context" "$output"
assert_contains "cached data includes task id" "t100" "$output"
assert_contains "cached data includes file reference" "src/foo.py" "$output"
assert_contains "cached data includes plan content" "Test Plan" "$output"

# Test 8: Multiple files from same directory use same cache
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 src/foo.py src/bar.py 2>&1)
assert_contains "multi-file same dir has header" "## Historical Architectural Context" "$output"
assert_contains "multi-file includes first file" "src/foo.py" "$output"
assert_contains "multi-file includes second file" "src/bar.py" "$output"

# Test 9: -- separator works for file args
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 -- src/foo.py 2>&1)
assert_contains "separator works" "## Historical Architectural Context" "$output"

# Test 10: Staleness detection - create cache with old timestamp, then check
# Create a cache entry with a timestamp from the past (before the initial commit)
stale_cb="$REPO_DIR/.aitask-explain/codebrowser"
rm -rf "$stale_cb"
mkdir -p "$stale_cb"
stale_run="$stale_cb/src__20200101_120000"
mkdir -p "$stale_run/plans"
cp "$REPO_DIR/.aitask-explain/codebrowser/../codebrowser/src__20990101_120000/reference.yaml" "$stale_run/reference.yaml" 2>/dev/null || \
cat > "$stale_run/reference.yaml" << 'YAMLEOF'
files:
  - path: src/foo.py
    line_ranges:
      - start: 1
        end: 10
        commits: [1]
        tasks: ["100"]
tasks:
  - id: "100"
    task_file: "tasks/t100.md"
    plan_file: "plans/p100.md"
YAMLEOF
cat > "$stale_run/plans/p100.md" << 'EOF'
# Old Stale Plan
This should be replaced.
EOF

# The stale cache timestamp (20200101) is before any git commit
# The script should detect staleness and regenerate via extract script (task 999)
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 src/foo.py 2>&1)
assert_contains "stale cache triggers regeneration" "t999" "$output"
assert_contains "regenerated data has content" "Generated Test Plan" "$output"

# Test 11: Cache miss triggers extract pipeline
# Remove all cached data
rm -rf "$REPO_DIR/.aitask-explain/codebrowser"
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 src/foo.py 2>&1)
assert_contains "cache miss triggers extract" "t999" "$output"

# Test 12: Verify run dir was created by extract
TOTAL=$((TOTAL + 1))
if ls "$REPO_DIR/.aitask-explain/codebrowser/src__"[0-9]* >/dev/null 2>&1; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: extract should create run dir in codebrowser/"
fi

# Test 13: Files from different directories create separate cache entries
mkdir -p "$REPO_DIR/lib"
echo 'module Lib' > "$REPO_DIR/lib/utils.rb"
git -C "$REPO_DIR" add lib/utils.rb
git -C "$REPO_DIR" commit -q -m "Add lib"

rm -rf "$REPO_DIR/.aitask-explain/codebrowser"
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 src/foo.py lib/utils.rb 2>&1)
# Should have tried to process both src and lib directories
TOTAL=$((TOTAL + 1))
src_count=$(ls -d "$REPO_DIR/.aitask-explain/codebrowser/src__"[0-9]* 2>/dev/null | wc -l | tr -d ' ')
lib_count=$(ls -d "$REPO_DIR/.aitask-explain/codebrowser/lib__"[0-9]* 2>/dev/null | wc -l | tr -d ' ')
if [[ "$src_count" -ge 1 && "$lib_count" -ge 1 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: multi-dir should create separate cache entries (src=$src_count, lib=$lib_count)"
fi

# Test 14: dir_to_key for root directory files
# Create a root-level file
echo 'root file' > "$REPO_DIR/README.md"
git -C "$REPO_DIR" add README.md
git -C "$REPO_DIR" commit -q -m "Add readme"

rm -rf "$REPO_DIR/.aitask-explain/codebrowser"
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 1 README.md 2>&1)
TOTAL=$((TOTAL + 1))
if ls -d "$REPO_DIR/.aitask-explain/codebrowser/_root___"[0-9]* >/dev/null 2>&1; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: root dir files should use _root_ key"
fi

# Test 15: Extract pipeline failure is handled gracefully
# Create a failing extract script
mv "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh" \
   "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh.bak"
cat > "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh" << 'EOF'
#!/usr/bin/env bash
echo "Simulated failure" >&2
exit 1
EOF
chmod +x "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh"

rm -rf "$REPO_DIR/.aitask-explain/codebrowser"
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 src/foo.py 2>&1)
exit_code=$?
assert_eq "extract failure exits 0 (graceful)" "0" "$exit_code"

# Restore working extract script
mv "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh.bak" \
   "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh"

# Test 16: Extract script not producing RUN_DIR is handled
cat > "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh.norundirtest" << 'EOF'
#!/usr/bin/env bash
echo "Some output without RUN_DIR"
exit 0
EOF
chmod +x "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh.norundirtest"
mv "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh" \
   "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh.bak2"
mv "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh.norundirtest" \
   "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh"

rm -rf "$REPO_DIR/.aitask-explain/codebrowser"
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 src/foo.py 2>&1)
exit_code=$?
assert_eq "no RUN_DIR exits 0 (graceful)" "0" "$exit_code"

# Restore working extract script
mv "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh.bak2" \
   "$REPO_DIR/.aitask-scripts/aitask_explain_extract_raw_data.sh"

# Test 17: Cache reuse (second run uses existing cache)
rm -rf "$REPO_DIR/.aitask-explain/codebrowser"
cd "$REPO_DIR"
./.aitask-scripts/aitask_explain_context.sh --max-plans 1 src/foo.py >/dev/null 2>&1

# Record cache state
cache_before=$(ls -d "$REPO_DIR/.aitask-explain/codebrowser/src__"[0-9]* 2>/dev/null)

# Run again — should reuse cache (no new run dir created)
./.aitask-scripts/aitask_explain_context.sh --max-plans 1 src/foo.py >/dev/null 2>&1
cache_after=$(ls -d "$REPO_DIR/.aitask-explain/codebrowser/src__"[0-9]* 2>/dev/null)

assert_eq "cache reuse: same run dir" "$cache_before" "$cache_after"

# Test 18: Context notes section present in output
rm -rf "$REPO_DIR/.aitask-explain/codebrowser"
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 2 src/foo.py 2>&1)
assert_contains "output has context notes" "Context Notes" "$output"

# Test 19: Nested directory path (dir_to_key with multiple segments)
mkdir -p "$REPO_DIR/a/b/c"
echo 'nested' > "$REPO_DIR/a/b/c/deep.txt"
git -C "$REPO_DIR" add a/b/c/deep.txt
git -C "$REPO_DIR" commit -q -m "Add nested file"

rm -rf "$REPO_DIR/.aitask-explain/codebrowser"
output=$(cd "$REPO_DIR" && ./.aitask-scripts/aitask_explain_context.sh --max-plans 1 a/b/c/deep.txt 2>&1)
TOTAL=$((TOTAL + 1))
if ls -d "$REPO_DIR/.aitask-explain/codebrowser/a__b__c__"[0-9]* >/dev/null 2>&1; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: nested dir should use a__b__c key"
fi

# Test 20: Shellcheck passes (info-level SC1091 is acceptable)
TOTAL=$((TOTAL + 1))
sc_output=$(shellcheck "$SCRIPT" 2>&1 || true)
if echo "$sc_output" | grep -q "SC[0-9]" && ! echo "$sc_output" | grep -q "SC1091"; then
    FAIL=$((FAIL + 1))
    echo "FAIL: shellcheck reported issues other than SC1091: $sc_output"
else
    PASS=$((PASS + 1))
fi

# --- Cleanup ---
rm -rf "$TMPDIR_BASE"

# --- Summary ---
echo ""
echo "=== Test Results ==="
echo "Total: $TOTAL  Pass: $PASS  Fail: $FAIL"

if [[ $FAIL -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
else
    echo "ALL TESTS PASSED"
    exit 0
fi
