#!/usr/bin/env bash
# test_brainstorm_apply_help.sh - --help / usage handling of the three
# `ait brainstorm apply-*` wrappers (t2305).
# Run: bash tests/test_brainstorm_apply_help.sh
#
# None of these cases reach Python on purpose. The "Python-free help" block
# points AIT_PYTHON at a failing stub to prove --help is parsed BEFORE the
# interpreter is resolved; its positive control proves the stub is really the
# interpreter these wrappers resolve, so the block cannot pass vacuously.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# Shared assertion helpers (see tests/lib/asserts.sh). All assertions run at
# top level (no subshells), so the in-process counters are sufficient.
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0
FAIL=0
TOTAL=0

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/brainstorm_apply_help.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

# bash-3.2-safe (macOS): plain functions instead of associative arrays.
script_of() { printf '%s' "$PROJECT_DIR/.aitask-scripts/aitask_brainstorm_apply_$1.sh"; }
# One more positional argument than each wrapper accepts.
too_many_args() {
    case "$1" in
        initializer) printf '%s' "42 43" ;;
        *)           printf '%s' "42 agent_x extra" ;;
    esac
}

# run <cmd...>: capture stdout, stderr and exit status into r_out / r_err / r_rc.
r_out="" r_err="" r_rc=""
run() {
    local out_f="$SCRATCH/out" err_f="$SCRATCH/err"
    r_rc=0
    "$@" >"$out_f" 2>"$err_f" || r_rc=$?
    r_out="$(cat "$out_f")"
    r_err="$(cat "$err_f")"
}

for kind in initializer explorer synthesizer; do
    script="$(script_of "$kind")"
    echo "--- apply-$kind ---"

    for flag in --help -h; do
        run bash "$script" "$flag"
        assert_eq "$kind $flag exits 0" "0" "$r_rc"
        assert_contains "$kind $flag shows usage line" \
            "Usage: ait brainstorm apply-$kind" "$r_out"
        assert_contains "$kind $flag documents APPLIED:" "APPLIED:" "$r_out"
        assert_contains "$kind $flag documents APPLY_FAILED:" "APPLY_FAILED:" "$r_out"
        assert_not_contains "$kind $flag does not attempt an apply" \
            "APPLY_FAILED:No initializer" "$r_out$r_err"
        assert_contains "$kind $flag says not every failure writes a log" \
            "Not every failure writes a log" "$r_out"
    done

    run bash "$script" 42 --help
    assert_eq "$kind: --help after a positional exits 0" "0" "$r_rc"
    assert_contains "$kind: --help after a positional shows usage" \
        "Usage: ait brainstorm apply-$kind" "$r_out"

    run bash "$script" --bogus
    assert_eq "$kind --bogus exits 2" "2" "$r_rc"
    assert_contains "$kind --bogus names the option" "Unknown option: --bogus" "$r_err"
    assert_contains "$kind --bogus points at --help" "--help" "$r_err"

    run bash "$script"
    assert_eq "$kind with no args exits 2" "2" "$r_rc"
    assert_contains "$kind with no args prints usage" "Usage:" "$r_err"

    # shellcheck disable=SC2046  # deliberate word splitting of the arg list
    run bash "$script" $(too_many_args "$kind")
    assert_eq "$kind with too many args exits 2" "2" "$r_rc"
    assert_contains "$kind with too many args names the extra" \
        "Unexpected argument:" "$r_err"
done

# --- Python-free help ---------------------------------------------------------
echo "--- Python-free help (failing interpreter stub) ---"
STUB="$SCRATCH/python_stub"
STUB_LOG="$SCRATCH/stub.log"
cat >"$STUB" <<'EOF'
#!/usr/bin/env bash
echo "called $*" >>"$STUB_LOG"
exit 1
EOF
chmod +x "$STUB"

run_stubbed() {
    env -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$STUB" STUB_LOG="$STUB_LOG" "$@"
}

for kind in initializer explorer synthesizer; do
    for flag in --help -h; do
        : >"$STUB_LOG"
        run run_stubbed bash "$(script_of "$kind")" "$flag"
        assert_eq "$kind $flag exits 0 with a broken interpreter" "0" "$r_rc"
        assert_contains "$kind $flag shows usage with a broken interpreter" \
            "Usage: ait brainstorm apply-$kind" "$r_out"
        assert_eq "$kind $flag never invokes the interpreter" "" "$(cat "$STUB_LOG")"
    done
done

# Positive control: a real apply under the same env must hit the stub and fail.
: >"$STUB_LOG"
run run_stubbed bash "$(script_of initializer)" 42
assert_exit_nonzero_rc "control: apply with a broken interpreter fails" "$r_rc"
if [[ -s "$STUB_LOG" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: control: the stub was never invoked — AIT_PYTHON is not the resolved interpreter, so the Python-free assertions above prove nothing"
fi

# --- Argument-count validation happens before Python -----------------------
# An empty positional must not leave its slot free for the next argument:
# `"" 42` is two positionals, not the task number 42. Each case runs under the
# failing stub, so an input that slips through to an apply attempt shows up as
# a stub invocation (and exit 1) instead of the usage error (exit 2).
echo "--- empty / surplus positionals rejected before Python ---"
assert_rejected_pre_python() {
    local desc="$1" needle="$2"; shift 2
    : >"$STUB_LOG"
    run run_stubbed bash "$@"
    assert_eq "$desc exits 2" "2" "$r_rc"
    assert_contains "$desc names the problem" "$needle" "$r_err"
    assert_eq "$desc never invokes the interpreter" "" "$(cat "$STUB_LOG")"
}

INIT="$(script_of initializer)"
assert_rejected_pre_python "initializer '' 42" "Unexpected argument:" "$INIT" "" 42
assert_rejected_pre_python "initializer 42 ''" "Unexpected argument:" "$INIT" 42 ""
assert_rejected_pre_python "initializer ''" "Empty <task_num> argument" "$INIT" ""
assert_rejected_pre_python "initializer brainstorm-" "Empty <task_num> argument" "$INIT" brainstorm-
assert_rejected_pre_python "initializer 42 43" "Unexpected argument: 43" "$INIT" 42 43

for kind in explorer synthesizer; do
    sc="$(script_of "$kind")"
    assert_rejected_pre_python "$kind '' 42 agent_x" "Unexpected argument:" "$sc" "" 42 agent_x
    assert_rejected_pre_python "$kind 42 '' agent_x" "Unexpected argument:" "$sc" 42 "" agent_x
    assert_rejected_pre_python "$kind 42 agent_x ''" "Unexpected argument:" "$sc" 42 agent_x ""
    assert_rejected_pre_python "$kind '' agent_x" "Empty <task_num> argument" "$sc" "" agent_x
    assert_rejected_pre_python "$kind 42 ''" "Empty <agent_name> argument" "$sc" 42 ""
    assert_rejected_pre_python "$kind 42 agent_x extra" "Unexpected argument: extra" "$sc" 42 agent_x extra
done

# --- Dispatcher route ---------------------------------------------------------
echo "--- dispatcher ---"
run "$PROJECT_DIR/ait" brainstorm apply-initializer --help
assert_eq "ait brainstorm apply-initializer --help exits 0" "0" "$r_rc"
assert_contains "ait brainstorm apply-initializer --help shows usage" \
    "Usage: ait brainstorm apply-initializer" "$r_out"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

if [[ "$FAIL" -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
fi
echo "ALL TESTS PASSED"
