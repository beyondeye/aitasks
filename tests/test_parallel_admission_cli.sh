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
#
# RUNTIME ~35s, and that is inherent: every `check`/`replay`/`sweep` below is a
# real invocation against the live corpus (a batch map, three probes, two corpus
# listings). This file is run on its own, not from the Python lane, so it costs
# the suite nothing.

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

# --- t1643: the measurement surface ----------------------------------------
#
# `sweep` and the exclusion flags are MEASUREMENT surfaces: they render no
# admission decision. The wrapper contract they must satisfy is the same
# exit-status split as everything above -- content states exit 0, misuse exits 2
# -- plus the labelling that stops a counterfactual rate from being read as a
# live one.

assert_eq "sweep exits 0" "0" "$(run_rc sweep --thresholds 10)"
sweep_out="$(run_out sweep --thresholds 8,10)"
assert_contains "sweep emits per-threshold rows" "SWEEP:8|" "$sweep_out"
assert_contains "sweep emits the second threshold too" "SWEEP:10|" "$sweep_out"
assert_contains "sweep names its plan scope" "SWEEP_SCOPE:full" "$sweep_out"
assert_contains "sweep sizes its own population" "SWEEP_POP:" "$sweep_out"
assert_contains "sweep reports the corpus-drift bias" "SWEEP_DRIFT:" "$sweep_out"
assert_contains "sweep derives the metrics" "SWEEP_METRIC:8|" "$sweep_out"

scoped_out="$(run_out sweep --thresholds 10 --plan-scope pre-implementation)"
assert_contains "the plan scope is echoed, so a run is self-describing" \
    "SWEEP_SCOPE:pre-implementation" "$scoped_out"

# Recall of CONFLICT u CLEAR_CAVEATED is INVARIANT in the hub threshold under
# demotion (t1569_3 Step 1) -- a STRUCTURAL property of demotion, so it is safe
# to assert against the live corpus: it cannot go false because tasks were
# archived. Field 3 of SWEEP_METRIC is that recall.
recalls="$(printf '%s\n' "$sweep_out" | sed -n 's/^SWEEP_METRIC:[0-9]*|[^|]*|\([^|]*\).*/\1/p' | sort -u | wc -l)"
assert_eq "recall is invariant across the swept thresholds" "1" "$recalls"

# The paired negative control -- that precision and the hard-stop share DO move,
# so the invariance above is not vacuous -- is deliberately NOT asserted here.
# Whether two thresholds grade differently depends on whether any path's touch
# count falls between them, which is a CORPUS STATISTIC: a corpus with no such
# path would fail this for no defect. It is pinned instead against a designed
# fixture, where the touch counts are chosen to straddle the thresholds:
# tests/test_parallel_admission_sweep.py::RecallInvarianceTests
#   ::test_negative_control_precision_and_grading_do_move.

# --- exclusion is replay-only, and the two refusals are distinct ------------
assert_eq "check --exclude exits 2" "2" "$(run_rc check --candidate 1 --exclude 9)"
assert_eq "check --exclude-no-plan exits 2" "2" \
    "$(run_rc check --candidate 1 --exclude-no-plan)"
assert_eq "sweep --exclude exits 2" "2" "$(run_rc sweep --exclude 9)"
assert_eq "sweep --exclude-no-plan exits 2" "2" "$(run_rc sweep --exclude-no-plan)"
assert_eq "--thresholds and --hub-threshold together exit 2" "2" \
    "$(run_rc replay --candidates - --thresholds 8 --hub-threshold 10)"

check_excl_err="$("$CHECKER" check --candidate 1 --exclude 9 2>&1 >/dev/null)"
sweep_excl_err="$("$CHECKER" sweep --exclude 9 2>&1 >/dev/null)"
assert_contains "check's refusal is about admission safety" \
    "admission point hides a real collision" "$check_excl_err"
assert_contains "sweep's refusal is about having nothing to filter" \
    "archived pairs" "$sweep_excl_err"
assert_eq "the two refusals are not the same message" "differ" \
    "$([[ "$check_excl_err" == "$sweep_excl_err" ]] && echo same || echo differ)"
check_excl_out="$("$CHECKER" check --candidate 1 --exclude 9 2>/dev/null)"
assert_not_contains "a refused check emits no verdict" "VERDICT:" "$check_excl_out"

# --- the EXCLUDED marker, in BOTH directions -------------------------------
#
# A marker that is always present labels nothing, and one that is always absent
# labels nothing either -- so both are asserted. (The BEHAVIOURAL half, that an
# exclusion actually moves the comparison, is pinned in
# tests/test_parallel_admission_collect.py; neither substitutes for the other.)
cand_list="$(mktemp)"
trap 'rm -f "$cand_list"' EXIT
printf '1\n' > "$cand_list"
plain_replay="$(run_out replay --candidates "$cand_list" --thresholds 10)"
excl_replay="$(run_out replay --candidates "$cand_list" --thresholds 10 --exclude t1)"
assert_not_contains "a plain replay carries no exclusion marker" \
    "EXCLUDED:" "$plain_replay"
assert_contains "an excluded replay names the canonicalised ids" \
    "EXCLUDED:1" "$excl_replay"

# An excluded rate must never be reportable on its own: every RATES_AT_EXCL row
# is emitted beside the RATES_AT row for the same threshold, so a counterfactual
# cannot be pasted onward as if it were the live figure.
assert_contains "the excluded run still reports the unexcluded population" \
    "RATES_AT:10|" "$excl_replay"
assert_contains "... alongside its counterfactual twin" \
    "RATES_AT_EXCL:10|" "$excl_replay"

# --- back-compat: the single-threshold protocol t1569_3 shipped ------------
legacy_replay="$(run_out replay --candidates "$cand_list")"
assert_contains "a single-threshold replay still emits RATES:" "RATES:" "$legacy_replay"
assert_not_contains "... and none of the swept lines" "RATES_AT:" "$legacy_replay"
assert_not_contains "... nor a snapshot header" "SNAPSHOT:" "$legacy_replay"

echo
echo "Results: $TOTAL total, $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
