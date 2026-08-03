#!/usr/bin/env bash
# test_python_resolve_pypy.sh - Tests for PyPy-aware functions in lib/python_resolve.sh
# Covers the AIT_USE_PYPY precedence table for require_ait_python_fast.
# Run: bash tests/test_python_resolve_pypy.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
LIB="$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PASS=0
FAIL=0
TOTAL=0

# Resolve to the underlying interpreter so stubs work after HOME is overridden.
# (`command -v python3` may return the framework wrapper at ~/.aitask/bin/python3,
# which exec's into $HOME/.aitask/venv/bin/python — broken once HOME=$SCRATCH.)
REAL_PY="$(python3 -c 'import sys; print(sys.executable)' 2>/dev/null)"
[[ -z "$REAL_PY" || ! -x "$REAL_PY" ]] && REAL_PY="$(command -v python3)"
[[ -z "$REAL_PY" ]] && { echo "No python3 on host; cannot run tests."; exit 2; }

TEST_BASH="$(command -v bash)"
[[ -z "$TEST_BASH" ]] && { echo "No bash on PATH; cannot run tests."; exit 2; }

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/test_python_resolve_pypy.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

mkdir -p "$SCRATCH/bin" "$SCRATCH/.aitask/bin" "$SCRATCH/.aitask/venv/bin" "$SCRATCH/.aitask/pypy_venv/bin"

# Subshells get a custom PATH so stubs win over system interpreters.
SUBPATH="$SCRATCH/bin:/usr/bin:/bin"

# make_cpython_stub <name> <reported_version>
# A bash stub mimicking CPython's --version output and -c semantics for the
# implementation-name and version-info checks.
make_cpython_stub() {
    local name="$1" ver="$2"
    local path="$SCRATCH/bin/$name"
    cat > "$path" <<STUB
#!/usr/bin/env bash
case "\$1" in
  --version) echo "Python $ver" ;;
  -c)
    shift
    code="\$1"
    real_py='$REAL_PY'
    "\$real_py" -c "
import sys, types
parts = '$ver'.split('.')
major = int(parts[0])
minor = int(parts[1]) if len(parts) > 1 else 0
patch = int(parts[2]) if len(parts) > 2 else 0
class _VI(tuple):
    @property
    def major(self): return self[0]
    @property
    def minor(self): return self[1]
    @property
    def micro(self): return self[2]
sys.version_info = _VI((major, minor, patch, 'final', 0))
# Copy the REAL implementation namespace and override only .name. A bare
# stand-in class is not enough: resolve_pypy_python's probe imports
# importlib.util, and the import machinery reads cache_tag/version off
# sys.implementation and constructs its type — a minimal fake raises
# (AttributeError / 'takes no arguments') instead of answering the probe.
_real_impl = sys.implementation
sys.implementation = types.SimpleNamespace(
    **{k: getattr(_real_impl, k) for k in dir(_real_impl) if not k.startswith('__')})
sys.implementation.name = 'cpython'
exec(compile('''\$code''', '<stub>', 'exec'))
"
    ;;
  *) echo "stub:$name:$ver:\$@" ;;
esac
STUB
    chmod +x "$path"
}

# Fake runtime packages. resolve_pypy_python() IMPORTS the whole
# $AIT_PYPY_RUNTIME_IMPORTS set, so the stubs need a way to present that set
# fully, partially, or broken — the three ways a real interpreter fails.
#
#   full        — every required module imports cleanly
#   partial     — textual present, `yaml` MISSING (the board imports yaml too)
#   broken      — every module present, but textual's __init__ raises (a
#                 discoverable package is not an importable one)
for _m in textual yaml linkify_it tomli; do
    mkdir -p "$SCRATCH/deps_full/$_m";   : > "$SCRATCH/deps_full/$_m/__init__.py"
    mkdir -p "$SCRATCH/deps_broken/$_m"; : > "$SCRATCH/deps_broken/$_m/__init__.py"
done
echo 'raise ImportError("simulated broken install")' > "$SCRATCH/deps_broken/textual/__init__.py"
# Importing the runtime set really does write to STDOUT: under PyPy, `import
# yaml` emits Cython diagnostic lines. resolve_pypy_python echoes the
# interpreter path on stdout, so an unredirected probe splices that noise into
# the path its caller captures. Reproduce it here so the healthy-interpreter
# assertions double as the guard for that redirection.
for _d in deps_full deps_broken; do
    printf '%s\n' 'print("(_common_types_metatype, 9088, 128, 128)")' \
        > "$SCRATCH/$_d/yaml/__init__.py"
done
for _m in textual linkify_it tomli; do
    mkdir -p "$SCRATCH/deps_partial/$_m"; : > "$SCRATCH/deps_partial/$_m/__init__.py"
done

# make_pypy_stub <path> <reported_version> [deps: full|none|partial|broken]
# A bash stub that reports sys.implementation.name == 'pypy' and the given
# Python version (via the version_info / implementation rewrite trick).
#
# <deps> selects which fake runtime set the stub exposes (default full). The
# probe runs the real interpreter with `-S` (no site-packages) so dependency
# visibility comes ONLY from this argument and never from whatever the host's
# python3 happens to have installed — on a dev box `python3` is often the
# framework venv, which really does have textual, and that would make a
# dependency-less stub silently pass.
make_pypy_stub() {
    local path="$1" ver="$2" deps="${3:-full}"
    local dir deps_line
    dir="$(dirname "$path")"
    mkdir -p "$dir"
    case "$deps" in
        full|1)   deps_line="export PYTHONPATH='$SCRATCH/deps_full'" ;;
        partial)  deps_line="export PYTHONPATH='$SCRATCH/deps_partial'" ;;
        broken)   deps_line="export PYTHONPATH='$SCRATCH/deps_broken'" ;;
        none|0)   deps_line="unset PYTHONPATH" ;;
        *) echo "make_pypy_stub: unknown deps profile '$deps'" >&2; exit 2 ;;
    esac
    cat > "$path" <<STUB
#!/usr/bin/env bash
$deps_line
case "\$1" in
  --version) echo "Python $ver [PyPy 7.3.x]" ;;
  -c)
    shift
    code="\$1"
    real_py='$REAL_PY'
    "\$real_py" -S -c "
import sys, types
parts = '$ver'.split('.')
major = int(parts[0])
minor = int(parts[1]) if len(parts) > 1 else 0
patch = int(parts[2]) if len(parts) > 2 else 0
class _VI(tuple):
    @property
    def major(self): return self[0]
    @property
    def minor(self): return self[1]
    @property
    def micro(self): return self[2]
sys.version_info = _VI((major, minor, patch, 'final', 0))
# See the cpython stub for why this copies the real namespace.
_real_impl = sys.implementation
sys.implementation = types.SimpleNamespace(
    **{k: getattr(_real_impl, k) for k in dir(_real_impl) if not k.startswith('__')})
sys.implementation.name = 'pypy'
exec(compile('''\$code''', '<stub>', 'exec'))
"
    ;;
  *) echo "stub:pypy:$ver:\$@" ;;
esac
STUB
    chmod +x "$path"
}

# Always provide a CPython fallback at the SCRATCH path so require_ait_python
# can resolve when the test isn't asserting PyPy.
make_cpython_stub python3 "3.13.0"
ln -sf "$SCRATCH/bin/python3" "$SCRATCH/.aitask/bin/python3"

# === Test 1: AIT_USE_PYPY=1 with no PyPy installed -> die ===
unset _AIT_RESOLVED_PYPY
rm -f "$SCRATCH/.aitask/pypy_venv/bin/python"
output="$(HOME="$SCRATCH" PATH="$SUBPATH" AIT_USE_PYPY=1 "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
require_ait_python_fast
" 2>&1 || true)"
assert_contains "Test 1: AIT_USE_PYPY=1 with no PyPy dies" "PyPy not found" "$output"

# === Test 2: AIT_USE_PYPY=1 with PyPy stub -> returns PyPy path ===
make_pypy_stub "$SCRATCH/.aitask/pypy_venv/bin/python" "3.11.0"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" AIT_USE_PYPY=1 "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
require_ait_python_fast
")"
assert_eq "Test 2: AIT_USE_PYPY=1 with PyPy returns PyPy path" "$SCRATCH/.aitask/pypy_venv/bin/python" "$result"

# === Test 3: AIT_USE_PYPY=0 with PyPy installed -> returns CPython (not PyPy) ===
result="$(HOME="$SCRATCH" PATH="$SUBPATH" AIT_USE_PYPY=0 "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
require_ait_python_fast
")"
# Must not be the PyPy path
if [[ "$result" == "$SCRATCH/.aitask/pypy_venv/bin/python" ]]; then
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "FAIL: Test 3: AIT_USE_PYPY=0 should not return PyPy path"
    echo "  actual: $result"
else
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
fi

# === Test 4: AIT_USE_PYPY unset + PyPy installed -> auto-PyPy ===
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY AIT_USE_PYPY
source '$LIB'
require_ait_python_fast
")"
assert_eq "Test 4: unset+PyPy auto-PyPy" "$SCRATCH/.aitask/pypy_venv/bin/python" "$result"

# === Test 5: AIT_USE_PYPY unset + no PyPy -> falls back to CPython ===
rm -f "$SCRATCH/.aitask/pypy_venv/bin/python"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY AIT_USE_PYPY
source '$LIB'
require_ait_python_fast
")"
assert_eq "Test 5: unset+no PyPy falls back to CPython" "$SCRATCH/.aitask/bin/python3" "$result"

# === Test 6: AIT_PYPY override resolves an explicit interpreter ===
make_pypy_stub "$SCRATCH/bin/custom_pypy" "3.11.5"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" AIT_PYPY="$SCRATCH/bin/custom_pypy" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY
source '$LIB'
resolve_pypy_python
")"
assert_eq "Test 6: AIT_PYPY override wins" "$SCRATCH/bin/custom_pypy" "$result"

# === Test 7: misnamed CPython at PYPY_VENV_DIR is rejected (impl != pypy) ===
make_cpython_stub fakepy "3.11.0"
mkdir -p "$SCRATCH/.aitask/pypy_venv/bin"
ln -sf "$SCRATCH/bin/fakepy" "$SCRATCH/.aitask/pypy_venv/bin/python"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
resolve_pypy_python
")"
# Should not return the fake CPython at the venv path; should be empty (no pypy3 on PATH stub)
if [[ "$result" == "$SCRATCH/.aitask/pypy_venv/bin/python" ]]; then
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "FAIL: Test 7: misnamed CPython at PYPY_VENV_DIR should be rejected"
    echo "  actual: $result"
else
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
fi

# === Test 9: misnamed CPython on PATH (pypy3) is rejected (impl != pypy) ===
unset _AIT_RESOLVED_PYPY
rm -f "$SCRATCH/.aitask/pypy_venv/bin/python"
make_cpython_stub pypy3 "3.11.0"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
resolve_pypy_python
")"
if [[ "$result" == "$SCRATCH/bin/pypy3" ]]; then
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "FAIL: Test 9: misnamed CPython on PATH should be rejected"
    echo "  actual: $result"
else
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
fi
rm -f "$SCRATCH/bin/pypy3"

# === Test 10: a REAL PyPy on PATH that cannot see the deps is rejected ===
# Identity is not sufficient. `pypy3` on PATH is a resolution candidate, so a
# system PyPy installed for unrelated reasons — or the very interpreter a
# now-removed pypy_venv was built from — used to be selected for `ait board`,
# which then died at `import textual`. It is also what made setup_pypy_venv's
# "remove the venv so the board falls back to CPython" degrade a no-op.
unset _AIT_RESOLVED_PYPY
rm -f "$SCRATCH/.aitask/pypy_venv/bin/python" "$SCRATCH/bin/pypy3"
make_pypy_stub "$SCRATCH/bin/pypy3" "3.11.0" none   # genuine PyPy, no deps
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
resolve_pypy_python
")"
assert_eq "Test 10: dep-bare PyPy on PATH is not resolved" "" "$result"

# ...and the caller therefore lands on CPython instead of a doomed PyPy.
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY AIT_USE_PYPY
source '$LIB'
require_ait_python_fast
")"
assert_eq "Test 10: fast path falls back to CPython when PyPy lacks deps" \
    "$SCRATCH/.aitask/bin/python3" "$result"

# === Test 11: textual present but the REST of the runtime set missing ===
# `ait board` imports yaml directly as well as Textual, so "has textual" is not
# the contract — "can provide the whole runtime set" is.
unset _AIT_RESOLVED_PYPY
make_pypy_stub "$SCRATCH/bin/pypy3" "3.11.0" partial   # textual yes, yaml no
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
resolve_pypy_python
")"
assert_eq "Test 11: PyPy with textual but no yaml is rejected" "" "$result"

# === Test 12: every module DISCOVERABLE, but textual fails to import ===
# find_spec() answers "present" for a package whose __init__ raises — a broken
# install, or a missing transitive dependency of Textual itself. Only an actual
# import distinguishes them, which is why the probe imports.
unset _AIT_RESOLVED_PYPY
make_pypy_stub "$SCRATCH/bin/pypy3" "3.11.0" broken
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
resolve_pypy_python
")"
assert_eq "Test 12: discoverable-but-unimportable textual is rejected" "" "$result"

# Positive control for Tests 10-12: the SAME stub with the complete, working
# runtime set IS selected — so the three rejections above are about the
# dependencies, not about the stub being unusable in general.
unset _AIT_RESOLVED_PYPY
make_pypy_stub "$SCRATCH/bin/pypy3" "3.11.0" full
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
resolve_pypy_python
")"
assert_eq "Tests 10-12: same PyPy with the FULL runtime set is resolved (control)" \
    "$SCRATCH/bin/pypy3" "$result"
rm -f "$SCRATCH/bin/pypy3"

# === Test 8: double-source guard preserves new functions ===
result="$("$TEST_BASH" --noprofile --norc -c "
source '$LIB'
source '$LIB'
declare -F resolve_pypy_python >/dev/null && \
declare -F require_ait_pypy >/dev/null && \
declare -F require_ait_python_fast >/dev/null && echo OK || echo MISSING
")"
assert_eq "Test 8: double-source guard preserves PyPy functions" "OK" "$result"

echo ""
echo "Tests: $TOTAL  Pass: $PASS  Fail: $FAIL"
if (( FAIL > 0 )); then
    exit 1
fi
