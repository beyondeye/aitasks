#!/usr/bin/env bash
set -euo pipefail

# Attribution verdict-log producer/consumer contract (t1510).
#
# The board-movement attribution negative control writes a machine-readable
# verdict record when AITASK_BOARD_ATTR_VERDICT_LOG names a path, and the
# acceptance protocol for that test greps the record to prove the localisation
# claim was EVALUATED (a `skipTest` leaves the aggregate suite green, so the
# suite's own exit status cannot tell "satisfied" from "declined to evaluate").
#
# WHY A SHELL TEST EXISTS AT ALL. The producer is pinned in Python by
# AttributionVerdictFormatTests, but that test asserts with Python's `re`, where
# `\t` IS a tab. The consumer is `grep -E`, and **POSIX ERE has no `\t`
# escape**: GNU grep prints "warning: stray \ before t" and matches NOTHING,
# and BSD grep behaves the same. A `^localised\t` matcher therefore reports
# FAILURE on a passing run on essentially every machine -- while silently
# working on the few greps that extend ERE (ugrep does), which is exactly the
# kind of false green that makes the acceptance check worthless. The Python
# format test cannot catch that, because it never runs grep. This file does.

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

#: THE canonical acceptance matcher. Portable POSIX bracket expression -- keep
#: this in sync with the acceptance commands in
#: aiplans/archived/p1510_*.md and any follow-up verification task.
VERDICT_MATCH_OK='^localised[[:space:]]'

# count_match <file> — records satisfying the acceptance matcher. `grep -c`
# prints the count and exits 1 when it is zero, so only the STATUS is swallowed;
# adding an `|| echo 0` fallback would emit a second line.
count_match() {
    grep -cE "$VERDICT_MATCH_OK" "$1" 2>/dev/null || true
}

PY="${PYTHON:-python3}"

# emit <verdict> <detail> [logfile] — drive the REAL writer (`_emit_verdict`),
# not a replica, so the env-var plumbing and the append mode are exercised too.
emit() {
    local verdict="$1" detail="$2" log="$3"
    AITASK_BOARD_ATTR_VERDICT_LOG="$log" "$PY" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from tests.test_board_movement import _emit_verdict
_emit_verdict(sys.argv[1], sys.argv[2])
" "$verdict" "$detail" 2>/dev/null
}

echo "=== Attribution verdict-log producer/consumer contract ==="
echo "grep in use: $(grep --version 2>&1 | head -1)"

# --- T1: the documented matcher finds a real record -------------------------
log="$TESTROOT/ok.log"
emit localised "refocus +50.1 ms | worst neighbour render +1.4 ms (bound 25.0 ms)" "$log"
assert_file_exists "T1: writer created the log" "$log"
assert_eq "T1: exactly one record" "1" "$(wc -l < "$log" | tr -d ' ')"
assert_eq "T1: documented matcher hits it" "1" \
    "$(count_match "$log")"

# --- T2: the record really is TAB-separated, token first --------------------
assert_eq "T2: first field is the bare verdict token" "localised" \
    "$(cut -f1 < "$log")"
assert_contains "T2: detail survives after the tab" "worst neighbour render" \
    "$(cut -f2 < "$log")"

# --- T3: NEGATIVE CONTROL — the human prose line must NOT satisfy acceptance -
# This is the regression the Python format test cannot see: if the writer ever
# logged the stderr prose instead of the record, acceptance must go red.
prose="$TESTROOT/prose.log"
printf 'attribution localisation: localised | refocus +50.1 ms\n' > "$prose"
assert_eq "T3: prose line does not match the acceptance pattern" "0" \
    "$(count_match "$prose")"

# --- T4: NEGATIVE CONTROL — a non-localised verdict must NOT match ----------
# An `undecidable` skip is explicitly NOT acceptance; it must not be counted.
for v in undecidable leaked; do
    f="$TESTROOT/$v.log"
    emit "$v" "some detail" "$f"
    assert_eq "T4: \`$v\` record is written at all" "1" \
        "$(wc -l < "$f" | tr -d ' ')"
    assert_eq "T4: ...but does not match the localised acceptance pattern" "0" \
        "$(count_match "$f")"
done

# --- T5: NEGATIVE CONTROL — the pattern is not matching a literal 't' -------
# Guards against a matcher that degraded into `^localised` + any char.
bogus="$TESTROOT/bogus.log"
printf 'localisedt not a real verdict\n' > "$bogus"
assert_eq "T5: 'localisedt' does not match" "0" \
    "$(count_match "$bogus")"

# --- T6: the non-portable \t form is NOT what we document -------------------
# Not asserting that `\t` fails (that is grep-implementation dependent -- ugrep
# extends ERE and would match). Asserting instead that the DOCUMENTED matcher
# works under whatever grep is on PATH, which is the property acceptance needs.
assert_not_contains "T6: documented matcher carries no backslash escape" \
    '\t' "$VERDICT_MATCH_OK"

# --- T7: appends rather than truncates --------------------------------------
# The triple-run protocol counts 3 records in ONE shared log across 3 runs.
multi="$TESTROOT/multi.log"
emit localised "run one" "$multi"
emit localised "run two" "$multi"
emit undecidable "run three" "$multi"
assert_eq "T7: three runs leave three records" "3" \
    "$(wc -l < "$multi" | tr -d ' ')"
assert_eq "T7: only the localised ones satisfy acceptance" "2" \
    "$(count_match "$multi")"

# --- T8: no env var => no file (default behaviour unchanged) ----------------
absent="$TESTROOT/never.log"
"$PY" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from tests.test_board_movement import _emit_verdict
_emit_verdict('localised', 'no log configured')
" 2>/dev/null
assert_file_not_exists "T8: unset env var writes no log" "$absent"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
