#!/usr/bin/env bash
#
# End-to-end CLI contract for aitask_parallel_admission.sh (t1569_3).
#
# The Python tests drive `main()` in-process; this file drives the SHELL
# WRAPPER, which is the surface t1569_4 actually calls from task-workflow. It
# pins the one thing the wrapper is responsible for: the exit-status split.
#
#   every CONTENT state -> exit 0 (the caller reads VERDICT:)
#   CLI misuse          -> exit 2 (a silent verdict for a typo is the hazard)
#
# Assertions run at top level in the parent shell, so the file-backed counters
# are not needed (same shape as tests/test_change_surface.sh).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
source "$SCRIPT_DIR/lib/asserts.sh"

PASS=0; FAIL=0; TOTAL=0
CHECKER="$REPO_ROOT/.aitask-scripts/aitask_parallel_admission.sh"

# Returns the exit status without tripping `set -e` semantics in callers.
run_rc() {
    "$CHECKER" "$@" >/dev/null 2>&1
    echo $?
}

run_out() {
    "$CHECKER" "$@" 2>/dev/null
}

echo "=== aitask_parallel_admission.sh CLI contract ==="

assert_file_exists "checker script exists" "$CHECKER"
assert_eq "checker is executable" "0" "$(test -x "$CHECKER" && echo 0 || echo 1)"

# --- CLI misuse dies -------------------------------------------------------
assert_eq "no subcommand exits 2" "2" "$(run_rc)"
assert_eq "unknown subcommand exits 2" "2" "$(run_rc frobnicate)"
assert_eq "check without --candidate exits 2" "2" "$(run_rc check --from plan)"
assert_eq "unknown flag exits 2" "2" "$(run_rc check --candidate 1 --nope x)"
assert_eq "bad --from exits 2" "2" "$(run_rc check --candidate 1 --from sideways)"
assert_eq "bad --lock-freshness exits 2" "2" \
    "$(run_rc check --candidate 1 --lock-freshness maybe)"
assert_eq "a typo'd --plan target exits 2 rather than returning a silent verdict" \
    "2" "$(run_rc check --candidate 1 --plan /no/such/plan.md)"
assert_eq "replay without --candidates exits 2" "2" "$(run_rc replay)"

# Misuse must say why, on stderr, and must NOT emit a verdict.
misuse_err="$("$CHECKER" check --from plan 2>&1 >/dev/null)"
assert_contains "misuse names the problem" "requires --candidate" "$misuse_err"
misuse_out="$("$CHECKER" check --from plan 2>/dev/null)"
assert_not_contains "misuse emits no verdict on stdout" "VERDICT:" "$misuse_out"

# --- content states exit 0 -------------------------------------------------
out="$(run_out check --candidate 1569_3 --from plan --lock-freshness allow-cached)"
assert_eq "a real check exits 0" "0" \
    "$(run_rc check --candidate 1569_3 --from plan --lock-freshness allow-cached)"
assert_contains "a real check emits a verdict" "VERDICT:" "$out"
assert_contains "a real check emits a display line" "DISPLAY:" "$out"
assert_contains "a real check emits the candidate record" "CANDIDATE:" "$out"
assert_contains "a real check emits the lock record" "LOCKS:" "$out"

# All three enumeration records, always, in the declared order.
sources="$(printf '%s\n' "$out" | grep '^INFLIGHT_SOURCE:' \
           | cut -d: -f2 | cut -d'|' -f1 | tr '\n' ' ')"
assert_eq "all three INFLIGHT_SOURCE records, in order" "gate lock status " "$sources"

# An unresolvable candidate is a CONTENT state: still exit 0, never CLEAR.
unk="$(run_out check --candidate 99999999 --from origin --lock-freshness allow-cached)"
assert_eq "an unresolvable candidate still exits 0" "0" \
    "$(run_rc check --candidate 99999999 --from origin --lock-freshness allow-cached)"
assert_contains "an unknown candidate is UNCHECKABLE" "VERDICT:UNCHECKABLE" "$unk"
assert_not_contains "an unknown candidate is never CLEAR" "VERDICT:CLEAR" "$unk"

# --- the wording guarantee, at the real CLI --------------------------------
# The forbidden phrase is verdict-INDEPENDENT: no verdict may ever claim it.
assert_not_contains "the CLI never claims parallel safety" \
    "safe to run in parallel" "$out"
# The required phrase belongs to the no-collision verdicts only; UNCHECKABLE
# says "could not compare". Which one we get depends on the live in-flight set,
# so gate the assertion on the verdict rather than pinning one outcome. The
# exhaustive, deterministic wording pin lives in
# tests/test_parallel_admission.py::ClearWordingTests, over fixtures.
verdict="$(printf '%s\n' "$out" | sed -n 's/^VERDICT://p')"
case "$verdict" in
    CLEAR|CLEAR_CAVEATED)
        assert_contains "a no-collision verdict states the observation, not a reservation" \
            "no known conflict at check time" "$out" ;;
    *)
        assert_contains "a non-clear verdict explains itself" "DISPLAY:" "$out" ;;
esac

# --- determinism -----------------------------------------------------------
# Scoped to the records that do NOT depend on the live in-flight set: this repo
# has concurrent agents claiming and releasing tasks, so INFLIGHT:/OVERLAP:/
# CAVEAT:/VERDICT: can legitimately differ between two runs seconds apart, and
# asserting on them here would be a race, not a determinism check. The strong
# guarantee -- identical input yields byte-identical output -- is pinned
# deterministically over a frozen AdmissionInput in
# tests/test_parallel_admission.py::RenderTests.
stable() {
    run_out check --candidate 1569_3 --from plan --lock-freshness allow-cached \
        | grep -E '^(CORPUS:|INFLIGHT_SOURCE:|CANDIDATE:)'
}
assert_eq "the input-derived records are stable across runs" "$(stable)" "$(stable)"

echo
echo "Results: $TOTAL total, $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
