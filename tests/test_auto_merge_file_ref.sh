#!/usr/bin/env bash
# test_auto_merge_file_ref.sh - Tests for aitask_create.sh --auto-merge flag
# Run: bash tests/test_auto_merge_file_ref.sh
#
# Covers:
#   - Default no-auto-merge keeps existing tasks standalone
#   - --auto-merge folds matching pending tasks into the new task
#   - --no-auto-merge is explicit (and equivalent to default)
#   - Status filter: non-Ready/Editing tasks are never folded
#   - Transitive fold: pre-folded A gets folded_into re-pointed
#   - No-op when no file refs and no candidates

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

        # Create scripts needed by create + auto-merge + verification
        cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_find_by_file.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_validate.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_content.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
        chmod +x .aitask-scripts/*.sh

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

# Helper: resolve task file path by name glob in aitasks/
find_task_file() {
    local repo="$1" name="$2"
    ls "$repo/aitasks"/t*_"$name".md 2>/dev/null | head -1
}

# Helper: extract a single-field value from a task file frontmatter
get_field() {
    local file="$1" field="$2"
    grep "^${field}:" "$file" 2>/dev/null | head -1 | sed "s/^${field}: *//"
}

# Helper: extract numeric id from a task file path like .../t42_name.md
task_num_from_file() {
    basename "$1" | grep -oE '^t[0-9]+' | sed 's/t//'
}

set +e

echo "=== auto-merge --file-ref Tests ==="
echo ""

# --- Test 1: Default (no flag) does not fold ---
echo "--- Test 1: Default (no flag) does not fold ---"
TMPDIR_1="$(setup_project)"
(cd "$TMPDIR_1/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "a1" \
        --desc "first" --file-ref "foo.py" >/dev/null 2>&1)
(cd "$TMPDIR_1/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "b1" \
        --desc "second" --file-ref "foo.py" >/dev/null 2>&1)
a1_file=$(find_task_file "$TMPDIR_1/local" a1)
b1_file=$(find_task_file "$TMPDIR_1/local" b1)
assert_eq "T1: a1 still Ready (not folded)" "Ready" "$(get_field "$a1_file" status)"
assert_eq "T1: b1 has no folded_tasks" "" "$(get_field "$b1_file" folded_tasks)"
rm -rf "$TMPDIR_1"

# --- Test 2: --auto-merge folds matching task ---
echo "--- Test 2: --auto-merge folds matching task ---"
TMPDIR_2="$(setup_project)"
(cd "$TMPDIR_2/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "a2" \
        --desc "first" --file-ref "foo.py" >/dev/null 2>&1)
a2_file=$(find_task_file "$TMPDIR_2/local" a2)
a2_id=$(task_num_from_file "$a2_file")
(cd "$TMPDIR_2/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "b2" \
        --desc "second" --file-ref "foo.py" --auto-merge >/dev/null 2>&1)
b2_file=$(find_task_file "$TMPDIR_2/local" b2)
b2_id=$(task_num_from_file "$b2_file")
assert_eq "T2: a2 status is Folded" "Folded" "$(get_field "$a2_file" status)"
assert_eq "T2: a2 folded_into points to b2" "$b2_id" "$(get_field "$a2_file" folded_into)"
assert_contains "T2: b2 folded_tasks contains a2" "$a2_id" "$(get_field "$b2_file" folded_tasks)"
rm -rf "$TMPDIR_2"

# --- Test 3: --no-auto-merge is explicit no-op ---
echo "--- Test 3: --no-auto-merge is explicit ---"
TMPDIR_3="$(setup_project)"
(cd "$TMPDIR_3/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "a3" \
        --desc "first" --file-ref "foo.py" >/dev/null 2>&1)
(cd "$TMPDIR_3/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "b3" \
        --desc "second" --file-ref "foo.py" --no-auto-merge >/dev/null 2>&1)
a3_file=$(find_task_file "$TMPDIR_3/local" a3)
b3_file=$(find_task_file "$TMPDIR_3/local" b3)
assert_eq "T3: a3 still Ready with explicit --no-auto-merge" "Ready" "$(get_field "$a3_file" status)"
assert_eq "T3: b3 has no folded_tasks" "" "$(get_field "$b3_file" folded_tasks)"
rm -rf "$TMPDIR_3"

# --- Test 4: Status filter - non-Ready task not folded ---
echo "--- Test 4: Status filter (Postponed task not folded) ---"
TMPDIR_4="$(setup_project)"
(cd "$TMPDIR_4/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "a4" \
        --desc "first" --file-ref "foo.py" >/dev/null 2>&1)
a4_file=$(find_task_file "$TMPDIR_4/local" a4)
a4_id=$(task_num_from_file "$a4_file")
(cd "$TMPDIR_4/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$a4_id" --status Postponed >/dev/null 2>&1)
(cd "$TMPDIR_4/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "d4" \
        --desc "second" --file-ref "foo.py" --auto-merge >/dev/null 2>&1)
d4_file=$(find_task_file "$TMPDIR_4/local" d4)
assert_eq "T4: a4 remains Postponed (not folded)" "Postponed" "$(get_field "$a4_file" status)"
assert_eq "T4: d4 has no folded_tasks" "" "$(get_field "$d4_file" folded_tasks)"
rm -rf "$TMPDIR_4"

# --- Test 5: Transitive fold re-points A's folded_into ---
echo "--- Test 5: Transitive fold ---"
TMPDIR_5="$(setup_project)"
(cd "$TMPDIR_5/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "a5" \
        --desc "first" --file-ref "foo.py" >/dev/null 2>&1)
(cd "$TMPDIR_5/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "b5" \
        --desc "second" --file-ref "foo.py" >/dev/null 2>&1)
a5_file=$(find_task_file "$TMPDIR_5/local" a5)
b5_file=$(find_task_file "$TMPDIR_5/local" b5)
a5_id=$(task_num_from_file "$a5_file")
b5_id=$(task_num_from_file "$b5_file")
# Manually pre-fold a5 into b5 so b5.folded_tasks=[a5], a5.status=Folded
(cd "$TMPDIR_5/local" && \
    ./.aitask-scripts/aitask_fold_mark.sh --commit-mode fresh "$b5_id" "$a5_id" >/dev/null 2>&1)
# Sanity check pre-fold state
assert_eq "T5 setup: a5 is Folded" "Folded" "$(get_field "$a5_file" status)"
assert_eq "T5 setup: a5 folded_into=b5" "$b5_id" "$(get_field "$a5_file" folded_into)"
# Now create e5 with --auto-merge; b5 (still Ready, unchanged body) should be folded into e5
(cd "$TMPDIR_5/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "e5" \
        --desc "third" --file-ref "foo.py" --auto-merge >/dev/null 2>&1)
e5_file=$(find_task_file "$TMPDIR_5/local" e5)
e5_id=$(task_num_from_file "$e5_file")
assert_eq "T5: b5 now Folded" "Folded" "$(get_field "$b5_file" status)"
assert_eq "T5: b5 folded_into=e5" "$e5_id" "$(get_field "$b5_file" folded_into)"
assert_eq "T5: a5 folded_into transitively re-pointed to e5" "$e5_id" "$(get_field "$a5_file" folded_into)"
assert_contains "T5: e5 folded_tasks contains b5" "$b5_id" "$(get_field "$e5_file" folded_tasks)"
assert_contains "T5: e5 folded_tasks contains a5 (transitive)" "$a5_id" "$(get_field "$e5_file" folded_tasks)"
rm -rf "$TMPDIR_5"

# --- Test 6: No candidates is a silent no-op ---
echo "--- Test 6: No candidates is a no-op ---"
TMPDIR_6="$(setup_project)"
(cd "$TMPDIR_6/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "x6" \
        --desc "lone" --file-ref "baz.py" --auto-merge >/dev/null 2>&1)
x6_file=$(find_task_file "$TMPDIR_6/local" x6)
assert_eq "T6: x6 created Ready" "Ready" "$(get_field "$x6_file" status)"
assert_eq "T6: x6 has no folded_tasks" "" "$(get_field "$x6_file" folded_tasks)"
rm -rf "$TMPDIR_6"

# --- Test 7: No --file-ref is a silent no-op ---
echo "--- Test 7: No --file-ref is a no-op ---"
TMPDIR_7="$(setup_project)"
(cd "$TMPDIR_7/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "y7" \
        --desc "norefs" --auto-merge >/dev/null 2>&1)
y7_file=$(find_task_file "$TMPDIR_7/local" y7)
assert_eq "T7: y7 created Ready" "Ready" "$(get_field "$y7_file" status)"
assert_eq "T7: y7 has no folded_tasks" "" "$(get_field "$y7_file" folded_tasks)"
rm -rf "$TMPDIR_7"

# --- Test 8: Finalize-path auto-merge via --batch --finalize ---
echo "--- Test 8: Finalize-path auto-merge ---"
TMPDIR_8="$(setup_project)"
# Step 1: Create A with --commit so there's an existing match.
(cd "$TMPDIR_8/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "a8" \
        --desc "first" --file-ref "foo.py" >/dev/null 2>&1)
a8_file=$(find_task_file "$TMPDIR_8/local" a8)
a8_id=$(task_num_from_file "$a8_file")

# Step 2: Create a draft (batch, no --commit) that references the same file.
(cd "$TMPDIR_8/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "b8" \
        --desc "second" --file-ref "foo.py" >/dev/null 2>&1)
draft_file=$(ls "$TMPDIR_8/local/aitasks/new"/draft_*_b8.md 2>/dev/null | head -1)

# Step 3: Finalize the draft with --auto-merge.
(cd "$TMPDIR_8/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --finalize "$(basename "$draft_file")" \
        --auto-merge >/dev/null 2>&1)
b8_file=$(find_task_file "$TMPDIR_8/local" b8)
b8_id=$(task_num_from_file "$b8_file")

assert_eq "T8: a8 status is Folded (finalize path)" "Folded" "$(get_field "$a8_file" status)"
assert_eq "T8: a8 folded_into points to b8" "$b8_id" "$(get_field "$a8_file" folded_into)"
assert_contains "T8: b8 folded_tasks contains a8" "$a8_id" "$(get_field "$b8_file" folded_tasks)"
rm -rf "$TMPDIR_8"

# --- Test 9: Syntax check on aitask_create.sh ---
echo "--- Test 9: Syntax check ---"
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_create.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Syntax check on aitask_create.sh"
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
