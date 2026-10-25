#!/usr/bin/env bash
# test_setup_pip_install_guards.sh — Tests that every `pip install` in
# aitask_setup.sh is guarded so a failing pip cannot abort `ait setup` (t1374).
#
# The script runs under `set -euo pipefail`. A bare `pip install` that exits
# non-zero (offline machine, unreachable index, unbuildable wheel) aborts the
# WHOLE run at that line, never reaching the validate / warn / degrade path each
# installer wrote below it. pip_install_guarded() keeps the call inside an `if !`
# condition so that path is actually reachable.
#
# Two harness properties are load-bearing:
#
#   1. Every case runs in a CHILD bash. A broken guard terminates the shell it
#      runs in, so a test that sourced the script into its own process would die
#      before it could assert anything about continuation.
#   2. The script under test is a PARAMETER (see driver.sh). The negative
#      controls below re-run the identical cases against mechanically mutated
#      copies of the real source, so they provably exercise the same code path
#      rather than a hand-written replica.
#
# Streams matter and are asserted separately: aitask_setup.sh's info/warn/success
# write to STDOUT; only die() writes to STDERR.
#
# Run: bash tests/test_setup_pip_install_guards.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
SETUP="$PROJECT_DIR/.aitask-scripts/aitask_setup.sh"

PASS=0
FAIL=0
TOTAL=0
SKIPPED=0

TEST_BASH="$(command -v bash)"
[[ -z "$TEST_BASH" ]] && { echo "No bash on PATH; cannot run tests."; exit 2; }

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/test_setup_pip_guards.XXXXXX")"
# Read-only fixtures (cases 5b/5c) leave unwritable dirs behind; restore the
# write bit before removing or the cleanup itself fails.
cleanup() { chmod -R u+w "$SCRATCH" 2>/dev/null || true; rm -rf "$SCRATCH"; }
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# make_home <home-dir> <deps_ok:0|1> [specs_ok:1|0|once, default 1]
# Builds a scratch $HOME containing a CPython venv and a PyPy venv, each with:
#   bin/pip    — always exits 1 (the offline / unreachable-index simulation)
#   bin/python — a bash stub answering every probe aitask_setup.sh makes:
#                  * sys.implementation.name  -> "pypy" / "cpython"
#                  * the find_modern_python version gate -> exit 0
#                  * sys.version_info[:2]     -> "3.13"
#                  * import <mod>             -> exit 0/1 per <deps_ok>
#                  * stdin program (verify_venv_specs) -> per <specs_ok>, see
#                    _make_py_stub
make_home() {
    local home="$1" deps_ok="$2" specs_ok="${3:-1}" venv pypy_venv
    venv="$home/.aitask/venv"
    pypy_venv="$home/.aitask/pypy_venv"
    # stubbin/ is prepended to PATH by run_case; empty unless a case plants a
    # system interpreter there (case 5d plants a dep-bare pypy3).
    mkdir -p "$venv/bin" "$pypy_venv/bin" "$home/stubbin"

    local d
    for d in "$venv" "$pypy_venv"; do
        cat > "$d/bin/pip" <<'PIPSTUB'
#!/usr/bin/env bash
echo "stub pip: simulated failure: $*" >&2
exit 1
PIPSTUB
        chmod +x "$d/bin/pip"
    done

    _make_py_stub "$venv/bin/python"      cpython "$deps_ok" "$deps_ok" "$specs_ok"
    _make_py_stub "$pypy_venv/bin/python" pypy    "$deps_ok" "$deps_ok" "$specs_ok"
}

# _make_py_stub <path> <impl> <deps_ok> [runtime_ok, default = deps_ok]
#               [specs_ok, default 1]
# <runtime_ok> is separate because resolve_pypy_python's probe asks a different
# question from verify_venv_imports: "can this interpreter import the whole
# framework runtime set", which a bare system PyPy answers no to even though it
# is a perfectly good interpreter. (Which module is missing, and
# discoverable-vs-importable, are pinned in tests/test_python_resolve_pypy.sh
# where a real interpreter runs the probe; here only the outcome matters.)
#
# <specs_ok> drives the stdin program (verify_venv_specs' inspection):
#   1    -> exit 0; canned bad-spec output unless <deps_ok> is 1
#   0    -> exit 1 every time — the inspection itself failing, as it does when
#           neither packaging nor pip._vendor.packaging imports
#   once -> exit 1 on the first inspection, clean exit 0 after (a failure the
#           repair fixes)
# Every inspection appends a line to <venv-dir>.inspections (see `inspections`),
# BESIDE the venv so the count survives setup removing the venv itself.
_make_py_stub() {
    local path="$1" impl="$2" deps_ok="$3" runtime_ok="${4:-$3}" specs_ok="${5:-1}"
    cat > "$path" <<PYSTUB
#!/usr/bin/env bash
impl="$impl"
deps_ok="$deps_ok"
runtime_ok="$runtime_ok"
specs_ok="$specs_ok"
inspect_log="${path%/bin/python}.inspections"
PYSTUB
    cat >> "$path" <<'PYSTUB'
case "${1:-}" in
  --version) echo "Python 3.13.0 ($impl stub)"; exit 0 ;;
  -c)
    src="${2:-}"
    case "$src" in
      # Order matters. The fast-path probe also mentions implementation.name,
      # and the version GATE also mentions version_info, so the more specific
      # pattern must come first in each pair. The fast-path probe is keyed on
      # its own guard line — NOT on "import textual", which is also exactly what
      # verify_venv_imports sends one module at a time.
      *"sys.implementation.name != 'pypy'"*)
        [ "$impl" = pypy ] && [ "$runtime_ok" = 1 ] && exit 0 || exit 1 ;;
      *sys.exit*implementation.name*)
        [ "$impl" = pypy ] && exit 0 || exit 1 ;;
      *implementation.name*)          echo "$impl"; exit 0 ;;
      *sys.exit*version_info*)        exit 0 ;;
      *version_info*)                 echo "3.13"; exit 0 ;;
      "import "*)                     [ "$deps_ok" = 1 ] && exit 0 || exit 1 ;;
      *)                              exit 0 ;;
    esac ;;
  -)
    cat >/dev/null            # discard verify_venv_specs' program
    # Best-effort: cases 5b/5c make the log's directory read-only, and they
    # never read the count.
    { echo x >> "$inspect_log"; } 2>/dev/null || :
    case "$specs_ok" in
      0)    exit 1 ;;
      once) [ "$(wc -l < "$inspect_log")" -gt 1 ] && exit 0 || exit 1 ;;
    esac
    [ "$deps_ok" = 1 ] && exit 0
    echo "textual 1.0.0 (need >=8.2.7,<9)"
    exit 0 ;;
  *) exit 0 ;;
esac
PYSTUB
    chmod +x "$path"
}

# ---------------------------------------------------------------------------
# Child-shell driver — the script under test is argument 1
# ---------------------------------------------------------------------------

DRIVER="$SCRATCH/driver.sh"
cat > "$DRIVER" <<'DRIVER_EOF'
#!/usr/bin/env bash
# driver.sh <setup-script-path> <case-name>
# Sources the given aitask_setup.sh with --source-only and drives one function.
# Prints __REACHED_END__ last: its ABSENCE is how the caller detects that `set
# -e` killed the shell mid-function.
set -euo pipefail
# shellcheck source=/dev/null
source "$1" --source-only

case "$2" in
    helper_bare)
        # Bare call, exactly as the converted sites make it. If the helper ever
        # returns non-zero, `set -e` kills this shell before the marker prints.
        pip_install_guarded "probe" "$VENV_DIR/bin/pip" --quiet somepkg
        ;;
    chat)        setup_chat_deps ;;
    dev)         setup_dev_deps ;;
    pypy)        setup_pypy_venv ;;
    cpython)     setup_python_venv ;;
    pypy_then_resolve)
        # The degrade and the resolver are two halves of ONE contract: removal
        # only produces the CPython fallback if resolution also declines the
        # system PyPy that PATH still offers. Assert the end state, not the step.
        setup_pypy_venv
        echo "RESOLVED_PYPY=[$(resolve_pypy_python)]"
        echo "FAST=[$(require_ait_python_fast)]"
        ;;
    *) echo "unknown case: $2" >&2; exit 64 ;;
esac

echo "__REACHED_END__"
DRIVER_EOF

RC=0; OUT=""; ERR=""
# run_case <setup-script> <home> <case-name>
run_case() {
    local script="$1" home="$2" case_name="$3"
    local outf="$SCRATCH/stdout" errf="$SCRATCH/stderr"
    set +e
    # A MINIMAL PATH, not the caller's. resolve_pypy_python probes
    # `pypy$AIT_PYPY_PREFERRED` (i.e. pypy3.11) BEFORE `pypy3`, so a real PyPy
    # anywhere on the developer's PATH silently becomes the resolved candidate
    # and the case stops measuring the stub it planted. Keep only the stub dir
    # plus the system utilities the driver and stubs need.
    HOME="$home" PATH="$home/stubbin:/usr/bin:/bin" \
        "$TEST_BASH" "$DRIVER" "$script" "$case_name" >"$outf" 2>"$errf"
    RC=$?
    set -e
    OUT="$(cat "$outf")"
    ERR="$(cat "$errf")"
}

# fresh_home <name> <deps_ok> [specs_ok] — a per-case $HOME (cases mutate/remove
# venvs)
fresh_home() {
    local home="$SCRATCH/home_$1"
    rm -rf "$home"
    make_home "$home" "$2" "${3:-1}"
    printf '%s' "$home"
}

# make_pip_ok <home> — swap the CPython venv's failing pip for one that
# succeeds. setup_dev_deps returns on a failing install before it verifies
# anything (deliberately — see its comment), so the dev cases need a pip that
# lets them reach the verify block.
make_pip_ok() {
    printf '#!/usr/bin/env bash\nexit 0\n' > "$1/.aitask/venv/bin/pip"
}

# inspections <venv-dir> — how many times verify_venv_specs inspected that venv
inspections() {
    if [[ -f "$1.inspections" ]]; then
        wc -l < "$1.inspections" | tr -d ' '
    else
        echo 0
    fi
}

echo "=== A. Behavioural cases against the real script ==="

# --- 1: the helper itself, called bare under set -e ---
h="$(fresh_home helper 1)"
run_case "$SETUP" "$h" helper_bare
assert_exit_zero_rc "1: bare pip_install_guarded does not abort the shell" "$RC"
assert_contains     "1: execution continued past the guarded call" "__REACHED_END__" "$OUT"
assert_contains     "1: the failure was reported, not swallowed" "pip install failed" "$OUT"

# --- 2/3: setup_chat_deps (optional tier — must never fail setup) ---
h="$(fresh_home chat_good 1)"
run_case "$SETUP" "$h" chat
assert_exit_zero_rc "2: chat tier survives a failing pip" "$RC"
assert_contains     "2: deps already good -> success, no false alarm" "Chat SDK deps ready" "$OUT"
assert_not_contains "2: healthy tier is not reported as broken" "could not be installed" "$OUT"

h="$(fresh_home chat_bad 0)"
run_case "$SETUP" "$h" chat
assert_exit_zero_rc "3: chat tier with unusable deps still returns 0" "$RC"
assert_contains     "3: unusable deps are reported" "Chat deps could not be installed" "$OUT"

# --- 4/5: setup_pypy_venv (degrade = remove, so the board falls back) ---
h="$(fresh_home pypy_good 1)"
run_case "$SETUP" "$h" pypy
assert_exit_zero_rc "4: pypy tier survives a failing pip" "$RC"
assert_dir_exists   "4: a healthy PyPy venv is kept" "$h/.aitask/pypy_venv"

h="$(fresh_home pypy_bad 0)"
run_case "$SETUP" "$h" pypy
assert_exit_zero_rc "5: pypy tier with unusable deps still returns 0" "$RC"
assert_dir_not_exists "5: unusable PyPy venv is removed (CPython fallback)" "$h/.aitask/pypy_venv"

# --- 5b/5c: removal itself fails ---
# resolve_pypy_python() selects $PYPY_VENV_DIR/bin/python on interpreter
# identity ALONE (lib/python_resolve.sh) — it never checks that the deps
# import. So removal is the fallback mechanism, and a removal that silently
# fails would leave a broken interpreter selected ahead of the CPython venv.
if [[ "$EUID" -eq 0 ]]; then
    echo "SKIP: 5b/5c (running as root — the write bit does not deny removal," \
         "so the fixture cannot reproduce the condition and would pass vacuously)"
    SKIPPED=$((SKIPPED + 2))
else
    # 5b: parent unwritable -> `rm -rf` fails, but bin/python is still removable
    h="$(fresh_home pypy_ro_parent 0)"
    chmod a-w "$h/.aitask"
    run_case "$SETUP" "$h" pypy
    chmod u+w "$h/.aitask"
    assert_exit_zero_rc "5b: partial removal still returns 0" "$RC"
    assert_contains     "5b: the leftover directory is reported" "could not be fully removed" "$OUT"
    assert_file_not_exists "5b: interpreter gone -> PyPy can no longer be selected" \
        "$h/.aitask/pypy_venv/bin/python"

    # 5c: bin/ unwritable -> the interpreter survives, so the fallback did NOT
    # happen and setup must say so rather than claim success.
    h="$(fresh_home pypy_ro_bin 0)"
    chmod a-w "$h/.aitask/pypy_venv/bin"
    run_case "$SETUP" "$h" pypy
    chmod u+w "$h/.aitask/pypy_venv/bin"
    assert_exit_nonzero_rc "5c: an undeletable broken PyPy venv is fatal, not silent" "$RC"
    assert_contains "5c: the message says what to do" "Remove it manually" "$ERR"
    assert_file_exists "5c: the fixture really did keep the interpreter" \
        "$h/.aitask/pypy_venv/bin/python"
fi

# --- 5d: the degrade must actually END on CPython, not merely delete a dir ---
# Removing $PYPY_VENV_DIR is only half the fallback: resolve_pypy_python's
# candidate list continues to `pypy<ver>` / `pypy3` on PATH — very often the
# same system interpreter the venv was built from. Asserting "directory gone"
# would pass while the board still launched on a dep-bare PyPy and died at
# `import textual`. Assert the resolution outcome instead.
h="$(fresh_home pypy_syspath 0)"
_make_py_stub "$h/stubbin/pypy3" pypy 0 0     # genuine PyPy on PATH, no textual
run_case "$SETUP" "$h" pypy_then_resolve
assert_exit_zero_rc "5d: degrade + resolution completes" "$RC"
assert_dir_not_exists "5d: the broken venv is gone" "$h/.aitask/pypy_venv"
assert_contains "5d: the system PyPy on PATH is NOT selected" "RESOLVED_PYPY=[]" "$OUT"
assert_contains "5d: the fast path really lands on the CPython venv" \
    "FAST=[$h/.aitask/venv/bin/python]" "$OUT"

# Control: the same system PyPy WITH the deps visible is still selected, so 5d
# is about the missing dependency and not about PATH stubs being unusable.
h="$(fresh_home pypy_syspath_ok 0)"
_make_py_stub "$h/stubbin/pypy3" pypy 0 1
run_case "$SETUP" "$h" pypy_then_resolve
assert_contains "5d control: a dep-complete system PyPy is still selected" \
    "RESOLVED_PYPY=[$h/stubbin/pypy3]" "$OUT"

# --- 6/7: setup_python_venv (core venv — still fails hard when truly broken) ---
h="$(fresh_home cpython_good 1)"
run_case "$SETUP" "$h" cpython
assert_exit_zero_rc "6: offline-but-healthy core venv no longer aborts setup" "$RC"
assert_contains     "6: execution continued to the end" "__REACHED_END__" "$OUT"

h="$(fresh_home cpython_bad 0)"
run_case "$SETUP" "$h" cpython
assert_exit_nonzero_rc "7: a genuinely broken core venv still fails hard" "$RC"
assert_contains "7: it dies with the actionable message, not a bare pip error" \
    "CPython venv still bad" "$ERR"

# --- 8: imports pass, the version inspection itself fails (t2135) ---
# verify_venv_specs leaves bad_specs EMPTY when its inspection fails, so a site
# testing only missing_imports/bad_specs read a failed check as "all in range"
# and enforced no version floor. Every site must treat it as needing repair and
# name it, never render it as "version: none".
h="$(fresh_home cpython_specfail 1 0)"
run_case "$SETUP" "$h" cpython
assert_exit_nonzero_rc "8a: cpython: a failed version check is fatal, not a pass" "$RC"
assert_contains "8a: cpython: the repair warning names the failed check" \
    "CPython venv deps need repair (missing: none; version check failed)" "$OUT"
assert_contains "8a: cpython: it dies naming the failed check" \
    "CPython venv still bad (missing: none; version check failed)" "$ERR"

h="$(fresh_home pypy_specfail 1 0)"
run_case "$SETUP" "$h" pypy
assert_exit_zero_rc "8b: pypy: a failed version check still returns 0" "$RC"
assert_dir_not_exists "8b: pypy: the unverifiable venv is removed (CPython fallback)" \
    "$h/.aitask/pypy_venv"
assert_contains "8b: pypy: the warning names the failed check" \
    "PyPy venv deps could not be installed (missing: none; version check failed)" "$OUT"

h="$(fresh_home chat_specfail 1 0)"
run_case "$SETUP" "$h" chat
assert_exit_zero_rc "8c: chat: a failed version check still returns 0" "$RC"
assert_contains "8c: chat: the warning names the failed check" \
    "Chat deps could not be installed (missing: none; version check failed)" "$OUT"
assert_not_contains "8c: chat: an unverified tier is not reported ready" \
    "Chat SDK deps ready" "$OUT"

# 8d is the control for the dev fixture (a succeeding pip, healthy deps): it
# proves 8e fails on the version check and not on a fixture the tier rejects.
h="$(fresh_home dev_good 1)"
make_pip_ok "$h"
run_case "$SETUP" "$h" dev
assert_exit_zero_rc "8d: dev control: a healthy tier returns 0" "$RC"
assert_contains "8d: dev control: a healthy tier is ready" "Dev/test deps ready" "$OUT"
assert_file_exists "8d: dev control: the opt-in marker is written" "$h/.aitask/dev_tier"

h="$(fresh_home dev_specfail 1 0)"
make_pip_ok "$h"
run_case "$SETUP" "$h" dev
assert_exit_zero_rc "8e: dev: a failed version check still returns 0" "$RC"
assert_contains "8e: dev: the warning names the failed check" \
    "Dev deps could not be installed (missing: none; version check failed)" "$OUT"
assert_file_not_exists "8e: dev: an unverified tier records no opt-in" "$h/.aitask/dev_tier"

# --- 9: the version check fails once, then the repair recovers (t2135) ---
# Section 8 pins only the rejection, and would still pass if a site skipped its
# post-repair re-check: the stale specs_check_ok=false from the FIRST inspection
# would then reject a venv the repair had made healthy. Here the inspection fails
# once and is clean afterwards, so each site must attempt the repair, re-check
# (exactly two inspections), and reach its ready outcome. C4 is the control.
h="$(fresh_home cpython_recover 1 once)"
run_case "$SETUP" "$h" cpython
assert_exit_zero_rc "9a: cpython: a repaired version check does not abort setup" "$RC"
assert_contains "9a: cpython: execution continued to the end" "__REACHED_END__" "$OUT"
assert_contains "9a: cpython: the repair was attempted" \
    "CPython venv deps need repair (missing: none; version check failed). Retrying..." "$OUT"
assert_not_contains "9a: cpython: no stale failure after the repair" "still bad" "$ERR"
assert_eq "9a: cpython: inspected before and after the repair" \
    "2" "$(inspections "$h/.aitask/venv")"

h="$(fresh_home pypy_recover 1 once)"
run_case "$SETUP" "$h" pypy
assert_exit_zero_rc "9b: pypy: a repaired version check returns 0" "$RC"
assert_dir_exists "9b: pypy: the repaired venv is kept" "$h/.aitask/pypy_venv"
assert_contains "9b: pypy: the repair was attempted" \
    "PyPy venv deps need repair (missing: none; version check failed)" "$OUT"
assert_not_contains "9b: pypy: no stale failure after the repair" \
    "could not be installed" "$OUT"
assert_eq "9b: pypy: inspected before and after the repair" \
    "2" "$(inspections "$h/.aitask/pypy_venv")"

h="$(fresh_home chat_recover 1 once)"
run_case "$SETUP" "$h" chat
assert_exit_zero_rc "9c: chat: a repaired version check returns 0" "$RC"
assert_contains "9c: chat: the repair was attempted" \
    "Chat deps need repair (missing: none; version check failed)" "$OUT"
assert_contains "9c: chat: the repaired tier is ready" "Chat SDK deps ready" "$OUT"
assert_eq "9c: chat: inspected before and after the repair" \
    "2" "$(inspections "$h/.aitask/venv")"

h="$(fresh_home dev_recover 1 once)"
make_pip_ok "$h"
run_case "$SETUP" "$h" dev
assert_exit_zero_rc "9d: dev: a repaired version check returns 0" "$RC"
assert_contains "9d: dev: the repair was attempted" \
    "Dev deps need repair (missing: none; version check failed)" "$OUT"
assert_contains "9d: dev: the repaired tier is ready" "Dev/test deps ready" "$OUT"
assert_file_exists "9d: dev: the opt-in marker is written" "$h/.aitask/dev_tier"
assert_eq "9d: dev: inspected before and after the repair" \
    "2" "$(inspections "$h/.aitask/venv")"

echo "=== B. Structural tripwire ==="

bare_sites="$(grep -nE '^[[:space:]]*"\$(VENV_DIR|PYPY_VENV_DIR)/bin/pip" install' \
    "$SETUP" || true)"
assert_eq "B: no unguarded pip install call site remains" "" "$bare_sites"

# AIT_IMPORTS_COMMON is DERIVED from AIT_PYPY_RUNTIME_IMPORTS, so those two
# cannot drift. The pairing derivation cannot enforce is specs<->imports: adding
# a distribution to AIT_PIP_SPECS_COMMON without its import name leaves the new
# dependency unverified after install AND absent from the fast-path probe.
counts="$("$TEST_BASH" -c '
    source "$1" --source-only
    echo "${#AIT_PIP_SPECS_COMMON[@]} ${#AIT_PYPY_RUNTIME_IMPORTS[@]} ${#AIT_IMPORTS_COMMON[@]}"
' _ "$SETUP")"
set -- $counts
assert_eq "B: every COMMON pip spec has a matching import name" "$1" "$2"
assert_eq "B: AIT_IMPORTS_COMMON is derived, not a second copy" "$2" "$3"

echo "=== C. Negative controls (mutations of the real source) ==="

# A mutated copy must be able to source its siblings: aitask_setup.sh derives
# SCRIPT_DIR from BASH_SOURCE[0] and sources $SCRIPT_DIR/lib/python_resolve.sh,
# which in turn sources terminal_compat.sh from its own dirname. A bare copy in
# /tmp dies at that `source` line, and the control would then "fail" for a
# reason that has nothing to do with the guard.
# make_mutant <name> <sed-script> — sets the global MUTANT to the mutated path.
#
# Returns via a GLOBAL, not stdout, and must never be called inside `$( )`:
# command substitution runs the function in a subshell, which would discard its
# PASS/FAIL/TOTAL updates and splice its failure messages into the captured path.
# That is precisely how the self-checks below would go silently missing.
MUTANT=""
make_mutant() {
    local name="$1" sed_script="$2"
    # Separate declaration: under `set -u`, bash expands every RHS in a single
    # `local` before the earlier names in that same statement exist.
    local dir="$SCRATCH/mut_$name"
    local out
    mkdir -p "$dir"
    ln -sfn "$PROJECT_DIR/.aitask-scripts/lib" "$dir/lib"
    out="$dir/aitask_setup.sh"
    sed "$sed_script" "$SETUP" > "$out"

    # The substitution must actually have matched — a silently no-op sed is the
    # classic vacuous negative control.
    if cmp -s "$SETUP" "$out"; then
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: mutation '$name' changed nothing (the sed target has drifted)"
    else
        PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
    fi

    # A mutation that merely fails to parse would also make the control "pass".
    if bash -n "$out" 2>/dev/null; then
        PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
    else
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: mutation '$name' does not parse"
    fi

    # ...and it must still be sourceable, so later failures come from the guard.
    if bash -c 'set -euo pipefail; source "$1" --source-only' _ "$out" >/dev/null 2>&1; then
        PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
    else
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: mutation '$name' cannot be sourced"
    fi

    MUTANT="$out"
}

# --- C1: un-guard the helper itself (one line covers all 8 call sites) ---
# `if ! CMD; then` -> `CMD; if false; then` — pip now runs bare under set -e,
# and the warn/fi block stays valid but unreachable. Exactly the pre-fix defect.
make_mutant helper \
    's|if ! "\$pip_bin" install "\$@"; then|"\$pip_bin" install "\$@"; if false; then|'
MUT_HELPER="$MUTANT"

for spec in "helper_bare:helper" "chat:chat_good:1" "chat:chat_bad:0" \
            "pypy:pypy_good:1" "pypy:pypy_bad:0" "cpython:cpython_good:1"; do
    IFS=: read -r case_name home_name deps <<< "$spec"
    h="$(fresh_home "neg_${home_name}" "${deps:-1}")"
    run_case "$MUT_HELPER" "$h" "$case_name"
    assert_exit_nonzero_rc "C1/$home_name: un-guarded helper aborts the run" "$RC"
    assert_not_contains "C1/$home_name: the shell died before the end" \
        "__REACHED_END__" "$OUT"
done

# Case 7 exits non-zero either way, so its discriminator is the MESSAGE: with the
# guard removed the run dies at pip, never reaching the informative die().
h="$(fresh_home neg_cpython_bad 0)"
run_case "$MUT_HELPER" "$h" cpython
assert_not_contains "C1/cpython_bad: un-guarded run never reaches the die() message" \
    "CPython venv still bad" "$ERR"

# --- C2: re-introduce ONE bare call site (this is what tripwire B detects) ---
# C1 leaves the call sites intact, so it cannot validate B; B needs its own
# mutation. This one is also a real behavioural regression, so it must flip the
# chat cases too.
make_mutant callsite \
    's|pip_install_guarded "Chat deps" "\$VENV_DIR/bin/pip" \\|"\$VENV_DIR/bin/pip" install \\|'
MUT_SITE="$MUTANT"

neg_bare_sites="$(grep -nE '^[[:space:]]*"\$(VENV_DIR|PYPY_VENV_DIR)/bin/pip" install' \
    "$MUT_SITE" || true)"
assert_contains "C2: tripwire B detects a re-introduced bare call site" \
    '"$VENV_DIR/bin/pip" install' "$neg_bare_sites"

h="$(fresh_home neg_site_chat 1)"
run_case "$MUT_SITE" "$h" chat
assert_exit_nonzero_rc "C2: a bare chat call site aborts the run" "$RC"
assert_not_contains "C2: the shell died before the end" "__REACHED_END__" "$OUT"

# The un-mutated sites are unaffected — proving the mutation is targeted.
h="$(fresh_home neg_site_pypy 1)"
run_case "$MUT_SITE" "$h" pypy
assert_exit_zero_rc "C2: sites left guarded still survive (mutation is targeted)" "$RC"

# --- C3: drop the specs_check_ok clause from venv_deps_bad (t2135) ---
# The pre-fix predicate. Every section-8 case must fall back to reading a failed
# version check as "all in range" — proving those cases detect exactly that
# clause. (The string occurs only in venv_deps_bad.)
make_mutant specscheck 's/ || "\$specs_check_ok" != true ]]/ ]]/'
MUT_SPECS="$MUTANT"

h="$(fresh_home neg_specs_cpython 1 0)"
run_case "$MUT_SPECS" "$h" cpython
assert_exit_zero_rc "C3/cpython: without the clause a failed check passes" "$RC"
assert_contains "C3/cpython: ...and setup runs to the end" "__REACHED_END__" "$OUT"

h="$(fresh_home neg_specs_pypy 1 0)"
run_case "$MUT_SPECS" "$h" pypy
assert_dir_exists "C3/pypy: without the clause the unverified venv is kept" \
    "$h/.aitask/pypy_venv"

h="$(fresh_home neg_specs_chat 1 0)"
run_case "$MUT_SPECS" "$h" chat
assert_contains "C3/chat: without the clause the unverified tier is ready" \
    "Chat SDK deps ready" "$OUT"

h="$(fresh_home neg_specs_dev 1 0)"
make_pip_ok "$h"
run_case "$MUT_SPECS" "$h" dev
assert_file_exists "C3/dev: without the clause the unverified tier records opt-in" \
    "$h/.aitask/dev_tier"

# --- C4: skip every post-repair re-check (t2135) ---
# The four post-repair verify_venv_specs calls are the only ones indented 8
# spaces with the column alignment (report_venv_dep_drift's has one space).
# With them no-op'd, specs_check_ok stays false from the first inspection, so
# every section-9 recovery must flip to a rejection — the failure mode section 8
# cannot see.
make_mutant norecheck 's|^        verify_venv_specs   |        : |'
MUT_RECHECK="$MUTANT"
recheck_lines="$(diff "$SETUP" "$MUT_RECHECK" | grep -c '^>' || true)"
assert_eq "C4: the mutation no-ops exactly the four post-repair re-checks" \
    "4" "$recheck_lines"

h="$(fresh_home neg_recheck_cpython 1 once)"
run_case "$MUT_RECHECK" "$h" cpython
assert_exit_nonzero_rc "C4/cpython: a skipped re-check rejects the repaired venv" "$RC"
assert_contains "C4/cpython: ...with the stale failure" "still bad" "$ERR"
assert_eq "C4/cpython: only the first inspection ran" "1" "$(inspections "$h/.aitask/venv")"

h="$(fresh_home neg_recheck_pypy 1 once)"
run_case "$MUT_RECHECK" "$h" pypy
assert_dir_not_exists "C4/pypy: a skipped re-check removes the repaired venv" \
    "$h/.aitask/pypy_venv"
assert_eq "C4/pypy: only the first inspection ran" "1" "$(inspections "$h/.aitask/pypy_venv")"

h="$(fresh_home neg_recheck_chat 1 once)"
run_case "$MUT_RECHECK" "$h" chat
assert_contains "C4/chat: a skipped re-check rejects the repaired tier" \
    "Chat deps could not be installed" "$OUT"
assert_eq "C4/chat: only the first inspection ran" "1" "$(inspections "$h/.aitask/venv")"

h="$(fresh_home neg_recheck_dev 1 once)"
make_pip_ok "$h"
run_case "$MUT_RECHECK" "$h" dev
assert_file_not_exists "C4/dev: a skipped re-check records no opt-in" "$h/.aitask/dev_tier"
assert_eq "C4/dev: only the first inspection ran" "1" "$(inspections "$h/.aitask/venv")"

echo ""
echo "Tests: $TOTAL  Pass: $PASS  Fail: $FAIL  Skipped: $SKIPPED"
if (( FAIL > 0 )); then
    exit 1
fi
