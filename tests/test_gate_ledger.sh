#!/usr/bin/env bash
# test_gate_ledger.sh - Tests for the gate ledger substrate (t635_1).
#
# Covers aitask_gate.sh (bash+awk primary path) and lib/gate_ledger.py
# (stdlib fallback): marker-first append, back-to-front state derivation,
# attempt auto-increment, section creation, `list` registry enrichment,
# error handling, and bash<->python parity. Also a BSD-awk portability guard
# (no gawk-only 3-arg match()).
#
# Run: bash tests/test_gate_ledger.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

# Resolve a python interpreter for the fallback-parity tests (may be empty).
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_gate_ledger_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

export TASK_DIR="$TMP/aitasks"
mkdir -p "$TASK_DIR/metadata"

# Minimal registry fixture.
cat > "$TASK_DIR/metadata/gates.yaml" <<'EOF'
gates:
  tests_pass:
    type: machine
    description: "Run project test suite; must all pass"
  review:
    type: human
    description: "Human code review sign-off"
EOF

make_task() {
    local id="$1"
    cat > "$TASK_DIR/t${id}_demo.md" <<EOF
---
priority: high
status: Implementing
gates: [tests_pass, review]
---

## Context
Body for t${id}.
EOF
}

# ============================================================
echo "--- append: section creation + marker format ---"
# ============================================================
make_task 10
out=$("$GATE" append 10 tests_pass fail run=2026-01-01T00:00:00Z verifier=aitask-gate-tests result="3 failed")
file="$TASK_DIR/t10_demo.md"

assert_contains "section header created" "## Gate Runs" "$(cat "$file")"
assert_contains "do-not-edit comment created" "Do not edit by hand" "$(cat "$file")"
assert_contains "marker icon + gate name" "> **❌ gate:tests_pass**" "$(cat "$file")"
assert_contains "marker has run=" "run=2026-01-01T00:00:00Z" "$out"
assert_contains "marker has status=" "status=fail" "$out"
assert_contains "attempt auto = 1" "attempt=1" "$out"
assert_contains "body verifier backticked" "> Verifier: \`aitask-gate-tests\`" "$out"
assert_contains "body result plain" "> Result: 3 failed" "$out"

# ============================================================
echo "--- append: attempt auto-increment + derivation (last wins) ---"
# ============================================================
out=$("$GATE" append 10 tests_pass pass run=2026-01-01T01:00:00Z)
assert_contains "attempt auto = 2" "attempt=2" "$out"

status_out=$("$GATE" status 10)
assert_contains "derive last-wins -> pass" "tests_pass: pass (attempt 2, run 2026-01-01T01:00:00Z)" "$status_out"

# ============================================================
echo "--- append: pending human gate (no attempt) + multi-gate status ---"
# ============================================================
out=$("$GATE" append 10 review pending type=human run=2026-01-01T02:00:00Z note="awaiting sign-off")
assert_contains "pending icon" "> **⏸ gate:review**" "$out"
assert_contains "pending has type=human" "type=human" "$out"
assert_not_contains "pending has no attempt" "attempt=" "$out"

status_out=$("$GATE" status 10)
assert_contains "multi-gate: tests_pass present" "tests_pass: pass" "$status_out"
assert_contains "multi-gate: review pending" "review: pending (run 2026-01-01T02:00:00Z)" "$status_out"

# ============================================================
echo "--- list: declared gates + registry enrichment ---"
# ============================================================
list_out=$("$GATE" list 10)
assert_contains "list shows tests_pass + type + desc" "tests_pass [machine] - Run project test suite; must all pass" "$list_out"
assert_contains "list shows review human" "review [human] - Human code review sign-off" "$list_out"

# No-gates task
cat > "$TASK_DIR/t11_nogate.md" <<'EOF'
---
status: Ready
---
body
EOF
assert_eq "list no-gates message" "(no gates declared)" "$("$GATE" list 11)"

# ============================================================
echo "--- errors ---"
# ============================================================
assert_exit_nonzero "unknown subcommand exits non-zero" "$GATE" frobnicate
assert_exit_nonzero "invalid status exits non-zero" "$GATE" append 10 tests_pass bogus
assert_exit_zero "--help exits zero" "$GATE" --help

# ============================================================
echo "--- bash <-> python parity ---"
# ============================================================
if [[ -n "$PY" ]]; then
    # status parity on the populated t10
    bash_status=$("$GATE" status 10)
    py_status=$(AIT_GATES_BACKEND=python "$GATE" status 10)
    assert_eq "status parity (bash vs python)" "$bash_status" "$py_status"

    # list parity
    bash_list=$("$GATE" list 10)
    py_list=$(AIT_GATES_BACKEND=python "$GATE" list 10)
    assert_eq "list parity (bash vs python)" "$bash_list" "$py_list"

    # append-block parity: identical explicit fields -> identical Gate Runs block
    make_task 20            # bash target
    make_task 21            # python target
    "$GATE" append 20 tests_pass pass run=2026-02-02T00:00:00Z attempt=1 verifier=v result=ok log=.aitask-gates/t20/x.log >/dev/null
    AIT_GATES_BACKEND=python "$GATE" append 21 tests_pass pass run=2026-02-02T00:00:00Z attempt=1 verifier=v result=ok log=.aitask-gates/t20/x.log >/dev/null
    block_bash=$(sed -n '/## Gate Runs/,$p' "$TASK_DIR/t20_demo.md")
    block_py=$(sed -n '/## Gate Runs/,$p' "$TASK_DIR/t21_demo.md")
    assert_eq "append-block parity (bash vs python)" "$block_bash" "$block_py"
else
    echo "SKIP: no python interpreter resolved — skipping bash<->python parity"
fi

# ============================================================
echo "--- macOS portability + syntax guards ---"
# ============================================================
# gawk-only 3-arg match(str, re, arr) is a hard syntax error under BSD awk.
TOTAL=$((TOTAL + 1))
if grep -qE 'match\([^,]+,[^,]+,[^)]+\)' "$GATE"; then
    FAIL=$((FAIL + 1)); echo "FAIL: 3-arg match() found in aitask_gate.sh (gawk-only)"
else
    PASS=$((PASS + 1))
fi

TOTAL=$((TOTAL + 1))
if bash -n "$GATE"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: bash -n aitask_gate.sh"; fi

if [[ -n "$PY" ]]; then
    TOTAL=$((TOTAL + 1))
    if "$PY" -c "import ast,sys; ast.parse(open('$PROJECT_DIR/.aitask-scripts/lib/gate_ledger.py').read())"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: python parse gate_ledger.py"
    fi
fi

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
