#!/usr/bin/env bash
# test_gate_pass.sh - Tests for `ait gate pass` signal creation (t635_15).
#
# Exercises .aitask-scripts/aitask_gate_pass.sh end-to-end against fixture tasks
# + a fixture registry (TASK_DIR override): machine-gate refusal, unknown-gate
# refusal, attended-only (no signal_target) refusal, witness creation (path
# substitution + code_digest binding), idempotence, and the integration path
# where the delegated `ait gates run` records the ledger `pass`.
#
# The witness dir is gitignored in the git fixture (mirrors the real gitignored
# .aitask-gates/) so the witness file itself does not perturb code_digest.
#
# Run: bash tests/test_gate_pass.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

PASS_SH="$PROJECT_DIR/.aitask-scripts/aitask_gate_pass.sh"

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gatepass_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata" "$tmp/sig"
    # A git fixture so code_digest is real; the witness dir is gitignored.
    ( cd "$tmp" && git init -q && git config user.email t@t && git config user.name t \
        && echo seed > code.txt && echo 'sig/' > .gitignore \
        && git add -A && git commit -qm init )
    cat > "$tmp/aitasks/metadata/gates.yaml" <<EOF
gates:
  review:
    type: human
    signal_target: "$tmp/sig/<task-id>-<gate>.signed"
  plan_only:
    type: human
  bg:
    type: machine
    verifier: x
EOF
    echo "$tmp"
}

write_task() {  # <dir> <id> <gates-csv>
    local dir="$1" id="$2" gates="$3"
    printf -- '---\nstatus: Implementing\ngates: [%s]\n---\nBody.\n' "$gates" \
        > "$dir/aitasks/t${id}_x.md"
}

gate_pass() {  # <dir> <id> <gate>
    local dir="$1" id="$2" gate="$3"
    ( cd "$dir" && TASK_DIR="$dir/aitasks" "$PASS_SH" "$id" "$gate" 2>&1 )
}

# ============================================================
# Test 1: refuses a machine gate (no witness created)
# ============================================================
echo "=== Test 1: refuses machine gate ==="
d="$(new_fixture)"; write_task "$d" 10 "bg"
out="$(gate_pass "$d" 10 bg)"; rc=$?
assert_eq "machine gate -> non-zero exit" "1" "$rc"
assert_contains "machine gate -> refusal message" "refuses machine gate" "$out"
[[ -e "$d/sig/t10-bg.signed" ]] \
    && { echo "FAIL: witness created for machine gate"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); } \
    || { PASS=$((PASS+1)); TOTAL=$((TOTAL+1)); }

# ============================================================
# Test 2: refuses an unknown gate
# ============================================================
echo "=== Test 2: refuses unknown gate ==="
d="$(new_fixture)"; write_task "$d" 11 "review"
out="$(gate_pass "$d" 11 no_such_gate)"; rc=$?
assert_eq "unknown gate -> non-zero exit" "1" "$rc"
assert_contains "unknown gate -> not defined" "not defined" "$out"

# ============================================================
# Test 3: refuses a human gate with no signal_target (attended-only)
# ============================================================
echo "=== Test 3: refuses attended-only human gate ==="
d="$(new_fixture)"; write_task "$d" 12 "plan_only"
out="$(gate_pass "$d" 12 plan_only)"; rc=$?
assert_eq "no signal_target -> non-zero exit" "1" "$rc"
assert_contains "no signal_target -> refusal" "no file-touch signal_target" "$out"

# ============================================================
# Test 4: creates a code-bound witness for a human gate
# ============================================================
echo "=== Test 4: creates code-bound witness ==="
d="$(new_fixture)"; write_task "$d" 13 "review"
out="$(gate_pass "$d" 13 review)"
sig="$d/sig/t13-review.signed"   # <task-id>->t13, <gate>->review
[[ -f "$sig" ]] \
    && { PASS=$((PASS+1)); TOTAL=$((TOTAL+1)); } \
    || { echo "FAIL: witness not created at $sig"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); }
assert_contains "witness records signer" "signer=" "$(cat "$sig" 2>/dev/null)"
assert_contains "witness records signed_at" "signed_at=" "$(cat "$sig" 2>/dev/null)"
assert_contains "witness records code_digest" "code_digest=" "$(cat "$sig" 2>/dev/null)"

# ============================================================
# Test 5: idempotent re-sign (still one witness, re-stamped)
# ============================================================
echo "=== Test 5: idempotent re-sign ==="
d="$(new_fixture)"; write_task "$d" 14 "review"
gate_pass "$d" 14 review >/dev/null
out="$(gate_pass "$d" 14 review)"
assert_contains "second call reports re-signed" "Re-signed" "$out"
n="$(find "$d/sig" -name 't14-review.signed' | wc -l | tr -d ' ')"
assert_eq "still exactly one witness file" "1" "$n"

# ============================================================
# Test 6: integration — delegated `ait gates run` records the ledger pass
#         (the durable, cross-PC artifact) with a signed_digest note
# ============================================================
echo "=== Test 6: delegated recording appends ledger pass ==="
d="$(new_fixture)"; write_task "$d" 15 "review"
gate_pass "$d" 15 review >/dev/null
task_body="$(cat "$d/aitasks/t15_x.md")"
assert_contains "ledger has a review pass block" "gate:review" "$task_body"
assert_contains "ledger pass is status=pass" "status=pass" "$task_body"
assert_contains "ledger pass carries signed_digest note" "signed_digest:" "$task_body"

# --- summary ---
echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done
[[ "$FAIL" -eq 0 ]] && { echo "All tests PASSED"; exit 0; } || { echo "SOME TESTS FAILED"; exit 1; }
