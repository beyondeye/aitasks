#!/usr/bin/env bash
# test_gate_effective_gates.sh - Tests for the t635_14 gate-resolution helpers,
# exercised through the real `aitask_gate.sh` entry point:
#   effective-gates / has-gates-field / should-self-record.
#
# - effective-gates: the literal `gates:` field wins when present (even `[]`);
#   otherwise fall back to the active profile's `default_gates`; else empty.
# - has-gates-field: field-presence oracle (exit 0 present incl. `[]`, exit 1
#   absent) — the Step-7 backfill keys off this so an explicit `gates: []`
#   opt-out is never overwritten (the case `list` cannot distinguish).
# - should-self-record: exit 0 = record (gate not literally declared), exit 1 =
#   skip (declared → the Step-9 orchestrator records it; avoids double-record).
#
# Run: bash tests/test_gate_effective_gates.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

# --- fixture helpers -------------------------------------------------------

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gateeff_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata/profiles" "$tmp/aiplans"
    printf 'name: fast\ndefault_gates: [risk_evaluated]\n' \
        > "$tmp/aitasks/metadata/profiles/fast.yaml"
    printf 'name: default\n' > "$tmp/aitasks/metadata/profiles/default.yaml"
    echo "$tmp"
}

# write_task <dir> <id> <gates-literal | __absent__>
# e.g. write_task "$d" 1 "[risk_evaluated, build_verified]" ; "[]" ; "__absent__"
write_task() {
    local dir="$1" id="$2" gates="$3"
    local path="$dir/aitasks/t${id}_x.md"
    {
        echo "---"
        echo "status: Ready"
        [[ "$gates" != "__absent__" ]] && echo "gates: ${gates}"
        echo "---"
        echo "Body."
    } > "$path"
}

# run_gate <dir> <args...> : run the real aitask_gate.sh from the fixture cwd
run_gate() {
    local dir="$1"; shift
    ( cd "$dir" && TASK_DIR=aitasks "$GATE" "$@" )
}

# --- tests -----------------------------------------------------------------

test_effective_gates() {
    local d; d="$(new_fixture)"
    write_task "$d" 1 "[risk_evaluated, build_verified]"
    write_task "$d" 2 "[]"
    write_task "$d" 3 "__absent__"
    local prof="aitasks/metadata/profiles"

    assert_eq "effective: populated field wins" "risk_evaluated,build_verified" \
        "$(run_gate "$d" effective-gates 1 --profile "$prof/fast.yaml" | paste -sd, -)"
    assert_eq "effective: empty [] opt-out honoured (NO profile fallback)" "" \
        "$(run_gate "$d" effective-gates 2 --profile "$prof/fast.yaml" | paste -sd, -)"
    assert_eq "effective: absent falls back to profile default_gates" "risk_evaluated" \
        "$(run_gate "$d" effective-gates 3 --profile "$prof/fast.yaml" | paste -sd, -)"
    assert_eq "effective: absent + profile w/o default_gates => empty" "" \
        "$(run_gate "$d" effective-gates 3 --profile "$prof/default.yaml" | paste -sd, -)"
    assert_eq "effective: absent + no --profile => empty" "" \
        "$(run_gate "$d" effective-gates 3 | paste -sd, -)"
    assert_eq "effective: absent + missing profile => empty (graceful)" "" \
        "$(run_gate "$d" effective-gates 3 --profile "$prof/nope.yaml" 2>/dev/null | paste -sd, -)"
}

test_has_gates_field() {
    local d; d="$(new_fixture)"
    write_task "$d" 1 "[risk_evaluated]"
    write_task "$d" 2 "[]"
    write_task "$d" 3 "__absent__"
    local rc
    run_gate "$d" has-gates-field 1; rc=$?
    assert_eq "has-field: populated => present (exit 0)" "0" "$rc"
    run_gate "$d" has-gates-field 2; rc=$?
    assert_eq "has-field: empty [] => present (exit 0)" "0" "$rc"
    run_gate "$d" has-gates-field 3; rc=$?
    assert_eq "has-field: absent => exit 1" "1" "$rc"
}

test_should_self_record() {
    local d; d="$(new_fixture)"
    write_task "$d" 1 "[risk_evaluated]"
    write_task "$d" 2 "[]"
    write_task "$d" 3 "__absent__"
    local rc
    run_gate "$d" should-self-record 1 risk_evaluated; rc=$?
    assert_eq "self-record: declared => skip (exit 1)" "1" "$rc"
    run_gate "$d" should-self-record 2 risk_evaluated; rc=$?
    assert_eq "self-record: empty [] not declared => record (exit 0)" "0" "$rc"
    run_gate "$d" should-self-record 3 risk_evaluated; rc=$?
    assert_eq "self-record: absent => record (exit 0)" "0" "$rc"
}

# --- Run ---
test_effective_gates
test_has_gates_field
test_should_self_record

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
