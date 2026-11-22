#!/usr/bin/env bash
# test_shell_bridge_python_resolve.sh - the Python shell bridges honour
# AIT_PYTHON (t2339).
#
# lib/launch_modes_sh.sh, lib/followup_kinds_sh.sh and lib/plan_paths_sh.sh used
# `${_AIT_RESOLVED_PYTHON:-python3}`. Under a scratch HOME the PATH python3 is
# the ~/.aitask/bin wrapper of a HOME that has no venv, so it fails — and the
# bridges ignored an explicit AIT_PYTHON. `ait brainstorm init` died with
# "failed to load launch_modes vocabulary". They now resolve through
# lib/python_resolve.sh when it is present, and keep the PATH python3 fallback
# when it is not (a test scaffold that copies a bridge on its own).
#
# Environment for every case: a scratch HOME with no .aitask, a `python3` stub
# that exits 1 FIRST on PATH (the broken wrapper), _AIT_RESOLVED_PYTHON unset.
#
#   fixed      — real bridges + AIT_PYTHON set  → work, through each public entry
#   fallback   — bridge copied WITHOUT python_resolve.sh, its Python module
#                reachable through the bridge's own dir hook:
#                  positive control: a working python3 on PATH → works
#                  negative:         the failing stub on PATH → fails closed
#
# Run: bash tests/test_shell_bridge_python_resolve.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/run_tmpdir.sh"
run_tmpdir_init test_shell_bridge_python_resolve
trap run_tmpdir_cleanup EXIT

LIB="$PROJECT_DIR/.aitask-scripts/lib"

# The real interpreter, resolved the framework's way in THIS (real-HOME) shell.
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$LIB/python_resolve.sh"
REAL_PY="$(resolve_python)"
if [[ -z "$REAL_PY" ]]; then
    echo "SKIP: no Python interpreter available"
    exit 0
fi
unset _AIT_RESOLVED_PYTHON _AIT_PYTHON_RESOLVE_LOADED

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/bridge_py_XXXXXX")"
SCRATCH_HOME="$ROOT/home"
BROKEN_BIN="$ROOT/broken_bin"
WORKING_BIN="$ROOT/working_bin"
mkdir -p "$SCRATCH_HOME" "$BROKEN_BIN" "$WORKING_BIN"
printf '#!/usr/bin/env bash\necho "stub python3: broken wrapper" >&2\nexit 1\n' \
    > "$BROKEN_BIN/python3"
printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$REAL_PY" > "$WORKING_BIN/python3"
chmod +x "$BROKEN_BIN/python3" "$WORKING_BIN/python3"

PLAN="$ROOT/plan.md"
printf 'Step 1: edit `foo/bar.py` and nothing else.\n' > "$PLAN"

# Expected launch-modes value, straight from the Python module.
EXPECTED_PIPE="$("$REAL_PY" -c "
import sys
sys.path.insert(0, '$LIB')
from launch_modes import launch_modes_pipe
sys.stdout.write(launch_modes_pipe())
")"

# run_bridge <bin-dir-first-on-PATH> <bridge-lib-dir> <case> [VAR=value ...]
# Runs one public entry point in a clean child shell; prints its output and
# a final "rc=<n>" line.
run_bridge() {
    local bin_dir="$1" lib_dir="$2" case_name="$3"
    shift 3
    env -u _AIT_RESOLVED_PYTHON -u _AIT_PYTHON_RESOLVE_LOADED \
        -u AIT_PYTHON -u AIT_LAUNCH_MODES_DIR -u AIT_FOLLOWUP_KINDS_DIR \
        -u AIT_PLAN_PATHS_DIR \
        HOME="$SCRATCH_HOME" PATH="$bin_dir:/usr/bin:/bin" PLAN="$PLAN" "$@" \
        bash -c '
lib="$1"
case "$2" in
  launch_modes)
    ( source "$lib/launch_modes_sh.sh" && printf "PIPE=%s\n" "$LAUNCH_MODES_PIPE" )
    echo "rc=$?" ;;
  followup_kinds)
    source "$lib/followup_kinds_sh.sh"
    if is_valid_followup_kind risk_mitigation; then echo "rc=0"; else echo "rc=$?"; fi ;;
  plan_paths)
    source "$lib/plan_paths_sh.sh"
    if out="$(printf "foo/bar.py\0" | plan_paths_references "$PLAN")"; then rc=0; else rc=$?; fi
    printf "OUT=%s\n" "$out"
    echo "rc=$rc" ;;
esac' _ "$lib_dir" "$case_name" 2>&1
}

# ============================================================
# fixed: real bridges, AIT_PYTHON set, broken python3 first on PATH
# ============================================================

echo "--- fixed: real bridges honour AIT_PYTHON ---"

out="$(run_bridge "$BROKEN_BIN" "$LIB" launch_modes AIT_PYTHON="$REAL_PY")"
assert_contains "launch_modes: sources under the broken PATH python3" "rc=0" "$out"
assert_contains "launch_modes: pipe equals the Python value" "PIPE=$EXPECTED_PIPE" "$out"
assert_not_contains "launch_modes: never reached the stub" "stub python3" "$out"

out="$(run_bridge "$BROKEN_BIN" "$LIB" followup_kinds AIT_PYTHON="$REAL_PY")"
assert_contains "followup_kinds: risk_mitigation is a valid kind" "rc=0" "$out"

out="$(run_bridge "$BROKEN_BIN" "$LIB" plan_paths AIT_PYTHON="$REAL_PY")"
assert_contains "plan_paths_references: succeeds" "rc=0" "$out"
assert_contains "plan_paths_references: finds the referenced path" "foo/bar.py" "$out"

# ============================================================
# resolver branch: NO AIT_PYTHON, broken python3 first on PATH, and a working
# framework venv under $HOME. Only lib/python_resolve.sh finds that venv, so
# this case fails if a bridge skips the resolver (AIT_PYTHON and the PATH
# fallback both miss it).
# ============================================================

echo "--- resolver branch: venv under HOME, no AIT_PYTHON ---"

VENV_HOME="$ROOT/venv_home"
mkdir -p "$VENV_HOME/.aitask/venv/bin"
printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$REAL_PY" > "$VENV_HOME/.aitask/venv/bin/python"
chmod +x "$VENV_HOME/.aitask/venv/bin/python"

out="$(run_bridge "$BROKEN_BIN" "$LIB" launch_modes HOME="$VENV_HOME")"
assert_contains "resolver: launch_modes finds the HOME venv" "PIPE=$EXPECTED_PIPE" "$out"
assert_not_contains "resolver: launch_modes never reached the stub" "stub python3" "$out"
out="$(run_bridge "$BROKEN_BIN" "$LIB" followup_kinds HOME="$VENV_HOME")"
assert_contains "resolver: followup_kinds finds the HOME venv" "rc=0" "$out"
out="$(run_bridge "$BROKEN_BIN" "$LIB" plan_paths HOME="$VENV_HOME")"
assert_contains "resolver: plan_paths finds the HOME venv" "foo/bar.py" "$out"

# ============================================================
# fallback: bridge copied without python_resolve.sh. The Python module stays
# reachable through the bridge's own dir hook, so a failure can only come
# from the interpreter choice.
# ============================================================

echo "--- fallback: no python_resolve.sh next to the bridge ---"

COPY="$ROOT/lib_copy"
mkdir -p "$COPY"
cp "$LIB/launch_modes_sh.sh" "$LIB/followup_kinds_sh.sh" "$LIB/plan_paths_sh.sh" "$COPY/"
assert_eq "fallback: the copy has no python_resolve.sh" "no" \
    "$([[ -e "$COPY/python_resolve.sh" ]] && echo yes || echo no)"
HOOKS=(AIT_LAUNCH_MODES_DIR="$LIB" AIT_FOLLOWUP_KINDS_DIR="$LIB" AIT_PLAN_PATHS_DIR="$LIB")

# Positive control: a working python3 on PATH -> the copy and the hooks work.
out="$(run_bridge "$WORKING_BIN" "$COPY" launch_modes "${HOOKS[@]}")"
assert_contains "positive control: launch_modes copy works" "rc=0" "$out"
assert_contains "positive control: launch_modes copy pipe" "PIPE=$EXPECTED_PIPE" "$out"
out="$(run_bridge "$WORKING_BIN" "$COPY" followup_kinds "${HOOKS[@]}")"
assert_contains "positive control: followup_kinds copy works" "rc=0" "$out"
out="$(run_bridge "$WORKING_BIN" "$COPY" plan_paths "${HOOKS[@]}")"
assert_contains "positive control: plan_paths copy works" "rc=0" "$out"
assert_contains "positive control: plan_paths copy finds the path" "foo/bar.py" "$out"

# Negative: no AIT_PYTHON and the failing stub on PATH -> the plain PATH
# fallback is kept, and it fails closed.
out="$(run_bridge "$BROKEN_BIN" "$COPY" launch_modes "${HOOKS[@]}")"
assert_contains "negative: launch_modes names its failure" \
    "failed to load launch_modes vocabulary" "$out"
assert_not_contains "negative: launch_modes does not succeed" "rc=0" "$out"
out="$(run_bridge "$BROKEN_BIN" "$COPY" followup_kinds "${HOOKS[@]}")"
assert_not_contains "negative: followup_kinds rejects (fails closed)" "rc=0" "$out"
out="$(run_bridge "$BROKEN_BIN" "$COPY" plan_paths "${HOOKS[@]}")"
assert_not_contains "negative: plan_paths_references fails" "rc=0" "$out"
assert_eq "negative: plan_paths_references prints nothing" "OUT=" \
    "$(printf '%s\n' "$out" | grep '^OUT=')"

# AIT_PYTHON is honoured by the bridge itself, before (and without) the
# resolver: the same broken PATH, with AIT_PYTHON set, works.
out="$(run_bridge "$BROKEN_BIN" "$COPY" launch_modes "${HOOKS[@]}" AIT_PYTHON="$REAL_PY")"
assert_contains "no resolver: launch_modes honours AIT_PYTHON" "PIPE=$EXPECTED_PIPE" "$out"
out="$(run_bridge "$BROKEN_BIN" "$COPY" followup_kinds "${HOOKS[@]}" AIT_PYTHON="$REAL_PY")"
assert_contains "no resolver: followup_kinds honours AIT_PYTHON" "rc=0" "$out"
out="$(run_bridge "$BROKEN_BIN" "$COPY" plan_paths "${HOOKS[@]}" AIT_PYTHON="$REAL_PY")"
assert_contains "no resolver: plan_paths honours AIT_PYTHON" "foo/bar.py" "$out"

# ============================================================
# HOME unset, through a real `set -u` entry point (aitask_crew_init.sh
# sources launch_modes_sh.sh at startup). The bridge skips python_resolve.sh
# without HOME (everything it adds beyond AIT_PYTHON lives under HOME), and
# python_resolve.sh itself no longer aborts there since t2347 — see
# tests/test_python_resolve_unset_home.sh.
# ============================================================

echo "--- HOME unset: crew entry point under set -u ---"

CREW="$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh"
run_crew_help() {
    # $1 = PATH, rest = extra VAR=value. HOME is deliberately absent (env -i).
    local path="$1"; shift
    env -i PATH="$path" "$@" bash "$CREW" --help >/dev/null 2>"$ROOT/crew_err"
    echo "rc=$?"
}
out="$(run_crew_help "$WORKING_BIN:/usr/bin:/bin" AIT_PYTHON="$REAL_PY")"
assert_eq "no HOME + AIT_PYTHON: crew --help exits 0" "rc=0" "$out"
assert_not_contains "no HOME + AIT_PYTHON: no unbound HOME" "unbound variable" \
    "$(cat "$ROOT/crew_err")"
out="$(run_crew_help "$WORKING_BIN:/usr/bin:/bin")"
assert_eq "no HOME, no AIT_PYTHON: PATH python3 fallback still works" "rc=0" "$out"
out="$(run_crew_help "$BROKEN_BIN:/usr/bin:/bin" AIT_PYTHON="$REAL_PY")"
assert_eq "no HOME + broken PATH python3: AIT_PYTHON rescues crew --help" "rc=0" "$out"

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed (of $TOTAL total)"
echo "================================"

if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
