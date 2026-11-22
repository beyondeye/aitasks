#!/usr/bin/env bash
# test_python_resolve_unset_home.sh - startup code survives an unset or empty
# HOME under `set -u` (t2347).
#
# cron, systemd and `env -i` run with no HOME. Before t2347 every startup path
# below expanded $HOME at top level and aborted a `set -euo pipefail` caller
# with "HOME: unbound variable", even when $AIT_PYTHON named a working
# interpreter:
#
#   lib/python_resolve.sh  PYPY_VENV_DIR default + resolve_python candidates
#   lib/aitask_path.sh     the ~/.aitask/bin PATH prepend (sourced first by most
#                          scripts, so fixing python_resolve.sh alone helped none
#                          of them)
#   ait                    check_for_updates, before dispatch (`ait ls`)
#   aitask_setup.sh        with HOME="" it continued on root-level paths, and
#                          would derive an EMPTY PYPY_VENV_DIR (/bin/pip,
#                          `rm -f /bin/python`) once python_resolve.sh stopped
#                          defaulting to `/.aitask/...`; it now refuses
#
# The HOME-based candidates are skipped (never rewritten to `/.aitask/...`);
# AIT_PYTHON and the PATH python3 still resolve. HOME-set behaviour is pinned
# alongside so the guard boundary is visible.
#
# Safety: setup is only ever SOURCED with --source-only (plain sourcing runs
# main; only --source-only returns before it), so even a regressed guard cannot
# reach the installer. `ait` is never run with a HOME set (its update check
# could reach the network). Every child runs from an empty read-only cwd.
#
# PYTHON_RESOLVE_TEST_ROOT=<tree> points the cases at another checkout holding
# `ait` + `.aitask-scripts` (default: this repository) — used for pre-fix
# controls against a fixture with one file reverted.
#
# Run: bash tests/test_python_resolve_unset_home.sh

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
run_tmpdir_init test_python_resolve_unset_home
trap run_tmpdir_cleanup EXIT

TREE="${PYTHON_RESOLVE_TEST_ROOT:-$PROJECT_DIR}"
LIB="$TREE/.aitask-scripts/lib"

# The real interpreter, resolved the framework's way in THIS (real-HOME) shell,
# then reduced to its sys.executable while that environment is still intact.
# resolve_python may answer a wrapper (AIT_PYTHON, or the ~/.aitask/bin/python3
# that setup installs) which needs HOME to find its interpreter, and every child
# below runs without HOME.
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
REAL_PY="$(resolve_python)"
[[ -n "$REAL_PY" ]] && REAL_PY="$("$REAL_PY" -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
if [[ -z "$REAL_PY" || ! -x "$REAL_PY" ]]; then
    echo "SKIP: no Python interpreter available"
    exit 0
fi
unset _AIT_RESOLVED_PYTHON _AIT_PYTHON_RESOLVE_LOADED
TEST_BASH="$(command -v bash)"

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/py_unset_home_XXXXXX")"
STUB_BIN="$ROOT/stub_bin"
SCRATCH_HOME="$ROOT/home"
ERR="$ROOT/stderr"
mkdir -p "$STUB_BIN" "$SCRATCH_HOME/.aitask/venv/bin"
# A working python3 first on PATH, so the PATH fallback is observable by path.
printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$REAL_PY" > "$STUB_BIN/python3"
# PyPy names on PATH that always fail the identity probe, so a system PyPy can
# never make resolve_pypy_python's answer host-dependent.
for n in pypy3 pypy3.11; do
    printf '#!/usr/bin/env bash\nexit 1\n' > "$STUB_BIN/$n"
done
# The scratch-HOME venv interpreter (for the HOME-set boundary case).
printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$REAL_PY" \
    > "$SCRATCH_HOME/.aitask/venv/bin/python"
chmod +x "$STUB_BIN"/* "$SCRATCH_HOME/.aitask/venv/bin/python"

# run_sh <home> <code> [VAR=value ...]
# <home>: `unset`, `empty` (HOME=), or a directory. Runs <code> under
# `set -euo pipefail` in a clean env (env -i), with $1 = the lib dir. Prints
# stdout then a final "rc=<n>" line; stderr goes to $ERR.
run_sh() {
    local home="$1" code="$2"
    shift 2
    local -a henv=()
    case "$home" in
        unset) ;;
        empty) henv=(HOME=) ;;
        *)     henv=(HOME="$home") ;;
    esac
    local rc=0 out
    out="$(env -i PATH="$STUB_BIN:/usr/bin:/bin" "${henv[@]}" "$@" \
        "$TEST_BASH" -c "set -euo pipefail; $code" _ "$LIB" 2>"$ERR")" || rc=$?
    printf '%s\nrc=%s\n' "$out" "$rc"
}

# ============================================================
echo "--- python_resolve.sh: source + resolve_python without HOME ---"
# ============================================================

for mode in unset empty; do
    out="$(run_sh "$mode" 'source "$1/python_resolve.sh"; echo sourced')"
    assert_contains "[$mode] python_resolve.sh sources under set -u" "sourced" "$out"
    assert_contains "[$mode] source rc 0" "rc=0" "$out"
    assert_not_contains "[$mode] no unbound variable" "unbound variable" "$(cat "$ERR")"

    out="$(run_sh "$mode" 'source "$1/python_resolve.sh"; resolve_python' \
        AIT_PYTHON="$REAL_PY")"
    assert_eq "[$mode] AIT_PYTHON wins" "$REAL_PY
rc=0" "$out"

    out="$(run_sh "$mode" 'source "$1/python_resolve.sh"; resolve_python')"
    assert_eq "[$mode] PATH python3 fallback resolves" "$STUB_BIN/python3
rc=0" "$out"

    out="$(run_sh "$mode" 'source "$1/python_resolve.sh"; printf "PYPY=[%s]\n" "$PYPY_VENV_DIR"')"
    assert_contains "[$mode] PYPY_VENV_DIR is empty, not root-level" "PYPY=[]" "$out"

    out="$(run_sh "$mode" 'source "$1/python_resolve.sh"; printf "[%s]\n" "$(resolve_pypy_python)"' \
        AIT_PYPY_PREFERRED=0.0)"
    assert_eq "[$mode] resolve_pypy_python: empty, rc 0" "[]
rc=0" "$out"

    out="$(run_sh "$mode" 'source "$1/python_resolve.sh"; require_ait_python_fast' \
        AIT_PYTHON="$REAL_PY" AIT_PYPY_PREFERRED=0.0)"
    assert_eq "[$mode] require_ait_python_fast falls back to AIT_PYTHON" "$REAL_PY
rc=0" "$out"
done

# ============================================================
echo "--- python_resolve.sh: HOME set is unchanged ---"
# ============================================================

out="$(run_sh "$SCRATCH_HOME" 'source "$1/python_resolve.sh"; printf "PYPY=[%s]\n" "$PYPY_VENV_DIR"')"
assert_contains "HOME set: PYPY_VENV_DIR default under HOME" \
    "PYPY=[$SCRATCH_HOME/.aitask/pypy_venv]" "$out"
out="$(run_sh "$SCRATCH_HOME" 'source "$1/python_resolve.sh"; printf "PYPY=[%s]\n" "$PYPY_VENV_DIR"' \
    PYPY_VENV_DIR=/x)"
assert_contains "HOME set: explicit PYPY_VENV_DIR kept" "PYPY=[/x]" "$out"
out="$(run_sh "$SCRATCH_HOME" 'source "$1/python_resolve.sh"; resolve_python')"
assert_eq "HOME set: venv candidate wins over PATH python3" \
    "$SCRATCH_HOME/.aitask/venv/bin/python
rc=0" "$out"

# ============================================================
echo "--- aitask_path.sh ---"
# ============================================================

for mode in unset empty; do
    out="$(run_sh "$mode" 'before="$PATH"; source "$1/aitask_path.sh"; [[ "$PATH" == "$before" ]] && echo unchanged; printf "PATH=%s\n" "$PATH"')"
    assert_contains "[$mode] aitask_path.sh sources, PATH unchanged" "unchanged" "$out"
    assert_contains "[$mode] aitask_path.sh rc 0" "rc=0" "$out"
    assert_not_contains "[$mode] no root-level /.aitask/bin on PATH" "/.aitask/bin" "$out"
    assert_not_contains "[$mode] aitask_path.sh: no unbound variable" "unbound variable" "$(cat "$ERR")"
done
out="$(run_sh "$SCRATCH_HOME" 'source "$1/aitask_path.sh"; unset _AIT_PATH_LOADED; source "$1/aitask_path.sh"; tr ":" "\n" <<<"$PATH" | grep -cxF "$HOME/.aitask/bin"')"
assert_eq "HOME set: ~/.aitask/bin prepended exactly once across two sources" "1
rc=0" "$out"

# ============================================================
echo "--- aitask_setup.sh refuses a missing destination (--source-only) ---"
# ============================================================

for mode in unset empty; do
    out="$(run_sh "$mode" 'source "$1/../aitask_setup.sh" --source-only; printf "PYPY=[%s]\n" "$PYPY_VENV_DIR"')"
    assert_contains "[$mode] setup exits 1" "rc=1" "$out"
    assert_not_contains "[$mode] setup derives no paths" "PYPY=" "$out"
    assert_contains "[$mode] setup names the cause" "ait setup needs HOME" "$(cat "$ERR")"
    assert_not_contains "[$mode] setup: no unbound variable" "unbound variable" "$(cat "$ERR")"
done
out="$(run_sh "$SCRATCH_HOME" 'source "$1/../aitask_setup.sh" --source-only; printf "PYPY=[%s]\n" "$PYPY_VENV_DIR"')"
assert_eq "HOME set: setup sources and derives its PyPy dir under HOME" \
    "PYPY=[$SCRATCH_HOME/.aitask/pypy_venv]
rc=0" "$out"

# ============================================================
echo "--- public launcher and direct entry points, no HOME ---"
# ============================================================

# run_entry <help-marker> <desc> <path> [args...] — HOME absent, AIT_PYTHON set.
run_entry() {
    local marker="$1" desc="$2"
    shift 2
    local rc=0 out
    out="$(env -i PATH=/usr/bin:/bin AIT_PYTHON="$REAL_PY" \
        "$TEST_BASH" "$@" 2>"$ERR" </dev/null)" || rc=$?
    assert_eq "$desc: rc 0" "0" "$rc"
    assert_contains "$desc: prints its usage" "$marker" "$out"
    assert_not_contains "$desc: no unbound variable" "unbound variable" "$(cat "$ERR")"
}
run_entry "Usage: aitask_ls.sh" "ait ls --help" "$TREE/ait" ls --help
run_entry "Usage: ait crew init" "ait crew init --help" "$TREE/ait" crew init --help
# Sources python_resolve.sh directly (no aitask_path.sh); its usage needs no
# external tool (aitask_add_model.sh is NOT used: it runs require_jq before
# dispatching --help, so a jq-less PATH would fail it for an unrelated reason).
run_entry "Usage: aitask_change_surface.sh" "aitask_change_surface.sh --help" \
    "$TREE/.aitask-scripts/aitask_change_surface.sh" --help
# Sources aitask_path.sh, then python_resolve.sh; shell-only usage.
run_entry "Usage: aitask_brainstorm_context.sh" "aitask_brainstorm_context.sh --help" \
    "$TREE/.aitask-scripts/aitask_brainstorm_context.sh" --help

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
