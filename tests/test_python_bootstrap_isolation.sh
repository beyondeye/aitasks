#!/usr/bin/env bash
# test_python_bootstrap_isolation.sh — every Python test file must bootstrap its
# own sys.path (t1236).
#
# `tests/run_all_python_tests.sh` no longer seeds PYTHONPATH, which removes the
# RUNNER-level masking of a wrong `sys.path.insert`. It does not remove the
# INTRA-PROCESS masking: pytest and `unittest discover` both import all 150+
# `tests/test_*.py` into one interpreter sharing one `sys.path`, so the first
# module that inserts `.aitask-scripts/lib` fixes the path for every module
# imported after it. Measured on the live tree: breaking the alphabetically
# first test's bootstrap fails the runner, but breaking the identical bootstrap
# in `tests/test_tmux_exec.py` still passes.
#
# This lane closes that hole: each test file is imported in its OWN interpreter
# with PYTHONPATH scrubbed, so its bootstrap is exercised exactly as shipped.
# Importing is the whole check — the bootstrap and the top-level imports both
# run at module-exec time. Test bodies are not executed (that is the runner's
# job), which is why the whole sweep costs seconds, not minutes.
#
# Scope boundary (stated rather than implied): this proves each file can be
# imported standalone. It says nothing about a path a test computes lazily
# inside a test body, or one a spawned subprocess needs.
#
# Layout assumption: the driver loads each file as a top-level module named
# after its file stem, which is what `unittest discover` and pytest's prepend
# import mode do for a FLAT, non-package `tests/`. Test 5 below is the tripwire
# for the day that stops being true.
#
# Run: bash tests/test_python_bootstrap_isolation.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PY="$(require_ait_python)"

DRIVER="$PROJECT_DIR/tests/lib/import_isolated.py"

PASS=0
FAIL=0
TOTAL=0

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Import one file in a fresh, PYTHONPATH-free interpreter.
import_isolated() {
  env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 "$PY" "$DRIVER" "$1" 2>&1
}

# --- Test 1: every test file imports standalone ----------------------------
broken=""
count=0
for f in "$PROJECT_DIR"/tests/test_*.py; do
  count=$((count + 1))
  if ! import_isolated "$f" >/dev/null 2>&1; then
    broken="$broken
  $(basename -- "$f")"
  fi
done

assert_eq "the sweep found test files to check" "yes" \
  "$([ "$count" -gt 0 ] && echo yes || echo no)"
assert_eq "every tests/test_*.py imports with its own sys.path bootstrap" "" "$broken"

if [[ -n "$broken" ]]; then
  echo "Files whose own sys.path bootstrap is incomplete (they were passing only"
  echo "because another test module put the directory on sys.path first):$broken"
  echo "Reproduce one with:"
  echo "  env -u PYTHONPATH python3 tests/lib/import_isolated.py tests/<file>.py"
fi

# --- Test 2 (positive control): a correct bootstrap is accepted -------------
# Guards against the sweep passing because the driver never really imports.
cat >"$TMP/test_negctrl_good.py" <<PY
import sys

sys.path.insert(0, "$PROJECT_DIR/.aitask-scripts/lib")
from task_yaml import parse_frontmatter  # noqa: E402,F401
PY
good_out="$(import_isolated "$TMP/test_negctrl_good.py")"
good_rc=$?
assert_exit_zero_rc "positive control: a correct lib bootstrap imports cleanly" "$good_rc"
assert_eq "positive control produces no error output" "" "$good_out"

# --- Test 3 (negative control): a broken bootstrap IS rejected -------------
# Identical to the fixture above except the directory name. A PASSING negative
# control would mean this lane cannot detect the very thing it exists for.
sed 's#/lib"#/lib_BROKEN_NEGCTRL"#' "$TMP/test_negctrl_good.py" \
  >"$TMP/test_negctrl_bad.py"
bad_out="$(import_isolated "$TMP/test_negctrl_bad.py")"
bad_rc=$?
assert_exit_nonzero_rc "negative control: a broken lib bootstrap is rejected" "$bad_rc"
assert_contains "negative control fails on the missing module, not something else" \
  "ModuleNotFoundError" "$bad_out"

# --- Test 4 (negative control): PYTHONPATH cannot rescue a broken bootstrap -
# The lane must be immune to the caller's environment — otherwise running it
# from a shell that already exports PYTHONPATH would reinstate the masking.
poisoned_out="$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" import_isolated "$TMP/test_negctrl_bad.py")"
poisoned_rc=$?
assert_exit_nonzero_rc "an inherited PYTHONPATH does not mask a broken bootstrap" "$poisoned_rc"
assert_contains "inherited-PYTHONPATH run still fails on the missing module" \
  "ModuleNotFoundError" "$poisoned_out"

# --- Test 5 (tripwire): the flat-layout assumption still holds --------------
# `import_isolated.py` loads each file under its bare stem, which matches the
# real runners ONLY while `tests/` is a flat, non-package directory. If that
# changes, this lane could report a failure the runner does not have — a false
# alarm is as corrosive as a miss. Fail here, loudly and with instructions,
# rather than let the driver quietly diverge.
pkg_markers="$(find "$PROJECT_DIR/tests" -name '__init__.py' -not -path '*/__pycache__/*' 2>/dev/null | sort)"
assert_eq "tests/ is still a flat, non-package directory" "" "$pkg_markers"

rel_imports="$(grep -lE '^[[:space:]]*from[[:space:]]+\.' "$PROJECT_DIR"/tests/test_*.py 2>/dev/null | sort)"
assert_eq "no test file uses a package-relative import" "" "$rel_imports"

if [[ -n "$pkg_markers" || -n "$rel_imports" ]]; then
  echo "tests/ has become package-based:"
  [[ -n "$pkg_markers" ]] && echo "  __init__.py: $pkg_markers"
  [[ -n "$rel_imports" ]] && echo "  relative imports: $rel_imports"
  echo "tests/lib/import_isolated.py loads each file under its bare file stem,"
  echo "which no longer matches how the runner imports it. Teach the driver to"
  echo "derive the dotted module name from the package root (and put that root"
  echo "on sys.path) — do NOT relax this tripwire."
fi

# --- Summary ---------------------------------------------------------------
echo "Swept $count test file(s) in isolated interpreters."
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
