#!/usr/bin/env bash
# test_aitask_merge.sh - Tests for aitask_merge.py auto-merge script (t228_2)
# Run: bash tests/test_aitask_merge.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
MERGE_SCRIPT="$PROJECT_DIR/aiscripts/board/aitask_merge.py"

PASS=0
FAIL=0
TOTAL=0
TMPDIR_TEST=""

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected: $(echo "$expected" | head -3)"
        echo "  actual:   $(echo "$actual" | head -3)"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected to contain '$expected')"
        echo "  actual: $(echo "$actual" | head -3)"
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

setup_tmpdir() {
    TMPDIR_TEST=$(mktemp -d)
}

cleanup_tmpdir() {
    [[ -n "$TMPDIR_TEST" ]] && rm -rf "$TMPDIR_TEST"
    TMPDIR_TEST=""
}

run_merge() {
    # Run aitask_merge.py from the board directory so imports work
    local file="$1"
    shift
    (cd "$PROJECT_DIR/aiscripts/board" && python3 aitask_merge.py "$file" "$@") 2>/dev/null
}

run_merge_with_stderr() {
    local file="$1"
    shift
    (cd "$PROJECT_DIR/aiscripts/board" && python3 aitask_merge.py "$file" "$@") 2>&1
}

# --- Test 1: Full auto-resolve (batch) ---

test_full_auto_resolve() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
priority: medium
effort: low
depends: [1, 3]
issue_type: feature
status: Ready
labels: [ui, backend]
updated_at: 2026-02-24 10:00
boardcol: now
boardidx: 40
---

## Task description
=======
---
priority: high
effort: high
depends: [1, 5]
issue_type: feature
status: Ready
labels: [backend, api]
updated_at: 2026-02-24 09:00
boardcol: next
boardidx: 80
---

## Task description
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    stdout=$(run_merge "$f" --batch) || true
    # Re-run to capture exit code properly
    set +e
    run_merge "$f" --batch > /dev/null 2>&1
    # File was already resolved on first run, re-create
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
priority: medium
effort: low
depends: [1, 3]
issue_type: feature
status: Ready
labels: [ui, backend]
updated_at: 2026-02-24 10:00
boardcol: now
boardidx: 40
---

## Task description
=======
---
priority: high
effort: high
depends: [1, 5]
issue_type: feature
status: Ready
labels: [backend, api]
updated_at: 2026-02-24 09:00
boardcol: next
boardidx: 80
---

## Task description
>>>>>>> origin/main
CONFLICT
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T1: stdout is RESOLVED" "RESOLVED" "$stdout"
    assert_exit_code "T1: exit code 0" "0" "$exit_code"

    # Verify merged content
    local content
    content=$(cat "$f")
    assert_contains "T1: boardcol kept LOCAL (now)" "boardcol: now" "$content"
    assert_contains "T1: boardidx kept LOCAL (40)" "boardidx: 40" "$content"
    assert_contains "T1: updated_at kept latest" "2026-02-24 10:00" "$content"
    assert_contains "T1: priority kept REMOTE (high)" "priority: high" "$content"
    assert_contains "T1: effort kept REMOTE (high)" "effort: high" "$content"
    # Labels should be union: api, backend, ui (sorted)
    assert_contains "T1: labels union contains api" "api" "$content"
    assert_contains "T1: labels union contains ui" "ui" "$content"
    assert_contains "T1: labels union contains backend" "backend" "$content"
    # Depends should be union: 1, 3, 5
    assert_contains "T1: depends union contains 3" "3" "$content"
    assert_contains "T1: depends union contains 5" "5" "$content"

    cleanup_tmpdir
}

# --- Test 2: Partial resolve (status conflict) ---

test_partial_resolve_status() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
priority: high
status: Done
updated_at: 2026-02-24 10:00
---

## Body
=======
---
priority: high
status: Postponed
updated_at: 2026-02-24 09:00
---

## Body
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T2: stdout is PARTIAL:status" "PARTIAL:status" "$stdout"
    assert_exit_code "T2: exit code 2" "2" "$exit_code"

    cleanup_tmpdir
}

# --- Test 3: Status Implementing wins ---

test_status_implementing_wins() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
status: Implementing
updated_at: 2026-02-24 10:00
---

## Body
=======
---
status: Ready
updated_at: 2026-02-24 09:00
---

## Body
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T3: stdout is RESOLVED" "RESOLVED" "$stdout"
    assert_exit_code "T3: exit code 0" "0" "$exit_code"

    local content
    content=$(cat "$f")
    assert_contains "T3: status is Implementing" "status: Implementing" "$content"

    cleanup_tmpdir
}

# --- Test 4: Body conflict ---

test_body_conflict() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
priority: high
updated_at: 2026-02-24 10:00
---

## Local body content
Some local text.
=======
---
priority: high
updated_at: 2026-02-24 10:00
---

## Remote body content
Some remote text.
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T4: stdout is PARTIAL:body" "PARTIAL:body" "$stdout"
    assert_exit_code "T4: exit code 2" "2" "$exit_code"

    local content
    content=$(cat "$f")
    assert_contains "T4: body has LOCAL marker" "<<<<<<< LOCAL" "$content"
    assert_contains "T4: body has local text" "Some local text." "$content"
    assert_contains "T4: body has remote text" "Some remote text." "$content"

    cleanup_tmpdir
}

# --- Test 5: No conflict markers ---

test_no_conflict_markers() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'EOF'
---
priority: high
status: Ready
---

## Normal task file
No conflict markers here.
EOF

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T5: stdout is SKIPPED" "SKIPPED" "$stdout"
    assert_exit_code "T5: exit code 1" "1" "$exit_code"

    cleanup_tmpdir
}

# --- Test 6: No frontmatter ---

test_no_frontmatter() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
# Just some markdown
No frontmatter here.
=======
# Different markdown
Also no frontmatter.
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T6: stdout is SKIPPED" "SKIPPED" "$stdout"
    assert_exit_code "T6: exit code 1" "1" "$exit_code"

    cleanup_tmpdir
}

# --- Test 7: diff3 style markers ---

test_diff3_markers() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
priority: low
effort: medium
status: Ready
updated_at: 2026-02-24 10:00
boardcol: now
---

## Body
||||||| merged common ancestor
---
priority: medium
effort: medium
status: Ready
updated_at: 2026-02-24 08:00
boardcol: next
---

## Body
=======
---
priority: high
effort: high
status: Ready
updated_at: 2026-02-24 09:00
boardcol: backlog
---

## Body
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T7: stdout is RESOLVED" "RESOLVED" "$stdout"
    assert_exit_code "T7: exit code 0" "0" "$exit_code"

    local content
    content=$(cat "$f")
    # boardcol should be LOCAL (now), not base or remote
    assert_contains "T7: boardcol kept LOCAL (now)" "boardcol: now" "$content"
    # priority should be REMOTE (high) in batch
    assert_contains "T7: priority kept REMOTE (high)" "priority: high" "$content"
    # updated_at should be latest (LOCAL: 10:00)
    assert_contains "T7: updated_at kept latest" "2026-02-24 10:00" "$content"

    cleanup_tmpdir
}

# --- Test 8: Field on one side only ---

test_field_one_side_only() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
priority: high
issue_type: feature
status: Ready
updated_at: 2026-02-24 10:00
---

## Body
=======
---
priority: high
assigned_to: user@example.com
status: Ready
updated_at: 2026-02-24 10:00
---

## Body
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T8: stdout is RESOLVED" "RESOLVED" "$stdout"
    assert_exit_code "T8: exit code 0" "0" "$exit_code"

    local content
    content=$(cat "$f")
    assert_contains "T8: has issue_type from LOCAL" "issue_type: feature" "$content"
    assert_contains "T8: has assigned_to from REMOTE" "assigned_to: user@example.com" "$content"

    cleanup_tmpdir
}

# --- Test 9: Key order preservation ---

test_key_order_preservation() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
priority: high
effort: low
status: Ready
labels: [ui]
updated_at: 2026-02-24 10:00
boardcol: now
boardidx: 40
---

## Body
=======
---
priority: high
effort: low
status: Ready
labels: [ui]
updated_at: 2026-02-24 10:00
boardcol: next
boardidx: 80
---

## Body
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T9: stdout is RESOLVED" "RESOLVED" "$stdout"

    local content
    content=$(cat "$f")
    # boardcol and boardidx should be at the end (after other fields)
    # Check that priority comes before boardcol in the output
    local priority_line boardcol_line
    priority_line=$(grep -n "^priority:" "$f" | head -1 | cut -d: -f1)
    boardcol_line=$(grep -n "^boardcol:" "$f" | head -1 | cut -d: -f1)
    if [[ -n "$priority_line" && -n "$boardcol_line" ]]; then
        TOTAL=$((TOTAL + 1))
        if [[ "$priority_line" -lt "$boardcol_line" ]]; then
            PASS=$((PASS + 1))
        else
            FAIL=$((FAIL + 1))
            echo "FAIL: T9: priority (line $priority_line) should come before boardcol (line $boardcol_line)"
        fi
    fi

    cleanup_tmpdir
}

# --- Test 10: Labels/depends dedup+sort ---

test_labels_depends_dedup_sort() {
    setup_tmpdir
    local f="$TMPDIR_TEST/task.md"
    cat > "$f" << 'CONFLICT'
<<<<<<< HEAD
---
labels: [backend, ui, api]
depends: [3, 1, 5]
updated_at: 2026-02-24 10:00
---

## Body
=======
---
labels: [api, backend, frontend]
depends: [1, 7, 3]
updated_at: 2026-02-24 10:00
---

## Body
>>>>>>> origin/main
CONFLICT

    local stdout exit_code
    set +e
    stdout=$(run_merge "$f" --batch)
    exit_code=$?
    set -e

    assert_eq "T10: stdout is RESOLVED" "RESOLVED" "$stdout"

    local content
    content=$(cat "$f")
    # Labels should be sorted union: api, backend, frontend, ui
    assert_contains "T10: labels has api" "api" "$content"
    assert_contains "T10: labels has frontend" "frontend" "$content"
    assert_contains "T10: labels has ui" "ui" "$content"
    # Depends should be sorted union: 1, 3, 5, 7
    assert_contains "T10: depends has 5" "5" "$content"
    assert_contains "T10: depends has 7" "7" "$content"

    cleanup_tmpdir
}

# --- Run all tests ---

echo "=== aitask_merge.py tests ==="
echo ""

test_full_auto_resolve
test_partial_resolve_status
test_status_implementing_wins
test_body_conflict
test_no_conflict_markers
test_no_frontmatter
test_diff3_markers
test_field_one_side_only
test_key_order_preservation
test_labels_depends_dedup_sort

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
