#!/usr/bin/env bash
# test_runner_python_isolation.sh — PYTHONPATH isolation guard for the Python
# test runner (t1236).
#
# `tests/run_all_python_tests.sh` used to export
#     PYTHONPATH="<repo>/.aitask-scripts/board:<repo>/.aitask-scripts/lib:$PYTHONPATH"
# before invoking pytest / unittest. Every Python test file already bootstraps
# its own `sys.path` from `__file__`, so that export was pure convenience — and
# it MASKED broken bootstraps: a test whose own `sys.path.insert` named the
# wrong directory still imported fine under the runner and failed only at TUI
# runtime (t1217 recorded this as a code-health risk and defended it with a
# manual `env -u PYTHONPATH` check, which only works while someone remembers).
#
# t1236 replaced the export with `unset PYTHONPATH`, which also scrubs a value
# inherited from the caller's environment — the same masking, one shell up.
# This test FAILS if either half of that regresses.
#
# Detection scope (documented on purpose — a guard that overclaims is worse than
# one with a known boundary):
#   * Scanned: `tests/run_all_python_tests.sh` only. Individual shell tests that
#     set PYTHONPATH per `python -c` invocation (test_crew_report.sh,
#     test_tmux_control.sh, …) are deliberate per-command setups, not a shared
#     masking lane, and are out of scope.
#   * Detected: any `PYTHONPATH=` assignment or export on a non-comment line,
#     and a missing `unset PYTHONPATH`.
#   * NOT detected: PYTHONPATH set indirectly — through a variable whose name is
#     built at runtime, an `env`/`declare` indirection, or a sourced helper.
#
# Run: bash tests/test_runner_python_isolation.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

RUNNER="$PROJECT_DIR/tests/run_all_python_tests.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- The checker -----------------------------------------------------------
# Prints one reason line per violation and returns non-zero if any were found.
# Takes the file as an argument so the negative controls below can run the SAME
# code against a deliberately broken copy — a guard that is only ever pointed at
# the healthy file proves nothing.
check_runner() {
  local file="$1"
  local body rc=0

  # Drop whole-line comments so the explanatory header (which necessarily says
  # "PYTHONPATH") cannot trip the assignment check.
  body="$(grep -vE '^[[:space:]]*#' -- "$file")"

  if printf '%s\n' "$body" | grep -qE '(^|[^A-Za-z_])PYTHONPATH='; then
    echo "VIOLATION:seeds-pythonpath"
    rc=1
  fi

  if ! printf '%s\n' "$body" | grep -qE '^[[:space:]]*unset[[:space:]]+PYTHONPATH[[:space:]]*$'; then
    echo "VIOLATION:missing-unset"
    rc=1
  fi

  return "$rc"
}

# --- Test 1: the live runner is isolated -----------------------------------
assert_file_exists "runner exists" "$RUNNER"

live_out="$(check_runner "$RUNNER")"
live_rc=$?
assert_exit_zero_rc "run_all_python_tests.sh does not seed PYTHONPATH and unsets it" "$live_rc"
assert_eq "live runner reports no violations" "" "$live_out"

# --- Test 2 (negative control): re-adding the export IS flagged ------------
# A PASSING negative control here would mean the checker is not actually
# looking at the file.
cp "$RUNNER" "$TMP/with_export.sh"
cat >>"$TMP/with_export.sh" <<'SH'
export PYTHONPATH="$PROJECT_DIR/.aitask-scripts/board:$PROJECT_DIR/.aitask-scripts/lib${PYTHONPATH:+:$PYTHONPATH}"
SH
neg_export="$(check_runner "$TMP/with_export.sh")"
neg_export_rc=$?
assert_exit_nonzero_rc "negative control: a re-added PYTHONPATH export is rejected" "$neg_export_rc"
assert_contains "negative control names the seeding violation" \
  "VIOLATION:seeds-pythonpath" "$neg_export"

# --- Test 3 (negative control): dropping the unset IS flagged --------------
# The other half of the contract: merely *not adding* to PYTHONPATH still lets
# an inherited value through, so the scrub itself must be pinned.
grep -vE '^[[:space:]]*unset[[:space:]]+PYTHONPATH[[:space:]]*$' -- "$RUNNER" \
  >"$TMP/without_unset.sh"
neg_unset="$(check_runner "$TMP/without_unset.sh")"
neg_unset_rc=$?
assert_exit_nonzero_rc "negative control: a runner missing 'unset PYTHONPATH' is rejected" "$neg_unset_rc"
assert_contains "negative control names the missing-unset violation" \
  "VIOLATION:missing-unset" "$neg_unset"

# --- Test 4: a bare comment mentioning PYTHONPATH does not trip the guard ---
# The runner's own header explains why the export is gone; that prose must not
# read as a violation.
cp "$RUNNER" "$TMP/commented.sh"
cat >>"$TMP/commented.sh" <<'SH'
# export PYTHONPATH="/somewhere"   <- a comment must NOT trip the guard
SH
comment_out="$(check_runner "$TMP/commented.sh")"
comment_rc=$?
assert_exit_zero_rc "a commented-out export does not trip the guard" "$comment_rc"
assert_eq "commented-out export reports no violations" "" "$comment_out"

# --- Summary ---------------------------------------------------------------
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
