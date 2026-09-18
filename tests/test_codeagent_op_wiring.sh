#!/usr/bin/env bash
# test_codeagent_op_wiring.sh - Cross-op wiring guard for aitask_codeagent.sh
# (t1823_3, risk mitigation [unwired_op_guard]).
#
# The operation list is duplicated across ~8 heterogeneous sites. The codex
# composer fails closed on an operation it does not know (tests/test_codeagent.sh
# Test 11d4 pins that), but claudecode and opencode fail OPEN: an operation added
# to SUPPORTED_OPERATIONS and nowhere else silently composes a launch with no
# slash command at all, and its arguments are never validated.
#
# This guard closes both halves for EVERY skill-backed operation, not just the
# one a focused test happens to cover:
#
#   prompt wiring     — `--dry-run invoke <op> probe` must compose a non-empty
#                       /aitask-… prompt for claudecode AND opencode;
#   validation cover  — every operation whose prompt actually carries the
#                       argument must refuse an empty one (the :443 alternation).
#
# The validation half is checked behaviourally rather than by regex-parsing the
# alternation: the property that matters is "this op refuses an unrepresentable
# argument", and an operation that ignores argv (explore) correctly has no such
# duty. Ops are read from the script itself, so a new operation is covered the
# day it is added.
#
# Run: bash tests/test_codeagent_op_wiring.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
# shellcheck source=lib/scratch_cwd.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
# shellcheck source=lib/asserts.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Operations that legitimately compose NO slash command. Each is a passthrough
# or a special launch, not a skill-backed op:
#   batch-review / raw  — argv is handed to the agent verbatim;
#   explore-relay       — claudecode-only headless launch gated on env vars
#                         (CHATLINK_*), which refuses before composing.
# The list is asserted to be a subset of the parsed operations below, so a
# renamed or removed operation cannot silently turn it into a blanket exemption.
EXEMPT_OPS=(batch-review raw explore-relay)

# Agents whose arms fail OPEN for an unwired operation (codex fails closed and
# is covered by test_codeagent.sh Test 11d4).
WIRING_AGENTS=(claudecode/opus5 opencode/openai_gpt_5_4)

# --- Test environment setup ---

setup_test_env() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    mkdir -p "$tmpdir/aitasks/metadata"
    setup_fake_aitask_repo "$tmpdir"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh" "$tmpdir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/agent_string.sh" "$tmpdir/.aitask-scripts/lib/"
    chmod +x "$tmpdir/.aitask-scripts/aitask_codeagent.sh"

    cp "$PROJECT_DIR/aitasks/metadata/models_claudecode.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/models_codex.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/models_opencode.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/seed/codeagent_config.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$tmpdir/aitasks/metadata/"

    (cd "$tmpdir" && git init --quiet && git config user.email "test@test.com" && git config user.name "Test")

    echo "$tmpdir"
}

cleanup_test_env() {
    [[ -n "${1:-}" && -d "$1" ]] && rm -rf "$1"
}

# --- Guard ---------------------------------------------------------------

# Last argv element of a DRY_RUN: line, unescaped (same helper shape as
# test_codeagent.sh Test 11e).
dry_run_last_arg() {
    printf '%s\n' "$1" | python3 -c "
import shlex, sys
for line in sys.stdin:
    if line.startswith('DRY_RUN:'):
        print(shlex.split(line[len('DRY_RUN:'):])[-1])"
}

parse_supported_operations() {
    # Same extraction as tests/test_website_doc_lists.sh: the array is a single
    # line by contract, and both guards break loudly if it is ever reformatted.
    sed -n 's/^SUPPORTED_OPERATIONS=(\(.*\))[[:space:]]*$/\1/p' "$1"
}

# Prints one tagged line per defect to stdout and returns the defect count.
# No PASS/FAIL side effects — the caller asserts on the count and the tags, so
# the same function can be run against the real script and against mutants.
#   PROMPT_UNWIRED:<agent>:<op>    — composed no /aitask-… prompt
#   VALIDATION_MISSING:<op>        — arg-bearing prompt, but an empty arg was accepted
op_wiring_failures() {
    local script="$1" workdir="$2"
    local failures=0
    local ops_raw op agent output rc last
    local -a all_ops

    ops_raw="$(parse_supported_operations "$script")"
    read -r -a all_ops <<<"$ops_raw"

    for op in "${all_ops[@]}"; do
        local exempt=0 e
        for e in "${EXEMPT_OPS[@]}"; do
            [[ "$op" == "$e" ]] && exempt=1
        done
        [[ "$exempt" == 1 ]] && continue

        local arg_bearing=0
        for agent in "${WIRING_AGENTS[@]}"; do
            rc=0
            output=$(cd "$workdir" || exit 1; bash "$script" --agent-string "$agent" \
                --dry-run invoke "$op" probe 2>&1) || rc=$?
            if [[ "$rc" -ne 0 || "$output" != *"DRY_RUN:"* ]]; then
                echo "PROMPT_UNWIRED:${agent%%/*}:$op"
                failures=$((failures + 1))
                continue
            fi
            last="$(dry_run_last_arg "$output")"
            if [[ ! "$last" =~ ^/aitask-[a-z-]+ ]]; then
                echo "PROMPT_UNWIRED:${agent%%/*}:$op"
                failures=$((failures + 1))
                continue
            fi
            # An op whose prompt carries the argument consumes argv, and so owes
            # the empty/whitespace refusal. `explore` ignores argv by design and
            # is therefore exempt from the validation half, with no list to rot.
            [[ "$last" == *" probe"* ]] && arg_bearing=1
        done

        [[ "$arg_bearing" == 1 ]] || continue

        rc=0
        output=$(cd "$workdir" || exit 1; bash "$script" --dry-run invoke "$op" "" 2>&1) || rc=$?
        if [[ "$rc" -eq 0 || "$output" != *"argument is empty"* ]]; then
            echo "VALIDATION_MISSING:$op"
            failures=$((failures + 1))
        fi
    done

    return "$failures"
}

# --- Tests ---

echo "=== test_codeagent_op_wiring.sh ==="
echo ""

if ! command -v jq &>/dev/null; then
    echo "SKIP: jq is required for these tests"
    exit 0
fi

TMPDIR_TEST="$(setup_test_env)"
CODEAGENT="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent.sh"

# Test 1: tripwire — the op list parsed, non-empty, and recognisable.
# Without this every containment loop below could pass vacuously.
echo "--- Test 1: SUPPORTED_OPERATIONS parses ---"
ops_raw="$(parse_supported_operations "$CODEAGENT")"
assert_exit_zero "SUPPORTED_OPERATIONS is non-empty" test -n "$ops_raw"
assert_contains "parsed operations include pick" "pick" "$ops_raw"
read -r -a parsed_ops <<<"$ops_raw"
assert_exit_zero "more than the exempt operations are parsed" \
    test "${#parsed_ops[@]}" -gt "${#EXEMPT_OPS[@]}"

# Test 2: the exemption list cannot rot into a blanket exemption
echo "--- Test 2: exemption list is a subset of the parsed operations ---"
for exempt_op in "${EXEMPT_OPS[@]}"; do
    found=0
    for op in "${parsed_ops[@]}"; do
        [[ "$op" == "$exempt_op" ]] && found=1
    done
    assert_eq "exempt op '$exempt_op' still exists in SUPPORTED_OPERATIONS" "1" "$found"
done

# Test 3: the shipped script is fully wired and fully validated
echo "--- Test 3: every skill-backed operation is wired and validated ---"
real_rc=0
real_out="$(op_wiring_failures "$CODEAGENT" "$TMPDIR_TEST")" || real_rc=$?
assert_eq "shipped script has no wiring defects" "0" "$real_rc"
assert_eq "shipped script reports no defect lines" "" "$real_out"

# Test 4 (negative control a): an operation added to SUPPORTED_OPERATIONS only.
# This is the fail-open regression the guard exists for. Mutate a separate copy,
# and assert the transform matched exactly once so a silently non-matching
# mutant cannot make the control vacuous.
echo "--- Test 4: negative control (a) — prompt wiring ---"
CODEAGENT_UNWIRED="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent_unwired.sh"
awk_rc_a=0
awk '
    /^SUPPORTED_OPERATIONS=\(/ {
        sub(/\(/, "(unwired-probe ")
        matches++
    }
    { print }
    END { if (matches != 1) exit 1 }
' "$CODEAGENT" > "$CODEAGENT_UNWIRED" || awk_rc_a=$?
assert_eq "mutant (a) transform matched exactly once" "0" "${awk_rc_a:-0}"
assert_exit_nonzero "mutant (a) actually differs from the shipped script"     cmp -s "$CODEAGENT" "$CODEAGENT_UNWIRED"
chmod +x "$CODEAGENT_UNWIRED"

mutant_a_rc=0
mutant_a_out="$(op_wiring_failures "$CODEAGENT_UNWIRED" "$TMPDIR_TEST")" || mutant_a_rc=$?
assert_exit_zero "guard reports defects on mutant (a)" test "$mutant_a_rc" -gt 0
assert_contains "mutant (a) defect names the unwired op (claudecode)" \
    "PROMPT_UNWIRED:claudecode:unwired-probe" "$mutant_a_out"
assert_contains "mutant (a) defect names the unwired op (opencode)" \
    "PROMPT_UNWIRED:opencode:unwired-probe" "$mutant_a_out"
# Cross-assertion: the two halves of the guard are independent. A never-wired op
# takes no arguments, so ONLY the prompt check may fire here.
assert_not_contains "mutant (a) does not trip the validation half" \
    "VALIDATION_MISSING" "$mutant_a_out"
rm -f "$CODEAGENT_UNWIRED"

# Test 5 (negative control b): an operation whose prompt is fully wired but
# whose empty/whitespace-argument protection was dropped from the :443
# alternation. Nothing in the prompt half can catch this — which is exactly why
# the validation half exists.
echo "--- Test 5: negative control (b) — validation coverage ---"
CODEAGENT_UNVALIDATED="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent_unvalidated.sh"
awk_rc_b=0
awk '
    /^[[:space:]]*pick\|explain\|qa\|shadow\|learn\|work-report\|trail\|discuss\)/ {
        sub(/\|discuss\)/, ")")
        matches++
    }
    { print }
    END { if (matches != 1) exit 1 }
' "$CODEAGENT" > "$CODEAGENT_UNVALIDATED" || awk_rc_b=$?
assert_eq "mutant (b) transform matched exactly once" "0" "${awk_rc_b:-0}"
assert_exit_nonzero "mutant (b) actually differs from the shipped script"     cmp -s "$CODEAGENT" "$CODEAGENT_UNVALIDATED"
chmod +x "$CODEAGENT_UNVALIDATED"

mutant_b_rc=0
mutant_b_out="$(op_wiring_failures "$CODEAGENT_UNVALIDATED" "$TMPDIR_TEST")" || mutant_b_rc=$?
assert_exit_zero "guard reports defects on mutant (b)" test "$mutant_b_rc" -gt 0
assert_contains "mutant (b) defect names the unvalidated op" \
    "VALIDATION_MISSING:discuss" "$mutant_b_out"
# Cross-assertion: prompt wiring is untouched by this mutation, so the prompt
# half must stay silent — the two controls prove different guards.
assert_not_contains "mutant (b) does not trip the prompt half" \
    "PROMPT_UNWIRED" "$mutant_b_out"
rm -f "$CODEAGENT_UNVALIDATED"

# --- Cleanup ---

set +e
cleanup_test_env "$TMPDIR_TEST"

# --- Summary ---

echo ""
echo "=== Results ==="
echo "PASS: $PASS / $TOTAL"
if [[ $FAIL -gt 0 ]]; then
    echo "FAIL: $FAIL"
    exit 1
else
    echo "All tests passed."
    exit 0
fi
