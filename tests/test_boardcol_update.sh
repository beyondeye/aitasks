#!/usr/bin/env bash
# test_boardcol_update.sh - Validation of `ait update --boardcol` (t1377_1).
#
# Before this validation existed, an unconfigured column id was written verbatim
# and produced a task that rendered in NO column at all — not even `unordered` —
# and that the work-report gatherer could not name either. The flag is on the
# documented cross-repo list, so the failure was silent and portable.
#
# Covers:
#   --boardcol c1          -> accepted and written
#   --boardcol unordered   -> accepted (the synthetic column IS a legal target)
#   --boardcol nope        -> non-zero, file UNCHANGED, message names valid ids
#   --boardcol ""          -> clears the field, skipping validation
#
# The clearing case is the one most easily broken by a naive guard: `--anchor ""`
# is the precedent this mirrors, and a `-n "$VALUE"` test is what preserves it.
#
# Every invocation below CAPTURES the command's output instead of discarding it,
# and asserts the exit code through assert_exit_zero_rc_out so the captured text
# lands in the FAIL line. That is deliberate (t1488): this file previously ran
# `>/dev/null 2>&1` under `set -e`, so a scaffold missing a Python module aborted
# it at the first call with no FAIL line, no summary and no error text — it read
# as a hang, not an assertion failure. test_scaffold_column_probe_works is the
# guard for that class; setup_project derives the Python module closure rather
# than listing it.
#
# Run: bash tests/test_boardcol_update.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

assert_nonzero() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got $rc)"
    fi
}

assert_no_field() {
    local desc="$1" file="$2" field="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qE "^${field}:" "$file"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('${field}:' unexpectedly present in $file)"
    else
        PASS=$((PASS + 1))
    fi
}

setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local local_dir="$tmpdir/local"
    mkdir -p "$local_dir"
    pushd "$local_dir" > /dev/null
    git init --quiet .
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_board_column.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    # task_utils.sh sources these at load time; without them it aborts before
    # any flag is parsed. Same set test_anchor_update.sh copies.
    for opt in archive_utils archive_scan agentcrew_utils; do
        cp "$PROJECT_DIR/.aitask-scripts/lib/$opt.sh" .aitask-scripts/lib/ 2>/dev/null || true
    done
    # board_columns is the only Python entry point the scaffolded scripts drive
    # (aitask_board_column.sh execs it); its transitive lib/ deps are DERIVED
    # rather than listed. The list this replaced had silently drifted: it
    # omitted record_protocol.py, so every --boardcol validation failed inside
    # the scaffold (t1488).
    copy_lib_py_closure "$PWD" board_columns
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\nfeature\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt
    cat > aitasks/metadata/board_config.json <<'JSON'
{
  "columns": [
    {"id": "c0", "title": "Col Zero", "color": "#FF5555"},
    {"id": "c1", "title": "Col One", "color": "#50FA7B"}
  ],
  "column_order": ["c0", "c1"]
}
JSON

    git add -A
    git commit -m "Initial setup" --quiet
}

teardown() {
    popd > /dev/null 2>&1 || true
}

seed_task() {
    local path="$1"; shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "issue_type: chore"
        printf '%s\n' "status: Ready"
        for extra in "$@"; do printf '%s\n' "$extra"; done
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\nBody\n'
    } > "$path"
}

# Runs the exact seam normalize_board_column() probes, with stderr CAPTURED
# rather than discarded. It is the guard against the whole silent-death class
# this file used to exhibit: a scaffold missing a Python module made every
# --boardcol call exit 1, `set -e` aborted the file at the first one, and the
# run printed no FAIL line, no summary and no error text. Here the same
# breakage surfaces as `ModuleNotFoundError: No module named '…'` inside a
# named FAIL. Independent ground truth — it drives the real entry point instead
# of re-deriving the same import list setup_project() derives.
test_scaffold_column_probe_works() {
    echo "=== Test: the scaffold's board-column probe is healthy ==="
    setup_project

    local out rc=0
    out="$(./.aitask-scripts/aitask_board_column.sh list-columns \
             --root . --task-dir aitasks --include-unordered 2>&1)" || rc=$?
    assert_exit_zero_rc_out "scaffold column probe exits zero" "$rc" "$out"
    assert_contains "probe lists the configured columns" "COLUMN:c1|" "$out"

    teardown
}

test_accepts_configured_column() {
    echo "=== Test: --boardcol accepts a configured id ==="
    setup_project
    seed_task "aitasks/t1_alpha.md" "boardcol: c0" "boardidx: 10"

    local out rc=0
    out="$(./.aitask-scripts/aitask_update.sh --batch 1 --boardcol c1 2>&1)" || rc=$?
    assert_exit_zero_rc_out "configured id accepted" "$rc" "$out"
    assert_contains "configured id written" "boardcol: c1" \
        "$(cat aitasks/t1_alpha.md)"

    teardown
}

test_accepts_unordered() {
    echo "=== Test: --boardcol accepts the synthetic 'unordered' ==="
    setup_project
    seed_task "aitasks/t1_alpha.md" "boardcol: c0" "boardidx: 10"

    local out rc=0
    out="$(./.aitask-scripts/aitask_update.sh --batch 1 --boardcol unordered 2>&1)" || rc=$?
    assert_exit_zero_rc_out "unordered accepted (exit)" "$rc" "$out"
    assert_contains "unordered accepted" "boardcol: unordered" \
        "$(cat aitasks/t1_alpha.md)"

    teardown
}

test_rejects_unknown_column() {
    echo "=== Test: --boardcol rejects an unconfigured id ==="
    setup_project
    seed_task "aitasks/t1_alpha.md" "boardcol: c0" "boardidx: 10"
    local before
    before="$(cat aitasks/t1_alpha.md)"

    local out rc=0
    out="$(./.aitask-scripts/aitask_update.sh --batch 1 --boardcol nope 2>&1)" || rc=$?
    assert_nonzero "unknown column exits non-zero" "$rc"
    assert_contains "message names the offending id" "nope" "$out"
    assert_contains "message names the valid ids" "c0" "$out"
    assert_contains "message offers unordered too" "unordered" "$out"
    assert_eq "task file unchanged" "$before" "$(cat aitasks/t1_alpha.md)"

    teardown
}

test_empty_value_clears_without_validating() {
    echo "=== Test: --boardcol '' clears the field ==="
    setup_project
    seed_task "aitasks/t1_alpha.md" "boardcol: c0" "boardidx: 10"

    local out rc=0
    out="$(./.aitask-scripts/aitask_update.sh --batch 1 --boardcol "" 2>&1)" || rc=$?
    assert_exit_zero_rc_out "clearing succeeds" "$rc" "$out"
    assert_no_field "boardcol cleared" "aitasks/t1_alpha.md" "boardcol"

    teardown
}

test_scaffold_column_probe_works
test_accepts_configured_column
test_accepts_unordered
test_rejects_unknown_column
test_empty_value_clears_without_validating

for d in "${CLEANUP_DIRS[@]}"; do rm -rf "$d"; done

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
