#!/usr/bin/env bash
# test_gate_no_double_record.sh - Regression for the risk_evaluated self-record
# structural fix (t635_13 req #3 / t635_14).
#
# The hazard: task-workflow Step 7 self-records `risk_evaluated`. For a task that
# DECLARES the gate, the Step-9 orchestrator owns recording — it runs the real
# `aitask-gate-risk` verifier. If Step 7 self-records first, the gate is already
# `pass`, so the orchestrator reports "All gates satisfied" and SKIPS the verifier
# entirely — the self-record masks the authoritative check (and would, in other
# orderings, duplicate it). The fix gates the Step-7 self-record on
# `aitask_gate.sh should-self-record` (exit 1 = declared = skip), so the
# orchestrator's verifier is the sole, authoritative recorder for declared tasks.
#
# The verifier's terminal record carries `verifier=aitask-gate-risk`; a workflow
# self-record (plain `aitask_gate.sh append`) does not — so the two are
# distinguishable in the ledger. This test exercises BOTH halves (the Step-7
# decision AND the Step-9 orchestrator) with a NEGATIVE CONTROL proving the guard
# is load-bearing:
#   A. declaring task, guard honoured  -> ONE terminal pass, FROM the verifier
#   B. declaring task, guard BYPASSED  -> verifier MASKED (no verifier record)
#   C. non-declaring task, guard records, orchestrator no-ops -> exactly ONE
#
# Run: bash tests/test_gate_no_double_record.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
ORCH="$PROJECT_DIR/.aitask-scripts/lib/gate_orchestrator.py"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || echo python3)"

# --- fixture helpers (mirror test_gate_risk_verifier.sh) -------------------

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gatedbl_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata" "$tmp/aiplans"
    cat > "$tmp/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  risk_evaluated:
    type: machine
    verifier: aitask-gate-risk
    max_retries: 0
EOF
    echo "$tmp"
}

task_file_path() {
    local dir="$1" id="$2"
    echo "$dir/aitasks/t${id}_x.md"
}

# write_task <dir> <id> <gates-csv|""> <ch-level> <goal-level>
write_task() {
    local dir="$1" id="$2" gates="$3" ch="$4" goal="$5"
    local path; path="$(task_file_path "$dir" "$id")"
    {
        echo "---"
        echo "status: Implementing"
        [[ -n "$gates" ]] && echo "gates: [${gates}]"
        echo "risk_code_health: ${ch}"
        echo "risk_goal_achievement: ${goal}"
        echo "---"
        echo "Body."
    } > "$path"
}

# write_plan <dir> <id> : a full ## Risk plan (both subsections)
write_plan() {
    local dir="$1" id="$2"
    cat > "$dir/aiplans/p${id}_x.md" <<'EOF'
# Plan

## Risk

### Code-health risk: low
- None identified.

### Goal-achievement risk: low
- None identified.
EOF
}

# in fixture cwd with TASK/PLAN dirs set
gate_in() { local dir="$1"; shift; ( cd "$dir" && TASK_DIR="$dir/aitasks" PLAN_DIR="$dir/aiplans" "$GATE" "$@" ); }

orch() {  # <dir> <id>
    local dir="$1" id="$2"
    ( cd "$dir" && TASK_DIR="$dir/aitasks" PLAN_DIR="$dir/aiplans" "$PY" "$ORCH" run \
        "$(task_file_path "$dir" "$id")" --task-id "$id" \
        --registry "$dir/aitasks/metadata/gates.yaml" 2>&1 )
}

# count terminal (pass) risk_evaluated markers in the task ledger
count_risk_pass() {
    local n; n="$(grep -c 'gate:risk_evaluated.*status=pass' "$1" 2>/dev/null)"
    echo "${n:-0}"
}

# count AUTHORITATIVE verifier-origin risk_evaluated passes. The aitask-gate-risk
# verifier's terminal pass carries a unique `> Result: risk evaluated ...` body
# line; a plain workflow self-record (`aitask_gate.sh append`) has no Result line.
count_verifier_records() {
    local n; n="$(grep -c 'Result: risk evaluated' "$1" 2>/dev/null)"
    echo "${n:-0}"
}

# --- A: declaring task, guard honoured -> ONE pass FROM the verifier --------

test_declaring_single_record() {
    echo "=== A: declaring task, Step-7 guard honoured -> verifier records once ==="
    local d; d="$(new_fixture)"
    write_task "$d" 10 "risk_evaluated" low low
    write_plan "$d" 10
    local tf; tf="$(task_file_path "$d" 10)"

    # Step-7 decision: declared -> should-self-record exits 1 (skip self-record).
    gate_in "$d" should-self-record 10 risk_evaluated; local rc=$?
    assert_eq "A: should-self-record exits 1 (declared -> skip)" "1" "$rc"
    # Guard honoured => no Step-7 append. Only the orchestrator records.
    orch "$d" 10 >/dev/null
    assert_eq "A: exactly one terminal risk_evaluated pass" \
        "1" "$(count_risk_pass "$tf")"
    assert_eq "A: the record is authoritative (from the verifier)" \
        "1" "$(count_verifier_records "$tf")"
}

# --- B: NEGATIVE CONTROL — guard bypassed masks the verifier ---------------

test_negative_control_masks_verifier() {
    echo "=== B: negative control — Step-7 self-records -> orchestrator verifier MASKED ==="
    local d; d="$(new_fixture)"
    write_task "$d" 11 "risk_evaluated" low low
    write_plan "$d" 11
    local tf; tf="$(task_file_path "$d" 11)"

    # Simulate the BUG: Step-7 self-records without consulting should-self-record.
    gate_in "$d" append 11 risk_evaluated pass run=step7 attempt=1 type=machine >/dev/null
    local out; out="$(orch "$d" 11)"
    # Pre-satisfied -> orchestrator skips the real verifier entirely.
    assert_contains "B: orchestrator sees the gate pre-satisfied" \
        "All gates satisfied" "$out"
    assert_eq "B: the real verifier never ran (no authoritative record) — guard is load-bearing" \
        "0" "$(count_verifier_records "$tf")"
}

# --- C: non-declaring task — guard records, orchestrator no-op -> ONE -------

test_non_declaring_single_record() {
    echo "=== C: non-declaring task, Step-7 records, orchestrator no-op -> one ==="
    local d; d="$(new_fixture)"
    write_task "$d" 12 "" low low      # no gates: field
    write_plan "$d" 12
    local tf; tf="$(task_file_path "$d" 12)"

    # Step-7 decision: not declared -> should-self-record exits 0 (record).
    gate_in "$d" should-self-record 12 risk_evaluated; local rc=$?
    assert_eq "C: should-self-record exits 0 (not declared -> record)" "0" "$rc"
    # Workflow self-records once.
    gate_in "$d" append 12 risk_evaluated pass run=step7 attempt=1 type=machine >/dev/null
    # Orchestrator sees no declared gates and records nothing.
    local out; out="$(orch "$d" 12)"
    assert_contains "C: orchestrator reports no declared gates" \
        "No gates declared" "$out"
    assert_eq "C: exactly one terminal risk_evaluated (self-record only)" \
        "1" "$(count_risk_pass "$tf")"
}

# --- Run ---
test_declaring_single_record
test_negative_control_masks_verifier
test_non_declaring_single_record

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
