#!/usr/bin/env bash
# run_all_python_tests.sh - Run all Python unit tests
# Run: bash tests/run_all_python_tests.sh
#      bash tests/run_all_python_tests.sh --test-dir <dir>   # a fixture subset
#
# `--test-dir <dir>` is honoured ONLY as the first argument; it is consumed here
# and every remaining argument forwards verbatim to pytest / unittest.
#
# Reading the result (t1179): the LAST line of output is always
#     PYTHON SUITE: PASSED|FAILED (runner=<backend>, exit=<n>)
# and it is derived from the backend's real exit status. Trust nothing else — a
# `Results: N passed, 0 failed` line earlier in the output belongs to ONE
# script-style test module, not to the suite.
#
# Caveat this script cannot fix: piping discards its status.
#     bash tests/run_all_python_tests.sh 2>&1 | tail -40   # exits with tail's 0
# Use `set -o pipefail` or check `${PIPESTATUS[0]}` in the caller. The verdict
# banner goes to stderr so the truth survives `2>&1 | tail` even when the exit
# status does not.
#
# Parallel lane (t1354_3). When pytest AND pytest-xdist are both importable —
# the opt-in dev tier, `ait setup --with-dev` — the pytest branch runs
# `-n <workers> --dist loadfile` over every module except a small serial
# carve-out, then runs the carve-out by itself, and combines the two exit
# statuses. `--dist loadfile` is MANDATORY, not a preference: ~39 modules chdir
# the process (directly or through tests/lib/board_fixture.py), and the default
# `--dist load` splits one file's tests across workers, which would break them.
#
#   AIT_TEST_PARALLEL=0   force the serial pytest path (execution opt-out)
#   AIT_TEST_WORKERS=<n>  worker count; default 2, NOT `auto`. `auto` means
#                         os.cpu_count(), which hands the whole machine to one
#                         suite run and starves anything else running on it.
#
# The unittest fallback is unchanged and remains the supported path for anyone
# who has not opted in. The verdict banner still reads `runner=pytest` in both
# pytest lanes — the t1179 contract above pins that string.
#
# INVOCATION POLICY, NOT A GUARANTEE: do not run this suite concurrently with
# `tests/*.sh`, which owns the real git index. Nothing here enforces that —
# there is no shared lock, so a second developer or a CI job can still collide.
# This hazard is pre-existing and is neither created nor widened by the parallel
# lane: the one module that touches the real index is carved into a serial phase
# either way.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TEST_DIR="$SCRIPT_DIR"
if [[ "${1:-}" == "--test-dir" ]]; then
    [[ -n "${2:-}" ]] || { echo "--test-dir needs a directory" >&2; exit 2; }
    TEST_DIR="$2"
    shift 2
fi

# Resolve the framework interpreter (prefers the aitask venv, which has the
# board/TUI third-party deps) instead of bare python3, which may be a system
# interpreter lacking yaml/textual/rich (t935).
# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PY="$(require_ait_python)"

# Do NOT seed PYTHONPATH (t1236). Every test file bootstraps its own sys.path
# from __file__; a runner-supplied path makes a wrong bootstrap pass here and
# fail only at TUI runtime. Any inherited value is scrubbed too, so the suite
# behaves identically regardless of the caller's environment.
unset PYTHONPATH
export PYTHONDONTWRITEBYTECODE=1
# Unbuffered stdout (t1179): a module's own print() output is block-buffered
# when redirected and would otherwise flush at exit — i.e. BELOW the framework's
# stderr verdict, making a failed run read as green from the tail.
export PYTHONUNBUFFERED=1

# Serial carve-out: modules that must NOT run inside the parallel pool.
# test_board_header_row_live.py boots the real `ait board` in a tmux pane against
# the real repo — taking .git/index.lock via `git status --porcelain -- aitasks/`
# — under a 45s boot budget that FAILS rather than skips. Under a loaded worker
# pool that budget becomes a flake, so it runs in its own serial phase.
# test_board_startup_focus_live.py boots the real `ait board` TWICE in a tmux
# pane, under the same wall-clock budget. It runs against its own synthetic
# project so it never touches the real .git/index.lock — but the budget half of
# the rationale above applies unchanged, so it is carved out too.
SERIAL_CARVE_OUT=(test_board_header_row_live.py test_board_startup_focus_live.py)

is_carved() {
    local base="${1##*/}" c
    for c in "${SERIAL_CARVE_OUT[@]}"; do
        [[ "$base" == "$c" ]] && return 0
    done
    return 1
}

# A forwarded path selector makes the carve-out partition a lie: "$@" is
# appended to EVERY phase, so a positional `.../test_board_header_row_live.py`
# would re-enter the parallel pool AND run again serially, losing exactly the
# protection the carve-out exists to give. The forwarded vector cannot be
# partitioned reliably — nothing here can tell the value `smoke` in `-k smoke`
# from a bare selector without re-implementing pytest's option grammar — so when
# one is seen the lane turns itself OFF rather than silently voiding the
# carve-out. Use --test-dir to narrow a run; it is consumed above and rebuilds
# the file list, so both partitions stay derived from one set.
has_path_selector() {
    local a
    for a in "$@"; do
        case "$a" in
            *.py|*.py::*) return 0 ;;
        esac
        [[ -e "$a" ]] && return 0
    done
    return 1
}

# Default worker count: 4 when the machine has headroom, 2 when it does not.
# Never `-n auto` — auto is os.cpu_count(), which hands the whole machine to one
# suite run, starves the other agents commonly running alongside it, and makes
# every timing a measurement of contention rather than of the suite.
#
# Measured on a 24-core box (t1354_4, one denominator, same pinned tree):
#   -n 2 → 200.1s   -n 4 → 111.3s   -n 6 → 101.0s
# N=4 is 1.80x faster than N=2 for ~10% more CPU and sits on the makespan
# crossover (total work ÷ 4 = 91.6s vs the slowest single file at 87.1s), so
# extra workers buy almost nothing past it. Taking 4 cores while the box is
# already busy would starve co-running agents, so the default steps back to 2
# under load.
#
# AIT_TEST_LOADAVG / AIT_TEST_NCPU are TEST SEAMS, not user knobs. A
# load-dependent argv would otherwise make tests/test_python_runner_exit_status.sh
# machine- and moment-dependent — the exact defect class the blocking xdist shim
# was added to remove — so the contract test injects both and drives each branch
# deterministically. Users override the result with AIT_TEST_WORKERS.
default_workers() {
    local n
    n="$("$PY" -c '
import os
try:
    raw_cpu = os.environ.get("AIT_TEST_NCPU")
    ncpu = int(raw_cpu) if raw_cpu else (os.cpu_count() or 1)
    raw = os.environ.get("AIT_TEST_LOADAVG")
    load = float(raw) if raw else os.getloadavg()[0]
except (OSError, ValueError):
    print(2)
else:
    print(4 if ncpu >= 4 and load <= ncpu / 2 else 2)
' 2>/dev/null)"
    if [[ "$n" =~ ^[1-9][0-9]*$ ]]; then printf '%s' "$n"; else printf '2'; fi
}

# Try pytest first, fall back to unittest. Choose the backend here but do not
# run it: execution, the verdict and the exit are one shared path below, so the
# result contract cannot drift between the two branches.
serial_cmd=()
if "$PY" -c "import pytest" 2>/dev/null; then
    backend=pytest
    # Expand the glob ONCE, so the parallel pool and the serial carve-out are
    # provably derived from the same set.
    files=("$TEST_DIR"/test_*.py)

    parallel=1
    # Glob matched nothing and bash left the literal: keep the pre-t1354_3
    # behaviour (pytest reports the missing path and the run fails).
    [[ ${#files[@]} -eq 1 && ! -e "${files[0]}" ]] && parallel=0
    [[ "${AIT_TEST_PARALLEL:-1}" == "0" ]] && parallel=0
    "$PY" -c "import xdist" 2>/dev/null || parallel=0
    if [[ "$parallel" -eq 1 ]] && has_path_selector "$@"; then
        echo "forwarded path selector detected — parallel lane disabled (the serial carve-out cannot be honoured for arbitrary path arguments)" >&2
        parallel=0
    fi

    # An explicit AIT_TEST_WORKERS always wins; otherwise the bounded, load-aware
    # default above decides. A malformed override falls back to that same default
    # rather than a second hard-coded constant, so "the default" has one meaning.
    workers_auto=0
    if [[ -n "${AIT_TEST_WORKERS:-}" ]]; then
        workers="$AIT_TEST_WORKERS"
        if [[ ! "$workers" =~ ^[1-9][0-9]*$ ]]; then
            workers="$(default_workers)"
            echo "AIT_TEST_WORKERS='${AIT_TEST_WORKERS}' is not a positive integer — using $workers" >&2
        fi
    else
        workers="$(default_workers)"
        workers_auto=1
    fi

    if [[ "$parallel" -eq 1 ]]; then
        pool=()
        serial=()
        for f in "${files[@]}"; do
            if is_carved "$f"; then serial+=("$f"); else pool+=("$f"); fi
        done
        echo "parallel lane: -n $workers --dist loadfile (serial carve-out: ${SERIAL_CARVE_OUT[*]})" >&2
        if [[ "$workers_auto" -eq 1 ]]; then
            echo "worker count: auto-selected -n $workers from machine load (override with AIT_TEST_WORKERS)" >&2
        fi
        # Either partition may be empty (e.g. a --test-dir subset holding neither
        # kind). An empty phase is SKIPPED, never invoked with no files: pytest
        # with no path argument collects the current directory instead.
        cmd=()
        [[ ${#pool[@]} -gt 0 ]] && cmd=("$PY" -m pytest "${pool[@]}" -v -n "$workers" --dist loadfile "$@")
        [[ ${#serial[@]} -gt 0 ]] && serial_cmd=("$PY" -m pytest "${serial[@]}" -v "$@")
    else
        cmd=("$PY" -m pytest "${files[@]}" -v "$@")
    fi
else
    backend=unittest
    echo "pytest not found, using unittest discovery"
    cmd=("$PY" -m unittest discover -s "$TEST_DIR" -p 'test_*.py' -v "$@")
fi

if [[ ${#cmd[@]} -eq 0 && ${#serial_cmd[@]} -eq 0 ]]; then
    echo "no test files selected — refusing to report a verdict for an empty run" >&2
    exit 2
fi

set +e
rc=0
if [[ ${#cmd[@]} -gt 0 ]]; then
    "${cmd[@]}"
    rc=$?
fi
if [[ ${#serial_cmd[@]} -gt 0 ]]; then
    "${serial_cmd[@]}"
    serial_rc=$?
    # A phase-1 failure is never masked by a clean phase 2.
    [[ "$rc" -eq 0 ]] && rc=$serial_rc
fi
set -e

if [ "$rc" -eq 0 ]; then
    echo "PYTHON SUITE: PASSED (runner=$backend, exit=$rc)" >&2
else
    echo "PYTHON SUITE: FAILED (runner=$backend, exit=$rc)" >&2
fi
exit "$rc"
