#!/usr/bin/env bash
# test_python_runner_exit_status.sh — the Python runner's result contract (t1179).
#
# `tests/run_all_python_tests.sh` never printed a false summary, but it made a
# failing run READ as green: six script-style test modules print their own
# `Results: N passed, 0 failed` tallies to stdout while the framework verdict
# goes to stderr, and CPython block-buffers stdout when redirected — so those
# green lines flushed at exit, BELOW `FAILED`. Anyone reading the tail (or
# piping through `tail`, which also discards the exit status) concluded the
# suite was green. t1179 made the true verdict the unmissable last line.
#
# This file pins that contract:
#   * a failing suite exits non-zero and ends with `PYTHON SUITE: FAILED`
#   * a passing suite exits 0 and ends with `PYTHON SUITE: PASSED`
#   * the banner is literally the LAST line of `2>&1` output
#   * a module's own tally appears ABOVE the framework verdict (PYTHONUNBUFFERED)
#   * `--test-dir` consumes exactly its own two arguments and forwards the rest
#   * the verdict/exit path behaves identically on BOTH backends
#
# Backend determinism without touching PYTHONPATH (t1236 forbids that — see
# test_runner_python_isolation.sh): CPython puts the CURRENT WORKING DIRECTORY
# on sys.path for both `-c` and `-m`, so the runner's `import pytest` probe and
# its `-m pytest` dispatch can both be steered by choosing the cwd we invoke it
# from. Two shim dirs do that:
#   * $CWD_UNITTEST holds a `pytest` package whose __init__ raises ImportError,
#     so the probe fails and the unittest branch runs — even on a machine that
#     has real pytest installed.
#   * $CWD_PYTEST holds a stub `pytest` package that records its argv and exits
#     with a chosen code, so the pytest branch runs — even on a machine with no
#     pytest at all (none of the interpreters here have it).
#
# Scope boundary, stated rather than implied: the stub proves the pytest
# branch's DISPATCH, ARGUMENT CONSTRUCTION and VERDICT PROPAGATION. It does not
# simulate pytest's own collection or reporting semantics, and nothing here
# claims it does.
#
# Run: bash tests/test_python_runner_exit_status.sh
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

# --- interpreter availability ----------------------------------------------
# Skip rather than fail: a checkout without the aitask venv cannot exercise the
# runner at all, and a red test there would be noise, not signal.
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
if ! source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; then
    echo "SKIP: .aitask-scripts/lib/python_resolve.sh not sourceable"
    exit 0
fi
if ! PY="$(require_ait_python 2>/dev/null)" || [[ -z "$PY" ]]; then
    echo "SKIP: no aitask python interpreter available"
    exit 0
fi

# --- fixture modules -------------------------------------------------------

write_failing() {
    cat > "$1/test_aa_failing.py" <<'PY'
import unittest


class FailingTests(unittest.TestCase):
    def test_fails(self):
        self.assertEqual(1, 2)
PY
}

# Passes under the framework AND prints its own green tally to stdout — the
# shape of the six real script-style modules that buried the verdict.
write_script_style() {
    cat > "$1/test_zz_script_style.py" <<'PY'
import unittest

print("Results: 3 passed, 0 failed")


class ScriptStyleTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(1, 1)
PY
}

# A collection error — a different failure channel from a failed assertion.
write_broken_import() {
    cat > "$1/test_bb_broken_import.py" <<'PY'
import definitely_not_a_module  # noqa: F401
import unittest


class NeverRunTests(unittest.TestCase):
    def test_never(self):
        pass
PY
}

# Records what PYTHONPATH the test process actually saw (t1236 guard, locally).
write_env_probe() {
    cat > "$1/test_cc_env_probe.py" <<'PY'
import os
import unittest

with open(os.environ["ENV_PROBE_FILE"], "w") as fh:
    fh.write(repr(os.environ.get("PYTHONPATH")))


class EnvProbeTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(1, 1)
PY
}

new_dir() {
    local d="$TMP/$1"
    mkdir -p "$d"
    echo "$d"
}

FIX_GREEN="$(new_dir fix_green)"
write_script_style "$FIX_GREEN"

FIX_FAIL="$(new_dir fix_fail)"
write_failing "$FIX_FAIL"
write_script_style "$FIX_FAIL"

FIX_IMPORT="$(new_dir fix_import)"
write_broken_import "$FIX_IMPORT"

FIX_ENV="$(new_dir fix_env)"
write_env_probe "$FIX_ENV"

# --- backend shims (cwd-resolved; PYTHONPATH is never involved) -------------

CWD_UNITTEST="$(new_dir cwd_unittest)"
mkdir -p "$CWD_UNITTEST/pytest"
cat > "$CWD_UNITTEST/pytest/__init__.py" <<'PY'
raise ImportError("pytest deliberately blocked by test fixture")
PY

CWD_PYTEST="$(new_dir cwd_pytest)"
mkdir -p "$CWD_PYTEST/pytest"
: > "$CWD_PYTEST/pytest/__init__.py"

# The stub pytest body, shared by the no-xdist and with-xdist shim dirs.
#
# STUB_ARGV_FILE is overwritten per invocation (last one wins), which is what
# the single-phase tests below read. STUB_ARGV_LOG, when set, additionally
# APPENDS one `===PHASE===` record per invocation, so the two-phase parallel
# lane can be inspected phase by phase. The per-phase exit code is STUB_RC for
# the first invocation and STUB_RC<n> for the nth — without which a test could
# not tell "pool failed, carve-out clean" from the reverse.
write_stub_pytest() {
    cat > "$1/pytest/__main__.py" <<'PY'
import os
import sys

args = sys.argv[1:]
log = os.environ.get("STUB_ARGV_LOG")

# Count BEFORE appending, so `n` is this invocation's 0-based index.
n = 0
if log and os.path.exists(log):
    with open(log) as fh:
        n = fh.read().count("===PHASE===")

with open(os.environ["STUB_ARGV_FILE"], "w") as fh:
    fh.write("\n".join(args))
if log:
    with open(log, "a") as fh:
        fh.write("===PHASE===\n" + "\n".join(args) + "\n")

print("stub pytest ran")
rc = os.environ.get("STUB_RC" if n == 0 else "STUB_RC%d" % (n + 1))
if rc is None:
    rc = os.environ.get("STUB_RC", "0")
sys.exit(int(rc))
PY
}
write_stub_pytest "$CWD_PYTEST"

# xdist deliberately BLOCKED here, mirroring the pytest block in $CWD_UNITTEST,
# so the "flags absent" assertions below rest on something WE control.
#
# Honest scope note (measured, not assumed): removing this shim does not
# currently turn the tests red. Real `xdist/__init__.py` executes
# `@pytest.hookimpl` at import time, which raises AttributeError against the
# stub `pytest` package sitting in this same cwd — so the runner's
# `import xdist` probe fails either way today, and the branch happens to be
# taken for a reason that lives in xdist's import graph rather than here.
# The shim is kept because that accident is not a contract: an xdist release
# with a lazier __init__ would make `import xdist` succeed from this cwd, and
# the "flags absent" assertions would silently become machine-dependent —
# passing on a clean checkout, failing wherever `ait setup --with-dev` has run.
mkdir -p "$CWD_PYTEST/xdist"
cat > "$CWD_PYTEST/xdist/__init__.py" <<'PY'
raise ImportError("xdist deliberately blocked by test fixture")
PY

# The parallel lane: stub pytest AND an importable xdist, so the runner takes
# its `-n <workers> --dist loadfile` branch regardless of what is installed.
CWD_PYTEST_XDIST="$(new_dir cwd_pytest_xdist)"
mkdir -p "$CWD_PYTEST_XDIST/pytest" "$CWD_PYTEST_XDIST/xdist"
: > "$CWD_PYTEST_XDIST/pytest/__init__.py"
: > "$CWD_PYTEST_XDIST/xdist/__init__.py"
write_stub_pytest "$CWD_PYTEST_XDIST"

# Carve-out fixture: the serially-carved module plus one ordinary module, so the
# partition has something to put in each phase.
FIX_CARVE="$(new_dir fix_carve)"
write_script_style "$FIX_CARVE"
cat > "$FIX_CARVE/test_board_header_row_live.py" <<'PY'
import unittest


class CarvedTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(1, 1)
PY

STUB_ARGV="$TMP/stub_argv.txt"
STUB_LOG="$TMP/stub_argv_log.txt"
ENV_PROBE="$TMP/env_probe.txt"

# Read the nth (1-based) `===PHASE===` record from the stub log as a
# newline-joined argv vector.
phase_argv() {
    "$PY" - "$STUB_LOG" "$1" <<'PY'
import sys

path, want = sys.argv[1], int(sys.argv[2])
try:
    with open(path) as fh:
        blocks = fh.read().split("===PHASE===\n")[1:]
except FileNotFoundError:
    blocks = []
print(blocks[want - 1].rstrip("\n") if len(blocks) >= want else "", end="")
PY
}

phase_count() {
    grep -c '===PHASE===' "$STUB_LOG" 2>/dev/null || echo 0
}

# The expected parallel-lane argv for a single-file fixture, as an EXACT vector.
#
# Compared with assert_eq, never assert_contains: `grep -F` splits a multi-line
# pattern into one alternative PER LINE, so a needle like "-n\n4" matches any
# haystack merely containing "-n" — it would pass against `-n 2` and prove
# nothing. Exact comparison is the only form that actually pins the value.
lane_vector() {  # lane_vector <test-file> <workers>
    printf '%s\n-v\n-n\n%s\n--dist\nloadfile' "$1" "$2"
}

# --- helpers ---------------------------------------------------------------

OUT=""
RC=0

# run_from <cwd> <fixture-dir> [extra args forwarded to the backend...]
run_from() {
    local cwd="$1" fix="$2"
    shift 2
    OUT="$(cd "$cwd" && bash "$RUNNER" --test-dir "$fix" "$@" 2>&1)"
    RC=$?
}

last_line() { printf '%s\n' "$1" | tail -n1; }

# Line number of the first line containing <needle>, or empty.
line_of() { printf '%s\n' "$2" | grep -nF -- "$1" | head -n1 | cut -d: -f1; }

# --- Tests: unittest backend -----------------------------------------------

test_unittest_green_passes() {
    run_from "$CWD_UNITTEST" "$FIX_GREEN"
    assert_exit_zero_rc "unittest: green fixture exits 0" "$RC"
    assert_contains "unittest: green fixture reports PASSED" \
        "PYTHON SUITE: PASSED" "$OUT"
    assert_contains "unittest: banner names the unittest backend" \
        "runner=unittest, exit=0" "$OUT"
}

test_unittest_failure_is_non_zero() {
    run_from "$CWD_UNITTEST" "$FIX_FAIL"
    assert_exit_nonzero_rc "unittest: failing fixture exits non-zero" "$RC"
    assert_contains "unittest: failing fixture reports FAILED" \
        "PYTHON SUITE: FAILED" "$OUT"
    assert_not_contains "unittest: failing fixture never reports PASSED" \
        "PYTHON SUITE: PASSED" "$OUT"
}

test_unittest_import_error_is_non_zero() {
    run_from "$CWD_UNITTEST" "$FIX_IMPORT"
    assert_exit_nonzero_rc "unittest: collection error exits non-zero" "$RC"
    assert_contains "unittest: collection error reports FAILED" \
        "PYTHON SUITE: FAILED" "$OUT"
}

# The direct regression guard for the reported symptom: a tail-reader must see
# the verdict, not a module's own green tally.
test_verdict_is_the_last_line() {
    run_from "$CWD_UNITTEST" "$FIX_FAIL"
    local last
    last="$(last_line "$OUT")"
    assert_contains "failing run: last line is the verdict banner" \
        "PYTHON SUITE: FAILED" "$last"
    assert_not_contains "failing run: last line is not a module tally" \
        "Results: 3 passed" "$last"

    run_from "$CWD_UNITTEST" "$FIX_GREEN"
    assert_contains "passing run: last line is the verdict banner" \
        "PYTHON SUITE: PASSED" "$(last_line "$OUT")"
}

# Pins PYTHONUNBUFFERED=1: without it the module's stdout tally flushes at exit,
# i.e. BELOW the framework's stderr `FAILED`.
test_module_tally_precedes_the_framework_verdict() {
    run_from "$CWD_UNITTEST" "$FIX_FAIL"
    local tally_at verdict_at
    tally_at="$(line_of 'Results: 3 passed, 0 failed' "$OUT")"
    verdict_at="$(line_of 'FAILED (' "$OUT")"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$tally_at" && -n "$verdict_at" && "$tally_at" -lt "$verdict_at" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: module tally must precede the framework verdict" \
             "(tally line '$tally_at', verdict line '$verdict_at')"
    fi
}

# --test-dir must consume exactly its own two arguments. `-p` is last-wins under
# `unittest discover`, so forwarding it narrows the run to the passing module;
# the unfiltered run above is the other half of the pair.
#
# Which assertion catches which mis-shift (measured, not assumed):
#   * consuming THREE args — `shift 3` with only two present aborts under
#     `set -e`, so this and most other cases in this file go red at once.
#   * consuming ONE arg — the directory leaks into the forwarded args. This
#     assertion does NOT catch it: `unittest discover` takes `start` as its
#     first positional, and the leaked value IS the same directory the runner
#     already passed via `-s`, so behaviour is unchanged. The pytest-stub argv
#     assertion below is what catches it — it compares the forwarded vector
#     exactly, and a leaked `<dir>` shows up between `-v` and `-k`.
test_unittest_forwards_remaining_arguments() {
    run_from "$CWD_UNITTEST" "$FIX_FAIL" -p 'test_zz_*.py'
    assert_exit_zero_rc "unittest: forwarded -p narrows the run to the passing module" "$RC"
    assert_contains "unittest: narrowed run reports PASSED" \
        "PYTHON SUITE: PASSED" "$OUT"
}

# --- Tests: pytest backend (stub) ------------------------------------------

test_pytest_backend_is_selected_and_zero_passes() {
    rm -f "$STUB_ARGV"
    OUT="$(cd "$CWD_PYTEST" && STUB_ARGV_FILE="$STUB_ARGV" STUB_RC=0 \
        bash "$RUNNER" --test-dir "$FIX_GREEN" 2>&1)"
    RC=$?
    assert_exit_zero_rc "pytest: backend exit 0 propagates" "$RC"
    assert_contains "pytest: banner names the pytest backend" \
        "PYTHON SUITE: PASSED (runner=pytest, exit=0)" "$OUT"
    assert_contains "pytest: the stub actually ran" "stub pytest ran" "$OUT"
}

test_pytest_backend_failure_propagates() {
    rm -f "$STUB_ARGV"
    OUT="$(cd "$CWD_PYTEST" && STUB_ARGV_FILE="$STUB_ARGV" STUB_RC=3 \
        bash "$RUNNER" --test-dir "$FIX_GREEN" 2>&1)"
    RC=$?
    assert_eq "pytest: backend exit code is propagated verbatim" "3" "$RC"
    assert_contains "pytest: non-zero backend reports FAILED" \
        "PYTHON SUITE: FAILED (runner=pytest, exit=3)" "$OUT"
    assert_not_contains "pytest: failing backend never reports PASSED" \
        "PYTHON SUITE: PASSED" "$OUT"
    assert_contains "pytest: verdict is the last line" \
        "PYTHON SUITE: FAILED" "$(last_line "$OUT")"
}

test_pytest_receives_the_expected_argv() {
    rm -f "$STUB_ARGV"
    OUT="$(cd "$CWD_PYTEST" && STUB_ARGV_FILE="$STUB_ARGV" STUB_RC=0 \
        bash "$RUNNER" --test-dir "$FIX_GREEN" -k smoke 2>&1)"
    RC=$?
    local expected
    expected="$(printf '%s\n%s\n%s\n%s' \
        "$FIX_GREEN/test_zz_script_style.py" "-v" "-k" "smoke")"
    assert_eq "pytest: argv is <fixture globs> -v <forwarded args>" \
        "$expected" "$(cat "$STUB_ARGV" 2>/dev/null)"
}

# --- Tests: the pytest-xdist parallel lane (t1354_3) -----------------------

# run_lane <cwd> <fixture-dir> [env assignments...] -- [extra args...]
# Resets the phase log, runs the runner, leaves OUT/RC set.
run_lane() {
    local cwd="$1" fix="$2"
    shift 2
    rm -f "$STUB_ARGV" "$STUB_LOG"
    OUT="$(cd "$cwd" && env STUB_ARGV_FILE="$STUB_ARGV" STUB_ARGV_LOG="$STUB_LOG" "$@" \
        bash "$RUNNER" --test-dir "$fix" 2>&1)"
    RC=$?
}

# The lane's flags, pinned as an EXACT vector. `--dist loadfile` is the
# load-bearing half: the default `--dist load` splits one file's tests across
# workers, which breaks the ~39 modules that chdir the process. `-n 2` is pinned
# too, so a regression back to `-n auto` — which would hand the whole machine to
# one suite run — fails here rather than in production.
test_lane_argv_is_bounded_and_loadfile() {
    run_lane "$CWD_PYTEST_XDIST" "$FIX_GREEN" STUB_RC=0
    assert_exit_zero_rc "lane: green fixture exits 0" "$RC"
    assert_eq "lane: argv is <globs> -v -n 2 --dist loadfile" \
        "$(lane_vector "$FIX_GREEN/test_zz_script_style.py" 2)" "$(phase_argv 1)"
    assert_contains "lane: announces itself on stderr" \
        "parallel lane: -n 2 --dist loadfile" "$OUT"
    assert_contains "lane: banner still names runner=pytest (t1179 contract)" \
        "PYTHON SUITE: PASSED (runner=pytest, exit=0)" "$OUT"
}

# The no-xdist branch must be flag-free — and deterministically so, which is
# what the blocking xdist shim in $CWD_PYTEST buys.
test_no_xdist_means_no_lane_flags() {
    run_lane "$CWD_PYTEST" "$FIX_GREEN" STUB_RC=0
    local argv
    argv="$(phase_argv 1)"
    assert_not_contains "no xdist: -n absent" "-n" "$argv"
    assert_not_contains "no xdist: --dist absent" "--dist" "$argv"
    assert_not_contains "no xdist: no lane announcement" "parallel lane:" "$OUT"
}

test_worker_count_is_overridable() {
    run_lane "$CWD_PYTEST_XDIST" "$FIX_GREEN" STUB_RC=0 AIT_TEST_WORKERS=4
    assert_eq "AIT_TEST_WORKERS=4 yields -n 4" \
        "$(lane_vector "$FIX_GREEN/test_zz_script_style.py" 4)" "$(phase_argv 1)"
}

# A malformed override must not reach pytest as a bare token. Asserted as an
# exact vector: it pins BOTH that the value is 2 and that `x` never appears.
test_malformed_worker_count_falls_back() {
    run_lane "$CWD_PYTEST_XDIST" "$FIX_GREEN" STUB_RC=0 AIT_TEST_WORKERS=x
    assert_eq "malformed AIT_TEST_WORKERS falls back to exactly -n 2" \
        "$(lane_vector "$FIX_GREEN/test_zz_script_style.py" 2)" "$(phase_argv 1)"
    assert_contains "malformed AIT_TEST_WORKERS warns" \
        "is not a positive integer" "$OUT"
}

test_parallel_opt_out_restores_serial_vector() {
    run_lane "$CWD_PYTEST_XDIST" "$FIX_GREEN" STUB_RC=0 AIT_TEST_PARALLEL=0
    local argv
    argv="$(phase_argv 1)"
    assert_eq "AIT_TEST_PARALLEL=0 restores the plain serial vector" \
        "$(printf '%s\n-v' "$FIX_GREEN/test_zz_script_style.py")" "$argv"
    assert_eq "AIT_TEST_PARALLEL=0 runs exactly one phase" "1" "$(phase_count)"
}

# The carve-out: the real-board module leaves the pool and gets its own serial
# invocation — without the lane flags, and exactly once.
test_carve_out_splits_into_two_phases() {
    run_lane "$CWD_PYTEST_XDIST" "$FIX_CARVE" STUB_RC=0
    assert_eq "carve-out: two phases ran" "2" "$(phase_count)"

    local pool serial
    pool="$(phase_argv 1)"
    serial="$(phase_argv 2)"

    assert_not_contains "carve-out: pool excludes the carved module" \
        "test_board_header_row_live.py" "$pool"
    assert_contains "carve-out: pool keeps the ordinary module" \
        "test_zz_script_style.py" "$pool"
    assert_contains "carve-out: pool is parallel" "--dist" "$pool"

    assert_contains "carve-out: serial phase gets the carved module" \
        "test_board_header_row_live.py" "$serial"
    assert_not_contains "carve-out: serial phase carries no other module" \
        "test_zz_script_style.py" "$serial"
    assert_not_contains "carve-out: serial phase is NOT parallel" "--dist" "$serial"
}

# Both failure directions, because a two-phase run has two ways to hide a red.
test_pool_failure_is_not_masked_by_clean_carve_out() {
    run_lane "$CWD_PYTEST_XDIST" "$FIX_CARVE" STUB_RC=1 STUB_RC2=0
    assert_exit_nonzero_rc "pool failure propagates" "$RC"
    assert_contains "pool failure reports FAILED" "PYTHON SUITE: FAILED" "$OUT"
    assert_not_contains "pool failure never reports PASSED" \
        "PYTHON SUITE: PASSED" "$OUT"
}

test_carve_out_failure_is_not_masked_by_clean_pool() {
    run_lane "$CWD_PYTEST_XDIST" "$FIX_CARVE" STUB_RC=0 STUB_RC2=1
    assert_exit_nonzero_rc "carve-out failure propagates" "$RC"
    assert_contains "carve-out failure reports FAILED" "PYTHON SUITE: FAILED" "$OUT"
    assert_not_contains "carve-out failure never reports PASSED" \
        "PYTHON SUITE: PASSED" "$OUT"
}

# A forwarded path selector would re-add the carved module to the pool AND run
# it again serially, so the lane must switch itself off instead.
test_forwarded_path_selector_disables_the_lane() {
    rm -f "$STUB_ARGV" "$STUB_LOG"
    OUT="$(cd "$CWD_PYTEST_XDIST" && STUB_ARGV_FILE="$STUB_ARGV" STUB_ARGV_LOG="$STUB_LOG" STUB_RC=0 \
        bash "$RUNNER" --test-dir "$FIX_CARVE" "$FIX_CARVE/test_board_header_row_live.py" 2>&1)"
    RC=$?
    assert_eq "path selector: exactly one phase runs" "1" "$(phase_count)"
    assert_not_contains "path selector: lane flags absent" "--dist" "$(phase_argv 1)"
    assert_contains "path selector: the reason is reported" \
        "parallel lane disabled" "$OUT"
}

# An empty partition must be SKIPPED, never invoked with no files — pytest with
# no path argument collects the current directory instead.
test_carve_out_only_subset_runs_one_phase() {
    local only_carved
    only_carved="$(new_dir fix_only_carved)"
    cat > "$only_carved/test_board_header_row_live.py" <<'PY'
import unittest


class CarvedOnlyTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(1, 1)
PY
    run_lane "$CWD_PYTEST_XDIST" "$only_carved" STUB_RC=0
    assert_eq "carved-only subset: exactly one phase runs" "1" "$(phase_count)"
    assert_contains "carved-only subset: it is the carved module" \
        "test_board_header_row_live.py" "$(phase_argv 1)"
    assert_not_contains "carved-only subset: no empty parallel phase" \
        "--dist" "$(phase_argv 1)"
    assert_exit_zero_rc "carved-only subset exits 0" "$RC"
}

# --- Test: the neighbouring t1236 contract still holds ---------------------

test_caller_pythonpath_is_still_scrubbed() {
    rm -f "$ENV_PROBE"
    OUT="$(cd "$CWD_UNITTEST" && PYTHONPATH="$TMP/should-not-leak" \
        ENV_PROBE_FILE="$ENV_PROBE" bash "$RUNNER" --test-dir "$FIX_ENV" 2>&1)"
    RC=$?
    assert_exit_zero_rc "env probe fixture passes" "$RC"
    assert_eq "caller PYTHONPATH is scrubbed before the tests run (t1236)" \
        "None" "$(cat "$ENV_PROBE" 2>/dev/null)"
}

# --- Run ---
test_unittest_green_passes
test_unittest_failure_is_non_zero
test_unittest_import_error_is_non_zero
test_verdict_is_the_last_line
test_module_tally_precedes_the_framework_verdict
test_unittest_forwards_remaining_arguments
test_pytest_backend_is_selected_and_zero_passes
test_pytest_backend_failure_propagates
test_pytest_receives_the_expected_argv
test_lane_argv_is_bounded_and_loadfile
test_no_xdist_means_no_lane_flags
test_worker_count_is_overridable
test_malformed_worker_count_falls_back
test_parallel_opt_out_restores_serial_vector
test_carve_out_splits_into_two_phases
test_pool_failure_is_not_masked_by_clean_carve_out
test_carve_out_failure_is_not_masked_by_clean_pool
test_forwarded_path_selector_disables_the_lane
test_carve_out_only_subset_runs_one_phase
test_caller_pythonpath_is_still_scrubbed

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
