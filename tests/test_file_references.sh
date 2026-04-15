#!/usr/bin/env bash
# test_file_references.sh - Tests for file_references frontmatter field
# Run: bash tests/test_file_references.sh
#
# Covers: create/update/draft round-trip, compact multi-range entries,
# exact-string dedup semantics, aitask_find_by_file.sh path-only match
# and status filter, and malformed-input rejection.

set -e

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
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qF "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (did NOT want '$needle', but it was present)"
    else
        PASS=$((PASS + 1))
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit)"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Project setup ---

setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived aitasks/metadata aitasks/new .aitask-scripts/lib

        cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_find_by_file.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
        chmod +x .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_claim_id.sh \
            .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_find_by_file.sh

        printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
            > aitasks/metadata/task_types.txt

        echo "aitasks/new/" > .gitignore

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null

        ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1
    )

    echo "$tmpdir"
}

# Helper: extract the single draft file from aitasks/new/
draft_path() {
    local repo="$1" name="$2"
    ls "$repo/aitasks/new/"draft_*_"$name".md 2>/dev/null | head -1
}

# Helper: read file_references line from a task/draft file frontmatter
read_file_refs_line() {
    local file="$1"
    grep '^file_references:' "$file" 2>/dev/null || true
}

set +e

echo "=== file_references Tests ==="
echo ""

# --- Test 1: Single --file-ref in batch create ---
echo "--- Test 1: Single --file-ref ---"
TMPDIR_1="$(setup_project)"
(cd "$TMPDIR_1/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t1" --desc "one ref" \
        --file-ref "foo.py" >/dev/null 2>&1)
draft1=$(draft_path "$TMPDIR_1/local" t1)
refs_line1=$(read_file_refs_line "$draft1")
assert_eq "Single ref in frontmatter" "file_references: [foo.py]" "$refs_line1"
rm -rf "$TMPDIR_1"

# --- Test 2: Multiple --file-ref mixed flags ---
echo "--- Test 2: Multiple --file-ref mixed flags ---"
TMPDIR_2="$(setup_project)"
(cd "$TMPDIR_2/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t2" --desc "mixed" \
        --file-ref "a.py" --file-ref "b.py:10-20" >/dev/null 2>&1)
draft2=$(draft_path "$TMPDIR_2/local" t2)
refs_line2=$(read_file_refs_line "$draft2")
assert_eq "Mixed refs preserve order" "file_references: [a.py, b.py:10-20]" "$refs_line2"
rm -rf "$TMPDIR_2"

# --- Test 3: Compact multi-range preserved verbatim ---
echo "--- Test 3: Compact multi-range preserved verbatim ---"
TMPDIR_3="$(setup_project)"
(cd "$TMPDIR_3/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t3" --desc "compact" \
        --file-ref "foo.py:10-20^30-40^89-100" >/dev/null 2>&1)
draft3=$(draft_path "$TMPDIR_3/local" t3)
refs_line3=$(read_file_refs_line "$draft3")
assert_eq "Compact multi-range kept as single entry" \
    "file_references: [foo.py:10-20^30-40^89-100]" "$refs_line3"
rm -rf "$TMPDIR_3"

# --- Test 4: Same ref twice dedups to single entry ---
echo "--- Test 4: Exact-string dedup on create ---"
TMPDIR_4="$(setup_project)"
(cd "$TMPDIR_4/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t4" --desc "dup" \
        --file-ref "foo.py:10-20" --file-ref "foo.py:10-20" >/dev/null 2>&1)
draft4=$(draft_path "$TMPDIR_4/local" t4)
refs_line4=$(read_file_refs_line "$draft4")
assert_eq "Duplicate exact-string ref deduped" \
    "file_references: [foo.py:10-20]" "$refs_line4"
rm -rf "$TMPDIR_4"

# --- Test 5: Order-sensitive dedup keeps two entries ---
echo "--- Test 5: Order-sensitive dedup keeps two entries ---"
TMPDIR_5="$(setup_project)"
(cd "$TMPDIR_5/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t5" --desc "order" \
        --file-ref "foo.py:10-20^30-40" \
        --file-ref "foo.py:30-40^10-20" >/dev/null 2>&1)
draft5=$(draft_path "$TMPDIR_5/local" t5)
refs_line5=$(read_file_refs_line "$draft5")
assert_eq "Reordered ranges are NOT deduped" \
    "file_references: [foo.py:10-20^30-40, foo.py:30-40^10-20]" "$refs_line5"
rm -rf "$TMPDIR_5"

# --- Test 6: Batch update --file-ref appends ---
echo "--- Test 6: Batch update --file-ref appends ---"
TMPDIR_6="$(setup_project)"
(cd "$TMPDIR_6/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "upd1" \
        --desc "initial" --file-ref "a.py" >/dev/null 2>&1)
task6=$(ls "$TMPDIR_6/local/aitasks"/t*_upd1.md 2>/dev/null | head -1)
task6_num=$(basename "$task6" | grep -oE '^t[0-9]+' | sed 's/t//')
(cd "$TMPDIR_6/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$task6_num" \
        --file-ref "c.py" >/dev/null 2>&1)
refs_line6=$(read_file_refs_line "$task6")
assert_eq "Update appends new ref" \
    "file_references: [a.py, c.py]" "$refs_line6"
rm -rf "$TMPDIR_6"

# --- Test 7: Batch update --remove-file-ref removes existing ---
echo "--- Test 7: Batch update --remove-file-ref removes ---"
TMPDIR_7="$(setup_project)"
(cd "$TMPDIR_7/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "upd2" \
        --desc "initial" --file-ref "a.py" --file-ref "b.py:10" >/dev/null 2>&1)
task7=$(ls "$TMPDIR_7/local/aitasks"/t*_upd2.md 2>/dev/null | head -1)
task7_num=$(basename "$task7" | grep -oE '^t[0-9]+' | sed 's/t//')
(cd "$TMPDIR_7/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$task7_num" \
        --remove-file-ref "a.py" >/dev/null 2>&1)
refs_line7=$(read_file_refs_line "$task7")
assert_eq "Update removes named ref" \
    "file_references: [b.py:10]" "$refs_line7"
rm -rf "$TMPDIR_7"

# --- Test 8: get_file_references round-trip ---
echo "--- Test 8: get_file_references round-trip ---"
TMPDIR_8="$(setup_project)"
(cd "$TMPDIR_8/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "rt" \
        --desc "round-trip" \
        --file-ref "a.py" --file-ref "b.py:10-20" \
        --file-ref "c.py:5^15-25" >/dev/null 2>&1)
task8=$(ls "$TMPDIR_8/local/aitasks"/t*_rt.md 2>/dev/null | head -1)
helper_out=$(cd "$TMPDIR_8/local" && \
    bash -c 'source .aitask-scripts/lib/task_utils.sh && get_file_references "'"$task8"'"')
assert_contains "Round-trip includes a.py" "a.py" "$helper_out"
assert_contains "Round-trip includes b.py:10-20" "b.py:10-20" "$helper_out"
assert_contains "Round-trip includes c.py:5^15-25" "c.py:5^15-25" "$helper_out"
line_count8=$(echo "$helper_out" | grep -c .)
assert_eq "Three entries parsed back" "3" "$line_count8"
rm -rf "$TMPDIR_8"

# --- Test 9: aitask_find_by_file.sh path-only match ---
echo "--- Test 9: aitask_find_by_file.sh path-only match ---"
TMPDIR_9="$(setup_project)"
(cd "$TMPDIR_9/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "find1" \
        --desc "ready task" --file-ref "a.py:10-20^30-40" >/dev/null 2>&1)
(cd "$TMPDIR_9/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "find2" \
        --desc "exact path" --file-ref "a.py" >/dev/null 2>&1)
(cd "$TMPDIR_9/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "find3" \
        --desc "unrelated" --file-ref "other.py" >/dev/null 2>&1)
find_out9=$(cd "$TMPDIR_9/local" && ./.aitask-scripts/aitask_find_by_file.sh a.py 2>&1)
assert_contains "find1 matched (compact range)" "find1.md" "$find_out9"
assert_contains "find2 matched (bare path)" "find2.md" "$find_out9"
assert_not_contains "find3 not matched" "find3.md" "$find_out9"
match_count9=$(echo "$find_out9" | grep -c '^TASK:')
assert_eq "Exactly 2 matches for a.py" "2" "$match_count9"
rm -rf "$TMPDIR_9"

# --- Test 10: aitask_find_by_file.sh excludes non-Ready/Editing ---
echo "--- Test 10: Status filter in find helper ---"
TMPDIR_10="$(setup_project)"
(cd "$TMPDIR_10/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "stat1" \
        --desc "ready" --file-ref "filt.py" >/dev/null 2>&1)
(cd "$TMPDIR_10/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "stat2" \
        --desc "will be impl" --file-ref "filt.py" >/dev/null 2>&1)
task10_impl=$(ls "$TMPDIR_10/local/aitasks"/t*_stat2.md 2>/dev/null | head -1)
task10_impl_num=$(basename "$task10_impl" | grep -oE '^t[0-9]+' | sed 's/t//')
(cd "$TMPDIR_10/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$task10_impl_num" \
        --status "Implementing" >/dev/null 2>&1)

find_out10=$(cd "$TMPDIR_10/local" && ./.aitask-scripts/aitask_find_by_file.sh filt.py 2>&1)
assert_contains "Ready task still matched" "stat1.md" "$find_out10"
assert_not_contains "Implementing task excluded" "stat2.md" "$find_out10"
rm -rf "$TMPDIR_10"

# --- Test 11: Malformed --file-ref rejected ---
echo "--- Test 11: Malformed refs rejected ---"
TMPDIR_11="$(setup_project)"
assert_exit_nonzero "Reject non-numeric range in create" \
    bash -c "cd '$TMPDIR_11/local' && ./.aitask-scripts/aitask_create.sh --batch --name bad1 --desc x --file-ref 'foo.py:abc'"
assert_exit_nonzero "Reject bad tail range in create" \
    bash -c "cd '$TMPDIR_11/local' && ./.aitask-scripts/aitask_create.sh --batch --name bad2 --desc x --file-ref 'foo.py:10-20^bad'"
# Also test update path validation
(cd "$TMPDIR_11/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "okv" \
        --desc "ok" >/dev/null 2>&1)
task11=$(ls "$TMPDIR_11/local/aitasks"/t*_okv.md 2>/dev/null | head -1)
task11_num=$(basename "$task11" | grep -oE '^t[0-9]+' | sed 's/t//')
assert_exit_nonzero "Reject non-numeric range in update" \
    bash -c "cd '$TMPDIR_11/local' && ./.aitask-scripts/aitask_update.sh --batch $task11_num --file-ref 'foo.py:xyz'"
rm -rf "$TMPDIR_11"

# --- Test 12: Interactive mode seeds all_file_refs from BATCH_FILE_REFS ---
echo "--- Test 12: Interactive seed from BATCH_FILE_REFS ---"
TMPDIR_12="$(setup_project)"
seed_out=$(cd "$TMPDIR_12/local" && bash -c '
set +e
fzf() { :; }
info() { :; }
success() { :; }
warn() { :; }
die() { :; }
func_src=$(sed -n "/^get_task_definition() {/,/^}\$/p" .aitask-scripts/aitask_create.sh)
eval "$func_src"
BATCH_FILE_REFS=("foo.py:10-20" "bar.py")
get_task_definition </dev/null
' 2>/dev/null)
seed_refs=$(echo "$seed_out" | awk '/__FILE_REFS_MARKER__/{flag=1;next} flag')
assert_contains "Pre-seeded foo.py:10-20 flows through interactive path" "foo.py:10-20" "$seed_refs"
assert_contains "Pre-seeded bar.py flows through interactive path" "bar.py" "$seed_refs"
rm -rf "$TMPDIR_12"

# --- Test 13: Syntax check on all touched scripts ---
echo "--- Test 13: Syntax check ---"
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" && \
   bash -n "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" && \
   bash -n "$PROJECT_DIR/.aitask-scripts/aitask_find_by_file.sh" && \
   bash -n "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Syntax check on touched scripts"
fi

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
