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

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

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

    mkdir -p aitasks/metadata aiplans/archived
    setup_fake_aitask_repo "$PWD"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_create_manual_verification.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    # Required by the best-effort --followup-of probe in --related mode (t1468_2)
    # and by aitask_create.sh's own --followup-of validation.
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
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
    assert_contains "frontmatter records manual_verification provenance" \
        "followup_kind: manual_verification" "$body"

    # FAIL-SAFE BASELINE (t1468_2). No t42 exists in this fixture, so `--related
    # 42` is an UNRESOLVABLE origin. `aitask_create.sh --followup-of` *dies* on
    # an unresolvable id, so the anchor threading added in t1468_2 must be
    # probe-guarded: this creation has to keep succeeding and simply stay a
    # topic root. This assertion passed before that change and must pass
    # unchanged after — it is what proves the probe, not the flag, was added.
    assert_not_contains_re "unresolvable origin leaves the task a topic root" \
        '^anchor:' "$body"

    teardown
}

# The companion to the fail-safe baseline above: when the origin DOES resolve,
# the standalone manual-verification follow-up must actually join its topic.
# Without this the guard could be satisfied by never threading the flag at all.
test_related_mode_anchors_to_resolvable_origin() {
    echo "=== Test: --related mode anchors to a resolvable origin ==="
    setup_project

    # A real origin task, so the anchor probe resolves.
    mkdir -p aitasks
    {
        printf '%s\n' "---" "priority: medium" "effort: low" "depends: []" \
            "issue_type: feature" "status: Ready" "labels: []" \
            "created_at: 2026-01-01 10:00" "updated_at: 2026-01-01 10:00" "---"
        printf '\nOrigin body\n'
    } > aitasks/t77_origin_feature.md
    git add -A; git commit -m "seed origin" --quiet

    local items
    items="$(mktemp)"
    printf 'Origin behaviour still holds\n' > "$items"

    local out rc
    out=$(bash .aitask-scripts/aitask_create_manual_verification.sh \
            --name mv_from_t77 \
            --verifies 77 \
            --related 77 \
            --items "$items" 2>&1) && rc=0 || rc=$?
    rm -f "$items"

    assert_eq "wrapper exits 0 with a resolvable origin" "0" "$rc"

    local new_path body
    new_path=$(created_path_from_output "$out")
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: task path not resolvable or file missing"
        echo "  out: $out"
        teardown
        return
    fi
    body=$(cat "$new_path")

    assert_contains "resolvable origin yields the origin's topic root" "anchor: 77" "$body"
    assert_contains "still records manual_verification provenance" \
        "followup_kind: manual_verification" "$body"
    assert_contains "dep on the origin is unchanged" "depends: [77]" "$body"

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
test_related_mode_anchors_to_resolvable_origin
test_empty_items_file_errors_cleanly
test_syntax_check

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
