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
echo "--- append: only TERMINAL runs consume an attempt (t1262) ---"
# ============================================================
# A completed attempt leaves TWO markers — the `running` block and the terminal
# block that closes it — so counting every marker advanced the counter by 2 per
# attempt. Only pass/fail/skip/error consume a number; running/pending do not.
make_task 12
"$GATE" append 12 lint running run=r1 attempt=1 type=machine >/dev/null
# SAME run id, `attempt=` omitted: proves the terminal block CLOSES the live run
# and inherits its number, not merely that markers are counted.
out=$("$GATE" append 12 lint pass run=r1)
assert_contains "terminal closing run r1 keeps its run id" "run=r1" "$out"
assert_contains "terminal closing run r1 reuses attempt 1" "attempt=1" "$out"

out=$("$GATE" append 12 lint fail run=r2)
assert_contains "next attempt after one terminal run = 2" "attempt=2" "$out"

"$GATE" append 12 lint pending run=r3 type=human >/dev/null
out=$("$GATE" append 12 lint skip run=r4)
assert_contains "pending consumed nothing; skip is numbered too" "attempt=3" "$out"

out=$("$GATE" append 12 lint error run=r5)
assert_contains "error is a terminal status and is numbered" "attempt=4" "$out"

# ============================================================
echo "--- append: malformed-verifier correction is its own run (t1262) ---"
# ============================================================
# gate_orchestrator.reconcile_terminal() appends a FRESH-run-id `error` when a
# verifier self-reports a status contradicting its exit code, reusing the same
# explicit attempt. One dispatch therefore leaves two terminal markers, and both
# count — matching what the retry budget (_attempts_used, which counts fail AND
# error) already charges for that dispatch.
make_task 13
"$GATE" append 13 tests_pass running run=c1 attempt=1 type=machine >/dev/null
"$GATE" append 13 tests_pass fail run=c1 attempt=1 type=machine >/dev/null
"$GATE" append 13 tests_pass error run=c2 attempt=1 type=machine \
    note="malformed: verifier reported fail but exit code mapped to error" >/dev/null
out=$("$GATE" append 13 tests_pass fail run=c3)
assert_contains "correction counts as its own terminal run -> next attempt 3" \
    "attempt=3" "$out"
if [[ -n "$PY" ]]; then
    # ... and the retry budget agrees, so the ordinal and the budget stay in
    # lockstep on this path rather than being assumed equal.
    used=$("$PY" -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
import gate_ledger as gl, gate_orchestrator as go
runs = [r for r in gl.parse_gate_run_blocks(open('$TASK_DIR/t13_demo.md', encoding='utf-8').read())
        if r.name == 'tests_pass' and r.run_id != 'c3']
print(go._attempts_used(runs) + 1)
")
    assert_eq "ordinal agrees with _attempts_used+1 on the correction path" "3" "$used"
fi

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

    # AUTO-attempt parity (t1262): the drift guard between bash's TERMINAL_STATUSES
    # scan and gate_ledger.next_attempt(). `AIT_GATES_BACKEND=python` delegates the
    # whole append before the bash auto path, so this genuinely exercises
    # build_block's computation, not just its formatting. Run ids are pinned, so
    # the comparison carries no wall-clock dependency.
    make_task 24            # bash target
    make_task 25            # python target
    for spec in "running r1 attempt=1" "pass r1 -" "fail r2 -" "skip r3 -" "error r4 -"; do
        set -- $spec
        st="$1"; rid="$2"; extra="$3"
        [[ "$extra" == "-" ]] && extra=""
        # shellcheck disable=SC2086
        "$GATE" append 24 tests_pass "$st" run="$rid" $extra type=machine >/dev/null
        # shellcheck disable=SC2086
        AIT_GATES_BACKEND=python "$GATE" append 25 tests_pass "$st" run="$rid" $extra type=machine >/dev/null
    done
    auto_bash=$(sed -n '/## Gate Runs/,$p' "$TASK_DIR/t24_demo.md")
    auto_py=$(sed -n '/## Gate Runs/,$p' "$TASK_DIR/t25_demo.md")
    assert_eq "auto-attempt parity across terminal statuses (bash vs python)" \
        "$auto_bash" "$auto_py"
    assert_contains "auto-attempt: bash closer reuses the running block's 1" \
        "status=pass attempt=1" "$auto_bash"
    assert_contains "auto-attempt: python closer reuses the running block's 1" \
        "status=pass attempt=1" "$auto_py"
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
