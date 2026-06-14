#!/usr/bin/env bash
# test_gate_guarded_archival.sh - Tests for gate-guarded archival (t635_4).
#
# Two layers:
#   Unit  — the archive-ready decision (gate_ledger.archive_status, surfaced as
#           `aitask_gate.sh archive-ready` and `gate_ledger.py archive-ready`):
#             no declared gates           -> NO_GATES
#             declared gate, no/pending   -> BLOCKED:<csv>
#             every declared gate passed  -> ALL_PASS
#             mixed (one pass, one pending) -> BLOCKED:<pending>
#   Integ — aitask_archive.sh gate_guard():
#             pending declared gate       -> exit 2, GATE_PENDING, NOT archived
#             after the gate passes        -> archives normally
#             --ignore-gates               -> archives despite pending gate
#             ungated task (dormancy)      -> archives exactly as today
#             child-task path              -> blocked / allowed
#
# Run: bash tests/test_gate_guarded_archival.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
GATE_PY="$PROJECT_DIR/.aitask-scripts/lib/gate_ledger.py"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"

# ============================================================
# Unit layer: archive-ready decision
# ============================================================

unit_setup() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gga_unit_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    export TASK_DIR="$tmp/aitasks"
    mkdir -p "$TASK_DIR/metadata"
}

# Write a task file with an optional `gates:` line. $2 (if given) is the inline
# gates value, e.g. "[review_approved, docs_updated]".
make_unit_task() {
    local id="$1" gates="${2:-}"
    {
        echo "---"
        echo "priority: high"
        echo "status: Implementing"
        [[ -n "$gates" ]] && echo "gates: $gates"
        echo "---"
        echo
        echo "Body for t${id}."
    } > "$TASK_DIR/t${id}_demo.md"
}

test_unit_archive_ready() {
    echo "=== Unit: archive-ready decision ==="
    unit_setup

    # No declared gates -> NO_GATES.
    make_unit_task 200
    assert_eq_trim "no gates -> NO_GATES" "NO_GATES" "$("$GATE" archive-ready 200)"

    # Declared gate, no recorded run -> BLOCKED.
    make_unit_task 201 "[review_approved]"
    assert_eq_trim "declared, no run -> BLOCKED" "BLOCKED:review_approved" "$("$GATE" archive-ready 201)"

    # Record the pass -> ALL_PASS.
    "$GATE" append 201 review_approved pass >/dev/null
    assert_eq_trim "declared, passed -> ALL_PASS" "ALL_PASS" "$("$GATE" archive-ready 201)"

    # Two gates, only one passed -> BLOCKED on the pending one.
    make_unit_task 202 "[review_approved, docs_updated]"
    "$GATE" append 202 review_approved pass >/dev/null
    assert_eq_trim "mixed -> BLOCKED on pending" "BLOCKED:docs_updated" "$("$GATE" archive-ready 202)"

    # A later fail run wins over an earlier pass (last-run-wins) -> BLOCKED.
    "$GATE" append 201 review_approved fail >/dev/null
    assert_eq_trim "last-run fail -> BLOCKED" "BLOCKED:review_approved" "$("$GATE" archive-ready 201)"

    # Direct python parity on the same fixtures.
    if [[ -n "$PY" ]]; then
        assert_eq_trim "py: no gates -> NO_GATES" "NO_GATES" "$("$PY" "$GATE_PY" archive-ready "$TASK_DIR/t200_demo.md")"
        assert_eq_trim "py: mixed -> BLOCKED" "BLOCKED:docs_updated" "$("$PY" "$GATE_PY" archive-ready "$TASK_DIR/t202_demo.md")"
    else
        echo "(skipping python-parity asserts: no interpreter resolved)"
    fi
}

# ============================================================
# Integration layer: aitask_archive.sh gate_guard
# ============================================================

setup_archive_project() {
    # The unit layer exports TASK_DIR; the archive flow must use the repo's
    # relative `aitasks` default (as in production), so clear the leak.
    unset TASK_DIR
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

    mkdir -p aitasks/archived aitasks/metadata aiplans/archived
    setup_fake_aitask_repo "$PWD"

    # Archive + gate tools and their leaf libs.
    cp "$PROJECT_DIR/.aitask-scripts/aitask_archive.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_gate.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/gate_ledger.py" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true

    chmod +x .aitask-scripts/*.sh .aitask-scripts/*.py 2>/dev/null || true

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true
}

teardown() { popd > /dev/null 2>&1 || true; }

# Write a feature task with an optional inline `gates:` value.
write_gated_task() {
    local path="$1" gates="${2:-}"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: feature"
        echo "status: Implementing"
        echo "labels: []"
        [[ -n "$gates" ]] && echo "gates: $gates"
        echo "created_at: 2026-06-14 10:00"
        echo "updated_at: 2026-06-14 10:00"
        echo "---"
        echo
        echo "Body."
    } > "$path"
}

test_pending_gate_blocks_archival() {
    echo ""
    echo "=== Integ 1: pending declared gate blocks archival ==="
    setup_archive_project

    write_gated_task aitasks/t300_gated.md "[review_approved]"
    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 300 2>&1)
    rc=$?
    set -e

    assert_eq_trim "Exits 2 when gate pending" "2" "$rc"
    assert_contains "GATE_PENDING emitted" "GATE_PENDING:review_approved" "$output"
    assert_contains "GATE_BLOCKED marker emitted" "GATE_BLOCKED" "$output"
    assert_not_contains "No COMMITTED on blocked gate" "COMMITTED:" "$output"
    assert_not_contains "No ARCHIVED_TASK on blocked gate" "ARCHIVED_TASK:" "$output"
    assert_file_exists "Task still in aitasks/" "aitasks/t300_gated.md"

    teardown
}

test_passed_gate_archives() {
    echo ""
    echo "=== Integ 2: archives once the gate passes ==="
    setup_archive_project

    write_gated_task aitasks/t301_gated.md "[review_approved]"
    git add -A && git commit -m "setup" --quiet
    # Record the gate as pass (the in-session 'resolve now & archive' path).
    bash .aitask-scripts/aitask_gate.sh append 301 review_approved pass >/dev/null
    git add -A && git commit -m "gate pass" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 301 2>&1)
    rc=$?
    set -e

    assert_eq_trim "Exits 0 once gate passes" "0" "$rc"
    assert_not_contains "No GATE_PENDING on success" "GATE_PENDING:" "$output"
    assert_contains "ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"
    assert_file_not_exists "Task moved out of aitasks/" "aitasks/t301_gated.md"

    teardown
}

test_ignore_gates_bypasses() {
    echo ""
    echo "=== Integ 3: --ignore-gates archives despite a pending gate ==="
    setup_archive_project

    write_gated_task aitasks/t302_gated.md "[review_approved]"
    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh --ignore-gates 302 2>&1)
    rc=$?
    set -e

    assert_eq_trim "Exits 0 with --ignore-gates" "0" "$rc"
    assert_not_contains "No GATE_PENDING with --ignore-gates" "GATE_PENDING:" "$output"
    assert_contains "ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"
    assert_file_not_exists "Task archived" "aitasks/t302_gated.md"

    teardown
}

test_ungated_archives_normally() {
    echo ""
    echo "=== Integ 4: ungated task archives exactly as today (dormancy) ==="
    setup_archive_project

    write_gated_task aitasks/t303_plain.md ""   # no gates: field
    git add -A && git commit -m "setup" --quiet

    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 303 2>&1)
    rc=$?
    set -e

    assert_eq_trim "Exits 0 for ungated task" "0" "$rc"
    assert_not_contains "No GATE_PENDING for ungated task" "GATE_PENDING:" "$output"
    assert_contains "ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"
    assert_file_not_exists "Task archived" "aitasks/t303_plain.md"

    teardown
}

test_child_task_gate() {
    echo ""
    echo "=== Integ 5: gate fires on the child-archive path ==="
    setup_archive_project

    cat > aitasks/t304_parent.md <<'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: []
children_to_implement: [t304_1]
created_at: 2026-06-14 10:00
updated_at: 2026-06-14 10:00
---

Parent.
TASK
    mkdir -p aitasks/t304
    write_gated_task aitasks/t304/t304_1_child.md "[review_approved]"
    git add -A && git commit -m "setup" --quiet

    # Blocked while pending.
    local output rc
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 304_1 2>&1)
    rc=$?
    set -e
    assert_eq_trim "Child gate exits 2 when pending" "2" "$rc"
    assert_contains "Child gate emits GATE_PENDING" "GATE_PENDING:review_approved" "$output"
    assert_file_exists "Child still in aitasks/" "aitasks/t304/t304_1_child.md"

    # Passes once the gate is recorded.
    bash .aitask-scripts/aitask_gate.sh append 304_1 review_approved pass >/dev/null
    git add -A && git commit -m "child gate pass" --quiet
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh 304_1 2>&1)
    rc=$?
    set -e
    assert_eq_trim "Child archives once gate passes" "0" "$rc"
    assert_contains "Child ARCHIVED_TASK emitted" "ARCHIVED_TASK:" "$output"
    assert_file_not_exists "Child moved out of aitasks/" "aitasks/t304/t304_1_child.md"

    teardown
}

# --- Run ---
test_unit_archive_ready
test_pending_gate_blocks_archival
test_passed_gate_archives
test_ignore_gates_bypasses
test_ungated_archives_normally
test_child_task_gate

# Cleanup
for dir in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dir"
done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
else
    echo "All tests PASSED"
fi
