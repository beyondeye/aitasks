#!/usr/bin/env bash
# test_create_manual_verification.sh - Regression tests for
# aitask_create_manual_verification.sh (t619).
#
# The wrapper used to pre-stage a `## Verification Checklist` header in the
# task description before invoking `aitask_verification_parse.sh seed`, which
# refuses to run when a section already exists. That produced a half-baked
# task file (empty checklist, already committed) and a non-zero exit from the
# wrapper. This test covers:
#
#   1. Happy path (--related): wrapper exits 0, emits MANUAL_VERIFICATION_CREATED
#      on stdout, and the created task contains exactly one checklist section
#      followed by one `- [ ]` line per input bullet.
#   2. Empty items file: wrapper exits non-zero and does not silently claim
#      success.
#
# Run: bash tests/test_create_manual_verification.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected: $expected"
        echo "  actual:   $actual"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (missing '$expected')"
        echo "  actual: $actual"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (unexpected '$unexpected' found)"
        echo "  actual: $actual"
    else
        PASS=$((PASS + 1))
    fi
}

# setup_project creates a bare-remote + local-clone pair, copies the minimal
# script set needed by aitask_create_manual_verification.sh (and its transitive
# deps), initializes the atomic id counter, and leaves CWD inside the local
# clone via pushd.
setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/metadata aiplans/archived .aitask-scripts/lib

    cp "$PROJECT_DIR/.aitask-scripts/aitask_create_manual_verification.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    # Stub out `./ait git` so the wrapper's post-seed commit succeeds inside
    # the fixture. The wrapper already redirects stdout/stderr to /dev/null,
    # so a pass-through to plain git is enough.
    cat > ./ait <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "git" ]]; then
    shift
    exec git "$@"
fi
exit 0
EOF
    chmod +x ./ait

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    ./.aitask-scripts/aitask_claim_id.sh --init > /dev/null 2>&1
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# Locate the task filepath emitted on the MANUAL_VERIFICATION_CREATED line.
created_path_from_output() {
    echo "$1" | sed -n 's/^MANUAL_VERIFICATION_CREATED:[^:]*:\(.*\)$/\1/p' | tail -1
}

test_happy_path_related_mode() {
    echo "=== Test: happy path — --related mode seeds checklist cleanly ==="
    setup_project

    local items
    items="$(mktemp)"
    printf 'Button opens the modal cleanly\nClose restores focus\n' > "$items"

    local out rc
    out=$(bash .aitask-scripts/aitask_create_manual_verification.sh \
            --name mv_from_t42 \
            --verifies 42 \
            --related 42 \
            --items "$items" 2>&1) && rc=0 || rc=$?
    rm -f "$items"

    assert_eq "wrapper exits 0" "0" "$rc"
    assert_contains "MANUAL_VERIFICATION_CREATED emitted" "MANUAL_VERIFICATION_CREATED:" "$out"
    assert_not_contains "no ERROR prefix on happy path" "ERROR:" "$out"

    local new_path
    new_path=$(created_path_from_output "$out")
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: task path not resolvable or file missing"
        echo "  out: $out"
        teardown
        return
    fi

    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))

    local body
    body=$(cat "$new_path")

    # Exactly one `## Verification Checklist` heading — the original bug
    # would leave an empty one behind OR (pre-fix) would fail before the
    # seed ever appended items. Either way, anything != 1 is a regression.
    local heading_count
    heading_count=$(grep -c '^## Verification Checklist' "$new_path" | tr -d ' ')
    assert_eq "exactly one checklist heading" "1" "$heading_count"

    assert_contains "first item present" "- [ ] Button opens the modal cleanly" "$body"
    assert_contains "second item present" "- [ ] Close restores focus" "$body"
    assert_contains "frontmatter type is manual_verification" "issue_type: manual_verification" "$body"
    assert_contains "frontmatter records dep on related" "depends: [42]" "$body"

    teardown
}

test_empty_items_file_errors_cleanly() {
    echo "=== Test: empty items file produces a non-zero exit ==="
    setup_project

    local items
    items="$(mktemp)"
    # Only blank lines — cmd_seed treats this as empty.
    printf '\n   \n\n' > "$items"

    local out rc
    out=$(bash .aitask-scripts/aitask_create_manual_verification.sh \
            --name mv_empty \
            --verifies 42 \
            --related 42 \
            --items "$items" 2>&1) && rc=0 || rc=$?
    rm -f "$items"

    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: wrapper should exit non-zero on empty items file"
        echo "  out: $out"
    fi
    assert_contains "error prefix emitted" "ERROR:" "$out"

    teardown
}

test_syntax_check() {
    echo "=== Test: syntax check touched script ==="
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_create_manual_verification.sh"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: syntax check"
    fi
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_happy_path_related_mode
test_empty_items_file_errors_cleanly
test_syntax_check

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
