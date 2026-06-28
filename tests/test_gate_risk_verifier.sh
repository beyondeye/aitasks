#!/usr/bin/env bash
# test_gate_risk_verifier.sh - Tests for the risk-evaluation machine-gate verifier
# (t635_13): .aitask-scripts/aitask_gate_risk.sh.
#
# The risk gate is STATE-inspection (not command-driven): it PASSES when the task's
# PLAN file has a `## Risk` section with BOTH `### Code-health risk` /
# `### Goal-achievement risk` subsections AND the task frontmatter carries both
# `risk_code_health` / `risk_goal_achievement` levels (high|medium|low). Otherwise
# FAIL (exit 1); an unresolvable task id => error (exit 3). There is NO skip path.
#
# Covers: pass; fail (no section / missing a dimension subsection / missing field /
# no plan file / invalid level); child-task path resolution; sidecar-log content;
# and orchestrator integration with reconciliation hygiene (exactly one terminal
# marker, status matches the exit code, no malformed/error correction).
#
# Run: bash tests/test_gate_risk_verifier.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

RISK="$PROJECT_DIR/.aitask-scripts/aitask_gate_risk.sh"
ORCH="$PROJECT_DIR/.aitask-scripts/lib/gate_orchestrator.py"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || echo python3)"

# --- fixture helpers -------------------------------------------------------

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gaterisk_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata" "$tmp/aiplans"
    echo "$tmp"
}

# task_file_path <dir> <id> ; child ids (<p>_<c>) live under aitasks/t<p>/.
task_file_path() {
    local dir="$1" id="$2"
    if [[ "$id" == *_* ]]; then echo "$dir/aitasks/t${id%%_*}/t${id}_x.md"; else echo "$dir/aitasks/t${id}_x.md"; fi
}

# write_task <dir> <id> <gates-csv> <code-health-level> <goal-level>
# Empty level => omit that frontmatter field; empty gates => no `gates:` line.
write_task() {
    local dir="$1" id="$2" gates="$3" ch="$4" goal="$5" path
    path="$(task_file_path "$dir" "$id")"
    mkdir -p "$(dirname "$path")"
    {
        echo "---"
        echo "status: Implementing"
        [[ -n "$gates" ]] && echo "gates: [${gates}]"
        [[ -n "$ch" ]]    && echo "risk_code_health: ${ch}"
        [[ -n "$goal" ]]  && echo "risk_goal_achievement: ${goal}"
        echo "---"
        echo "Body."
    } > "$path"
}

# write_plan <dir> <id> <variant>  variant: full | no_section | no_goal_sub
write_plan() {
    local dir="$1" id="$2" variant="$3" path
    if [[ "$id" == *_* ]]; then
        mkdir -p "$dir/aiplans/p${id%%_*}"
        path="$dir/aiplans/p${id%%_*}/p${id}_x.md"
    else
        path="$dir/aiplans/p${id}_x.md"
    fi
    case "$variant" in
        full)
            cat > "$path" <<'EOF'
# Plan

## Risk

### Code-health risk: low
- None identified.

### Goal-achievement risk: low
- None identified.
EOF
            ;;
        no_section)
            printf '# Plan\n\nJust a body, no risk section.\n' > "$path"
            ;;
        no_goal_sub)
            cat > "$path" <<'EOF'
# Plan

## Risk

### Code-health risk: low
- None identified.
EOF
            ;;
    esac
}

# run_verifier <dir> <task-id> <attempt> <run-id>; sets RC
run_verifier() {
    local dir="$1"; shift
    ( cd "$dir" && TASK_DIR="$dir/aitasks" PLAN_DIR="$dir/aiplans" "$RISK" "$@" )
    RC=$?
}

orch() {  # <dir> <id> [flags...]
    local dir="$1" id="$2"; shift 2
    ( cd "$dir" && TASK_DIR="$dir/aitasks" PLAN_DIR="$dir/aiplans" "$PY" "$ORCH" run \
        "$(task_file_path "$dir" "$id")" --task-id "$id" \
        --registry "$dir/aitasks/metadata/gates.yaml" "$@" 2>&1 )
}

count_status() {  # <file> <status-token>
    local c; c="$(grep -c "status=$2" "$1" 2>/dev/null)"; echo "${c:-0}"
}

risk_registry() {  # writes a minimal registry declaring risk_evaluated -> the verifier
    cat > "$1/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  risk_evaluated:
    type: machine
    verifier: aitask-gate-risk
    max_retries: 0
EOF
}

# ============================================================
# Test 1: pass — section + both subsections + both levels
# ============================================================
test_pass() {
    echo "=== Test 1: pass ==="
    local d; d="$(new_fixture)"
    write_task "$d" 10 "" low low
    write_plan "$d" 10 full
    run_verifier "$d" 10 1 "rpass"
    assert_eq "pass: exit 0" "0" "$RC"
    assert_contains "pass: ledger pass" "status=pass" "$(cat "$(task_file_path "$d" 10)")"
    assert_eq "pass: sidecar log exists" "yes" \
        "$([[ -f "$d/.aitask-gates/10/risk_evaluated_rpass.log" ]] && echo yes || echo no)"
}

# ============================================================
# Test 2: fail — no ## Risk section
# ============================================================
test_fail_no_section() {
    echo "=== Test 2: fail (no ## Risk section) ==="
    local d; d="$(new_fixture)"
    write_task "$d" 11 "" low low
    write_plan "$d" 11 no_section
    run_verifier "$d" 11 1 "rf"
    assert_eq "no-section: exit 1" "1" "$RC"
    assert_contains "no-section: ledger fail" "status=fail" "$(cat "$(task_file_path "$d" 11)")"
}

# ============================================================
# Test 2b: fail — ## Risk present but a dimension subsection missing
# ============================================================
test_fail_missing_subsection() {
    echo "=== Test 2b: fail (missing dimension subsection) ==="
    local d; d="$(new_fixture)"
    write_task "$d" 12 "" low low
    write_plan "$d" 12 no_goal_sub
    run_verifier "$d" 12 1 "rf"
    assert_eq "missing-subsection: exit 1" "1" "$RC"
    assert_contains "missing-subsection: log names the missing subsection" "Goal-achievement risk" \
        "$(cat "$d/.aitask-gates/12/risk_evaluated_rf.log")"
}

# ============================================================
# Test 3: fail — task missing a risk field
# ============================================================
test_fail_missing_field() {
    echo "=== Test 3: fail (missing frontmatter field) ==="
    local d; d="$(new_fixture)"
    write_task "$d" 13 "" low ""        # risk_goal_achievement omitted
    write_plan "$d" 13 full
    run_verifier "$d" 13 1 "rf"
    assert_eq "missing-field: exit 1" "1" "$RC"
    assert_contains "missing-field: ledger fail" "status=fail" "$(cat "$(task_file_path "$d" 13)")"
}

# ============================================================
# Test 4: fail — no plan file on disk
# ============================================================
test_fail_no_plan() {
    echo "=== Test 4: fail (no plan file) ==="
    local d; d="$(new_fixture)"
    write_task "$d" 14 "" low low       # no write_plan
    run_verifier "$d" 14 1 "rf"
    assert_eq "no-plan: exit 1" "1" "$RC"
    assert_contains "no-plan: log says no plan file" "no plan file" \
        "$(cat "$d/.aitask-gates/14/risk_evaluated_rf.log")"
}

# ============================================================
# Test 5: fail — invalid level value
# ============================================================
test_fail_invalid_level() {
    echo "=== Test 5: fail (invalid level) ==="
    local d; d="$(new_fixture)"
    write_task "$d" 15 "" bogus low
    write_plan "$d" 15 full
    run_verifier "$d" 15 1 "rf"
    assert_eq "invalid-level: exit 1" "1" "$RC"
    assert_contains "invalid-level: log flags the bad level" "risk_code_health not" \
        "$(cat "$d/.aitask-gates/15/risk_evaluated_rf.log")"
}

# ============================================================
# Test 6: child-task path resolution (task + plan under t<p>/ and p<p>/)
# ============================================================
test_child_pass() {
    echo "=== Test 6: child-task pass ==="
    local d; d="$(new_fixture)"
    write_task "$d" 10_2 "" medium high
    write_plan "$d" 10_2 full
    run_verifier "$d" 10_2 1 "rchild"
    assert_eq "child: exit 0" "0" "$RC"
    assert_contains "child: ledger pass" "status=pass" "$(cat "$(task_file_path "$d" 10_2)")"
}

# ============================================================
# Test 7: sidecar log content (pass names plan + levels)
# ============================================================
test_sidecar_content() {
    echo "=== Test 7: sidecar log content ==="
    local d; d="$(new_fixture)"
    write_task "$d" 16 "" high medium
    write_plan "$d" 16 full
    run_verifier "$d" 16 1 "rlog"
    local logf="$d/.aitask-gates/16/risk_evaluated_rlog.log"
    assert_contains "sidecar: records RESULT pass" "RESULT: pass" "$(cat "$logf")"
    assert_contains "sidecar: records code-health level" "risk_code_health: high" "$(cat "$logf")"
    assert_contains "sidecar: records goal level" "risk_goal_achievement: medium" "$(cat "$logf")"
}

# ============================================================
# Test 8: orchestrator integration + reconciliation hygiene
# ============================================================
test_orchestrator_integration() {
    echo "=== Test 8: orchestrator integration + reconciliation hygiene ==="
    # pass: verifier self-appends a terminal `pass` that matches its exit 0, so the
    # engine's reconcile is a no-op (no duplicate, no malformed correction).
    local d tf out; d="$(new_fixture)"; risk_registry "$d"
    write_task "$d" 40 "risk_evaluated" low low
    write_plan "$d" 40 full
    out="$(orch "$d" 40)"; tf="$(task_file_path "$d" 40)"
    assert_contains "integration pass: reported pass" "risk_evaluated: pass" "$out"
    assert_eq "integration pass: exactly one terminal pass" "1" "$(count_status "$tf" pass)"
    assert_eq "integration pass: no error correction" "0" "$(count_status "$tf" error)"
    assert_not_contains "integration pass: no malformed correction" "malformed" "$(cat "$tf")"

    # fail: same hygiene for a fail (no ## Risk section).
    d="$(new_fixture)"; risk_registry "$d"
    write_task "$d" 41 "risk_evaluated" low low
    write_plan "$d" 41 no_section
    out="$(orch "$d" 41)"; tf="$(task_file_path "$d" 41)"
    assert_contains "integration fail: reported fail" "risk_evaluated: fail" "$out"
    assert_eq "integration fail: exactly one terminal fail" "1" "$(count_status "$tf" fail)"
    assert_eq "integration fail: no error correction" "0" "$(count_status "$tf" error)"
    assert_not_contains "integration fail: no malformed correction" "malformed" "$(cat "$tf")"
}

# --- Run ---
test_pass
test_fail_no_section
test_fail_missing_subsection
test_fail_missing_field
test_fail_no_plan
test_fail_invalid_level
test_child_pass
test_sidecar_content
test_orchestrator_integration

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
